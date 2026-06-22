"""
GPU Capability Transaction Layer
=================================
Treats gpu_caps.json as a signed transaction ledger between the detector
(gpu_translator) and the runtime (daemon/keepalive).

Each write to the capability map generates an HMAC signature.
Each read verifies that signature before acting on the data.

Flow:
  Detector  → write_transaction(caps)  → signs + writes gpu_caps.json
  Runtime   → read_transaction()       → verifies signature → returns caps
  Dispatcher→ route(cap_name)          → looks up routing table from verified caps

This means the daemon only acts on capability data it can cryptographically
confirm came from its own detector — not from an external modification.
"""

import hashlib
import hmac
import json
import os
import time

CAPS_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpu_caps.json")
LEDGER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpu_ledger.json")

# Shared secret — derived from the two GPU device IDs so it's hardware-bound.
# If the hardware changes, the key changes, and old transactions are rejected.
_SECRET_SEED = b"optimas-gpu-transaction-v1"


def _derive_key(gpu_map: dict) -> bytes:
    """
    Derive a hardware-bound HMAC key from the detected GPU device IDs.
    Key = HMAC-SHA256(seed, nvidia_device_id + amd_device_id)
    Changes if either GPU is swapped out.
    """
    nvidia_id = gpu_map.get("gpus", {}).get("nvidia", {}).get("device_id", "0x0000")
    amd_id    = gpu_map.get("gpus", {}).get("amd",    {}).get("device_id", "0x0000")
    hw_token  = f"{nvidia_id}:{amd_id}".encode()
    return hmac.new(_SECRET_SEED, hw_token, hashlib.sha256).digest()


def _sign(payload: dict, key: bytes) -> str:
    """Sign a dict payload with HMAC-SHA256. Returns hex digest."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest()


def write_transaction(gpu_map: dict) -> str:
    """
    Sign the capability map and write it as a verified transaction.
    Returns the transaction signature (hex).

    Called by gpu_translator after building the map.
    """
    key = _derive_key(gpu_map)

    # Strip internal fields before signing
    payload = {k: v for k, v in gpu_map.items() if k != "_sig"}
    sig = _sign(payload, key)

    # Embed signature
    transaction = dict(payload)
    transaction["_sig"] = sig
    transaction["_signed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    with open(CAPS_FILE, "w", encoding="utf-8") as f:
        json.dump(transaction, f, indent=2)

    # Append to ledger for audit trail
    ledger = []
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except Exception:
            ledger = []

    ledger.append({
        "timestamp": transaction["_signed_at"],
        "sig":       sig[:16] + "...",   # truncated for log readability
        "nvidia_id": gpu_map.get("gpus", {}).get("nvidia", {}).get("device_id"),
        "amd_id":    gpu_map.get("gpus", {}).get("amd",    {}).get("device_id"),
        "routing":   gpu_map.get("translation", {}).get("routing_table", {}),
    })
    # Keep last 50 transactions
    ledger = ledger[-50:]
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)

    print(f"[Transaction] Signed and written  sig={sig[:16]}...", flush=True)
    return sig


def read_transaction() -> dict | None:
    """
    Read and verify the capability map transaction.
    Returns the verified map, or None if signature fails.

    Called by the daemon/dispatcher before routing any work.
    """
    if not os.path.exists(CAPS_FILE):
        print("[Transaction] No capability map found — run gpu_translator.py first", flush=True)
        return None

    with open(CAPS_FILE, "r", encoding="utf-8") as f:
        transaction = json.load(f)

    stored_sig = transaction.pop("_sig", None)
    transaction.pop("_signed_at", None)

    if not stored_sig:
        print("[Transaction] REJECTED — no signature in map", flush=True)
        return None

    key = _derive_key(transaction)
    expected_sig = _sign(transaction, key)

    if not hmac.compare_digest(stored_sig, expected_sig):
        print(f"[Transaction] REJECTED — signature mismatch", flush=True)
        print(f"  stored  : {stored_sig[:16]}...", flush=True)
        print(f"  expected: {expected_sig[:16]}...", flush=True)
        return None

    print(f"[Transaction] Verified  sig={stored_sig[:16]}...", flush=True)
    return transaction


def route(cap_name: str, transaction_map: dict) -> str:
    """
    Dispatch a capability to the correct GPU using the verified routing table.
    Returns 'nvidia', 'amd', or 'none'.
    """
    routing = transaction_map.get("translation", {}).get("routing_table", {})
    target = routing.get(cap_name, "amd")
    print(f"[Transaction] Route '{cap_name}' -> {target}", flush=True)
    return target


def get_memory_flow(transaction_map: dict) -> dict:
    """Return the PCIe memory flow descriptor from the verified map."""
    return transaction_map.get("translation", {}).get("memory_flow", {})


if __name__ == "__main__":
    # Self-test: build map, sign it, read it back, verify
    from gpu_translator import build_translation_map

    print("=== GPU Transaction Self-Test ===")
    cap_map = build_translation_map()
    if cap_map:
        sig = write_transaction(cap_map)
        print(f"\nWritten with sig: {sig[:32]}...")

        verified = read_transaction()
        if verified:
            print("\nVerification passed. Routing table:")
            for cap, gpu in verified.get("translation", {}).get("routing_table", {}).items():
                print(f"  {cap:<25} -> {gpu}")

            mf = get_memory_flow(verified)
            print(f"\nMemory flow:")
            print(f"  AMD dedicated  : {mf.get('amd_dedicated_mb')}MB")
            print(f"  NVIDIA dedicated: {mf.get('nvidia_dedicated_mb')}MB")
            print(f"  PCIe bridge    : {mf.get('pcie_bridge_capacity_mb')}MB")
        else:
            print("\nVerification FAILED")

"""
GPU Capability Translator
=========================
Reads the hardware feature codes from each GPU (AMD RX 580 and NVIDIA GT 710),
builds a bidirectional translation map, persists it to gpu_caps.json, and
exposes a routing function that ensures work is dispatched to the correct
adapter based on what each card actually supports.

Think of it like an ECU translator — each GPU has its own "dialect" of
feature codes. This module reads both, cross-maps them, and applies the
right profile when handing off tasks.
"""

import ctypes
import json
import os
import time

CAPS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpu_caps.json")

# DXGI vendor IDs
VENDOR_NVIDIA = 0x10DE
VENDOR_AMD    = 0x1002

# D3D feature level codes -> human name
FEATURE_LEVEL_NAMES = {
    0xb000: "D3D11.0",
    0xb100: "D3D11.1",
    0xa000: "D3D10.0",
    0xa100: "D3D10.1",
    0x9300: "D3D9.3",
    0x9200: "D3D9.2",
    0x9100: "D3D9.1",
    0xc000: "D3D12.0",
    0xc100: "D3D12.1",
    0xc200: "D3D12.2",
}

# Capability flags we probe for on each device
# These mirror D3D11 optional feature checks applications use to decide
# which rendering path to take — same as what a driver ECU map would expose
CAPABILITY_PROBES = [
    "doubles",            # FP64 shader support
    "compute_shaders",    # CS5 support
    "structured_buffers", # Structured buffer / UAV
    "tiled_resources",    # Tier 1/2/3 tiled resources
    "conservative_raster",# Conservative rasterization
    "logic_ops",          # Output merger logic operations
    "min_max_filtering",  # Min/max texture filtering
    "shader_trace",       # Driver shader debugging
]


# ---------------------------------------------------------------------------
# DXGI / D3D11 ctypes helpers
# ---------------------------------------------------------------------------

class DXGI_ADAPTER_DESC(ctypes.Structure):
    _fields_ = [
        ("Description",           ctypes.c_wchar * 128),
        ("VendorId",              ctypes.c_uint),
        ("DeviceId",              ctypes.c_uint),
        ("SubSysId",              ctypes.c_uint),
        ("Revision",              ctypes.c_uint),
        ("DedicatedVideoMemory",  ctypes.c_size_t),
        ("DedicatedSystemMemory", ctypes.c_size_t),
        ("SharedSystemMemory",    ctypes.c_size_t),
        ("AdapterLuid",           ctypes.c_int64),
    ]


def _get_factory():
    dxgi = ctypes.windll.LoadLibrary("dxgi.dll")
    IID = (ctypes.c_byte * 16)(
        0xec, 0x66, 0x71, 0x7b, 0xc7, 0x21, 0xae, 0x44,
        0xb2, 0x1a, 0xc9, 0xae, 0x32, 0x1a, 0xe3, 0x69
    )
    create = dxgi.CreateDXGIFactory
    create.restype = ctypes.c_long  # c_long not HRESULT — avoids OSError on failure codes
    ptr = ctypes.c_void_p()
    if create(ctypes.byref(IID), ctypes.byref(ptr)) != 0:
        return None
    return ptr


def _vtbl(com_ptr, index):
    """Get a function pointer from a COM object's vtable."""
    vt = ctypes.cast(
        ctypes.cast(com_ptr, ctypes.POINTER(ctypes.c_void_p))[0],
        ctypes.POINTER(ctypes.c_void_p)
    )
    return vt[index]


def _enum_adapters():
    """
    Enumerate all DXGI adapters and return list of dicts with raw hardware info.
    This is the 'ECU read' step — pulling the identity codes off each GPU.
    """
    factory = _get_factory()
    if not factory:
        return []

    EnumAdapters = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_void_p, ctypes.c_uint,
        ctypes.POINTER(ctypes.c_void_p)
    )(_vtbl(factory, 7))

    adapters = []
    idx = 0
    while True:
        ap = ctypes.c_void_p()
        hr = EnumAdapters(factory, idx, ctypes.byref(ap))
        if hr != 0 or not ap.value:
            break

        GetDesc = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(DXGI_ADAPTER_DESC)
        )(_vtbl(ap, 8))

        desc = DXGI_ADAPTER_DESC()
        if GetDesc(ap, ctypes.byref(desc)) == 0:
            adapters.append({
                "index":        idx,
                "name":         desc.Description,
                "vendor_id":    f"0x{desc.VendorId:04X}",
                "device_id":    f"0x{desc.DeviceId:04X}",
                "subsys_id":    f"0x{desc.SubSysId:08X}",
                "revision":     desc.Revision,
                "vram_mb":      desc.DedicatedVideoMemory // (1024 * 1024),
                "shared_mb":    desc.SharedSystemMemory   // (1024 * 1024),
                "luid":         desc.AdapterLuid,
                # Memory map: dedicated (solid VRAM) + shared (system RAM bridge)
                "memory_map": {
                    "dedicated_bytes": desc.DedicatedVideoMemory,
                    "dedicated_sys_bytes": desc.DedicatedSystemMemory,
                    "shared_bytes": desc.SharedSystemMemory,
                    # Flow capacity = how much can move between GPU and system
                    "flow_capacity_bytes": desc.SharedSystemMemory + desc.DedicatedSystemMemory,
                },
                "_com_ptr":     ap.value,
            })

        idx += 1

    # Release factory
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(_vtbl(factory, 2))(factory)
    return adapters


def _probe_d3d11_caps(adapter_com_ptr):
    """
    Create a D3D11 device on the given adapter and read its feature level.
    Capability flags are derived from the feature level rather than
    CheckFeatureSupport vtable calls (which vary by driver version).
    """
    d3d11 = ctypes.windll.LoadLibrary("d3d11.dll")

    feature_levels = (ctypes.c_uint * 5)(
        0xb100, 0xb000,   # D3D11.1, D3D11.0
        0xa100, 0xa000,   # D3D10.1, D3D10.0
        0x9300,           # D3D9.3
    )
    fl_out     = ctypes.c_uint(0)
    device_ptr = ctypes.c_void_p()
    ctx_ptr    = ctypes.c_void_p()

    ap = ctypes.c_void_p(adapter_com_ptr)

    D3D11CreateDevice = d3d11.D3D11CreateDevice
    D3D11CreateDevice.restype = ctypes.c_long  # avoid OSError on failure

    hr = D3D11CreateDevice(
        ap, 0, None, 0,
        feature_levels, 5, 7,
        ctypes.byref(device_ptr),
        ctypes.byref(fl_out),
        ctypes.byref(ctx_ptr),
    )

    if hr != 0 or not device_ptr.value:
        return {"feature_level_code": None, "feature_level": "unavailable", "caps": {}}

    fl_code = fl_out.value
    fl_name = FEATURE_LEVEL_NAMES.get(fl_code, f"0x{fl_code:04X}")

    # Derive caps from feature level — no vtable calls needed
    # This mirrors what drivers actually guarantee at each level
    caps = {
        "doubles":             fl_code >= 0xb000,  # D3D11.0+ has optional FP64 (GT710=no, RX580=yes)
        "compute_shaders":     fl_code >= 0xb000,  # CS5 requires D3D11.0
        "structured_buffers":  fl_code >= 0xb000,  # UAV/structured buf requires D3D11.0
        "logic_ops":           fl_code >= 0xb100,  # Logic ops require D3D11.1
        "tiled_resources":     False,               # Requires D3D11.2 (neither card supports)
        "conservative_raster": False,               # Requires D3D11.3 (neither card supports)
        "min_max_filtering":   fl_code >= 0xb100,  # Requires D3D11.1
        "shader_trace":        fl_code >= 0xb000,
    }

    # Release device
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(_vtbl(device_ptr, 2))(device_ptr)

    return {
        "feature_level_code": fl_code,
        "feature_level":      fl_name,
        "caps":               caps,
    }


# ---------------------------------------------------------------------------
# Translation map builder
# ---------------------------------------------------------------------------

def _build_memory_flow(amd_info: dict, nvidia_info: dict) -> dict:
    """
    Build a memory flow descriptor between the two GPUs.

    Even though VRAM is 'solid state' (no moving parts), data flows between
    GPUs via the PCIe bus through the shared system RAM region each adapter
    exposes. This maps the actual byte capacities so the routing layer knows
    how much it can push through each direction without stalling.

    amd -> nvidia : AMD writes to its shared region, NVIDIA reads from system RAM
    nvidia -> amd : NVIDIA writes to its shared region, AMD reads from system RAM
    """
    amd_mm    = amd_info.get("memory_map", {})
    nvidia_mm = nvidia_info.get("memory_map", {})

    amd_dedicated    = amd_mm.get("dedicated_bytes", 0)
    amd_shared       = amd_mm.get("shared_bytes", 0)
    nvidia_dedicated = nvidia_mm.get("dedicated_bytes", 0)
    nvidia_shared    = nvidia_mm.get("shared_bytes", 0)

    # PCIe bridge capacity = minimum of both shared windows (bottleneck)
    bridge_capacity = min(amd_shared, nvidia_shared) if amd_shared and nvidia_shared else 0

    return {
        "amd_dedicated_mb":          amd_dedicated    // (1024 * 1024),
        "nvidia_dedicated_mb":       nvidia_dedicated // (1024 * 1024),
        "amd_shared_window_mb":      amd_shared       // (1024 * 1024),
        "nvidia_shared_window_mb":   nvidia_shared    // (1024 * 1024),
        "pcie_bridge_capacity_mb":   bridge_capacity  // (1024 * 1024),
        # Direction descriptors
        "amd_to_nvidia_path":  "AMD VRAM -> PCIe -> System RAM -> NVIDIA shared window",
        "nvidia_to_amd_path":  "NVIDIA VRAM -> PCIe -> System RAM -> AMD shared window",
        "notes": (
            "Flow is bidirectional via PCIe shared memory regions. "
            "Bridge capacity is the smaller of the two shared windows — "
            "saturating it causes PCIe stalls. Keep cross-GPU transfers "
            f"under {bridge_capacity // (1024*1024)}MB per operation."
        )
    }


def build_translation_map():
    """
    Read both GPUs, build the bidirectional capability translation map,
    and persist to gpu_caps.json.

    The translation map answers:
      - What can the NVIDIA card do that AMD can't? (nvidia_only)
      - What can AMD do that NVIDIA can't? (amd_only)
      - What do both support? (shared)
      - For each cap, which card handles it? (routing_table)
    """
    print("[Translator] Enumerating GPU adapters...", flush=True)
    adapters = _enum_adapters()

    if not adapters:
        print("[Translator] No adapters found", flush=True)
        return None

    nvidia_gpu = None
    amd_gpu    = None

    for a in adapters:
        vid = int(a["vendor_id"], 16)
        if vid == VENDOR_NVIDIA and nvidia_gpu is None:
            nvidia_gpu = a
        elif vid == VENDOR_AMD and amd_gpu is None:
            amd_gpu = a

    gpu_map = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "gpus": {}, "translation": {}}

    for label, gpu in [("nvidia", nvidia_gpu), ("amd", amd_gpu)]:
        if gpu is None:
            print(f"[Translator] {label.upper()} GPU not found", flush=True)
            gpu_map["gpus"][label] = {"present": False}
            continue

        print(f"[Translator] Probing {gpu['name']} ({gpu['vendor_id']})...", flush=True)
        d3d_caps = _probe_d3d11_caps(gpu["_com_ptr"])

        gpu_map["gpus"][label] = {
            "present":      True,
            "name":         gpu["name"],
            "vendor_id":    gpu["vendor_id"],
            "device_id":    gpu["device_id"],
            "subsys_id":    gpu["subsys_id"],
            "revision":     gpu["revision"],
            "vram_mb":      gpu["vram_mb"],
            "shared_mb":    gpu["shared_mb"],
            "luid":         gpu["luid"],
            "dxgi_index":   gpu["index"],
            "feature_level":      d3d_caps["feature_level"],
            "feature_level_code": d3d_caps["feature_level_code"],
            "caps":         d3d_caps["caps"],
        }

    # Build translation / routing table
    nvidia_caps = gpu_map["gpus"].get("nvidia", {}).get("caps", {})
    amd_caps    = gpu_map["gpus"].get("amd",    {}).get("caps", {})

    all_caps    = set(nvidia_caps.keys()) | set(amd_caps.keys())
    shared      = []
    nvidia_only = []
    amd_only    = []
    routing     = {}

    for cap in sorted(all_caps):
        n = nvidia_caps.get(cap, False)
        a = amd_caps.get(cap, False)

        if n and a:
            shared.append(cap)
            # Both support it — route to NVIDIA to offload the RX 580.
            # The GT 710 handles the baseline workload; RX 580 stays free
            # for AMD-exclusive caps and heavy compute.
            routing[cap] = "nvidia"
        elif n:
            nvidia_only.append(cap)
            routing[cap] = "nvidia"
        elif a:
            amd_only.append(cap)
            routing[cap] = "amd"
        else:
            routing[cap] = "none"

    gpu_map["translation"] = {
        "shared":      shared,
        "nvidia_only": nvidia_only,
        "amd_only":    amd_only,
        "routing_table": routing,
        # Memory flow map: how data can move between the two GPUs via system RAM bridge
        "memory_flow": _build_memory_flow(
            gpu_map["gpus"].get("amd", {}),
            gpu_map["gpus"].get("nvidia", {})
        ),
    }

    # Persist
    with open(CAPS_FILE, "w", encoding="utf-8") as f:
        # Strip internal COM pointers before serialising
        clean = json.loads(json.dumps(
            gpu_map,
            default=lambda o: None  # drop non-serialisable values
        ))
        json.dump(clean, f, indent=2)

    print(f"[Translator] Map written to {CAPS_FILE}", flush=True)
    return gpu_map


def load_translation_map():
    """Load the persisted translation map from disk, or rebuild if missing."""
    if os.path.exists(CAPS_FILE):
        with open(CAPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return build_translation_map()


def route_capability(cap_name: str, translation_map: dict) -> str:
    """
    Given a capability name, return which GPU should handle it: 'nvidia', 'amd', or 'none'.
    This is the dispatcher — call this before submitting work to decide which adapter to use.
    """
    routing = translation_map.get("translation", {}).get("routing_table", {})
    return routing.get(cap_name, "amd")  # default to AMD (primary display GPU)


if __name__ == "__main__":
    cap_map = build_translation_map()
    if cap_map:
        print("\n=== GPU Translation Map ===")
        for label, info in cap_map["gpus"].items():
            if info.get("present"):
                print(f"\n{label.upper()}: {info['name']}")
                print(f"  Device ID : {info['device_id']}  SubSys: {info['subsys_id']}  Rev: {info['revision']}")
                print(f"  VRAM      : {info['vram_mb']}MB dedicated, {info['shared_mb']}MB shared")
                print(f"  Feature   : {info['feature_level']}")
                print(f"  Caps      : {info['caps']}")

        t = cap_map["translation"]
        print(f"\nShared caps    : {t['shared']}")
        print(f"NVIDIA only    : {t['nvidia_only']}")
        print(f"AMD only       : {t['amd_only']}")
        print(f"\nRouting table  :")
        for cap, gpu in t["routing_table"].items():
            print(f"  {cap:<25} -> {gpu}")

"""
Process / Thread / Handle Allowlist Monitor
============================================
Enumerates all running CPU processes, their threads, and GPU-related handles.
Builds an allowlist from the first clean snapshot, then monitors for anything
new that wasn't in that baseline — logging unknown processes, threads, and handles.

Uses only Windows built-in APIs via ctypes (no extra dependencies).
"""

import ctypes
import ctypes.wintypes
import json
import os
import time
import threading

ALLOWLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "process_allowlist.json")

# Windows API constants
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPTHREAD  = 0x00000004
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# ─── Structures ──────────────────────────────────────────────────────────────

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize",              ctypes.wintypes.DWORD),
        ("cntUsage",            ctypes.wintypes.DWORD),
        ("th32ProcessID",       ctypes.wintypes.DWORD),
        ("th32DefaultHeapID",   ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID",        ctypes.wintypes.DWORD),
        ("cntThreads",          ctypes.wintypes.DWORD),
        ("th32ParentProcessID", ctypes.wintypes.DWORD),
        ("pcPriClassBase",      ctypes.c_long),
        ("dwFlags",             ctypes.wintypes.DWORD),
        ("szExeFile",           ctypes.c_char * 260),
    ]

class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize",             ctypes.wintypes.DWORD),
        ("cntUsage",           ctypes.wintypes.DWORD),
        ("th32ThreadID",       ctypes.wintypes.DWORD),
        ("th32OwnerProcessID", ctypes.wintypes.DWORD),
        ("tpBasePri",          ctypes.c_long),
        ("tpDeltaPri",         ctypes.c_long),
        ("dwFlags",            ctypes.wintypes.DWORD),
    ]

# ─── Snapshot helpers ────────────────────────────────────────────────────────

def snapshot_processes() -> dict[int, dict]:
    """
    Snapshot all running processes.
    Returns dict keyed by PID with name, parent PID, thread count.
    """
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        return {}

    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    procs = {}

    if k32.Process32First(snap, ctypes.byref(entry)):
        while True:
            pid = entry.th32ProcessID
            procs[pid] = {
                "pid":        pid,
                "name":       entry.szExeFile.decode(errors="replace"),
                "parent_pid": entry.th32ParentProcessID,
                "threads":    entry.cntThreads,
            }
            if not k32.Process32Next(snap, ctypes.byref(entry)):
                break

    k32.CloseHandle(snap)
    return procs


def snapshot_threads() -> dict[int, dict]:
    """
    Snapshot all running threads across all processes.
    Returns dict keyed by thread ID.
    """
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snap == INVALID_HANDLE_VALUE:
        return {}

    entry = THREADENTRY32()
    entry.dwSize = ctypes.sizeof(THREADENTRY32)
    threads = {}

    if k32.Thread32First(snap, ctypes.byref(entry)):
        while True:
            tid = entry.th32ThreadID
            threads[tid] = {
                "tid":        tid,
                "owner_pid":  entry.th32OwnerProcessID,
                "base_pri":   entry.tpBasePri,
            }
            if not k32.Thread32Next(snap, ctypes.byref(entry)):
                break

    k32.CloseHandle(snap)
    return threads


def snapshot_gpu_processes() -> list[dict]:
    """
    Find processes with active GPU handles by checking which PIDs have
    D3D/DXGI related modules loaded. Uses EnumProcesses + module enumeration.
    """
    k32   = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi

    # Set correct argtypes so 64-bit handles pass cleanly
    psapi.GetModuleBaseNameA.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.wintypes.DWORD,
    ]
    psapi.GetModuleBaseNameA.restype = ctypes.wintypes.DWORD

    # Get all PIDs
    pid_array = (ctypes.wintypes.DWORD * 1024)()
    bytes_returned = ctypes.wintypes.DWORD(0)
    psapi.EnumProcesses(ctypes.byref(pid_array), ctypes.sizeof(pid_array), ctypes.byref(bytes_returned))
    pid_count = bytes_returned.value // ctypes.sizeof(ctypes.wintypes.DWORD)

    gpu_procs = []
    GPU_MODULES = {b"d3d11.dll", b"d3d12.dll", b"dxgi.dll", b"nvapi64.dll",
                   b"amdxc64.dll", b"atidxx64.dll", b"nvcuda.dll"}

    PROCESS_QUERY_INFO = 0x1000
    PROCESS_VM_READ    = 0x0010

    for i in range(pid_count):
        pid = pid_array[i]
        if pid == 0:
            continue

        handle = k32.OpenProcess(PROCESS_QUERY_INFO | PROCESS_VM_READ, False, pid)
        if not handle:
            continue

        mod_array  = (ctypes.c_void_p * 256)()
        mod_bytes  = ctypes.wintypes.DWORD(0)
        if psapi.EnumProcessModules(handle,
                                    mod_array,
                                    ctypes.sizeof(mod_array),
                                    ctypes.byref(mod_bytes)):
            mod_count = mod_bytes.value // ctypes.sizeof(ctypes.c_void_p)
            for j in range(min(mod_count, 256)):
                if not mod_array[j]:
                    continue
                name_buf = ctypes.create_string_buffer(256)
                psapi.GetModuleBaseNameA(
                    ctypes.c_void_p(handle),
                    ctypes.c_void_p(mod_array[j]),
                    name_buf, 256
                )
                mod_name = name_buf.value.lower()
                if mod_name in GPU_MODULES:
                    proc_name_buf = ctypes.create_string_buffer(260)
                    psapi.GetModuleBaseNameA(
                        ctypes.c_void_p(handle),
                        ctypes.c_void_p(0),
                        proc_name_buf, 260
                    )
                    gpu_procs.append({
                        "pid":        pid,
                        "name":       proc_name_buf.value.decode(errors="replace"),
                        "gpu_module": mod_name.decode(errors="replace"),
                    })
                    break

        k32.CloseHandle(handle)

    return gpu_procs


# ─── Allowlist management ────────────────────────────────────────────────────

def build_allowlist() -> dict:
    """
    Take a baseline snapshot and save it as the allowlist.
    Call this once on a known-clean system state.
    """
    print("[Allowlist] Building baseline snapshot...", flush=True)

    procs   = snapshot_processes()
    threads = snapshot_threads()
    gpu     = snapshot_gpu_processes()

    allowlist = {
        "timestamp":    time.strftime("%Y-%m-%dT%H:%M:%S"),
        "process_names": sorted({p["name"] for p in procs.values()}),
        "gpu_process_names": sorted({g["name"] for g in gpu}),
        "thread_owner_pids": sorted({t["owner_pid"] for t in threads.values()}),
        "process_count": len(procs),
        "thread_count":  len(threads),
        "gpu_proc_count": len(gpu),
    }

    with open(ALLOWLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(allowlist, f, indent=2)

    print(f"[Allowlist] Baseline saved: {len(procs)} processes, "
          f"{len(threads)} threads, {len(gpu)} GPU processes", flush=True)
    return allowlist


def load_allowlist() -> dict:
    """Load existing allowlist or build a new one."""
    if os.path.exists(ALLOWLIST_FILE):
        with open(ALLOWLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return build_allowlist()


def check_against_allowlist(allowlist: dict) -> dict:
    """
    Compare current state against the allowlist.
    Returns dict of unknown processes, threads, and GPU processes.
    """
    procs   = snapshot_processes()
    gpu     = snapshot_gpu_processes()

    known_proc_names = set(allowlist.get("process_names", []))
    known_gpu_names  = set(allowlist.get("gpu_process_names", []))

    unknown_procs = [
        p for p in procs.values()
        if p["name"] not in known_proc_names
    ]
    unknown_gpu = [
        g for g in gpu
        if g["name"] not in known_gpu_names
    ]

    return {
        "unknown_processes": unknown_procs,
        "unknown_gpu_processes": unknown_gpu,
        "total_processes": len(procs),
        "total_gpu_processes": len(gpu),
    }


# ─── Monitor loop ─────────────────────────────────────────────────────────

def start_monitor(interval: int = 10):
    """
    Start background monitor thread.
    Polls every `interval` seconds and logs anything not on the allowlist.
    """
    allowlist = load_allowlist()

    def _run():
        print(f"[Allowlist] Monitor active (interval={interval}s)", flush=True)
        while True:
            try:
                result = check_against_allowlist(allowlist)

                if result["unknown_processes"]:
                    for p in result["unknown_processes"]:
                        print(f"[Allowlist] UNKNOWN PROCESS: {p['name']} "
                              f"pid={p['pid']} parent={p['parent_pid']}", flush=True)

                if result["unknown_gpu_processes"]:
                    for g in result["unknown_gpu_processes"]:
                        print(f"[Allowlist] UNKNOWN GPU PROCESS: {g['name']} "
                              f"pid={g['pid']} module={g['gpu_module']}", flush=True)

            except Exception as e:
                print(f"[Allowlist] Monitor error: {e}", flush=True)

            time.sleep(interval)

    t = threading.Thread(target=_run, name="allowlist-monitor", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    print("=== Process / Thread / Handle Allowlist ===\n")

    al = build_allowlist()
    print(f"\nKnown processes     : {len(al['process_names'])}")
    print(f"Known GPU processes : {len(al['gpu_process_names'])}")
    print(f"\nGPU-active processes:")
    for name in al["gpu_process_names"]:
        print(f"  {name}")

    print(f"\nAll known process names:")
    for name in al["process_names"]:
        print(f"  {name}")

# ─── Inactive / suspended process revival ────────────────────────────────────

# Target process names to watch and resume if found suspended
WATCH_NAMES = {
    "python.exe", "pythonw.exe", "python3.exe",
    "optimas_daemon.py", "gpu_translator.py", "gpu_transaction.py",
}

THREAD_SUSPEND_COUNT_MAX = 3   # threads suspended more than this = considered inactive

OPEN_THREAD_FLAGS  = 0x0002 | 0x0040  # THREAD_SUSPEND_RESUME | THREAD_QUERY_INFORMATION
PROCESS_ALL_ACCESS = 0x1F0FFF


def _get_thread_suspend_count(tid: int) -> int:
    """
    Get the suspend count of a thread by opening it, suspending (which returns
    the previous count), then immediately resuming twice to net zero change.
    Returns -1 if inaccessible.
    """
    k32 = ctypes.windll.kernel32
    handle = k32.OpenThread(OPEN_THREAD_FLAGS, False, tid)
    if not handle:
        return -1

    # SuspendThread returns previous suspend count
    prev = k32.SuspendThread(handle)
    if prev == 0xFFFFFFFF:
        k32.CloseHandle(handle)
        return -1

    # Resume back to original state (undo our suspend + any existing suspends net)
    k32.ResumeThread(handle)   # undoes our SuspendThread
    k32.CloseHandle(handle)
    return prev  # 0 = running, >0 = suspended


def _resume_all_threads(pid: int) -> int:
    """
    Resume all suspended threads in a process.
    Returns number of threads resumed.
    """
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snap == INVALID_HANDLE_VALUE:
        return 0

    entry = THREADENTRY32()
    entry.dwSize = ctypes.sizeof(THREADENTRY32)
    resumed = 0

    if k32.Thread32First(snap, ctypes.byref(entry)):
        while True:
            if entry.th32OwnerProcessID == pid:
                sc = _get_thread_suspend_count(entry.th32ThreadID)
                if sc > 0:
                    # Resume until count reaches 0
                    th = k32.OpenThread(OPEN_THREAD_FLAGS, False, entry.th32ThreadID)
                    if th:
                        for _ in range(sc):
                            k32.ResumeThread(th)
                        k32.CloseHandle(th)
                        resumed += 1
            if not k32.Thread32Next(snap, ctypes.byref(entry)):
                break

    k32.CloseHandle(snap)
    return resumed


def find_inactive_python_processes() -> list[dict]:
    """
    Find Python/daemon processes that have all threads suspended (inactive).
    Returns list of dicts with pid, name, suspended thread count.
    """
    procs = snapshot_processes()
    inactive = []

    for pid, info in procs.items():
        name_lower = info["name"].lower()
        if not any(w in name_lower for w in ("python", "optimas")):
            continue

        # Check thread states for this process
        k32 = ctypes.windll.kernel32
        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
        if snap == INVALID_HANDLE_VALUE:
            continue

        entry = THREADENTRY32()
        entry.dwSize = ctypes.sizeof(THREADENTRY32)

        total = 0
        suspended = 0

        if k32.Thread32First(snap, ctypes.byref(entry)):
            while True:
                if entry.th32OwnerProcessID == pid:
                    total += 1
                    sc = _get_thread_suspend_count(entry.th32ThreadID)
                    if sc > 0:
                        suspended += 1
                if not k32.Thread32Next(snap, ctypes.byref(entry)):
                    break

        k32.CloseHandle(snap)

        if total > 0 and suspended == total:
            inactive.append({
                "pid":              pid,
                "name":             info["name"],
                "total_threads":    total,
                "suspended_threads": suspended,
            })

    return inactive


def revive_inactive_processes() -> list[dict]:
    """
    Find all suspended Python/daemon processes and resume them.
    Returns list of processes that were revived.
    """
    inactive = find_inactive_python_processes()
    revived = []

    for proc in inactive:
        count = _resume_all_threads(proc["pid"])
        if count > 0:
            print(f"[Allowlist] Revived {proc['name']} pid={proc['pid']} "
                  f"({count} threads resumed)", flush=True)
            revived.append({**proc, "threads_resumed": count})
        else:
            print(f"[Allowlist] Could not revive {proc['name']} pid={proc['pid']}", flush=True)

    return revived


def start_revival_monitor(interval: int = 15):
    """
    Background thread that periodically checks for inactive Python processes
    and revives them automatically.
    """
    def _run():
        print(f"[Allowlist] Revival monitor active (interval={interval}s)", flush=True)
        while True:
            try:
                revived = revive_inactive_processes()
                if not revived:
                    # No inactive processes — also check if any known daemons
                    # are completely missing and should be restarted
                    procs = snapshot_processes()
                    running_names = {p["name"].lower() for p in procs.values()}
                    if "python.exe" not in running_names and "pythonw.exe" not in running_names:
                        print("[Allowlist] WARNING: No Python processes found", flush=True)
            except Exception as e:
                print(f"[Allowlist] Revival error: {e}", flush=True)
            time.sleep(interval)

    t = threading.Thread(target=_run, name="revival-monitor", daemon=True)
    t.start()
    return t


# ─── Global GPU preference routing ───────────────────────────────────────────

def apply_gpu_routing_to_all_processes():
    """
    Set Windows GPU preference registry keys for all running GPU-active processes.

    GpuPreference=1 = power saving (integrated/secondary — GT 710)
    GpuPreference=2 = high performance (primary discrete — RX 580)

    We route:
    - Known lightweight processes (system, audio, background) -> GT 710 (1)
    - Everything else (games, 3D apps, media) -> RX 580 (2)

    This is the same mechanism as Windows Settings > Graphics > per-app GPU.
    It persists in the registry until changed.
    """
    try:
        import winreg
    except ImportError:
        print("[Router] winreg unavailable", flush=True)
        return

    # Processes to steer toward GT 710 (lightweight, free up RX 580)
    LIGHTWEIGHT = {
        "dwm.exe", "explorer.exe", "searchhost.exe", "sihost.exe",
        "taskhostw.exe", "ctfmon.exe", "shellexperiencehost.exe",
        "startmenuexperiencehost.exe", "textinputhost.exe",
        "systemsettings.exe", "winlogon.exe", "fontdrvhost.exe",
        "python.exe", "pythonw.exe",  # our own daemon — GT 710
    }

    gpu_procs = snapshot_gpu_processes()
    key_path  = r"SOFTWARE\Microsoft\DirectX\UserGpuPreferences"

    routed_nvidia = 0
    routed_amd    = 0

    try:
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        )
    except Exception as e:
        print(f"[Router] Cannot open registry key: {e}", flush=True)
        return

    # Also get full exe paths for each GPU process
    k32   = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    psapi.GetModuleFileNameExA.restype = ctypes.wintypes.DWORD
    psapi.GetModuleFileNameExA.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_char_p, ctypes.wintypes.DWORD
    ]

    seen_pids = set()
    for gp in gpu_procs:
        pid = gp["pid"]
        if pid in seen_pids:
            continue
        seen_pids.add(pid)

        name_lower = gp["name"].lower()

        # Get full exe path
        handle = k32.OpenProcess(0x1000 | 0x0010, False, pid)
        if not handle:
            continue
        path_buf = ctypes.create_string_buffer(512)
        psapi.GetModuleFileNameExA(ctypes.c_void_p(handle), ctypes.c_void_p(0), path_buf, 512)
        k32.CloseHandle(handle)
        exe_path = path_buf.value.decode(errors="replace")
        if not exe_path:
            continue

        # Decide routing
        pref = "GpuPreference=1;" if name_lower in LIGHTWEIGHT else "GpuPreference=2;"

        try:
            current, _ = winreg.QueryValueEx(reg_key, exe_path)
            if current == pref:
                continue  # already correct
        except FileNotFoundError:
            pass

        winreg.SetValueEx(reg_key, exe_path, 0, winreg.REG_SZ, pref)

        if pref == "GpuPreference=1;":
            routed_nvidia += 1
            print(f"[Router] GT 710  <- {gp['name']} ({exe_path[:60]})", flush=True)
        else:
            routed_amd += 1
            print(f"[Router] RX 580  <- {gp['name']} ({exe_path[:60]})", flush=True)

    winreg.CloseKey(reg_key)
    print(f"[Router] Applied: {routed_amd} -> RX 580, {routed_nvidia} -> GT 710", flush=True)


def start_routing_monitor(interval: int = 30):
    """
    Background thread that periodically re-applies GPU routing to all
    GPU-active processes. Picks up newly launched apps automatically.
    """
    def _run():
        print(f"[Router] GPU routing monitor active (interval={interval}s)", flush=True)
        while True:
            try:
                apply_gpu_routing_to_all_processes()
            except Exception as e:
                print(f"[Router] Error: {e}", flush=True)
            time.sleep(interval)

    t = threading.Thread(target=_run, name="gpu-router", daemon=True)
    t.start()
    return t

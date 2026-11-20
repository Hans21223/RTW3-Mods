"""Where a frozen Rule the Waves 3 is stuck, saved for a bug report.

The Mod Manager runs watch() while it is open. When a window of this folder's game has not answered Windows for
HUNG_SECONDS, capture() pauses the window's thread SAMPLES times (well under a millisecond each) and notes where it
is: the instruction pointer and the return addresses on its stack. Game addresses are given as in the mods' code and
notes (RTW3.exe at REFERENCE); mod code is named by the mod whose hooks lead into it (runtime_host_report.json).
A loop shows as the same addresses in every sample.

  python hang_report.py      report on the running game now, frozen or not (a check that it works)
"""
from collections import Counter
import ctypes as c
import ctypes.wintypes as w
from datetime import datetime
import json
from pathlib import Path
import struct
import time

import weekly_runtime as rt

HOME = Path(__file__).resolve().parent
GAME = HOME.parent.parent
REPORT = HOME / "hang-report.txt"
HOST_REPORT = GAME / "Mods" / "CampaignOverhaul" / "runtime_host_report.json"
STATE = GAME / "Mods" / "Manager" / "state.json"
HUNG_SECONDS, SAMPLES, INTERVAL, STACK = 60, 40, 0.1, 0x10000
REFERENCE = 0x300000                     # RTW3.exe's base in the mods' addresses (its text at 0x301000)
WOW64 = c.sizeof(c.c_void_p) == 8        # a 64-bit Python reads the 32-bit game's threads through WOW64
U = c.WinDLL("user32", use_last_error=True)
WNDENUMPROC = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)


class MEMORY_BASIC_INFORMATION(c.Structure):
    _fields_ = [("BaseAddress", c.c_void_p), ("AllocationBase", c.c_void_p), ("AllocationProtect", w.DWORD),
                ("RegionSize", c.c_size_t), ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]


def api():
    rt.configure_api()
    K = rt.K
    K.VirtualQueryEx.argtypes = [w.HANDLE, c.c_void_p, c.POINTER(MEMORY_BASIC_INFORMATION), c.c_size_t]
    K.VirtualQueryEx.restype = c.c_size_t
    K.OpenThread.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    K.OpenThread.restype = w.HANDLE
    for name in ("Wow64SuspendThread" if WOW64 else "SuspendThread", "ResumeThread"):
        getattr(K, name).argtypes = [w.HANDLE]
        getattr(K, name).restype = w.DWORD
    context = K.Wow64GetThreadContext if WOW64 else K.GetThreadContext
    context.argtypes = [w.HANDLE, c.c_void_p]
    context.restype = w.BOOL
    U.EnumWindows.argtypes = [WNDENUMPROC, w.LPARAM]
    U.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    U.GetWindowThreadProcessId.restype = w.DWORD
    U.IsWindowVisible.argtypes = U.IsHungAppWindow.argtypes = [w.HWND]


def windows(pids):
    """(hwnd, pid, thread) of the visible top-level windows of these processes."""
    found = []

    def each(hwnd, _):
        pid = w.DWORD()
        thread = U.GetWindowThreadProcessId(hwnd, c.byref(pid))
        if pid.value in pids and U.IsWindowVisible(hwnd):
            found.append((hwnd, pid.value, thread))
        return True
    U.EnumWindows(WNDENUMPROC(each), 0)
    return found


def frozen(game=GAME):
    """(pid, thread) of a game window that isn't answering Windows, or None."""
    exe = str((game / "RTW3.exe").resolve()).lower()
    pids = {pid for pid, path in rt.process_candidates() if str(path.resolve()).lower() == exe}
    return next(((pid, thread) for hwnd, pid, thread in windows(pids) if U.IsHungAppWindow(hwnd)), None)


def query(process, address):
    info = MEMORY_BASIC_INFORMATION()
    return info if rt.K.VirtualQueryEx(process, address, c.byref(info), c.sizeof(info)) else None


def places(process, pid):
    """[(start, end, name)]: the process's modules (its exe first) and the allocations the mods' hooks lead into."""
    found = []
    snapshot = rt.K.CreateToolhelp32Snapshot(0x18, pid)    # with the 32-bit modules of a WOW64 process
    if snapshot == c.c_void_p(-1).value:
        raise rt.win_error("Cannot list the game's modules")
    try:
        entry = rt.MODULEENTRY32()
        entry.dwSize = c.sizeof(entry)
        more = rt.K.Module32FirstW(snapshot, c.byref(entry))
        while more:
            found.append((entry.modBaseAddr, entry.modBaseAddr + entry.modBaseSize, entry.szModule))
            more = rt.K.Module32NextW(snapshot, c.byref(entry))
    finally:
        rt.K.CloseHandle(snapshot)
    try:
        host = json.loads(HOST_REPORT.read_text(encoding="utf-8"))
        hooks = host["hooks"] if host["session"]["pid"] == pid and rt.report_is_current(HOST_REPORT, pid) else []
    except (OSError, ValueError, KeyError):
        hooks = []
    for hook in hooks:
        code = bytes.fromhex(hook["replacement"])
        if code[:1] not in (b"\xe8", b"\xe9") or len(code) < 5:
            continue
        target = (hook["address"] + 5 + struct.unpack_from("<i", code, 1)[0]) & 0xFFFFFFFF
        info = query(process, target)
        if not info or any(start <= target < end for start, end, _ in found):
            continue
        start = end = info.AllocationBase
        while (part := query(process, end)) and part.AllocationBase == start:   # all regions of the allocation
            end = part.BaseAddress + part.RegionSize
        found.append((start, end, hook["owner"]))
    return found


def where(address, known):
    """A game address as in the mods' code, mod code as mod+offset, a system module as module+offset."""
    for index, (start, end, name) in enumerate(known):
        if start <= address < end:
            return f"game {address - start + REFERENCE:#x}" if index == 0 else f"{name}+{address - start:#x}"
    return f"{address:#x}"


def after_call(code):
    """The 7 bytes before an address end with a call: E8 rel32, or FF /2 with any operand."""
    if code[2] == 0xE8:
        return True
    for n in (2, 3, 4, 6, 7):
        op, modrm = code[7 - n], code[8 - n]
        if op != 0xFF or (modrm >> 3) & 7 != 2:
            continue
        mod, rm = modrm >> 6, modrm & 7
        size = 2 + (mod != 3 and rm == 4) + (mod == 1) + 4 * (mod == 2 or (mod == 0 and rm == 5))
        if mod == 0 and rm == 4 and n > 2 and code[9 - n] & 7 == 5:
            size += 4      # SIB without a base: disp32
        if size == n:
            return True
    return False


def returns(stack, is_return):
    """Return addresses on the stack, innermost first."""
    return [value for value in struct.unpack_from(f"<{len(stack) // 4}I", stack) if is_return(value)]


def chain(registers, stack):
    """The EBP frame chain Delphi's code keeps: its return addresses, innermost first."""
    found, ebp, esp = [], registers["ebp"], registers["esp"]
    while esp <= ebp <= esp + len(stack) - 8 and len(found) < 64:
        parent, back = struct.unpack_from("<II", stack, ebp - esp)
        found.append(back)
        if parent <= ebp:
            break
        ebp = parent
    return found


def sample(process, thread):
    """(registers, the stack from ESP up) of the thread, paused while they are read."""
    context = c.create_string_buffer(716)              # (WOW64_)CONTEXT, x86 layout
    struct.pack_into("<I", context, 0, 0x10003)        # CONTEXT_i386 | CONTROL | INTEGER
    pause = rt.K.Wow64SuspendThread if WOW64 else rt.K.SuspendThread
    if pause(thread) == 0xFFFFFFFF:
        raise rt.win_error("Cannot pause the game's thread")
    try:
        if not (rt.K.Wow64GetThreadContext if WOW64 else rt.K.GetThreadContext)(thread, context):
            raise rt.win_error("Cannot read the game's thread")
        registers = dict(zip(("edi", "esi", "ebx", "edx", "ecx", "eax", "ebp", "eip"),
                             struct.unpack_from("<8I", context, 0x9C)))
        registers["esp"] = struct.unpack_from("<I", context, 0xC4)[0]
        info = query(process, registers["esp"])
        top = info.BaseAddress + info.RegionSize if info else registers["esp"]
        stack = rt.read(process, registers["esp"], min(STACK, top - registers["esp"]) & ~3)
    finally:
        rt.K.ResumeThread(thread)
    return registers, stack


def capture(pid, thread_id, samples=SAMPLES, interval=INTERVAL):
    """The report's text: SAMPLES looks at the thread, INTERVAL seconds apart."""
    api()
    process = rt.K.OpenProcess(0x410, False, pid)           # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
    thread = rt.K.OpenThread(0x4A, False, thread_id)        # SUSPEND_RESUME | GET_CONTEXT | QUERY_INFORMATION
    try:
        if not process or not thread:
            raise rt.win_error("Cannot open the game")
        known = places(process, pid)
        code = known[:1] + [p for p in known[1:] if not p[2].lower().endswith((".dll", ".exe", ".drv"))]
        checked = {}

        def is_return(value):   # into the game's or a mod's code, after a call
            if value not in checked:
                checked[value] = False
                if any(start + 7 <= value < end for start, end, _ in code):
                    try:
                        checked[value] = after_call(rt.read(process, value - 7, 7))
                    except OSError:
                        pass
            return checked[value]

        taken = []
        for _ in range(samples):
            registers, stack = sample(process, thread)
            taken.append((registers, returns(stack, is_return), chain(registers, stack)))
            time.sleep(interval)
    finally:
        for handle in (process, thread):
            if handle:
                rt.K.CloseHandle(handle)
    return text(taken, known, interval)


def text(taken, known, interval):
    try:
        mods = ", ".join(json.loads(STATE.read_text(encoding="utf-8")).get("enabled", [])) or "none"
    except (OSError, ValueError):
        mods = "unknown"
    try:
        import updates
        version = updates.VERSION
    except ImportError:
        version = "unknown"
    seen = Counter(a for _, stack, _ in taken for a in set(stack))
    order = list(dict.fromkeys(a for _, stack, _ in taken for a in stack))
    lines = [f"Rule the Waves 3 stopped responding: where it was, {datetime.now():%Y-%m-%d %H:%M:%S}",
             f"Mod Manager {version}. Mods on: {mods}",
             f"Game addresses as in the mods' code (RTW3.exe at {REFERENCE:#x}); mod code by the mod that hooked it.",
             "", f"Instruction pointer in {len(taken)} samples over {len(taken) * interval:.0f} s:"]
    lines += [f"{n:5}  {name}" for name, n in Counter(where(r["eip"], known) for r, _, _ in taken).most_common(20)]
    lines += ["", "Return addresses on the stack, innermost first, with the samples each was in:"]
    lines += [f"{seen[a]:5}  {where(a, known)}" for a in order[:80]]
    registers, _, frames = taken[0]
    lines += ["", "Frame chain of the first sample: " + ", ".join(where(a, known) for a in frames),
              "Registers of the first sample: " + " ".join(f"{k}={v:08x}" for k, v in registers.items()),
              "Mod code this session: " + ", ".join(f"{name} {start:#x}-{end:#x}" for start, end, name in known[1:]
                                                    if not name.lower().endswith((".dll", ".exe", ".drv")))]
    return "\n".join(lines) + "\n"


def watch(said, game=GAME, every=5):
    """While the manager is open: one report per freeze, its path passed to said()."""
    api()
    since = done = None
    while True:
        time.sleep(every)
        try:
            hung = frozen(game)
        except OSError:
            continue
        if hung != since:                     # a new freeze, or answering again
            since, start, done = hung, time.monotonic(), False
        if hung and not done and time.monotonic() - start >= HUNG_SECONDS:
            done = True
            try:
                report = capture(*hung)
            except Exception as error:        # still worth sending: says why there is no stack
                report = f"Rule the Waves 3 stopped responding, but its thread couldn't be read: {error}\n"
            REPORT.write_text(report, encoding="utf-8")
            said(REPORT)


if __name__ == "__main__":
    api()
    exe = str((GAME / "RTW3.exe").resolve()).lower()
    pids = {pid for pid, path in rt.process_candidates() if str(path.resolve()).lower() == exe}
    found = windows(pids)
    if not found:
        raise SystemExit("Rule the Waves 3 isn't running from this folder.")
    print(capture(found[0][1], found[0][2]), end="")

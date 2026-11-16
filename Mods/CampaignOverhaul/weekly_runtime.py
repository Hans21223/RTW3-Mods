"""Inspect and optionally attach a seven-day calendar mod to a running RTW3.

The official on-disk executable is never edited. Steam must already have
started and authenticated the game normally. This is an experimental calendar
patch: all other monthly simulation routines retain their original cadence.
"""
from __future__ import annotations

import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import time


HERE = Path(__file__).resolve().parent
GAME = HERE.parent.parent
REPORT = HERE / "weekly_runtime_report.json"
K = c.WinDLL("kernel32", use_last_error=True) if sys.platform == "win32" else None


class PROCESSENTRY32(c.Structure):
    _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
                ("th32DefaultHeapID", c.c_size_t), ("th32ModuleID", w.DWORD),
                ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD),
                ("pcPriClassBase", w.LONG), ("dwFlags", w.DWORD), ("szExeFile", w.WCHAR * 260)]


class MODULEENTRY32(c.Structure):
    _fields_ = [("dwSize", w.DWORD), ("th32ModuleID", w.DWORD), ("th32ProcessID", w.DWORD),
                ("GlblcntUsage", w.DWORD), ("ProccntUsage", w.DWORD), ("modBaseAddr", c.c_void_p),
                ("modBaseSize", w.DWORD), ("hModule", w.HMODULE),
                ("szModule", w.WCHAR * 256), ("szExePath", w.WCHAR * 260)]


def configure_api():
    K.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    K.CreateToolhelp32Snapshot.restype = w.HANDLE
    for name, typ in (("Process32FirstW", PROCESSENTRY32), ("Process32NextW", PROCESSENTRY32),
                      ("Module32FirstW", MODULEENTRY32), ("Module32NextW", MODULEENTRY32)):
        function = getattr(K, name)
        function.argtypes = [w.HANDLE, c.POINTER(typ)]
        function.restype = w.BOOL
    K.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    K.OpenProcess.restype = w.HANDLE
    K.CloseHandle.argtypes = [w.HANDLE]
    K.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
    K.QueryFullProcessImageNameW.restype = w.BOOL
    K.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
    K.ReadProcessMemory.restype = w.BOOL
    K.WriteProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
    K.WriteProcessMemory.restype = w.BOOL
    K.VirtualProtectEx.argtypes = [w.HANDLE, c.c_void_p, c.c_size_t, w.DWORD, c.POINTER(w.DWORD)]
    K.VirtualProtectEx.restype = w.BOOL
    K.FlushInstructionCache.argtypes = [w.HANDLE, c.c_void_p, c.c_size_t]
    K.FlushInstructionCache.restype = w.BOOL
    K.GetExitCodeProcess.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    K.GetExitCodeProcess.restype = w.BOOL
    K.GetProcessTimes.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)]*4
    K.GetProcessTimes.restype = w.BOOL


def win_error(label):
    return OSError(c.get_last_error(), label)


def process_created(pid):
    """Process start time as a FILETIME. Unlike a PID, never reused."""
    configure_api()
    handle = K.OpenProcess(0x1000, False, pid)
    if not handle:
        raise win_error("Cannot identify game session")
    try:
        stamps = [w.FILETIME() for _ in range(4)]
        if not K.GetProcessTimes(handle, *(c.byref(stamp) for stamp in stamps)):
            raise win_error("Cannot identify game session")
        return stamps[0].dwLowDateTime | (stamps[0].dwHighDateTime << 32)
    finally:
        K.CloseHandle(handle)


def report_is_current(path, pid):
    # Windows reuses PIDs and usually maps the game at the same base each
    # launch, so pid+base alone can revive a report from an earlier session.
    return path.stat().st_mtime_ns >= (process_created(pid)-116444736000000000)*100


def process_candidates():
    snapshot = K.CreateToolhelp32Snapshot(2, 0)
    if snapshot == c.c_void_p(-1).value:
        raise win_error("Cannot list game processes")
    found = []
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = c.sizeof(entry)
        more = K.Process32FirstW(snapshot, c.byref(entry))
        while more:
            if entry.szExeFile.lower() == "rtw3.exe":
                handle = K.OpenProcess(0x1000, False, entry.th32ProcessID)
                if handle:
                    try:
                        name = c.create_unicode_buffer(32768)
                        length = w.DWORD(len(name))
                        if K.QueryFullProcessImageNameW(handle, 0, name, c.byref(length)):
                            found.append((entry.th32ProcessID, Path(name.value)))
                    finally:
                        K.CloseHandle(handle)
            more = K.Process32NextW(snapshot, c.byref(entry))
    finally:
        K.CloseHandle(snapshot)
    return found


def module_info(pid):
    # Windows can return ERROR_BAD_LENGTH while DLLs load/unload. Retry that
    # documented transient condition only, with a bound so failure stays visible.
    # https://learn.microsoft.com/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot
    for attempt in range(20):
        snapshot = K.CreateToolhelp32Snapshot(0x18, pid)
        if snapshot != c.c_void_p(-1).value:
            break
        error = c.get_last_error()
        if error != 24 or attempt == 19:
            raise OSError(error, "Cannot inspect the game module")
        time.sleep(0.05)
    try:
        entry = MODULEENTRY32()
        entry.dwSize = c.sizeof(entry)
        more = K.Module32FirstW(snapshot, c.byref(entry))
        while more:
            if entry.szModule.lower() == "rtw3.exe":
                return entry.modBaseAddr, entry.modBaseSize
            more = K.Module32NextW(snapshot, c.byref(entry))
    finally:
        K.CloseHandle(snapshot)
    raise ValueError("The running game has no RTW3 module.")


def read(handle, address, size):
    data = c.create_string_buffer(size)
    actual = c.c_size_t()
    if not K.ReadProcessMemory(handle, address, data, size, c.byref(actual)) or actual.value != size:
        raise win_error(f"Cannot read game memory at {address:#x}")
    return data.raw


def write_code(handle, address, original, replacement):
    if len(original) != len(replacement) or read(handle, address, len(original)) != original:
        raise ValueError("The game changed while preparing the patch. No write performed.")
    previous = w.DWORD()
    if not K.VirtualProtectEx(handle, address, len(original), 0x40, c.byref(previous)):
        raise win_error("Cannot make the game's turn block writable")
    try:
        size = c.c_size_t()
        data = c.create_string_buffer(replacement)
        if not K.WriteProcessMemory(handle, address, data, len(replacement), c.byref(size)) or size.value != len(replacement):
            raise win_error("Could not write the entire turn block")
        K.FlushInstructionCache(handle, address, len(replacement))
    finally:
        ignored = w.DWORD()
        K.VirtualProtectEx(handle, address, len(original), previous.value, c.byref(ignored))


def text_section(handle, base):
    header = read(handle, base, 0x1000)
    pe = struct.unpack_from("<I", header, 0x3C)[0]
    if header[:2] != b"MZ" or header[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Not a PE game image.")
    count = struct.unpack_from("<H", header, pe + 6)[0]
    opt_size = struct.unpack_from("<H", header, pe + 20)[0]
    for i in range(count):
        off = pe + 24 + opt_size + 40 * i
        name = header[off:off + 8].rstrip(b"\0")
        size, rva = struct.unpack_from("<II", header, off + 8)
        if name == b".text":
            return base + rva, read(handle, base + rva, size)
    raise ValueError("No game code section.")


def method_address(blob, text_base, name):
    encoded = name.encode("ascii")
    needle = bytes([len(encoded)]) + encoded
    start = 0
    found = set()
    while True:
        at = blob.find(needle, start)
        if at < 0:
            break
        if at >= 6:
            length, address = struct.unpack_from("<HI", blob, at - 6)
            if 7 + len(encoded) <= length < 1200 and text_base <= address < text_base + len(blob):
                found.add(address)
        start = at + len(needle)
    if len(found) != 1:
        raise ValueError(f"Expected one verified method address for {name}, found {len(found)}.")
    return found.pop()


def turn_blocks(blob, text_base):
    pattern = re.compile(rb"\xff\x35(.{4})\xff\x35(.{4})\xb8\x01\x00\x00\x00\xe8(.{4})\xdd\x1d(.{4})\x9b", re.DOTALL)
    blocks = []
    for name in ("DoTurn", "DoStrategicTurn"):
        start = method_address(blob, text_base, name)
        offset = start - text_base
        matches = []
        for match in pattern.finditer(blob, offset, min(offset + 0x1200, len(blob))):
            high, low, displacement, stored = [struct.unpack("<I", group)[0] for group in match.groups()]
            if high != low + 4 or stored != low:
                continue
            matches.append({"method": name, "function": start, "address": text_base + match.start(), "clock": low,
                            "original": match.group().hex(), "length": len(match.group())})
        # Search windows can overlap the following function. The first valid
        # clock advance belongs to the named method; also require distinct sites.
        if not matches:
            raise ValueError(f"No recognized calendar advance in {name}.")
        blocks.append(matches[0])
    if len({block["address"] for block in blocks}) != 2 or len({block["clock"] for block in blocks}) != 1:
        raise ValueError("Campaign turn paths do not match the expected shared clock.")
    return blocks


def replacement(block, days=7):
    # push imm8 is signed; 28 days or fewer also never skips a calendar month.
    if not 1 <= days <= 28:
        raise ValueError("Calendar turns must advance 1 to 28 days.")
    address = struct.pack("<I", block["clock"])
    code = b"\xdd\x05" + address + b"\x6a" + bytes([days]) + b"\xdb\x04\x24\xde\xc1\x58\xdd\x1d" + address + b"\x9b"
    if len(code) > block["length"]:
        raise ValueError("Replacement exceeds the calendar block.")
    return code.ljust(block["length"], b"\x90")


def wait_for_game_code(handle, pid, deadline):
    # A process becomes visible before Steam has finished loading its image.
    # Wait for readable method metadata; never modify a half-loaded image.
    while True:
        try:
            base, size = module_info(pid)
            text_base, blob = text_section(handle, base)
            blocks = turn_blocks(blob, text_base)
            return base, size, blocks
        except (OSError, ValueError):
            exit_code = w.DWORD()
            if K.GetExitCodeProcess(handle, c.byref(exit_code)) and exit_code.value != 259:
                raise ValueError("The game exited before its calendar methods were ready.")
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


def _attach_to_handle(handle, pid, path, deadline, days):
    base, size, blocks = wait_for_game_code(handle, pid, deadline)
    saved = {"pid": pid, "path": str(path), "base": base, "image_size": size,
             "exe_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
             "blocks": blocks, "attached": False, "balanced": False}
    updated = []
    try:
        for block in blocks:
            write_code(handle, block["address"], bytes.fromhex(block["original"]), replacement(block, days))
            updated.append(block)
    except Exception:
        for block in reversed(updated):
            write_code(handle, block["address"], replacement(block, days), bytes.fromhex(block["original"]))
        raise
    saved.update(attached=True, days=days)
    REPORT.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    return saved


def attach(wait=60, days=7):
    """Callable host entry point; the launcher handles experimental consent."""
    if type(days) is not int or not 1 <= days <= 28:
        raise ValueError("Calendar days must be a whole number from 1 to 28.")
    configure_api()
    deadline = time.monotonic() + wait
    while True:
        candidates = [(pid, path) for pid, path in process_candidates()
                      if path.resolve() == (GAME/"RTW3.exe").resolve()]
        if len(candidates) == 1:
            break
        if len(candidates) > 1 or time.monotonic() >= deadline:
            raise ValueError("Open exactly one RTW3.exe from this updated folder.")
        time.sleep(0.5)
    pid, path = candidates[0]
    handle = K.OpenProcess(0x438, False, pid)
    if not handle:
        raise win_error("Cannot open this game process")
    try:
        return _attach_to_handle(handle, pid, path, deadline, days)
    finally:
        K.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "attach", "detach", "clock"))
    parser.add_argument("--wait", type=int, default=0, help="Seconds to wait for this game copy to open")
    parser.add_argument("--inspect-steam-copy", action="store_true", help="Read-only inspection of the registered Steam installation")
    parser.add_argument("--accept-experimental-calendar", action="store_true",
                        help="Accept that monthly economy, AI and timers are not rebalanced")
    parser.add_argument("--settings", default="{}", help='JSON mod.json settings, for example {"days": 14}')
    args = parser.parse_args()
    if K is None:
        parser.error("Windows is required.")
    if args.command == "attach" and not args.accept_experimental_calendar:
        parser.error("This changes the calendar only. Use --accept-experimental-calendar for an experimental campaign.")
    if args.inspect_steam_copy and args.command != "inspect":
        parser.error("Inspection of the separate Steam copy is read-only.")
    configure_api()
    try:
        days = json.loads(args.settings).get("days", 7)
        deadline = time.monotonic() + args.wait
        while True:
            target = Path(r"D:\SteamLibrary\steamapps\common\Rule the Waves 3") if args.inspect_steam_copy else GAME
            candidates = [(pid, path) for pid, path in process_candidates() if path.resolve() == (target / "RTW3.exe").resolve()]
            if len(candidates) == 1:
                break
            if len(candidates) > 1 or time.monotonic() >= deadline:
                raise ValueError("Open exactly one RTW3.exe from this updated folder. No game memory changed.")
            time.sleep(1)
        pid, path = candidates[0]
        access = 0x410 if args.command in ("inspect", "clock") else 0x438
        handle = K.OpenProcess(access, False, pid)
        if not handle:
            raise win_error("Cannot open this game process")
        try:
            if args.command in ("detach", "clock"):
                base, size = module_info(pid)
                saved = json.loads(REPORT.read_text(encoding="utf-8"))
                if saved["pid"] != pid or saved["base"] != base or not report_is_current(REPORT, pid):
                    raise ValueError("Saved attachment belongs to another game session. Restart to reset patches.")
                if args.command == "clock":
                    clock = struct.unpack("<d", read(handle, saved["blocks"][0]["clock"], 8))[0]
                    import datetime
                    print((datetime.datetime(1899, 12, 30) + datetime.timedelta(days=clock)).isoformat())
                    return 0
                # Reports written before configurable turns always used seven days.
                attached_days = saved.get("days", 7)
                for block in saved["blocks"]:
                    current = read(handle, block["address"], block["length"])
                    if current not in (replacement(block, attached_days), bytes.fromhex(block["original"])):
                        raise ValueError("A turn block has unexpected changes. No detach performed.")
                for block in saved["blocks"]:
                    current = read(handle, block["address"], block["length"])
                    if current == replacement(block, attached_days):
                        write_code(handle, block["address"], current, bytes.fromhex(block["original"]))
                saved["attached"] = False
            elif args.command == "attach":
                saved = _attach_to_handle(handle, pid, path, deadline, days)
            else:
                base, size, blocks = wait_for_game_code(handle, pid, deadline)
                saved = {"pid": pid, "path": str(path), "base": base, "image_size": size,
                         "exe_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "blocks": blocks, "attached": False, "balanced": False}
            REPORT.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(saved, indent=2))
            if saved["attached"]:
                print(f"Experimental {days}-day calendar attached. Monthly economy, AI and timers are unchanged.")
                print("Restart the game or use detach to return to the original turn clock.")
        finally:
            K.CloseHandle(handle)
    except (OSError, ValueError, KeyError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

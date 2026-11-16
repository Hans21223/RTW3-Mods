"""Show the calendar week beside the native campaign month/year label."""
from __future__ import annotations
import argparse
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path
import re
import struct
import time
import weekly_runtime as rt

REPORT = Path(__file__).with_name("week_display_report.json")


def build_thunk(address, day_slot, formats, original_function):
    # FormatDateTime uses EAX=format, EDX=settings, ECX=out string, date on stack.
    # Select an immutable Delphi UnicodeString, restore all nonvolatile registers,
    # and tail-call the original formatter with its original date and out pointer.
    code = bytearray(b"\x52\x53\x8b\x1d" + struct.pack("<I", day_slot))
    code += b"\x85\xdb\x74\x04\x8b\x1b\xeb\x02\x31\xdb"  # null-safe day
    code += b"\x4b\x83\xfb\x1e\x76\x02\x31\xdb"  # clamp invalid days
    code += b"\x89\xd8\x31\xd2\xbb\x07\x00\x00\x00\xf7\xf3"
    code += b"\x8b\x04\x85" + struct.pack("<I", formats)
    code += b"\x5b\x5a\xe9"
    code += struct.pack("<i", original_function - (address + len(code) + 4))
    return bytes(code)


def configure():
    rt.configure_api()
    rt.K.VirtualAllocEx.argtypes = [w.HANDLE, c.c_void_p, c.c_size_t, w.DWORD, w.DWORD]
    rt.K.VirtualAllocEx.restype = c.c_void_p
    rt.K.VirtualFreeEx.argtypes = [w.HANDLE, c.c_void_p, c.c_size_t, w.DWORD]
    rt.K.VirtualFreeEx.restype = w.BOOL


def write(handle, address, data):
    buf = c.create_string_buffer(data)
    size = c.c_size_t()
    if not rt.K.WriteProcessMemory(handle, address, buf, len(data), c.byref(size)) or size.value != len(data):
        raise rt.win_error("Could not write the week display buffer")
    if rt.read(handle, address, len(data)) != data:
        raise ValueError("Week display write did not verify.")


def discover(handle, pid):
    base, size = rt.module_info(pid)
    text_base, blob = rt.text_section(handle, base)
    function = rt.method_address(blob, text_base, "UpdateBudgetNumbers")
    turn = rt.method_address(blob, text_base, "DoTurn")
    day_slots = []
    for match in re.finditer(rb"\x0f\xb7\x45.\x8b\x15(.{4})\x89\x02", blob[turn-text_base:turn-text_base+0x500], re.DOTALL):
        day_slots.append(struct.unpack("<I", match.group(1))[0])
    if len(day_slots) != 3:
        raise ValueError("Expected the year/month/day decoding sequence in DoTurn.")
    day_slot = day_slots[-1]
    sites = []
    for match in re.finditer(rb"\xb8(.{4})\xe8(.{4})", blob[function-text_base:function-text_base+0x250], re.DOTALL):
        pointer, = struct.unpack("<I", match.group(1))
        if not text_base <= pointer < text_base + len(blob) - 16:
            continue
        off = pointer - text_base
        if blob[off:off+16] != "mmm yyyy".encode("utf-16-le"):
            continue
        call = function + match.start() + 5
        displacement, = struct.unpack("<i", match.group(2))
        sites.append((call, call + 5 + displacement))
    if len(sites) != 1 or not base <= day_slot < base + size:
        raise ValueError("Could not uniquely verify the native campaign date formatter.")
    return base, sites[0][0], sites[0][1], day_slot


def attach(wait=30):
    configure()
    deadline = time.monotonic() + wait
    while True:
        games = [(pid, path) for pid, path in rt.process_candidates() if path.resolve() == (rt.GAME / "RTW3.exe").resolve()]
        if len(games) == 1:
            break
        if time.monotonic() >= deadline:
            raise ValueError("Open the local RTW3 copy first.")
        time.sleep(0.5)
    pid, path = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle:
        raise rt.win_error("Cannot open the local game")
    try:
        while True:
            try:
                base, call, original_function, day_slot = discover(handle, pid)
                break
            except (OSError, ValueError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)
        if REPORT.exists():
            prior = json.loads(REPORT.read_text(encoding="utf-8"))
            if prior.get("pid") == pid and prior.get("base") == base and prior.get("attached") and rt.report_is_current(REPORT, pid):
                if rt.read(handle, prior["call"], 5).hex() == prior["replacement"]:
                    return prior
                raise ValueError("A previous week display attachment has unexpected changes.")
        allocation = rt.K.VirtualAllocEx(handle, None, 4096, 0x3000, 0x40)
        if not allocation:
            raise rt.win_error("Cannot allocate the native week display")
        patched_site = False
        original = None
        patched = None
        try:
            formats = allocation + 0x100
            payload = bytearray(0x120)
            pointers = []
            for week in range(1, 6):
                text = f"mmm yyyy 'Week {week}'"
                payload += struct.pack("<HHiI", 1200, 2, -1, len(text))
                pointers.append(allocation + len(payload))
                payload += text.encode("utf-16-le") + b"\x00\x00"
            struct.pack_into("<5I", payload, 0x100, *pointers)
            thunk = build_thunk(allocation, day_slot, formats, original_function)
            payload[:len(thunk)] = thunk
            write(handle, allocation, bytes(payload))
            rt.K.FlushInstructionCache(handle, allocation, len(thunk))
            original = rt.read(handle, call, 5)
            patched = b"\xe8" + struct.pack("<i", allocation - call - 5)
            rt.write_code(handle, call, original, patched)
            patched_site = True
            report = {"pid": pid, "base": base, "call": call, "allocation": allocation,
                      "day_slot": day_slot, "original": original.hex(), "replacement": patched.hex(), "attached": True,
                      "format_example": "Japan, Feb 1890 Week 2", "weeks": "1-7, 8-14, 15-21, 22-28, 29-31"}
            REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            return report
        except Exception:
            if patched_site:
                rt.write_code(handle, call, patched, original)
            rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise
    finally:
        rt.K.CloseHandle(handle)


def detach():
    configure()
    saved = json.loads(REPORT.read_text(encoding="utf-8"))
    candidates = {pid: path for pid, path in rt.process_candidates()}
    if saved["pid"] not in candidates or candidates[saved["pid"]] != rt.GAME / "RTW3.exe":
        raise ValueError("This attachment's game session has ended.")
    handle = rt.K.OpenProcess(0x438, False, saved["pid"])
    try:
        base, size = rt.module_info(saved["pid"])
        if base != saved["base"]:
            raise ValueError("The game session changed.")
        original = bytes.fromhex(saved["original"])
        current = rt.read(handle, saved["call"], 5)
        if current != original:
            rt.write_code(handle, saved["call"], bytes.fromhex(saved["replacement"]), original)
        # Keep the tiny immutable buffer until process exit: a UI call could
        # still be returning through the thunk at the instant of detachment.
        saved["attached"] = False
        REPORT.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
        return saved
    finally:
        rt.K.CloseHandle(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attach", "detach"))
    args = parser.parse_args()
    try:
        print(json.dumps(attach() if args.command == "attach" else detach()))
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "message": str(error)}))
        raise SystemExit(1)

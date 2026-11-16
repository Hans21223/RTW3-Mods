"""Expose manual legacy-fleet building in every native campaign start year."""
import argparse
import json
from pathlib import Path
import re
import struct
import time
import weekly_runtime as rt
import week_display as memory
from hull_rules import patch, unique, message_ref, dpi_scaled

REPORT = Path(__file__).with_name("legacy_fleet_report.json")
REFERENCE = 0x301000
# TControl.SetTop(EAX control, EDX top): no relocations, so its bytes must match exactly.
SET_TOP = (0x450F24, "53568bd88b4358508b435c508b43508bca8bd3928b30ff96e0000000808b9800000002f6431c0274098b4354"
                     "8983c00100005e5bc3")
# Native Top of the checkbox and its caption, and below the 1920 arms-limitation treaty list (Top 419, height 49),
# which the game shows in the same place.
TOPS = {"Legacy checkbox": (405, 476), "Legacy caption": (403, 474)}
TREATY_YEAR = 1920
TREATY_LIST = (0x518, 193)   # lbTreaty: form field and width at 96 DPI (the TOPS are 96-DPI): display-scaling reference


def year_thunk(address, year_slot, resume):
    # The old instruction stores 1899 through EAX. Use the selected start year
    # minus one instead. Preserve EDX and flags, just as the original MOV did.
    code = b"\x9c\x52\x8b\x15"+struct.pack("<I", year_slot)
    code += b"\x8b\x12\x4a\x89\x10\x5a\x9d\xe9"
    code += struct.pack("<i", resume-(address+len(code)+4))
    return code


def top_thunk(address, control, tops, set_top):
    """Replaces CMP [ESI],1900 / SETE DL: always visible (DL=1), placed below the treaty list in its year."""
    native, moved = (dpi_scaled(top, *TREATY_LIST) for top in tops)
    code = b"\x60\x81\x3e"+struct.pack("<I", TREATY_YEAR)+b"\x75"+bytes([len(moved)+2])
    code += moved+b"\xeb"+bytes([len(native)])+native
    code += b"\x8b\x83"+struct.pack("<I", control)+b"\xe8"
    code += struct.pack("<i", set_top-(address+len(code)+4))
    return code+b"\x61\xb2\x01\xc3"


def discover(blob, base, allocation):
    click = rt.method_address(blob, base, "lbLegacyFleetClick")-base
    field_match = list(re.finditer(rb"\x8b\xb3(.{4})\x8b\xc6", blob[click:click+0x20], re.DOTALL))
    if len(field_match) != 1:
        raise ValueError("Cannot identify native legacy-fleet checkbox.")
    field, = struct.unpack("<I", field_match[0].group(1))
    year_method = rt.method_address(blob, base, "lb1900Click")-base
    body = blob[year_method:year_method+0x340]
    # Both checkbox and caption are hidden by a year==1900 condition.
    condition = b"\x81\x3e\x6c\x07\x00\x00\x0f\x94\xc2"
    candidates = []
    for match in re.finditer(re.escape(condition)+rb"\x8b\x83(.{4})\xe8(.{4})", body, re.DOTALL):
        control, = struct.unpack("<I", match.group(1))
        if control in (field, field+0x10):
            candidates.append((match, control))
    if len(candidates) != 2 or {c for _, c in candidates} != {field, field+0x10}:
        raise ValueError("Unsupported legacy-fleet year visibility gates.")
    set_top = SET_TOP[0]-REFERENCE+base
    if blob[set_top-base:set_top-base+len(bytes.fromhex(SET_TOP[1]))] != bytes.fromhex(SET_TOP[1]):
        raise ValueError("Unsupported native control positioning.")
    plans, thunks = [], b""
    for match, control in sorted(candidates, key=lambda item: item[1]):
        label, at = "Legacy checkbox" if control == field else "Legacy caption", allocation+0x40+len(thunks)
        site = base+year_method+match.start()
        plans.append(patch(label, site, condition, b"\xe8"+struct.pack("<i", at-(site+5))+b"\x90"*4))
        thunks += top_thunk(at, control, TOPS[label], set_top).ljust(0x40, b"\xcc")
    year_slot, = struct.unpack_from("<I", body, unique(body[:0x30], b"\x8b\x35", "start-year pointer")+2)
    ref = message_ref(blob, base, "Build your existing fleet")
    # The manual construction stage has a separate hardcoded design year.
    old = b"\xc7\x00\x6b\x07\x00\x00"
    off = ref-0x100 + unique(blob[ref-0x100:ref], old, "legacy design year")
    # Verify that this is the same checkbox whose state selects the manual path.
    preceding = blob[max(0, off-0x800):off]
    if b"\x8b\x80"+struct.pack("<I", field)+b"\x8b\x10\xff\x92\x6c\x01\x00\x00\x84\xc0" not in preceding:
        raise ValueError("Cannot verify manual fleet construction selection.")
    resume = base+off+len(old)
    plans.append(patch("Legacy design year", base+off, old,
                       b"\xe9"+struct.pack("<i", allocation-(base+off+5))+b"\x90"))
    return plans, year_thunk(allocation, year_slot, resume).ljust(0x40, b"\xcc")+thunks, year_slot


def attach(wait=30):
    memory.configure()
    deadline = time.monotonic()+wait
    while True:
        games = [g for g in rt.process_candidates() if g[1] == rt.GAME/"RTW3.exe"]
        if len(games) == 1:
            break
        if time.monotonic() >= deadline:
            raise ValueError("Open the local RTW3 copy first.")
        time.sleep(0.5)
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle:
        raise rt.win_error("Cannot open local game")
    try:
        if REPORT.exists():
            saved = json.loads(REPORT.read_text(encoding="utf-8"))
            base, _ = rt.module_info(pid)
            if saved.get("pid") == pid and saved.get("base") == base and saved.get("attached") and rt.report_is_current(REPORT, pid):
                for item in saved["patches"]:
                    if rt.read(handle, item["address"], len(bytes.fromhex(item["replacement"]))).hex() != item["replacement"]:
                        raise ValueError("Existing legacy-fleet attachment has unexpected changes.")
                return saved
        while True:
            try:
                base, _ = rt.module_info(pid)
                text_base, blob = rt.text_section(handle, base)
                discover(blob, text_base, 0x10000000)
                break
            except (OSError, ValueError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)
        allocation = rt.K.VirtualAllocEx(handle, None, 4096, 0x3000, 0x40)
        if not allocation:
            raise rt.win_error("Cannot allocate legacy-fleet adapter")
        applied = []
        try:
            plans, code, year_slot = discover(blob, text_base, allocation)
            memory.write(handle, allocation, code)
            rt.K.FlushInstructionCache(handle, allocation, len(code))
            for item in plans:
                old = bytes.fromhex(item["original"])
                if rt.read(handle, item["address"], len(old)) != old:
                    raise ValueError("Game changed during legacy-fleet preparation.")
            for item in plans:
                rt.write_code(handle, item["address"], bytes.fromhex(item["original"]), bytes.fromhex(item["replacement"]))
                applied.append(item)
                if rt.read(handle, item["address"], len(bytes.fromhex(item["replacement"]))).hex() != item["replacement"]:
                    raise ValueError("Legacy-fleet patch did not verify.")
            saved = {"pid": pid, "base": base, "allocation": allocation, "attached": True,
                     "patches": plans, "year_slot": year_slot, "native_start_years": [1890, 1900, 1920, 1935],
                     "manual_design_year": "selected start year minus one", "personal_saves_modified": False}
            REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
            return saved
        except Exception:
            for item in reversed(applied):
                rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]), bytes.fromhex(item["original"]))
            # Keep an allocation that may have been entered by the native thread.
            if not applied:
                rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise
    finally:
        rt.K.CloseHandle(handle)


def detach():
    memory.configure()
    saved = json.loads(REPORT.read_text(encoding="utf-8"))
    if dict(rt.process_candidates()).get(saved["pid"]) != rt.GAME/"RTW3.exe":
        raise ValueError("The attached game session ended.")
    handle = rt.K.OpenProcess(0x438, False, saved["pid"])
    try:
        if rt.module_info(saved["pid"])[0] != saved["base"]:
            raise ValueError("The game session changed.")
        for item in saved["patches"]:
            if rt.read(handle, item["address"], len(bytes.fromhex(item["replacement"]))).hex() != item["replacement"]:
                raise ValueError("Legacy attachment changed; no partial detach performed.")
        for item in reversed(saved["patches"]):
            rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]), bytes.fromhex(item["original"]))
        saved["attached"] = False
        REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
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

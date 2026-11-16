"""Read-only native-code emulation against a normally launched local game.

Exercises displacement/class gates, NOT full designs or campaign gameplay.
The live process is only read; all changed instructions run inside Unicorn.
"""
import json
import re
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor"))
sys.path.insert(0, str(HERE.parent / "CampaignOverhaul"))
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import *
import weekly_runtime as rt
import hull_rules as rules


def main():
    rt.configure_api()
    games = [g for g in rt.process_candidates() if g[1] == rt.GAME/"RTW3.exe"]
    if len(games) != 1:
        raise ValueError("Open exactly one unmodified local game for the read-only test.")
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x410, False, pid)
    try:
        image, _ = rt.module_info(pid)
        base, blob = rt.text_section(handle, image)
        allocation, data, stack = 0x10000000, 0x20000000, 0x30000000
        class_plans, strings = rules.class_patches(blob, base, allocation)
        engine_plans, native_table, new_table, interpolation, engine = rules.machinery_patches(blob, base, allocation)
        table = rules.extended_table(rt.read(handle, native_table+100, 9000))
        checks = []

        def machine(patched):
            m = Uc(UC_ARCH_X86, UC_MODE_32)
            m.mem_map(base, (len(blob)+4095)//4096*4096)
            m.mem_write(base, blob)
            m.mem_map(allocation, 0x10000)
            m.mem_write(new_table, table)
            m.mem_write(allocation+0x100, interpolation)
            m.mem_write(allocation+0x8000, strings)
            m.mem_map(data, 0x5000); m.mem_map(stack, 0x4000)
            m.reg_write(UC_X86_REG_ESP, stack+0x2000)
            m.reg_write(UC_X86_REG_EBP, stack+0x2100)
            if patched:
                for item in class_plans+engine_plans:
                    m.mem_write(item["address"], bytes.fromhex(item["replacement"]))
            return m

        labels = {p["label"]: p["address"] for p in class_plans}
        cvl = labels["CVL class ceiling"]
        common = base+(cvl-base)+rules.unique(blob[cvl-base:cvl-base+0x50], b"\x84\xdb\x75", "class verdict")

        def class_gate(kind, tons, aircraft=0, speed=30, torpedoes=True, patched=True):
            m = machine(patched)
            if kind == "CA":
                ref = rules.message_ref(blob, base, "A CA must be larger than 4000 tons, have a speed of at least 19 knots, at least 2 inches B armour and main guns larger than 5 in.")
                start = base+ref-0x40+rules.unique(blob[ref-0x40:ref], b"\x8b\x46\x2c\x3d\xa0\x0f\x00\x00", "CA class gate")
            else:
                start = labels[{"DD": "DD class ceiling", "CL": "Pre-1928 CL ceiling",
                                "KE": "KE class ceiling", "CVL": "CVL class ceiling"}[kind]]
            if kind in ("CL", "KE"):
                start -= 3  # mov eax/edi,[esi+displacement]
            elif kind == "CVL":
                start -= 16  # mov edx,[esi+aircraft] and its lower/upper checks
            m.mem_write(data+0x2c, struct.pack("<I", tons))
            m.mem_write(data+0xa20, struct.pack("<I", speed))
            m.mem_write(data+0x9e0, struct.pack("<I", aircraft))
            m.mem_write(data+0x40, struct.pack("<I", 6))
            m.mem_write(data+0x6d, struct.pack("<I", 8))
            m.reg_write(UC_X86_REG_ESI, data)
            m.reg_write(UC_X86_REG_EAX, data+0x2000)
            m.reg_write(UC_X86_REG_EBX, 1)
            # Native register-call helpers: torpedo presence and string assignment.
            dd_off = labels["DD class ceiling"]-base
            call = dd_off+rules.unique(blob[dd_off:dd_off+0x20], b"\xe8", "torpedo call")
            target = base+call+5+struct.unpack_from("<i", blob, call+1)[0]
            m.mem_write(target, b"\xb8"+struct.pack("<I", int(torpedoes))+b"\xc3")
            ref = rules.message_ref(blob, base, "A DD must not be larger than 3800 tons, have a speed of at least 20 knots and have torpedoes.")
            call = ref+4
            assign = base+call+5+struct.unpack_from("<i", blob, call+1)[0]
            m.mem_write(assign, b"\xc3")
            # A late year lets the original CL code reach its final hard cap.
            first = labels["Pre-1928 CL ceiling"]-base
            year_slot, = struct.unpack_from("<I", blob, first+9)
            page = year_slot & ~4095
            m.mem_map(page, 4096)
            m.mem_write(year_slot, struct.pack("<I", data+0x4000))
            m.mem_write(data+0x4000, struct.pack("<I", 1948))
            m.emu_start(start, common, count=1000)
            if m.reg_read(UC_X86_REG_EIP) != common:
                raise AssertionError("Class emulation did not reach the native verdict.")
            return bool(m.reg_read(UC_X86_REG_EBX) & 255)

        def check(label, actual, expected):
            if actual != expected:
                raise AssertionError(f"{label}: expected {expected}, received {actual}")
            checks.append({"case": label, "passed": True})

        check("Worcester CL 14700: original gate rejects", class_gate("CL", 14700, patched=False), False)
        check("Worcester CL 14700: expanded gate accepts", class_gate("CL", 14700), True)
        check("Saipan CVL 14500 / 50 aircraft: original gate rejects", class_gate("CVL", 14500, aircraft=50, patched=False), False)
        check("Saipan CVL 14500 / 50 aircraft: expanded gate accepts", class_gate("CVL", 14500, aircraft=50), True)
        for kind, kwargs in (("DD", {}), ("CL", {}), ("KE", {"torpedoes": False}), ("CVL", {"aircraft": 80})):
            check(kind+" upper boundary accepts", class_gate(kind, rules.LIMITS[kind], **kwargs), True)
            check(kind+" over upper boundary rejects", class_gate(kind, rules.LIMITS[kind]+100, **kwargs), False)
        check("CL minimum displacement retained", class_gate("CL", 2000), False)
        check("CL minimum speed retained", class_gate("CL", 14700, speed=16), False)
        check("DD requires torpedoes", class_gate("DD", 5000, torpedoes=False), False)
        check("DD minimum speed retained", class_gate("DD", 5000, speed=19), False)
        check("KE torpedo restriction retained", class_gate("KE", 4000), False)
        check("CVL 81 aircraft rejects", class_gate("CVL", 20000, aircraft=81), False)
        check("CVL minimum aircraft retained", class_gate("CVL", 20000, aircraft=3), False)

        # Run the original lookup/interpolation instructions, including the
        # native Delphi rounding helper, in an isolated emulated address space.
        native = rt.read(handle, native_table+100, 9000)
        flag_match = list(re.finditer(rb"\x80\x3d(.{4})\x00", blob[engine-base:engine-base+0x100], re.DOTALL))
        if len(flag_match) != 1:
            raise ValueError("Cannot identify machinery initialization flag.")
        flag, = struct.unpack("<I", flag_match[0].group(1))
        stop = engine+rules.unique(blob[engine-base:engine-base+0x300], b"\x80\xbb\xd3\x09\x00\x00\x09", "end of machinery interpolation")

        def power(tons, speed, patched):
            m = machine(patched)
            native_page = native_table & ~4095
            m.mem_map(native_page, ((native_table+9100-native_page+4095)//4096)*4096)
            m.mem_write(native_table+100, native)
            # The flag lies in the unused prefix just before the first table row.
            m.mem_write(flag, b"\x00")
            m.mem_write(data+0x2c, struct.pack("<I", tons))
            m.mem_write(data+0xa20, struct.pack("<I", speed))
            m.reg_write(UC_X86_REG_EBX, data)
            # Begin immediately after the two native SEH frames are installed.
            m.emu_start(engine+0x2a, stop, count=3000)
            if m.reg_read(UC_X86_REG_EIP) != stop:
                raise AssertionError("Machinery emulation did not reach its endpoint.")
            return struct.unpack("<i", m.mem_read(data+0x3c, 4))[0]

        for tons in (1000, 2500, 14700, 17000, 60500, 65000, 70000, 80000, 89900, 90000):
            for speed in (16, 28, 33):
                check(f"Native power unchanged: {tons}t/{speed}kn", power(tons, speed, True), power(tons, speed, False))
        for tons in (90100, 100000, 130000, 199900, 200000):
            for speed in (16, 28, 33):
                result = power(tons, speed, True)
                check(f"Extended power finite/positive: {tons}t/{speed}kn", 0 < result < 2000000000, True)
        engine_cap = next(p["address"] for p in engine_plans if p["label"] == "Machinery hard maximum")
        for tons, patched, allowed in ((90000, False, True), (90100, False, False),
                                       (200000, True, True), (200100, True, False)):
            m = machine(patched)
            m.mem_write(data+0x2c, struct.pack("<I", tons))
            m.reg_write(UC_X86_REG_EBX, data)
            m.emu_start(engine_cap, engine_cap+0x100, count=2)
            check(f"Machinery hard guard {tons}t, expanded={patched}", m.reg_read(UC_X86_REG_EIP) != engine_cap+9, allowed)
        dd = rt.method_address(blob, base, "CheckDDSize")
        dd_ref = rules.message_ref(blob, base, "You cannot build destroyers of that displacement")
        verdict = base+dd_ref-7
        if blob[verdict-base:verdict-base+2] != b"\x84\xdb":
            raise ValueError("Unexpected destroyer hull-technology verdict.")
        dd_call = dd+rules.unique(blob[dd-base:dd-base+0x35], b"\xe8", "destroyer hull-tech call")
        tech = dd_call+5+struct.unpack_from("<i", blob, dd_call-base+1)[0]
        for tons, available, expected in ((10000, True, True), (10000, False, False), (10100, True, False)):
            m = machine(True)
            m.mem_write(tech, b"\xb8"+struct.pack("<I", int(available))+b"\xc3")
            m.reg_write(UC_X86_REG_ESI, tons)
            m.reg_write(UC_X86_REG_EBX, data)
            m.emu_start(labels["DD research hard maximum"], verdict, count=1000)
            if m.reg_read(UC_X86_REG_EIP) != verdict:
                raise AssertionError("Destroyer hull-technology check did not reach its verdict.")
            check(f"DD hull research {tons}t, tech={available}", bool(m.reg_read(UC_X86_REG_EBX)&255), expected)
        for tons in (60500, 65000, 80000):
            check(f"Paper-design tonnage within global ceiling: {tons}t", tons <= rules.LIMITS["overall"], True)
        profiles = json.loads((HERE.parent/"CampaignOverhaul"/"historical_hulls.json").read_text(encoding="utf-8"))
        for item in profiles["benchmarks"]:
            tons = item["game_test_tons"]
            check(item["name"]+": machinery lookup", power(tons, 28, True) > 0, True)
            if item["class"] in ("CL", "CA", "CVL"):
                check(item["name"]+": native class gate", class_gate(item["class"], tons, aircraft=item.get("game_test_aircraft", 0)), True)
        altered = bytearray(blob)
        address = labels["DD class ceiling"]-base
        altered[address+3] ^= 1
        try:
            rules.class_patches(bytes(altered), base, allocation)
        except ValueError:
            check("Altered native class instruction is refused", True, True)
        else:
            raise AssertionError("Altered native class instruction was accepted")
        for p in class_plans:
            if p["label"].startswith("Designer CV limit"):
                m = machine(True)
                m.emu_start(p["address"], p["address"]+5)
                check(p["label"]+" covers United States 65000t", m.reg_read(UC_X86_REG_EAX) >= 65000, True)
        out = {"ok": True, "test_count": len(checks), "checks": checks,
               "live_process_modified": False, "personal_saves_modified": False,
               "scope": "Native class-size gates and machinery lookup; not complete ship designs or gameplay."}
        (HERE/"hull-runtime-test.json").write_text(json.dumps(out, indent=2)+"\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in out.items() if k != "checks"}, indent=2))
    finally:
        rt.K.CloseHandle(handle)


if __name__ == "__main__":
    main()

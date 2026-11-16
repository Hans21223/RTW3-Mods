"""Read-only native legacy-fleet visibility checks in an x86 emulator."""
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).parent / "vendor"))
sys.path.insert(0, str(Path(__file__).parent.parent / "CampaignOverhaul"))
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import *
import weekly_runtime as rt
import legacy_fleet as legacy
import live_cheats


def main():
    rt.configure_api()
    pid, _ = [g for g in rt.process_candidates() if g[1] == rt.GAME/"RTW3.exe"][0]
    handle = rt.K.OpenProcess(0x410, False, pid)
    try:
        image, _ = rt.module_info(pid)
        base, blob = rt.text_section(handle, image)
        original_blob = bytearray(blob)
        # Reconstruct original bytes in this local test buffer only.
        for report in (legacy.REPORT, live_cheats.REPORT):
            if report.exists():
                saved = json.loads(report.read_text(encoding="utf-8"))
                if saved.get("pid") == pid and saved.get("base") == image and saved.get("attached"):
                    for item in saved.get("patches", [saved.get("patch")]):
                        if item:
                            off = item["address"]-base
                            old = bytes.fromhex(item["original"])
                            original_blob[off:off+len(old)] = old
        blob = bytes(original_blob)
        allocation, data, stack = 0x10000000, 0x20000000, 0x30000000
        plans, code, slot = legacy.discover(blob, base, allocation)
        live_layout = live_cheats.discover(blob, base)
        checks = []
        for year in (1890, 1900, 1920, 1935):
            for expanded in (False, True):
                m = Uc(UC_ARCH_X86, UC_MODE_32)
                m.mem_map(base, (len(blob)+4095)//4096*4096); m.mem_write(base, blob)
                m.mem_map(allocation, 0x10000); m.mem_map(data, 0x6000); m.mem_map(stack, 0x2000)
                form, checkbox, vtable = data, data+0x1000, data+0x2000
                first, second = plans[:2]
                field, = struct.unpack_from("<I", blob, first["address"]-base+11)
                m.mem_write(form+field, struct.pack("<I", checkbox))
                m.mem_write(checkbox, struct.pack("<I", vtable))
                m.mem_write(checkbox+0x200, b"\x01")
                m.mem_write(vtable+0x170, struct.pack("<I", allocation+0x8000))
                m.mem_write(allocation+0x8000, b"\x88\x90\x00\x02\x00\x00\xc3")
                # The patched sites call legacy_fleet's placement code, which moves both controls (SetBounds).
                m.mem_write(allocation, code); caption = data+0x4000
                m.mem_write(form+0x4bc, struct.pack("<I", caption)); m.mem_write(caption, struct.pack("<I", vtable))
                m.mem_write(vtable+0xe0, struct.pack("<I", allocation+0x8100)); m.mem_write(allocation+0x8100, b"\xc2\x08\x00")
                call = first["address"]+15
                setter = call+5+struct.unpack_from("<i", blob, call-base+1)[0]
                m.mem_write(setter, b"\x88\x50\x69\xc3")
                m.mem_write(data+0x3000, struct.pack("<I", year))
                m.reg_write(UC_X86_REG_ESI, data+0x3000); m.reg_write(UC_X86_REG_EBX, form)
                m.reg_write(UC_X86_REG_ESP, stack+0x1000)
                if expanded:
                    for item in plans[:2]: m.mem_write(item["address"], bytes.fromhex(item["replacement"]))
                m.emu_start(first["address"], second["address"], count=1000)
                expected = expanded or year == 1900
                assert m.mem_read(checkbox+0x69, 1) == bytes([expected])
                assert m.mem_read(checkbox+0x200, 1) == bytes([expected])
                checks.append({"year": year, "expanded": expanded, "checkbox_visibility_and_selection": True})
                m.reg_write(UC_X86_REG_EDX, 0)
                m.emu_start(second["address"], second["address"]+9)
                assert bool(m.reg_read(UC_X86_REG_EDX)&255) == expected
                checks.append({"year": year, "expanded": expanded, "caption_visibility": True})
        output = {"ok": True, "native_visibility_checks": len(checks), "checks": checks,
                  "live_layout_discovered": live_layout, "live_process_modified_by_test": False,
                  "new_campaign_gameplay_tested": False}
        (Path(__file__).parent/"legacy-runtime-test.json").write_text(json.dumps(output, indent=2)+"\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in output.items() if k not in ("checks", "live_layout_discovered")}, indent=2))
    finally: rt.K.CloseHandle(handle)


if __name__ == "__main__": main()

"""Read-only native discovery and isolated display-gate emulation, no gameplay."""
import json
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import battle_reveal as reveal


class BattleRevealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.base = json.loads((HERE/"native-designer-inspection.json").read_text())["text_base"]
        cls.layout = reveal.discover(cls.blob, cls.base)

    def run_gate(self, site, enabled=0, zoom=1000, hidden=1, sunk=0, newly=0, original=False):
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for at, size in ((0x100000, 0x10000), (0x200000, 0x10000), (0x850000, 0x10000)):
            vm.mem_map(at, size)
        state, ship, form, globe, zoom_object = 0x200000, 0x201000, 0x205000, 0x207000, 0x209000
        vm.mem_write(state, struct.pack("<I", enabled))
        vm.mem_write(ship+self.layout["hidden_field"], bytes([hidden]))
        vm.mem_write(ship+self.layout["sunk_field"], bytes([sunk]))
        vm.mem_write(ship+reveal.field(self.blob, "Newlysighted"), bytes([newly]))
        vm.mem_write(form+0x498, struct.pack("<I", globe))
        vm.mem_write(globe+0x2e0, struct.pack("<I", zoom_object))
        vm.mem_write(zoom_object+0x10, struct.pack("<I", zoom))
        initial = {UC_X86_REG_EAX: zoom_object, UC_X86_REG_EBX: form,
                   UC_X86_REG_ECX: 0x1234, UC_X86_REG_EDX: 0x2345,
                   UC_X86_REG_ESI: ship, UC_X86_REG_EDI: 0x3456,
                   UC_X86_REG_EBP: 0x109000, UC_X86_REG_ESP: 0x108000}
        for reg, value in initial.items(): vm.reg_write(reg, value)
        vm.reg_write(UC_X86_REG_EFLAGS, 0x246)
        if original:
            start = site["address"]
            vm.mem_write(start, bytes.fromhex(site["original"]))
        else:
            start = 0x100000
            code = reveal.thunk(start, state, site, self.layout["sunk_field"])
            self.assertLessEqual(len(code), 0x100)
            vm.mem_write(start, code)
        destinations = []
        def stop(m, address, size, user):
            if address in (site["taken"], site["fall"]):
                destinations.append(address); m.emu_stop()
        vm.hook_add(UC_HOOK_CODE, stop)
        before = bytes(vm.mem_read(0x200000, 0x10000))
        vm.emu_start(start, 0x110000, count=100)
        self.assertEqual(len(destinations), 1)
        self.assertEqual(before, bytes(vm.mem_read(0x200000, 0x10000)), "Display gate wrote game state")
        self.assertEqual(initial, {reg: vm.reg_read(reg) for reg in initial})
        return destinations[0], vm.reg_read(UC_X86_REG_EFLAGS)

    def test_only_four_audited_player_map_sites(self):
        d = self.layout
        self.assertEqual(len(d["sites"]), 4)
        self.assertTrue(d["display_only"])
        for key in ("spotting_changed", "ai_information_changed", "ship_details_unlocked", "battle_gameplay_verified"):
            self.assertFalse(d[key])
        for site in d["sites"]:
            self.assertTrue(d["renderer"] < site["address"] < d["renderer"]+0x300)
            self.assertEqual(self.blob[site["address"]-self.base:site["address"]-self.base+len(bytes.fromhex(site["original"]))].hex(), site["original"])

    def test_disabled_path_matches_native_branch_flags_and_registers(self):
        for site in self.layout["sites"]:
            for zoom in (0, 500, 1000, 1001, 2000, 2001, 50000):
                for hidden in (0, 1):
                    for newly in (0, 1):
                        args = dict(zoom=zoom, hidden=hidden, newly=newly)
                        with self.subTest(site=site["label"], **args):
                            self.assertEqual(self.run_gate(site, **args), self.run_gate(site, original=True, **args))

    def test_enabled_markers_at_every_zoom_with_sunk_filter(self):
        for site in self.layout["sites"][:3]:
            for zoom in (100, 1000, 2000, 50000):
                for hidden in (0, 1):
                    for sunk in (0, 1):
                        target = site[site["force"]]
                        if site["label"] == "hidden marker" and (sunk or (not hidden and zoom <= 1000)):
                            target = site["taken"]
                        elif site["label"] == "detail zoom" and not hidden:
                            target = site["taken"] if zoom > 2000 else site["fall"]
                        self.assertEqual(self.run_gate(site, enabled=1, zoom=zoom, hidden=hidden, sunk=sunk)[0], target)

    def test_known_ships_do_not_get_duplicate_close_zoom_overlay_markers(self):
        site = self.layout["sites"][1]
        self.assertTrue(self.layout["known_ship_rendering_preserved"])
        for zoom in (100, 500, 1000):
            for hidden in (0, 1):
                target, _ = self.run_gate(site, enabled=1, zoom=zoom, hidden=hidden)
                self.assertEqual(target == site["fall"], bool(hidden))
        # Distant native known-ship markers are retained, not removed.
        self.assertEqual(self.run_gate(site, enabled=1, zoom=5000, hidden=0)[0], site["fall"])

    def test_close_zoom_never_enters_new_sighting_update_block(self):
        site = self.layout["sites"][3]
        for newly in (0, 1):
            for zoom in (0, 500, 1000):
                self.assertEqual(self.run_gate(site, enabled=1, zoom=zoom, newly=newly)[0], site["taken"])
            for zoom in (1001, 2000, 50000):
                self.assertEqual(self.run_gate(site, enabled=1, zoom=zoom, newly=newly),
                                 self.run_gate(site, original=True, zoom=zoom, newly=newly))

    def test_changed_native_gate_or_draw_target_is_refused(self):
        for at in [site["address"]-self.base for site in self.layout["sites"]]:
            changed = bytearray(self.blob); changed[at] ^= 1
            with self.assertRaises(ValueError): reveal.discover(bytes(changed), self.base)


if __name__ == "__main__": unittest.main(verbosity=2)

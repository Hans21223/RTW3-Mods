"""Legacy-fleet checkbox and caption: visible in every start year, below the 1920 treaty list (no RTW3 needed)."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import legacy_fleet as legacy

BASE, ALLOC, DATA, STACK = 0x301000, 0x10000000, 0x20000000, 0x30000000
FORM, CHECKBOX, CAPTION, VMT, YEAR, SET_BOUNDS = (DATA, DATA+0x1000, DATA+0x2000, DATA+0x3000, DATA+0x4000,
                                                  DATA+0x5000)
TREATY = DATA+0x5800   # the form's treaty list: the display-scaling reference


class LegacyFleetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.plans, cls.code, _ = legacy.discover(cls.blob, BASE, ALLOC)

    def run_site(self, label, year, treaty_width=193):
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        vm.mem_map(BASE, 0x800000); vm.mem_write(BASE, self.blob)
        vm.mem_map(ALLOC, 0x1000); vm.mem_write(ALLOC, self.code)
        vm.mem_map(DATA, 0x6000); vm.mem_map(STACK, 0x2000)
        for item in self.plans: vm.mem_write(item["address"], bytes.fromhex(item["replacement"]))
        for control, offset in ((CHECKBOX, 0x4ac), (CAPTION, 0x4bc)):
            vm.mem_write(FORM+offset, struct.pack("<I", control)); vm.mem_write(control, struct.pack("<I", VMT))
        vm.mem_write(VMT+0xe0, struct.pack("<I", SET_BOUNDS)); vm.mem_write(SET_BOUNDS, b"\xc2\x08\x00")   # ret 8
        vm.mem_write(YEAR, struct.pack("<I", year))
        vm.mem_write(FORM+0x518, struct.pack("<I", TREATY)); vm.mem_write(TREATY+0x58, struct.pack("<I", treaty_width))
        bounds = []
        vm.hook_add(UC_HOOK_CODE, lambda m, *_: bounds.append((m.reg_read(UC_X86_REG_EAX), m.reg_read(UC_X86_REG_ECX))),
                    begin=SET_BOUNDS, end=SET_BOUNDS)
        for reg, value in ((UC_X86_REG_ESI, YEAR), (UC_X86_REG_EBX, FORM), (UC_X86_REG_EDX, 0),
                           (UC_X86_REG_EDI, 0x33333333), (UC_X86_REG_ESP, STACK+0x1000)):
            vm.reg_write(reg, value)
        site = next(item["address"] for item in self.plans if item["label"] == label)
        vm.emu_start(site, site+9, count=1000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EDX) & 0xff, 1)                    # always visible
        self.assertEqual([vm.reg_read(r) for r in (UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_ESP)],
                         [FORM, YEAR, 0x33333333, STACK+0x1000])
        return bounds

    def test_checkbox_and_caption_move_below_the_treaty_list_only_in_1920(self):
        for year in (1890, 1900, 1920, 1935, 1947):
            moved = year == legacy.TREATY_YEAR
            self.assertEqual(self.run_site("Legacy checkbox", year), [(CHECKBOX, 476 if moved else 405)], year)
            self.assertEqual(self.run_site("Legacy caption", year), [(CAPTION, 474 if moved else 403)], year)
        # Windows display scaling at 150% (the game's list is 290 wide): the same places, scaled like the game's.
        self.assertEqual(self.run_site("Legacy checkbox", 1920, 290), [(CHECKBOX, 476*290//193)])
        self.assertEqual(self.run_site("Legacy caption", 1900, 290), [(CAPTION, 403*290//193)])

    def test_unknown_control_positioning_is_refused(self):
        changed = bytearray(self.blob); changed[legacy.SET_TOP[0]-BASE+3] ^= 1
        with self.assertRaisesRegex(ValueError, "control positioning"):
            legacy.discover(bytes(changed), BASE, ALLOC)


if __name__ == "__main__": unittest.main(verbosity=2)

"""Read-only native audit and isolated x86 tests; never opens a personal save."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import campaign_security as security
import modern_research as audit


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.info = security.discover(cls.blob, 0x301000)

    def vm(self):
        m = Uc(UC_ARCH_X86, UC_MODE_32)
        m.mem_map(0x300000, 0x800000)
        m.mem_map(0x1200000, 0x40000)
        for reg, val in ((UC_X86_REG_EAX, 0x1211000), (UC_X86_REG_EBX, 0x222),
                         (UC_X86_REG_ECX, 0x333), (UC_X86_REG_EDX, 0x444),
                         (UC_X86_REG_ESI, 0x555), (UC_X86_REG_EDI, 0x666),
                         (UC_X86_REG_EBP, 0x1231000), (UC_X86_REG_ESP, 0x1232000),
                         (UC_X86_REG_EFLAGS, 0x247)):
            m.reg_write(reg, val)
        m.mem_write(0x1232000, struct.pack("<I", 0x120f000))
        return m

    def run_until(self, m, start, *ends):
        hook = m.hook_add(UC_HOOK_CODE, lambda vm, address, size, _: vm.emu_stop() if address in ends else None)
        try: m.emu_start(start, 0, count=10000)
        finally: m.hook_del(hook)
        self.assertIn(m.reg_read(UC_X86_REG_EIP), ends)
        return m.reg_read(UC_X86_REG_EIP)

    def test_native_discovery_and_relocation_are_guarded(self):
        delta = 0x510000
        moved = bytearray(self.blob)
        for offset in audit.text_relocations():
            val = struct.unpack_from("<I", moved, offset)[0]
            struct.pack_into("<I", moved, offset, (val+delta) & 0xffffffff)
        found = security.discover(bytes(moved), 0x301000+delta)
        for key in ("spy", "intel", "build", "budget", "random", "main_slot"):
            self.assertEqual(found[key], self.info[key]+delta)
        for name in security.AUDITED:
            changed = bytearray(self.blob)
            changed[self.info["methods"][name]-0x301000] ^= 1
            with self.assertRaisesRegex(ValueError, "changed native code"):
                security.discover(bytes(changed), 0x301000)

    def test_budget_uses_native_intel_total_and_wide_multiply(self):
        for annual, percent in ((120000, 0), (120000, 1), (120000, 10),
                                (2_000_000_000, 10), (0, 10), (120000, 11)):
            m = self.vm(); state, main = 0x1210000, 0x1211000
            m.mem_write(state, struct.pack("<III", percent, 999, 0))
            m.mem_write(main+self.info["player_field"], struct.pack("<I", 0x1218000))
            m.mem_write(self.info["budget"], b"\xb8"+struct.pack("<I", annual)+b"\xc3")
            m.mem_write(0x1200000, security.budget_thunk(0x1200000, state, self.info))
            # Original native tail pops EDI, ESI and EBX before RET.
            m.mem_write(0x1232000, struct.pack("<4I", 0x666, 0x555, 0x222, 0x120f000))
            m.reg_write(UC_X86_REG_ESI, main); m.reg_write(UC_X86_REG_EDI, 90)
            self.run_until(m, 0x1200000, 0x120f000)
            expected = annual*percent//1200 if 0 < percent <= 10 else 0
            self.assertEqual(m.reg_read(UC_X86_REG_EAX), 90+expected)
            self.assertEqual(int.from_bytes(m.mem_read(state+4, 4), "little"), expected)
            for reg, value in ((UC_X86_REG_ECX, 0x333), (UC_X86_REG_EDX, 0x444),
                               (UC_X86_REG_EBX, 0x222), (UC_X86_REG_ESI, 0x555),
                               (UC_X86_REG_EDI, 0x666), (UC_X86_REG_EFLAGS, 0x247)):
                self.assertEqual(m.reg_read(reg), value)

    def test_counterintelligence_targets_only_foreign_spies_and_respects_roll(self):
        for thief, target, percent, roll, blocked in (
                (1, 0, 0, 0, False), (1, 0, 1, 7, True), (1, 0, 1, 8, False),
                (8, 0, 10, 79, True), (8, 0, 10, 80, False),
                (0, 1, 10, 0, False), (2, 3, 10, 0, False),
                (0, 0, 10, 0, False), (9, 0, 10, 0, False), (1, 0, 11, 0, False)):
            m = self.vm(); state = 0x1210000
            m.mem_write(state, struct.pack("<3I", percent, 0, 0))
            m.mem_write(self.info["random"], b"\xb8"+struct.pack("<I", roll)+b"\xc3")
            m.mem_write(0x1200000, security.spy_thunk(0x1200000, state, self.info))
            m.reg_write(UC_X86_REG_EDX, thief); m.reg_write(UC_X86_REG_ECX, target)
            end = self.run_until(m, 0x1200000, self.info["spy"]+9, 0x120f000)
            self.assertEqual(end == 0x120f000, blocked)
            self.assertEqual(int.from_bytes(m.mem_read(state+8, 4), "little"), int(blocked))
            self.assertEqual(m.reg_read(UC_X86_REG_EDX), thief)
            self.assertEqual(m.reg_read(UC_X86_REG_EAX), 0x1211000)
            if blocked:
                self.assertEqual(m.reg_read(UC_X86_REG_ECX), target)
                self.assertEqual(m.reg_read(UC_X86_REG_ESP), 0x1232004)
                self.assertEqual(m.reg_read(UC_X86_REG_EFLAGS), 0x247)

    def test_existing_player_yard_design_cannot_create_an_ai_order(self):
        for player_order, yard, rejected in ((True, 0, False), (True, 2, False),
                                             (False, 0, True), (False, 3, False)):
            m = self.vm(); main, player, design = 0x1211000, 0x1218000, 0x1220000
            m.reg_write(UC_X86_REG_EDI, main); m.reg_write(UC_X86_REG_EAX, design)
            m.mem_write(main+self.info["player_field"], struct.pack("<I", player))
            m.mem_write(0x1231000-12, struct.pack("<I", player if player_order else player+0x100))
            m.mem_write(design+0x1c, struct.pack("<I", yard))
            before = bytes(m.mem_read(main, 0xf000))
            m.mem_write(0x1200000, security.yard_thunk(0x1200000, self.info))
            end = self.run_until(m, 0x1200000, self.info["build_cleanup"], self.info["build"]+9)
            self.assertEqual(end == self.info["build_cleanup"], rejected)
            self.assertEqual(m.reg_read(UC_X86_REG_ESI), design)
            self.assertEqual(m.reg_read(UC_X86_REG_EAX), design)
            self.assertEqual(bytes(m.mem_read(main, 0xf000)), before)

    def test_theft_dispatch_skips_entire_gun_unlock_and_progress_branch(self):
        plan = self.info["static_patches"][0]
        for carry in (0, 1):
            m = self.vm(); address = plan["address"]
            m.mem_write(address, bytes.fromhex(plan["replacement"]))
            m.reg_write(UC_X86_REG_EFLAGS, 0x246+carry)
            destination = self.info["spy"]+0x196f if carry else address+6
            self.assertEqual(self.run_until(m, address, destination), destination)
        plan = self.info["static_patches"][1]
        self.assertEqual(plan["original"], "7e71")
        self.assertEqual(plan["replacement"], "eb71")


if __name__ == "__main__": unittest.main(verbosity=2)

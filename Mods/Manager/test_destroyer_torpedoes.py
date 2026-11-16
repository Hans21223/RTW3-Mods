"""Execute the complete native torpedo-mount validator in isolation."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / "vendor"), str(HERE.parent / "CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
    UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP,
    UC_X86_REG_EIP, UC_X86_REG_EFLAGS,
)
import destroyer_torpedoes as torpedoes
import designer_visuals
import hull_rules
import modern_research as audit

BASE, ALLOCATION = 0x301000, 0x1000000
SHIP, FORM, MOUNT, NATION = 0x200000, 0x202000, 0x204000, 0x206000
STACK, DONE = 0x108000, 0x100F00
ALL_TECH = {0x398, 0x39A, 0x328, 0x32E, 0x6A7}


class DestroyerTorpedoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE / "native-designer-inspection.text.bin").read_bytes()

    def machine(self, patched=True, limit=10000, owned=ALL_TECH):
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address, size in ((0, 0x1000), (0x100000, 0x10000),
                              (SHIP, 0x10000), (0x300000, 0x800000),
                              (ALLOCATION, 0x10000)):
            vm.mem_map(address, size)
        vm.mem_write(BASE, self.blob)
        info = torpedoes.discover(self.blob, BASE, limit)
        built = torpedoes.build(ALLOCATION, info)
        if patched:
            for block in built["blocks"]:
                vm.mem_write(block["address"], bytes.fromhex(block["bytes"]))
            for plan in built["patches"]:
                vm.mem_write(plan["address"], bytes.fromhex(plan["replacement"]))
        # Only external Delphi string handling and nation ID lookup are mocked;
        # the native mount classification, gates, frame, SEH and return execute.
        for address in (0x30B8DC, 0x30B93C, 0x30BCCC, 0x30C464):
            vm.mem_write(address, b"\xc3")
        vm.mem_write(0x30C71C, b"\xc2\x10\x00")

        def research(machine, address, size, unused):
            machine.reg_write(UC_X86_REG_EAX, int(machine.reg_read(UC_X86_REG_EDX) in owned))
            sp = machine.reg_read(UC_X86_REG_ESP)
            machine.reg_write(UC_X86_REG_EIP, struct.unpack("<I", machine.mem_read(sp, 4))[0])
            machine.reg_write(UC_X86_REG_ESP, sp+4)

        vm.hook_add(UC_HOOK_CODE, research, begin=0x729FA4, end=0x729FA4)
        return vm, info, built

    def validate(self, vm, tons, kind=9, position="P", quantity=5, mount_type=0):
        vm.mem_write(SHIP, b"\0" * 0x1000)
        vm.mem_write(SHIP+0x2C, struct.pack("<I", tons))
        vm.mem_write(SHIP+0x9D3, bytes([kind]))
        vm.mem_write(FORM+0xC63, struct.pack("<I", NATION))
        vm.mem_write(MOUNT, b"\0" * 0x100)
        vm.mem_write(MOUNT+4, struct.pack("<I", quantity))
        vm.mem_write(MOUNT+8, struct.pack("<H", ord(position)))
        vm.mem_write(MOUNT+0xE, bytes([mount_type]))
        before = bytes(vm.mem_read(SHIP, 0x1000)), bytes(vm.mem_read(MOUNT, 0x100))
        values = {UC_X86_REG_EAX: FORM, UC_X86_REG_EDX: SHIP, UC_X86_REG_ECX: MOUNT,
                  UC_X86_REG_EBX: 0x1234, UC_X86_REG_ESI: 0x2345,
                  UC_X86_REG_EDI: 0x3456, UC_X86_REG_EBP: 0x109000,
                  UC_X86_REG_ESP: STACK, UC_X86_REG_EFLAGS: 0x246}
        for reg, value in values.items():
            vm.reg_write(reg, value)
        vm.mem_write(STACK, struct.pack("<II", DONE, 0x208000))
        vm.emu_start(torpedoes.VALIDATOR, DONE, count=5000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP), DONE)
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP), STACK+8)
        for reg in (UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP):
            self.assertEqual(vm.reg_read(reg), values[reg])
        self.assertEqual(before, (bytes(vm.mem_read(SHIP, 0x1000)), bytes(vm.mem_read(MOUNT, 0x100))))
        return bool(vm.reg_read(UC_X86_REG_EAX))

    def test_reproduces_reported_P_and_V_rejection_then_accepts_10000t_DD(self):
        old, _, _ = self.machine(False)
        fixed, _, _ = self.machine()
        for position in ("P", "V"):
            self.assertFalse(self.validate(old, 10000, position=position))
            self.assertTrue(self.validate(fixed, 10000, position=position))

    def test_configured_DD_limit_inclusive_and_over_limit_rejected(self):
        for limit in (3800, 7000, 10000, 15000, 280000):
            vm, _, _ = self.machine(limit=limit)
            effective = max(7000, limit)
            for position in ("P", "V"):
                self.assertTrue(self.validate(vm, effective, position=position))
                self.assertFalse(self.validate(vm, effective+1, position=position))

    def test_native_research_gates_still_required(self):
        for owned, tons, expected in ((set(), 2500, True), (set(), 2501, False),
                                      ({0x398}, 3500, True), ({0x398}, 3501, False),
                                      ({0x39A}, 10000, True), (set(), 10000, False)):
            vm, _, _ = self.machine(owned=owned)
            self.assertEqual(self.validate(vm, tons), expected, (owned, tons))
        vm, _, _ = self.machine(owned=set())
        self.assertFalse(self.validate(vm, 10000, mount_type=7))

    def test_other_ship_classes_keep_original_verdicts_and_7000t_cap(self):
        old, _, _ = self.machine(False)
        fixed, _, _ = self.machine()
        for kind in range(16):
            if kind == 9:
                continue
            for tons in (2500, 3500, 7000, 7001, 10000, 20000):
                self.assertEqual(self.validate(fixed, tons, kind), self.validate(old, tons, kind))
        self.assertTrue(self.validate(fixed, 7000, kind=4))
        self.assertFalse(self.validate(fixed, 7001, kind=4))
        self.assertFalse(self.validate(fixed, 7000, kind=7))  # original AMC prohibition

    def test_original_range_and_non_centreline_or_empty_mounts_preserved(self):
        old, _, _ = self.machine(False)
        fixed, _, _ = self.machine()
        for tons in (200, 500, 2500, 2501, 3500, 3501, 3800, 7000):
            for position in ("P", "V", "F", "0"):
                self.assertEqual(self.validate(fixed, tons, position=position),
                                 self.validate(old, tons, position=position))
        for args in (dict(position="F"), dict(quantity=0), dict(mount_type=2)):
            self.assertEqual(self.validate(fixed, 20000, **args), self.validate(old, 20000, **args))

    def test_compare_thunk_preserves_registers_stack_and_native_flags(self):
        vm, info, built = self.machine()
        start = ALLOCATION+torpedoes.CODE_OFFSET
        for kind, tons in ((9, 10000), (9, 10001), (4, 7000), (4, 7001)):
            vm.mem_write(SHIP+0x2C, struct.pack("<I", tons))
            vm.mem_write(SHIP+0x9D3, bytes([kind]))
            values = {UC_X86_REG_EAX: 0x1234, UC_X86_REG_EBX: 0x2345,
                      UC_X86_REG_ECX: 0x3456, UC_X86_REG_EDX: 0x4567,
                      UC_X86_REG_ESI: 0x5678, UC_X86_REG_EDI: SHIP,
                      UC_X86_REG_EBP: 0x109000, UC_X86_REG_ESP: STACK}
            for reg, value in values.items():
                vm.reg_write(reg, value)
            vm.emu_start(start, info["resume"], count=100)
            self.assertEqual(vm.reg_read(UC_X86_REG_EIP), info["resume"])
            for reg, value in values.items():
                self.assertEqual(vm.reg_read(reg), value)
            flags = vm.reg_read(UC_X86_REG_EFLAGS)
            self.assertEqual(bool(flags & 0x40), tons == (10000 if kind == 9 else 7000))

    def test_reservations_do_not_overlap_other_large_hull_components(self):
        _, info, built = self.machine()
        visuals = designer_visuals.build(ALLOCATION, designer_visuals.discover(self.blob, BASE))
        _, strings = hull_rules.class_patches(self.blob, BASE, ALLOCATION)
        blocks = [(block["address"], len(bytes.fromhex(block["bytes"])), block["name"])
                  for block in built["blocks"]+visuals["blocks"]]
        blocks += [(ALLOCATION, 0x100, "input"), (ALLOCATION+0x100, 0x100, "machinery thunk"),
                   (ALLOCATION+0x300, 245, "class suggestion"),
                   (ALLOCATION+0x1000, 282*100, "max machinery table"),
                   (ALLOCATION+0x8000, len(strings), "class messages"),
                   (ALLOCATION+0xF000, 8, "visual menu state")]
        blocks.sort()
        for left, right in zip(blocks, blocks[1:]):
            self.assertLessEqual(left[0]+left[1], right[0], (left, right))
        self.assertLessEqual(blocks[-1][0]+blocks[-1][1], ALLOCATION+65536)
        message = built["blocks"][1]
        text = bytes.fromhex(message["bytes"])[12:-2].decode("utf-16-le")
        self.assertIn("10000", text)
        self.assertIn("7000", text)

    def test_changed_native_code_and_invalid_settings_refused(self):
        for address in (torpedoes.VALIDATOR, 0x5E630E, torpedoes.SITE, 0x5E6410):
            blob = bytearray(self.blob)
            blob[address-BASE] ^= 1
            with self.assertRaises(ValueError):
                torpedoes.discover(bytes(blob), BASE, 10000)
        for invalid in (True, 3799, 280001, "10000", 10000.0):
            with self.assertRaises(ValueError):
                torpedoes.discover(self.blob, BASE, invalid)

    def test_aslr_relocated_build_discovered(self):
        delta = 0x400000
        blob = bytearray(self.blob)
        for offset in audit.text_relocations():
            value = struct.unpack_from("<I", blob, offset)[0]
            struct.pack_into("<I", blob, offset, (value+delta) & 0xFFFFFFFF)
        info = torpedoes.discover(bytes(blob), BASE+delta, 15000)
        self.assertEqual(info["site"], torpedoes.SITE+delta)
        self.assertEqual(info["dd_limit"], 15000)


if __name__ == "__main__":
    unittest.main()

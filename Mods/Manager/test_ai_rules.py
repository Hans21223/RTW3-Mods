"""Offline native-code tests. No running game or personal save is modified."""
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
import ai_rules as rules
import ai_runtime as runtime
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *


class AIRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Retained, unpacked code from the supported authenticated game build.
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.base = json.loads((HERE/"native-designer-inspection.json").read_text())["text_base"]

    def plans(self, mode, blob=None):
        return rules.discover(self.blob if blob is None else blob, self.base, mode)

    def vm(self):
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        vm.mem_map(0x100000, 0x10000)
        vm.mem_map(0x200000, 0x10000)
        vm.mem_map(0x300000, 0x10000)
        vm.reg_write(UC_X86_REG_ESP, 0x30f000)
        return vm

    def test_torpedo_discovery_changes_exactly_two_single_byte_roll_bounds(self):
        plans, details = self.plans("torpedo-initiative")
        self.assertEqual(len(plans), 2)
        for p in plans:
            self.assertEqual(p["original"], "64")
            self.assertEqual(p["replacement"], "4b")
        self.assertEqual(details["assessment_roll_after"], 75)
        self.assertEqual(details["applies_to"], "both sides, automated torpedo decisions")
        self.assertFalse(details["hit_chances_changed"])

    def test_all_final_launch_and_hit_logic_is_byte_identical(self):
        plans, details = self.plans("torpedo-initiative")
        edited = bytearray(self.blob)
        for p in plans:
            at = p["address"]-self.base
            edited[at:at+1] = bytes.fromhex(p["replacement"])
        start = details["automatic_fire"]-self.base
        self.assertEqual(edited[start:], self.blob[start:])
        self.assertEqual(sum(a != b for a, b in zip(edited, self.blob)), 2)

    def test_opportunity_thresholds_still_reject_zero_and_negative_interest(self):
        # The native JGE still rejects zero/negative thresholds. A larger
        # assessment chance cannot turn a rejected target into a forced launch.
        for threshold in (-10, 0, 1, 10, 40, 70, 100):
            for bound in (100, 75):
                for roll in (0, bound//2, bound-1):
                    vm = self.vm()
                    vm.mem_write(0x30f004, struct.pack("<i", threshold))
                    code = b"\x3b\x44\x24\x04\x7d\x07\xbb\x01\x00\x00\x00\xeb\x05\xbb\x00\x00\x00\x00"
                    vm.mem_write(0x100000, code)
                    vm.reg_write(UC_X86_REG_EAX, roll)
                    vm.emu_start(0x100000, 0x100000+len(code))
                    self.assertEqual(vm.reg_read(UC_X86_REG_EBX), int(roll < threshold))

    def test_more_assessments_without_claiming_more_hits(self):
        for threshold in (10, 20, 40, 70):
            old = sum(r < threshold for r in range(100))/100
            new = sum(r < threshold for r in range(75))/75
            self.assertGreater(new, old)
            self.assertLessEqual(new, 1)

    def test_changed_torpedo_gate_is_refused(self):
        plans, _ = self.plans("torpedo-initiative")
        b = bytearray(self.blob)
        b[plans[0]["address"]-self.base] = 99
        with self.assertRaises(ValueError):
            self.plans("torpedo-initiative", bytes(b))

    def test_fairness_discovery_and_equal_patch_sizes(self):
        plans, details = self.plans("fair-ai")
        self.assertEqual(len(plans), 7)
        self.assertEqual(details["advantage_decision_reads_disabled"], 6)
        self.assertEqual(details["emergency_grant_removed"], 2000)
        self.assertFalse(details["all_ai_asymmetries_audited"])
        self.assertFalse(details["campaign_settings_edited"])
        for p in plans:
            self.assertEqual(len(bytes.fromhex(p["original"])), len(bytes.fromhex(p["replacement"])))

    def test_five_advantage_checks_match_disabled_option_flags_and_preserve_registers(self):
        plans, details = self.plans("fair-ai")
        registers = (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
                     UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_ESP)
        for p in plans[:5]:
            results = []
            for kind, option in (("original", 0), ("replacement", 0), ("replacement", 1)):
                vm = self.vm()
                for reg in registers[:-1]:
                    vm.reg_write(reg, 0x200000)
                vm.mem_write(0x200000+details["advantage_field"], bytes([option]))
                code = bytes.fromhex(p[kind])
                vm.mem_write(0x100000, code)
                vm.emu_start(0x100000, 0x100000+len(code))
                results.append(([vm.reg_read(r) for r in registers], vm.reg_read(UC_X86_REG_EFLAGS)))
            self.assertEqual(results[0], results[1])
            self.assertEqual(results[0], results[2])

    def test_arithmetic_advantage_matches_off_without_changing_flags(self):
        plans, details = self.plans("fair-ai")
        for option in (0, 1):
            vm = self.vm()
            vm.reg_write(UC_X86_REG_EDI, 0x200000)
            vm.reg_write(UC_X86_REG_EFLAGS, 0x246)
            vm.mem_write(0x200000+details["advantage_field"], bytes([option]))
            code = bytes.fromhex(plans[5]["replacement"])
            vm.mem_write(0x100000, code)
            vm.emu_start(0x100000, 0x100000+len(code))
            self.assertEqual(vm.reg_read(UC_X86_REG_EDX), 0)
            self.assertEqual(vm.reg_read(UC_X86_REG_EFLAGS), 0x246)

    def test_grant_event_is_skipped_without_cash_write_or_message_call(self):
        plans, details = self.plans("fair-ai")
        p = plans[-1]
        vm = self.vm()
        vm.reg_write(UC_X86_REG_EBX, 0x200000)
        vm.mem_write(0x200000+details["nation_funds_field"], struct.pack("<i", -20000))
        at = p["address"]-self.base
        code = bytes.fromhex(p["replacement"]) + self.blob[at+10:at+75]
        vm.mem_write(0x100000, code)
        visited = []
        vm.hook_add(UC_HOOK_CODE, lambda m, a, n, u: visited.append(a))
        vm.emu_start(0x100000, 0x100000+75, count=20)
        self.assertEqual(visited, [0x100000])
        self.assertEqual(struct.unpack("<i", vm.mem_read(0x200000+details["nation_funds_field"], 4))[0], -20000)
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP), 0x30f000)

    def test_unknown_advantage_consumer_count_is_refused(self):
        plans, _ = self.plans("fair-ai")
        b = self.blob + bytes.fromhex(plans[0]["original"])
        with self.assertRaises(ValueError):
            self.plans("fair-ai", b)

    def test_changed_grant_is_refused(self):
        _, d = self.plans("fair-ai")
        b = self.blob.replace(b"\x81\x83"+struct.pack("<II", d["nation_funds_field"], 2000),
                              b"\x81\x83"+struct.pack("<II", d["nation_funds_field"], 3000))
        with self.assertRaises(ValueError):
            self.plans("fair-ai", b)

    def test_both_mods_are_disjoint(self):
        a, _ = self.plans("torpedo-initiative")
        b, _ = self.plans("fair-ai")
        addresses = lambda ps: {p["address"]+i for p in ps for i in range(len(bytes.fromhex(p["original"])))}
        self.assertFalse(addresses(a) & addresses(b))

    def test_partial_attach_failure_rolls_back(self):
        plans, _ = self.plans("torpedo-initiative")
        memory = {p["address"]: bytes.fromhex(p["original"]) for p in plans}
        calls = []
        def write(handle, at, before, after):
            self.assertEqual(memory[at], before)
            calls.append(at)
            if len(calls) == 2:
                raise OSError("simulated failure")
            memory[at] = after
        with patch.object(runtime.rt, "read", side_effect=lambda h, a, n: memory[a]), patch.object(runtime.rt, "write_code", side_effect=write):
            with self.assertRaisesRegex(OSError, "simulated"):
                runtime.apply_plans(None, plans)
        for p in plans:
            self.assertEqual(memory[p["address"]], bytes.fromhex(p["original"]))

    def test_conflict_is_refused_before_any_write(self):
        plans, _ = self.plans("fair-ai")
        with patch.object(runtime.rt, "read", return_value=b"\xcc"*7), patch.object(runtime.rt, "write_code") as write:
            with self.assertRaises(ValueError):
                runtime.apply_plans(None, plans)
            write.assert_not_called()

    def test_loaded_campaign_and_null_main_are_refused(self):
        layout = {"main_slot": 0x1000, "player_field": 0x200}
        for values in ([0], [0x2000, 0x3000]):
            with patch.object(runtime.live, "integer", side_effect=values):
                with self.assertRaisesRegex(ValueError, "no live AI rule swap"):
                    runtime.require_title_screen(None, layout)
        with patch.object(runtime.live, "integer", side_effect=[0x2000, 0]):
            runtime.require_title_screen(None, layout)

    def test_unknown_adapter_refused(self):
        with self.assertRaises(ValueError):
            self.plans("unreviewed-ai")
        with self.assertRaises(ValueError):
            runtime.report_path("../other")


if __name__ == "__main__":
    unittest.main(verbosity=2)

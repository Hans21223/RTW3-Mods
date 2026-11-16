"""Native instruction and limited mine knowledge audit tests; no gameplay."""
import json
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
import ai_rules
import hazard_rules as hazards
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *


class HazardRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.base = json.loads((HERE/"native-designer-inspection.json").read_text())["text_base"]

    def plans(self, blob=None):
        return hazards.discover(self.blob if blob is None else blob, self.base)

    def vm(self):
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for page in (0x100000, 0x200000, 0x300000):
            vm.mem_map(page, 0x10000)
        vm.reg_write(UC_X86_REG_ESP, 0x30f000)
        return vm

    def test_seven_verified_sites_and_honest_scope(self):
        plans, d = self.plans()
        self.assertEqual(len(plans), 7)
        self.assertEqual(d["predictive_decision_blocks_skipped"], 6)
        self.assertTrue(d["predictive_following_disabled"])
        self.assertTrue(d["new_battles_required"])
        self.assertTrue(d["native_last_minute_torpedo_evasion_preserved"])
        self.assertFalse(d["projectile_spotting_model_added"])
        self.assertFalse(d["full_ai_information_access_audited"])
        self.assertFalse(d["mine_knowledge_audit"]["mine_avoidance_changed"])
        for p in plans:
            self.assertEqual(len(bytes.fromhex(p["original"])), len(bytes.fromhex(p["replacement"])))

    def test_predictive_blocks_do_not_write_stance_threat_or_log(self):
        plans, _ = self.plans()
        for p in plans[:6]:
            vm = self.vm()
            at = p["address"]-self.base
            code = bytes.fromhex(p["replacement"])
            end = 5+struct.unpack_from("<i", code, 1)[0]
            vm.mem_write(0x100000, code+self.blob[at+7:at+end])
            vm.reg_write(UC_X86_REG_EBX, 0x200000)
            vm.mem_write(0x20002f, b"\x03")
            vm.mem_write(0x20002b, struct.pack("<I", 0x12345678))
            registers = (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX,
                         UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_ESP)
            for index, reg in enumerate(registers[:-1]):
                vm.reg_write(reg, 0x11223300+index)
            before = [vm.reg_read(r) for r in registers]
            vm.reg_write(UC_X86_REG_EFLAGS, 0x246)
            visited = []
            vm.hook_add(UC_HOOK_CODE, lambda m, a, n, u: visited.append(a))
            vm.emu_start(0x100000, 0x100000+end, count=10)
            self.assertEqual(visited, [0x100000])
            self.assertEqual(vm.mem_read(0x20002f, 1), b"\x03")
            self.assertEqual(struct.unpack("<I", vm.mem_read(0x20002b, 4))[0], 0x12345678)
            self.assertEqual(before, [vm.reg_read(r) for r in registers])
            self.assertEqual(vm.reg_read(UC_X86_REG_EFLAGS), 0x246)

    def test_follower_does_not_copy_predictive_course(self):
        p = self.plans()[0][-1]
        at = p["address"]-self.base
        code = bytes.fromhex(p["replacement"])+self.blob[at+1:at+2]
        end = 2+struct.unpack("<b", code[1:2])[0]
        vm = self.vm()
        vm.mem_write(0x100000, code+self.blob[at+2:at+end])
        visited = []
        vm.hook_add(UC_HOOK_CODE, lambda m, a, n, u: visited.append(a))
        vm.reg_write(UC_X86_REG_EFLAGS, 0x246)  # even if leader WAS in stance 6
        vm.emu_start(0x100000, 0x100000+end, count=10)
        self.assertEqual(visited, [0x100000])
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP), 0x30f000)

    def test_no_changes_to_mine_hits_torpedo_hits_or_weapon_movement(self):
        plans, d = self.plans()
        edited = bytearray(self.blob)
        for p in plans:
            at = p["address"]-self.base
            edited[at:at+len(bytes.fromhex(p["replacement"]))] = bytes.fromhex(p["replacement"])
        # All sites are in AI stance decisions; the native collision, damage,
        # late torpedo evasion and mine proximity/detection code stays intact.
        for method, size in (("HandleTorpedoHit", 0x1000), ("CheckEvading", 0x70)):
            at = hazards.rt.method_address(self.blob, self.base, method)-self.base
            self.assertEqual(edited[at:at+size], self.blob[at:at+size])
        q = d["mine_knowledge_audit"]["query"]-self.base
        self.assertEqual(edited[q:q+0x138], self.blob[q:q+0x138])

    def test_mine_routing_has_three_actual_ship_arguments(self):
        audit = self.plans()[1]["mine_knowledge_audit"]
        self.assertEqual(len(audit["explicit_ship_ai_query_calls"]), 3)
        self.assertFalse(audit["mine_detection_and_damage_changed"])

    def test_actual_mine_query_skips_both_layers_when_ship_is_supplied(self):
        audit = self.plans()[1]["mine_knowledge_audit"]
        at = audit["ship_guard"]-self.base
        branch = audit["ship_layer_branch"]-self.base
        code = self.blob[at:branch]
        vm = self.vm()
        vm.mem_write(0x100000, code)
        vm.reg_write(UC_X86_REG_EBX, 0x200000)
        visited = []
        vm.hook_add(UC_HOOK_CODE, lambda m, a, n, u: visited.append(a))
        vm.emu_start(0x100000, 0x100000+len(code), count=10)
        self.assertEqual(visited, [0x100000, 0x100002])
        # The actual selected layer uses ship.Side, never the enemy side here.
        self.assertEqual(self.blob[branch+3:branch+9], b"\x8b\x83\x55\x0a\x00\x00")

    def test_changed_decision_prefix_refused(self):
        p = self.plans()[0][0]
        b = bytearray(self.blob)
        b[p["address"]-self.base+3] = 5
        with self.assertRaises(ValueError):
            self.plans(bytes(b))

    def test_extra_predictive_assignment_refused(self):
        with self.assertRaises(ValueError):
            self.plans(self.blob+b"\xc6\x43\x2f\x06")

    def test_changed_mine_ship_side_or_nil_guard_refused(self):
        audit = self.plans()[1]["mine_knowledge_audit"]
        for at in (audit["ship_layer_branch"]-self.base+5, audit["ship_guard"]-self.base+2):
            b = bytearray(self.blob)
            b[at] ^= 1
            with self.assertRaises(ValueError):
                self.plans(bytes(b))

    def test_ai_mods_have_no_overlapping_writes(self):
        used = set()
        for mode in ("torpedo-initiative", "fair-ai", "detection-only-evasion"):
            plans, _ = ai_rules.discover(self.blob, self.base, mode)
            locations = {p["address"]+i for p in plans for i in range(len(bytes.fromhex(p["original"])))}
            self.assertFalse(used & locations)
            used |= locations


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Freed design rules (hull_rules.FREED_*, vls_cells.FREED_RULES) on the retained native code.

Each patch replaces whole instructions right behind a real conditional jump that skips the same block
when the rule is met; the unpatched code from there is that rule's failure (it runs the check's
"not allowed" store); and the skipped code names only freed rules, never a kept research, treaty,
weight or naming error. The DP clamp sends 3- and 4-gun mounts to the native test as twin mounts.
"""
from pathlib import Path
import re
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
                               UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)
import hull_rules
import vls_cells

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
BASE, ALLOCATION = 0x301000, 0x10000000
# The checks that hold freed rules (start, end) -> CHECKS kind: the design report up to the
# modern-research hook, TurretCheck, TurretGunsOK, TurretPositionOK, the superimposed-turret test,
# the armour check and the two balance checks.
# The superimposed-turret test has a jump table at 0x732964-0x7329B8.
FUNCTIONS = {(0x5D316C, 0x5D7290): "report", (0x728308, 0x728960): "turrets", (0x7294CC, 0x7295D1): "mount",
             (0x729954, 0x72999A): "mount", (0x73270C, 0x732964): "mount", (0x7329B8, 0x732C04): "mount",
             (0x947208, 0x947337): "armour", (0x947E08, 0x947E6A): "balance", (0x947EAC, 0x947F73): "launchers"}
DATA, STACK = 0x20000000, 0x30000000
CONSTANT = b"\xb0\x04\x02\x00\xff\xff\xff\xff"   # Delphi string literal header: UTF-16, never freed
VLS_MESSAGES = ("Error:  Carriers cannot carry heavy SAM mounts!",
                "Maximum 2 launchers for non centreline mounts on ships below 1200 tons.",
                "Maximum 2 tubes for non centreline torpedo mounts on ships below 1200 tons.",
                "Maximum 3 launchers for non centreline mounts on ships below 6000 tons.",
                "Maximum 3 tubes for non centreline torpedo mounts on ships below 6000 tons.")
FRAGMENTS = ("Error: Missile mount ", "Error: Torpedo mount ", " must have an armour deck!",
             " secondary and tertiary guns")   # parts of freed messages
KEPT = ("Error: Building nation has not developed flight deck catapults!", "Error: Ship is seriously overweight!",
        "Error! Ship is dangerously top heavy! Reduce AA guns or other topside equipment!",
        "Error: Ship class must have a name!", "Error: Ship exceeds treaty limitations!",
        "Error: Design parameters outside legal ship types! ", "Error: Maximum 16 gun mounts!",
        "Error: Ships can have a maximum of 20 main guns!", "Error: A carrier must have a flight deck!",
        "Error: To have triple secondary turrets on BB or BC, you must have researched triple turrets for CL!",
        "Double mounts for DD not researched", "Triple turrets not researched", "Quadruple turrets not researched",
        ") has not invented wing turrets for main battery guns > 7 inches in double turrets!",
        ". Building nation has not developed dual purpose mountings for that calibre or gun combination.",
        "Ship cannot have additional deck armour if it has no deck armour",
        "Cannot combine A or B with 1 or 2 turret positions.")


def literal(address):
    """The string literal a code operand points to, or None."""
    offset = address-BASE
    if not 12 <= offset < len(BLOB) or BLOB[offset-12:offset-4] != CONSTANT:
        return None
    return BLOB[offset:offset+2*struct.unpack_from("<I", BLOB, offset-4)[0]].decode("utf-16-le")


class FreedRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        cls.code, cls.kind = {}, {}
        for (start, end), kind in FUNCTIONS.items():
            for insn in md.disasm(BLOB[start-BASE:end-BASE], start):
                cls.code[insn.address], cls.kind[insn.address] = insn, kind
        cls.before = {i.address+i.size: i for i in cls.code.values()}
        cls.targets = {int(i.op_str, 16) for i in cls.code.values() if i.mnemonic.startswith("j") and i.op_str.startswith("0x")}
        cls.vls_names = {"VLS cells: "+name for name, *_ in vls_cells.FREED_RULES}
        cls.vls = vls_cells.build(ALLOCATION, vls_cells.discover(BLOB, BASE))["patches"]
        cls.plans = hull_rules.freed_error_patches(BLOB, BASE)+[p for p in cls.vls if p["label"] in cls.vls_names]
        cls.freed = ({m for m, _ in hull_rules.FREED_ERRORS} | {m for _, m in hull_rules.FREED_REASONS}
                     | {m for *_, m in hull_rules.FREED_PREFIXED} | set(VLS_MESSAGES) | set(FRAGMENTS))
        cls.native = {p["address"]: cls.run_block(p["address"], cls.destination(p)) for p in cls.plans}

    @staticmethod
    def destination(plan):
        start, code = plan["address"], bytes.fromhex(plan["replacement"])
        return start+2+struct.unpack("<b", code[1:2])[0] if code[0] == 0xEB else start+5+struct.unpack("<i", code[1:5])[0]

    @classmethod
    def messages(cls, addresses):
        found = set()
        for address in addresses:
            insn = cls.code.get(address)
            for at in range(address+1, address+insn.size-3) if insn else ():
                text = literal(struct.unpack_from("<I", BLOB, at-BASE)[0])
                if text is not None: found.add(text)
        return found

    @classmethod
    def run_block(cls, start, end, plan=None):
        """Runs from `start` until control leaves [start, end); native helper calls return 0.
        Returns whether the check's "not allowed" store ran, where control left, and the path."""
        flag = hull_rules.CHECKS[cls.kind[start]][1]
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        page = start & ~0xFFF
        vm.mem_map(page, 0x2000); vm.mem_write(page, BLOB[page-BASE:page-BASE+0x2000])
        if plan: vm.mem_write(plan["address"], bytes.fromhex(plan["replacement"]))
        for address in (0, DATA, STACK): vm.mem_map(address, 0x10000)
        frame = STACK+0x8000
        vm.mem_write(frame-0xC, struct.pack("<I", DATA+0x8000))   # report error lines: any object
        for reg, value in ((UC_X86_REG_EBP, frame), (UC_X86_REG_ESP, frame-0x400), (UC_X86_REG_EBX, DATA),
                           (UC_X86_REG_ESI, DATA+0x2000), (UC_X86_REG_EDI, DATA+0x4000)):
            vm.reg_write(reg, value)
        stored, left, path = [], [], []

        def step(vm, address, size, _):
            if not start <= address < end:
                left.append(address); vm.emu_stop(); return
            path.append(address)
            if cls.code[address].mnemonic == "call":
                vm.reg_write(UC_X86_REG_EAX, 0); vm.reg_write(UC_X86_REG_EIP, address+size)
            elif bytes(vm.mem_read(address, size)) == flag:
                stored.append(address)
        vm.hook_add(UC_HOOK_CODE, step)
        vm.emu_start(start, 0, count=500)
        return bool(stored), left[0] if left else None, path

    def test_every_freed_rule_is_found_once_per_check(self):
        expected = (sum(n for _, n in hull_rules.FREED_ERRORS)+len(hull_rules.FREED_REASONS)
                    + len(hull_rules.FREED_PREFIXED)+len(vls_cells.FREED_RULES))
        self.assertEqual(len(self.plans), expected)
        self.assertEqual(len({p["address"] for p in self.plans}), len(self.plans))

    def test_each_patch_skips_exactly_its_own_rule_behind_its_guard(self):
        for plan in self.plans:
            start, end, length = plan["address"], self.destination(plan), len(bytes.fromhex(plan["replacement"]))
            with self.subTest(plan["label"]):
                self.assertIn(start, self.code)                       # whole instructions
                guard = self.before[start]
                self.assertTrue(guard.mnemonic.startswith("j") and guard.mnemonic != "jmp", guard.mnemonic)
                self.assertEqual(int(guard.op_str, 16), end)          # the rule's own "rule met" jump
                self.assertFalse([t for t in self.targets if start < t < start+length])
                stored, left, path = self.native[start]
                self.assertTrue(stored and left is not None)                          # native: the rule fails
                self.assertEqual(self.run_block(start, end, plan)[:2], (False, end))  # patched: skipped
                named = {m for m in self.messages(path) if len(m) >= 20}              # what the skip bypasses
                self.assertLessEqual(named, self.freed, named-self.freed)

    def test_kept_errors_stay_reachable(self):
        bypassed = {address for _, _, path in self.native.values() for address in path}
        found = set()
        for address in self.code:
            for message in self.messages((address,)) & set(KEPT):
                found.add(message)
                self.assertNotIn(address, bypassed, message)
        self.assertEqual(found, set(KEPT))

    def test_dp_triple_and_quad_mounts_are_tested_as_twins_in_the_designer_only(self):
        plans, data = hull_rules.class_patches(BLOB, BASE, ALLOCATION)
        calls = [p for p in plans if p["label"].startswith("DP triple/quad")]
        self.assertEqual(len(calls), 11)
        test = calls[0]["address"]+5+struct.unpack("<i", bytes.fromhex(calls[0]["original"])[1:])[0]
        clamp = calls[0]["address"]+5+struct.unpack("<i", bytes.fromhex(calls[0]["replacement"])[1:])[0]
        for plan in calls:   # every redirected call used to reach the native DP test
            self.assertEqual(plan["address"]+5+struct.unpack("<i", bytes.fromhex(plan["original"])[1:])[0], test)
        native = [m.start() for m in re.finditer(rb"\xe8", BLOB[:-5])
                  if BASE+m.start()+5+struct.unpack_from("<i", BLOB, m.start()+1)[0] == test]
        self.assertEqual(len(native)-len(calls), 10)                  # AI and ship-code callers stay native
        for guns, asked in ((1, 1), (2, 2), (3, 2), (4, 2), (5, 5), (0x63, 0x63)):
            vm = Uc(UC_ARCH_X86, UC_MODE_32)
            vm.mem_map(ALLOCATION, 0x10000); vm.mem_write(ALLOCATION+0x8000, data)
            vm.reg_write(UC_X86_REG_EDX, guns)
            vm.emu_start(clamp, test, count=10)
            self.assertEqual((vm.reg_read(UC_X86_REG_EIP), vm.reg_read(UC_X86_REG_EDX)), (test, asked), guns)

    def test_catapult_counts_are_free_but_catapult_research_still_applies(self):
        plan = hull_rules.catapult_patch(BLOB, BASE)
        check, count_of, assign, campaign = 0x5EE340, 0x94F7FC, 0x30BCCC, 0x9F7324   # CatapultsOK and helpers

        def allowed(kind, count, researched=True, patched=True, angled=0, tons=20000):
            vm = Uc(UC_ARCH_X86, UC_MODE_32)
            vm.mem_map(0x300000, 0x800000); vm.mem_write(BASE, BLOB)
            if patched: vm.mem_write(plan["address"], bytes.fromhex(plan["replacement"]))
            for address in (DATA, STACK): vm.mem_map(address, 0x10000)
            form, ship, flag, reason, sp = DATA, DATA+0x1000, DATA+0x3000, DATA+0x3100, STACK+0x8000
            vm.mem_write(campaign, struct.pack("<I", flag)); vm.mem_write(flag, b"\x01")   # campaign: research counts
            vm.mem_write(ship+0x9D3, bytes([kind])); vm.mem_write(ship+0x9DA, bytes([angled]))
            vm.mem_write(ship+0x2C, struct.pack("<I", tons)); vm.mem_write(sp, struct.pack("<II", 0x1000, reason))
            messages = []

            def native(vm, address, size, _):
                result = {count_of: count, 0x729FA4: int(researched), assign: 0}.get(address)
                if result is None: return
                if address == assign: messages.append(vm.reg_read(UC_X86_REG_EDX))
                top = vm.reg_read(UC_X86_REG_ESP)
                vm.reg_write(UC_X86_REG_EAX, result); vm.reg_write(UC_X86_REG_ESP, top+4)
                vm.reg_write(UC_X86_REG_EIP, struct.unpack("<I", vm.mem_read(top, 4))[0])
            vm.hook_add(UC_HOOK_CODE, native)
            for reg, value in ((UC_X86_REG_EAX, form), (UC_X86_REG_EDX, ship), (UC_X86_REG_ESP, sp), (UC_X86_REG_EBP, STACK+0x9000)):
                vm.reg_write(reg, value)
            vm.reg_write(UC_X86_REG_ECX, 0)
            vm.mem_map(0, 0x2000)
            vm.emu_start(check, 0x1000, count=2000)
            self.assertEqual(vm.reg_read(UC_X86_REG_ESP), sp+8)   # ret 4
            return bool(vm.reg_read(UC_X86_REG_EAX) & 0xFF), len(messages)

        for kind, count, extra in ((9, 1, {}), (10, 2, {}), (0, 3, {}), (5, 5, dict(angled=1)), (4, 2, dict(tons=6000)),
                                   (8, 3, dict(tons=6000))):   # DD, KE, BB, angled CV, small CL, small AV
            self.assertEqual(allowed(kind, count, patched=False, **extra), (False, 1), (kind, count))
            self.assertEqual(allowed(kind, count, **extra), (True, 0), (kind, count))
        self.assertEqual(allowed(0, 1, researched=False), (False, 1))   # research still needed
        self.assertEqual(allowed(0, 0, researched=False), (True, 0))    # no catapults: nothing to check

    def test_patches_do_not_overlap_other_hull_or_vls_patches(self):
        plans, _ = hull_rules.class_patches(BLOB, BASE, ALLOCATION)
        spans = sorted((p["address"], p["address"]+len(bytes.fromhex(p["original"]))) for p in plans+self.vls)
        for (_, end), (start, _) in zip(spans, spans[1:]):
            self.assertLessEqual(end, start)


if __name__ == "__main__":
    unittest.main()

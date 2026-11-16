"""Retained-build discovery and x86 emulation; never attaches to a real game."""
import struct
import sys
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
import aircraft_improvements as mod
import modern_research as audit
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
                              UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP,
                              UC_X86_REG_EIP, UC_X86_REG_EFLAGS)

BASE, CODE, DATA, STACK, END = 0x301000, 0x10000000, 0x20000000, 0x30000000, 0x1000fff0
FORM, LV, ROW, SOURCE, CLONE, MENU, ROOTMENU, DIALOG, ROLE, NATION, MAIN = [DATA+x*0x1000 for x in range(1, 12)]
# MAIN needs the native campaign's 0x4aaa-byte layout, outside the other objects.
MAIN = DATA+0x10000
SLOT, DIALOG_SLOT, LIST_SLOT, ALL_TYPES = DATA+0xb000, DATA+0xb004, DATA+0xb008, DATA+0xc000


class Fixture:
    def __init__(self, blob, info):
        self.info = info; self.vm = Uc(UC_ARCH_X86, UC_MODE_32)
        self.vm.mem_map(BASE, 0x800000); self.vm.mem_write(BASE, blob)
        self.vm.mem_map(CODE, 0x10000); self.vm.mem_map(DATA, 0x20000); self.vm.mem_map(STACK, 0x10000)
        self.product = mod.build(CODE, info); self.state = self.product["state"]
        for block in self.product["code_blocks"]+self.product["literals"]:
            self.vm.mem_write(block["address"], bytes.fromhex(block["bytes"]))
        self.put(info["main_root"], SLOT); self.put(SLOT, MAIN); self.put(MAIN+0x3204, NATION)
        self.put(info["dialog_root"], DIALOG_SLOT); self.put(DIALOG_SLOT, DIALOG)
        self.put(info["aircraft_root"], LIST_SLOT); self.put(LIST_SLOT, ALL_TYPES)
        self.put(FORM+0x438, LV); self.put(FORM+0x44c, ROOTMENU); self.put(ROOTMENU+0x44, ROOTMENU)
        self.put(DIALOG+0x448, ROLE); self.put(ROLE, ROLE+0x300); self.put(ROLE+0x300+0x9c, CODE+0x7000)
        self.put(ROW+0x28, SOURCE); self.put(SOURCE, info["aircraft_vmt"])
        self.put(SOURCE+0x99, 123); self.put(SOURCE+0x14, 150); self.vm.mem_write(SOURCE+0x81, b"\x03")
        self.put(MENU, info["menu_vmt"])
        self.selected = ROW; self.accept = True; self.create = True
        self.calls = []; self.stops = set()
        self.stubs = {
            info["selected"]: lambda: self.ret(self.selected),
            info["menu_create"]: self.create_menu,
            info["menu_add"]: self.add_menu,
            info["menu_caption"]: self.caption,
            info["menu_enabled"]: self.enabled,
            info["request_click"]: self.request,
            info["request_execute"]: self.execute,
            info["variant"]: self.variant,
            info["priorities"]: self.priorities,
            info["development"]: self.development,
            info["refresh"]: lambda: (self.calls.append(("refresh",)), self.ret(clean=12)),
            info["explain"]: lambda: self.ret(),
            info["message"]: lambda: (self.calls.append(("error",)), self.ret()),
            CODE+0x7000: self.role_enabled,
        }
        self.vm.hook_add(UC_HOOK_CODE, self.step)

    def put(self, address, value): self.vm.mem_write(address, struct.pack("<I", value))
    def get(self, address): return struct.unpack("<I", self.vm.mem_read(address, 4))[0]
    def reg(self, register): return self.vm.reg_read(register)
    def ret(self, value=None, clean=0):
        if value is not None: self.vm.reg_write(UC_X86_REG_EAX, value)
        sp = self.reg(UC_X86_REG_ESP)
        self.vm.reg_write(UC_X86_REG_EIP, self.get(sp)); self.vm.reg_write(UC_X86_REG_ESP, sp+4+clean)
    def step(self, vm, address, size, unused):
        if address in self.stops: vm.emu_stop()
        elif address in self.stubs: self.stubs[address]()
    def run(self, name, eax=FORM, esi=0, edi=0, stops=()):
        for reg, value in [(UC_X86_REG_EAX, eax), (UC_X86_REG_EBX, 0x11111111), (UC_X86_REG_ECX, 0x22222222),
                           (UC_X86_REG_EDX, 0x33333333), (UC_X86_REG_ESI, esi), (UC_X86_REG_EDI, edi),
                           (UC_X86_REG_EBP, STACK+0x9000), (UC_X86_REG_ESP, STACK+0x8000), (UC_X86_REG_EFLAGS, 0x246)]:
            self.vm.reg_write(reg, value)
        self.put(STACK+0x8000, END); self.stops = set(stops)
        self.vm.emu_start(self.product["locations"][name], END, count=20000)
        if self.reg(UC_X86_REG_EIP) not in self.stops|{END}: raise AssertionError("Emulation did not complete")
        return self.reg(UC_X86_REG_EAX)
    def create_menu(self):
        self.calls.append(("create", self.reg(UC_X86_REG_EAX), self.reg(UC_X86_REG_ECX))); self.ret(MENU)
    def add_menu(self):
        self.calls.append(("add", self.reg(UC_X86_REG_EAX), self.reg(UC_X86_REG_EDX))); self.ret()
    def caption(self):
        pointer = self.reg(UC_X86_REG_EDX); n = self.get(pointer-4)
        self.calls.append(("caption", bytes(self.vm.mem_read(pointer, n*2)).decode("utf-16-le"))); self.ret()
    def enabled(self):
        self.calls.append(("enabled", self.reg(UC_X86_REG_EDX)&255)); self.ret()
    def role_enabled(self):
        self.calls.append(("role_enabled", self.reg(UC_X86_REG_EDX)&255)); self.ret()
    def request(self):
        self.calls.append(("request", self.reg(UC_X86_REG_EAX)))
        self.put(MAIN+0x4aa9, 5 if self.accept else 0); self.ret()
    def execute(self):
        self.calls.append(("execute", self.reg(UC_X86_REG_EAX), self.reg(UC_X86_REG_EDX))); self.ret()
    def variant(self):
        self.calls.append(("variant", self.reg(UC_X86_REG_EAX)))
        self.put(SOURCE+0x8c, 99)
        if self.create: self.put(self.state+mod.CLONE, CLONE)
        self.ret()
    def priorities(self):
        self.calls.append(("priorities", self.reg(UC_X86_REG_EAX), self.reg(UC_X86_REG_EDX), self.reg(UC_X86_REG_ECX)))
        self.ret()
    def development(self):
        self.calls.append(("development", self.reg(UC_X86_REG_EAX), self.reg(UC_X86_REG_EDX), self.reg(UC_X86_REG_ECX)))
        self.ret(7)


class AircraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.info = mod.discover(cls.blob, BASE)

    def fixture(self): return Fixture(self.blob, self.info)

    def test_exact_build_and_all_patch_boundaries(self):
        built = mod.build(CODE, self.info)
        self.assertEqual(len(built["patches"]), 5)
        self.assertEqual(len(built["code_blocks"]), 8)
        for plan in built["patches"]:
            before, after = bytes.fromhex(plan["original"]), bytes.fromhex(plan["replacement"])
            self.assertEqual(len(before), len(after)); self.assertEqual(after[0], 0xe9)
            off = plan["address"]-BASE
            self.assertEqual(self.blob[off:off+len(before)], before)

    def test_all_reviewed_ranges_reject_mutation(self):
        for name, (address, size, digest) in mod.AUDITED.items():
            damaged = bytearray(self.blob); damaged[address-BASE] ^= 1
            with self.assertRaisesRegex(ValueError, name): mod.discover(bytes(damaged), BASE)

    def test_windows_address_randomization(self):
        shifted = bytearray(self.blob); delta = 0x500000
        for offset in audit.text_relocations():
            struct.pack_into("<I", shifted, offset, (struct.unpack_from("<I", shifted, offset)[0]+delta)&0xffffffff)
        moved = mod.discover(bytes(shifted), BASE+delta)
        self.assertEqual(moved["menu_create"], self.info["menu_create"]+delta)
        self.assertEqual(moved["sites"][4]["address"], self.info["sites"][4]["address"]+delta)

    def test_eligibility_rejects_foreign_developing_obsolete_and_superseded(self):
        f = self.fixture()
        self.assertEqual(f.run("eligible"), SOURCE)
        for field, value in [(0x88, 1), (0x84, 4), (0x8c, 99), (0x8c, 5), (0x90, 1)]:
            f.put(SOURCE+field, value)
            self.assertEqual(f.run("eligible"), 0, (field, value))
            f.put(SOURCE+field, 0)
        f.put(MAIN+0x4aa9, 5); self.assertEqual(f.run("eligible"), 0)
        f.put(MAIN+0x4aa9, 0); f.selected = 0; self.assertEqual(f.run("eligible"), 0)
        f.selected = ROW; f.put(SLOT, 0); self.assertEqual(f.run("eligible"), 0)

    def test_native_menu_owned_by_form_created_once_with_real_click_event(self):
        f = self.fixture(); f.run("ensure"); f.run("ensure")
        self.assertEqual([call for call in f.calls if call[0] == "create"], [("create", self.info["menu_vmt"], FORM)])
        self.assertIn(("add", ROOTMENU, MENU), f.calls)
        self.assertIn(("caption", "Improve aircraft model..."), f.calls)
        self.assertEqual(f.get(MENU+0x98), f.product["locations"]["click"])
        self.assertEqual(f.get(MENU+0x9c), FORM)

    def test_popup_uses_the_same_eligibility_gate(self):
        f = self.fixture(); f.put(f.state+mod.MENU, MENU)
        stop = self.info["sites"][1]["address"]+9
        f.run("popup", stops=[stop]); self.assertIn(("enabled", 1), f.calls)
        f.calls.clear(); f.put(SOURCE+0x88, 1)
        f.run("popup", stops=[stop]); self.assertIn(("enabled", 0), f.calls)

    def test_request_role_locked_only_during_improvement(self):
        f = self.fixture(); stop = self.info["sites"][2]["address"]+8
        f.run("dispatch", eax=DIALOG, stops=[stop])
        self.assertEqual(f.calls, [("execute", DIALOG, 0xffffffff)])
        f.calls.clear(); f.put(f.state+mod.MODE, 1); f.put(f.state+mod.SOURCE, SOURCE)
        f.run("dispatch", eax=DIALOG, stops=[stop])
        self.assertEqual(f.calls, [("role_enabled", 0), ("execute", DIALOG, 3), ("role_enabled", 1)])

    def test_cancel_does_not_create_successor_or_queue_request(self):
        f = self.fixture(); f.accept = False
        before = bytes(f.vm.mem_read(SOURCE, 0xac)); f.run("click")
        self.assertEqual(before, bytes(f.vm.mem_read(SOURCE, 0xac)))
        self.assertFalse(any(call[0] == "variant" for call in f.calls))
        self.assertEqual(f.get(MAIN+0x4aa9), 0); self.assertEqual(f.get(f.state+mod.MODE), 0)

    def test_confirm_calls_native_variant_and_clears_unrelated_new_request(self):
        f = self.fixture(); f.run("click")
        self.assertIn(("request", FORM), f.calls); self.assertIn(("variant", SOURCE), f.calls)
        self.assertEqual(f.get(MAIN+0x4aa9), 0)
        self.assertEqual(f.get(SOURCE+0x8c), 99)
        self.assertEqual(f.get(f.state+mod.CLONE), CLONE)
        self.assertEqual(f.get(f.state+mod.MODE), 0)
        self.assertEqual(f.reg(UC_X86_REG_EBX), 0x11111111)
        self.assertEqual(f.reg(UC_X86_REG_ESP), STACK+0x8004)

    def test_constructor_failure_restores_version_and_cancels_request(self):
        f = self.fixture(); f.create = False; f.put(SOURCE+0x8c, 2); f.run("click")
        self.assertEqual(f.get(SOURCE+0x8c), 2); self.assertEqual(f.get(MAIN+0x4aa9), 0)
        self.assertIn(("error",), f.calls); self.assertEqual(f.get(f.state+mod.MODE), 0)

    def test_foreign_force_click_and_reentrant_click_do_nothing(self):
        for foreign, mode in [(1, 0), (0, 1), (0, 2)]:
            f = self.fixture(); f.put(SOURCE+0x88, foreign); f.put(f.state+mod.MODE, mode)
            f.run("click"); self.assertFalse(any(call[0] in ("request", "variant") for call in f.calls))

    def test_prototype_gets_both_priorities_native_time_and_saved_list(self):
        f = self.fixture(); f.put(f.state+mod.MODE, 2); f.put(f.state+mod.SOURCE, SOURCE); f.put(f.state+mod.DELAY, 5)
        f.put(DATA+0xd000, CLONE)
        stop = self.info["sites"][3]["address"]+7
        f.run("prototype", esi=SOURCE, edi=DATA+0xd000, stops=[stop])
        self.assertIn(("priorities", CLONE, 0, 1), f.calls)
        self.assertIn(("development", MAIN, NATION, 3), f.calls)
        self.assertEqual(f.get(CLONE+0x84), 12)
        self.assertEqual(f.reg(UC_X86_REG_EAX), ALL_TYPES)
        self.assertEqual(f.reg(UC_X86_REG_EDX), CLONE)
        self.assertEqual(f.get(SOURCE+0x14), 150)

    def test_normal_automatic_variant_insertion_keeps_scratch_list(self):
        f = self.fixture(); original = bytes.fromhex(self.info["sites"][3]["original"])
        scratch_slot = struct.unpack_from("<I", original, 3)[0]; f.put(scratch_slot, DATA+0xe000)
        f.put(DATA+0xd000, CLONE); stop = self.info["sites"][3]["address"]+7
        f.run("prototype", esi=SOURCE, edi=DATA+0xd000, stops=[stop])
        self.assertEqual(f.reg(UC_X86_REG_EAX), DATA+0xe000); self.assertEqual(f.calls, [])
        self.assertEqual(f.get(CLONE+0x84), 0)

    def test_quiet_feedback_only_scopes_explicit_variant_and_preserves_source_obsolete_flag(self):
        f = self.fixture(); f.put(DATA+0xd000, CLONE)
        return_site = self.info["variant_quiet_return"]
        normal = self.info["sites"][4]["address"]+13
        f.run("feedback", esi=SOURCE, edi=DATA+0xd000, stops=[return_site, normal])
        self.assertEqual(f.reg(UC_X86_REG_EIP), normal)
        f.put(f.state+mod.MODE, 2); f.put(f.state+mod.SOURCE, SOURCE)
        f.run("feedback", esi=SOURCE, edi=DATA+0xd000, stops=[return_site, normal])
        self.assertEqual(f.reg(UC_X86_REG_EIP), return_site)
        self.assertEqual(f.get(f.state+mod.CLONE), CLONE)
        self.assertEqual(bytes(f.vm.mem_read(SOURCE+0x90, 1)), b"\0")

    def test_actual_native_copy_does_not_duplicate_aircraft_stockpiles(self):
        f = self.fixture()
        f.put(SOURCE+0x9d, 200); f.put(SOURCE+0xa1, 7)
        # Execute the retained engine copy method, stubbing only its Unicode
        # reference assignment helper. It must copy the design, not inventories.
        def assign_string():
            f.put(f.reg(UC_X86_REG_EAX), f.reg(UC_X86_REG_EDX)); f.ret()
        f.stubs[0x30bccc] = assign_string
        for register, value in [(UC_X86_REG_EAX, SOURCE), (UC_X86_REG_EDX, CLONE),
                                (UC_X86_REG_ESP, STACK+0x8000)]: f.vm.reg_write(register, value)
        f.put(STACK+0x8000, END)
        f.vm.emu_start(self.info["copy"], END, count=2000)
        self.assertEqual(f.get(CLONE+0x14), 150)
        self.assertEqual(f.get(CLONE+0x9d), 0); self.assertEqual(f.get(CLONE+0xa1), 0)
        self.assertEqual(f.get(SOURCE+0x9d), 200); self.assertEqual(f.get(SOURCE+0xa1), 7)


if __name__ == "__main__": unittest.main()

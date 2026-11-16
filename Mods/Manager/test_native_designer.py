import struct
import sys
from pathlib import Path
import unittest
sys.path[:0]=[str(Path(__file__).parent/"vendor"),str(Path(__file__).parent.parent/"CampaignOverhaul")]
import native_designer as native
import submarine_factory as factory
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *


class NativeDesignerTests(unittest.TestCase):
    def run_gate(self,active=1,matching=True,signal=0,stack=0,call=False):
        vm=Uc(UC_ARCH_X86,UC_MODE_32)
        for at in (0x100000,0x200000,0x300000):vm.mem_map(at,0x10000)
        state=0x200000;vm.mem_write(state,struct.pack("<III",active,0x200100,0))
        original=b"\xe8"+struct.pack("<i",0x108000-0x101005) if call else b"\xb8\x42\x00\x00\x00"
        vm.mem_write(0x100000,native.gate(0x100000,state,original,0x101005,signal,stack))
        vm.mem_write(0x101005,b"\xc2"+struct.pack("<H",stack))
        vm.mem_write(0x108000,b"\xb8\x42\x00\x00\x00\xc3")
        vm.mem_write(0x30f000,struct.pack("<II",0x10f000,0x1234));vm.reg_write(UC_X86_REG_ESP,0x30f000)
        vm.reg_write(UC_X86_REG_EAX,0x200100 if matching else 0x200200);vm.reg_write(UC_X86_REG_EFLAGS,0x246)
        vm.reg_write(UC_X86_REG_ECX,0x11223344);vm.reg_write(UC_X86_REG_EDX,0x55667788)
        vm.emu_start(0x100000,0x10f000,count=1000)
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP),0x30f004+stack)
        self.assertEqual(vm.reg_read(UC_X86_REG_EFLAGS),0x246)
        self.assertEqual(vm.reg_read(UC_X86_REG_ECX),0x11223344);self.assertEqual(vm.reg_read(UC_X86_REG_EDX),0x55667788)
        return vm.reg_read(UC_X86_REG_EAX),struct.unpack("<I",vm.mem_read(state+8,4))[0]

    def test_original_surface_handlers_unmodified_when_inactive(self):self.assertEqual(self.run_gate(active=0),(0x42,0))
    def test_other_form_instance_not_intercepted(self):self.assertEqual(self.run_gate(matching=False),(0x42,0))
    def test_active_submarine_mode_does_not_enter_surface_type_or_save_code(self):self.assertEqual(self.run_gate(),(0x200100,0))
    def test_finish_and_save_signals_preserve_registers(self):
        for signal in (1,2):self.assertEqual(self.run_gate(signal=signal),(0x200100,signal))
    def test_native_key_events_pop_shift_stack_argument(self):
        for active in (0,1):self.run_gate(active=active,stack=4)
    def test_relocated_surface_save_call_keeps_original_target(self):self.assertEqual(self.run_gate(active=0,call=True),(0x42,0))
    def test_submarine_save_never_calls_surface_save_target(self):self.assertEqual(self.run_gate(call=True,signal=1),(0x200100,1))

    def test_f11_dispatch_uses_native_design_command_once(self):
        vm=Uc(UC_ARCH_X86,UC_MODE_32)
        for at in (0x100000,0x200000,0x300000):vm.mem_map(at,0x10000)
        queue=0x200000;root=0x200100;main=0x200200;player=0x200400;active=0x200500
        vm.mem_write(root,struct.pack("<I",main));vm.mem_write(main+0x100,struct.pack("<I",player));vm.mem_write(queue+0x40,struct.pack("<III",1,main,player))
        layout={"main_slot":root,"player_field":0x100,"design_click":0x108000,"build_click":0x109000}
        vm.mem_write(0x100000,factory.request_thunk(0x100000,queue,active,layout))
        # The modal form pumps idle once. Re-entry must not reopen it.
        vm.mem_write(0x108000,b"\xe8"+struct.pack("<i",0x100000-0x108005)+b"\xc3")
        calls=[]
        def hook(m,at,size,data):
            if at in (0x108000,0x109000):calls.append(at)
        vm.hook_add(UC_HOOK_CODE,hook);vm.mem_write(0x30f000,struct.pack("<I",0x10f000));vm.reg_write(UC_X86_REG_ESP,0x30f000)
        vm.emu_start(0x100000,0x10f000,count=1000)
        self.assertEqual(calls,[0x108000]);self.assertEqual(struct.unpack("<I",vm.mem_read(queue+0x40,4))[0],2)


if __name__=="__main__":unittest.main(verbosity=2)

"""Isolated national research effort tests; never changes a real campaign."""
from pathlib import Path
import struct
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/"vendor"),str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import *
import research_traits as traits
import modern_research as audit

CODE,DATA,STACK,STATE=0x1200000,0x1300000,0x1500000,0x1310000


class ResearchTraitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob=(HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.info=traits.discover(cls.blob,0x301000)

    def run_effort(self,effort=100,advantage=0,technical=0,area=0,settings=None,nation=DATA):
        vm=Uc(UC_ARCH_X86,UC_MODE_32)
        for a,n in ((0x300000,0x800000),(CODE,0x10000),(DATA,0x20000),(STACK,0x10000)):vm.mem_map(a,n)
        info=self.info if settings is None else traits.discover(self.blob,0x301000,settings)
        vm.mem_write(CODE,traits.effort_thunk(CODE,STATE,info))
        frame=STACK+0x8000;allocation=DATA+0xf000
        vm.mem_write(frame-0x54,struct.pack("<I",allocation));vm.mem_write(allocation,struct.pack("<i",effort))
        vm.mem_write(nation+info["technical_excellence"],bytes([technical]))
        if 0<=area<=24:vm.mem_write(nation+info["advantage_base"]+area*53,bytes([advantage]))
        # An adjacent branch advantage must not affect this branch.
        vm.mem_write(nation+info["advantage_base"]+((area+1)%25)*53,b"\x01")
        before=bytes(vm.mem_read(DATA,0x10000))
        registers={UC_X86_REG_EAX:0x1234,UC_X86_REG_EBX:nation,UC_X86_REG_ECX:0x2345,
                   UC_X86_REG_EDX:0x3456,UC_X86_REG_ESI:area&0xffffffff,UC_X86_REG_EDI:0x4567,
                   UC_X86_REG_ESP:STACK+0x7000,UC_X86_REG_EBP:frame,UC_X86_REG_EFLAGS:0x246}
        for reg,value in registers.items():vm.reg_write(reg,value)
        vm.emu_start(CODE,info["site"]+8,count=10000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP),info["site"]+8)
        self.assertEqual(bytes(vm.mem_read(DATA,0x10000)),before,"Nation or raw allocation was edited.")
        for reg,value in registers.items():self.assertEqual(vm.reg_read(reg),effort&0xffffffff if reg==UC_X86_REG_EAX else value)
        result=int.from_bytes(vm.mem_read(frame-0x28,4),"little",signed=True)
        return result,vm

    def test_flags_change_only_their_own_effort_and_add_not_compound(self):
        for area in (0,7,21,22,23,24):
            for nation in (DATA,DATA+0x5000):
                for advantage,technical,expected in ((0,0,100),(1,0,150),(0,1,125),(1,1,175)):
                    result,_=self.run_effort(100,advantage,technical,area,nation=nation)
                    self.assertEqual(result,expected)

    def test_integer_rounding_zero_negative_and_invalid_areas(self):
        for effort in (0,-1,-100):self.assertEqual(self.run_effort(effort,1,1)[0],effort)
        self.assertEqual(self.run_effort(1,0,1)[0],1)
        self.assertEqual(self.run_effort(4,0,1)[0],5)
        for area in (-1,25,1000):self.assertEqual(self.run_effort(100,1,1,area)[0],100)

    def test_zero_settings_are_identity_and_large_inputs_saturate_safely(self):
        self.assertEqual(self.run_effort(100,1,1,settings=dict(research_advantage_bonus_percent=0,technical_excellence_bonus_percent=0))[0],100)
        for effort in (1000000,1000000000,0x7ffffffe,0x7fffffff):
            expected=min(0x7fffffff,effort*600//100)
            self.assertEqual(self.run_effort(effort,1,1,settings=dict(research_advantage_bonus_percent=300,technical_excellence_bonus_percent=200))[0],expected)

    def test_original_native_progress_cap_still_executes_after_the_boost(self):
        # The existing native clamp is not replaced: boosted effort 175 for a
        # cost-500 invention is still reduced to 100 by this native stage.
        result,vm=self.run_effort(100,1,1)
        self.assertEqual(result,175)
        start,end=0x762df1,0x762e1f;vm.mem_write(start,self.blob[start-0x301000:end-0x301000])
        vm.mem_write(STACK+0x8000-0x2c,struct.pack("<i",500))
        vm.emu_start(start,end,count=1000)
        self.assertEqual(int.from_bytes(vm.mem_read(STACK+0x8000-0x28,4),"little"),100)
        # The other native random, era, priority and completion code is not
        # patched or called early by the trait thunk.
        self.assertTrue(self.info["native_era_and_prerequisite_checks_preserved"])

    def test_discovery_relocates_and_refuses_mutated_fields_or_unknown_settings(self):
        delta=0x510000;moved=bytearray(self.blob)
        for off in audit.text_relocations():struct.pack_into("<I",moved,off,(struct.unpack_from("<I",moved,off)[0]+delta)&0xffffffff)
        found=traits.discover(bytes(moved),0x301000+delta)
        self.assertEqual(found["site"],self.info["site"]+delta)
        for reference in (0x762a8c,0x720a75,0x724f2a,0x762df1):
            changed=bytearray(self.blob);changed[reference-0x301000]^=1
            with self.assertRaises(ValueError):traits.discover(bytes(changed),0x301000)
        for settings in ({"research_advantage_bonus_percent":301},{"technical_excellence_bonus_percent":True},{"unknown":1}):
            with self.assertRaises(ValueError):traits.discover(self.blob,0x301000,settings)


if __name__=="__main__":unittest.main(verbosity=2)

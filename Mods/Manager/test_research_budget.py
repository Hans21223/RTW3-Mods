"""Isolated research budget scaling tests; never changes a real campaign."""
from pathlib import Path
import struct
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/"vendor"),str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import *
import research_budget as budget
import modern_research as audit

CODE,STACK,STATE=0x1200000,0x1500000,0x1201000
FRAME=STACK+0x8000
REGS={UC_X86_REG_EAX:0x1234,UC_X86_REG_EBX:0x2000000,UC_X86_REG_ECX:0x2345,UC_X86_REG_EDX:0x3456,
      UC_X86_REG_ESI:7,UC_X86_REG_EDI:0x4567,UC_X86_REG_ESP:STACK+0x7000,UC_X86_REG_EBP:FRAME,UC_X86_REG_EFLAGS:0x246}


class ResearchBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob=(HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.info=budget.discover(cls.blob,0x301000)

    def vm(self):
        vm=Uc(UC_ARCH_X86,UC_MODE_32)
        for a,n in ((0x300000,0x800000),(CODE,0x10000),(STACK,0x10000),(0x2000000,0x10000)):vm.mem_map(a,n)
        vm.mem_write(0x301000,self.blob)
        for reg,value in REGS.items():vm.reg_write(reg,value)
        return vm

    def local(self,vm,offset,value=None):
        if value is not None:vm.mem_write(FRAME+offset,struct.pack("<i",value))
        return int.from_bytes(vm.mem_read(FRAME+offset,4),"little",signed=True)

    def run_cap(self,cost,effort,settings=None,native=False):
        vm=self.vm()
        info=self.info if settings is None else budget.discover(self.blob,0x301000,settings)
        self.local(vm,-0x2c,cost);self.local(vm,-0x28,effort)
        start=0x762df1
        if not native:vm.mem_write(CODE+0x400,budget.cap_thunk(CODE+0x400,STATE,info));start=CODE+0x400
        vm.emu_start(start,0x762e1f,count=10000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP),0x762e1f)
        if not native:
            for reg,value in REGS.items():self.assertEqual(vm.reg_read(reg),value)
            self.assertEqual(self.local(vm,-0x2c),cost)
        return self.local(vm,-0x28)

    def test_native_clamp_unchanged_at_or_below_the_old_limit(self):
        for cost in (1,4,5,7,120000,880000):
            for effort in (-5,0,1,cost//5-1,cost//5):
                self.assertEqual(self.run_cap(cost,effort),self.run_cap(cost,effort,native=True))

    def test_effort_above_the_limit_counts_at_half_rate_up_to_sixty_percent(self):
        for cost in (120000,240000,800000):
            cap=cost//5
            for effort in (cap+1,cap+2,2*cap,3*cap,5*cap,50*cap,0x7fffffff):
                expected=cap+min((effort-cap)*50//100,cost*60//100-cap)
                self.assertEqual(self.run_cap(cost,effort),expected)
            self.assertGreater(self.run_cap(cost,3*cap),self.run_cap(cost,2*cap))

    def test_identity_settings_reproduce_the_native_clamp(self):
        for settings in ({"overflow_percent":0},{"max_turn_progress_percent":20}):
            for cost in (3,5,120000,880000):
                for effort in (cost//5+1,cost,10*cost,0x7fffffff):
                    self.assertEqual(self.run_cap(cost,effort,settings),self.run_cap(cost,effort,native=True))

    def run_total(self,points,speed,native=False):
        vm=self.vm();self.local(vm,-0x24,points);vm.mem_write(0xa1c918,struct.pack("<i",speed))
        start=0x7627dc
        if not native:vm.mem_write(CODE,budget.total_thunk(CODE,STATE,self.info));start=CODE
        vm.emu_start(start,0x762803,count=10000)
        if not native:
            for reg,value in REGS.items():self.assertEqual(vm.reg_read(reg),value)
            self.assertEqual((vm.reg_read(UC_X86_REG_FPSW)>>11)&7,0,"FPU stack not balanced.")
        return self.local(vm,-0x24),int.from_bytes(vm.mem_read(STATE+4,4),"little")

    def test_total_matches_native_until_it_would_overflow(self):
        for points,speed in ((121,100),(1801,100),(1801,1000),(142857,100),(14285,1000),(7,1)):
            self.assertEqual(self.run_total(points,speed),(self.run_total(points,speed,native=True)[0],0))

    def test_huge_budgets_saturate_instead_of_wrapping(self):
        # Native wraps around 2^31 points*140*speed; e.g. 200000 at speed 100 turns negative.
        self.assertLess(self.run_total(200000,100,native=True)[0],0)
        for points,speed in ((200000,100),(10000000,1000),(0x7fffffff,1000)):
            self.assertEqual(self.run_total(points,speed),(budget.TOTAL_LIMIT,1))

    def run_static(self,label,start,end,native=False):
        vm=self.vm();progress=0x2000000+7*0x35+0x332
        vm.mem_write(progress,struct.pack("<i",100001));self.local(vm,-0x28,5000)
        if not native:
            item=next(p for p in self.info["static_patches"] if p["label"]==label)
            vm.mem_write(item["address"],bytes.fromhex(item["replacement"]))
        vm.emu_start(start,end,count=1000)
        return int.from_bytes(vm.mem_read(progress,4),"little"),self.local(vm,-0x28)

    def test_setbacks_no_longer_halve_accumulated_progress(self):
        labels=[p["label"] for p in self.info["static_patches"]]
        for label,(start,end),effort in zip(labels,((0x76310b,0x763127),(0x76333e,0x76335a),(0x7637a9,0x7637c5)),(5000,5000,0)):
            self.assertEqual(self.run_static(label,start,end,native=True),(50001,5000))
            self.assertEqual(self.run_static(label,start,end),(100001,effort))

    def test_discovery_relocates_and_refuses_changed_code_or_settings(self):
        delta=0x510000;moved=bytearray(self.blob)
        for off in audit.text_relocations():struct.pack_into("<I",moved,off,(struct.unpack_from("<I",moved,off)[0]+delta)&0xffffffff)
        found=budget.discover(bytes(moved),0x301000+delta)
        self.assertEqual((found["cap_site"],found["speed"]),(self.info["cap_site"]+delta,self.info["speed"]+delta))
        for address,size,_ in budget.WINDOWS:
            changed=bytearray(self.blob);changed[address-0x301000+size-1]^=1
            with self.assertRaises(ValueError):budget.discover(bytes(changed),0x301000)
        for settings in ({"overflow_percent":101},{"max_turn_progress_percent":19},{"overflow_percent":True},{"unknown":1}):
            with self.assertRaises(ValueError):budget.discover(self.blob,0x301000,settings)


if __name__=="__main__":unittest.main(verbosity=2)

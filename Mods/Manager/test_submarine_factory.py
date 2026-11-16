import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).parent/"vendor"))
sys.path.insert(0,str(Path(__file__).parent.parent/"CampaignOverhaul"))
import submarine_factory as factory
import in_game_submarines as hosting
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *


class FactoryTests(unittest.TestCase):
    def fixture(self):
        vm=Uc(UC_ARCH_X86,UC_MODE_32)
        for addr in (0x100000,0x200000,0x210000,0x220000,0x230000,0x240000,0x300000):vm.mem_map(addr,0x10000)
        self.layout={"main_slot":0x200000,"year_slot":0x200004,"player_field":0x100,"append":0x108000,"build_click":0x109000,"return_original":"8bc35f5e5b5dc20400"}
        self.active=0x200100;self.packet=0x200200;self.queue=0x200300
        def put(at,*values):vm.mem_write(at,struct.pack("<"+"I"*len(values),*[v&0xffffffff for v in values]))
        self.put=put;self.get=lambda at:struct.unpack("<I",vm.mem_read(at,4))[0]
        put(0x200000,0x210000,0x200008,2000);put(0x210100,0x220000)
        put(self.active,self.packet,0,0);put(self.packet,0x210000,0x220000,3,1960,125,-1,0x240000)
        put(0x230008,70,0);vm.mem_write(0x230010,b"\x03")
        vm.mem_write(self.layout["append"],b"\xc3")
        return vm

    def run_factory(self,mutate=None):
        vm=self.fixture()
        if mutate:mutate(vm)
        code=factory.factory_thunk(0x100000,self.active,self.layout);vm.mem_write(0x100000,code)
        self.put(0x30f000,0xd1,0xd2,0xd3,0xd4,0x10f000,0x240000)
        vm.reg_write(UC_X86_REG_ESP,0x30f000);vm.reg_write(UC_X86_REG_EBX,0x230000);vm.reg_write(UC_X86_REG_ESI,0x220000)
        vm.reg_write(UC_X86_REG_ECX,0x12345678);vm.reg_write(UC_X86_REG_EDX,0x23456789);vm.reg_write(UC_X86_REG_EFLAGS,0x246)
        appends=[]
        def hook(machine,at,size,user):
            if at==self.layout["append"]:appends.append((machine.reg_read(UC_X86_REG_EAX),machine.reg_read(UC_X86_REG_EDX)))
        vm.hook_add(UC_HOOK_CODE,hook);vm.emu_start(0x100000,0x10f000,count=1000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EAX),0x230000)
        for reg,value in ((UC_X86_REG_EDI,0xd1),(UC_X86_REG_ESI,0xd2),(UC_X86_REG_EBX,0xd3),(UC_X86_REG_EBP,0xd4),(UC_X86_REG_ECX,0x12345678),(UC_X86_REG_EDX,0x23456789),(UC_X86_REG_ESP,0x30f018),(UC_X86_REG_EFLAGS,0x246)):
            self.assertEqual(vm.reg_read(reg),value)
        return vm,appends

    def test_matching_player_class_and_native_epilogue(self):
        vm,appends=self.run_factory();self.assertEqual(self.get(0x230008),125);self.assertEqual(self.get(0x23000c),0xffffffff)
        self.assertEqual(appends,[(0x230004,0x240000)]);self.assertEqual(self.get(self.active+4),1);self.assertEqual(self.get(self.active+8),0x230000)

    def test_inactive_other_nation_role_future_and_changed_campaign_refused(self):
        for at,value in ((0x200100,0),(0x210100,0x221000),(0x200200,0x211000),(0x200204,0x221000),(0x200208,4),(0x20020c,2001)):
            with self.subTest(address=at):
                vm,appends=self.run_factory(lambda v:self.put(at,value));self.assertEqual(self.get(0x230008),70);self.assertEqual(self.get(self.active+4),0);self.assertEqual(appends,[])

    def test_profile_range_guards(self):
        for at,value in ((0x200210,39),(0x200210,131),(0x200214,-3),(0x200214,2)):
            with self.subTest(value=value):
                vm,_=self.run_factory(lambda v:self.put(at,value));self.assertEqual(self.get(0x230008),70);self.assertEqual(self.get(self.active+4),0)

    def test_no_synthetic_build_cost_tonnage_or_timer_writes(self):
        vm,_=self.run_factory(lambda v:self.put(0x230014,0x11223344,0x55667788,0x12345678,0x87654321))
        self.assertEqual(bytes(vm.mem_read(0x230014,16)),struct.pack("<4I",0x11223344,0x55667788,0x12345678,0x87654321))

    def run_request(self,stale=False):
        vm=self.fixture();self.put(self.active,0,7,0);self.put(self.queue,1,self.packet,0,0)
        if stale:self.put(self.packet,0x211000)
        vm.mem_write(0x100000,factory.request_thunk(0x100000,self.queue,self.active,self.layout))
        # Native modal handler pumps idle once. Nested request must not call it
        # again while state=3; native count changes only during this dialog.
        stub=b"\xe8"+struct.pack("<i",0x100000-0x109000-5)+b"\xff\x05"+struct.pack("<I",self.active+4)+b"\xc3"
        vm.mem_write(0x109000,stub);self.put(0x30f000,0x10f000);vm.reg_write(UC_X86_REG_ESP,0x30f000)
        calls=[]
        def hook(machine,at,size,user):
            if at==0x109000:
                calls.append(at);self.assertEqual(self.get(self.queue),3);self.assertEqual(self.get(self.active),self.packet)
                self.assertEqual(machine.reg_read(UC_X86_REG_EAX),0x210000);self.assertEqual(machine.reg_read(UC_X86_REG_EDX),0)
        vm.hook_add(UC_HOOK_CODE,hook);vm.emu_start(0x100000,0x10f000,count=1000);return calls

    def test_native_dialog_dispatch_and_reentry_guard(self):
        calls=self.run_request();self.assertEqual(calls,[0x109000]);self.assertEqual(self.get(self.queue),2)
        self.assertEqual(self.get(self.active),0);self.assertEqual(self.get(self.queue+8),7);self.assertEqual(self.get(self.queue+12),8)

    def test_stale_campaign_never_opens_dialog(self):
        self.assertEqual(self.run_request(True),[]);self.assertEqual(self.get(self.queue),4);self.assertEqual(self.get(self.active),0)


class HostingTests(unittest.TestCase):
    def run_host(self,fail_phase=0):
        vm=Uc(UC_ARCH_X86,UC_MODE_32);vm.mem_map(0x100000,0x10000);vm.mem_map(0x200000,0x10000);vm.mem_map(0x300000,0x10000)
        keys=("status","meta","info","host","result","iid_meta","clsid_meta","version","iid_info","clsid_host","iid_host","assembly","type","method","argument")
        data={key:0x200000+i*0x100 for i,key in enumerate(keys)}
        functions=[0x108000+n*0x100 for n in range(5)];objects=[0x20a000+n*0x100 for n in range(3)]
        def put(at,*values):vm.mem_write(at,struct.pack("<"+"I"*len(values),*values))
        for obj in objects:put(obj,obj+0x10)
        put(objects[0]+0x10+12,functions[1]);put(objects[1]+0x10+36,functions[2]);put(objects[2]+0x10+12,functions[3]);put(objects[2]+0x10+44,functions[4])
        for i,fn in enumerate(functions):vm.mem_write(fn,b"\xc2"+struct.pack("<H",[12,16,16,4,28][i]))
        calls=[]
        def hook(machine,at,size,user):
            if at not in functions:return
            i=functions.index(at);calls.append(i+1);esp=machine.reg_read(UC_X86_REG_ESP)
            argc=[3,4,4,1,6][i];args=struct.unpack("<"+"I"*argc,machine.mem_read(esp+4,argc*4))
            expected=[(data["clsid_meta"],data["iid_meta"],data["meta"]),(objects[0],data["version"],data["iid_info"],data["info"]),(objects[1],data["clsid_host"],data["iid_host"],data["host"]),(objects[2],),(objects[2],data["assembly"],data["type"],data["method"],data["argument"],data["result"])]
            self.assertEqual(args,expected[i])
            if i in (0,1,2):put(args[-1],objects[i])
            if i==4:put(data["result"],0)
            machine.reg_write(UC_X86_REG_EAX,0x80004005 if fail_phase==i+1 else 0)
        # Correct stdcall byte counts, including the COM this pointer.
        vm.mem_write(functions[4],b"\xc2\x18\x00")
        vm.hook_add(UC_HOOK_CODE,hook);code=hosting.bootstrap(0x100000,data,functions[0]);vm.mem_write(0x100000,code)
        put(0x30f000,0x10f000,0);vm.reg_write(UC_X86_REG_ESP,0x30f000)
        for reg in (UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP):vm.reg_write(reg,0x12345678)
        vm.emu_start(0x100000,0x10f000,count=1000)
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP),0x30f008)
        for reg in (UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP):self.assertEqual(vm.reg_read(reg),0x12345678)
        return calls,vm.reg_read(UC_X86_REG_EAX),struct.unpack("<I",vm.mem_read(data["status"],4))[0]

    def test_clr_com_contract_and_stack(self):self.assertEqual(self.run_host(),([1,2,3,4,5],0,6))
    def test_each_failed_hresult_stops_hosting(self):
        for n in range(1,6):
            with self.subTest(phase=n):self.assertEqual(self.run_host(n),(list(range(1,n+1)),0x80004005,n))


if __name__=="__main__":unittest.main(verbosity=2)

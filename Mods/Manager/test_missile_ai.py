"""Shared missile test world plus audits of the native helpers missile_range reuses."""
from pathlib import Path
import struct
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/"vendor"),str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.x86_const import *
import battle_ai
import missile_ai
import missile_range
import modern_research as audit

BASE=0x301000
CODE,DATA,STACK=0x1200000,0x1300000,0x1500000
FORM,DIV,SHIP=DATA+0x5000,DATA+0x3000,DATA+0x1000
STOP,STATE=CODE+0xF800,CODE+0xF000


class World:
    def __init__(self,blob,settings=None):
        self.info=battle_ai.discover(blob,BASE,settings)
        self.info.update(self.info["missile"])
        self.vm=Uc(UC_ARCH_X86,UC_MODE_32)
        for a,n in ((0x300000,0x800000),(CODE,0x20000),(DATA,0x100000),(STACK,0x10000)):
            self.vm.mem_map(a,n)
        self.vm.mem_write(BASE,blob)
        self.cursor=DATA+0x50000
        self.ranges={4:50000,5:40000,6:10000}
        self.distances={};self.contacts={};self.flagships={DIV:SHIP}
        self.damage=0;self.guns=10000;self.nearest=30000
        self.blocked_targets=set();self.blocked_mounts=set()
        self.fired=[];self.clearance=[];self.native_calls=0;self.range_calls=0
        self.return_limit=100;self.active_target=None;self.blocked_bearings=set();self.bearings={}
        self.put(self.info["minute_slot"],DATA+0x800)
        self.put(self.info["clock_slot"],DATA+0x900)
        self.time(100)
        self.put(DIV+0x30,1,1);self.put(DIV+0x2F,3,1)
        self.put(DIV+0x57,DATA+0x7000);self.put(DATA+0x701C,0,1)
        self.put(FORM+0x7E9,0,1)
        # Poison the native world enemy-list indirection: no custom AI path
        # may read it or enter the old selector while AI-controlled.
        self.put(0x9F79D8,0xDEAD0000)
        self.vm.hook_add(UC_HOOK_CODE,self.native)
        self.ship(SHIP)

    def put(self,a,v,n=4):self.vm.mem_write(a,(v&((1<<(8*n))-1)).to_bytes(n,"little"))
    def get(self,a,n=4):return int.from_bytes(self.vm.mem_read(a,n),"little")
    def allocate(self,n=0x100):
        a=self.cursor;self.cursor+=(n+15)&~15;return a
    def time(self,minute,epoch=0x40E30000):
        self.put(DATA+0x800,minute);self.put(DATA+0x904,epoch)
    def ship(self,p,side=0,mounts=((4,8,4,0),)):
        self.put(p+0xA55,side);self.put(p+0x9D3,9,1);self.put(p+0x14,side)
        items=[]
        for kind,loaded,tubes,damaged in mounts:
            m=self.allocate();self.put(m+0xE,kind,1);self.put(m+0xF1,loaded)
            self.put(m+4,tubes);self.put(m+0xF0,damaged,1);items.append(m)
        lst,entries=self.allocate(),self.allocate(4*len(items)+16)
        self.put(p+0x9E,lst);self.put(lst+4,entries);self.put(lst+8,len(items))
        for i,m in enumerate(items):self.put(entries+4*i,m)
        return items
    def target(self,p=DATA+0x10000,kind=5,side=1,visual=2,radar=0,sunk=0):
        self.put(p+0xA55,side);self.put(p+0x9D3,kind,1)
        self.put(p+0xD55,visual);self.put(p+0xD59,radar);self.put(p+0xA9F,sunk,1)
        self.vm.mem_write(p+0xA1C,struct.pack("<3I",111,222,0))
        return p
    def see(self,ship,targets,distance=30000):
        self.contacts[ship]=targets
        lst,items=self.allocate(),self.allocate(4*len(targets)+16)
        self.put(ship+0xAD9,lst);self.put(lst+4,items);self.put(lst+8,len(targets))
        for i,p in enumerate(targets):self.put(items+4*i,p);self.distances[ship,p]=distance

    def ret(self,value=0,cleanup=0):
        sp=self.vm.reg_read(UC_X86_REG_ESP);dest=self.get(sp)
        self.vm.reg_write(UC_X86_REG_EAX,value)
        self.vm.reg_write(UC_X86_REG_ESP,sp+4+cleanup);self.vm.reg_write(UC_X86_REG_EIP,dest)
    def native(self,m,a,size,unused):
        eax=m.reg_read(UC_X86_REG_EAX);edx=m.reg_read(UC_X86_REG_EDX)
        if a==self.info["range"]:
            self.range_calls+=1;self.ret(self.ranges[edx])
        elif a==self.info["ship_distance"]:self.ret(self.distances[eax,edx])
        elif a==self.info["true_bearing"]:
            self.active_target=edx;self.ret(90)
        elif a==self.info["relative_bearing"]:self.ret(self.bearings.get(edx,60))
        elif a==self.info["arc"]:self.ret(int(eax not in self.blocked_mounts and edx not in self.blocked_bearings))
        elif a==self.info["minimum_range"]:self.ret(1000)
        elif a==self.info["friendly_line"]:
            sp=m.reg_read(UC_X86_REG_ESP)
            self.clearance.append((eax,edx,m.reg_read(UC_X86_REG_ECX),self.get(sp+4)))
            self.ret(int(self.active_target in self.blocked_targets),4)
        elif a==self.info["fire"]:
            sp=m.reg_read(UC_X86_REG_ESP)
            requested,bearing,position,target=(self.get(sp+x) for x in (4,8,12,16))
            assert eax==FORM and position==target+0xA1C and bearing==self.bearings.get(target,60)
            assert self.get(edx+0xE,1) in (4,5,6),"SAM spent on surface target"
            assert target in self.contacts[m.reg_read(UC_X86_REG_ECX)]
            assert 0<requested<=min(self.get(edx+0xF1),self.get(edx+4))
            count=min(requested,self.return_limit) if edx not in self.blocked_mounts else 0
            if count:
                self.put(edx+0xF1,self.get(edx+0xF1)-count)
                self.fired.append((m.reg_read(UC_X86_REG_ECX),target,count))
            self.ret(count,16)
        elif a==self.info["selector"]:
            self.native_calls+=1;self.ret(eax)
        elif a==self.info["flagship"]:self.ret(self.flagships.get(eax,0))
        elif a==self.info["damage"]:self.ret(self.damage)
        elif a==self.info["main_gun_range"]:self.ret(self.guns)
        elif a==self.info["closest_enemy"]:self.ret(self.nearest)
        elif a==self.info["dispatcher"]:
            self.put(edx+0x2F,3,1);self.ret()

    def execute(self,address,eax,edx=0,esi=DIV,args=()):
        sp=STACK+0x8000
        values={UC_X86_REG_EAX:eax,UC_X86_REG_EDX:edx,UC_X86_REG_ECX:0x1234,
                UC_X86_REG_EBX:0x2345,UC_X86_REG_ESI:esi,UC_X86_REG_EDI:0x3456,
                UC_X86_REG_EBP:STACK+0x9000,UC_X86_REG_ESP:sp,UC_X86_REG_EFLAGS:0x246}
        for r,v in values.items():self.vm.reg_write(r,v)
        for i,v in enumerate((STOP,)+args):self.put(sp+4*i,v)
        self.vm.emu_start(address,STOP,count=100000)
        assert self.vm.reg_read(UC_X86_REG_EIP)==STOP
        assert self.vm.reg_read(UC_X86_REG_ESP)==sp+4+4*len(args)
        for r in (UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP):
            assert self.vm.reg_read(r)==values[r]
        return self.vm.reg_read(UC_X86_REG_EAX)


class MissileAITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.blob=(HERE/"native-designer-inspection.text.bin").read_bytes()
    def world(self,settings=None):return World(self.blob,settings)

    def test_missile_blocks_fit_beside_battle_ai_code_caches_and_counters(self):
        built=missile_range.build(CODE,self.world().info,STATE)
        intervals=[(b["address"],len(bytes.fromhex(b["bytes"])),b["name"]) for b in built["blocks"]]
        intervals += [(CODE,0x5400,"older code"),(CODE+0x8000,0x3000,"stance cache"),(STATE,0x80,"counters")]
        intervals.sort()
        for left,right in zip(intervals,intervals[1:]):
            self.assertLessEqual(left[0]+left[1],right[0],(left,right))
        self.assertLessEqual(intervals[-1][0]+intervals[-1][1],CODE+0x20000)

    def test_changed_code_refused_and_relocated_image_accepted(self):
        for address,_,_ in missile_ai.WINDOWS:
            changed=bytearray(self.blob);changed[address-BASE]^=1
            with self.assertRaises(ValueError):missile_ai.discover(bytes(changed),BASE)
        delta=0x400000;blob=bytearray(self.blob)
        for offset in audit.text_relocations():
            value=struct.unpack_from("<I",blob,offset)[0]
            struct.pack_into("<I",blob,offset,(value+delta)&0xFFFFFFFF)
        info=missile_ai.discover(bytes(blob),BASE+delta)
        self.assertEqual(info["site"],0x87945A+delta)


if __name__=="__main__":unittest.main()

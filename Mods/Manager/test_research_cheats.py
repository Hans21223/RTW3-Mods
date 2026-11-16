"""Isolated research/aircraft plans, including randomized native slot ordering."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/"vendor"),str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP
import big_guns
import live_cheats as live
import research_cheats as cheats
import modern_tree as tree


class ResearchCheatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob=(HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.layout=cheats.discover(cls.blob,0x301000)

    def fixture(self,raw,gun_base=0x11d):
        vm=Uc(UC_ARCH_X86,UC_MODE_32)
        vm.mem_map(0x200000,0x40000); vm.mem_map(0x9f0000,0x10000); vm.mem_map(0xa10000,0x20000)
        areas=tree.parse(raw); info=self.layout
        vm.mem_map(info["gun_read"]&~0xfff,0x1000); vm.mem_write(info["gun_read"],struct.pack("<I",gun_base))
        vm.mem_write(info["area_count"],struct.pack("<I",len(areas)))
        for area in areas:
            nodes=list(area["rows"])
            if len(nodes)>2: nodes[0],nodes[1]=nodes[1],nodes[0]
            for slot,node in enumerate(nodes):
                at=info["table_id_base"]-21+area["area"]*0x414+slot*29
                vm.mem_write(at,struct.pack("<I",0x500000+slot*100))
                vm.mem_write(at+8,struct.pack("<i",node["year"]+2))  # native variation
                vm.mem_write(at+21,struct.pack("<i",node["id"]))
                vm.mem_write(0x200000+0x336+area["area"]*53+slot,bytes([int(slot==0)]))
        for calibre in range(2,21):
            vm.mem_write(0x200000+gun_base+calibre*4,struct.pack("<i",9 if calibre>10 else -1))
        return vm,dict(layout={"research_cheats":info})

    def contexts(self,vm,root):
        return (patch.object(live.rt,"GAME",root),
                patch.object(live.rt,"read",side_effect=lambda handle,address,size:bytes(vm.mem_read(address,size))))

    def test_all_valid_flags_only_and_guns_for_baseline_and_modern(self):
        for raw,gun_base in ((tree.BASELINE.read_bytes(),0x11d),(tree.render()[0],0x11d),(tree.render()[0],big_guns.GUNS)):
            vm,saved=self.fixture(raw,gun_base)
            # Adjacent nation and unallocated flags must remain unchanged.
            vm.mem_write(0x210000,b"\x55"*0x1000)
            with tempfile.TemporaryDirectory(prefix="research-cheat-") as temp:
                root=Path(temp);(root/"Data").mkdir();(root/"Data/ResearchAreas3.dat").write_bytes(raw)
                a,b=self.contexts(vm,root)
                with a,b:
                    before,records=cheats.research_state(saved,None,0x200000)
                    self.assertEqual(before["completed"],len(tree.parse(raw)))
                    for address,old,new,width in records:
                        self.assertEqual(live.integer(None,address,width),old)
                        vm.mem_write(address,int(new).to_bytes(width,"little",signed=new<0))
                    after,_=cheats.research_state(saved,None,0x200000)
                    self.assertEqual(after["completed"],after["total"])
                    self.assertEqual(after["percent"],100)
                    self.assertEqual(after["guns_maxed"],19 if gun_base==0x11d else 39)   # Big Guns: 2-40 in
                    self.assertEqual(after["total"],sum(len(a["rows"]) for a in tree.parse(raw)))
                    for area in tree.parse(raw):
                        count=len(area["rows"])
                        self.assertEqual(bytes(vm.mem_read(0x200000+0x336+area["area"]*53+count,36-count)),b"\0"*(36-count))
            self.assertEqual(bytes(vm.mem_read(0x210000,0x1000)),b"\x55"*0x1000)
            if gun_base!=0x11d:   # Big Guns: the native array is left alone
                self.assertEqual(bytes(vm.mem_read(0x200000+0x125,19*4)),b"\0"*19*4)

    def test_changed_table_or_invalid_flag_refuses_before_any_write(self):
        raw=tree.BASELINE.read_bytes()
        for bad in ("id","flag"):
            vm,saved=self.fixture(raw)
            if bad=="id": vm.mem_write(self.layout["table_id_base"],struct.pack("<I",999999))
            else: vm.mem_write(0x200000+0x336,b"\x02")
            original=bytes(vm.mem_read(0x200000,0x2000))
            with tempfile.TemporaryDirectory(prefix="research-cheat-") as temp:
                root=Path(temp);(root/"Data").mkdir();(root/"Data/ResearchAreas3.dat").write_bytes(raw)
                a,b=self.contexts(vm,root)
                with a,b,self.assertRaises(ValueError): cheats.research_state(saved,None,0x200000)
            self.assertEqual(bytes(vm.mem_read(0x200000,0x2000)),original)

    def test_full_research_transaction_is_atomic_if_a_late_guard_changes(self):
        raw=tree.render()[0]
        with tempfile.TemporaryDirectory(prefix="research-atomic-") as temp:
            root=Path(temp);(root/"Data").mkdir();(root/"Data/ResearchAreas3.dat").write_bytes(raw)
            for stale in (None,"flag","table"):
                vm,saved=self.fixture(raw)
                a,b=self.contexts(vm,root)
                with a,b: _,records=cheats.research_state(saved,None,0x200000)
                vm.mem_map(0x100000,0x1000);vm.mem_map(0x300000,0x1000);vm.mem_map(0x400000,0x60000)
                main,player,mailbox=0x230000,0x200000,0x400000
                layout=dict(main_slot=0x230800,player_field=0x20,idle=0x100800,
                            update=0x100900,original="558bec83c4f0",
                            records_offset=0x1000,max_edits=live.BULK_MAX_EDITS)
                vm.mem_write(layout["main_slot"],struct.pack("<I",main));vm.mem_write(main+0x20,struct.pack("<I",player))
                vm.mem_write(mailbox,struct.pack("<8I",1,main,player,len(records),0,0,0,0))
                vm.mem_write(mailbox+0x1000,b"".join(struct.pack("<4I",address,old&0xffffffff,new&0xffffffff,width)
                                                   for address,old,new,width in records))
                vm.mem_write(0x100000,live.idle_thunk(0x100000,mailbox,layout));vm.mem_write(layout["update"],b"\xc3")
                vm.reg_write(UC_X86_REG_ESP,0x300800)
                if stale:
                    candidates=[r for r in records if r[3]==(1 if stale=="flag" else 4) and (r[0]>0xa00000 if stale=="table" else True)]
                    target=candidates[-1];vm.mem_write(target[0],int(target[1]+1).to_bytes(target[3],"little"))
                original=bytes(vm.mem_read(player,0x2000))
                vm.emu_start(0x100000,layout["idle"]+6,count=300000)
                self.assertEqual(int.from_bytes(vm.mem_read(mailbox,4),"little"),4 if stale else 2)
                if stale: self.assertEqual(bytes(vm.mem_read(player,0x2000)),original)
                else:
                    with a,b: after,_=cheats.research_state(saved,None,player)
                    self.assertEqual(after["percent"],100)

    def test_aircraft_uses_player_only_and_preserves_ready_and_enemy_models(self):
        vm,saved=self.fixture(tree.BASELINE.read_bytes());d=self.layout;main=0x220000
        vm.mem_write(main+d["request_timer"],struct.pack("<I",8))
        vm.mem_write(d["aircraft_list"],struct.pack("<I",0x230000))
        vm.mem_write(0x230000,struct.pack("<I",0x230100))
        vm.mem_write(0x230104,struct.pack("<II",0x230200,3))
        for i,(owner,timer) in enumerate(((0,12),(1,14),(0,0))):
            pointer=0x231000+i*0x200
            vm.mem_write(0x230200+i*4,struct.pack("<I",pointer))
            vm.mem_write(pointer+d["prototype_owner"],struct.pack("<I",owner))
            vm.mem_write(pointer+d["prototype_timer"],struct.pack("<I",timer))
        with patch.object(live.rt,"read",side_effect=lambda h,a,n:bytes(vm.mem_read(a,n))):
            view,records=cheats.aircraft_state(saved,None,main)
            self.assertEqual(view,dict(available=True,pending_request=True,prototypes=1))
            for address,old,new,width in records: vm.mem_write(address,struct.pack("<I",new))
        self.assertEqual(int.from_bytes(vm.mem_read(main+d["request_timer"],4),"little"),1)
        self.assertEqual(int.from_bytes(vm.mem_read(0x231000+d["prototype_timer"],4),"little"),1)
        self.assertEqual(int.from_bytes(vm.mem_read(0x231200+d["prototype_timer"],4),"little"),14)
        self.assertEqual(int.from_bytes(vm.mem_read(0x231400+d["prototype_timer"],4),"little"),0)


if __name__=="__main__":unittest.main(verbosity=2)

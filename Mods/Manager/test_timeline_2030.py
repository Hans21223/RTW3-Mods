import struct
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent/"vendor"))
sys.path.insert(0,str(Path(__file__).parent.parent/"CampaignOverhaul"))
import timeline_2030 as timeline
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_ESP  # noqa


class TimelineTests(unittest.TestCase):
    def fixture(self):
        base=0x400000
        data=bytearray(0x1000)
        hard=b"\x2d\x6c\x07\x00\x00\x83\xf8\x59"
        data[0x10:0x10+16]=b"\xa1"+struct.pack("<I",0x900000)+b"\x8b\x00"+hard+b"\x7e"
        soft=b"\xa1"+struct.pack("<I",0x900000)+b"\x81\x38\xb2\x07\x00\x00\x0f\x85"
        data[0x40:0x40+len(soft)]=soft
        for n,text in enumerate((timeline.NOTICE,timeline.CONTINUE)):
            at=0x300+n*0x200
            encoded=text.encode("utf-16-le")+b"\0\0"
            struct.pack_into("<I",data,at-4,len(text))
            data[at:at+len(encoded)]=encoded
            data[0x70+n*10:0x75+n*10]=b"\xba"+struct.pack("<I",base+at)
        return data,base

    def plans(self,data,base):
        with patch.object(timeline.rt,"method_address",return_value=base):
            return timeline.discover(bytes(data),base)

    def test_four_patches_only_and_same_size(self):
        data,base=self.fixture()
        plans,slot=self.plans(data,base)
        self.assertEqual(slot,0x900000)
        self.assertEqual(len(plans),4)
        for p in plans:
            self.assertEqual(len(bytes.fromhex(p["original"])),len(bytes.fromhex(p["replacement"])))
        self.assertEqual(bytes.fromhex(plans[1]["replacement"]),struct.pack("<I",2030))

    def run_gate(self,code,year):
        vm=Uc(UC_ARCH_X86,UC_MODE_32)
        vm.mem_map(0x100000,0x1000)
        # Both gates fit eight bytes and feed the same signed JLE. EBX is one
        # for the playable branch and zero for forced retirement.
        sequence=code+b"\x7e\x07\xbb\x00\x00\x00\x00\xeb\x05\xbb\x01\x00\x00\x00"
        vm.mem_write(0x100000,sequence)
        vm.reg_write(UC_X86_REG_EAX,year)
        vm.emu_start(0x100000,0x100000+len(sequence))
        return vm.reg_read(UC_X86_REG_EBX)

    def test_original_gate_ends_in_1990(self):
        data,base=self.fixture(); plans,_=self.plans(data,base)
        old=bytes.fromhex(plans[0]["original"])
        for year in (1890,1900,1970,1989): self.assertEqual(self.run_gate(old,year),1)
        for year in (1990,2029,2030,2031): self.assertEqual(self.run_gate(old,year),0)

    def test_extended_gate_includes_2030_and_stops_2031(self):
        data,base=self.fixture(); plans,_=self.plans(data,base)
        new=bytes.fromhex(plans[0]["replacement"])
        for year in (1890,1970,1989,1990,2000,2029,2030): self.assertEqual(self.run_gate(new,year),1)
        for year in (2031,2040,2100): self.assertEqual(self.run_gate(new,year),0)

    def test_unicode_messages_keep_native_lengths(self):
        data,base=self.fixture(); plans,_=self.plans(data,base)
        self.assertIn("2030",bytes.fromhex(plans[2]["replacement"]).decode("utf-16-le"))
        self.assertIn("2031",bytes.fromhex(plans[3]["replacement"]).decode("utf-16-le"))
        self.assertIn("technical development will level out",bytes.fromhex(plans[3]["replacement"]).decode("utf-16-le"))

    def test_changed_cutoff_refused(self):
        data,base=self.fixture(); data[0x1e]=88
        with self.assertRaises(ValueError): self.plans(data,base)

    def test_changed_year_source_refused(self):
        data,base=self.fixture(); struct.pack_into("<I",data,0x41,0x900004)
        with self.assertRaises(ValueError): self.plans(data,base)

    def test_unowned_notice_refused(self):
        data,base=self.fixture(); data[0x70]=0xb9
        with self.assertRaises(ValueError): self.plans(data,base)

    def test_corrupt_unicode_header_refused(self):
        data,base=self.fixture();struct.pack_into("<I",data,0x2fc,10)
        with self.assertRaises(ValueError): self.plans(data,base)


class YearTableTests(unittest.TestCase):
    """The year switches on the reference build: years before 1991 keep their native branch, later years
    stay in the last range instead of falling into the default (pre-table) branch."""
    BLOB=(Path(__file__).parent/"native-designer-inspection.text.bin").read_bytes()
    BASE,CAVE=0x301000,0x2000000

    def patched(self,last_year=2050):
        plans,code=timeline.year_tables(self.BLOB,self.BASE,last_year,self.CAVE)
        data=bytearray(self.BLOB)
        for p in plans:
            at=p["address"]-self.BASE; old=bytes.fromhex(p["original"])
            self.assertEqual(bytes(data[at:at+len(old)]),old)
            data[at:at+len(old)]=bytes.fromhex(p["replacement"])
        return plans,code,bytes(data)

    def landing(self,blob,code,chain,register,year):
        """Where control leaves the chain (a range's code or the default), for this year in the register."""
        address,hexed,_,_=chain; end=address+len(bytes.fromhex(hexed))
        vm=Uc(UC_ARCH_X86,UC_MODE_32); vm.mem_map(0x300000,0x800000); vm.mem_map(self.CAVE,0x1000)
        vm.mem_write(0x301000,blob); vm.mem_write(self.CAVE,code or b"\x90")
        landed=[]
        def hook(m,at,size,_):
            if not (address<=at<end or self.CAVE<=at<self.CAVE+0x1000): landed.append(at); m.emu_stop()
        vm.hook_add(UC_HOOK_CODE,hook)
        vm.reg_write(register,year); vm.reg_write(UC_X86_REG_ESP,0x700000)
        vm.emu_start(address,0,count=64)
        return landed[0]

    def test_seventy_one_tables_one_byte_or_a_short_thunk(self):
        plans,code,_=self.patched()
        self.assertEqual(len(plans),71)
        sizes=sorted({len(bytes.fromhex(p["original"])) for p in plans})
        self.assertEqual(sizes,[1,5])
        self.assertEqual(sum(len(bytes.fromhex(p["original"]))==5 for p in plans),19)
        self.assertEqual(len(code),19*17)
        self.assertEqual(timeline.year_tables(self.BLOB,self.BASE,1990),([],b""))

    def test_later_years_stay_in_the_last_range(self):
        plans,code,blob=self.patched()
        registers=(UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,None,None,UC_X86_REG_ESI,None)
        for chain in timeline.YEAR_TABLES:
            address,hexed,sub_off,start=chain
            raw=bytes.fromhex(hexed); end=start+raw[sub_off+2]          # the native table's first missing year
            register=registers[raw[1]&7] if raw[0]==0x81 else UC_X86_REG_EAX
            for year in (1850,start-1,start,end-1):
                self.assertEqual(self.landing(blob,code,chain,register,year),self.landing(self.BLOB,b"",chain,register,year),
                                 (hex(address),year))
            last=self.landing(self.BLOB,b"",chain,register,start)
            for year in (end,2000,2030,2050,2060):
                self.assertEqual(self.landing(blob,code,chain,register,year),last,(hex(address),year))

    def test_map_missions_ending_in_1999_stay_open_and_others_still_end(self):
        slot=0x9F7328   # the campaign year, as CheckEndOfGame loads it
        (p,)=timeline.mission_year_plans(self.BLOB,self.BASE,slot)
        blob=bytearray(self.BLOB); at=p["address"]-self.BASE
        blob[at:at+12]=bytes.fromhex(p["replacement"])
        def offered(code,year,first,last):   # BattleOK from its first-year check: BL stays 1 when offered
            vm=Uc(UC_ARCH_X86,UC_MODE_32); vm.mem_map(0x300000,0x800000); vm.mem_map(0x1000000,0x10000)
            vm.mem_write(0x301000,bytes(code)); vm.mem_write(slot,struct.pack("<I",0x1000100))
            vm.mem_write(0x1000100,struct.pack("<I",year))
            vm.mem_write(0x1008000-8,struct.pack("<ii",first,last))
            vm.reg_write(UC_X86_REG_EBX,1); vm.reg_write(UC_X86_REG_ESP,0x1007000)
            from unicorn.x86_const import UC_X86_REG_EBP
            vm.reg_write(UC_X86_REG_EBP,0x1008000)
            vm.emu_start(timeline.MISSION_YEARS,timeline.MISSION_YEARS+0x1A)
            return vm.reg_read(UC_X86_REG_EBX)&0xFF
        for year,first,last,native,now in ((1930,1890,1940,1,1),(1941,1890,1940,0,0),(2011,1890,1940,0,0),
                                           (1995,1890,1999,1,1),(2011,1890,1999,0,1),(2050,1890,1999,0,1),
                                           (2011,1890,2099,1,1),(1885,1890,1999,0,0),(2011,2015,2099,0,0)):
            self.assertEqual((offered(self.BLOB,year,first,last),offered(blob,year,first,last)),(native,now),
                             (year,first,last))

    def test_aircraft_windows_still_match_with_the_tables_in_place(self):
        import aircraft_improvements as aircraft
        _,_,blob=self.patched()
        aircraft.discover(blob,self.BASE)


if __name__=="__main__": unittest.main(verbosity=2)

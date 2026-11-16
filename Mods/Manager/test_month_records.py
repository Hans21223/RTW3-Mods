"""Monthly statistics past 1990: the month-record table moved out of the campaign window (month_records.py)."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX
import modern_research as audit
import month_records as records

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
BASE = records.BASE
MAIN, TABLE = 0x10000000, 0x20001000           # the campaign window object and the moved table


class MonthRecordTests(unittest.TestCase):
    def setUp(self):
        self.info = records.discover(BLOB, BASE)
        self.plans = records.plans(self.info, MAIN, TABLE)

    def test_every_reference_moves_by_one_constant(self):
        self.assertEqual(len(self.plans), 52)
        shifts = {(int.from_bytes(bytes.fromhex(p["replacement"]), "little")-int.from_bytes(bytes.fromhex(p["original"]),
                   "little")) & 0xFFFFFFFF for p in self.plans}
        self.assertEqual(shifts, {(TABLE-(MAIN+records.TABLE)) & 0xFFFFFFFF})
        self.assertTrue(all(records.FIELDS[0] <= d < records.FIELDS[1] for _, d in self.info["sites"]))

    def store(self, year, month, value):
        """LoadMonthRecords' store mov [edx+ecx*4+field], eax as patched, for a row and month; returns the vm."""
        site = next(p for p in self.plans if p["address"] == 0x7DA832+3)
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        code = bytearray(BLOB[0x7DA832-BASE:0x7DA839-BASE]); code[3:7] = bytes.fromhex(site["replacement"])
        vm.mem_map(0x7DA000, 0x1000); vm.mem_write(0x7DA832, bytes(code))
        vm.mem_map(MAIN, 0x30000); vm.mem_map(TABLE-0x1000, records.ALLOCATION)
        vm.reg_write(UC_X86_REG_EDX, MAIN+(year-1900)*records.ROW)   # lea edx,[main+row*0x96*8]
        vm.reg_write(UC_X86_REG_ECX, month*25)                      # month*25 dwords
        vm.reg_write(UC_X86_REG_EAX, value)
        vm.emu_start(0x7DA832, 0x7DA839)
        return vm

    def test_records_from_1890_to_2060_land_in_the_moved_table(self):
        for year, month in ((1890, 1), (1990, 12), (1991, 1), (2050, 12), (2060, 12)):
            vm = self.store(year, month, 0x1234)
            offset = (year-records.FIRST)*records.ROW+month*100
            self.assertEqual(struct.unpack("<I", vm.mem_read(TABLE+offset, 4))[0], 0x1234, (year, month))
            self.assertEqual(bytes(vm.mem_read(MAIN+records.SIZE, 0x400)), bytes(0x400))   # nothing past the window

    def test_changed_code_and_aslr(self):
        changed = bytearray(BLOB); changed[0x7DA832+1-BASE] ^= 1
        with self.assertRaisesRegex(ValueError, "refuse changed"): records.discover(bytes(changed), BASE)
        delta, moved = 0x200000, bytearray(BLOB)
        for offset in audit.text_relocations():
            value = struct.unpack_from("<I", moved, offset)[0]
            struct.pack_into("<I", moved, offset, (value+delta) & 0xFFFFFFFF)
        info = records.discover(bytes(moved), BASE+delta)
        self.assertEqual((info["main"], info["vmt"]), (records.MAIN+delta, records.VMT+delta))
        self.assertEqual([d for _, d in info["sites"]], [d for _, d in self.info["sites"]])


if __name__ == "__main__":
    unittest.main()

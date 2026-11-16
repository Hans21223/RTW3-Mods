import contextlib
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import mod_loader
import save_cheats as cheats
sys.path.insert(0, str(Path(__file__).parent / "vendor"))
sys.path.insert(0, str(Path(__file__).parent.parent / "CampaignOverhaul"))
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EDI
import week_display
import large_hulls
import hull_rules


SAMPLE = (b"\xef\xbb\xbf[General]\r\nYear=1890\r\nMonth=2\r\nDay=12\r\nResearchSpeed=100\r\n"
          b"[Nation0]\r\nName=Japan\r\nFunds=25000\r\nBudgetModifier=16\r\nBaseResources=7700\r\nDockSize=6000\r\nPrestige=20\r\nUnrestLevel=0\r\n"
          b"[Nation0Ships]\r\nShip0Name=Test cruiser\r\nShip0ShipType=CA\r\nShip0Cost=26000\r\nShip0BuildProgress=22000\r\nShip0MonthlyCost=1000\r\nShip0YearBuilt=1891\r\nShip0Halted=0\r\nShip0Hurry=0\r\n")


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="campaign-tools-test-", dir=mod_loader.HERE)
        self.root = Path(self.temp.name)
        self.saves = self.root / "Save"
        self.slot = self.saves / "Game1"
        self.slot.mkdir(parents=True)
        self.path = self.slot / "RTWGame1.bcs"
        self.path.write_bytes(SAMPLE)
        (self.slot / "DesignFiles0.des").write_bytes(b"design bytes")
        self.context = contextlib.ExitStack()
        self.context.enter_context(patch.object(cheats, "SAVE_ROOT", self.saves))
        self.context.enter_context(patch.object(cheats, "BACKUPS", self.root / "backups"))
        self.context.enter_context(patch.object(mod_loader, "running_games", return_value=[]))

    def tearDown(self):
        self.context.close()
        self.temp.cleanup()

    def test_money_edit_preserves_bom_and_other_bytes(self):
        before = cheats.digest(self.path)
        result = cheats.edit(self.path, "Nation0", {"funds": 125000}, expected_hash=before)
        self.assertEqual(self.path.read_bytes(), SAMPLE.replace(b"Funds=25000", b"Funds=125000"))
        self.assertEqual((Path(result["backup"])/self.path.name).read_bytes(), SAMPLE)
        self.assertEqual((Path(result["backup"])/"DesignFiles0.des").read_bytes(), b"design bytes")

    def test_all_requested_fields_and_build_time(self):
        result = cheats.edit(self.path, "Nation0", {"income_level": 32, "income_resources": 15400, "dock_tons": 200000, "research_speed": 250}, ship_index=0, turns=2, expected_hash=cheats.digest(self.path))
        view = result["save"]
        self.assertEqual(view["values"]["dock_tons"], 200000)
        self.assertEqual(view["values"]["income_level"], 32)
        self.assertEqual(view["values"]["research_speed"], 250)
        self.assertEqual(view["ships"][0]["remaining_turns"], 2)
        self.assertEqual(view["ships"][0]["cost"], 26000)
        self.assertEqual(view["ships"][0]["spent"], 22000)

    def test_live_game_blocks_save_writes(self):
        with patch.object(mod_loader, "running_games", return_value=[{"pid": 42}]):
            with self.assertRaisesRegex(ValueError, "Close RTW3"):
                cheats.edit(self.path, "Nation0", {"funds": 100000}, expected_hash=cheats.digest(self.path))
        self.assertEqual(self.path.read_bytes(), SAMPLE)

    def test_changed_save_blocks_edits(self):
        with self.assertRaisesRegex(ValueError, "save changed"):
            cheats.edit(self.path, "Nation0", {"funds": 100000}, expected_hash="wrong")

    def test_invalid_value_and_outside_slot_blocked(self):
        with self.assertRaisesRegex(ValueError, "between"):
            cheats.edit(self.path, "Nation0", {"research_speed": 0}, expected_hash=cheats.digest(self.path))
        outside = self.root / "outside.bcs"
        outside.write_bytes(SAMPLE)
        with self.assertRaisesRegex(ValueError, "inside"):
            cheats.resolve_save(outside)


class RuntimeTests(unittest.TestCase):
    def test_machinery_extension_preserves_native_rows_and_invalid_speeds(self):
        rows = b"".join(struct.pack("<25i", *([k]*18+[-1]*5+[0]*2)) for k in range(1, 91))
        extended = hull_rules.extended_table(rows)
        self.assertEqual(extended[100:9100], rows)
        self.assertEqual(len(extended), 20200)
        last = struct.unpack_from("<25i", extended, 20100)
        self.assertGreater(last[0], 90)
        self.assertEqual(last[18:], (-1,)*5+(0,)*2)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            hull_rules.extended_table(rows[:-4])
        with self.assertRaisesRegex(ValueError, "initialized"):
            hull_rules.extended_table(bytes(9000))

    def test_designer_class_suggestion_expansions_and_fallback_preserve_registers(self):
        code, data, stack, original = 0x100000, 0x200000, 0x300000, 0x100800
        cases = [(4, 14700, 0, 4), (9, 10000, 0, 9), (10, 6000, 0, 10),
                 (6, 14500, 50, 6), (6, 30000, 80, 6), (6, 30000, 81, 17),
                 (6, 5999, 50, 17), (6, 14500, 34, 17), (6, 45001, 50, 17),
                 (4, 25001, 0, 17), (4, 12000, 0, 17), (5, 65000, 68, 17),
                 # CA (kind 3) with main calibre and belt (half-inches): Alaska 12-inch guns and 9-inch belt kept;
                 # 13-inch guns, a belt over 10 inches and out-of-range tonnage go to the native suggestion.
                 (3, 30000, 0, 3, 12, 18), (3, 9000, 0, 3, 8, 20), (3, 30000, 0, 17, 13, 18), (3, 30000, 0, 17, 12, 21),
                 (3, 35001, 0, 17, 12, 18), (3, 4000, 0, 17, 8, 10)]
        for kind, tons, aircraft, expected, *extra in cases:
            calibre, belt = (extra+[0, 0])[:2]
            machine = Uc(UC_ARCH_X86, UC_MODE_32)
            for address in (code, data, stack):
                machine.mem_map(address, 0x1000)
            machine.mem_write(code, hull_rules.classification_thunk(code, original))
            machine.mem_write(original, b"\xb8\x11\x00\x00\x00\xc3")
            machine.mem_write(data+0x2c, struct.pack("<I", tons))
            machine.mem_write(data+0x9d3, bytes([kind]))
            machine.mem_write(data+0x9e0, struct.pack("<I", aircraft))
            machine.mem_write(data+0x6d, struct.pack("<I", calibre))
            machine.mem_write(data+0x40, struct.pack("<I", belt))
            machine.mem_write(stack+0x800, struct.pack("<I", code+0xf00))
            machine.reg_write(UC_X86_REG_EAX, data)
            machine.reg_write(UC_X86_REG_EDX, 0xbeef)
            machine.reg_write(UC_X86_REG_ECX, 0xcafe)
            machine.reg_write(UC_X86_REG_ESP, stack+0x800)
            machine.emu_start(code, code+0xf00, count=1000)
            self.assertEqual(machine.reg_read(UC_X86_REG_EAX), expected, (kind, tons, aircraft))
            self.assertEqual(machine.reg_read(UC_X86_REG_EDX), 0xbeef)
            self.assertEqual(machine.reg_read(UC_X86_REG_ECX), 0xcafe)
            self.assertEqual(machine.reg_read(UC_X86_REG_ESP), stack+0x804)

    def test_week_formatter_all_calendar_days_and_call_registers(self):
        code_address, data_address, stack, original = 0x100000, 0x200000, 0x300000, 0x100800
        slot, day, formats = data_address, data_address+0x20, data_address+0x100
        pointers = [data_address+0x200+index*0x40 for index in range(5)]
        for calendar_day in range(0, 33):
            machine = Uc(UC_ARCH_X86, UC_MODE_32)
            for base in (code_address, data_address, stack):
                machine.mem_map(base, 0x1000)
            machine.mem_write(code_address, week_display.build_thunk(code_address, slot, formats, original))
            machine.mem_write(slot, struct.pack("<I", day))
            machine.mem_write(day, struct.pack("<I", calendar_day))
            machine.mem_write(formats, struct.pack("<5I", *pointers))
            registers = {UC_X86_REG_ESP: stack+0x800, UC_X86_REG_EBX: 0x1234, UC_X86_REG_EDX: 0x5678, UC_X86_REG_ECX: 0xabcd}
            for register, value in registers.items():
                machine.reg_write(register, value)
            machine.emu_start(code_address, original)
            expected = (calendar_day-1)//7 if 1 <= calendar_day <= 31 else 0
            self.assertEqual(machine.reg_read(UC_X86_REG_EAX), pointers[expected])
            for register, value in registers.items():
                self.assertEqual(machine.reg_read(register), value)

    def test_large_hull_hook_updates_only_max_and_replays_prologue(self):
        code_address, data_address, stack, original = 0x100000, 0x200000, 0x300000, 0x100800
        form, spin, field, maximum = data_address, data_address+0x1000, 0x438, 0x30c
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(code_address, 0x1000); machine.mem_map(data_address, 0x3000); machine.mem_map(stack, 0x1000)
        machine.mem_write(code_address, large_hulls.build_thunk(code_address, original, field, maximum, b"\x53\x56\x57\x8b\xd8"))
        machine.mem_write(form+field, struct.pack("<I", spin))
        machine.mem_write(spin+maximum-4, struct.pack("<II", 200, 70000))
        machine.reg_write(UC_X86_REG_EAX, form); machine.reg_write(UC_X86_REG_EDX, 0xbeef)
        machine.reg_write(UC_X86_REG_EBX, 1); machine.reg_write(UC_X86_REG_ESI, 2); machine.reg_write(UC_X86_REG_EDI, 3)
        machine.reg_write(UC_X86_REG_ESP, stack+0x800)
        machine.emu_start(code_address, original+5)
        self.assertEqual(struct.unpack("<II", machine.mem_read(spin+maximum-4, 8)), (200, 200000))
        self.assertEqual(machine.reg_read(UC_X86_REG_EDX), 0xbeef)
        self.assertEqual(machine.reg_read(UC_X86_REG_EBX), form)
        self.assertEqual(machine.reg_read(UC_X86_REG_ESP), stack+0x800-12)
        self.assertEqual(struct.unpack("<III", machine.mem_read(stack+0x800-12, 12)), (3, 2, 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)

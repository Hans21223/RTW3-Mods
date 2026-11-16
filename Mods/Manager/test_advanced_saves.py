"""Advanced editor regression tests against synthetic temporary save slots."""
import contextlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import advanced_saves as advanced
import save_cheats as saves
import mod_loader

SAMPLE = (b"\xef\xbb\xbf[General]\r\nYear=1890\r\nMonth=1\r\nDay=1\r\nResearchSpeed=100\r\nResearchVariation=1\r\nFleetSize=8\r\nIDNo=500\r\n"
          b"[Nation0]\r\nName=Japan\r\nNationNumber=6\r\nFunds=25000\r\nBudgetModifier=16\r\nBaseResources=7700\r\nDockSize=6000\r\nPrestige=20\r\nUnrestLevel=0\r\nResearchPct=8\r\nResearch0Prio=2\r\nResearch0ResearchPoints=1\r\nResearch0CurrentLevel=0\r\nAdmiralName=Togo\r\n"
          b"[Nation0Ships]\r\nShip0Id=124\r\nShip0DesignRefId=2\r\nShip0Name=Test cruiser\r\nShip0Cost=26000\r\nShip0BuildProgress=22000\r\nShip0MonthlyCost=1000\r\nShip0RepairTime=4\r\nShip0YearBuilt=1891\r\n")


class AdvancedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="advanced-save-test-", dir=mod_loader.HERE)
        self.root = Path(self.temp.name)
        self.save_root = self.root/"Save"; self.slot = self.save_root/"Game1"; self.slot.mkdir(parents=True)
        self.path = self.slot/"RTWGame1.bcs"; self.path.write_bytes(SAMPLE)
        (self.slot/"design.des").write_bytes(b"original design")
        self.context = contextlib.ExitStack()
        self.context.enter_context(patch.object(saves, "SAVE_ROOT", self.save_root))
        self.context.enter_context(patch.object(saves, "BACKUPS", self.root/"backups"))
        self.context.enter_context(patch.object(mod_loader, "running_games", return_value=[]))

    def tearDown(self):
        self.context.close(); self.temp.cleanup()

    def edit(self, section, key, value, more=None):
        _, data, _ = saves.parse(self.path.read_bytes())
        changes = [{"section": section, "key": key, "value": value, "expected": data[section][key]}]
        return advanced.edit(self.path, changes+(more or []), saves.digest(self.path))

    def test_search_paging_and_protected_rows(self):
        result = advanced.inspect(self.path, "*", "Research", limit=2)
        self.assertGreater(result["total"], 2)
        self.assertEqual(len(result["fields"]), 2)
        row = advanced.inspect(self.path, "Nation0", "CurrentLevel")["fields"][0]
        self.assertFalse(row["editable"])
        self.assertGreater(advanced.inspect(self.path, "Nation0")["editable"], 8)

    def test_multiple_fields_text_research_and_repairs_preserve_other_bytes(self):
        changes = [{"section": "Nation0", "key": "Research0Prio", "value": "3", "expected": "2"},
                   {"section": "Nation0Ships", "key": "Ship0RepairTime", "value": "0", "expected": "4"}]
        result = self.edit("Nation0Ships", "Ship0Name", "Takao", changes)
        expected = SAMPLE.replace(b"Ship0Name=Test cruiser", b"Ship0Name=Takao").replace(b"Research0Prio=2", b"Research0Prio=3").replace(b"Ship0RepairTime=4", b"Ship0RepairTime=0")
        self.assertEqual(self.path.read_bytes(), expected)
        backup = Path(result["backup"])
        self.assertEqual((backup/self.path.name).read_bytes(), SAMPLE)
        self.assertEqual((backup/"design.des").read_bytes(), b"original design")

    def test_invalid_date_rejected_before_backup_or_write(self):
        with self.assertRaisesRegex(ValueError, "valid calendar date"):
            self.edit("General", "Month", "2", [{"section": "General", "key": "Day", "value": "31", "expected": "1"}])
        self.assertEqual(self.path.read_bytes(), SAMPLE)
        self.assertFalse((self.root/"backups").exists())

    def test_structural_fields_and_new_fields_rejected(self):
        for section, key in (("General", "IDNo"), ("Nation0", "NationNumber"), ("Nation0Ships", "Ship0DesignRefId")):
            with self.assertRaisesRegex(ValueError, "Protected"):
                self.edit(section, key, "7")
        with self.assertRaisesRegex(ValueError, "cannot be added"):
            advanced.edit(self.path, [{"section": "Nation0", "key": "NewField", "value": "1", "expected": "0"}], saves.digest(self.path))

    def test_build_cost_consistency_and_numeric_range(self):
        with self.assertRaisesRegex(ValueError, "build progress"):
            self.edit("Nation0Ships", "Ship0Cost", "1000")
        with self.assertRaisesRegex(ValueError, "outside"):
            self.edit("Nation0", "Research0Prio", "99")
        with self.assertRaisesRegex(ValueError, "single-line"):
            self.edit("Nation0Ships", "Ship0Name", "Bad\nInjected=1")

    def test_running_game_stale_hash_and_duplicate_fields_rejected(self):
        with patch.object(mod_loader, "running_games", return_value=[{"pid": 1}]):
            with self.assertRaisesRegex(ValueError, "Close RTW3"):
                advanced.edit(self.path, [], saves.digest(self.path))
        with self.assertRaisesRegex(ValueError, "save changed"):
            advanced.edit(self.path, [], "wrong")
        item = {"section": "Nation0", "key": "Funds", "value": "200", "expected": "25000"}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            advanced.edit(self.path, [item, item], saves.digest(self.path))
        self.assertEqual(self.path.read_bytes(), SAMPLE)


if __name__ == "__main__": unittest.main(verbosity=2)

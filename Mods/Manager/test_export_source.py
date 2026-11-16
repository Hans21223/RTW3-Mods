"""The public source export: code, docs and mod packages only, synced into a clone, and refused on personal data."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import export_source as export


class ExportTests(unittest.TestCase):
    def test_exports_source_only_and_removes_what_was_dropped(self):
        with tempfile.TemporaryDirectory() as folder:
            clone = Path(folder)
            stale = clone/"Mods"/"Library"/"week-display"/"mod.json"
            stale.parent.mkdir(parents=True); stale.write_text("{}")
            (clone/".git").mkdir(); (clone/".git"/"config").write_text("kept")
            count = export.export(clone)
            names = {p.relative_to(clone).as_posix() for p in (clone/"Mods").rglob("*") if p.is_file()}
            self.assertEqual(len(names), count)
            for name in ("Mods/Manager/mod_loader.py", "Mods/CampaignOverhaul/designer_visuals.py",
                         "Mods/ModManager/updates.py", "Mods/Library/timeline-2030/mod.json"):
                self.assertIn(name, names)
            self.assertFalse(stale.exists())
            self.assertEqual((clone/".git"/"config").read_text(), "kept")
            self.assertIn("# RTW3-Mods", (clone/"README.md").read_text())
            self.assertEqual((clone/".gitattributes").read_text(), "* -text\n")
            (clone/"README.md").write_text("edited on GitHub")
            export.export(clone)
            self.assertEqual((clone/"README.md").read_text(), "edited on GitHub")   # never overwritten
            for name in names:
                self.assertNotRegex(name, r"vanilla/|backups/|baseline/|vendor/|\.text\.bin$|_report\.json$|state\.json$")

    def test_personal_data_stops_the_export(self):
        with patch.object(export, "secrets", return_value=[b"def files"]), \
             self.assertRaisesRegex(ValueError, "personal data"):
            export.files()


if __name__ == "__main__": unittest.main()

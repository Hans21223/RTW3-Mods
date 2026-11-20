import contextlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


MANAGER = Path(__file__).resolve().parent
OVERHAUL = Path(__file__).resolve().parent.parent / "CampaignOverhaul"
sys.path.insert(0, str(OVERHAUL))
sys.path.insert(0, str(MANAGER))
import campaign_mod
import mod_loader


class CampaignEventDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output, cls.changed, cls.total = campaign_mod.render_events()
        cls.groups = campaign_mod.parse_events(cls.output)
        cls.baseline = campaign_mod.parse_events(campaign_mod.EVENT_BASE.read_bytes())
        cls.outcomes = json.loads(campaign_mod.EVENT_OUTCOMES.read_text(encoding="utf-8"))

    def test_every_question_lists_its_three_responses_effects(self):
        # The one-line answer buttons clip long text, so the effects follow the question, which wraps.
        self.assertEqual((self.changed, self.total), (100, 100))
        self.assertEqual(len(self.groups), 100)
        for slot, group in enumerate(self.groups):
            with self.subTest(slot=slot):
                self.assertEqual(len(group[1:]), 3)
                summary = group[0][0][group[0][0].index(" Effects: "):]
                for number, response in enumerate(group[1:], 1):
                    self.assertTrue(response[0])
                    self.assertNotIn(" [", response[0])
                    self.assertIn(f"({number}) {campaign_mod.event_effect_hint(response)}.", summary)
        self.assertTrue(self.groups[36][0][0].endswith(
            "Effects: (1) Tension -1. (2) Budget +300, Tension +1. (3) Budget +100."))   # zero changes left out

    def test_only_declared_mechanical_changes_are_made(self):
        additions = {
            (int(slot), response["answer"])
            for slot, response in self.outcomes["add_responses"].items()
        }
        overrides = {
            (int(slot), int(answer))
            for slot, values in self.outcomes["overrides"].items()
            for answer in values
        }
        disabled = set(self.outcomes["disabled_questions"])
        for slot, (rendered, baseline) in enumerate(zip(self.groups, self.baseline)):
            expected = baseline[0][1:]
            if slot in disabled:   # moved past the campaign era: the engine has no off switch
                expected[5:7] = ["9999", "9999"]
            self.assertEqual(rendered[0][1:], expected, slot)
            for answer, (after, before) in enumerate(zip(rendered[1:], baseline[1:])):
                with self.subTest(slot=slot, answer=answer):
                    if (slot, answer) in additions:
                        self.assertEqual(before, ["", "", "", "", "", "0"])
                    elif (slot, answer) not in overrides:
                        self.assertEqual(after[1:], before[1:])

    def test_authored_expansions_and_balance_adjustments(self):
        for slot in range(100):
            self.assertEqual(sum(bool(row[0]) for row in self.groups[slot][1:]), 3)
        self.assertEqual(self.groups[26][1][1:4], ["0", "1", "2"])
        self.assertEqual(self.groups[75][1][5], "12")
        self.assertEqual(self.groups[75][3][5], "11")
        self.assertEqual(self.groups[84][3][1:4], ["1", "-1", "0"])
        self.assertEqual(self.groups[90][1][1:4], ["0", "-1", "-1"])
        self.assertEqual(self.groups[95][2][1:4], ["-1", "0", "-1"])
        self.assertEqual(self.groups[95][3][1:4], ["-2", "0", "-2"])
        self.assertNotEqual(self.groups[37][1][1:], self.groups[37][2][1:])
        self.assertNotEqual(self.groups[44][2][1:], self.groups[44][3][1:])

    def test_mod_manager_installs_and_restores_the_event_package(self):
        original_events = b"original event table\r\n"
        original_tips = b"original tips\r\n"
        with tempfile.TemporaryDirectory(prefix="campaign-event-install-", dir=MANAGER) as temp:
            root = Path(temp)
            game = root / "game"
            manager = game / "Mods" / "Manager"
            library = game / "Mods" / "Library"
            data = game / "Data"
            manager.mkdir(parents=True)
            data.mkdir(parents=True)
            (game / "RTW3.exe").write_bytes(b"test executable")
            (data / "Events.dat").write_bytes(original_events)
            (data / "Tips.txt").write_bytes(original_tips)
            shutil.copytree(mod_loader.LIBRARY / "campaign-events", library / "campaign-events")
            patcher = contextlib.ExitStack()
            patcher.enter_context(patch.object(mod_loader, "GAME", game))
            patcher.enter_context(patch.object(mod_loader, "HERE", manager))
            patcher.enter_context(patch.object(mod_loader, "LIBRARY", library))
            patcher.enter_context(patch.object(mod_loader, "STATE", manager / "state.json"))
            patcher.enter_context(patch.object(mod_loader, "running_games", return_value=[]))
            try:
                mod_loader.write_json(mod_loader.STATE, {
                    "schema": 1, "enabled": [], "applied": {}, "originals": {},
                    "history": [], "game_sha256": mod_loader.sha(game / "RTW3.exe"),
                    "build": "test",
                })
                mod_loader.apply(["campaign-events"])
                self.assertEqual((data / "Events.dat").read_bytes(), self.output)
                installed_tips = (library / "campaign-events" / "Files" / "Data" / "Tips.txt").read_bytes()
                self.assertEqual((data / "Tips.txt").read_bytes(), installed_tips)
                mod_loader.apply([])
                self.assertEqual((data / "Events.dat").read_bytes(), original_events)
                self.assertEqual((data / "Tips.txt").read_bytes(), original_tips)
            finally:
                patcher.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

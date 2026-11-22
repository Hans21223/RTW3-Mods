"""Nuclear Armageddon: the switch it writes into Expanded Timeline's runtime, its order and its package.
The rules it switches on are tested with their weapons (test_modern_navy, test_nuclear_subs, test_air_defence)."""
import json
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
import modern_research as modern
import nuclear_armageddon as armageddon
import runtime_registry as registry
import shell_doctrine as sd

DETAILS = modern.discover(open(HERE/"native-designer-inspection.text.bin", "rb").read(), 0x301000)


class ArmageddonTests(unittest.TestCase):
    def test_it_sets_the_flag_and_renames_the_missile_tick_box(self):
        blocks = {b["name"]: b for b in modern.build(0x2000000, DETAILS)[0]}
        (flag, old_flag, new_flag), (text, old_text, new_text) = armageddon.plan(blocks)
        self.assertEqual((flag, old_flag, new_flag), (blocks[sd.ARMAGEDDON_BLOCK]["address"], bytes(4), struct.pack("<I", 1)))
        self.assertEqual(text, blocks[sd.MISSILE_TEXT_BLOCK]["address"])
        self.assertEqual(old_text, sd.literal(sd.TEXTS["missile"])[:len(new_text)])
        self.assertEqual(new_text, sd.literal("Use nuclear SSBN, SSM, SAM (1500 each)"))

    def test_an_older_expanded_timeline_is_refused(self):
        with self.assertRaises(ValueError): armageddon.plan({})

    def test_it_attaches_after_expanded_timeline_and_needs_it(self):
        order = [step["adapter"] for step in registry.plan(["nuclear-armageddon", "modern-research", "timeline-2030"])]
        self.assertLess(order.index("modern-research"), order.index("nuclear-armageddon"))
        with self.assertRaises(ValueError): registry.plan(["nuclear-armageddon", "timeline-2030"])

    def test_the_package_needs_expanded_timeline_and_ships_no_files(self):
        manifest = json.loads((HERE.parent/"Library/nuclear-armageddon/mod.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["id"], manifest["requires"], manifest["runtime"], manifest["files"]),
                         ("nuclear-armageddon", ["timeline-2030"], {"adapter": "nuclear-armageddon"}, []))


if __name__ == "__main__": unittest.main(verbosity=2)

"""Guard the 25-to-100 native ship-graphics extension without a running game."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "CampaignOverhaul"))
import ship_visual_layers


class ShipVisualLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE / "native-designer-inspection.text.bin").read_bytes()
        cls.base = 0x301000

    def test_add_mirror_copy_and_both_design_loaders_go_to_100(self):
        result = ship_visual_layers.discover(self.blob, self.base)
        self.assertEqual((result["native_limit"], result["visual_limit"]), (25, 100))
        sites = {(site["kind"], site["address"]): (site["original"], site["replacement"]) for site in result["sites"]}
        guard, loop = ("83780819", "83780864"), ("83fe19", "83fe64")   # CMP [EAX+8],25 / CMP ESI,25 -> 100
        self.assertEqual(sites, {("add", 0x5F318D): guard, ("add", 0x5F4F07): guard, ("add", 0x5F535D): guard,
                                 ("load", 0x8EE6B7): loop, ("load", 0x9438D4): loop})

    def test_unknown_add_handler_is_refused(self):
        changed = bytearray(self.blob)
        at = 0x5f318d - self.base
        changed[at:at+4] = b"\x83\x78\x08\x18"
        with self.assertRaisesRegex(ValueError, "25-graphic add limit"):
            ship_visual_layers.discover(bytes(changed), self.base)

    def test_a_changed_design_loader_is_refused(self):
        changed = bytearray(self.blob)
        at = 0x9438d4 - self.base
        changed[at:at+3] = b"\x83\xfe\x1a"
        with self.assertRaisesRegex(ValueError, "25-graphic load limits"):
            ship_visual_layers.discover(bytes(changed), self.base)


if __name__ == "__main__":
    unittest.main()

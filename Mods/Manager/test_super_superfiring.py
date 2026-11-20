"""Focused checks for the added raised turret positions and package wiring."""
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "CampaignOverhaul"))
sys.path.insert(0, str(ROOT / "Manager"))

import mod_loader
import runtime_registry
import super_superfiring as feature


class SuperSuperfiringTests(unittest.TestCase):
    def test_thunk_routes_all_added_codes_to_true_and_others_to_native(self):
        address, passthrough = 0x10000000, 0x10001000
        code = feature.raised_position_thunk(address, passthrough)
        true_offset = 12 * len(feature.ADDED_POSITIONS) + 5

        self.assertEqual(len(code), true_offset + 6)
        for index, position in enumerate(feature.ADDED_POSITIONS):
            start = index * 12
            self.assertEqual(code[start:start+6], b"\x66\x81\x78\x08" + struct.pack("<H", ord(position)))
            self.assertEqual(code[start+6:start+8], b"\x0f\x84")
            displacement = struct.unpack_from("<i", code, start+8)[0]
            self.assertEqual(address + start + 12 + displacement, address + true_offset)

        self.assertEqual(code[true_offset-5], 0xe9)
        passthrough_delta = struct.unpack_from("<i", code, true_offset-4)[0]
        self.assertEqual(address + true_offset + passthrough_delta, passthrough)
        self.assertEqual(code[true_offset:], bytes.fromhex("b801000000c3"))

    def test_native_signature_is_checked_before_hook_planning(self):
        base = 0x401000
        with patch.object(feature.rt, "method_address", return_value=base):
            result = feature.discover(bytes.fromhex("0fb740086683e8") + b"\0"*8, base)
            self.assertEqual(result["added_positions"], list(feature.ADDED_POSITIONS))
            with self.assertRaisesRegex(ValueError, "Unknown native turret-height check"):
                feature.discover(b"\x90"*15, base)

    def test_package_and_dependency_order_include_the_data_file(self):
        package = mod_loader.read_manifest(ROOT / "Library" / "super-superfiring-turret")
        self.assertEqual(package["runtime"]["adapter"], "super-superfiring-turret")
        self.assertEqual(package["files"], [{"source": "Files/Data/gunpos.txt", "target": "Data/gunpos.txt"}])
        positions = (ROOT / "Library" / "super-superfiring-turret" / "Files" / "Data" / "gunpos.txt").read_text(encoding="ascii")
        for position in feature.ADDED_POSITIONS:
            self.assertIn(position + " - ", positions)

        plan = runtime_registry.plan(["super-superfiring-turret", "big-guns", "large-hulls"])
        order = [step["adapter"] for step in plan]
        self.assertLess(order.index("large-hulls"), order.index("super-superfiring-turret"))
        self.assertLess(order.index("big-guns"), order.index("super-superfiring-turret"))


if __name__ == "__main__":
    unittest.main()

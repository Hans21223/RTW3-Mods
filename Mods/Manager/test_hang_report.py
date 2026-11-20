"""The freeze report's address naming, call detection and frame walk, on made-up stacks (no game needed)."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent/"ModManager"), str(HERE.parent/"CampaignOverhaul")]
import hang_report as hang

GAME, MOD = 0xCB0000, 0x7040000
KNOWN = [(GAME, GAME+0xD00000, "RTW3.exe"), (0x77000000, 0x77100000, "ntdll.dll"), (MOD, MOD+0x10000, "vls-cells")]


class HangReportTests(unittest.TestCase):
    def test_addresses_are_named_as_the_mods_code_names_them(self):
        self.assertEqual(hang.where(GAME+0x4B6B03, KNOWN), "game 0x7b6b03")   # as in ai_modern's SITE
        self.assertEqual(hang.where(MOD+0x769A, KNOWN), "vls-cells+0x769a")
        self.assertEqual(hang.where(0x77000010, KNOWN), "ntdll.dll+0x10")
        self.assertEqual(hang.where(0x1234, KNOWN), "0x1234")

    def test_return_addresses_follow_a_call(self):
        before = lambda code: (b"\x90"*7 + code)[-7:]
        for call in (b"\xe8\0\0\0\0", b"\xff\x15\0\0\0\0", b"\xff\xd0", b"\xff\x50\x08", b"\xff\x90\0\0\0\0",
                     b"\xff\x14\x85\0\0\0\0", b"\xff\x54\x24\x08"):
            self.assertTrue(hang.after_call(before(call)), call.hex())
        for other in (b"\x8b\x45\xfc", b"\xff\x75\x08", b"\x90\x90"):   # mov, push [ebp+8], nops
            self.assertFalse(hang.after_call(before(other)), other.hex())

    def test_the_frame_chain_and_the_report(self):
        esp = 0x100000
        stack = bytearray(0x40)
        struct.pack_into("<II", stack, 0x10, esp+0x20, GAME+0x10)    # EBP -> saved EBP, return address
        struct.pack_into("<II", stack, 0x20, 0, MOD+0x20)              # the outermost frame
        registers = dict(edi=0, esi=0, ebx=0, edx=0, ecx=0, eax=0, ebp=esp+0x10, eip=GAME+0x5, esp=esp)
        self.assertEqual(hang.chain(registers, bytes(stack)), [GAME+0x10, MOD+0x20])
        report = hang.text([(registers, [MOD+0x20], [GAME+0x10])] * 3, KNOWN, 0.1)
        self.assertIn("    3  game 0x300005", report)                   # where it was, in all three samples
        self.assertIn("    3  vls-cells+0x20", report)
        self.assertIn("vls-cells 0x7040000-0x7050000", report)


if __name__ == "__main__":
    unittest.main()

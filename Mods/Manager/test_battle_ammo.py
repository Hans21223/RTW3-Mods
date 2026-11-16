"""Synthetic battle + real x86 transaction tests. No game/save writes."""
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
import battle_ammo as ammo
import live_cheats as live
import test_live_cheats as protocol
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EDX, UC_X86_REG_ECX, UC_X86_REG_ESP

D = 0x200000


class AmmoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()

    def setUp(self):
        self.memory = bytearray(0x50000)
        self.info = dict(form_slot=D+0x27000, ships_slot=D+0x27004, side_slot=D+0x27008)
        self.saved = dict(layout=dict(battle_ammo=self.info), battle_environment=dict(state=D+0x26000, version=2))
        self.before = dict(player=D+0x2000, main=D+0x1000, sha256="fixture")
        self.ship, self.turret, self.mount = D+0x30000, D+0x40000, D+0x40200
        self.put(D+0x26008, D+0x28000); self.put(self.info["form_slot"], D+0x28000)
        self.put(self.info["ships_slot"], D+0x27010)
        self.pool(D+0x27010, D+0x27020, D+0x27100,
                  [self.ship, D+0x31000, D+0x32000, D+0x33000, D+0x34000])
        for i, value in enumerate([50, 50, 0]*4): self.put(D+0x20c0+i*4, value)
        self.put(self.ship+0x10, 123)
        self.put(self.ship+0x8b, 120); self.put(self.ship+0x6d, 16)
        self.pool(self.ship+0x9a, D+0x41000, D+0x41100, [self.turret, D+0x40100])
        self.pool(self.ship+0x9e, D+0x41200, D+0x41300, [self.mount, D+0x40300])
        self.put(self.turret+4, 4); self.put(self.turret+0x29, 12); self.put(self.turret+0x2d, 40)
        self.put(self.turret+0x20, 7)  # Jammed: refill must not repair it.
        self.put(D+0x40124, 1, 1); self.put(D+0x40129, 17)  # Destroyed gun mount.
        self.put(self.mount+4, 4); self.put(self.mount+0xf, 3); self.put(self.mount+0xf5, 5)
        self.put(D+0x403f0, 1, 1); self.put(D+0x40304, 8)  # Destroyed torpedo mount.
        self.put(self.ship+0xba3, 1000); self.put(self.ship+0x71, 5)
        self.put(self.ship+0xb87, 20); self.put(self.ship+0xb8b, 10)
        self.put(self.ship+0xba7, 400); self.put(self.ship+0x75, 3)
        # Enemy, allied, sunk and sinking rows deliberately have no weapon lists.
        self.put(D+0x31000+0xa55, 1); self.put(D+0x31000+0x14, 1)
        self.put(D+0x32000+0x14, 2)
        self.put(D+0x33000+0xa9f, 1, 1); self.put(D+0x34000+0xb35, 1)

    def put(self, address, value, width=4):
        self.memory[address-D:address-D+width] = value.to_bytes(width, "little", signed=False)

    def read(self, handle, address, size):
        if not D <= address <= address+size <= D+len(self.memory):
            raise ValueError("Invalid fixture memory read")
        return bytes(self.memory[address-D:address-D+size])

    def pool(self, address, pool, entries, members):
        self.put(address, pool); self.put(pool+4, entries); self.put(pool+8, len(members))
        for i, value in enumerate(members): self.put(entries+i*4, value)

    def plan(self):
        with patch.object(live.rt, "read", side_effect=self.read):
            return ammo.plan(self.saved, 1, self.before)

    def test_native_layout_and_changed_code_refusal(self):
        self.assertEqual(ammo.discover(self.blob, 0x301000)["side_slot"], 0xa23630)
        for address, _, _ in ammo.WINDOWS:
            data = bytearray(self.blob); data[address-0x301000] ^= 1
            with self.assertRaisesRegex(ValueError, "refuses changed"):
                ammo.discover(data, 0x301000)

    def test_loadout_caps_and_native_ammo_categories(self):
        doctrine = [50, 50, 0]*4
        self.assertEqual(ammo.loadout(1000, 5, False, doctrine), [500, 500, 0])
        self.assertEqual(ammo.loadout(1000, 5, True, doctrine), [0, 1000, 0])
        self.assertEqual(ammo.loadout(1000, 6, True, doctrine), [0, 900, 100])
        self.assertEqual(ammo.loadout(1000, 3, False, doctrine), [0, 1000, 0])
        for cap in range(1, 99): self.assertEqual(sum(ammo.loadout(cap, 16, False, doctrine)), cap)

    def transaction(self, records, stale=None):
        helper = protocol.MailboxTests()
        vm, mailbox, layout = helper.make([(a, o & 0xffffffff, n & 0xffffffff, w) for a, o, n, w in records], bulk=True)
        vm.mem_write(D+0x2000, bytes(self.memory[0x2000:0x2100]))
        vm.mem_write(D+0x26000, bytes(self.memory[0x26000:]))
        if stale: vm.mem_write(stale[0], stale[1])
        helper.run_code(vm, layout)
        return vm, int.from_bytes(vm.mem_read(mailbox, 4), "little")

    def test_refill_commits_and_native_remaining_ammo_reads_new_values(self):
        untouched = bytes(self.memory)
        records, message = self.plan()
        self.assertEqual(bytes(self.memory), untouched)  # Planning never writes.
        self.assertIn("1 player ships", message)
        vm, result = self.transaction(records)
        self.assertEqual(result, 2)
        self.assertEqual(list(struct.unpack("<3i", vm.mem_read(self.turret+0x29, 12))), [240, 240, 0])
        self.assertEqual(list(struct.unpack("<3i", vm.mem_read(self.ship+0xb87, 12))), [500, 500, 0])
        self.assertEqual(list(struct.unpack("<3i", vm.mem_read(self.ship+0xb93, 12))), [0, 400, 0])
        self.assertEqual(int.from_bytes(vm.mem_read(self.mount+0xf1, 4), "little"), 4)
        for address, size in [(self.turret+0x20, 4), (self.mount+0xf, 4), (self.mount+0xf5, 4),
                              (D+0x40100, 256), (D+0x40300, 256), (D+0x31000, 0x4000),
                              (self.ship+0xbb3, 8)]:
            self.assertEqual(bytes(vm.mem_read(address, size)), self.read(1, address, size))
        # Run the actual native tactical ammo reader after the real mailbox.
        vm.mem_map(0x910000, 0x10000); vm.mem_map(0x3b0000, 0x10000)
        vm.mem_write(0x917df0, self.blob[0x917df0-0x301000:0x917e97-0x301000])
        vm.mem_write(0x3b6d6c, b"\x8b\x40\x04\x8b\x04\x90\xc3")
        for battery, expected in [(1, 480), (2, 1000), (3, 400)]:
            vm.mem_write(0x302000, struct.pack("<I", 0x100f00))
            for reg, value in [(UC_X86_REG_ESP, 0x302000), (UC_X86_REG_EAX, self.ship),
                               (UC_X86_REG_EDX, battery), (UC_X86_REG_ECX, 3)]: vm.reg_write(reg, value)
            vm.emu_start(0x917df0, 0x100f00)
            self.assertEqual(vm.reg_read(UC_X86_REG_EAX), expected)

    def test_battle_or_magazine_change_cancels_every_write(self):
        records, _ = self.plan()
        for address in (self.info["form_slot"], self.turret+0x29, D+0x27020+8, self.ship+0x14):
            vm, result = self.transaction(records, (address, struct.pack("<I", 99)))
            self.assertEqual(result, 4)
            self.assertEqual(bytes(vm.mem_read(self.ship+0xb87, 12)), self.read(1, self.ship+0xb87, 12))
            self.assertEqual(int.from_bytes(vm.mem_read(self.mount+0xf1, 4), "little"), 0)

    def test_already_full_returns_no_transaction(self):
        for address, _, new, width in self.plan()[0]: self.put(address, new & ((1 << (width*8))-1), width)
        records, message = self.plan()
        self.assertEqual(records, [])
        self.assertIn("already full", message)

    def test_outside_battle_and_invalid_magazine_fail_closed(self):
        self.put(D+0x26008, 0)
        with self.assertRaisesRegex(ValueError, "Open a battle"): self.plan()
        self.put(D+0x26008, D+0x28000)
        self.put(self.ship+0xba3, 0xffffffff)
        with self.assertRaisesRegex(ValueError, "Invalid ship magazine"): self.plan()

    def test_noop_action_dispatch_preserves_specific_message(self):
        snapshot = dict(self.before, values={}, ships=[])
        with patch.object(live, "session", return_value=(self.saved, 1)), \
             patch.object(live, "snapshot", return_value=snapshot), \
             patch.object(ammo, "plan", return_value=([], "Already full fixture")) as planner, \
             patch.object(live.rt.K, "CloseHandle", create=True):
            result = live.edit(1, {}, "fixture", action="refill-ammo")
            planner.assert_called_once()
            self.assertEqual(result["message"], "Already full fixture")


if __name__ == "__main__": unittest.main(verbosity=2)

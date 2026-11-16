"""Isolated live-cheat protocol tests. Never edits a real campaign."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / "vendor"))
sys.path.insert(0, str(Path(__file__).parent.parent / "CampaignOverhaul"))
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import *
import live_cheats as live
import legacy_fleet


class MailboxTests(unittest.TestCase):
    code, data, stack = 0x100000, 0x200000, 0x300000

    def make(self, records, status=1, expected_main=None, expected_player=None, original="83c4e433d2", bulk=False):
        m = Uc(UC_ARCH_X86, UC_MODE_32)
        m.mem_map(self.code, 0x4000); m.mem_map(self.data, 0x6000 if not bulk else 0x50000); m.mem_map(self.stack, 0x4000)
        main, player, mailbox = self.data+0x1000, self.data+0x2000, self.data+0x3000
        layout = {"main_slot": self.data, "player_field": 0x20, "idle": self.code+0x800,
                  "update": self.code+0x900, "original": original}
        if bulk: layout.update(records_offset=0x1000, max_edits=live.BULK_MAX_EDITS)
        m.mem_write(self.data, struct.pack("<I", main))
        m.mem_write(main+0x20, struct.pack("<I", player))
        m.mem_write(mailbox, struct.pack("<8I", status, main if expected_main is None else expected_main,
                                        player if expected_player is None else expected_player, len(records), 0, 0, 0, 0))
        m.mem_write(mailbox+layout.get("records_offset", 32), b"".join(struct.pack("<4I", *row) for row in records))
        # Simulated budget refresh: count calls, deliberately clobber scratch registers.
        m.mem_write(layout["update"], b"\xff\x05"+struct.pack("<I", self.data+0x4000)+b"\xb8\xef\xbe\x00\x00\xba\xad\xde\x00\x00\xc3")
        m.mem_write(self.code, live.idle_thunk(self.code, mailbox, layout))
        for reg, value in ((UC_X86_REG_EAX, 0x111), (UC_X86_REG_EBX, 0x222), (UC_X86_REG_ECX, 0x333),
                           (UC_X86_REG_EDX, 0x444), (UC_X86_REG_ESI, 0x555), (UC_X86_REG_EDI, 0x666),
                           (UC_X86_REG_EBP, self.stack+0x2800), (UC_X86_REG_ESP, self.stack+0x2000)):
            m.reg_write(reg, value)
        return m, mailbox, layout

    def run_code(self, m, layout):
        end = layout["idle"]+len(bytes.fromhex(layout["original"]))
        m.emu_start(self.code, end, count=100000)
        self.assertEqual(m.reg_read(UC_X86_REG_EIP), end)

    def test_actual_native_idle_prologue_replayed_with_original_frame(self):
        target = self.data+0x5000
        m, mailbox, layout = self.make([(target, 100, 200, 4)], original="558bec83c4f0")
        m.mem_write(target, struct.pack("<I", 100))
        self.run_code(m, layout)
        self.assertEqual(m.reg_read(UC_X86_REG_EBP), self.stack+0x2000-4)
        self.assertEqual(m.reg_read(UC_X86_REG_ESP), self.stack+0x2000-20)
        self.assertEqual(m.reg_read(UC_X86_REG_EDX), 0x444)
        self.assertEqual(struct.unpack("<I", m.mem_read(self.stack+0x2000-4, 4))[0], self.stack+0x2800)

    def test_scalar_and_boolean_transaction_preserves_neighbors_and_refreshes(self):
        target = self.data+0x5000
        m, mailbox, layout = self.make([(target, 100, 200000, 4), (target+5, 1, 0, 1)])
        m.mem_write(target, struct.pack("<I", 100)+b"\xaa\x01\xbb\xcc")
        self.run_code(m, layout)
        self.assertEqual(m.mem_read(target, 8), struct.pack("<I", 200000)+b"\xaa\x00\xbb\xcc")
        self.assertEqual(struct.unpack("<I", m.mem_read(mailbox, 4))[0], 2)
        self.assertEqual(struct.unpack("<I", m.mem_read(self.data+0x4000, 4))[0], 1)
        for reg, value in ((UC_X86_REG_EAX, 0x111), (UC_X86_REG_EBX, 0x222), (UC_X86_REG_ECX, 0x333),
                           (UC_X86_REG_EDX, 0), (UC_X86_REG_ESI, 0x555), (UC_X86_REG_EDI, 0x666),
                           (UC_X86_REG_EBP, self.stack+0x2800), (UC_X86_REG_ESP, self.stack+0x2000-28)):
            self.assertEqual(m.reg_read(reg), value)

    def test_stale_second_value_cancels_every_write(self):
        target = self.data+0x5000
        m, mailbox, layout = self.make([(target, 100, 200, 4), (target+4, 10, 20, 4)])
        m.mem_write(target, struct.pack("<II", 100, 11))
        self.run_code(m, layout)
        self.assertEqual(m.mem_read(target, 8), struct.pack("<II", 100, 11))
        self.assertEqual(struct.unpack("<I", m.mem_read(mailbox, 4))[0], 4)
        self.assertEqual(struct.unpack("<I", m.mem_read(self.data+0x4000, 4))[0], 0)

    def test_wrong_session_zero_count_and_invalid_width_rejected(self):
        cases = [([], {}), ([(self.data+0x5000, 0, 1, 2)], {}),
                 ([(self.data+0x5000, 0, 1, 4)], {"expected_main": self.data+0x1100}),
                 ([(self.data+0x5000, 0, 1, 4)], {"expected_player": self.data+0x2100})]
        for rows, kwargs in cases:
            m, mailbox, layout = self.make(rows, **kwargs)
            self.run_code(m, layout)
            self.assertEqual(struct.unpack("<I", m.mem_read(mailbox, 4))[0], 4)
            self.assertEqual(m.mem_read(self.data+0x5000, 4), b"\0"*4)

    def test_pending_inactive_request_does_not_execute_again(self):
        for status in (0, 2, 3, 4):
            m, mailbox, layout = self.make([(self.data+0x5000, 0, 1, 4)], status=status)
            self.run_code(m, layout)
            self.assertEqual(m.mem_read(self.data+0x5000, 4), b"\0"*4)
            self.assertEqual(struct.unpack("<I", m.mem_read(mailbox, 4))[0], status)

    def test_maximum_transaction_and_overflow_guard(self):
        for count in (24, 25):
            rows = [(self.data+0x5000+index*4, 0, index+1, 4) for index in range(count)]
            m, mailbox, layout = self.make(rows)
            self.run_code(m, layout)
            self.assertEqual(struct.unpack("<I", m.mem_read(mailbox, 4))[0], 2 if count == 24 else 4)

    def test_bulk_pool_is_atomic_and_preserves_companion_state(self):
        target = self.data+0x30000
        rows = [(target+i*4, 0, i+1, 4) for i in range(1000)]
        for stale in (False, True):
            vm, mailbox, layout = self.make(rows, bulk=True)
            # First word is an actual callback pointer, not opaque data.
            vm.mem_write(self.code+0x950, b"\xc3")
            reserved = struct.pack("<I", self.code+0x950)+b"unchanged submarine / reveal state"
            vm.mem_write(mailbox+0x700, reserved)
            if stale: vm.mem_write(target+999*4, struct.pack("<I", 99))
            self.run_code(vm, layout)
            self.assertEqual(bytes(vm.mem_read(mailbox+0x700, len(reserved))), reserved)
            self.assertEqual(int.from_bytes(vm.mem_read(mailbox, 4), "little"), 4 if stale else 2)
            self.assertEqual(int.from_bytes(vm.mem_read(target, 4), "little"), 0 if stale else 1)
            self.assertEqual(int.from_bytes(vm.mem_read(target+999*4, 4), "little"), 99 if stale else 1000)

    def test_environment_callback_runs_after_commit_and_also_on_idle(self):
        target,observed=self.data+0x5000,self.data+0x5010
        for status in (0,1):
            vm,mailbox,layout=self.make([(target,0,1,4)],status=status)
            layout["environment_sync"]=self.code+0xa00
            # The fixed native helper must see the newly committed setting.
            vm.mem_write(layout["environment_sync"],b"\xa1"+struct.pack("<I",target)+b"\xa3"+struct.pack("<I",observed)+b"\xc3")
            vm.mem_write(self.code,live.idle_thunk(self.code,mailbox,layout))
            self.run_code(vm,layout)
            self.assertEqual(int.from_bytes(vm.mem_read(observed,4),"little"),status)
            self.assertEqual(vm.reg_read(UC_X86_REG_EAX),0x111)


class LegacyYearTests(unittest.TestCase):
    def test_all_start_years_use_previous_design_year_and_preserve_flags(self):
        for year in (1890, 1900, 1920, 1935):
            m = Uc(UC_ARCH_X86, UC_MODE_32)
            for addr in (0x100000, 0x200000, 0x300000): m.mem_map(addr, 0x1000)
            m.mem_write(0x100000, legacy_fleet.year_thunk(0x100000, 0x200000, 0x100800))
            m.mem_write(0x200000, struct.pack("<I", 0x200100))
            m.mem_write(0x200100, struct.pack("<I", year))
            m.reg_write(UC_X86_REG_EAX, 0x200200); m.reg_write(UC_X86_REG_EDX, 0x1234)
            m.reg_write(UC_X86_REG_ESP, 0x300800); m.reg_write(UC_X86_REG_EFLAGS, 0x247)
            m.emu_start(0x100000, 0x100800)
            self.assertEqual(struct.unpack("<I", m.mem_read(0x200200, 4))[0], year-1)
            self.assertEqual(m.reg_read(UC_X86_REG_EDX), 0x1234)
            self.assertEqual(m.reg_read(UC_X86_REG_ESP), 0x300800)
            self.assertEqual(m.reg_read(UC_X86_REG_EFLAGS), 0x247)


class LaterAdapterDiscoveryTests(unittest.TestCase):
    def test_adapters_after_live_cheats_discover_from_unhooked_code(self):
        # 2026-11-04 launch: vls-cells ran discover() on code already carrying
        # live-cheats' idle hook and every Play with mods launch stopped there.
        import json, tempfile
        base = 0x301000; blob = (Path(__file__).parent/"native-designer-inspection.text.bin").read_bytes()
        layout = live.discover(blob, base); idle = layout["idle"]
        hook = b"\xe9"+struct.pack("<i", 0x20000000-idle-5)+b"\x90"
        hooked = bytearray(blob); hooked[idle-base:idle-base+len(hook)] = hook
        with self.assertRaises(ValueError): live.discover(bytes(hooked), base)
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp)/"live_cheats_report.json"
            report.write_text(json.dumps({"pid": 7, "base": 0x300000, "attached": True, "patch": {
                "address": idle, "original": layout["original"], "replacement": hook.hex()}}), encoding="utf-8")
            current = {7: True}
            with patch.object(live, "REPORT", report), patch.object(live.rt, "module_info", return_value=(0x300000, 0)), \
                    patch.object(live.rt, "text_section", return_value=(base, bytes(hooked))), \
                    patch.object(live.rt, "report_is_current", lambda path, pid: current.get(pid, False)):
                module, text_base, clean = live.unhooked_text(7, None)
                self.assertEqual(live.unhooked_text(8, None)[2], bytes(hooked))   # another session's report is ignored
                current[7] = False   # same PID and base, but written before this process started
                self.assertEqual(live.unhooked_text(7, None)[2], bytes(hooked))
        self.assertEqual((module, text_base, clean), (0x300000, base, blob))
        self.assertEqual(live.discover(clean, base)["idle"], idle)


if __name__ == "__main__": unittest.main(verbosity=2)

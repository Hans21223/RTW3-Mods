"""Framework tests with simulated memory. No game, campaign or real hooks used."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/"CampaignOverhaul"))
import modern_research as modern
import runtime_registry as registry
import runtime_host as host
import weekly_runtime as rt


class RegistryTests(unittest.TestCase):
    def test_every_adapter_module_imports_first_in_a_fresh_game_session(self):
        # 2026-11-04: an import cycle only failed when campaign_security loaded first,
        # which is the launch order; tests that imported modern_research first passed.
        import subprocess
        folder = Path(registry.__file__).parent
        for module in sorted({a.module for a in registry.REGISTRY.values()} | {"live_cheats", "research_cheats"}):
            with self.subTest(module=module):
                result = subprocess.run([sys.executable, "-c", "import "+module], cwd=folder, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr[-400:])

    def test_order_is_independent_of_checkbox_order(self):
        selected = list(reversed(registry.REGISTRY))
        order = [item["adapter"] for item in registry.plan(selected)]
        self.assertEqual(order, list(registry.REGISTRY))

    def test_dependency_is_presence_not_attachment_order(self):
        self.assertEqual([s["adapter"] for s in registry.plan(["live-cheats", "campaign-security"])],
                         ["campaign-security", "live-cheats"])
        with self.assertRaisesRegex(ValueError, "requires"):
            registry.plan(["campaign-security"])

    def test_cycles_rejected(self):
        specs = {"a": registry.Adapter("a", "a", after=("b",)), "b": registry.Adapter("b", "b", after=("a",))}
        with self.assertRaisesRegex(ValueError, "cycle"):
            registry.plan(["b", "a"], registry=specs)

    def test_unknown_duplicate_and_unselected_settings_rejected(self):
        for selected, settings in [(["arbitrary.py"], {}), (["fair-ai", "fair-ai"], {}), ([], {"fair-ai": {}})]:
            with self.assertRaises(ValueError):
                registry.plan(selected, settings)

    def test_direct_launcher_settings_have_same_bounds_as_packages(self):
        for values in ({"days": True}, {"days": 29}, {"module": "evil"}, []):
            with self.assertRaises(ValueError):
                registry.validate_settings("calendar-days", values)
        with self.assertRaises(ValueError):
            registry.validate_settings("timeline-2030", {"end_year": 2030, "cutoff_year": 2030})

    def test_invocation_routes_only_reviewed_callables_and_own_settings(self):
        module = Mock()
        with patch.object(registry.importlib, "import_module", return_value=module) as load:
            registry.invoke("calendar-days", {"days": 14}, 55)
            module.attach.assert_called_with(days=14)
            registry.invoke("torpedo-initiative", {"roll": 50}, 55)
            module.attach.assert_called_with("torpedo-initiative", settings={"roll": 50})
            registry.invoke("battle-ai", {"contact_memory_minutes": 15}, 55)
            module.attach.assert_called_with(settings={"contact_memory_minutes": 15})
            registry.invoke("in-game-submarines", {}, 55)
            module.attach.assert_called_with(pid=55)
            registry.invoke("week-display", {}, 55)
            module.attach.assert_called_with()
            before = load.call_count
            with self.assertRaises(ValueError):
                registry.invoke("some.package", {}, 55)
            self.assertEqual(load.call_count, before)


class Memory:
    def __init__(self):
        self.data = bytearray(512)
        self.writes = []

    def read(self, handle, address, size):
        return bytes(self.data[address-0x1000:address-0x1000+size])

    def write(self, handle, address, original, replacement):
        if self.read(handle, address, len(original)) != original:
            raise ValueError("Changed simulated code")
        self.writes.append(address)
        self.data[address-0x1000:address-0x1000+len(original)] = replacement


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.memory = Memory()
        self.ledger = host.HookLedger(self.memory.write, self.memory.read)
        self.ledger.owner = "first"

    def test_cross_owner_partial_overlap_rejected_before_write(self):
        self.ledger.write(1, 0x1010, b"\0"*4, b"abcd")
        self.ledger.owner = "second"
        with self.assertRaisesRegex(ValueError, "second overlaps first"):
            self.ledger.write(2, 0x1013, b"d\0", b"ef")
        self.assertEqual(self.memory.writes, [0x1010])
        self.assertEqual(self.memory.read(1, 0x1010, 5), b"abcd\0")

    def test_adjacent_hooks_and_exact_owner_rollback(self):
        self.ledger.write(1, 0x1010, b"\0"*4, b"abcd")
        self.ledger.write(1, 0x1014, b"\0", b"e")
        self.ledger.write(1, 0x1010, b"abcd", b"\0"*4)
        self.assertEqual([h["address"] for h in self.ledger.hooks], [0x1014])

    def test_other_owner_cannot_undo_or_chain_hook(self):
        self.ledger.write(1, 0x1010, b"\0", b"a")
        self.ledger.owner = "second"
        for before, after in [(b"a", b"\0"), (b"a", b"b")]:
            with self.assertRaisesRegex(ValueError, "conflict"):
                self.ledger.write(1, 0x1010, before, after)
        self.assertEqual(len(self.memory.writes), 1)

    def test_invalid_ranges_and_readback_failure(self):
        for address, before, after in [(0, b"a", b"b"), (0xffffffff, b"aa", b"bb"), (0x1010, b"", b""), (0x1010, b"a", b"bb")]:
            with self.assertRaises(ValueError):
                self.ledger.write(1, address, before, after)
        ledger = host.HookLedger(Mock(), lambda *args: b"wrong")
        ledger.owner = "first"
        with self.assertRaisesRegex(ValueError, "readback"):
            ledger.write(1, 0x1010, b"\0", b"a")
        self.assertEqual(ledger.hooks[0]["state"], "uncertain")


class HostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/"report.json"
        self.identity = {"pid": 55, "base": 0x300000, "path": "test.exe", "created_filetime": 1234}
        self.memory = Memory()

    def tearDown(self):
        self.temp.cleanup()

    def run_host(self, invoker, selected=("fair-ai", "week-display"), **kwargs):
        with patch.object(rt, "write_code", self.memory.write), patch.object(rt, "read", self.memory.read):
            return host.run(selected, {}, 55, invoker=invoker,
                            session_reader=kwargs.pop("session_reader", lambda pid: self.identity),
                            verifier=kwargs.pop("verifier", lambda identity, hooks: []), report_path=self.path, **kwargs)

    def test_one_host_writes_owned_hooks_and_records_timings(self):
        calls = []
        def invoke(ident, settings, pid):
            rt.write_code(1, 0x1010+len(calls), b"\0", b"a")
            calls.append(ident)
            return {"attached": True, "pid": pid}
        result = self.run_host(invoke)
        self.assertTrue(result["ok"])
        self.assertEqual(result["hooks_verified"], 2)
        self.assertEqual([h["owner"] for h in result["hooks"]], calls)
        self.assertTrue(all(a["elapsed_ms"] >= 0 for a in result["adapters"]))
        self.assertEqual(json.loads(self.path.read_text()), result)

    def test_failed_adapter_stops_following_mods_and_preserves_honest_partial_state(self):
        def invoke(ident, settings, pid):
            rt.write_code(1, 0x1010, b"\0", b"a")
            return {"attached": True}
        result = self.run_host(invoke, selected=("fair-ai", "week-display", "legacy-fleet"))
        self.assertFalse(result["ok"])
        self.assertTrue(result["requires_restart"])
        self.assertEqual([a["state"] for a in result["adapters"]], ["loaded", "failed"])
        self.assertEqual(len(result["hooks"]), 1)
        self.assertIn("conflict", result["error"])

    def test_session_change_refuses_next_adapter(self):
        identities = iter([self.identity, dict(self.identity, created_filetime=9999)])
        invoke = Mock()
        result = self.run_host(invoke, session_reader=lambda pid: next(identities))
        self.assertFalse(result["ok"])
        invoke.assert_not_called()

    def test_final_readback_mismatch_and_failed_result_rejected(self):
        result = self.run_host(lambda *args: {"attached": True}, verifier=lambda *args: [{"address": 0x1010}])
        self.assertFalse(result["ok"])
        self.assertIn("readback", result["error"])
        result = self.run_host(lambda *args: {"ok": False})
        self.assertFalse(result["ok"])
        self.assertIn("confirm", result["error"])

    def test_diagnostics_read_only_current_and_stale(self):
        self.run_host(lambda *args: {"attached": True})
        verifier = Mock(return_value=[])
        result = host.diagnostics(["fair-ai", "week-display"], {}, report_path=self.path,
                                  session_reader=lambda pid: self.identity, verifier=verifier)
        self.assertEqual(result["session_state"], "current")
        verifier.assert_called_once()
        verifier.reset_mock()
        result = host.diagnostics(["fair-ai"], {}, report_path=self.path,
                                  session_reader=lambda pid: dict(self.identity, created_filetime=9999), verifier=verifier)
        self.assertEqual(result["session_state"], "stale")
        self.assertTrue(result["warnings"])
        verifier.assert_not_called()

    def test_ended_session_and_no_report_have_no_live_checks(self):
        self.assertEqual(host.diagnostics([], {}, report_path=self.path)["session_state"], "no-report")
        self.run_host(lambda *args: {"attached": True})
        verifier = Mock()
        result = host.diagnostics([], {}, report_path=self.path,
                                  session_reader=Mock(side_effect=ValueError("ended")), verifier=verifier)
        self.assertEqual(result["session_state"], "ended-or-unavailable")
        verifier.assert_not_called()


class MetadataCacheTests(unittest.TestCase):
    def test_only_immutable_file_metadata_is_cached_and_changes_invalidate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"RTW3.exe"
            path.write_bytes(b"first")
            modern._cached_relocations.cache_clear()
            with patch.object(rt, "GAME", Path(folder)), patch.object(modern, "_parse_relocations", return_value=(1, 2)) as parse:
                self.assertEqual(modern.text_relocations(), (1, 2))
                self.assertIs(modern.text_relocations(), modern.text_relocations())
                self.assertEqual(parse.call_count, 1)
                path.write_bytes(b"different size")
                modern.text_relocations()
                self.assertEqual(parse.call_count, 2)
            modern._cached_relocations.cache_clear()


class ModuleSnapshotTests(unittest.TestCase):
    def test_transient_module_snapshot_retries_and_closes_successful_handle(self):
        kernel = Mock()
        kernel.CreateToolhelp32Snapshot.side_effect = [rt.c.c_void_p(-1).value]*2 + [77]
        def first(snapshot, entry):
            entry._obj.szModule = "RTW3.exe"
            entry._obj.modBaseAddr = 0x300000
            entry._obj.modBaseSize = 0x100000
            return True
        kernel.Module32FirstW.side_effect = first
        with patch.object(rt, "K", kernel), patch.object(rt.c, "get_last_error", return_value=24), patch.object(rt.time, "sleep") as sleep:
            self.assertEqual(rt.module_info(55), (0x300000, 0x100000))
        self.assertEqual(sleep.call_count, 2)
        kernel.CloseHandle.assert_called_once_with(77)

    def test_persistent_and_nontransient_errors_are_bounded(self):
        for error, attempts in [(24, 20), (5, 1)]:
            kernel = Mock()
            kernel.CreateToolhelp32Snapshot.return_value = rt.c.c_void_p(-1).value
            with patch.object(rt, "K", kernel), patch.object(rt.c, "get_last_error", return_value=error), patch.object(rt.time, "sleep"):
                with self.assertRaises(OSError):
                    rt.module_info(55)
            self.assertEqual(kernel.CreateToolhelp32Snapshot.call_count, attempts)
            kernel.CloseHandle.assert_not_called()


class SessionStampTests(unittest.TestCase):
    def test_report_written_before_process_start_is_stale(self):
        # A recycled PID at the same base must not revive an older adapter report.
        import os
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp)/"adapter_report.json"; report.write_text("{}")
            written = 1_800_000_000*10**9; os.utime(report, ns=(written, written))
            filetime = written//100+116444736000000000
            for created, current in ((filetime-1, True), (filetime, True), (filetime+1, False)):
                with patch.object(rt, "process_created", return_value=created):
                    self.assertEqual(rt.report_is_current(report, 55), current)

    @unittest.skipUnless(sys.platform == "win32", "Windows process times")
    def test_real_process_start_precedes_a_report_written_now(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp)/"new_report.json"; report.write_text("{}")
            self.assertTrue(rt.report_is_current(report, os.getpid()))


if __name__ == "__main__":
    unittest.main()

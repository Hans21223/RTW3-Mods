"""Offline tests for mod.json runtime settings. No running game or save is touched.

Patches are generated from the retained unpacked code of the supported build,
and the changed instructions run in Unicorn.
"""
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
import ai_rules
import hull_rules
import large_hulls
import launch
import timeline_2030 as timeline
import weekly_runtime as rt
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESP

CODE, DATA, STACK = 0x100000, 0x200000, 0x280000


class RetainedBuildSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.base = json.loads((HERE/"native-designer-inspection.json").read_text())["text_base"]

    def test_calendar_turn_adds_the_configured_days(self):
        block = rt.turn_blocks(self.blob, self.base)[0]
        self.assertIn(b"\x6a\x07", rt.replacement(block))
        for days in (1, 7, 14, 28):
            code = rt.replacement(block, days)
            self.assertEqual(len(code), block["length"])
            vm = Uc(UC_ARCH_X86, UC_MODE_32)
            vm.mem_map(CODE, 0x1000); vm.mem_map(STACK, 0x1000)
            vm.mem_map(block["clock"] & ~0xfff, 0x2000)
            vm.mem_write(CODE, code)
            vm.mem_write(block["clock"], struct.pack("<d", 45000.0))
            vm.reg_write(UC_X86_REG_ESP, STACK+0x800)
            vm.emu_start(CODE, CODE+len(code))
            self.assertEqual(struct.unpack("<d", vm.mem_read(block["clock"], 8))[0], 45000.0+days)
            self.assertEqual(vm.reg_read(UC_X86_REG_ESP), STACK+0x800)
        for days in (0, 29, 128):
            with self.assertRaises(ValueError):
                rt.replacement(block, days)

    def run_gate(self, code, year):
        # Same harness as test_timeline_2030: EBX is one when the native JLE keeps playing.
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        vm.mem_map(CODE, 0x1000)
        sequence = code+b"\x7e\x07\xbb\x00\x00\x00\x00\xeb\x05\xbb\x01\x00\x00\x00"
        vm.mem_write(CODE, sequence)
        vm.reg_write(UC_X86_REG_EAX, year)
        vm.emu_start(CODE, CODE+len(sequence))
        return vm.reg_read(UC_X86_REG_EBX)

    def test_timeline_end_offer_and_cutoff_years(self):
        plans, _ = timeline.discover(self.blob, self.base, 1950, 1960)
        gate = bytes.fromhex(plans[0]["replacement"])
        for year, playable in ((1890, 1), (1950, 1), (1959, 1), (1960, 0), (2030, 0)):
            self.assertEqual(self.run_gate(gate, year), playable, year)
        self.assertEqual(bytes.fromhex(plans[1]["replacement"]), struct.pack("<I", 1950))
        self.assertIn("end of year 1950", bytes.fromhex(plans[2]["replacement"]).decode("utf-16-le"))
        self.assertIn("hard cutoff at 1960", bytes.fromhex(plans[3]["replacement"]).decode("utf-16-le"))
        default, _ = timeline.discover(self.blob, self.base)
        self.assertEqual(bytes.fromhex(default[0]["replacement"]), b"\x3d"+struct.pack("<I", 2030)+b"\x90"*3)
        for years in ((2030, 2030), (2040, 2031), (1889, 1950), (2030, 10000)):
            with self.assertRaises(ValueError):
                timeline.discover(self.blob, self.base, *years)

    def test_hull_limits_reach_every_generated_check(self):
        limits = large_hulls.hull_limits({"max_tons": 280000, "dd_tons": 15000, "cl_tons": 25000, "ke_tons": 8000,
                                          "cvl_tons": 45000, "cv_tons": 250000, "cvl_aircraft": 127})
        plans, strings = hull_rules.class_patches(self.blob, self.base, 0x10000000, limits)
        patched = {p["label"]: bytes.fromhex(p["replacement"]) for p in plans}
        for label, value in (("DD class ceiling", 15000), ("DD research hard maximum", 15000), ("Special CL ceiling", 25000),
                             ("CL 12000 ceiling", 25000), ("KE class ceiling", 8000), ("CVL class ceiling", 45000),
                             ("CA class ceiling", hull_rules.LIMITS["CA"])):
            self.assertTrue(patched[label].endswith(struct.pack("<I", value)), label)
        self.assertEqual(patched["CVL class aircraft"][-1], 127)
        self.assertEqual(patched["Designer CV limit 2"], b"\xb8"+struct.pack("<I", 250000))
        for message in ("A DD must be no larger than 15000 tons", "A CVL must carry 4 to 127 aircraft and displace no more than 45000 tons."):
            self.assertIn(message.encode("utf-16-le"), strings)
        engine, *_ = hull_rules.machinery_patches(self.blob, self.base, 0x10000000, limits)
        maximum = next(p for p in engine if p["label"] == "Machinery hard maximum")
        self.assertTrue(bytes.fromhex(maximum["replacement"]).endswith(struct.pack("<I", 280000)))
        interpolation = hull_rules.machinery_patches(self.blob, self.base, 0x10000000, limits)[3]
        self.assertEqual(interpolation[:5], b"\x3d"+struct.pack("<I", 280))
        rows = b"".join(struct.pack("<25i", *([k]*18+[-1]*5+[0]*2)) for k in range(1, 91))
        table = hull_rules.extended_table(rows, limits["overall"])
        # Row 281 is the interpolation endpoint; the table must end before the hook strings.
        self.assertEqual(len(table), 282*100)
        self.assertLessEqual(0x1000+len(table), 0x8000)
        self.assertEqual(large_hulls.hull_limits({}), hull_rules.LIMITS)
        for bad in ({"cvl_aircraft": 128}, {"max_tons": 290000}, {"speed": 30}):
            with self.assertRaises(ValueError):
                large_hulls.hull_limits(bad)

    def test_class_suggestion_follows_configured_ceilings(self):
        limits = large_hulls.hull_limits({"dd_tons": 15000, "cl_tons": 25000, "ke_tons": 8000, "cvl_tons": 45000, "cvl_aircraft": 127})
        original = CODE+0x800
        cases = ((9, 15000, 0, 9), (9, 15001, 0, 17), (4, 25000, 0, 4), (4, 25001, 0, 17), (10, 8000, 0, 10),
                 (10, 8001, 0, 17), (6, 45000, 127, 6), (6, 45001, 50, 17), (6, 40000, 128, 17))
        for kind, tons, aircraft, expected in cases:
            vm = Uc(UC_ARCH_X86, UC_MODE_32)
            for address in (CODE, DATA, STACK):
                vm.mem_map(address, 0x1000)
            vm.mem_write(CODE, hull_rules.classification_thunk(CODE, original, limits))
            vm.mem_write(original, b"\xb8\x11\x00\x00\x00\xc3")
            vm.mem_write(DATA+0x2c, struct.pack("<I", tons))
            vm.mem_write(DATA+0x9d3, bytes([kind]))
            vm.mem_write(DATA+0x9e0, struct.pack("<I", aircraft))
            vm.mem_write(STACK+0x800, struct.pack("<I", CODE+0xf00))
            vm.reg_write(UC_X86_REG_EAX, DATA); vm.reg_write(UC_X86_REG_EDX, 0xbeef); vm.reg_write(UC_X86_REG_ECX, 0xcafe)
            vm.reg_write(UC_X86_REG_ESP, STACK+0x800)
            vm.emu_start(CODE, CODE+0xf00, count=1000)
            self.assertEqual(vm.reg_read(UC_X86_REG_EAX), expected, (kind, tons, aircraft))
            self.assertEqual((vm.reg_read(UC_X86_REG_EDX), vm.reg_read(UC_X86_REG_ECX)), (0xbeef, 0xcafe))

    def test_torpedo_assessment_roll(self):
        plans, details = ai_rules.discover(self.blob, self.base, "torpedo-initiative", {"roll": 50})
        self.assertEqual([p["replacement"] for p in plans], ["32", "32"])
        self.assertEqual(details["assessment_roll_after"], 50)
        for roll in (0, 256):
            with self.assertRaises(ValueError):
                ai_rules.torpedo_plans(self.blob, self.base, roll)


class LaunchForwardingTests(unittest.TestCase):
    def test_each_adapter_receives_only_its_own_settings(self):
        settings = {"calendar-days": {"days": 14}, "torpedo-initiative": {"roll": 50},
                    "large-hulls": {"max_tons": 250000}, "week-display": {},
                    "campaign-qol": {"max_active_ships": 500, "min_procurement_days": 30},
                    "battle-ai": {"contact_memory_minutes": 15},
                    "research-traits": {"research_advantage_bonus_percent": 75, "technical_excellence_bonus_percent": 30}}
        game = Mock(pid=4321)
        game.poll.return_value = None
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return Mock(returncode=0)
        host = Mock(return_value={"ok": True, "elapsed_ms": 1, "hooks_verified": 0, "adapters": []})
        argv = ["launch.py", "--no-dialog", "--weekly", "--torpedo-initiative", "--large-hulls", "--week-display", "--campaign-qol", "--campaign-security", "--battle-ai", "--research-traits", "--live-cheats",
                "--settings", json.dumps(settings)]
        with patch.object(launch.campaign_mod, "state", return_value={"upgrade": {"complete": True, "steam_exe_sha256": "x"}}), \
                patch.object(launch.campaign_mod, "digest", return_value="x"), \
                patch.object(launch.weekly_runtime, "configure_api"), \
                patch.object(launch.weekly_runtime, "process_candidates", return_value=[]), \
                patch.object(launch, "steam_path", return_value=Path(sys.executable)), \
                patch.object(launch.subprocess, "Popen", return_value=game), \
                patch.object(launch.runtime_host, "wait_session"), \
                patch.object(launch.runtime_host, "run", host), \
                patch.object(sys, "argv", argv):
            self.assertEqual(launch.main(), 0)
        selected, forwarded, pid = host.call_args.args
        self.assertEqual(forwarded, settings)
        self.assertEqual(pid, 4321)
        order = [step["adapter"] for step in launch.runtime_registry.plan(selected, forwarded)]
        chain = ["campaign-security", "campaign-qol", "battle-ai", "research-traits", "live-cheats"]
        self.assertEqual([ident for ident in order if ident in chain], chain)
        self.assertIn("calendar-days", selected)


if __name__ == "__main__":
    unittest.main(verbosity=2)

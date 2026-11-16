"""Isolated loader regression tests. Does not touch the real game's files."""
import contextlib
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import mod_loader as loader


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rtw-manager-test-", dir=loader.HERE)
        self.root = Path(self.temp.name)
        self.game = self.root / "game"
        self.manager = self.game / "Mods" / "Manager"
        self.library = self.game / "Mods" / "Library"
        self.manager.mkdir(parents=True)
        self.library.mkdir(parents=True)
        (self.game / "Data").mkdir()
        (self.game / "RTW3.exe").write_bytes(b"unchanged-test-engine")
        (self.game / "Data" / "Tips.txt").write_bytes(b"original tips\r\n")
        self.patches = contextlib.ExitStack()
        self.patches.enter_context(patch.object(loader, "GAME", self.game))
        self.patches.enter_context(patch.object(loader, "HERE", self.manager))
        self.patches.enter_context(patch.object(loader, "LIBRARY", self.library))
        self.patches.enter_context(patch.object(loader, "STATE", self.manager / "state.json"))
        self.patches.enter_context(patch.object(loader, "running_games", return_value=[]))
        loader.write_json(loader.STATE, {"schema": 1, "enabled": [], "applied": {}, "originals": {}, "history": [], "game_sha256": loader.sha(self.game / "RTW3.exe"), "build": "test"})

    def tearDown(self):
        self.patches.close()
        self.temp.cleanup()

    def mod(self, ident, target="Data/Tips.txt", content=b"new tips\r\n", requires=None):
        folder = self.library / ident
        source = folder / "Files" / "payload.dat"
        source.parent.mkdir(parents=True)
        source.write_bytes(content)
        loader.write_json(folder / "mod.json", {"schema": 1, "id": ident, "name": ident, "version": "1.0.0", "description": "Test package", "kind": "data", "files": [{"source": "Files/payload.dat", "target": target}], "requires": requires or [], "conflicts": []})
        return folder

    def test_apply_restore_roundtrip(self):
        self.mod("first")
        original = (self.game / "Data/Tips.txt").read_bytes()
        loader.apply(["first"])
        self.assertEqual((self.game / "Data/Tips.txt").read_bytes(), b"new tips\r\n")
        loader.apply([])
        self.assertEqual((self.game / "Data/Tips.txt").read_bytes(), original)
        self.assertEqual(loader.load_state()["enabled"], [])

    def test_conflicting_files_block_before_writes(self):
        self.mod("first")
        self.mod("second", target="Data/TIPS.txt")
        with self.assertRaisesRegex(ValueError, "File conflict"):
            loader.apply(["first", "second"])
        self.assertEqual((self.game / "Data/Tips.txt").read_bytes(), b"original tips\r\n")
        self.assertEqual(loader.load_state()["enabled"], [])

    def test_missing_dependency_blocks(self):
        self.mod("first", requires=["absent"])
        with self.assertRaisesRegex(ValueError, "requires"):
            loader.apply(["first"])

    def test_manual_edits_are_preserved(self):
        self.mod("first")
        loader.apply(["first"])
        (self.game / "Data/Tips.txt").write_bytes(b"user's changes")
        with self.assertRaisesRegex(ValueError, "Untracked changes"):
            loader.apply([])
        self.assertEqual((self.game / "Data/Tips.txt").read_bytes(), b"user's changes")

    def test_added_file_is_recoverable_when_disabled(self):
        self.mod("first", target="Data/NewTable.dat")
        loader.apply(["first"])
        self.assertTrue((self.game / "Data/NewTable.dat").exists())
        loader.apply([])
        self.assertFalse((self.game / "Data/NewTable.dat").exists())
        self.assertTrue(list((self.manager / "backups").glob("*/removed-mod-files/Data/NewTable.dat")))

    def test_failed_install_restores_previous_bytes(self):
        folder = self.mod("first")
        (folder / "Files/other.dat").write_bytes(b"second payload")
        manifest = json.loads((folder / "mod.json").read_text())
        manifest["files"].append({"source": "Files/other.dat", "target": "Data/NewTable.dat"})
        loader.write_json(folder / "mod.json", manifest)
        normal_copy = loader.atomic_copy
        calls = []
        def fail_on_second(source, dest):
            calls.append(str(dest))
            if len(calls) == 2:
                raise OSError("simulated copy failure")
            normal_copy(source, dest)
        with patch.object(loader, "atomic_copy", side_effect=fail_on_second):
            with self.assertRaisesRegex(OSError, "simulated"):
                loader.apply(["first"])
        self.assertEqual((self.game / "Data/Tips.txt").read_bytes(), b"original tips\r\n")
        self.assertFalse((self.game / "Data/NewTable.dat").exists())
        self.assertEqual(loader.load_state()["enabled"], [])

    def test_zip_traversal_rejected(self):
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("../escaped.txt", "bad")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            loader.import_package(archive)
        self.assertFalse((self.manager / "escaped.txt").exists())

    def test_export_import_roundtrip_and_duplicate_id(self):
        folder = self.mod("first")
        archive = self.root / "first.zip"
        loader.export_package("first", archive)
        folder.rename(self.root / "archived-first")
        result = loader.import_package(archive)
        self.assertTrue(result["ok"])
        self.assertEqual((self.library / "first/Files/payload.dat").read_bytes(), b"new tips\r\n")
        with self.assertRaisesRegex(ValueError, "already exists"):
            loader.import_package(archive)

    def test_executable_replacement_blocked(self):
        self.mod("first", target="Data/plugin.dll")
        with self.assertRaisesRegex(ValueError, "Unsupported content"):
            loader.read_manifest(self.library / "first")

    def test_running_game_blocks_apply(self):
        self.mod("first")
        with patch.object(loader, "running_games", return_value=[{"pid": 123, "path": "RTW3.exe"}]):
            with self.assertRaisesRegex(ValueError, "Close RTW3"):
                loader.apply(["first"])

    def test_partial_copy_cleans_temp_and_preserves_destination(self):
        self.mod("first")
        source = self.library / "first/Files/payload.dat"
        dest = self.game / "Data/Tips.txt"
        original = dest.read_bytes()
        def interrupted_copy(src, temporary):
            temporary.write_bytes(b"partial bytes")
            raise OSError("disk write interrupted")
        with patch.object(loader.shutil, "copy2", side_effect=interrupted_copy):
            with self.assertRaisesRegex(OSError, "interrupted"):
                loader.atomic_copy(source, dest)
        self.assertEqual(dest.read_bytes(), original)
        self.assertFalse(dest.with_name(dest.name + ".rtwmod-tmp").exists())

    def runtime_mod(self, ident, adapter):
        folder = self.library / ident
        folder.mkdir()
        loader.write_json(folder / "mod.json", {"schema": 1, "id": ident, "name": ident, "version": "1.0", "description": "Runtime test", "kind": "runtime", "experimental": isinstance(adapter, dict) and adapter.get("adapter") == "calendar-days", "files": [], "requires": [], "conflicts": [], "runtime": adapter})

    def test_visual_and_hull_adapters_coexist_without_weekly_turns(self):
        self.runtime_mod("display", {"adapter": "week-display"})
        self.runtime_mod("hulls", {"adapter": "large-hulls", "max_tons": 200000})
        loader.apply(["display", "hulls"])
        class Result:
            returncode = 0
            stdout = "loaded"
            stderr = ""
        with patch.object(loader, "verify"), patch.object(loader.subprocess, "run", return_value=Result()) as command:
            response = loader.launch()
        arguments = command.call_args.args[0]
        self.assertIn("--week-display", arguments)
        self.assertIn("--large-hulls", arguments)
        self.assertNotIn("--weekly", arguments)
        self.assertIn("monthly turns", response["message"])

    def test_duplicate_runtime_adapter_is_blocked(self):
        self.runtime_mod("display-one", {"adapter": "week-display"})
        self.runtime_mod("display-two", {"adapter": "week-display"})
        with self.assertRaisesRegex(ValueError, "one mod per runtime"):
            loader.apply(["display-one", "display-two"])

    def test_experimental_hulls_require_acknowledgement_without_enabling_weekly(self):
        self.runtime_mod("hulls", {"adapter": "large-hulls", "max_tons": 200000})
        manifest_path = self.library / "hulls" / "mod.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["experimental"] = True
        loader.write_json(manifest_path, manifest)
        loader.apply(["hulls"])
        with patch.object(loader, "verify"), patch.object(loader.subprocess, "run") as command:
            with self.assertRaisesRegex(ValueError, "Experimental runtime"):
                loader.launch()
            command.assert_not_called()
            command.return_value.returncode = 0
            command.return_value.stdout = "loaded"
            result = loader.launch(accept_experimental=True)
            self.assertTrue(result["ok"])
            self.assertNotIn("--weekly", command.call_args.args[0])

    def test_live_and_legacy_adapters_route_without_accidental_weekly_mode(self):
        self.runtime_mod("live", {"adapter": "live-cheats"})
        self.runtime_mod("legacy", {"adapter": "legacy-fleet"})
        loader.apply(["live", "legacy"])
        with patch.object(loader, "verify"), patch.object(loader.subprocess, "run") as command:
            command.return_value.returncode = 0
            command.return_value.stdout = "loaded"
            loader.launch()
            args = command.call_args.args[0]
            self.assertIn("--live-cheats", args); self.assertIn("--legacy-fleet", args)
            self.assertNotIn("--weekly", args)

    def test_one_package_can_bundle_several_adapters(self):
        self.runtime_mod("era", [{"adapter": "timeline-2030", "end_year": 2050}, {"adapter": "live-cheats"}])
        loader.apply(["era"])
        with patch.object(loader, "verify"), patch.object(loader.subprocess, "run") as command:
            command.return_value.returncode = 0
            command.return_value.stdout = "loaded"
            loader.launch(accept_experimental=True)
            args = command.call_args.args[0]
            self.assertIn("--timeline-2030", args); self.assertIn("--live-cheats", args)
            self.assertEqual(json.loads(args[args.index("--settings")+1])["timeline-2030"], {"end_year": 2050})
        self.runtime_mod("cheats", {"adapter": "live-cheats"})
        with self.assertRaisesRegex(ValueError, "one mod per runtime adapter"):
            loader.resolve_plan(["era", "cheats"])
        for index, runtime in enumerate(([], [{"adapter": "live-cheats"}, {"adapter": "live-cheats"}],
                                         [{"adapter": "timeline-2030", "end_year": True}])):
            self.runtime_mod(f"bad-bundle-{index}", runtime)
            with self.assertRaises(ValueError):
                loader.read_manifest(self.library / f"bad-bundle-{index}")

    def test_timeline_adapter_routes_without_enabling_weekly_mode(self):
        self.runtime_mod("timeline", {"adapter": "timeline-2030"})
        loader.apply(["timeline"])
        with patch.object(loader, "verify"), patch.object(loader.subprocess, "run") as command:
            command.return_value.returncode = 0
            command.return_value.stdout = "loaded"
            loader.launch()
            self.assertIn("--timeline-2030", command.call_args.args[0])
            self.assertNotIn("--weekly", command.call_args.args[0])

    def test_in_game_submarines_routes_to_fixed_module_without_weekly(self):
        self.runtime_mod("submarine", {"adapter":"in-game-submarines"})
        self.runtime_mod("cheats", {"adapter":"live-cheats"})
        loader.apply(["submarine", "cheats"])
        with patch.object(loader,"verify"),patch.object(loader.subprocess,"run") as command:
            command.return_value.returncode=0;command.return_value.stdout="loaded"
            loader.launch()
            self.assertIn("--in-game-submarines",command.call_args.args[0]);self.assertNotIn("--weekly",command.call_args.args[0])

    def test_native_scratch_design_is_not_an_immutable_installation_file(self):
        import io
        import campaign_mod
        scratch = self.game/"Data"/"tmpShip.ttp"
        scratch.write_bytes(b"a user-created temporary design")
        # Custom starting designs: one replaced, one removed (2026-11-04 report).
        expected = {"RTW3.exe": loader.sha(self.game/"RTW3.exe"), "Data/tmpShip.ttp": "old-copy-hash", "Data/Tips.txt": loader.sha(self.game/"Data"/"Tips.txt"),
                    "Data/IDes/B0F0.tdf": "old-copy-hash", "Data/IDes/B1U1.tdf": "removed-file-hash"}
        state = {"upgrade": {"complete": True, "installed": expected, "backup": str(self.root/"backup")}}
        with patch.object(campaign_mod, "GAME", self.game), patch.object(campaign_mod, "state", return_value=state), contextlib.redirect_stdout(io.StringIO()):
            campaign_mod.verify()
            (self.game/"Data"/"Tips.txt").write_bytes(b"unexpected change")
            with self.assertRaisesRegex(ValueError, "Tips.txt"):
                campaign_mod.verify()

    def test_add_mod_turns_loose_game_files_into_a_sub_mod_that_wins_either_way(self):
        self.mod("base")                                        # supplies Data/Tips.txt
        source = self.root/"Faster tips"; source.mkdir()
        (source/"Tips.txt").write_bytes(b"sub tips\r\n")        # no folder: goes where the game keeps Tips.txt
        (source/"notes.md").write_text("how to")                 # not a game file
        answer = loader.add_package(source)
        self.assertIn("notes.md", answer["message"])
        manifest = json.loads((self.library/"faster-tips"/"mod.json").read_text())
        self.assertEqual((manifest["added"], manifest["overrides"], manifest["files"]),
                         (True, ["base"], [{"source": "Files/Data/Tips.txt", "target": "Data/Tips.txt"}]))
        for order in (["base", "faster-tips"], ["faster-tips", "base"]):
            loader.apply(order)
            self.assertEqual((self.game/"Data/Tips.txt").read_bytes(), b"sub tips\r\n", order)
        with self.assertRaisesRegex(ValueError, "already exists"):
            loader.add_package(source)
        with self.assertRaisesRegex(ValueError, "Turn the mod off"):
            loader.remove_package("faster-tips")
        with self.assertRaisesRegex(ValueError, "comes with the mods"):
            loader.remove_package("base")
        loader.apply(["base"])
        self.assertEqual((self.game/"Data/Tips.txt").read_bytes(), b"new tips\r\n")
        loader.remove_package("faster-tips")
        self.assertFalse((self.library/"faster-tips").exists())
        self.assertEqual(len(list((self.manager/"backups"/"removed-mods").iterdir())), 1)

    def test_add_mod_imports_packages_and_zipped_game_folders(self):
        package = self.root/"package.zip"
        with zipfile.ZipFile(package, "w") as z:
            z.writestr("pack/mod.json", json.dumps({"schema": 1, "id": "zipped", "name": "Zipped", "version": "2.0.0",
                       "description": "x", "kind": "data", "files": [{"source": "Files/a.dat", "target": "Data/a.dat"}]}))
            z.writestr("pack/Files/a.dat", b"a")
        loader.add_package(package)
        self.assertTrue(json.loads((self.library/"zipped"/"mod.json").read_text())["added"])
        loose = self.root/"Loose.zip"
        with zipfile.ZipFile(loose, "w") as z:
            z.writestr("Loose/Data/b.dat", b"b")
        loader.add_package(loose)
        self.assertEqual(json.loads((self.library/"loose"/"mod.json").read_text())["files"],
                         [{"source": "Files/Data/b.dat", "target": "Data/b.dat"}])
        nothing = self.root/"readme.txt"; nothing.write_text("hi")
        with self.assertRaisesRegex(ValueError, "Nothing in it"):
            loader.add_package(nothing)

    def test_release_install_bootstraps_only_the_supported_untouched_game(self):
        import campaign_mod
        import modern_tree
        research = self.game/"Data"/"ResearchAreas3.dat"
        research.write_bytes(b"original research table")
        loader.STATE.unlink()
        with patch.object(campaign_mod, "state", return_value={}), \
             patch.object(modern_tree, "VANILLA_SHA256", loader.sha(research)):
            with self.assertRaisesRegex(ValueError, "1.01.44"):
                loader.bootstrap()
            with patch.object(loader, "RELEASE_EXE", loader.sha(self.game/"RTW3.exe")):
                research.write_bytes(b"time-stretched research table")
                with self.assertRaisesRegex(ValueError, "ResearchAreas3.dat"):
                    loader.bootstrap()
                self.assertFalse(loader.STATE.exists())
                research.write_bytes(b"original research table")
                self.assertEqual(loader.bootstrap()["enabled"], [])
                self.mod("first")
                loader.apply(["first"])
                self.assertEqual(loader.verify()["enabled"], ["first"])   # no Steam-copy record to check
                (self.game/"RTW3.exe").write_bytes(b"patched engine")
                with self.assertRaisesRegex(ValueError, "executable changed"):
                    loader.verify()

    def test_ai_mods_route_separately_and_require_experimental_acknowledgement(self):
        for ident in ("torpedo-initiative", "fair-ai", "detection-only-evasion"):
            self.runtime_mod(ident, {"adapter": ident})
            path = self.library/ident/"mod.json"
            manifest = json.loads(path.read_text())
            manifest["experimental"] = True
            loader.write_json(path, manifest)
        loader.apply(["torpedo-initiative", "fair-ai", "detection-only-evasion"])
        with patch.object(loader, "verify"), patch.object(loader.subprocess, "run") as command:
            with self.assertRaisesRegex(ValueError, "Experimental runtime"):
                loader.launch()
            command.assert_not_called()
            command.return_value.returncode = 0
            command.return_value.stdout = "loaded"
            loader.launch(accept_experimental=True)
            args = command.call_args.args[0]
            self.assertIn("--torpedo-initiative", args)
            self.assertIn("--fair-ai", args)
            self.assertIn("--detection-only-evasion", args)
            self.assertNotIn("--weekly", args)

    def test_runtime_staging_changes_selection_only_while_game_is_running(self):
        self.runtime_mod("live", {"adapter": "live-cheats"})
        before = (self.game/"Data"/"Tips.txt").read_bytes()
        with patch.object(loader, "running_games", return_value=[{"pid": 123, "path": str(self.game/"RTW3.exe")}]):
            result = loader.stage_runtime(["live"])
            self.assertTrue(result["status"]["runtime_restart_required"])
            self.assertEqual(loader.load_state()["enabled"], ["live"])
            self.assertEqual((self.game/"Data"/"Tips.txt").read_bytes(), before)
        self.mod("content")
        with self.assertRaisesRegex(ValueError, "Only file-free"):
            loader.stage_runtime(["content"])

    def test_runtime_settings_are_range_checked(self):
        cases = (({"adapter": "calendar-days", "days": 29}, "from 1 to 28"),
                 ({"adapter": "large-hulls", "speed": 40}, "Unknown large-hulls setting"),
                 ({"adapter": "timeline-2030", "end_year": True}, "whole number"),
                 ({"adapter": "torpedo-initiative", "roll": 50.5}, "whole number"),
                 ({"adapter": "fair-ai", "roll": 50}, "Unknown fair-ai setting"),
                 ({"adapter": "unreviewed"}, "Unknown runtime adapter"),
                 ({"adapter": "campaign-qol", "max_active_ships": 49}, "from 50 to 10000"),
                 ({"adapter": "campaign-qol", "max_building_ships": 0}, "from 1 to 1000"),
                 ({"adapter": "campaign-qol", "min_procurement_days": True}, "whole number"),
                 ({"adapter": "battle-ai", "contact_memory_minutes": 0}, "from 1 to 60"),
                 ({"adapter": "battle-ai", "memory_radius_yards": True}, "whole number"),
                 ({"adapter": "research-traits", "research_advantage_bonus_percent": 301}, "from 0 to 300"),
                 ({"adapter": "research-traits", "technical_excellence_bonus_percent": False}, "whole number"))
        for index, (runtime, error) in enumerate(cases):
            with self.subTest(runtime=runtime):
                self.runtime_mod(f"bad-{index}", runtime)
                with self.assertRaisesRegex(ValueError, error):
                    loader.read_manifest(self.library / f"bad-{index}")

    def test_runtime_settings_reach_launch_and_calendar_message(self):
        self.runtime_mod("fortnight", {"adapter": "calendar-days", "days": 14})
        self.runtime_mod("hulls", {"adapter": "large-hulls", "max_tons": 250000, "cvl_aircraft": 100})
        self.runtime_mod("display", {"adapter": "week-display"})
        loader.apply(["fortnight", "hulls", "display"])
        with patch.object(loader, "verify"), patch.object(loader.subprocess, "run") as command:
            command.return_value.returncode = 0
            command.return_value.stdout = "loaded"
            result = loader.launch(accept_experimental=True)
        args = command.call_args.args[0]
        for flag in ("--weekly", "--large-hulls", "--week-display"):
            self.assertIn(flag, args)
        self.assertEqual(json.loads(args[args.index("--settings")+1]),
                         {"calendar-days": {"days": 14}, "large-hulls": {"max_tons": 250000, "cvl_aircraft": 100}, "week-display": {}})
        self.assertIn("14-day calendar", result["message"])

    def test_native_design_and_shape_files_are_moddable(self):
        targets = {"design": "Data/IDes/Paper Battleship.tdf", "hull": "Data/Graphics/HullPaper.hus",
                   "turret": "Data/Graphics/PaperTurret.tus", "gear": "Data/Graphics/Paper Radar.eqs"}
        for ident, target in targets.items():
            self.mod(ident, target=target)
        loader.apply(list(targets))
        for target in targets.values():
            self.assertEqual((self.game / target).read_bytes(), b"new tips\r\n")
        loader.apply([])
        for target in targets.values():
            self.assertFalse((self.game / target).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

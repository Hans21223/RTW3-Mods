"""The beta ZIP ships only the manager, the loader code and the shipped mods, and works from a fresh game folder;
the manager's updater (Mods/ModManager/updates.py) installs a release over an older one."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import build_beta_release as release

sys.path.insert(0, str(release.WINDOW))
import updates

GAME = release.MODS.parent


def archive(files):
    """A release ZIP from {name: bytes}, with its file list."""
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
        z.writestr(updates.MANIFEST, "\n".join(sorted([*files, updates.MANIFEST]))+"\n")
    return data.getvalue()


class BetaReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="rtw-beta-")
        cls.zip = release.build(Path(cls.temp.name)/"beta.zip")
        cls.names = set(zipfile.ZipFile(cls.zip).namelist())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_ships_the_manager_loader_and_mods_only(self):
        listed = zipfile.ZipFile(self.zip).read(updates.MANIFEST).decode().splitlines()
        self.assertEqual(set(listed), self.names)
        digest, name = self.zip.with_name(self.zip.name+".sha256").read_text().split()
        self.assertEqual((digest, name), (hashlib.sha256(self.zip.read_bytes()).hexdigest(), self.zip.name))
        for name in ("README.txt", "Mods/ModManager/Mod Manager.exe", "Mods/ModManager/modman.pyw",
                     "Mods/ModManager/updates.py",
                     "Mods/ModManager/LICENSE", "Mods/Manager/mod_loader.py", "Mods/CampaignOverhaul/launch.py",
                     "Mods/CampaignOverhaul/frigate_type_sites.json", "Mods/Manager/vendor/capstone/lib/capstone.dll"):
            self.assertIn(name, self.names)
        mods = {name.split("/")[2] for name in self.names if name.startswith("Mods/Library/")}
        self.assertEqual(mods, set(release.SHIPPED))
        for name in self.names:
            path = Path(name)
            self.assertFalse(path.name.startswith("test_") or path.suffix in (".md", ".cs", ".pdf", ".xlsx"), name)
            self.assertFalse({"backups", "baseline", "vanilla", "unicorn", "__pycache__"} & set(path.parts), name)
            self.assertNotIn(path.name, ("state.json", "RTW3.exe", "advanced_saves.py"))

    def test_a_fresh_game_folder_turns_the_mods_on_and_off(self):
        game = Path(self.temp.name)/"game"
        (game/"Data").mkdir(parents=True)
        self.assertEqual(updates.install(self.zip.read_bytes(), game), (len(self.names), 0))
        shutil.copy2(GAME/"RTW3.exe", game)
        research = game/"Data"/"ResearchAreas3.dat"
        shutil.copy2(release.OVERHAUL/"vanilla"/"ResearchAreas3.dat", research)
        python = game/"Mods"/"ModManager"/"Mod Manager.exe"

        def run(*args):
            done = subprocess.run([str(python), *map(str, args)], cwd=game, capture_output=True, text=True, timeout=600)
            if "Close RTW3" in done.stdout:
                self.skipTest("RTW3 is running")
            return done

        def loader(*args):
            answer = json.loads(run(game/"Mods/Manager/mod_loader.py", *args).stdout.strip().splitlines()[-1])
            self.assertTrue(answer["ok"], answer)
            return answer

        self.assertEqual(loader("bootstrap")["enabled"], [])
        loader("apply", "--enabled", ",".join(release.SHIPPED))
        package = game/"Mods/Library/timeline-2030/Files/Data/ResearchAreas3.dat"
        self.assertEqual(research.read_bytes(), package.read_bytes())
        self.assertIn(f"selftest ok: {len(release.SHIPPED)} mods listed, {len(release.SHIPPED)} on",
                      run(game/"Mods/ModManager/modman.pyw", "--selftest").stdout)
        modules = sorted(Path(n).stem for n in self.names if n.startswith("Mods/CampaignOverhaul/") and n.endswith(".py"))
        imported = run("-c", f"import mod_loader, capstone; [__import__(m) for m in {modules}]; "
                             "capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); import modern_tree; "
                             f"print('imported', modern_tree.render()[0] == open(r'{package}', 'rb').read())")
        self.assertIn("imported True", imported.stdout, imported.stderr)   # the tree builds on the player's own file
        loader("apply", "--enabled", "")
        self.assertEqual(research.read_bytes(), (release.OVERHAUL/"vanilla"/"ResearchAreas3.dat").read_bytes())


class UpdaterTests(unittest.TestCase):
    def test_newest_release_needs_its_checksum_and_a_higher_version(self):
        def release_(tag, *names, draft=False):
            return {"draft": draft, "body": f"notes {tag}",
                    "assets": [{"name": n, "browser_download_url": "https://x/"+n} for n in names]}
        zip_ = lambda v: f"RTW3-Mods-Beta-{v}.zip"
        releases = [release_("a", zip_("2026.11.17"), zip_("2026.11.17")+".sha256"),
                    release_("b", zip_("2026.12.1")),                                   # no checksum: skipped
                    release_("c", zip_("2026.12.2"), zip_("2026.12.2")+".sha256", draft=True),
                    release_("d", zip_("2026.11.20.2"), zip_("2026.11.20.2")+".sha256")]
        found = updates.newest(releases, "2026.11.17")
        self.assertEqual(found[0], "2026.11.20.2"); self.assertEqual(found[3], "notes d")
        self.assertIsNone(updates.newest(releases, "2026.11.20.2"))

    def test_download_must_match_its_checksum(self):
        good = b"release bytes"
        answers = {"zip": good, "sha": hashlib.sha256(good).hexdigest().encode()+b"  x.zip\n"}
        with patch.object(updates, "fetch", side_effect=lambda url, timeout=30: answers[url]):
            self.assertEqual(updates.download("zip", "sha"), good)
            answers["zip"] = b"tampered"
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                updates.download("zip", "sha")

    def test_update_writes_changed_files_and_removes_what_the_release_dropped(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            (game/"Mods"/"Manager").mkdir(parents=True)
            (game/"Mods"/"Manager"/"state.json").write_text("player state")
            old = {"README.txt": b"r", "Mods/Library/week-display/mod.json": b"{}", "Mods/Manager/mod_loader.py": b"1",
                   "Mods/ModManager/modman.pyw": b"m"}
            self.assertEqual(updates.install(archive(old), game), (5, 0))
            new = dict(old); del new["Mods/Library/week-display/mod.json"]; new["Mods/Manager/mod_loader.py"] = b"2"
            self.assertEqual(updates.install(archive(new), game), (2, 1))   # the loader and the file list changed
            self.assertFalse((game/"Mods"/"Library"/"week-display").exists())
            self.assertTrue((game/"Mods"/"Library").is_dir())
            self.assertEqual((game/"Mods"/"Manager"/"mod_loader.py").read_bytes(), b"2")
            self.assertEqual((game/"Mods"/"Manager"/"state.json").read_text(), "player state")   # never shipped

    def test_unsafe_or_foreign_archives_change_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            for name in ("../evil.txt", "C:/evil.txt", "Data/Events.dat", "Mods/../../evil.txt"):
                with self.assertRaisesRegex(RuntimeError, "outside the mods folder"):
                    updates.install(archive({name: b"x", "Mods/a.txt": b"a"}), game)
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as z: z.writestr("Mods/a.txt", b"a")
            with self.assertRaisesRegex(RuntimeError, "isn't an RTW3 mods release"):
                updates.install(data.getvalue(), game)
            self.assertEqual(list(game.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

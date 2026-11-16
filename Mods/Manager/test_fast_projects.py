"""Selected-project cheats: isolated saves, native discovery and x86 emulation."""
import contextlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
import live_cheats as live
import mod_loader
import project_cheats as projects
import save_cheats as saves
import test_campaign_tools as fixtures
import test_live_cheats as protocol


def ship_row(**overrides):
    row = dict(Cost=1000, BuildProgress=0, MonthlyCost=100, YearBuilt=1889,
               Halted=0, Hurry=0, Rebuild=0, RepairTime=3, TimeToRefit=60, Sunk=0)
    row.update(overrides)
    return row


class ClassificationTests(unittest.TestCase):
    def test_active_projects_and_in_service_sentinels(self):
        for overrides, kind in (({}, "refit"), ({"RepairTime": 0}, None),
                ({"RepairTime": 100}, None), ({"RepairTime": 101}, None),
                ({"RepairTime": -1}, None), ({"Sunk": 1}, None),
                ({"YearBuilt": 1891, "RepairTime": 100}, None),
                ({"BuildProgress": 200, "RepairTime": 101}, None),
                ({"BuildProgress": 200, "Rebuild": 1}, "rebuild")):
            with self.subTest(overrides=overrides):
                found = projects.describe(ship_row(**overrides), 1890)
                self.assertEqual(found["kind"] if found else None, kind)

    def test_one_turn_preserves_cost_and_maintenance_due(self):
        for overrides in ({}, {"BuildProgress": 1, "YearBuilt": 1891},
                          {"BuildProgress": 1, "Rebuild": 1}):
            row = ship_row(**overrides)
            project = projects.describe(row, 1890)
            changes = projects.changes(project, 1)
            self.assertNotIn("Cost", changes)
            self.assertNotIn("BuildProgress", changes)
            self.assertNotIn("TimeToRefit", changes)
            self.assertEqual(changes, {"RepairTime": 1} if project["kind"] == "refit" else
                             {"MonthlyCost": 999, "Halted": 0, "Hurry": 0})

    def test_countdown_ranges_and_ceil_division(self):
        refit = projects.describe(ship_row(), 1890)
        build = projects.describe(ship_row(BuildProgress=1), 1890)
        self.assertEqual(projects.changes(build, 2)["MonthlyCost"], 500)
        for bad in (True, False, 0, -1, 1.5, 1201, None):
            with self.assertRaises(ValueError): projects.changes(build, bad)
        for bad in (100, 101, 1200):
            with self.assertRaises(ValueError): projects.changes(refit, bad)


class SavedProjectTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        temp = self.context.enter_context(tempfile.TemporaryDirectory(prefix="fast-projects-"))
        self.root = Path(temp)
        self.save_root = self.root/"Save"
        self.slot = self.save_root/"Game1"
        self.slot.mkdir(parents=True)
        self.path = self.slot/"test.bcs"
        self.original = fixtures.SAMPLE + b"".join(
            ("Ship%dName=Yard ship %d\r\n" % (i, i) + "".join(
                "Ship%d%s=%s\r\n" % (i, k, v) for k, v in ship_row(**extra).items())).encode()
            for i, extra in ((1, {}), (2, {"BuildProgress": 200, "Rebuild": 1}),
                             (3, {"RepairTime": 100}), (4, {"Sunk": 1})))
        self.path.write_bytes(self.original)
        (self.slot/"design.des").write_bytes(b"unchanged design")
        self.context.enter_context(patch.object(saves, "SAVE_ROOT", self.save_root))
        self.context.enter_context(patch.object(saves, "BACKUPS", self.root/"backups"))
        self.context.enter_context(patch.object(mod_loader, "running_games", return_value=[]))

    def tearDown(self): self.context.close()

    def apply(self, index):
        return saves.edit(self.path, "Nation0", {}, index, 1, saves.digest(self.path))

    def test_selected_refit_changes_only_countdown_and_backs_up_slot(self):
        view = saves.inspect(self.path)
        self.assertEqual([s["kind"] for s in view["ships"]], ["build", "refit", "rebuild"])
        result = self.apply(1)
        self.assertEqual(self.path.read_bytes(), self.original.replace(b"Ship1RepairTime=3", b"Ship1RepairTime=1"))
        self.assertEqual((Path(result["backup"])/self.path.name).read_bytes(), self.original)
        self.assertEqual((Path(result["backup"])/"design.des").read_bytes(), b"unchanged design")

    def test_nonproject_fleet_is_visible_but_not_eligible(self):
        view = saves.inspect(self.path)
        self.assertEqual([s["index"] for s in view["fleet_ships"]], [0, 1, 2])
        self.assertEqual([s["index"] for s in view["ships"]], [0, 1, 2])
        self.path.write_bytes(self.original.replace(b"Ship3RepairTime=100", b"Ship3RepairTime=0"))
        view = saves.inspect(self.path)
        self.assertEqual(view["fleet_ships"][-1]["kind"], "inactive")
        self.assertEqual(view["fleet_ships"][-1]["name"], "Yard ship 3")

    def test_new_build_and_rebuild_target_one_turn_without_free_completion(self):
        for index, old, new in ((0, 1000, 4000), (2, 100, 800)):
            self.path.write_bytes(self.original)
            result = self.apply(index)
            self.assertEqual(self.path.read_bytes(), self.original.replace(
                ("Ship%dMonthlyCost=%d" % (index, old)).encode(),
                ("Ship%dMonthlyCost=%d" % (index, new)).encode()))
            ship = next(s for s in result["save"]["ships"] if s["index"] == index)
            self.assertEqual(ship["remaining_turns"], 1)

    def test_nonprojects_stale_hash_and_running_game_are_refused(self):
        for index in (3, 4, 99, True):
            with self.assertRaises(ValueError): self.apply(index)
        with self.assertRaisesRegex(ValueError, "save changed"):
            saves.edit(self.path, "Nation0", {}, 1, 1, "stale")
        with patch.object(mod_loader, "running_games", return_value=[{"pid": 1}]):
            with self.assertRaisesRegex(ValueError, "Close RTW3"): self.apply(1)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_all_builds_and_all_refits_are_scoped_and_backed_up(self):
        for kind, indices in (("build", (0,)), ("refit", (1, 2))):
            self.path.write_bytes(self.original)
            result = saves.edit(self.path, "Nation0", {}, expected_hash=saves.digest(self.path), all_projects=kind)
            view = result["save"]
            for ship in view["ships"]:
                if ship["index"] in indices: self.assertEqual(ship["remaining_turns"], 1)
            expected = self.original
            for i in indices:
                if i == 1: expected = expected.replace(b"Ship1RepairTime=3", b"Ship1RepairTime=1")
                else: expected = expected.replace((f"Ship{i}MonthlyCost="+("1000" if i == 0 else "100")).encode(),
                                                 (f"Ship{i}MonthlyCost="+("4000" if i == 0 else "800")).encode())
            self.assertEqual(self.path.read_bytes(), expected)
            self.assertEqual((Path(result["backup"])/self.path.name).read_bytes(), self.original)
        for kind in ("both", True, "", 5):
            with self.assertRaises(ValueError):
                projects.select([], all_projects=kind)
        with self.assertRaises(ValueError): projects.select([], ship_index=0, all_projects="build")


class NativeProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.base = json.loads((HERE/"native-designer-inspection.json").read_text())["text_base"]
        cls.fields = live.discover(cls.blob, cls.base)["ship"]

    def test_verified_native_refit_and_maintenance_fields_are_distinct(self):
        self.assertEqual(self.fields["RepairTime"], 0x25)
        self.assertEqual(self.fields["TimeToRefit"], 0x21)
        self.assertNotIn("Sunk", self.fields)

    def test_ship_names_use_reviewed_name_field_not_numeric_id(self):
        self.assertEqual(live.discover_ship_name(self.blob, self.base), 0xc)
        changed = bytearray(self.blob)
        at = changed.index(bytes.fromhex("0fb65f1480fb0c750c8bc68b570c"))
        changed[at+12] = 4
        with self.assertRaisesRegex(ValueError, "ship-name field"):
            live.discover_ship_name(bytes(changed), self.base)

    def test_changed_native_refit_routine_fails_closed(self):
        start = live.rt.method_address(self.blob, self.base, "SendToRefit")-self.base
        changed = bytearray(self.blob)
        at = changed.index(b"\x01\x73\x25", start, start+0xa0)
        changed[at+2] ^= 4
        with self.assertRaisesRegex(ValueError, "verification failed"):
            live.discover_yard_fields(bytes(changed), self.base)

    def emulate(self, row, stale=None):
        row = {key: row[key] for key in self.fields}
        harness = protocol.MailboxTests()
        pointer, entry = harness.data+0x5000, harness.data+0x4800
        project = projects.describe(row, 1890)
        ship = dict(project, pointer=pointer, entry=entry, raw=row)
        records = live.project_records(ship, self.fields, 1)
        self.assertLessEqual(len(records)+7, live.MAX_EDITS)
        vm, mailbox, layout = harness.make(records)
        vm.mem_write(entry, struct.pack("<I", pointer))
        for key, old in row.items():
            vm.mem_write(pointer+self.fields[key], int(old).to_bytes(projects.SHIP_WIDTHS[key], "little"))
        if stale:
            key, new = stale
            vm.mem_write(pointer+self.fields[key], int(new).to_bytes(projects.SHIP_WIDTHS[key], "little"))
        harness.run_code(vm, layout)
        after = {key: int.from_bytes(vm.mem_read(pointer+offset, projects.SHIP_WIDTHS[key]), "little")
                 for key, offset in self.fields.items()}
        return int.from_bytes(vm.mem_read(mailbox, 4), "little"), after

    def test_live_selected_refit_build_and_rebuild_transactions(self):
        for overrides in ({}, {"BuildProgress": 1, "YearBuilt": 1891},
                          {"BuildProgress": 1, "Rebuild": 1}):
            row = {key: value for key, value in ship_row(**overrides).items() if key in self.fields}
            status, after = self.emulate(row)
            self.assertEqual(status, 2)
            self.assertEqual(after, dict(row, **projects.changes(projects.describe(row, 1890), 1)))

    def test_live_roster_keeps_serving_ships_and_uses_campaign_loss_status(self):
        import campaign_security
        memory = {}
        def write(address, data): memory.update({address+i: value for i, value in enumerate(data)})
        def number(address, value): write(address, struct.pack("<I", value))
        def read(handle, address, size): return bytes(memory.get(address+i, 0) for i in range(size))
        def label(field, pointer, value):
            number(field, pointer); number(pointer-4, len(value)); write(pointer, value.encode("utf-16le"))
        layout = dict(main_slot=0x100, player_field=0x20, year_slot=0x104, research=0x108,
                      nation={"funds": 0x1b5}, ship_list=0x80, ship=self.fields, ship_name=0xc)
        number(0x100, 0x1000); number(0x1020, 0x10000)
        number(0x104, 0x120); number(0x120, 1900); number(0x108, 100)
        label(0x10004, 0x40000, "Fixture nation")
        number(0x10080, 0x20000); number(0x20004, 0x20020); number(0x20008, 3)
        for i, (name, extra) in enumerate((("Alpha", {"YearBuilt": 1901}), ("Beta", {}), ("Lost ship", {"RepairTime": 100}))):
            pointer = 0x30000+i*0x400; number(0x20020+i*4, pointer)
            number(pointer+4, 129+i)  # Numeric ID must never be read as a name.
            label(pointer+0xc, 0x40200+i*0x100, name)
            write(pointer+0x1a, b"\xff")  # Unrelated pointer byte is not Sunk.
            row = ship_row(RepairTime=0, **extra) if "RepairTime" not in extra else ship_row(**extra)
            for key, offset in self.fields.items():
                write(pointer+offset, int(row[key]).to_bytes(projects.SHIP_WIDTHS[key], "little"))
        saved = dict(layout=layout, pid=42, base=0x300000, dispatcher_version=2)
        with patch.object(live.rt, "read", side_effect=read), patch.object(campaign_security, "attached_state", return_value=None):
            view = live.snapshot(saved, None)
        self.assertEqual([ship["name"] for ship in view["fleet_ships"]], ["Alpha", "Beta"])
        self.assertEqual([ship["name"] for ship in view["ships"]], ["Alpha"])
        self.assertEqual(view["fleet_ships"][1]["kind"], "inactive")

    def test_live_stale_project_state_aborts_all_writes(self):
        for key, new in (("TimeToRefit", 59), ("RepairTime", 2), ("Rebuild", 1), ("RepairTime", 100), ("RepairTime", 101), ("YearBuilt", 1890)):
            row = {key: value for key, value in ship_row().items() if key in self.fields}
            status, after = self.emulate(row, (key, new))
            self.assertEqual(status, 4)
            self.assertEqual(after, dict(row, **{key: new}))


if __name__ == "__main__": unittest.main(verbosity=2)

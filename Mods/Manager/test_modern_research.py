"""Append-only data compatibility and full native getter emulation. No saves edited."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import *
import modern_tree as tree
import modern_research as modern
import mod_loader as loader
import research_slot_audit as slots


class TreeTests(unittest.TestCase):
    def setUp(self):
        self.original = tree.BASELINE.read_bytes()
        self.payload, self.nodes = tree.render()
        self.old, self.new = tree.parse(self.original), tree.parse(self.payload)

    def test_all_original_rows_ids_slots_headers_and_pictures_preserved(self):
        for old, new in zip(self.old, self.new):
            self.assertEqual(old["name"], new["name"])
            self.assertEqual(old["rows"], new["rows"][:len(old["rows"])])
            self.assertEqual([s.rstrip("\r\n") for s in old["lines"]],
                             [s.rstrip("\r\n") for s in new["lines"][:len(old["lines"])]])
        self.assertFalse(self.payload.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", self.payload.replace(b"\r\n", b""))

    def test_effectful_nodes_in_21_extended_and_2_new_branches(self):
        appended = [node for node in self.nodes if node["area"] < 22]
        added = [node for node in self.nodes if node["area"] >= 22]
        self.assertEqual((len(appended), len({node["area"] for node in appended})), (83, 21))
        self.assertEqual([area["name"] for area in self.new[22:]], ["Vertical launch systems", "Naval combat systems"])
        self.assertEqual(len(added), sum(len(area["rows"]) for area in self.new[22:]))
        self.assertEqual(max(node["year"] for node in self.nodes), 2030)
        self.assertEqual(self.old[16]["rows"], self.new[16]["rows"])
        for area in self.new: self.assertLessEqual(len(area["rows"]), 36)
        # VLS Cells and modern_sensors implement these IDs instead of getter hooks.
        implemented = (set(tree.VLS_CELLS.values())|{i for i, _ in tree.VLS_LIGHT+tree.VLS_DENSE}|{i for i, _, _ in tree.STEALTH}
                       |{tree.RAILGUN, tree.LASERS, tree.HYPERSONIC, tree.INTEGRATED_POWER[0], *tree.RAILGUN_EFFICIENCY}
                       |{tree.AESA[0], tree.GUIDED_TORPEDOES[0], tree.GUIDED_SHELLS[0], tree.EMALS[0],
                         tree.HEAVY_GUIDED_SHELLS[0], tree.SATELLITES[0], tree.UAVS, tree.RAILGUN_SECONDARIES, tree.RAILGUN_POINT_DEFENCE[0], tree.ASW_TORPEDOES, tree.VL_ASW, tree.COMPOSITE[0], tree.USV, tree.NUCLEAR_SHELLS[0], tree.SKI_JUMP[0], tree.VTOL, tree.SSN, tree.SSBN, tree.STEALTH_SSM[0], tree.HYPERSONIC_SAM[0], *(i for i, *_ in tree.SEAD), tree.HYBRID[0], *(i for i, *_ in tree.MISSILE_RANGES), tree.DRONE_SWARMS[0], tree.HVP_AA[0], tree.AERIAL_REFUELLING[0], tree.CARRIER_TANKERS[0],
                         tree.GUN_MISSILE, tree.RAM, tree.SEARAM, tree.PD_MAGAZINES[0], tree.ANTI_TORPEDO})
        for node in self.nodes:
            self.assertTrue(node["effects"] or node["area"] in tree.NATIVE or node["id"] in implemented)
            self.assertTrue(set(node["effects"]) <= tree.LABELS.keys())
            # Nuclear propulsion reuses slot 32 (ID 40) and follows Gas turbines (1960).
            if node in appended and node["id"] != tree.NUCLEAR_PROPULSION: self.assertGreaterEqual(node["year"], 1978)   # Aegis: at sea 1973, CG-47 laid down 1980
            self.assertLessEqual(node["slot"], 35)
            if node["year"] == 2030: self.assertIn("projected", node["name"])

    def test_every_added_node_has_a_valid_ordered_native_prerequisite(self):
        original = {row["id"] for area in self.old for row in area["rows"]}
        for index, area in enumerate(self.new):
            old_rows = self.old[index]["rows"] if index < 22 else []
            # New branches start from a technology in another original branch.
            known = {row["id"] for row in old_rows} if index < 22 else set(original)
            date = old_rows[-1]["year"] if index < 22 else 1900
            for row in area["rows"][len(old_rows):]:
                self.assertIn(row["prerequisite"], known)
                self.assertGreater(row["year"], date)
                date = row["year"]; known.add(row["id"])

    def test_packaged_table_matches_builder_and_index(self):
        self.assertEqual((tree.PACKAGE/"Files/Data/ResearchAreas3.dat").read_bytes(), self.payload)
        index = json.loads((tree.PACKAGE/"research-index.json").read_text())
        self.assertEqual(index["nodes"], self.nodes)
        self.assertEqual(index["sha256"], hashlib.sha256(self.payload).hexdigest())

    def test_manifest_bundles_calendar_research_and_vls_adapters(self):
        package = loader.read_manifest(tree.PACKAGE)
        self.assertEqual(package["runtime"], [{"adapter": "timeline-2030", "end_year": 2050},
                                              {"adapter": "modern-research"}, {"adapter": "vls-cells"}])
        self.assertEqual(package["requires"], [])
        self.assertTrue(package["experimental"])
        _, _, runtime = loader.resolve_plan(["timeline-2030", "battle-ai", "live-cheats", "in-game-submarines"])
        order = [step["adapter"] for step in loader.runtime_registry.plan(
            [entry["adapter"] for mod in runtime for entry in loader.runtime_entries(mod)])]
        self.assertLess(order.index("timeline-2030"), order.index("modern-research"))
        self.assertLess(order.index("modern-research"), order.index("vls-cells"))

    def test_invalid_and_overfull_inputs_rejected(self):
        with self.assertRaises(ValueError): tree.render(b"\xef\xbb\xbf"+self.original)
        with self.assertRaises(ValueError): tree.render(self.payload)
        duplicate = self.original.replace(b";31;Lighter", b";30;Lighter")
        with self.assertRaises(ValueError): tree.render(duplicate)

    def test_runtime_refuses_changed_active_research_table(self):
        with tempfile.TemporaryDirectory(prefix="modern-table-check-") as temp:
            root = Path(temp); (root/"Data").mkdir()
            p = root/"Data/ResearchAreas3.dat"; p.write_bytes(self.payload)
            with patch.object(modern.rt, "GAME", root):
                self.assertEqual(modern.check_payload(), hashlib.sha256(self.payload).hexdigest())
                p.write_bytes(self.original)
                with self.assertRaisesRegex(ValueError, "table differs"): modern.check_payload()
                # A research-speed sub-mod: earlier years, other costs and chances, same technologies.
                faster = self.payload.replace(b"Y-S-T engine;1891;Y;100;6;30;", b"Y-S-T engine;1885;Y;90;4;30;")
                self.assertNotEqual(faster, self.payload); p.write_bytes(faster)
                self.assertEqual(modern.check_payload(), hashlib.sha256(faster).hexdigest())
                lines = self.payload.split(b"\r\n")
                first = next(i for i, line in enumerate(lines) if line.startswith(b"Y-S-T engine;"))
                lines[first], lines[first+1] = lines[first+1], lines[first]           # two technologies swapped
                p.write_bytes(b"\r\n".join(lines))
                with self.assertRaisesRegex(ValueError, "moved"): modern.check_payload()
                p.write_bytes(self.payload.replace(b"Y-S-T engine;1891;", b"Y-S-T engine;1849;"))
                with self.assertRaisesRegex(ValueError, "can't be read"): modern.check_payload()


class NativeResearchTests(unittest.TestCase):
    nation, other, main, year, stack, done = 0x200000, 0x208000, 0x210000, 0x220000, 0x108000, 0x100f00

    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.base = json.loads((HERE/"native-designer-inspection.json").read_text())["text_base"]
        cls.details = modern.discover(cls.blob, cls.base)
        # Two empty entries: the new branches 22-23 own no original rows.
        cls.original = tree.parse(tree.BASELINE.read_bytes())+[{"rows": []}]*2
        payload, cls.nodes = tree.render()
        cls.areas = tree.parse(payload)

    def machine(self, owned=(), enabled=True, legacy=True, other_owned=()):
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        vm.mem_map(0, 0x1000)  # isolated Delphi SEH chain; no OS hooks
        vm.mem_map(0x100000, 0x20000)
        vm.mem_map(0x200000, 0x30000)
        vm.mem_map(0x300000, 0x800000)
        vm.mem_map(0x1000000, 0x10000)
        vm.mem_write(self.base, self.blob)
        d = self.details
        # Native research-table count and records; names are nil so temporary
        # string reference operations never allocate or call the operating system.
        vm.mem_write(0xa1c924, struct.pack("<I", len(self.areas)))
        for a, area in enumerate(self.areas):
            for slot, row in enumerate(area["rows"]):
                at = d["table_id_base"]+a*d["table_stride"]+slot*d["record_stride"]
                vm.mem_write(at, struct.pack("<I", row["id"]))
                vm.mem_write(at-13, struct.pack("<I", row["year"]))
                for nation, selected in ((self.nation, owned), (self.other, other_owned)):
                    if (legacy and slot < len(self.original[a]["rows"])) or row["id"] in selected:
                        vm.mem_write(nation+d["flag_base"]+a*d["nation_stride"]+slot, b"\x01")
        vm.mem_write(0xa23000, struct.pack("<I", self.main))
        vm.mem_write(self.main+0x4aa4, struct.pack("<I", 1935))
        vm.mem_write(self.main+0x3204, struct.pack("<I", self.nation))
        vm.mem_write(0x9f7328, struct.pack("<I", self.year))
        vm.mem_write(self.year, struct.pack("<I", 2030))
        if enabled:
            for i, site in enumerate(d["getters"]):
                address = 0x1000000+i*0x1000
                vm.mem_write(address, modern.effect_thunk(site))
                size = len(bytes.fromhex(site["original"]))
                vm.mem_write(site["address"], b"\xe9"+struct.pack("<i", address-site["address"]-5)+b"\x90"*(size-5))
        return vm

    def call(self, vm, method, nation=None, edx=0):
        values = {UC_X86_REG_EAX: self.nation if nation is None else nation,
                  UC_X86_REG_EBX: 0xbeef, UC_X86_REG_ECX: 0,
                  UC_X86_REG_EDX: edx, UC_X86_REG_ESI: 0x1234,
                  UC_X86_REG_EDI: 0x5678, UC_X86_REG_EBP: 0x109000,
                  UC_X86_REG_ESP: self.stack, UC_X86_REG_EFLAGS: 0x246}
        for reg, val in values.items(): vm.reg_write(reg, val)
        vm.mem_write(self.stack, struct.pack("<I", self.done))
        before = bytes(vm.mem_read(self.nation, 0x18000))
        start = modern.rt.method_address(self.blob, self.base, method)
        vm.emu_start(start, self.done, count=2000000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP), self.done)
        self.assertEqual(before, bytes(vm.mem_read(self.nation, 0x18000)), "Research effect wrote nation or campaign data")
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP), self.stack+4)
        for reg in (UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP):
            self.assertEqual(vm.reg_read(reg), values[reg])
        return vm.reg_read(UC_X86_REG_EAX), {reg: vm.reg_read(reg) for reg in (UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EFLAGS)}

    def test_native_abi_and_ten_bounded_getter_hooks(self):
        d = self.details
        self.assertEqual((d["max_levels"], d["flag_base"], d["nation_stride"]), (36, 0x336, 0x35))
        self.assertEqual(len(d["getters"]), 10)
        self.assertIn("record 24", d["save_format_changed"])
        self.assertFalse(d["new_weapon_types"])
        for site in d["getters"]:
            self.assertLess(len(modern.effect_thunk(site)), 0x1000)
            self.assertLessEqual(site["maximum_bonus"], 10)

    def test_no_new_research_is_exact_native_result_and_flags(self):
        native, patched = self.machine(enabled=False), self.machine()
        for site in self.details["getters"]:
            with self.subTest(method=site["name"]):
                self.assertEqual(self.call(native, site["name"]), self.call(patched, site["name"]))

    def test_all_owned_technologies_change_full_native_getter_results(self):
        native = self.machine(enabled=False)
        patched = self.machine(owned={node["id"] for node in self.nodes})
        for site in self.details["getters"]:
            with self.subTest(method=site["name"]):
                base, state = self.call(native, site["name"])
                result, after = self.call(patched, site["name"])
                self.assertEqual(result, (base+site["maximum_bonus"]) & 0xffffffff)
                self.assertEqual(state, after)

    def test_each_new_flag_has_only_its_declared_direct_bonuses(self):
        vm = self.machine()
        base = {s["name"]: self.call(vm, s["name"])[0] for s in self.details["getters"]}
        for node in (n for n in self.nodes if n["effects"]):
            flag = self.nation+self.details["flag_base"]+node["area"]*53+node["slot"]
            vm.mem_write(flag, b"\x01")
            for site in self.details["getters"]:
                result = self.call(vm, site["name"])[0]
                self.assertEqual(result, (base[site["name"]]+(site["name"] in node["effects"])) & 0xffffffff,
                                 (node["id"], site["name"]))
            vm.mem_write(flag, b"\x00")

    def test_player_and_ai_use_only_their_own_completed_research(self):
        vm = self.machine(owned={n["id"] for n in self.nodes})
        site = next(s for s in self.details["getters"] if s["name"] == "GetSAMQ")
        player = self.call(vm, "GetSAMQ", self.nation)[0]
        other = self.call(vm, "GetSAMQ", self.other)[0]
        self.assertEqual(player-other, site["maximum_bonus"])
        for row in site["contributions"]: vm.mem_write(self.other+row["flag"], b"\x01")
        self.assertEqual(player, self.call(vm, "GetSAMQ", self.other)[0])

    def test_wrong_table_id_and_nonboolean_flag_do_not_grant_bonus(self):
        vm = self.machine()
        baseline = self.call(vm, "GetSAMQ")[0]
        site = next(s for s in self.details["getters"] if s["name"] == "GetSAMQ")
        entry = site["contributions"][0]
        vm.mem_write(self.nation+entry["flag"], b"\x02")
        self.assertEqual(self.call(vm, "GetSAMQ")[0], baseline)
        vm.mem_write(self.nation+entry["flag"], b"\x01")
        vm.mem_write(entry["table"], struct.pack("<I", 9999))
        self.assertEqual(self.call(vm, "GetSAMQ")[0], baseline)

    def test_native_id_lookup_recognizes_every_new_completed_node(self):
        vm = self.machine(owned={n["id"] for n in self.nodes})
        for node in self.nodes:
            self.assertEqual(self.call(vm, "HasResearchId", edx=node["id"])[0] & 0xff, 1)
        self.assertEqual(self.call(vm, "HasResearchId", edx=9999)[0] & 0xff, 0)

    def test_native_generic_levels_gunnery_armour_ap_and_invasion_progress(self):
        native = self.machine(enabled=False)
        modern_vm = self.machine(owned={n["id"] for n in self.nodes})
        for method, gain in (("GetAccuracyMod", 2), ("GetArmorModifier", 4),
                             ("GetPenetrationModifier", 4), ("GetInvasionRange", 400),
                             ("GetMaxCarrierDisplacement", 12000)):
            with self.subTest(method=method):
                old = self.call(native, method)[0]
                new = self.call(modern_vm, method)[0]
                self.assertEqual(new, (old+gain) & 0xffffffff)
        for area in tree.NATIVE:
            old = self.call(native, "CountResearchLevels", edx=area)[0]
            new = self.call(modern_vm, "CountResearchLevels", edx=area)[0]
            self.assertEqual(new-old, len(tree.BRANCHES[area]))

    def test_native_machinery_and_hull_weight_factors_really_decrease(self):
        native = self.machine(enabled=False)
        modern_vm = self.machine(owned={n["id"] for n in self.nodes})
        ship = 0x224000
        for vm in (native, modern_vm): vm.mem_write(ship+0xb28, struct.pack("<I", 2030))
        for method, offset in (("SetEngineWeightSavingFactor", 0xa34), ("SetHullWeightSavingFactor", 0xa2c)):
            self.call(native, method, edx=ship)
            self.call(modern_vm, method, edx=ship)
            before = struct.unpack("<f", native.mem_read(ship+offset, 4))[0]
            after = struct.unpack("<f", modern_vm.mem_read(ship+offset, 4))[0]
            self.assertAlmostEqual(before-after, 0.04, places=5)

    def test_changed_audited_code_is_refused_before_patching(self):
        for site in self.details["getters"]:
            changed = bytearray(self.blob); changed[site["address"]-self.base] ^= 1
            with self.assertRaisesRegex(ValueError, "audited build"):
                modern.discover(bytes(changed), self.base)

    def test_address_randomization_preserves_validation_and_relocates_all_hooks(self):
        delta = 0x510000
        relocated = bytearray(self.blob)
        for offset in modern.text_relocations():
            value = struct.unpack_from("<I", relocated, offset)[0]
            struct.pack_into("<I", relocated, offset, (value+delta) & 0xffffffff)
        actual = modern.discover(bytes(relocated), self.base+delta)
        self.assertEqual(actual["table_id_base"], self.details["table_id_base"]+delta)
        for expected, got in zip(self.details["getters"], actual["getters"]):
            self.assertEqual(got["address"], expected["address"]+delta)
            for a, b in zip(expected["contributions"], got["contributions"]):
                self.assertEqual(a["flag"], b["flag"])
                self.assertEqual(a["table"]+delta, b["table"])
        broken = bytearray(relocated)
        broken[self.details["getters"][0]["address"]-self.base] ^= 1
        with self.assertRaisesRegex(ValueError, "audited build"):
            modern.discover(bytes(broken), self.base+delta)


class SaveIni(slots.IniHarness):
    """A real save omits unknown keys; the native reader then returns its default."""
    def read(self):
        key = self.text(self.vm.reg_read(UC_X86_REG_ECX))
        default = slots.u32(self.vm, self.vm.reg_read(UC_X86_REG_ESP)+4)
        self.vm.reg_write(UC_X86_REG_EAX, self.values.get(key, default))
        self.calls += 1
        self.finish(4)


class OlderSaveTests(unittest.TestCase):
    """Native research save/load loops in an emulator, with the adapter's loader hooks."""
    blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
    stride, code = slots.NATION_STRIDE, 0x2000000
    empty = bytes([0])+struct.pack("<4I", 2, 0, 0, 0)+bytes(36)   # native defaults

    @staticmethod
    def records(regular):
        data = bytearray()
        for area in range(regular+1):
            data += bytes([1])+struct.pack("<4I", 3, 17+area, area % 36, 100000+area)
            data += bytes((area+level) % 2 for level in range(36))
        return bytes(data)

    def save(self, regular):
        vm = slots.machine(self.blob, regular)
        vm.mem_write(slots.NATION+slots.NATION_START, self.records(regular))
        ini = slots.IniHarness(vm)
        vm.reg_write(UC_X86_REG_EBX, slots.NATION); vm.reg_write(UC_X86_REG_ESI, 0x210000); vm.reg_write(UC_X86_REG_EDI, 0)
        vm.emu_start(0x724F0E, 0x72520C, count=500000)
        return ini.values

    def load(self, values, regular=24, attached=True):
        vm = slots.machine(self.blob, regular)
        if attached:
            vm.mem_map(self.code, 0x30000)
            blocks, plans, _ = modern.build(self.code, modern.discover(self.blob, slots.BASE))
            for item in blocks+[dict(address=p["address"], bytes=p["replacement"]) for p in plans]:
                vm.mem_write(item["address"], bytes.fromhex(item["bytes"]))
        ini = SaveIni(vm, values)
        slots.put(vm, slots.FRAME-4, ini.string("Nation0"))
        vm.reg_write(UC_X86_REG_EBX, slots.NATION); vm.reg_write(UC_X86_REG_ESI, 0x210000)
        vm.emu_start(0x7206E2, 0x7208DD, count=500000)
        self.assertEqual((vm.reg_read(UC_X86_REG_EIP), vm.reg_read(UC_X86_REG_ESP)), (0x7208DD, slots.STACK))
        return bytes(vm.mem_read(slots.NATION+slots.NATION_START, 25*self.stride))

    def test_older_save_moves_gun_research_to_24_and_starts_new_branches_empty(self):
        old, n = self.records(22), self.stride
        loaded = self.load(self.save(22))
        self.assertEqual(loaded[:22*n], old[:22*n])
        self.assertEqual(loaded[22*n:24*n], self.empty*2)
        self.assertEqual(loaded[24*n:], old[22*n:])
        # Without the adapter the old gun record would land in the VLS branch.
        self.assertEqual(self.load(self.save(22), attached=False)[22*n:23*n], old[22*n:])

    def test_expanded_save_and_unexpanded_table_round_trip_unchanged(self):
        self.assertEqual(self.load(self.save(24)), self.records(24))
        self.assertEqual(self.load(self.save(22), regular=22)[:23*self.stride], self.records(22))


class AircraftTableTests(unittest.TestCase):
    def setUp(self):
        import modern_aircraft
        self.aircraft = modern_aircraft
        self.old = modern_aircraft.BASELINE.read_bytes().decode("ascii").split("\r\n")
        self.new = modern_aircraft.render().decode("ascii").split("\r\n")

    def rows(self, lines, section):
        start = lines.index(f"[{section}]")+1
        end = next(i for i in range(start, len(lines)) if lines[i].startswith("["))
        return {int(line[:4]): line.split(";") for line in lines[start:end]}

    def test_stealth_sections_follow_their_jet_with_bays_and_shaping(self):
        for base, name in self.aircraft.STEALTH.items():
            plain, stealth = self.rows(self.new, base), self.rows(self.new, name)
            self.assertEqual(sorted(stealth), list(self.aircraft.STEALTH_YEARS))
            for year, row in stealth.items():
                expected = list(plain[year])
                for column, percent in self.aircraft.STEALTH_PERCENT.items():
                    expected[column] = str(int(expected[column])*percent//100)
                for column, plus in self.aircraft.STEALTH_PLUS.items():
                    if expected[column] != "-": expected[column] = str(int(expected[column])+plus)
                self.assertEqual(row, expected, (name, year))

    def test_original_rows_kept_and_modern_types_improve_every_two_years_to_2030(self):
        first = next(i for i, line in enumerate(self.new) if line.startswith("[STEALTH"))
        plain = self.new[:first]+self.new[self.new.index("[END]"):]
        self.assertEqual([line for line in plain if line[:4] not in {str(y) for y in self.aircraft.YEARS}
                          or line.startswith("[")], self.old)
        for section, anchors in self.aircraft.ANCHORS.items():
            rows = self.rows(self.new, section)
            base = rows[1970]
            self.assertEqual(sorted(y for y in rows if y > 1970), list(self.aircraft.YEARS))
            previous = base
            for year in self.aircraft.YEARS:
                row = rows[year]
                self.assertEqual(len(row), len(base))
                for column, field in enumerate(row[1:], 1):
                    if column in anchors:
                        self.assertGreaterEqual(int(field), int(previous[column]), (section, year, column))
                    else:
                        self.assertEqual(field, base[column], (section, year, column))
                previous = row
            # Native lookup: that year's row or the previous year's, so 1971-2031 never
            # falls back to "last row plus 1%" before 2031.
            for year in range(1971, 2032):
                self.assertTrue(year in rows or year-1 in rows, (section, year))

    def test_packaged_table_and_manifest(self):
        self.assertEqual((self.aircraft.PACKAGE/"Files/Data/AircraftBasicData3.dat").read_bytes(), self.aircraft.render())
        files = loader.read_manifest(self.aircraft.PACKAGE)["files"]
        self.assertIn({"source": "Files/Data/AircraftBasicData3.dat", "target": "Data/AircraftBasicData3.dat"}, files)


if __name__ == "__main__": unittest.main(verbosity=2)

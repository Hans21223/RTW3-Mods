"""Later start years: the year-screen labels, the year click, the start flags and tech, run in an emulator."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI,
                               UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP)
import campaign_qol as qol
import modern_research as audit
import start_years as sy

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
BASE = sy.BASE
PAGE, STUBS, DATA, HEAP, STACK = 0x10000000, 0x11000000, 0x12000000, 0x13000000, 0x14000000
FORM, PANEL, IMAGE, PICTURE, LB1935, OTHER = DATA, DATA+0x1000, DATA+0x1100, DATA+0x1200, DATA+0x1300, DATA+0x1400
YEAR, DATE, DIR, DIR_TEXT, MAIN, LIST = DATA+0x2000, DATA+0x2010, DATA+0x2020, DATA+0x2030, DATA+0x3000, DATA+0x8000
NAMES = ("encode_date", "cat3", "clear", "assign", "file_exists", "load_picture", "set_left", "set_top", "set_width",
         "set_height", "set_show_hint", "set_transparent", "native_1935", "after_year", "no_year", "after_image",
         "after_button", "flags_1935", "after_flags", "after_nations", "after_map", "create", "set_parent",
         "set_auto_size")
STOPS = ("native_1935", "after_year", "no_year", "after_image", "after_button", "flags_1935", "after_flags",
         "after_nations", "after_map")
NATIVE_FILES = dict(bnat_1935=0x0BAD1935, mapdata_1920=0x0BAD1920)            # the game's own file-name strings
REGS = dict(eax=UC_X86_REG_EAX, ebx=UC_X86_REG_EBX, ecx=UC_X86_REG_ECX, edx=UC_X86_REG_EDX, esi=UC_X86_REG_ESI,
            edi=UC_X86_REG_EDI, ebp=UC_X86_REG_EBP, esp=UC_X86_REG_ESP)


class World:
    """The page's code with stand-ins for the VCL and RTL calls it makes."""
    def __init__(self, picture=True):
        self.at = {name: STUBS+0x10*i for i, name in enumerate(NAMES)}
        self.vmt = STUBS+0x1000                              # a TLabel class: create at +0x3C, slots after
        info = {k: self.at[k] for k in NAMES if k not in ("create", "set_parent", "set_auto_size")}
        info.update(label_vmt=self.vmt, year=YEAR, date=DATE, game_dir=DIR, click=0x69C6C4, set_auto_size=0x94,
                    sites=[dict(name=n, address=a, original=o) for n, a, o in sy.SITES], **NATIVE_FILES)
        self.blocks, self.plans = sy.build(PAGE, info)
        vm = self.vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address in (PAGE, STUBS, DATA, HEAP, STACK): vm.mem_map(address, 0x10000)
        for block in self.blocks: vm.mem_write(block["address"], bytes.fromhex(block["bytes"]))
        vm.mem_write(STUBS, b"\xc3"*0x1000)
        vm.mem_write(self.at["encode_date"], b"\xdd\x05"+struct.pack("<I", DATA+0x2040)+b"\xc3")   # fld [date]
        for slot, name in ((0x3C, "create"), (0xA0, "set_parent"), (0x94, "set_auto_size")):
            self.put(self.vmt+slot, self.at[name])
        self.put(FORM+sy.FORM["panel"], PANEL); self.put(FORM+sy.FORM["image"], IMAGE)
        self.put(IMAGE+sy.VCL["picture"], PICTURE); self.put(FORM+sy.FORM["lb1935"], LB1935)
        self.put(FORM+sy.FORM["components"], LIST); self.put(LIST+4, LIST+0x10); self.put(LIST+8, 0)
        self.put(LB1935, self.vmt); self.put(OTHER, self.vmt)
        self.put(YEAR, YEAR+4); self.put(DATE, DATE+4); self.put(DIR, DIR_TEXT)
        self.picture, self.heap, self.calls, self.labels, self.dates = picture, HEAP, [], [], []
        vm.hook_add(UC_HOOK_CODE, self.stand_in, begin=STUBS, end=STUBS+0x1000)
        self.stops = {self.at[n]: n for n in STOPS}
        vm.hook_add(UC_HOOK_CODE, lambda m, a, s, d: m.emu_stop() if a in self.stops else None, begin=STUBS, end=STUBS+0x1000)

    def put(self, address, value, size=4): self.vm.mem_write(address, value.to_bytes(size, "little"))
    def get(self, address): return struct.unpack("<I", self.vm.mem_read(address, 4))[0]

    def stand_in(self, vm, address, size, data):
        name = next((n for n, a in self.at.items() if a == address), None)
        if name is None or name in STOPS: return
        eax, ecx, edx = (vm.reg_read(r) for r in (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX))
        self.calls.append((name, eax, edx & 0xFF if name.startswith(("set_auto", "set_trans", "set_show", "file")) else edx))
        result = eax
        if name == "encode_date":
            self.dates.append((eax & 0xFFFF, edx & 0xFFFF, ecx & 0xFFFF)); return      # runs its fld
        if name == "create":
            self.heap += 0x200; result = self.heap; self.put(result, eax); self.labels.append(result)
            count = self.get(LIST+8); self.put(LIST+0x10+4*count, result); self.put(LIST+8, count+1)
        elif name == "cat3": self.put(eax, 0xC0DE)                            # the path string
        elif name == "file_exists": result = int(self.picture)
        elif name == "assign": self.put(eax, edx)
        elif name in ("set_left", "set_top", "set_width", "set_height"):
            self.put(eax+{"set_left": 0x50, "set_top": 0x54, "set_width": 0x58, "set_height": 0x5C}[name], edx)
        elif name == "set_parent": self.put(eax+0x30, edx)
        sp = vm.reg_read(UC_X86_REG_ESP)
        vm.reg_write(UC_X86_REG_EAX, result); vm.reg_write(UC_X86_REG_ECX, 0xDEAD0001)
        vm.reg_write(UC_X86_REG_EDX, 0xDEAD0002)                                      # volatile
        vm.reg_write(UC_X86_REG_ESP, sp+4); vm.reg_write(UC_X86_REG_EIP, self.get(sp))

    def text(self, pointer):
        return bytes(self.vm.mem_read(pointer, 2*self.get(pointer-4))).decode("utf-16-le")

    def run(self, start, **regs):
        values = dict(ebx=0x11111111, esi=0x22222222, edi=0x33333333, ebp=0x44444444, esp=STACK+0x8000)
        values.update(regs)
        for name, value in values.items(): self.vm.reg_write(REGS[name], value)
        self.vm.emu_start(start, 0xFFFFFFFF, count=200000)
        return self.stops.get(self.vm.reg_read(UC_X86_REG_EIP)), {r: self.vm.reg_read(r) for r in
                                                                   (UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI)}


class LabelTests(unittest.TestCase):
    def test_new_game_makes_the_labels_over_the_new_boxes_once(self):
        w = World()
        stop, regs = w.run(PAGE+0x400, ebx=FORM)
        self.assertEqual(stop, "after_image")
        self.assertEqual(w.vm.reg_read(UC_X86_REG_EAX), PANEL)                     # the replaced load
        self.assertEqual(regs[UC_X86_REG_EBX], FORM)
        self.assertIn(("load_picture", PICTURE, 0xC0DE), w.calls)
        self.assertEqual(len(w.labels), 4)
        for label, (year, (left, top)) in zip(w.labels, sy.PLACES.items()):
            self.assertEqual(w.get(label+0xC), sy.MAGIC | year)
            self.assertEqual([w.get(label+o) for o in (0x30, 0x50, 0x54, 0x58, 0x5C)],
                             [PANEL, left, top, sy.WIDTH, sy.HEIGHT])
            self.assertEqual((w.get(label+0x120), w.get(label+0x124)), (0x69C6C4, FORM))   # lb1900Click, the form
            self.assertTrue(w.text(w.get(label+0x90)).startswith(f"Start a game in {year}"))
            self.assertIn(("set_auto_size", label, 0), w.calls)
            self.assertIn(("set_transparent", label, 1), w.calls)
            self.assertIn(("set_show_hint", label, 1), w.calls)
        calls = len(w.calls)
        self.assertEqual(w.run(PAGE+0x440, ebx=FORM)[0], "after_button")         # the other New game path
        self.assertEqual((len(w.labels), [c[0] for c in w.calls[calls:]]), (4, ["clear"]))

    def test_without_the_picture_the_year_screen_stays_native(self):
        w = World(picture=False)
        self.assertEqual(w.run(PAGE+0x440, ebx=FORM)[0], "after_button")
        self.assertEqual((w.labels, [c[0] for c in w.calls]), ([], ["cat3", "file_exists", "clear"]))


class YearTests(unittest.TestCase):
    def click(self, sender, tag=0):
        w = World()
        if sender not in (0, LB1935): w.put(sender, w.vmt); w.put(sender+0xC, tag)
        w.vm.mem_write(DATA+0x2040, struct.pack("<d", 21916.0))                     # 1 January 1960
        stop, _ = w.run(PAGE+0x480, ebx=FORM, edx=sender, esi=YEAR+4)             # ESI: the year itself
        return stop, w.get(YEAR+4), struct.unpack("<d", w.vm.mem_read(DATE+4, 8))[0], w.dates

    def test_a_new_label_sets_its_year_and_date_and_takes_the_1935_branch(self):
        self.assertEqual(self.click(OTHER, sy.MAGIC | 1960), ("after_year", 1960, 21916.0, [(1960, 1, 1)]))

    def test_native_and_unknown_senders_keep_their_paths(self):
        self.assertEqual(self.click(LB1935)[0], "native_1935")
        for sender, tag in ((OTHER, 0), (OTHER, 0x52570000 | 1960), (0, 0)):
            self.assertEqual(self.click(sender, tag), ("no_year", 0, 0.0, []))


class StartTests(unittest.TestCase):
    def flags(self, year):
        w = World()
        w.put(YEAR+4, year); w.put(DATA+0x2100, MAIN)
        stop, _ = w.run(PAGE+0x500, eax=YEAR+4, edi=DATA+0x2100)
        return stop, bytes(w.vm.mem_read(MAIN+0x4A4B, 7))

    def test_later_years_mark_the_1935_notices_seen(self):
        self.assertEqual(self.flags(1935), ("flags_1935", bytes(7)))
        self.assertEqual(self.flags(1920), ("after_flags", bytes(7)))
        self.assertEqual(self.flags(1960), ("after_flags", b"\x01\0\0\0\0\0\x01"))

    def test_start_tech_uses_the_start_year(self):
        """The native start code from 0x6997F4 with the in-place patch: SetTechForYear(main, year) from 1935."""
        tech = next(p for p in sy.build(PAGE, sy.discover(BLOB, BASE))[1] if p["label"].endswith("start year"))
        for year, expected in ((1920, None), (1935, 1935), (1960, 1960), (2000, 2000)):
            vm = Uc(UC_ARCH_X86, UC_MODE_32)
            vm.mem_map(BASE, (len(BLOB)+0xFFF) & ~0xFFF); vm.mem_write(BASE, BLOB)
            vm.mem_write(tech["address"], bytes.fromhex(tech["replacement"]))
            vm.mem_map(DATA, 0x10000); vm.mem_map(0x9F7000, 0x1000)                   # data globals past the text
            vm.mem_write(0x9F7328, struct.pack("<I", DATA)); vm.mem_write(DATA, struct.pack("<I", year))
            vm.mem_write(DATA+0x100, struct.pack("<I", MAIN))
            vm.reg_write(UC_X86_REG_EDI, DATA+0x100); vm.reg_write(UC_X86_REG_ESP, DATA+0x8000)
            seen = []
            vm.hook_add(UC_HOOK_CODE, lambda m, a, s, d: (seen.append((m.reg_read(UC_X86_REG_EAX), m.reg_read(UC_X86_REG_EDX))),
                                                         m.emu_stop()), begin=0x7E1698, end=0x7E1698)
            vm.emu_start(0x6997F4, 0x69980F, count=50)
            self.assertEqual(seen, [] if expected is None else [(MAIN, expected)], year)


class FileTests(unittest.TestCase):
    def test_later_years_read_their_own_nation_and_map_files(self):
        for kind, offset, native, name in (("nations", 0x580, "bnat_1935", "BNat{}.dat"),
                                           ("map", 0x640, "mapdata_1920", "MapData{}.dat")):
            for year in (1920, 1935)+sy.YEARS:
                w = World(); w.put(YEAR+4, year)
                stop, _ = w.run(PAGE+offset, edx=0x5150, ebp=STACK+0x4000)
                ecx, eax, edx = (w.vm.reg_read(r) for r in (UC_X86_REG_ECX, UC_X86_REG_EAX, UC_X86_REG_EDX))
                self.assertEqual((stop, edx), ("after_"+("nations" if kind == "nations" else "map"), 0x5150))
                self.assertEqual(eax, STACK+0x4000-(4 if kind == "nations" else 0x14))   # the native result variable
                if year in sy.YEARS: self.assertEqual(w.text(ecx), "\\Data\\"+name.format(year))
                else: self.assertEqual(ecx, NATIVE_FILES[native])


class DataTests(unittest.TestCase):
    """The package's nation and possession files for the later starts."""
    PACKAGE = HERE.parent/"Library"/"timeline-2030"/"Files"/"Data"
    GAME = HERE.parent.parent/"Data"

    def nations(self, year):
        import re
        text = (self.PACKAGE/f"BNat{year}.dat").read_text(encoding="utf-8-sig")
        out = {}
        for body in re.split(r"^\[Nation\d\]\s*$", text, flags=re.M)[1:]:
            values = {}
            for line in body.splitlines():
                if "=" in line: values.setdefault(*line.split("=", 1))
            out[values["Name"]] = values
        return out


class SuperstateTests(DataTests):
    """The 2000 start: ten blocs, each with its own war, ship and officer files."""
    YEARS = (sy.SUPERSTATES,)

    def world(self):
        import superstates_data as blocs
        return blocs.MODERN, lambda game, files: blocs.write(game, files)

    def test_blocs_have_one_home_area_owned_land_and_resolving_names(self):
        for year in self.YEARS: self.check(year)

    def check(self, year):
        import re
        world = self.world()[0]
        nations = self.nations(year)
        self.assertEqual(set(nations), {b["name"] for b in world["blocs"].values()})
        asian = set(world["asian"])
        text = (self.PACKAGE/f"MapData{year}.dat").read_text(encoding="utf-8-sig")
        land = re.findall(r"Owner=(.*)\r?\n.*Name=(.*)\r?\n.*Value=(.*)", text)
        self.assertLessEqual({o for o, _, _ in land}, set(nations) | {"Neutral"})
        for name, values in nations.items():
            homes = [n for o, n, v in land if o == name and v == "200"]                    # GetHomeProvince
            self.assertEqual(len(homes), 1, name)
            self.assertIn(homes[0], qol.HOMELANDS, name)                                  # closed to invasion
            for key in ("Friend", "Enemy1", "Enemy2"): self.assertIn(values.get(key) or name, nations, (name, key))
            self.assertTrue((self.PACKAGE.parent/"Flags"/values["FlagFileName"]).exists()
                            or (self.GAME.parent/"Flags"/values["FlagFileName"]).exists(), name)
            for kind in ("WarInfo20.dat", "WarInfo.dat", "ShipNames20.dat", "ShipNames.dat", "Names.txt"):
                self.assertTrue((self.PACKAGE/(name+kind)).exists(), name+kind)
            war = (self.PACKAGE/(name+"WarInfo20.dat")).read_bytes()
            self.assertTrue(war.startswith(b"[Nation1]\r\n"))                               # a plain INI file
            enemies = re.findall(r"NationName=(.*)\r", war.decode("cp1252"))
            self.assertEqual((len(enemies), len(set(enemies))), (8, 8), name)
            self.assertLessEqual(set(enemies), set(nations)-{name}, name)
            # The player's file picks the campaign's nations: Southeast Asia only for Asian players.
            for_asians = world["skip"][1]
            self.assertEqual(for_asians in enemies, name in asian-{for_asians}, name)
            self.assertIn(values["GGP"], "01", name)
            self.assertGreaterEqual(int(values["BaseResources"]), 2500, name)
            self.assertEqual(war.count(b"Mission"), 88)
            ships = (self.PACKAGE/(name+"ShipNames20.dat")).read_text(encoding="utf-8-sig")
            for section in ("BB", "DD", "CV", "XX", "Aircraft names", "Aircraft manufacturers"):
                self.assertRegex(ships, r"\["+section+r"\]\n\S", (name, section))
        native = {p.name for p in self.GAME.glob("*WarInfo*.dat")} if self.GAME.exists() else set()
        self.assertFalse({n+"WarInfo20.dat" for n in nations} & native-{p.name for p in self.PACKAGE.iterdir()})

    def test_positions_use_the_game_s_degree_minute_second_text(self):
        import superstates_data as blocs
        self.assertEqual(blocs.position(4.693055, 53.310833), "44135E 531839N")       # a native North Sea point
        self.assertEqual(blocs.position(-73.578333, 20.207222), "733442W 201226N")
        self.assertEqual(blocs.position(2.35, 0.75), "22100E 04500N")              # "4500N" is an error in the game
        self.assertEqual(blocs.position(0, 0), "00000E 00000N")

    def test_package_files_match_the_generator(self):
        write = self.world()[1]
        if not (self.GAME/"USAShipNames20.dat").exists(): self.skipTest("game data not present")
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as folder:
            files = Path(folder)/"Library"/"timeline-2030"/"Files"
            (files/"Data").mkdir(parents=True)
            qol = Path(folder)/"Library"/"campaign-qol"/"Files"/"Data"; qol.mkdir(parents=True)
            shutil.copy(HERE.parent/"Library"/"campaign-qol"/"Files"/"Data"/"MapData.dat", qol/"MapData.dat")
            for name in write(self.GAME.parent, files):
                self.assertEqual((files/"Data"/name).read_bytes(), (self.PACKAGE/name).read_bytes(), name)


class ColdWarTests(SuperstateTests):
    """The 1947, 1960 and 1980 starts: Cold War blocs and five minor powers."""
    YEARS = (1947, 1960, 1980)

    def world(self):
        import coldwar_data as cold
        return cold.WORLD, cold.write

    def test_history_moves_between_the_years(self):
        import re
        owner = {}
        for year in self.YEARS:
            text = (self.PACKAGE/f"MapData{year}.dat").read_text(encoding="utf-8-sig")
            owner[year] = {n.strip(): o.strip() for o, n in re.findall(r"Owner=(.*)\r?\n.*Name=(.*)", text)}
        self.assertEqual([owner[y]["Kenya"] for y in self.YEARS], ["European NATO", "European NATO", "Neutral"])
        self.assertEqual([owner[y]["Egypt"] for y in self.YEARS], ["European NATO", "Neutral", "Neutral"])
        self.assertEqual({owner[y]["Eastern Germany"] for y in self.YEARS}, {"Warsaw Pact"})
        self.assertEqual({owner[y]["Persia"] for y in self.YEARS}, {"Iran"})
        economy = [int(self.nations(y)["Brazil"]["BaseResources"]) for y in self.YEARS]
        self.assertEqual(economy, sorted(economy))

    test_positions_use_the_game_s_degree_minute_second_text = None


class DiscoveryTests(unittest.TestCase):
    def test_plans_are_same_size_and_avoid_legacy_fleet(self):
        import legacy_fleet
        plans = sy.build(PAGE, sy.discover(BLOB, BASE))[1]
        self.assertEqual(len(plans), 8)
        self.assertTrue(all(len(p["original"]) == len(p["replacement"]) for p in plans))
        legacy = legacy_fleet.discover(BLOB, BASE, PAGE)[0]
        spans = sorted((p["address"], p["address"]+len(p["original"])//2) for p in plans+legacy)
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])))

    def test_aslr_and_changed_code(self):
        delta, moved = 0x400000, bytearray(BLOB)
        for offset in audit.text_relocations():
            value = struct.unpack_from("<I", moved, offset)[0]
            struct.pack_into("<I", moved, offset, (value+delta) & 0xFFFFFFFF)
        info = sy.discover(bytes(moved), BASE+delta)
        self.assertEqual((info["click"], info["set_transparent"]), (0x69C6C4+delta, 0x476CFC+delta))
        for address, _, _ in sy.WINDOWS:
            changed = bytearray(BLOB); changed[address-BASE+1] ^= 1
            with self.assertRaisesRegex(ValueError, "refuse changed"): sy.discover(bytes(changed), BASE)


if __name__ == "__main__":
    unittest.main()

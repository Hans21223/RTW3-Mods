"""Guided shells and torpedoes, hypersonic missile speed and EMALS, executed on the patched native sites."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import modern_combat as combat
import modern_extension as extension
import modern_railgun as railgun
import modern_research as modern
import modern_tree as tree

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
CODE, DATA, STACK = 0x2000000, 0x1300000, 0x1500000
SHIP, TARGET, NATION, MAIN, OBJECT = DATA+0x1000, DATA+0x2000, DATA+0x8000, DATA+0x9000, DATA+0xB000
FRAME, PRELUDE, CHANCE = STACK+0x9000, CODE+0x2F000, CODE+0x2F100   # past the modern research allocation


class World:
    def __init__(self, owned=()):
        self.vm = vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address, size in ((0, 0x1000), (0x300000, 0x800000), (DATA, 0x20000), (STACK, 0x10000), (CODE, 0x30000)):
            vm.mem_map(address, size)
        vm.mem_write(0x301000, BLOB)
        details = modern.discover(BLOB, 0x301000)
        self.info = details["combat"]
        blocks, plans, _ = modern.build(CODE, details)
        for item in blocks+[dict(address=p["address"], bytes=p["replacement"]) for p in plans]:
            vm.mem_write(item["address"], bytes.fromhex(item["bytes"]))
        self.railgun = {b["name"][9:]: b["address"] for b in blocks if b["name"].startswith("Railgun: ")}
        self.doctrine = next(b["address"] for b in blocks if b["name"] == "Shell doctrine: table")
        self.put(self.doctrine, NATION); self.put(self.doctrine+4, 3); self.put(NATION+0x1B5, 1000000)   # the player fires both
        self.owned, self.catapults, self.distance = set(owned), 0, 0
        self.put(self.info["main"], DATA+0x200); self.put(DATA+0x200, MAIN); self.put(MAIN+0x3204, NATION)
        n = self.info
        self.stubs = {n["has_research"]: lambda: int(self.reg("EAX") == NATION and self.reg("EDX") in self.owned),
                      n["nation"]: lambda: NATION if (self.reg("EAX"), self.reg("EDX")) == (MAIN, 3) else 0,
                      n["catapults"]: lambda: self.catapults, n["distance"]: lambda: self.distance}
        vm.hook_add(UC_HOOK_CODE, self.boundary)

    def put(self, address, value, size=4): self.vm.mem_write(address, (value & (1 << 8*size)-1).to_bytes(size, "little"))
    def get(self, address): return int.from_bytes(self.vm.mem_read(address, 4), "little")
    def reg(self, name): return self.vm.reg_read(globals()["UC_X86_REG_"+name])

    def boundary(self, vm, address, size, unused):
        if address in self.stubs:
            result = self.stubs[address]()
            sp = vm.reg_read(UC_X86_REG_ESP)
            vm.reg_write(UC_X86_REG_EAX, result); vm.reg_write(UC_X86_REG_EIP, self.get(sp)); vm.reg_write(UC_X86_REG_ESP, sp+4)

    def run(self, start, stop, **registers):
        defaults = dict(EAX=0, EBX=0x2345, ECX=0x1234, EDX=0x3456, ESI=0x4567, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000)
        for name, value in {**defaults, **registers}.items(): self.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        self.vm.emu_start(start, stop, count=100000)
        assert self.reg("EIP") == stop and self.reg("ESP") == STACK+0x8000
        return self


def site(world, name): return next(s["address"] for s in world.info["sites"] if s["name"] == name)


class GuidedShellTests(unittest.TestCase):
    def test_the_player_needs_the_shell_doctrine_and_pays_per_salvo(self):
        owned = {tree.GUIDED_SHELLS[0]}
        self.assertEqual(self.chance(owned, 5, flags=0), 12.5)                 # researched, not chosen
        self.assertEqual(self.chance(owned, 5, flags=2), 12.5)                 # nuclear only
        self.assertEqual((self.chance(owned, 5, flags=1), self.funds), (25.0, 1000000-1))

    def chance(self, owned, calibre, battery=1, flags=3):
        world = World(owned); world.put(world.doctrine+4, flags)
        world.vm.mem_write(SHIP, bytes(0x100)); world.put(SHIP+0x14, 3); world.put(SHIP+0x69+4*battery, calibre)
        world.put(FRAME-0x24, SHIP); world.put(FRAME+0x18, battery)
        world.vm.mem_write(CHANCE, struct.pack("<f", 12.5))
        world.vm.mem_write(PRELUDE, b"\xd9\x05"+struct.pack("<I", CHANCE)+b"\xe9"+struct.pack("<i", site(world, "shells")-(PRELUDE+11)))
        world.run(PRELUDE, world.info["shells_back"], EDI=0x5678)
        self.assertEqual((world.reg("EDI"), world.reg("EBX")), (0x5678, 0x2345))
        self.funds = world.get(NATION+0x1B5)
        return struct.unpack("<f", world.vm.mem_read(FRAME-0x38, 4))[0]

    def test_guns_of_six_inches_and_less_hit_twice_as_often_with_the_research(self):
        owned = {tree.GUIDED_SHELLS[0]}
        self.assertEqual(self.chance(owned, 5), 25.0)
        self.assertEqual(self.chance(owned, 6, battery=2), 25.0)      # secondary guns too
        self.assertEqual(self.chance(owned, 8), 12.5)
        self.assertEqual(self.chance(set(), 5), 12.5)
        self.assertEqual(self.chance(owned, 0), 12.5)

    def test_guns_over_six_inches_hit_half_again_as_often_with_heavy_guided_shells(self):
        heavy = {tree.GUIDED_SHELLS[0], tree.HEAVY_GUIDED_SHELLS[0]}
        self.assertEqual(self.chance(heavy, 16), 18.75)
        self.assertEqual(self.chance(heavy, 5), 25.0)
        self.assertEqual(self.chance({tree.GUIDED_SHELLS[0]}, 16), 12.5)


class RailgunTagTests(unittest.TestCase):
    def execute(self, world, start, stop, **registers):
        for name, value in dict(dict(EAX=0x77, EBX=0x2345, ESP=STACK+0x8000, EBP=FRAME), **registers).items():
            world.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        world.vm.emu_start(start, stop, count=2000)
        self.assertEqual(world.reg("EIP"), stop)

    def text(self, world, pointer): return bytes(world.vm.mem_read(pointer, 2*world.get(pointer-4))).decode("utf-16-le")

    def log(self, name, battery, railgun, bits=0):
        world = World(); world.vm.mem_write(SHIP, bytes(0xE20)); world.put(SHIP+combat.RAILGUN_BYTE, 2 if railgun else 1, 1)
        size = extension.CLASSES["fighting"][1]   # a battle ship with extension data (railgun secondaries)
        world.put(SHIP, extension.NATIVE["fighting_vmt"]); world.put(SHIP+size, bits); world.put(SHIP+size+4, extension.MAGIC ^ (SHIP+size))
        world.put(FRAME-0x24, SHIP); world.put(FRAME+0x18, battery)
        self.execute(world, site(world, name), site(world, name)+5)
        self.assertEqual((world.reg("ESP"), world.reg("EAX")), (STACK+0x8000-4, 0x77))
        return self.text(world, world.get(STACK+0x8000-4))

    def test_railgun_main_batteries_fire_railguns_in_the_battle_log(self):
        self.assertEqual(self.log("log_own", 1, True), "in railguns at ")
        self.assertEqual(self.log("log_own", 1, False), "in guns at ")
        self.assertEqual(self.log("log_own", 2, True), "in guns at ")     # secondary guns are never railguns
        self.assertEqual(self.log("log_seen", 1, True), " railguns at ")
        self.assertEqual(self.log("log_seen", 1, False), " guns at ")
        sec, ter = extension.SECONDARY_RAIL_BIT, extension.TERTIARY_RAIL_BIT
        self.assertEqual(self.log("log_own", 2, False, sec), "in railguns at ")     # railgun secondaries
        self.assertEqual(self.log("log_seen", 3, False, ter), " railguns at ")
        self.assertEqual(self.log("log_own", 3, False, sec), "in guns at ")

    def test_railgun_main_batteries_show_eml_in_the_three_ship_information_screens(self):
        form, label = DATA+0xC000, DATA+0xC800
        for name, _, size, ship, form_local, temp in combat.TAGS:
            for railgun in (True, False):
                world = World(); calls = []; n = world.info
                world.vm.mem_write(SHIP, bytes(0xC00)); world.put(SHIP+combat.RAILGUN_BYTE, 2 if railgun else 0, 1)
                world.put(FRAME+ship, SHIP); world.put(FRAME+form_local, form); world.put(form+combat.LABEL, label)
                world.put(form+0x5C8, 0x4444); world.put(SHIP+0xAE, 0x5555)       # what the replayed loads read
                def get_text(): calls.append(("get", world.reg("EAX"), world.reg("EDX"))); world.put(world.reg("EDX"), 0x1111); return 0
                def cat(): calls.append(("cat", world.reg("EAX"), self.text(world, world.reg("EDX")))); return 0
                def set_text(): calls.append(("set", world.reg("EAX"), world.reg("EDX"))); return 0
                world.stubs.update({n["get_text"]: get_text, n["str_cat"]: cat, n["set_text"]: set_text})
                start = site(world, name); self.execute(world, start, start+size)
                self.assertEqual(calls, [("get", label, FRAME+temp), ("cat", FRAME+temp, " (EML)"), ("set", label, 0x1111)]
                                 if railgun else [], name)
                if name == "tag_battle":
                    self.assertEqual((world.reg("ESP"), world.get(STACK+0x8000-4)), (STACK+0x8000-4, 0x6D1D78))
                elif name == "tag_info": self.assertEqual(world.reg("EAX"), 0x4444)
                else: self.assertEqual((world.reg("EAX"), world.reg("EBX")), (SHIP, 0x5555))


class GuidedTorpedoTests(unittest.TestCase):
    def launch(self, world, torpedo, nation_index):
        world.put(SHIP+0x14, nation_index)
        world.run(site(world, "torpedo_launch"), world.info["launch_back"], EBX=torpedo, ESI=SHIP)
        self.assertEqual(world.reg("EAX"), nation_index*0xA7)        # the replayed native imul

    def hit_distance(self, world, torpedo):
        world.put(FRAME-0x18, 200); world.put(FRAME-0x14, 100)
        world.run(site(world, "torpedo_hit"), world.info["hit_back"], EBX=torpedo, ECX=7, EDI=8, ESI=SHIP)   # no ATT
        self.assertEqual((world.reg("EAX"), world.reg("ECX"), world.reg("EDI")), (200, 7, 8))
        return world.get(FRAME-0x14)

    def test_torpedoes_from_a_researching_nation_hit_from_further_away(self):
        world = World({tree.GUIDED_TORPEDOES[0]})
        self.launch(world, OBJECT, 3)
        self.assertEqual(self.hit_distance(world, OBJECT), 250)
        self.assertEqual(self.hit_distance(world, OBJECT+0x100), 100)    # another torpedo
        self.launch(world, OBJECT, 4)                                     # same address reused, no research
        self.assertEqual(self.hit_distance(world, OBJECT), 100)
        world = World()
        self.launch(world, OBJECT, 3)
        self.assertEqual(self.hit_distance(world, OBJECT), 100)


class HypersonicSpeedTests(unittest.TestCase):
    def step(self, hyper, distance, target=TARGET, native=2000):
        world = World(); world.distance = distance
        world.vm.mem_write(OBJECT, bytes(0x60)); world.put(OBJECT+0x34, target)
        if hyper:
            table = world.railgun["missile_table"]
            world.put(table+8, OBJECT); world.put(table+12, railgun.HYPER_BIT)
        world.run(site(world, "missile_step"), world.info["step_back"], EAX=native, EBX=OBJECT)
        self.assertEqual(world.reg("EAX"), STACK+0x8000+8)               # the replayed lea eax, [esp+8]
        return world.reg("ESI")

    def test_hypersonic_missiles_fly_five_times_as_fast_but_never_past_the_target(self):
        self.assertEqual(self.step(True, 100000), 10000)
        self.assertEqual(self.step(True, 6000), 5000)       # ends half a native step short of the target
        self.assertEqual(self.step(True, 2500), 2000)       # already close: never slower than native
        self.assertEqual(self.step(True, 0, target=0), 10000)
        self.assertEqual(self.step(False, 100000), 2000)


class EMALSTests(unittest.TestCase):
    def spot(self, owned, catapults, laid_down):
        world = World(owned); world.catapults = catapults
        world.vm.mem_write(SHIP, bytes(0x100)); world.put(SHIP+0x14, 3); world.put(SHIP+0xE4, laid_down)
        world.run(site(world, "spot"), world.info["spot_back"], EBX=SHIP, ESI=40)
        return world.reg("ESI")

    def test_each_catapult_adds_four_spot_on_new_emals_carriers(self):
        emals = {tree.EMALS[0]}
        self.assertEqual(self.spot(emals, 2, 2020), 48)
        self.assertEqual(self.spot(emals, 2, tree.EMALS[1]-1), 42)
        self.assertEqual(self.spot(set(), 2, 2020), 42)
        self.assertEqual(self.spot(emals, 0, 2020), 40)

    def test_ski_jump_flight_decks_ready_more_aircraft_without_catapults(self):
        spot = tree.SKI_JUMP[1]
        # JetCapable byte: 1 jet capable, 3 jet capable with the designer's ski jump
        for deck, jet, catapults, expected in ((1, 3, 0, 40+spot), (1, 1, 0, 40), (1, 0, 0, 40), (0, 3, 0, 40),
                                               (1, 3, 2, 42), (1, 2, 0, 40+spot)):
            world = World(); world.catapults = catapults
            world.vm.mem_write(SHIP, bytes(0xA00)); world.put(SHIP+0x14, 3); world.put(SHIP+0xE4, 1960)
            world.put(SHIP+0x9D9, deck, 1); world.put(SHIP+0x9DF, jet, 1)
            world.run(site(world, "spot"), world.info["spot_back"], EBX=SHIP, ESI=40)
            self.assertEqual(world.reg("ESI"), expected, (deck, jet, catapults))

    def test_heavy_jets_need_24000_tons_with_emals_instead_of_30000(self):
        for owned, tons, allowed in (({tree.EMALS[0]}, 25000, True), (set(), 25000, False), (set(), 30000, True),
                                     ({tree.EMALS[0]}, 23000, False)):
            world = World(owned); world.put(OBJECT+0x2B, tons)
            world.run(site(world, "heavy_jets"), world.info["jets_back"], EAX=OBJECT)
            flags = world.reg("EFLAGS")
            self.assertEqual(bool(flags & 0x80) == bool(flags & 0x800), allowed, (owned, tons))   # jge: SF == OF
            self.assertEqual(world.reg("EAX"), OBJECT)

    def test_a_ski_jump_lets_angled_decks_without_catapults_take_heavy_jets(self):
        # TCampaignShip+0F3h is the design's JetCapable byte: bit 1 is the ski jump. Research alone no longer counts.
        for jet, catapults, allowed in ((3, 0, True), (1, 0, False), (1, 2, True), (3, 2, True), (2, 0, True)):
            world = World({tree.SKI_JUMP[0]}); world.put(OBJECT+0xEF, catapults); world.put(OBJECT+0xF3, jet, 1)
            world.run(site(world, "jets_ui"), world.info["jets_ok" if allowed else "jets_refused"], EBX=OBJECT)
            world = World({tree.SKI_JUMP[0]}); world.put(OBJECT+0xEF, catapults); world.put(OBJECT+0xF3, jet, 1)
            world.run(site(world, "jets_unit"), world.info["unit_angled" if allowed else "unit_refused"], ESI=OBJECT, EDI=SHIP)
            self.assertEqual((world.reg("ESI"), world.reg("EDI"), world.reg("EBX")), (OBJECT, SHIP, 0x2345))


if __name__ == "__main__":
    unittest.main()

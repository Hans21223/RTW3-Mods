"""ASW torpedoes, composite superstructures, USVs, nuclear shells and frigates on the patched native sites."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn.x86_const import *
from test_modern_combat import World, BLOB, SHIP, NATION, DATA, STACK, FRAME
from test_modern_recon import execute, call
import modern_extension as extension
import modern_navy as navy
import modern_railgun as rail
import modern_research as modern
import modern_tree as tree
import shell_doctrine as sd

NAVY = modern.discover(BLOB, 0x301000)["navy"]
LIST, ITEMS, MOUNTS, TEXT, YEAR = DATA+0xD000, DATA+0xD100, DATA+0xD200, DATA+0xE000, DATA+0xE800


def site(name): return next(s["address"] for s in NAVY["sites"] if s["name"] == name)


def text(world, pointer): return bytes(world.vm.mem_read(pointer, 2*world.get(pointer-4))).decode("utf-16-le")


def literal(world, address, value):
    world.vm.mem_write(address, struct.pack("<HHiI", 1200, 2, -1, len(value))+value.encode("utf-16-le")+b"\0\0")
    return address+12


class ASWTests(unittest.TestCase):
    def asw(self, owned, kind=9, mounts=((0, 2),), drive=2, year=2000):
        world = World(owned); world.vm.mem_write(SHIP, bytes(0xC00)); world.put(SHIP+0x9D3, kind, 1)
        world.put(SHIP+0x9D4, drive, 1); world.put(SHIP+0xB28, year)
        world.put(SHIP+0x9E, LIST); world.put(LIST+4, ITEMS); world.put(LIST+8, len(mounts))
        for i, (mount_type, tubes) in enumerate(mounts):
            mount = MOUNTS+i*0x40; world.put(ITEMS+4*i, mount); world.put(mount+0xE, mount_type, 1); world.put(mount+4, tubes)
        execute(world, site("asw"), NAVY["asw_back"], EBX=SHIP, EDI=NATION, ESI=3)
        self.assertEqual((world.reg("EBX"), world.reg("EDI"), world.reg("ESP")), (SHIP, NATION, STACK+0x8000))
        return world.reg("ESI")

    def test_torpedo_mounts_and_vls_banks_add_asw_value_with_research(self):
        torpedo, vls = tree.ASW_TORPEDOES, tree.VL_ASW
        self.assertEqual(self.asw({torpedo}), 5)
        self.assertEqual(self.asw(set()), 3)
        self.assertEqual(self.asw({torpedo, vls}, mounts=((5, 32), (0, 2))), 7)
        self.assertEqual(self.asw({vls}, kind=4, mounts=((5, 32),)), 5)            # cruisers too
        self.assertEqual(self.asw({torpedo}, kind=15), 5)                           # frigate_type.py's FF
        self.assertEqual(self.asw({vls}, mounts=((5, 4),)), 3)                      # a launcher, not a VLS bank
        self.assertEqual(self.asw({torpedo, vls}, kind=0, mounts=((0, 2), (5, 32))), 3)   # battleships unchanged


    def test_hybrid_electric_drive_runs_quiet_for_asw(self):
        hybrid, year, bonus = tree.HYBRID
        for owned, kind, drive, built, value in (({hybrid}, 9, 3, year, 3+bonus), ({hybrid}, 10, 4, 2000, 3+bonus),
                                                 ({hybrid}, 9, 2, 2000, 3), ({hybrid}, 9, 3, year-1, 3),
                                                 (set(), 9, 3, 2000, 3), ({hybrid}, 0, 3, 2000, 3)):   # steam, older, battleship
            self.assertEqual(self.asw(owned, kind=kind, drive=drive, year=built), value, (owned, kind, drive, built))


class CompositeTests(unittest.TestCase):
    def ship(self, owned, aluminium=1, year=2000):
        world = World(owned); world.vm.mem_write(SHIP, bytes(0xC00))
        world.put(SHIP+0x9AA, aluminium, 1); world.put(SHIP+0xB28, year); world.put(SHIP+0x14, 3)
        return world

    def test_designer_weight_and_cost_factors(self):
        ident = tree.COMPOSITE[0]
        for owned, year, weight, cost in (({ident}, 2000, 850, 1300), (set(), 2000, 920, 1150), ({ident}, 1990, 920, 1150)):
            world = self.ship(owned, year=year); world.put(SHIP+0xA64, 1000); world.put(SHIP+0xA90, 1000)
            execute(world, 0x939677, 0x93968A, EBX=SHIP)
            self.assertEqual(world.reg("EAX"), weight, (owned, year))
            execute(world, 0x93A3B5, 0x93A3C8, EBX=SHIP)
            self.assertEqual(world.reg("EAX"), cost, (owned, year))
            self.assertEqual(world.reg("ESP"), STACK+0x8000)

    def test_composite_ships_skip_the_aluminium_battle_penalties(self):
        ident = tree.COMPOSITE[0]
        for owned, aluminium, year, penalty in (({ident}, 1, 2000, False), (set(), 1, 2000, True), ({ident}, 0, 2000, False),
                                                ({ident}, 1, tree.COMPOSITE[1]-1, True)):
            for name, skip, paid in (("fire1", 0x9130AC, 0x913090), ("fire3", 0x913521, 0x913504)):
                world = self.ship(owned, aluminium, year)
                world.vm.hook_add(__import__("unicorn").UC_HOOK_CODE, lambda vm, a, s, d: vm.emu_stop() if a in (skip, paid) else None)
                world.vm.reg_write(UC_X86_REG_EAX, SHIP); world.vm.reg_write(UC_X86_REG_ESP, STACK+0x8000)
                world.vm.emu_start(site(name), 0, count=2000)
                self.assertEqual(world.reg("EIP"), paid if penalty else skip, (owned, aluminium, year, name))
                self.assertEqual((world.reg("EAX"), world.reg("ESP")), (SHIP, STACK+0x8000))


class USVTests(unittest.TestCase):
    def test_usv_nations_name_and_design_their_squadrons_as_usvs(self):
        for owned, name, design in ((set(), "MTB ", "\\Data\\Ides\\MTB4.sdf"), ({tree.USV}, "USV ", navy.USV_DESIGN)):
            world = World(owned)
            execute(world, site("usv_name"), site("usv_name")+5, ESI=3, EAX=0x11, ECX=0x22)
            self.assertEqual((text(world, world.reg("EDX")), world.reg("EAX"), world.reg("ECX")), (name, 0x11, 0x22))
            execute(world, site("usv_design"), site("usv_design")+5, ESI=3, EAX=0x11, EDX=0x33)
            self.assertEqual((text(world, world.reg("ECX")), world.reg("EAX"), world.reg("EDX")), (design, 0x11, 0x33))


class NuclearShellTests(unittest.TestCase):
    def test_one_nuclear_hit_per_main_battery_per_battle(self):
        ident, minimum, calibre = tree.NUCLEAR_SHELLS
        size = extension.CLASSES["fighting"][1]
        for owned, battery, main, pushed in (({ident}, 1, 16, [calibre, 16]), (set(), 1, 16, [16, 16]),
                                             ({ident}, 1, 15, [15, 15]), ({ident}, 2, 16, [5, 5])):
            world = World(owned); world.vm.mem_write(SHIP, bytes(0xE30)); world.put(SHIP+0x14, 3)
            world.put(SHIP, extension.NATIVE["fighting_vmt"]); world.put(SHIP+size+4, extension.MAGIC ^ (SHIP+size))
            world.put(SHIP+0x6D, main); world.put(SHIP+0x71, 5)
            for expected in pushed:   # two hits in one battle
                execute(world, site("nuclear"), NAVY["nuclear_back"], EAX=SHIP, EDX=battery)
                self.assertEqual((world.get(STACK+0x8000-4), world.reg("ESP")), (expected, STACK+0x8000-4), (owned, battery, main))
            self.assertEqual(bool(world.get(SHIP+size+extension.BATTLE_FLAGS) & navy.NUCLEAR_USED_BIT), pushed[0] == calibre)
            self.assertEqual(world.get(SHIP+size), 0)                                         # saved data untouched

    def test_every_hit_is_nuclear_under_armageddon(self):
        ident, minimum, calibre = tree.NUCLEAR_SHELLS
        size = extension.CLASSES["fighting"][1]
        world = World({ident}); world.vm.mem_write(SHIP, bytes(0xE20)); world.put(SHIP+0x14, 3)
        world.put(SHIP, extension.NATIVE["fighting_vmt"]); world.put(SHIP+size+4, extension.MAGIC ^ (SHIP+size))
        world.put(SHIP+0x6D, 16); world.put(world.doctrine+sd.SLOTS*8+8, 1)            # Nuclear Armageddon's flag
        funds = world.get(NATION+sd.FUNDS)
        for _ in range(3):
            execute(world, site("nuclear"), NAVY["nuclear_back"], EAX=SHIP, EDX=1)
            self.assertEqual(world.get(STACK+0x8000-4), calibre)
        self.assertEqual(world.get(NATION+sd.FUNDS), funds-3*sd.NUCLEAR_COST)


class NuclearAATests(unittest.TestCase):
    def heavy(self, owned, main=16, flags=3, lasers=None, helicopters=0, rain=False, sea=0):
        world = World(owned); world.vm.mem_write(SHIP, bytes(0xE20)); world.put(SHIP+0x14, 3); world.put(SHIP+0x6D, main)
        world.put(SHIP+0x9E5, helicopters, 1)
        world.put(NAVY["precipitation"], DATA+0x7100); world.put(DATA+0x7100, 1 if rain else rail.CLEAR_WEATHER, 1)
        world.put(NAVY["sea"], DATA+0x7104); world.put(DATA+0x7104, sea)
        if lasers is not None:
            size = extension.CLASSES["fighting"][1]; world.put(SHIP, extension.NATIVE["fighting_vmt"])
            world.put(SHIP+size+4, extension.MAGIC ^ (SHIP+size)); world.put(SHIP+size, 0x100 | lasers)
        world.put(world.doctrine+4, flags)
        record, funds = DATA+0x7000, world.get(NATION+0x1B5)
        def values():   # the native routine: fills the record, drops its two stack arguments
            sp = world.reg("ESP"); assert (world.reg("EAX"), world.get(sp+4), world.get(sp+8)) == (SHIP, record, 1)
            world.put(record, 10); world.put(sp+8, world.get(sp)); world.vm.reg_write(UC_X86_REG_ESP, sp+8); return 0x77
        world.stubs[NAVY["aa_values"]] = values
        world.put(STACK+0x8000-8, record); world.put(STACK+0x8000-4, 1)
        execute(world, site("haa2"), site("haa2")+5, EAX=SHIP, ESP=STACK+0x8000-8, ESI=0x4567, EDI=0x5678)
        self.assertEqual((world.reg("EAX"), world.reg("ESP"), world.reg("ESI"), world.reg("EDI")), (0x77, STACK+0x8000, 0x4567, 0x5678))
        self.assertEqual(world.get(NATION+0x1B5), funds)                          # asking costs nothing
        return world.get(record)

    def test_ships_that_may_fire_nuclear_shells_have_more_heavy_aa(self):
        owned = {tree.NUCLEAR_SHELLS[0]}
        self.assertEqual(self.heavy(owned), 10+navy.NUCLEAR_HAA)
        self.assertEqual((self.heavy(set()), self.heavy(owned, main=15), self.heavy(owned, flags=1)), (10, 10, 10))

    def test_laser_mounts_add_aa_value_against_aircraft(self):
        self.assertEqual((self.heavy(set(), lasers=0), self.heavy(set(), lasers=3)), (10, 10+3*navy.LASER_AA))
        self.assertEqual(self.heavy({tree.NUCLEAR_SHELLS[0]}, lasers=8), 10+navy.NUCLEAR_HAA+8*navy.LASER_AA)

    def test_rain_mist_and_heavy_seas_each_halve_laser_aa(self):
        full = 4*navy.LASER_AA
        self.assertEqual([self.heavy(set(), lasers=4, rain=rain, sea=sea)-10 for rain, sea in
                          ((False, rail.SEA_ROUGH-1), (True, 0), (False, rail.SEA_ROUGH), (True, rail.SEA_ROUGH+2))],
                         [full, full//2, full//2, full//4])

    def test_interceptor_drones_add_aa_value_against_aircraft(self):
        drones, _, value = tree.DRONE_SWARMS
        self.assertEqual(self.heavy({drones}, main=5, helicopters=1), 10+value)
        self.assertEqual((self.heavy(set(), main=5, helicopters=1), self.heavy({drones}, main=5)), (10, 10))
        self.assertEqual(self.heavy({drones}, main=5, lasers=2, helicopters=1), 10+2*navy.LASER_AA+value)


class BBVTests(unittest.TestCase):
    def carrier(self, kind, deck=1, aircraft=12, caller=0x5E2476):
        world = World(); world.vm.mem_write(SHIP, bytes(0xA00))
        world.put(SHIP+0x9D3, kind, 1); world.put(SHIP+0x9D9, deck, 1); world.put(SHIP+0x9E0, aircraft)
        world.put(STACK+0x8000-4, caller)
        execute(world, 0x950090, caller, ESP=STACK+0x8000-4, EAX=SHIP, ECX=0x1234, EDI=0x5678)
        self.assertEqual((world.reg("ESP"), world.reg("ECX"), world.reg("EDI")), (STACK+0x8000, 0x1234, 0x5678))
        return world.reg("EAX")

    def test_flight_deck_battleships_are_carriers_except_in_battle_tactics(self):
        self.assertEqual([self.carrier(kind) for kind in (5, 6, 0, 1, 3, 9)], [1, 1, 1, 1, 0, 0])
        self.assertEqual((self.carrier(0, deck=0), self.carrier(1, aircraft=0)), (0, 0))   # not hybrids
        for site in (navy.BBV_TACTICAL[0], navy.BBV_TACTICAL[-1], 0x92B909):
            self.assertEqual(self.carrier(0, caller=site+5), 0)                          # tactics: a battleship
            self.assertEqual(self.carrier(5, caller=site+5), 1)                          # real carriers unchanged
        self.assertEqual(self.carrier(1, caller=0x963FD8), 1)                            # deck operations

    def test_an_av_with_a_flight_deck_is_a_carrier_for_air_operations(self):
        self.assertEqual((self.carrier(navy.AV), self.carrier(navy.AV, deck=0), self.carrier(navy.AV, aircraft=0)), (1, 0, 0))
        self.assertEqual(self.carrier(navy.AV, caller=navy.BBV_TACTICAL[0]+5), 0)         # tactics: still an AV
        self.assertEqual([self.carrier(kind) for kind in (7, 9)], [0, 0])                # AMC, DD


class FrigateTests(unittest.TestCase):
    def name(self, year, kind=navy.KE):
        world = World(); world.put(NAVY["year"], YEAR); world.put(YEAR, year); world.put(STACK+0x100, 0)
        world.stubs[0x30BCCC] = lambda: world.put(world.reg("EAX"), world.reg("EDX")) or 0   # UStrAsg without the heap
        call(world, 0x9514E0, EAX=kind, EDX=STACK+0x100)
        return text(world, world.get(STACK+0x100))

    def test_ke_reads_ff_from_1975(self):
        self.assertEqual((self.name(1974), self.name(1975), self.name(1990, kind=9)), ("KE", "FF", "DD"))

    def test_the_type_reader_takes_ff_and_ke_as_escorts(self):
        world = World()
        for value in ("FF", "KE"):
            self.assertEqual(call(world, 0x9518FC, EAX=literal(world, TEXT, value)) & 0xFF, navy.KE, value)
        self.assertEqual(call(world, 0x9518FC, EAX=literal(world, TEXT, "DD")) & 0xFF, 9)


if __name__ == "__main__":
    unittest.main()

"""Missile range research, satellite fixes and shipborne UAVs, executed on the patched native sites."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import *
from test_modern_combat import World, BLOB, SHIP, TARGET, DATA, STACK, FRAME, CODE
import modern_research as modern
import modern_sensors as sensors
import modern_tree as tree

RECON = modern.discover(BLOB, 0x301000)["recon"]
STOP, LIST = CODE+0x1F800, DATA+0xD000
SAT, UAV = tree.SATELLITES[0], tree.UAVS


def site(name): return next(s["address"] for s in RECON["sites"] if s["name"] == name)


def execute(world, start, stop, **registers):
    for name, value in dict(dict(EAX=0, EBX=0x2345, ECX=0x1234, EDX=0x3456, ESI=0x4567, EDI=0x5678, EBP=FRAME,
                                 ESP=STACK+0x8000), **registers).items():
        world.vm.reg_write(globals()["UC_X86_REG_"+name], value)
    world.vm.emu_start(start, stop, count=100000)
    assert world.reg("EIP") == stop


def call(world, address, **registers):
    world.put(STACK+0x8000-4, STOP)
    execute(world, address, STOP, ESP=STACK+0x8000-4, **registers)
    assert world.reg("ESP") == STACK+0x8000
    return world.reg("EAX")


class MissileRangeTests(unittest.TestCase):
    LEVEL, FLAG = 5, 1

    def tables(self, put):   # nation 3's range level and flag; the native routine also reads the year (after 1960: x1.2)
        put(RECON["levels"]+3*0x14E, self.LEVEL); put(RECON["flags"]+3*0x14E, self.FLAG, 1)
        put(0x9F7328, STACK+0x100); put(STACK+0x100, 2000)

    def native(self, kind):
        vm = Uc(UC_ARCH_X86, UC_MODE_32); vm.mem_map(0x300000, 0x800000); vm.mem_map(STACK, 0x10000)
        vm.mem_write(0x301000, BLOB)
        self.tables(lambda a, v, size=4: vm.mem_write(a, v.to_bytes(size, "little")))
        vm.mem_write(STACK+0x7FFC, struct.pack("<I", 0x300000)); vm.reg_write(UC_X86_REG_ESP, STACK+0x7FFC)
        vm.reg_write(UC_X86_REG_EAX, 3); vm.reg_write(UC_X86_REG_EDX, kind)
        vm.emu_start(0x91ACCC, 0x300000, count=10000)
        return vm.reg_read(UC_X86_REG_EAX)

    def range(self, owned, kind):
        world = World(owned); self.tables(world.put)
        return call(world, 0x91ACCC, EAX=3, EDX=kind)

    def test_range_research_multiplies_the_native_missile_ranges(self):
        heavy_ssm, light_ssm, heavy_sam, light_sam = (self.native(k) for k in (4, 6, 1, 3))
        self.assertEqual(self.range((), 4), heavy_ssm)                       # the rebuilt wrapper is native
        self.assertEqual(self.range({2324}, 4), heavy_ssm*150//100)
        self.assertEqual(self.range({2324, 2327}, 6), light_ssm*150//100*150//100)
        self.assertEqual(self.range({2325, 2328}, 1), heavy_sam*200//100*150//100)
        self.assertEqual(self.range({2324, 2325}, 3), light_sam)                # light SAMs and torpedoes unchanged
        self.assertEqual(self.range({2325}, 4), heavy_ssm)


class StartDistanceTests(unittest.TestCase):
    def test_missile_era_battles_start_further_apart(self):
        import modern_recon as recon
        for year, native, grown in ((1959, 30000, 30000), (1960, 30000, 45000), (1974, 50000, 75000),
                                    (1975, 30000, 60000), (2030, 50000, 100000), (2030, 90000, recon.START_CAP)):
            world = World(); world.put(0x9F7328, STACK+0x100); world.put(STACK+0x100, year)
            world.put(FRAME-0x74, native)
            execute(world, site("start_distance"), 0x6B160E, ECX=0x1234)
            self.assertEqual((world.get(FRAME-0x74), world.reg("EAX"), world.reg("EDX"), world.reg("ECX")),
                             (grown, grown, 0x66666667, 0x1234), (year, native))


class DatalinkTests(unittest.TestCase):
    STRIKE, CARRIER_SHIP, SHIPS, LOG, LOG_VMT, LOGGED = (DATA+0x11000, DATA+0x11200, DATA+0x11400, DATA+0x11800,
                                                        DATA+0x11900, DATA+0x11A00)

    def test_a_datalink_aims_the_strike_at_the_nearest_spotted_enemy_near_the_old_point(self):
        import modern_recon as recon
        # ships: (side, spotted, type, afloat, distance from the old aim point)
        near, far, unseen, own, sub, sunk = ((1, 1, 0, True, 9000), (1, 1, 0, True, 15000), (1, 0, 0, True, 1000),
                                            (0, 1, 0, True, 500), (1, 1, 14, True, 800), (1, 1, 0, False, 700))
        for owned, ships, picked in (({recon.DATALINK}, (far, near, unseen, own, sub, sunk), 1),
                                     ({recon.DATALINK}, ((1, 1, 0, True, recon.DATALINK_REACH+1),), None),
                                     (set(), (near,), None), ({recon.DATALINK}, (unseen, own, sub, sunk), None)):
            world = World(owned); logged = []
            world.vm.mem_write(self.STRIKE, bytes(0x100)); world.put(self.STRIKE+0x38, 3)
            world.put(self.STRIKE+0x4D, self.CARRIER_SHIP); world.vm.mem_write(self.CARRIER_SHIP, bytes(0xE00))
            world.put(self.CARRIER_SHIP+0xA55, 0)
            for offset, value in ((0x51, 0x111), (0x55, 0x222), (0x59, 0x333)): world.put(self.STRIKE+offset, value)
            addresses = []
            for i, (side, spotted, kind, afloat, distance) in enumerate(ships):
                ship = DATA+0x12000+i*0xE00; addresses.append(ship)
                world.vm.mem_write(ship, bytes(0xE00)); world.put(ship+0xA55, side); world.put(ship+0xD59, spotted)
                world.put(ship+0x9D3, kind, 1)
                for offset in (0, 4, 8): world.put(ship+0xA1C+offset, 0x1000*(i+1)+offset)
            table = dict(zip(addresses, ships))
            world.put(RECON["ships"], self.SHIPS); world.put(self.SHIPS, self.SHIPS+0x10); world.put(self.SHIPS+0x18, len(ships))
            world.stubs.update({RECON["list_get"]: lambda: addresses[world.reg("EDX")],
                                RECON["afloat"]: lambda: int(table[world.reg("EAX")][3]),
                                RECON["distance"]: lambda: table[world.reg("EAX")][4] if world.reg("EDX") == self.STRIKE+0x51 else -1,
                                self.LOGGED: lambda: logged.append(world.reg("ECX")) or 0})
            world.put(RECON["battle_log"], self.LOG); world.put(self.LOG, self.LOG_VMT); world.put(self.LOG_VMT+0x40, self.LOGGED)
            stop = 0x97BABD if picked is not None else 0x97B939
            execute(world, site("datalink"), stop, EBX=self.STRIKE, ESI=0x4567, EDI=0x1111)
            aim = [world.get(self.STRIKE+o) for o in (0x51, 0x55, 0x59)]
            expected = [0x1000*(picked+1)+o for o in (0, 4, 8)] if picked is not None else [0x111, 0x222, 0x333]
            self.assertEqual((aim, logged), (expected, [self.CARRIER_SHIP] if picked is not None else []), (owned, ships))
            self.assertEqual([world.reg(r) for r in ("EBX", "ESI", "EDI", "ESP")], [self.STRIKE, 0x4567, 0x1111 if picked is not None else 0xF, STACK+0x8000])


class SatelliteTests(unittest.TestCase):
    def fix(self, owned, roll=0, spotted=0, kind=1, side=1, in_band=False, listed=False):
        world = World(owned); calls = []
        for ship, nation, team in ((SHIP, 3, 0), (TARGET, 4, side)):
            world.vm.mem_write(ship, bytes(0xE00)); world.put(ship+0x14, nation); world.put(ship+0xA55, team)
        world.put(TARGET+0x9D3, kind, 1); world.put(TARGET+0xD59, spotted); world.put(SHIP+0xAD9, LIST)
        world.put(FRAME-0x1C, SHIP); world.put(FRAME-4, TARGET)
        world.stubs.update({RECON["random"]: lambda: calls.append(("random", world.reg("EAX"))) or roll,
                            RECON["index_of"]: lambda: 0 if listed else -1,
                            RECON["add"]: lambda: calls.append(("add", world.reg("EAX"), world.reg("EDX"))) or 0})
        execute(world, site("satellite"), 0x89AB52 if in_band else 0x89AF15, EFLAGS=0x202 if in_band else 0x246)
        self.assertEqual(world.reg("ESP"), STACK+0x8000)
        return world.get(TARGET+0xD59), calls

    def test_satellite_fixes_far_enemy_surface_ships_for_radar_ships(self):
        self.assertEqual(self.fix({SAT}, roll=4), (1, [("random", 1000), ("add", LIST, TARGET)]))
        self.assertEqual(self.fix({SAT}, roll=5), (0, [("random", 1000)]))
        self.assertEqual(self.fix(set(), roll=0), (0, [("random", 1000)]))
        self.assertEqual(self.fix({SAT}, listed=True), (1, [("random", 1000)]))      # already a contact
        self.assertEqual(self.fix({SAT}, spotted=1), (1, []))
        self.assertEqual(self.fix({SAT}, kind=14), (0, []))                          # submarines stay hidden
        self.assertEqual(self.fix({SAT}, kind=12), (0, []))                          # land targets
        self.assertEqual(self.fix({SAT}, side=0), (0, []))                           # friendly ships
        self.assertEqual(self.fix({SAT}, in_band=True), (0, []))                     # in radar band: native


class UAVTests(unittest.TestCase):
    def ship(self, world, catapults=0):
        world.vm.mem_write(SHIP, bytes(0xE00)); world.put(SHIP+0x14, 3); world.put(SHIP+0x9D3, 1, 1)
        world.catapults = catapults

    def models(self, world, *models):
        """The game's aircraft list: (mark, role, nation index, months of development left, withdrawn) each."""
        items = DATA+0x10100
        world.put(RECON["aircraft_types"], DATA+0x10000); world.put(DATA+0x10004, items); world.put(DATA+0x10008, len(models))
        for i, (mark, role, nation, development, withdrawn) in enumerate(models):
            model = DATA+0x10400+i*0x200
            world.vm.mem_write(model, bytes(0x200))
            world.put(model+sensors.MARK, mark); world.put(model+0x81, role, 1); world.put(model+0x88, nation)
            world.put(model+0x84, development); world.put(model+0x8C, 99 if withdrawn else 0); world.put(items+4*i, model)

    UAV_MARK = sensors.UAV_MARK
    IN_SERVICE = (UAV_MARK, 3, 3, 0, False)
    NOT_YET = ((0, 3, 3, 0, False), (sensors.STEALTH_MARK, 3, 3, 0, False), (UAV_MARK, 3, 4, 0, False),
               (UAV_MARK, 3, 3, 12, False), (UAV_MARK, 3, 3, 0, True), (UAV_MARK, 13, 3, 0, False))
    # a floatplane, another mark, another nation's, unfinished, withdrawn, another role

    def test_ships_with_a_uav_model_in_service_never_stop_or_slow_for_their_scouts(self):
        for models, stop in ((self.NOT_YET, 1), (self.NOT_YET+(self.IN_SERVICE,), 0)):
            for mode in (1, 2):
                world = World({UAV}); self.ship(world); self.models(world, *models)
                self.assertEqual(call(world, 0x918FB8, EAX=SHIP, EDX=mode) & 0xFF, stop, (len(models), mode))

    def test_uav_ships_count_as_catapult_launches_for_the_prompt_and_the_ai(self):
        for name, back in (("ai_count", 0x92A2F6), ("prompt_count", 0x919053)):
            for models, native, count in ((self.NOT_YET, 0, 0), ((self.IN_SERVICE,), 0, 1), (self.NOT_YET, 2, 2)):
                world = World({UAV}); self.ship(world); self.models(world, *models)
                world.stubs[RECON["catapults"]] = lambda: native
                execute(world, site(name), back, EAX=SHIP, ESI=SHIP)
                self.assertEqual((world.reg("EAX"), world.reg("ESP")), (count, STACK+0x8000), (name, len(models)))

    def test_the_launch_prompt_calls_them_uavs(self):
        for models, text in ((self.NOT_YET, "Catapult launch search floatplane(s) from "),
                             ((self.IN_SERVICE,), "Launch search UAV(s) from ")):
            world = World({UAV}); self.ship(world); self.models(world, *models)
            execute(world, site("prompt_text"), 0x91905C, ESI=SHIP, EAX=0x77)
            pointer = world.get(STACK+0x8000-4)
            self.assertEqual((world.reg("ESP"), world.reg("EAX")), (STACK+0x8000-4, 0x77))
            self.assertEqual(bytes(world.vm.mem_read(pointer, 2*world.get(pointer-4))).decode("utf-16-le"), text)


if __name__ == "__main__":
    unittest.main()

"""Interceptor drones, hypervelocity AA rounds and nuclear SAMs on the patched native sites, in the emulator."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from test_modern_combat import World, BLOB, CODE, SHIP, NATION, DATA, STACK, FRAME
from test_modern_recon import execute, call
import modern_air_defence as air
import modern_carrier as carrier
import modern_defence as defence
import modern_research as modern
import modern_tree as tree
import shell_doctrine as sd

DETAILS = modern.discover(BLOB, 0x301000)
AIR, DEFENCE = DETAILS["air"], DETAILS["defence"]
AT = {b["name"][13:]: b["address"] for b in modern.build(CODE, DETAILS)[0] if b["name"].startswith("Air defence: ")}
HAS_SPECIAL = CODE+len(DETAILS["getters"])*0x1000+0x11000+carrier.HAS_SPECIAL
DRONES, HVP, WARHEAD = tree.DRONE_SWARMS[0], tree.HVP_AA[0], tree.NUCLEAR_SHELLS[0]
SLOT, PARENT, FORMATION, LOG, VMT, LOG_METHOD = DATA+0x500, DATA+0x3100, DATA+0x3400, DATA+0x3600, DATA+0x3700, CODE+0x1F800


def ship(world, railgun=False, helicopters=0, catapults=0, deck=0):
    world.vm.mem_write(SHIP, bytes(0xE20)); world.put(SHIP+0x14, 3)
    world.put(SHIP+air.SHIP["elevation"], air.RAILGUN if railgun else 1, 1)
    world.put(SHIP+air.SHIP["helicopters"], helicopters, 1); world.put(SHIP+air.SHIP["catapults"], catapults)
    world.put(SHIP+air.SHIP["flight_deck"], deck, 1)


def never():
    raise AssertionError("not expected")


class DroneTests(unittest.TestCase):
    def test_ships_with_a_helicopter_deck_catapult_or_flight_deck_carry_drones(self):
        for owned, aboard, expected in (({DRONES}, dict(helicopters=1), 1), ({DRONES}, dict(catapults=2), 1),
                                        ({DRONES}, dict(deck=1), 1), ({DRONES}, {}, 0), (set(), dict(helicopters=1), 0)):
            w = World(owned); ship(w, **aboard)
            self.assertEqual(call(w, AT["drone_ship"], EAX=SHIP, ECX=0x1111, EDX=0x2222) & 0xFF, expected, (owned, aboard))
            self.assertEqual((w.reg("ECX"), w.reg("EDX"), w.reg("EBX"), w.reg("ESI"), w.reg("EDI")),
                             (0x1111, 0x2222, 0x2345, 0x4567, 0x5678))

    def test_carriers_of_a_drone_nation_count_as_having_an_aew_squadron(self):
        site = 0x962EAE   # CAPIntercept: one of the three CAP vectoring checks
        for owned, special, is_carrier, expected in (({DRONES}, 1, 0, 1), (set(), 1, 1, 1), ({DRONES}, 0, 1, 1),
                                                     (set(), 0, 1, 0), ({DRONES}, 0, 0, 0)):
            w = World(owned); ship(w, deck=1)
            w.stubs[HAS_SPECIAL] = lambda: special if (w.reg("EAX"), w.reg("ECX")) == (SHIP, carrier.AEW) else never()
            w.stubs[AIR["is_carrier"]] = lambda: is_carrier if w.reg("EAX") == SHIP else never()
            execute(w, site, site+5, EAX=SHIP)
            self.assertEqual(w.reg("EAX") & 0xFF, expected, (owned, special, is_carrier))
            self.assertEqual((w.reg("EBX"), w.reg("ESI"), w.reg("EDI"), w.reg("EBP"), w.reg("ESP")),
                             (0x2345, 0x4567, 0x5678, FRAME, STACK+0x8000))

    def test_drones_add_to_the_chance_of_stopping_an_incoming_missile(self):
        for owned, aboard, percent in (({DRONES}, dict(helicopters=1), 13+tree.DRONE_SWARMS[1]), ({DRONES}, {}, 13),
                                       (set(), dict(helicopters=1), 13)):
            w = World(owned); ship(w, **aboard); w.put(SHIP+defence.DESIGN_YEAR, 1960)
            w.stubs[DEFENCE["operational"]] = lambda: 1
            site = DEFENCE["sites"]["decoy"]
            execute(w, site, site+7, ESI=13, EDI=3, EBP=SHIP)
            self.assertEqual((w.reg("ESI"), w.reg("EDI"), w.reg("EBP")), (percent, 3, SHIP), (owned, aboard))


class HypervelocityTests(unittest.TestCase):
    def value(self, owned, railgun=True, guns=9, native=0):
        w = World(owned); ship(w, railgun=railgun)
        w.stubs[AIR["count_guns"]] = lambda: guns if (w.reg("EAX"), w.reg("EDX") & 0xFF) == (SHIP, 1) else never()
        w.put(FRAME-0x20, native); w.put(FRAME-0xC, 1 if native else 0)
        execute(w, AIR["sites"]["value"], AIR["value_back"], ESI=SHIP)
        self.assertEqual((w.reg("ESI"), w.reg("EBP"), w.reg("ESP")), (SHIP, FRAME, STACK+0x8000))
        return w.get(FRAME-0x20), w.get(FRAME-0xC)

    def test_railgun_main_batteries_of_any_calibre_count_as_heavy_aa(self):
        per_gun = tree.HVP_AA[1]
        self.assertEqual(self.value({HVP}), (9*per_gun, 1))                    # not DP: nothing natively
        self.assertEqual(self.value({HVP}, guns=2, native=27), (2*per_gun, 1))  # a 5-inch DP railgun's own value
        self.assertEqual(self.value({HVP}, guns=1, native=50), (50, 1))         # a larger native value stays
        self.assertEqual(self.value(set()), (0, 0))
        self.assertEqual(self.value({HVP}, railgun=False), (0, 0))

    def test_they_engage_air_strikes_from_three_times_as_far(self):
        for owned, railgun, expected in (({HVP}, True, 5000*tree.HVP_AA[2]), (set(), True, 5000), ({HVP}, False, 5000)):
            w = World(owned); ship(w, railgun=railgun)
            w.stubs[AIR["heavy_range"]] = lambda: 5000 if w.reg("EAX") == SHIP else never()
            site = AIR["sites"]["range"]
            execute(w, site, site+5, EAX=SHIP)
            self.assertEqual((w.reg("EAX"), w.reg("ESI"), w.reg("EBX")), (expected, 0x4567, 0x2345), (owned, railgun))

    def test_their_shots_are_counted_apart(self):
        w = World({HVP}); ship(w, railgun=True); w.put(SLOT, SHIP)
        w.put(FRAME-0x28, 77); w.put(AT["hypervelocity shots"], 5)
        site = AIR["sites"]["reset"]
        execute(w, site, site+5)
        self.assertEqual((w.get(FRAME-0x28), w.get(AT["hypervelocity shots"]), w.reg("EAX")), (0, 0, 0))
        for name in ("add", "add2"):
            w.put(FRAME-0x28, 0); w.put(AT["hypervelocity shots"], 0)
            for railgun, shots, total, counted in ((True, 10, 10, 10), (False, 10, 20, 10), (True, 0, 20, 10)):
                ship(w, railgun=railgun); w.put(SLOT, SHIP)
                site = AIR["sites"][name]
                execute(w, site, site+5, EDI=shots, ESI=SLOT)
                self.assertEqual((w.get(FRAME-0x28), w.get(AT["hypervelocity shots"]), w.reg("EDI"), w.reg("ESI")),
                                 (total, counted, shots, SLOT), (name, railgun, shots))
                self.assertEqual(bool(w.reg("EFLAGS") & 0x40), shots == 0)        # ZF of TEST EDI,EDI for the JLE

    def test_a_hypervelocity_hit_strikes_two_aircraft_by_its_share_of_the_shots(self):
        spread = tree.HVP_AA[3]
        for name, kind, counter in (("kill", 0xC, 0x14), ("damage", 0xB, 0x18)):
            for hvp, roll, expected in ((10, 9, spread), (10, 10, 1), (0, None, 1)):
                w = World({HVP})
                w.put(FRAME-0x28, 20); w.put(AT["hypervelocity shots"], hvp); w.put(FRAME-counter, 1); w.put(FRAME-0x24, 5)
                w.stubs[AIR["random"]] = (lambda: roll if w.reg("EAX") == 20 else never()) if roll is not None else never
                site = AIR["sites"][name]
                execute(w, site, site+5, ECX=0x700+kind)
                extra = expected-1
                self.assertEqual((w.reg("EDX"), w.reg("ECX"), w.get(FRAME-counter), w.get(FRAME-0x24)),
                                 (expected, 0x700+kind, 1+extra, 5-extra), (name, hvp, roll))


class HeavyDPTests(unittest.TestCase):
    FORM_VAR, FORM = DATA+0x3800, DATA+0x3900

    def dp(self, calibre, barrels, owned):
        w = World(owned)
        w.put(AIR["designer"], self.FORM_VAR); w.put(self.FORM_VAR, self.FORM); w.put(self.FORM+air.DESIGNER_NATION, NATION)
        result = call(w, 0x95274C, EAX=calibre, EDX=barrels) & 0xFF
        self.assertEqual((w.reg("EBX"), w.reg("ESI"), w.reg("EDI")), (0x2345, 0x4567, 0x5678))
        return result

    def test_seven_and_eight_inch_guns_may_be_dp_with_both_researches(self):
        mounts, autoloader, twin = air.HEAVY_DP_RESEARCH+(1402,)
        both = {mounts, autoloader}
        self.assertEqual([self.dp(8, 1, both), self.dp(7, 99, both), self.dp(8, 2, both | {twin})], [1, 1, 1])
        self.assertEqual([self.dp(8, 1, {mounts}), self.dp(8, 1, {autoloader}), self.dp(8, 2, both)], [0, 0, 0])
        self.assertEqual([self.dp(8, 3, both | {twin}), self.dp(9, 1, both), self.dp(7, 4, both)], [0, 0, 0])
        self.assertEqual([self.dp(6, 1, {mounts}), self.dp(5, 1, {1403}), self.dp(6, 1, set()), self.dp(4, 1, {512})],
                         [1, 1, 0, 1])                                              # the native calibres as before

    def aa(self, calibre, loaded=0, battery=1):
        w = World()
        w.vm.mem_write(SHIP, bytes(0x100)); w.put(SHIP+0x69+4*battery, calibre); w.put(SHIP+0x75+4*battery, 2)   # gun mark
        w.put(SHIP+0x87+battery, loaded, 1)
        return call(w, 0x950270, EAX=SHIP, EDX=battery, ECX=7), (w.reg("EBX"), w.reg("ESI"), w.reg("EDI"))

    def test_seven_and_eight_inch_dp_guns_count_as_heavy_aa(self):
        kept = (0x2345, 0x4567, 0x5678)
        for calibre, loaded, battery, value in ((8, 0, 1, air.HEAVY_DP[8]), (8, 1, 1, air.HEAVY_DP[8]+1),
                                                (7, 0, 2, air.HEAVY_DP[7]), (7, 1, 3, air.HEAVY_DP[7]+1),
                                                (6, 0, 1, 5), (6, 1, 1, 6), (5, 0, 1, 9+2), (3, 1, 2, 7+2), (9, 0, 1, 0)):
            self.assertEqual(self.aa(calibre, loaded, battery), (value, kept), (calibre, loaded, battery))


class TankerTests(unittest.TestCase):
    FORMATION, BASE_SHIP, TYPE = DATA+0x4000, DATA+0x4800, DATA+0x5000
    REFUEL, LAND = tree.AERIAL_REFUELLING
    DRONES, SEA = tree.CARRIER_TANKERS

    def world(self, owned, kind=12, carrier=0, special=0, base=True):
        w = World(owned)
        w.vm.mem_write(self.FORMATION, bytes(0x100)); w.vm.mem_write(self.BASE_SHIP, bytes(0xA00))
        w.put(self.FORMATION+air.FORMATION_NATION, 3); w.put(self.FORMATION+0x10, self.TYPE)
        w.put(self.FORMATION+air.FORMATION_BASE, self.BASE_SHIP if base else 0); w.put(self.BASE_SHIP+0x9D3, kind, 1)
        w.stubs[AIR["is_carrier"]] = lambda: carrier if w.reg("EAX") == self.BASE_SHIP else never()
        w.stubs[AIR["has_special"]] = lambda: special if w.reg("EAX") == self.BASE_SHIP else never()
        w.stubs[AIR["radius"]] = lambda: 300 if (w.reg("EAX"), w.reg("EDX")) == (self.TYPE, 2) else never()
        return w

    def test_airfields_with_refuelling_and_carriers_with_tanker_drones_in_their_special_squadron(self):
        for owned, setup, percent in (({self.REFUEL}, {}, self.LAND), (set(), {}, 100), ({self.DRONES}, {}, 100),
                                      ({self.DRONES}, dict(kind=5, carrier=1, special=1), self.SEA),
                                      ({self.DRONES}, dict(kind=5, carrier=1), 100),               # no special squadron
                                      ({self.REFUEL}, dict(kind=5, carrier=1, special=1), 100),    # land tankers only
                                      ({self.REFUEL, self.DRONES}, dict(kind=3), 100),             # a cruiser's floatplanes
                                      ({self.REFUEL}, dict(base=False), 100)):
            w = self.world(owned, **setup)
            self.assertEqual(call(w, AT["tanker"], EAX=self.FORMATION), percent, (owned, setup))
            self.assertEqual((w.reg("EBX"), w.reg("ESI"), w.reg("EDI")), (0x2345, 0x4567, 0x5678))

    def test_a_formation_takes_off_with_the_extra_fuel(self):
        for owned, fuel in (({self.REFUEL}, 600), (set(), 400)):
            w = self.world(owned); w.put(self.TYPE+0x28+4*2, 400)
            w.stubs[0x9666A0] = lambda: 2                                                # GetLoadoutNumber
            call(w, 0x974CE8, EAX=self.FORMATION)                                         # SetFullFuelLoad
            self.assertEqual((w.get(self.FORMATION+air.FUEL), w.reg("EBX")), (fuel, 0x2345), owned)

    def test_every_range_check_with_the_formation_sees_the_tanker(self):
        slot = DATA+0x5800
        for owned, radius in (({self.REFUEL}, 300*self.LAND//100), (set(), 300)):
            w = self.world(owned); w.put(slot, self.FORMATION); w.put(FRAME-8, self.FORMATION)
            for kind, registers in (("ebx", dict(EBX=self.FORMATION)), ("slot", dict(EBX=slot)), ("frame", dict(EBX=0x2345))):
                for site in AIR["radius_calls"][kind]:
                    execute(w, site, site+5, EAX=self.TYPE, EDX=2, **registers)
                    self.assertEqual((w.reg("EAX"), w.reg("EBX"), w.reg("ESI"), w.reg("EBP")),
                                     (radius, registers["EBX"], 0x4567, FRAME), (owned, hex(site)))


class NuclearSAMTests(unittest.TestCase):
    def world(self, owned, armageddon=1, flags=sd.MISSILE):
        w = World(owned); ship(w); w.put(w.doctrine+4, flags)
        w.put(w.doctrine+sd.SLOTS*8+8, armageddon)
        return w

    def test_a_heavy_sam_may_be_nuclear_only_under_armageddon(self):
        for owned, armageddon, kind, flags, expected in (({WARHEAD}, 1, 1, sd.MISSILE, 1), ({WARHEAD}, 0, 1, sd.MISSILE, 0),
                                                         ({WARHEAD}, 1, 2, sd.MISSILE, 0), (set(), 1, 1, sd.MISSILE, 0),
                                                         ({WARHEAD}, 1, 1, sd.NUCLEAR, 0)):
            w = self.world(owned, armageddon, flags)
            funds = w.get(NATION+sd.FUNDS)
            self.assertEqual(call(w, AT["nuclear_sam"], EAX=SHIP, EDX=kind, ECX=0x1111) & 0xFF, expected,
                             (owned, armageddon, kind, flags))
            self.assertEqual((w.reg("ECX"), w.reg("EDX")), (0x1111, kind))
            self.assertEqual((w.get(NATION+sd.FUNDS), w.get(w.doctrine+sd.SLOTS*8+4)),
                             (funds-sd.MISSILE_COST, 1) if expected else (funds, 0))

    def sam_air(self, owned, armageddon=1, aircraft=12, destroyed=0, esi=1):
        w = self.world(owned, armageddon)
        w.put(FRAME+8, PARENT); w.put(PARENT-0x30, SHIP); w.put(PARENT-0xC, FORMATION)
        w.vm.mem_write(FORMATION, bytes(0x100)); w.put(FORMATION+0x18, aircraft); w.put(FORMATION+0x8D, destroyed)
        w.put(AIR["battle_log"], LOG); w.put(LOG, VMT); w.put(VMT+0x40, LOG_METHOD)
        logged = []
        w.stubs[LOG_METHOD] = lambda: logged.append((w.reg("ECX"), bytes(w.vm.mem_read(w.reg("EDX"), 2*w.get(w.reg("EDX")-4))).decode("utf-16-le"))) or 0
        stops = (AIR["sam_air_back"], AIR["sam_air_skip"])
        w.vm.hook_add(UC_HOOK_CODE, lambda vm, address, size, data: vm.emu_stop() if address in stops else None)
        for name, value in dict(EAX=0x11, EBX=1, ECX=0x22, EDX=0x33, ESI=esi, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000).items():
            w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        w.vm.emu_start(AIR["sites"]["sam_air"], 0, count=20000)
        self.assertEqual((w.reg("EBX"), w.reg("EDI"), w.reg("EBP"), w.reg("ESP")), (1, 0x5678, FRAME, STACK+0x8000))
        return w.reg("EIP"), w.reg("ESI"), logged

    def test_a_nuclear_sam_hit_strikes_up_to_ten_aircraft(self):
        back, skip = AIR["sam_air_back"], AIR["sam_air_skip"]
        text = air.TEXT
        self.assertEqual(self.sam_air({WARHEAD}), (back, air.NUCLEAR_SAM_AIRCRAFT-1, [(SHIP, text)]))
        self.assertEqual(self.sam_air({WARHEAD}, aircraft=6, destroyed=2), (back, 3, [(SHIP, text)]))   # four left
        self.assertEqual(self.sam_air({WARHEAD}, aircraft=2, destroyed=2), (back, 0, [(SHIP, text)]))
        self.assertEqual(self.sam_air({WARHEAD}, armageddon=0), (back, 1, []))
        self.assertEqual(self.sam_air(set()), (back, 1, []))
        self.assertEqual(self.sam_air(set(), esi=0xFFFFFFFF), (skip, 0xFFFFFFFF, []))

    def test_a_nuclear_heavy_sam_shoots_down_the_incoming_missile(self):
        for owned, armageddon, kind, nuclear in (({WARHEAD}, 1, 1, True), ({WARHEAD}, 0, 1, False), ({WARHEAD}, 1, 2, False)):
            w = self.world(owned, armageddon); w.put(FRAME-8, 0)
            stops = (DEFENCE["no_shot"], DEFENCE["shot"])
            w.vm.hook_add(UC_HOOK_CODE, lambda vm, address, size, data: vm.emu_stop() if address in stops else None)
            for name, value in dict(EAX=2, EBX=kind, ESI=SHIP, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
            w.vm.emu_start(DEFENCE["sites"]["fired"], 0, count=20000)
            case = (owned, armageddon, kind)
            self.assertEqual(w.reg("EIP"), DEFENCE["no_shot"] if nuclear else DEFENCE["shot"], case)
            self.assertEqual(w.vm.mem_read(FRAME-5, 1)[0], 1 if nuclear else 0, case)
            if not nuclear: self.assertEqual(w.reg("EAX"), 1, case)
            self.assertEqual((w.reg("EBX"), w.reg("ESI"), w.reg("ESP")), (kind, SHIP, STACK+0x8000), case)


if __name__ == "__main__": unittest.main(verbosity=2)

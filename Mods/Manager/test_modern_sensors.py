"""Aegis radar class 6, AESA class 7 and ship radar stealth, executed on the native radar code."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import modern_research as modern
import modern_sensors as sensors
import modern_tree as tree

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
CODE, DATA, STACK, STOP = 0x2000000, 0x1300000, 0x1500000, 0x2010000
SHIP, NATION, MAIN, OBSERVER = DATA+0x1000, DATA+0x8000, DATA+0x9000, DATA+0xA000
RADARS = (1501, 1502, 1506, 1511, 1512)


class World:
    def __init__(self, owned=(), patched=True):
        self.vm = vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address, size in ((0, 0x1000), (0x300000, 0x800000), (DATA, 0x20000), (STACK, 0x10000), (CODE, 0x20000)):
            vm.mem_map(address, size)
        vm.mem_write(0x301000, BLOB)
        details = modern.discover(BLOB, 0x301000)
        self.info = details["sensors"]
        if patched:
            blocks, plans, _ = modern.build(CODE, details)
            for item in blocks+[dict(address=p["address"], bytes=p["replacement"]) for p in plans]:
                vm.mem_write(item["address"], bytes.fromhex(item["bytes"]))
        self.owned, self.queries, self.assigned = set(owned), [], []
        self.put(0x9F7328, DATA+0x100); self.put(DATA+0x100, 1990)          # campaign year
        self.put(self.info["main"], DATA+0x200); self.put(DATA+0x200, MAIN)  # main campaign object
        self.stubs = {0x729FA4: self.research, 0x750040: self.nation, 0x8ECD20: lambda: 12345,
                      0x30BCCC: self.assign}
        vm.hook_add(UC_HOOK_CODE, self.boundary)

    def put(self, address, value, size=4): self.vm.mem_write(address, (value & (1 << 8*size)-1).to_bytes(size, "little"))
    def get(self, address): return int.from_bytes(self.vm.mem_read(address, 4), "little")

    def research(self):
        ident = self.vm.reg_read(UC_X86_REG_EDX); self.queries.append(ident)
        return int(self.vm.reg_read(UC_X86_REG_EAX) == NATION and ident in self.owned)

    def nation(self):
        return NATION if (self.vm.reg_read(UC_X86_REG_EAX), self.vm.reg_read(UC_X86_REG_EDX)) == (MAIN, 3) else 0

    def assign(self):
        pointer = self.vm.reg_read(UC_X86_REG_EDX); size = self.get(pointer-4)
        self.assigned.append(bytes(self.vm.mem_read(pointer, size*2)).decode("utf-16-le")); return 0

    def boundary(self, vm, address, size, unused):
        if address in self.stubs:
            result = self.stubs[address]()
            sp = vm.reg_read(UC_X86_REG_ESP)
            vm.reg_write(UC_X86_REG_EAX, result); vm.reg_write(UC_X86_REG_EIP, self.get(sp)); vm.reg_write(UC_X86_REG_ESP, sp+4)

    def call(self, address, eax=0, edx=0, ecx=0):
        sp = STACK+0x8000
        for reg, value in ((UC_X86_REG_EAX, eax), (UC_X86_REG_EDX, edx), (UC_X86_REG_ECX, ecx), (UC_X86_REG_EBX, 0x2345),
                           (UC_X86_REG_ESI, 0x3456), (UC_X86_REG_EDI, 0x4567), (UC_X86_REG_EBP, STACK+0x9000), (UC_X86_REG_ESP, sp)):
            self.vm.reg_write(reg, value)
        self.put(sp, STOP); self.vm.mem_write(STOP, b"\xc3")
        self.vm.emu_start(address, STOP, count=200000)
        assert self.vm.reg_read(UC_X86_REG_ESP) == sp+4
        return self.vm.reg_read(UC_X86_REG_EAX)

    def text_at(self, pointer):
        return bytes(self.vm.mem_read(pointer, self.get(pointer-4)*2)).decode("utf-16-le")

    def ship(self, radar, side=2):
        self.vm.mem_write(SHIP, bytes(0xC00))
        self.put(SHIP+0xA0B, radar); self.put(SHIP+0xA55, side); self.put(SHIP+0x9D3, 1, 1)
        return SHIP


class AegisRadarTests(unittest.TestCase):
    def test_class_6_needs_all_five_search_radars_and_the_phased_array_tech(self):
        aesa = tree.AESA[0]
        for owned, expected in ((RADARS+(tree.PHASED_ARRAY,), 6), (RADARS, 5), (RADARS[:4]+(tree.PHASED_ARRAY,), 4), ((), 0),
                                (RADARS+(tree.PHASED_ARRAY, aesa), 7), (RADARS+(aesa,), 5)):
            for patched in (True, False):
                world = World(owned, patched)
                self.assertEqual(world.call(0x733AA8, NATION), expected if patched else min(expected, 5), owned)

    def test_battle_range_chance_sighting_and_name_for_class_6_and_unchanged_5(self):
        world = World()
        for radar, (yards, chance), sighting in ((6, (42000, 55), 38000), (5, (39900, 42), 35000),
                                                 (7, (50400, 66), 45600), (8, (0, 0), 0)):
            ship = world.ship(radar)
            world.call(0x91963C, ship, DATA+0x300, DATA+0x304)   # year 1990: native +5%
            self.assertEqual((world.get(DATA+0x300), world.get(DATA+0x304)), (yards, chance), radar)
            self.assertEqual(world.call(0x8CAB14, 0, ship), sighting, radar)
        names = []
        for radar in (7, 6, 5):
            world.assigned.clear(); world.call(0x94F928, world.ship(radar), DATA+0x400)
            names.append(world.assigned[0])
        self.assertEqual(names, ["AESA phased-array search", "Phased-array search (Aegis)", "Very advanced search"])

    def test_radar_limit_7_and_the_ai_reserve_above_it_weigh_200_tons(self):
        for patched in (True, False):
            world = World(patched=patched)
            self.assertEqual([world.call(0x950A60, SHIP, limit) for limit in (3, 5, 6, 7, 8, -1 & 0xFFFFFFFF)],
                             [30, 100, 200, 200, 200, 0] if patched else [30, 100, 200, 0, 0, 0])


class StealthTests(unittest.TestCase):
    def run_site(self, owned, design_year, nation_index=3, observer=None):
        world = World(owned)
        world.vm.mem_write(SHIP, bytes(0xC00)); world.vm.mem_write(OBSERVER, bytes(0xC00))
        world.put(SHIP+0x14, nation_index); world.put(SHIP+0xB28, design_year)
        if observer:   # radar fitted to the observing ship
            world.put(OBSERVER+0xA0B, observer); world.put(OBSERVER+0xA13, 8)
        frame = STACK+0x9000; world.put(frame-8, 40000)
        sp = STACK+0x8000
        for reg, value in ((UC_X86_REG_EBX, SHIP), (UC_X86_REG_ESI, OBSERVER), (UC_X86_REG_EDI, 0x4567),
                           (UC_X86_REG_EBP, frame), (UC_X86_REG_ESP, sp), (UC_X86_REG_EAX, 1), (UC_X86_REG_EDX, 2)):
            world.vm.reg_write(reg, value)
        back = world.info["stealth_site"]+9
        world.vm.emu_start(world.info["stealth_site"], back, count=100000)
        self.assertEqual(world.vm.reg_read(UC_X86_REG_EIP), back)
        self.assertEqual(world.vm.reg_read(UC_X86_REG_EAX), 12345)   # native GetRangeToShip result kept
        for reg, value in ((UC_X86_REG_EBX, SHIP), (UC_X86_REG_ESI, OBSERVER), (UC_X86_REG_EDI, 0x4567),
                           (UC_X86_REG_EBP, frame), (UC_X86_REG_ESP, sp)):
            self.assertEqual(world.vm.reg_read(reg), value)
        return world.get(frame-8)

    def test_enemy_radar_range_shrinks_only_for_ships_designed_after_owned_stealth_tech(self):
        both = {2308, 2310}
        self.assertEqual(self.run_site(both, 2016), 25600)    # 40,000 x 0.8 x 0.8
        self.assertEqual(self.run_site(both, 2000), 32000)
        self.assertEqual(self.run_site(both, 1985), 40000)
        self.assertEqual(self.run_site(set(), 2016), 40000)
        self.assertEqual(self.run_site(both, 2016, nation_index=99), 40000)   # no nation object

    def test_observers_with_aesa_fitted_halve_enemy_stealth(self):
        both = {2308, 2310}
        self.assertEqual(self.run_site(both, 2016, observer=7), 32400)   # 40,000 x 0.9 x 0.9
        self.assertEqual(self.run_site(both, 1985, observer=7), 40000)   # no stealth
        self.assertEqual(self.run_site(both, 2016, observer=6), 25600)   # Aegis, whatever its radar limit


class AircraftStealthTests(unittest.TestCase):
    MODEL, FORMATION = DATA+0xB000, DATA+0xB800

    def run_at(self, world, start, stop, regs, frame=STACK+0x9000):
        sp = STACK+0x8000
        defaults = {UC_X86_REG_EAX: 0, UC_X86_REG_EBX: 0x2345, UC_X86_REG_ECX: 0, UC_X86_REG_EDX: 0,
                    UC_X86_REG_ESI: 0x3456, UC_X86_REG_EDI: 0x4567, UC_X86_REG_EBP: frame, UC_X86_REG_ESP: sp}
        for reg, value in {**defaults, **regs}.items(): world.vm.reg_write(reg, value)
        world.vm.emu_start(start, stop, count=100000)
        self.assertEqual(world.vm.reg_read(UC_X86_REG_EIP), stop)
        self.assertEqual(world.vm.reg_read(UC_X86_REG_ESP), sp)
        return world

    def mark(self, world):
        """The label site, twice, on a model holding junk at MARK: the mark the first run leaves (the second: 0)."""
        randomized, marks = [], []
        world.stubs[0x96DF4C] = lambda: randomized.append(world.vm.reg_read(UC_X86_REG_EAX)) or 0
        for _ in range(2):
            world.put(self.MODEL+sensors.MARK, 0x7777)
            self.run_at(world, 0x7ED960, 0x7ED967, {UC_X86_REG_EBX: self.MODEL})
            marks.append(world.get(self.MODEL+sensors.MARK))
        self.assertEqual((randomized, marks[1]), ([self.MODEL]*2, 0))
        return marks[0]

    def test_jets_developed_from_1990_with_the_tech_become_named_stealth_models(self):
        frame = STACK+0x9000
        for kind, year, owned, stealth in ((11, 1995, {2308}, True), (11, 1985, {2308}, False), (11, 1995, set(), False),
                                           (0, 1995, {2308}, False), (12, 2030, {2308}, True), (12, 2018, {2308, 2326}, True),
                                           (11, 2030, {2308, 2326}, True), (12, 2020, {2308, 2326}, "unmanned"),
                                           (12, 2030, {2326}, False)):
            world = World(owned)
            world.put(frame-0x14, year); world.put(frame-0xD, kind, 1)
            self.run_at(world, 0x7ED65F, 0x7ED665, {UC_X86_REG_ESI: MAIN, UC_X86_REG_EDI: 3, UC_X86_REG_EBX: self.MODEL})
            self.assertEqual((world.vm.reg_read(UC_X86_REG_EAX), world.vm.reg_read(UC_X86_REG_ECX)), (kind, self.MODEL))
            # The data lookup then names the section from the type, once.
            names = []
            world.stubs[0x30BCCC] = lambda: (names.append(world.assigned_text()) or 0)
            world.stubs[0x970254] = lambda: (names.append("native") or 0)
            world.assigned_text = lambda: bytes(world.vm.mem_read(world.vm.reg_read(UC_X86_REG_EDX), 50)).decode("utf-16-le").split("\0")[0]
            for _ in range(2):
                self.run_at(world, 0x9710DA, 0x9710DF, {UC_X86_REG_EAX: kind, UC_X86_REG_EDX: DATA+0x500})
            expected = ["Stealth heavy jet fighter" if kind == 11 else "Stealth jet attack"] if stealth else ["native"]
            if stealth == "unmanned": expected = ["Unmanned jet attack"]
            self.assertEqual(names, expected+["native"], (kind, year, owned))
            # ...and the new model keeps its mark (the game renames it later).
            marks = {True: sensors.STEALTH_MARK, "unmanned": sensors.UCAV_MARK, False: 0}
            self.assertEqual(self.mark(world), marks[stealth], (kind, year, owned))

    def test_floatplane_scouts_from_2005_with_shipborne_uavs_become_uav_models(self):
        frame = STACK+0x9000
        for kind, year, owned, uav in ((3, 2006, {2326}, True), (3, tree.UAV_YEAR, {2326}, True), (3, 2004, {2326}, False),
                                       (3, 2010, set(), False), (3, 2010, {2308}, False), (4, 2010, {2326}, False)):
            world = World(owned)
            world.put(frame-0x14, year); world.put(frame-0xD, kind, 1)
            self.run_at(world, 0x7ED65F, 0x7ED665, {UC_X86_REG_ESI: MAIN, UC_X86_REG_EDI: 3, UC_X86_REG_EBX: self.MODEL})
            self.assertEqual((world.vm.reg_read(UC_X86_REG_EAX), world.vm.reg_read(UC_X86_REG_ECX)), (kind, self.MODEL))
            names = []
            world.assigned_text = lambda: bytes(world.vm.mem_read(world.vm.reg_read(UC_X86_REG_EDX), 50)).decode("utf-16-le").split("\0")[0]
            world.stubs[0x30BCCC] = lambda: (names.append(world.assigned_text()) or 0)
            world.stubs[0x970254] = lambda: (names.append("native") or 0)
            for _ in range(2):
                self.run_at(world, 0x9710DA, 0x9710DF, {UC_X86_REG_EAX: kind, UC_X86_REG_EDX: DATA+0x500})
            self.assertEqual(names, (["Shipborne UAV"] if uav else ["native"])+["native"], (kind, year, owned))
            self.assertEqual(self.mark(world), sensors.UAV_MARK if uav else 0, (kind, year, owned))

    def test_the_players_floatplane_scouts_become_uavs_only_by_request(self):
        frame = STACK+0x9000
        build = modern.build(CODE, modern.discover(BLOB, 0x301000))[0]
        flag = next(b["address"] for b in build if b["name"] == "UAV prototype")-0xF10+sensors.UAV_REQUEST
        lookup = next(b["address"] for b in build if b["name"] == "UAV prototype")-0xF10+0xF00
        for requested, year, owned, uav in ((1, 2010, {2326}, True), (0, 2010, {2326}, False), (1, 1960, set(), True)):
            world = World(owned); world.put(MAIN+0x3204, NATION)                     # nation 3 is the player's
            world.put(flag, requested, 1)
            world.put(frame-0x14, year); world.put(frame-0xD, 3, 1)
            for _ in range(3):   # every prototype of the request: modern_carrier clears the flag after completion
                self.run_at(world, 0x7ED65F, 0x7ED665, {UC_X86_REG_ESI: MAIN, UC_X86_REG_EDI: 3, UC_X86_REG_EBX: self.MODEL})
                self.assertEqual((world.get(lookup) & 0xFFFF, world.get(flag) & 0xFF), (0x0303 if uav else 0, requested))

    def formation(self, world, mark):
        world.put(self.FORMATION+0x10, self.MODEL); world.put(self.MODEL+sensors.MARK, mark)
        return self.FORMATION

    def test_cap_radar_range_and_aa_radar_bonus_drop_against_stealth_models(self):
        for name, stealth in ((sensors.STEALTH_MARK, True), (sensors.UCAV_MARK, True), (0, False), (sensors.UAV_MARK, False)):
            world = World(); sp = STACK+0x8000
            world.put(sp, 30000); world.put(sp+4, 50)
            self.run_at(world, 0x962DE3, 0x962DEB, {UC_X86_REG_ESI: self.formation(world, name)})
            self.assertEqual(world.vm.reg_read(UC_X86_REG_EAX), 19500 if stealth else 30000, name)
            self.assertEqual(world.get(sp+4), 50)
            frame = STACK+0x9000
            world.put(frame-0xC, self.FORMATION); world.put(frame-4, 10); world.put(SHIP+0xA0B, 6)
            self.run_at(world, 0x961074, 0x96107D, {UC_X86_REG_EAX: SHIP})
            self.assertEqual(world.get(frame-4), 13 if stealth else 16, name)


class AegisHullAgeTests(unittest.TestCase):
    FORM, SPIN = DATA+0xC000, DATA+0xC800

    def test_radar_limit_6_needs_a_hull_from_1975_and_7_one_from_the_aesa_year(self):
        for asked, year, limit, warned in ((6, 1974, 5, 1), (6, 1975, 6, 0), (6, 1990, 6, 0), (7, 1974, 5, 1),
                                           (7, tree.AESA[1]-1, 6, 1), (7, tree.AESA[1], 7, 0), (5, 1900, 5, 0)):
            world = World(); state = {"value": asked}; messages = []
            world.stubs.update({0x590C6C: lambda: state["value"],
                                0x590CC4: lambda: state.update(value=world.vm.reg_read(UC_X86_REG_EDX)) or
                                          world.call_nested(0x5F6C8C, self.FORM),
                                0x4D7124: lambda: messages.append(world.text_at(world.vm.reg_read(UC_X86_REG_EAX))) or 0, 0x9395F8: lambda: 0, 0x5E9D88: lambda: 0})
            world.call_nested = lambda address, eax: self.nested(world, address, eax)
            world.put(self.FORM+0xE67, 1, 1); world.put(self.FORM+0xA5C, self.SPIN); world.put(self.FORM+0xE6C, SHIP)
            world.vm.mem_write(SHIP, bytes(0xC00)); world.put(SHIP+0xE4, year)
            world.call(0x5F6C8C, self.FORM)
            self.assertEqual((world.get(SHIP+0xA13), len(messages), state["value"]), (limit, warned, limit), (asked, year))
            if warned: self.assertIn(f"radar limit {limit+1}", messages[0])

    @staticmethod
    def nested(world, address, eax):
        """Run the native change handler again from inside a stub (control's OnChange)."""
        vm = world.vm
        saved = {reg: vm.reg_read(reg) for reg in (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
                                                   UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP)}
        sp = saved[UC_X86_REG_ESP]-0x400; back = STOP+0x10
        vm.mem_write(back, b"\xc3"); world.put(sp, back)
        vm.reg_write(UC_X86_REG_EAX, eax); vm.reg_write(UC_X86_REG_ESP, sp)
        vm.emu_start(address, back, count=100000)
        for reg, value in saved.items(): vm.reg_write(reg, value)
        return 0


if __name__ == "__main__": unittest.main(verbosity=2)

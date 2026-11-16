"""Nuclear propulsion (designer type 5), executed on the native designer and ship code."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import destroyer_fuel
import modern_propulsion as nuclear
import modern_research as modern
import modern_tree as tree

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
CODE, DATA, STACK, STOP = 0x2000000, 0x1300000, 0x1500000, 0x2010000
SHIP, FORM, COMBO, ITEMS, NATION = DATA+0x1000, DATA+0x3000, DATA+0x3400, DATA+0x3800, DATA+0x8000
FORM_GLOBAL, FORM_VAR = 0x9F7A34, DATA+0x5000   # designer form global (GetResults) -> variable -> form
COMBO_VMT, ITEMS_VMT, STUBS = DATA+0x4000, DATA+0x4400, DATA+0x7000
OIL = 2


class BattleFuelTests(unittest.TestCase):
    def test_nuclear_ships_stay_full_and_burn_no_fuel_in_battle(self):
        for propulsion, fuel, back in ((nuclear.NUCLEAR, 900, 0x923FBC), (OIL, 50, 0x923F00)):
            world = World(); world.put(SHIP+0x9D4, propulsion, 1); world.put(SHIP+0xA4C, 50); world.put(SHIP+0xA50, 900)
            world.run(0x923EFA, back, EBX=SHIP)
            self.assertEqual((world.reg("EIP"), world.get(SHIP+0xA4C)), (back, fuel))
            if propulsion == OIL: self.assertEqual(world.reg("EAX"), 50)   # the replayed native load


class World:
    def __init__(self, owned=(), patched=True):
        self.vm = vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address, size in ((0, 0x1000), (0x300000, 0x800000), (DATA, 0x20000), (STACK, 0x10000), (CODE, 0x20000)):
            vm.mem_map(address, size)
        vm.mem_write(0x301000, BLOB)
        details = modern.discover(BLOB, 0x301000)
        self.info = details["propulsion"]
        if patched:
            blocks, plans, _ = modern.build(CODE, details)
            for item in blocks+[dict(address=p["address"], bytes=p["replacement"]) for p in plans]:
                vm.mem_write(item["address"], bytes.fromhex(item["bytes"]))
        self.owned, self.count, self.index, self.log = set(owned), 5, 0, []
        vm.mem_write(SHIP, bytes(0xC00))
        # Designer form: cbFuelType +0x564 (Items +0x304), nation +0xC63, editable +0xE67, design +0xE6C.
        for address, value in ((FORM+0x564, COMBO), (COMBO, COMBO_VMT), (COMBO+0x304, ITEMS), (ITEMS, ITEMS_VMT),
                               (FORM+0xC63, NATION), (FORM+0xE6C, SHIP)):
            self.put(address, value)
        self.put(FORM+0xE67, 1, 1)
        self.stubs = {0x729FA4: self.research, 0x4D7124: lambda: self.note("message", self.text(self.reg("EAX"))),
                      0x9395F8: lambda: self.note("recompute", self.reg("EAX")), 0x5E9D88: lambda: self.note("refresh"),
                      STUBS: lambda: self.index, STUBS+0x10: lambda: self.note("item index", self.reg("EDX")),
                      STUBS+0x20: lambda: self.count, STUBS+0x30: lambda: self.note("add", self.text(self.reg("EDX")))}
        for slot, stub in ((COMBO_VMT+0x16C, STUBS), (COMBO_VMT+0x170, STUBS+0x10), (ITEMS_VMT+0x14, STUBS+0x20),
                           (ITEMS_VMT+0x3C, STUBS+0x30)):
            self.put(slot, stub)
        vm.hook_add(UC_HOOK_CODE, self.boundary)

    def put(self, address, value, size=4): self.vm.mem_write(address, (value & (1 << 8*size)-1).to_bytes(size, "little"))
    def get(self, address, size=4): return int.from_bytes(self.vm.mem_read(address, size), "little")
    def reg(self, name): return self.vm.reg_read(globals()["UC_X86_REG_"+name])
    def text(self, pointer): return bytes(self.vm.mem_read(pointer, self.get(pointer-4)*2)).decode("utf-16-le")
    def note(self, *entry): self.log.append(entry); return 0

    def research(self):
        ident = self.reg("EDX"); self.note("research", ident)
        return int(self.reg("EAX") == NATION and ident in self.owned)

    def boundary(self, vm, address, size, unused):
        if address in self.stubs:
            result = self.stubs[address]()
            sp = vm.reg_read(UC_X86_REG_ESP)
            vm.reg_write(UC_X86_REG_EAX, result); vm.reg_write(UC_X86_REG_EIP, self.get(sp)); vm.reg_write(UC_X86_REG_ESP, sp+4)

    def call(self, address, eax=0, edx=0):
        sp = STACK+0x8000
        for name, value in (("EAX", eax), ("EDX", edx), ("EBX", 0x2345), ("ESI", 0x3456), ("EDI", 0x4567), ("ESP", sp)):
            self.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        self.put(sp, STOP); self.vm.mem_write(STOP, b"\xc3")
        self.vm.emu_start(address, STOP, count=200000)
        assert self.reg("ESP") == sp+4
        return self.reg("EAX")

    def run(self, start, stop, **registers):
        """Executes from a hooked site to the native instruction where control must come back."""
        self.vm.reg_write(UC_X86_REG_ESP, STACK+0x8000)
        for name, value in registers.items(): self.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        self.vm.emu_start(start, stop, count=200000)
        return self.reg("EIP") == stop

    def design(self, fuel, **fields):
        offsets = dict(fuel=(0x9D4, 1), displacement=(0x2C, 4), range=(0x9AD, 1), unit=(0x9AB, 1),
                       weight=(0xA60, 4), cost=(0xA80, 4), remaining=(0xA4C, 4), capacity=(0xA50, 4))
        self.vm.mem_write(SHIP, bytes(0xC00))
        for name, value in dict(fields, fuel=fuel).items(): self.put(SHIP+offsets[name][0], value, offsets[name][1])
        return SHIP


class DesignerTests(unittest.TestCase):
    def test_nuclear_is_added_to_the_propulsion_list_once(self):
        for count, added in ((5, [("add", "Nuclear")]), (6, [])):
            world = World(); world.count = count
            self.assertTrue(world.run(0x5CCFA8, 0x5CCFAD, EAX=FORM, EBX=0x2345))
            self.assertEqual(world.log, added)
            self.assertEqual((world.reg("EAX"), world.reg("EBX"), world.reg("EBP")), (FORM, 0x2345, STACK+0x8000-4))

    def test_choosing_nuclear_needs_the_research_and_otherwise_falls_back_to_oil(self):
        for owned, index, stored, log in (
                ({tree.NUCLEAR_PROPULSION}, 5, 5, [("research", 40), ("recompute", SHIP), ("refresh",)]),
                ((), 5, OIL, [("research", 40), ("message", nuclear.TEXT), ("item index", OIL), ("recompute", SHIP), ("refresh",)]),
                ((), 3, 3, [("recompute", SHIP), ("refresh",)])):
            world = World(owned); world.index = index
            world.call(0x5EBEE4, FORM)   # native cbFuelTypeChange
            self.assertEqual((world.get(SHIP+0x9D4, 1), world.log), (stored, log), (owned, index))


class ShipTests(unittest.TestCase):
    def test_reactor_machinery_is_heavier_and_costlier_only_for_nuclear(self):
        thorium = {tree.THORIUM[0]}
        for owned, form, fuel, unit, expected in (
                ((), True, nuclear.NUCLEAR, 0, (1600, 1500)), ((), True, OIL, 0, (1000, 500)),
                ((), True, nuclear.NUCLEAR, 1, (1600, 1500)), (thorium, True, nuclear.NUCLEAR, 0, (1300, 1500)),
                (thorium, True, OIL, 0, (1000, 500)), (thorium, False, nuclear.NUCLEAR, 0, (1600, 1500))):
            world = World(owned)
            if form: world.put(FORM_GLOBAL, FORM_VAR); world.put(FORM_VAR, FORM)   # no form: no nation, no thorium
            world.design(fuel, weight=1000, cost=500, unit=unit)
            self.assertTrue(world.run(0x93907C, 0x939083, EBX=SHIP, EAX=11, ECX=22, EDX=33))
            self.assertEqual((world.get(SHIP+0xA60), world.get(SHIP+0xA80)), expected, (owned, form, fuel))
            self.assertEqual((world.reg("EAX"), world.reg("ECX"), world.reg("EDX")), (11, 22, 33))
            self.assertEqual(bool(world.reg("EFLAGS") & 0x40), unit == 0)   # replayed unit-machinery compare

    def test_range_setting_does_not_change_nuclear_fuel_weight(self):
        patched, native = World(), World(patched=False)
        for displacement in (2000, 10000):
            for setting in range(4):
                factors = []
                for fuel, world in ((OIL, patched), (OIL, native), (nuclear.NUCLEAR, patched)):
                    world.design(fuel, displacement=displacement, range=setting)
                    self.assertTrue(world.run(0x939CAA, 0x939E32, EBX=SHIP, ESI=0))
                    factors.append(world.reg("ESI"))
                self.assertEqual(factors[0], factors[1])   # oil keeps the native factor
                self.assertEqual(factors[2], nuclear.RANGE_FACTOR)

    def test_nuclear_ships_report_full_fuel_and_no_oil_shortage(self):
        world = World()
        for fuel, remaining, capacity, percent in ((nuclear.NUCLEAR, 200, 1000, 100), (nuclear.NUCLEAR, 0, 0, 100),
                                                   (OIL, 200, 1000, 20), (OIL, 0, 0, 100)):
            ship = world.design(fuel, remaining=remaining, capacity=capacity)
            self.assertEqual(world.call(0x9145FC, ship), percent, (fuel, remaining))
        self.assertEqual(world.call(0x7472D4, 0, world.design(nuclear.NUCLEAR)), 0)
        world.design(OIL)
        self.assertTrue(world.run(0x7472D5, 0x7472DC, EDX=SHIP))   # oil continues into the native check
        self.assertEqual(world.reg("EAX"), OIL)

    def test_hook_sites_avoid_the_large_hulls_fuel_recovery_hooks(self):
        for _, address, _, _, size in destroyer_fuel.RECOVERY_WINDOWS:
            for name, length in nuclear.SITES:
                start = nuclear.ADDRESSES[name]
                self.assertFalse(start < address+size and address < start+length, name)


if __name__ == "__main__":
    unittest.main()

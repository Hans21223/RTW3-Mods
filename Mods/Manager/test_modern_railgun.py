"""Railgun main batteries, executed on the native designer, results, battle and save code."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import modern_railgun as railgun
import modern_research as modern
import modern_tree as tree

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
CODE, DATA, STACK, HEAP, STOP = 0x2000000, 0x1300000, 0x1500000, 0x1600000, 0x2010000
SHIP, SHIP2, FORM, LIST, ITEMS = DATA+0x1000, DATA+0xA000, DATA+0x2000, DATA+0x4000, DATA+0x4100
BOX, LABEL, ELEV, NATION, ERRORS, CELL, TURRET = (DATA+0x5000, DATA+0x5400, DATA+0x5800, DATA+0x8000,
                                                  DATA+0x6000, DATA+0x7000, DATA+0x7100)
CHECKBOX, LABEL_VMT, SPIN_VMT = railgun.NATIVE["checkbox_vmt"], railgun.NATIVE["label_vmt"], railgun.NATIVE["spin_vmt"]
LASERS, LASER_LABEL, AA_GROUP = DATA+0x5C00, DATA+0x5E00, DATA+0x9100
HYPER, ADDITIONAL, FIGHTER, SUPER = DATA+0x5A00, DATA+0x9200, DATA+0x10000, DATA+0x9400
GEN, GEN_LABEL, SKI = DATA+0x9600, DATA+0x9800, DATA+0x9C00   # SKI: modern_carrier's box
import modern_extension as extension
import modern_carrier as carrier


def u32(address): return struct.unpack_from("<I", BLOB, address-0x301000)[0]


class World:
    def __init__(self, owned=(tree.RAILGUN,)):
        self.vm = vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address, size in ((0, 0x1000), (0x300000, 0x800000), (DATA, 0x20000), (STACK, 0x10000),
                              (HEAP, 0x10000), (CODE, 0x20000)):
            vm.mem_map(address, size)
        vm.mem_write(0x301000, BLOB)
        details = modern.discover(BLOB, 0x301000)
        self.railgun_info = details["railgun"]
        blocks, plans, _ = modern.build(CODE, details)
        for item in blocks+[dict(address=p["address"], bytes=p["replacement"]) for p in plans]:
            vm.mem_write(item["address"], bytes.fromhex(item["bytes"]))
        self.at = {b["name"][9:]: b["address"] for b in blocks if b["name"].startswith("Railgun: ")}
        self.plans = {p["label"][9:]: p for p in plans if p["label"].startswith("Railgun: ")}
        self.owned, self.guns, self.log, self.checked, self.heap = set(owned), 1, [], {}, HEAP
        self.spin, self.rolls, self.damage = {}, [], 0
        n = railgun.NATIVE
        self.stubs = {n["has_research"]: self.research, n["message"]: lambda: self.note("message", self.text(self.reg("EAX"))),
                      n["recompute"]: lambda: self.note("recompute"), n["update"]: lambda: self.note("update"),
                      n["refresh"]: lambda: self.note("refresh"), n["count_guns"]: lambda: self.guns,
                      n["int_to_str"]: self.int_to_str, n["cat_n"]: self.cat_n, n["clear_n"]: lambda: 0,
                      n["assign"]: self.assign, n["set_text"]: lambda: self.note("text", self.reg("EAX"), self.text(self.reg("EDX"))),
                      n["set_show_hint"]: lambda: self.note("show hint", self.reg("EAX"))}
        for name in ("set_left", "set_top", "set_width", "set_height"):
            self.stubs[n[name]] = lambda name=name: self.note(name, self.reg("EAX"), self.reg("EDX"))
        for vmt in (CHECKBOX, LABEL_VMT, SPIN_VMT):
            self.stubs[u32(vmt+0x3C)] = lambda vmt=vmt: self.construct(vmt)
            self.stubs[u32(vmt+0xA0)] = lambda: self.note("parent", self.reg("EAX"), self.reg("EDX"))
        self.stubs[u32(SPIN_VMT+0x9C)] = lambda: self.note("enabled", self.reg("EAX"), self.reg("EDX") & 0xFF)
        self.stubs[n["spin_get"]] = lambda: self.spin.get(self.reg("EAX"), 0)
        self.stubs[n["spin_set"]] = self.spin_set
        self.stubs[n["random"]] = lambda: self.rolls.pop(0)
        self.stubs[n["superstructure"]] = lambda: self.damage
        self.stubs[n["lstr_asg"]] = lambda: (self.put(self.reg("EAX"), self.reg("EDX")), self.note("shot", self.text(self.reg("EDX"))))[1]
        self.stubs[u32(CHECKBOX+0x16C)] = lambda: self.checked.get(self.reg("EAX"), 0)
        self.stubs[u32(CHECKBOX+0x170)] = self.set_checked
        self.stubs[u32(CHECKBOX+0x9C)] = lambda: self.note("enabled", self.reg("EAX"), self.reg("EDX") & 0xFF)
        self.stubs[DATA+0x7F00] = lambda: self.note("error", self.text(self.reg("EDX")))   # TStrings.Add
        vm.hook_add(UC_HOOK_CODE, self.boundary)
        # Designer form, its components (our two controls exist), design ships and an error list.
        for address, value in ((FORM+0x10, LIST), (LIST+4, ITEMS), (LIST+8, 9), (ITEMS+32, SKI), (SKI, CHECKBOX), (SKI+0xC, carrier.MAGIC_SKI), (ITEMS, BOX), (ITEMS+4, LABEL),
                               (ITEMS+24, GEN), (ITEMS+28, GEN_LABEL), (GEN, SPIN_VMT), (GEN+0xC, railgun.MAGIC_GEN),
                               (GEN+0x2E0, self.at["gen_change"]), (GEN+0x2E4, FORM), (GEN_LABEL, LABEL_VMT),
                               (GEN_LABEL+0xC, railgun.MAGIC_GEN_LABEL),
                               (ITEMS+20, SUPER), (SUPER, CHECKBOX), (SUPER+0xC, railgun.MAGIC_SUPER),
                               (SUPER+0x120, self.at["super_click"]), (SUPER+0x124, FORM),
                               (ITEMS+16, HYPER), (HYPER, CHECKBOX), (HYPER+0xC, railgun.MAGIC_HYPER),
                               (HYPER+0x120, self.at["hyper_click"]), (HYPER+0x124, FORM), (FORM+0x618, ADDITIONAL),
                               (ITEMS+8, LASERS), (ITEMS+12, LASER_LABEL), (LASERS, SPIN_VMT), (LASERS+0xC, railgun.MAGIC_LASERS),
                               (LASERS+0x2E0, self.at["laser_change"]), (LASERS+0x2E4, FORM), (LASER_LABEL, LABEL_VMT),
                               (LASER_LABEL+0xC, railgun.MAGIC_LASER_LABEL), (FORM+0x9F0, AA_GROUP),
                               (BOX, CHECKBOX), (BOX+0xC, railgun.MAGIC_CHECKBOX), (LABEL, LABEL_VMT),
                               (LABEL+0xC, railgun.MAGIC_LABEL), (ELEV, CHECKBOX), (ELEV+0x120, 0xDEAD0000),
                               (BOX+0x120, self.at["click"]), (BOX+0x124, FORM),
                               (FORM+0x64C, DATA+0x9000), (FORM+0x6A0, ELEV), (FORM+0xC63, NATION),
                               (FORM+0xC6B, SHIP2), (FORM+0xE6C, SHIP), (ERRORS, DATA+0x7E00), (DATA+0x7E00+0x3C, DATA+0x7F00)):
            self.put(address, value)
        self.put(FORM+0xE67, 1, 1)

    def put(self, address, value, size=4): self.vm.mem_write(address, (value & (1 << 8*size)-1).to_bytes(size, "little"))
    def get(self, address, size=4): return int.from_bytes(self.vm.mem_read(address, size), "little")
    def reg(self, name): return self.vm.reg_read(globals()["UC_X86_REG_"+name])
    def text(self, pointer): return bytes(self.vm.mem_read(pointer, self.get(pointer-4)*2)).decode("utf-16-le") if pointer else ""
    def note(self, *entry): self.log.append(entry); return 0

    def string(self, text):
        body = struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"
        address = self.heap; self.vm.mem_write(address, body); self.heap += (len(body)+15) & ~15
        return address+12

    def research(self):
        return int(self.reg("EAX") == NATION and self.reg("EDX") in self.owned)

    def int_to_str(self): self.put(self.reg("EDX"), self.string(str(self.reg("EAX")))); return 0
    def assign(self): self.put(self.reg("EAX"), self.reg("EDX")); self.note("assign", self.reg("EAX"), self.text(self.reg("EDX"))); return 0

    def cat_n(self):
        count, sp = self.reg("EDX"), self.reg("ESP")
        parts = [self.text(self.get(sp+4*i)) for i in range(count, 0, -1)]
        self.put(self.reg("EAX"), self.string("".join(parts)))
        self.pop_extra = 4*count
        return 0

    def spin_set(self):
        obj, value = self.reg("EAX"), self.reg("EDX")
        self.spin[obj] = value; self.note("spin", obj, value, self.get(obj+0x2E0)); return 0

    def guard(self, ship, data=0, vmt=None, kind="design"):   # a ship created after the mod attached
        size = extension.CLASSES[kind][1]
        self.put(ship, vmt or extension.NATIVE[kind+"_vmt"]); self.put(ship+size, data)
        self.put(ship+size+4, extension.MAGIC ^ (ship+size))

    def lasers(self, ship): return self.get(ship+extension.CLASSES["design"][1]) & 0xFF

    def construct(self, vmt):
        obj = self.heap; self.heap += 0x400; self.vm.mem_write(obj, bytes(0x400)); self.put(obj, vmt)
        self.note("create", vmt, self.reg("ECX")); return obj

    def set_checked(self):
        obj, value = self.reg("EAX"), self.reg("EDX") & 0xFF
        self.checked[obj] = value
        self.note("checked", obj, value, self.get(obj+0x120)); return 0

    def boundary(self, vm, address, size, unused):
        if address in self.stubs:
            self.pop_extra = 0
            result = self.stubs[address]()
            sp = vm.reg_read(UC_X86_REG_ESP)
            vm.reg_write(UC_X86_REG_EAX, result); vm.reg_write(UC_X86_REG_EIP, self.get(sp))
            vm.reg_write(UC_X86_REG_ESP, sp+4+self.pop_extra)

    def call(self, address, eax=0, edx=0):
        sp = STACK+0x8000
        for name, value in (("EAX", eax), ("EDX", edx), ("EBX", 0x2345), ("ESI", 0x3456), ("EDI", 0x4567),
                            ("EBP", STACK+0xA000), ("ESP", sp)):
            self.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        self.put(sp, STOP); self.vm.mem_write(STOP, b"\xc3")
        self.vm.emu_start(address, STOP, count=300000)
        assert self.reg("ESP") == sp+4 and (self.reg("EBX"), self.reg("ESI"), self.reg("EDI")) == (0x2345, 0x3456, 0x4567)
        return self.reg("EAX")

    def run(self, start, stop, **registers):
        self.vm.reg_write(UC_X86_REG_ESP, STACK+0x8000)
        for name, value in registers.items(): self.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        self.vm.emu_start(start, stop, count=300000)
        return self.reg("EIP") == stop

    def design(self, railgun_byte=0, fuel=4, hp=100000, calibre=5, ship=SHIP):
        self.vm.mem_write(ship, bytes(0xC00))
        self.put(ship+0x9A6, railgun_byte, 1); self.put(ship+0x9D4, fuel, 1); self.put(ship+0x3C, hp); self.put(ship+0x6D, calibre)


class DesignerTests(unittest.TestCase):
    def test_power_needs_16_mw_per_5_inch_gun_and_spares_nuclear_all_gas_turbine_a_quarter(self):
        world = World()
        for guns, calibre, fuel, hp, expected in ((2, 5, 4, 100000, (32, 18)), (1, 16, 5, 400000, (164, 298)),
                                                   (6, 18, 5, 515968, (1244, 384)), (3, 8, 2, 100000, (123, 0)),
                                                   (4, 0, 5, 100000, (0, 74))):
            world.guns = guns; world.design(railgun_byte=2, fuel=fuel, hp=hp, calibre=calibre)
            needed = world.call(world.at["power"], SHIP, NATION)
            self.assertEqual((needed, world.reg("EDX")), expected, (guns, calibre, fuel))

    def test_pulsed_power_research_cuts_need_and_integrated_power_doubles_gas_turbine_spare(self):
        for owned, needed, gas in (((), 1244, 96), ((2314,), 933, 96), ((2314, 2315), 699, 96), ((2313,), 1244, 192)):
            world = World(owned); world.guns = 6
            world.design(railgun_byte=2, fuel=4, hp=515968, calibre=18)
            self.assertEqual((world.call(world.at["power"], SHIP, NATION), world.reg("EDX")), (needed, gas), owned)

    def test_power_counts_only_railguns_unless_asked_and_adds_railgun_secondaries(self):
        world = World(); world.guns = 2; world.design(fuel=4, hp=100000, calibre=5)
        self.assertEqual(world.call(world.at["power"], SHIP, NATION), 0)          # conventional main battery
        world.vm.reg_write(UC_X86_REG_ECX, 1)                                      # the Railgun tick asks "would it fit"
        world.put(STACK+0x8000, STOP); world.vm.reg_write(UC_X86_REG_ESP, STACK+0x8000)
        world.vm.reg_write(UC_X86_REG_EAX, SHIP); world.vm.reg_write(UC_X86_REG_EDX, NATION)
        world.vm.emu_start(world.at["power"], STOP, count=300000)
        self.assertEqual(world.reg("EAX"), 32)
        # 8 secondary 5-inch railguns (16 MW each) and 4 tertiary 3-inch (6 MW each: 9x16/25 rounded)
        world.put(SHIP+0x71, 5); world.put(SHIP+0xAE, 8); world.put(SHIP+0x75, 3); world.put(SHIP+0xB2, 4)
        world.guard(SHIP, railgun.SECONDARY_RAIL_BIT)
        self.assertEqual(world.call(world.at["power"], SHIP, NATION), 128)
        world.guard(SHIP, railgun.SECONDARY_RAIL_BIT | railgun.TERTIARY_RAIL_BIT)
        self.assertEqual(world.call(world.at["power"], SHIP, NATION), 128+(4*9*16+12)//25)

    def test_hybrid_drive_lets_diesel_ships_spare_power_and_mount_railguns(self):
        hybrid = tree.HYBRID[0]
        for owned, spare in (((), 0), ((hybrid,), 96), ((hybrid, 2313), 192)):    # like a gas turbine
            world = World(owned); world.guns = 6; world.design(railgun_byte=2, fuel=railgun.DIESEL, hp=515968, calibre=18)
            world.call(world.at["power"], SHIP, NATION)
            self.assertEqual(world.reg("EDX"), spare, owned)
        for owned, stored in (((tree.RAILGUN,), 0), ((tree.RAILGUN, hybrid), 2)):  # the Railgun tick
            world = World(owned); world.design(fuel=railgun.DIESEL, hp=100000); world.design(ship=SHIP2)
            world.checked[BOX] = 1
            world.call(world.at["click"], FORM, BOX)
            self.assertEqual(world.get(SHIP+0x9A6, 1), stored, owned)
        for owned, errors in (((tree.RAILGUN,), 1), ((tree.RAILGUN, hybrid), 0)):   # the design report
            world = World(owned); world.design(railgun_byte=2, fuel=railgun.DIESEL, hp=100000)
            frame = STACK+0xA000; world.put(frame-0xC, ERRORS); world.put(frame-6, 1, 1); world.put(frame-5, 1, 1)
            self.assertTrue(world.run(railgun.SITES[1][1], 0x5D72B3, EBX=SHIP, ESI=FORM, EBP=frame))
            self.assertEqual(len([e for e in world.log if e[0] == "error"]), errors, owned)

    def test_newer_reactor_generations_spare_more_and_gas_turbines_do_not_change(self):
        for owned, nuclear, gas in (((), 384, 96), ((41,), 481, 96), ((41, 42), 577, 96), ((41, 42, 43), 769, 96), ((43,), 769, 96)):
            world = World(owned)
            for fuel, expected in ((5, nuclear), (4, gas)):
                world.design(fuel=fuel, hp=515968, calibre=18); world.guns = 6
                world.call(world.at["power"], SHIP, NATION)
                self.assertEqual(world.reg("EDX"), expected, (owned, fuel))
            world.design(fuel=5, hp=515968, calibre=18)
            world.call(world.at["power"], SHIP, NATION+0x100)   # another nation's research does not count
            self.assertEqual(world.reg("EDX"), 384)

    def test_checkbox_needs_research_electric_drive_and_power_then_sets_both_designs(self):
        cases = (((), 4, 100000, 0, "Railguns need research"), ((tree.RAILGUN,), 2, 100000, 0, "electric power"),
                 ((tree.RAILGUN,), 4, 10000, 0, "Not enough power"), ((tree.RAILGUN,), 4, 100000, 2, None))
        for owned, fuel, hp, stored, refusal in cases:
            world = World(owned); world.design(fuel=fuel, hp=hp); world.design(ship=SHIP2)
            world.checked[BOX] = 1
            world.call(world.at["click"], FORM, BOX)
            self.assertEqual((world.get(SHIP+0x9A6, 1), world.get(SHIP2+0x9A6, 1)), (stored, stored), owned)
            messages = [entry[1] for entry in world.log if entry[0] == "message"]
            if refusal:
                self.assertEqual(len(messages), 1); self.assertIn(refusal, messages[0])
                self.assertIn(("checked", BOX, 0, 0), world.log)   # box unticked without firing OnClick
                self.assertEqual(world.get(BOX+0x120), world.at["click"])
            else:
                self.assertEqual(messages, [])
                self.assertEqual([e[0] for e in world.log if e[0] in ("recompute", "update", "refresh")], ["recompute", "update", "refresh"])

    def test_unticking_keeps_increased_elevation(self):
        world = World(); world.design(railgun_byte=2); world.design(railgun_byte=2, ship=SHIP2)
        world.checked[BOX] = 0
        world.call(world.at["click"], FORM, BOX)
        self.assertEqual((world.get(SHIP+0x9A6, 1), world.get(SHIP2+0x9A6, 1)), (1, 1))

    def test_refresh_mirrors_the_design_and_writes_power(self):
        world = World(); world.guns = 2; world.design(railgun_byte=2, fuel=4, hp=100000, calibre=5)
        world.call(world.at["sync"], FORM)
        self.assertIn(("checked", BOX, 1, 0), world.log)               # ticked silently
        self.assertIn(("checked", ELEV, 1, 0), world.log)              # elevation shown ticked, silently
        self.assertEqual((world.get(BOX+0x120), world.get(ELEV+0x120)), (world.at["click"], 0xDEAD0000))
        self.assertIn(("enabled", BOX, 1), world.log)
        self.assertIn(("text", LABEL, "Power: 32 / 18 MW"), world.log)
        world.log.clear(); world.put(FORM+0xE67, 0, 1)                  # locked design: shown but disabled
        world.call(world.at["sync"], FORM)
        self.assertIn(("enabled", BOX, 0), world.log)

    def test_controls_are_created_once_in_the_main_gun_group_and_beside_the_hull_data(self):
        world = World(); world.put(LIST+8, 0); world.design()
        world.call(world.at["sync"], FORM)
        created = [entry for entry in world.log if entry[0] == "create"]
        self.assertEqual([(vmt, owner) for _, vmt, owner in created],
                         [(CHECKBOX, FORM), (LABEL_VMT, FORM), (SPIN_VMT, FORM), (LABEL_VMT, FORM), (CHECKBOX, FORM), (CHECKBOX, FORM),
                          (SPIN_VMT, FORM), (LABEL_VMT, FORM), (CHECKBOX, FORM), (CHECKBOX, FORM),
                          (CHECKBOX, FORM)])   # the last: modern_carrier's Ski jump, through the same sync chain
        box, label = [entry[2] for entry in world.log if entry[0] == "parent"], None
        box = next(e[1] for e in world.log if e[0] == "parent" and e[2] == DATA+0x9000)
        label = next(e[1] for e in world.log if e[0] == "parent" and e[2] == FORM)
        bounds = {e[0]: e[2] for e in world.log if e[0].startswith("set_") and e[1] == box}
        self.assertEqual(bounds, dict(set_left=226, set_top=318, set_width=80, set_height=17))
        self.assertEqual({e[0]: e[2] for e in world.log if e[0].startswith("set_") and e[1] == label}, dict(set_left=440, set_top=432))
        self.assertIn(("text", box, "Railgun"), world.log)
        self.assertEqual((world.get(box+0xC), world.get(box+0x120), world.get(box+0x124)),
                         (railgun.MAGIC_CHECKBOX, world.at["click"], FORM))
        self.assertEqual(world.get(label+0xC), railgun.MAGIC_LABEL)
        self.assertEqual(sum(1 for e in world.log if e[0] == "show hint"), 11)   # with the Ski jump box
        for magic, left, caption in ((railgun.MAGIC_SEC_RAIL, 16, "Railgun secondaries"), (railgun.MAGIC_TER_RAIL, 166, "Railgun tertiaries")):
            box2 = next(e[1] for e in world.log if e[0] == "parent" and e[2] == ADDITIONAL and world.get(e[1]+0xC) == magic)
            self.assertEqual({e[0]: e[2] for e in world.log if e[0].startswith("set_") and e[1] == box2},
                             dict(set_left=left, set_top=594, set_width=145, set_height=16))
            self.assertIn(("text", box2, caption), world.log)
        generators = next(e[1] for e in world.log if e[0] == "parent" and e[2] == FORM and world.get(e[1]+0xC) == railgun.MAGIC_GEN)
        self.assertEqual({e[0]: e[2] for e in world.log if e[0].startswith("set_") and e[1] == generators},
                         dict(set_left=550, set_top=448, set_width=64, set_height=22))
        self.assertEqual([world.get(generators+offset) for offset in (0x308, 0x30C, 0x310, 0x2E0, 0x2E4)],
                         [0, 2550, 10, world.at["gen_change"], FORM])
        self.assertIn("Generators (MW)", [e[2] for e in world.log if e[0] == "text"])
        heavy = next(e[1] for e in world.log if e[0] == "parent" and e[2] == ADDITIONAL and world.get(e[1]+0xC) == railgun.MAGIC_SUPER)
        self.assertEqual({e[0]: e[2] for e in world.log if e[0].startswith("set_") and e[1] == heavy},
                         dict(set_left=496, set_top=594, set_width=140, set_height=16))
        self.assertIn(("text", heavy, "Super heavy SSMs"), world.log)
        hyper = next(e[1] for e in world.log if e[0] == "parent" and e[2] == ADDITIONAL)
        self.assertEqual({e[0]: e[2] for e in world.log if e[0].startswith("set_") and e[1] == hyper},
                         dict(set_left=336, set_top=594, set_width=170, set_height=16))
        self.assertEqual((world.get(hyper+0xC), world.get(hyper+0x120), world.get(hyper+0x124)),
                         (railgun.MAGIC_HYPER, world.at["hyper_click"], FORM))
        self.assertIn(("text", hyper, "Hypersonic SSMs"), world.log)
        spin = next(e[1] for e in world.log if e[0] == "parent" and e[2] == AA_GROUP and world.get(e[1]) == SPIN_VMT)
        self.assertEqual({e[0]: e[2] for e in world.log if e[0].startswith("set_") and e[1] == spin},
                         dict(set_left=92, set_top=114, set_width=49, set_height=22))
        self.assertEqual((world.get(spin+0x308), world.get(spin+0x30C), world.get(spin+0x2E0), world.get(spin+0x2E4)),
                         (0, railgun.MAX_LASERS, world.at["laser_change"], FORM))
        self.assertIn("Lasers", [e[2] for e in world.log if e[0] == "text"])

    def test_legality_report_lists_each_railgun_failure(self):
        for owned, fuel, hp, errors in (((), 2, 100000, ["research", "Nuclear or Gas turbine"]),
                                        ((tree.RAILGUN,), 4, 10000, ["more power"]), ((tree.RAILGUN,), 5, 100000, [])):
            world = World(owned); world.design(railgun_byte=2, fuel=fuel, hp=hp)
            frame = STACK+0xA000; world.put(frame-0xC, ERRORS); world.put(frame-6, 1, 1); world.put(frame-5, 1, 1)
            self.assertTrue(world.run(railgun.SITES[1][1], 0x5D72B3, EBX=SHIP, ESI=FORM, EBP=frame))
            found = [e[1] for e in world.log if e[0] == "error"]
            self.assertEqual(len(found), len(errors), found)
            for text, part in zip(found, errors): self.assertIn(part, text)
            self.assertEqual(world.get(frame-6, 1), 0 if errors else 1)
            self.assertEqual((world.reg("EBX"), world.reg("ESI")), (SHIP, FORM))

    def test_pulsed_power_research_lightens_railgun_mounts(self):
        for owned, weight in (((), 1500), ((2314,), 1250), ((2314, 2315), 1100), ((2315,), 1100)):
            world = World(owned); world.design(railgun_byte=2); world.put(CELL, SHIP); world.put(TURRET+0x17, 1000)
            world.put(DATA+0x9800, FORM); world.put(world.railgun_info["design_form"], DATA+0x9800)
            self.assertTrue(world.run(0x93BD9D, 0x93BDA2, EBX=CELL, EDI=TURRET, ECX=0x1234))
            self.assertEqual((world.get(TURRET+0x17), world.reg("ECX")), (weight, 0x1234), owned)

    def test_mounts_heavier_costlier_and_ammunition_lighter(self):
        for railgun_byte, weight, cost, ammo in ((2, 1500, 2500, 400), (1, 1000, 1000, 800)):
            world = World(); world.design(railgun_byte=railgun_byte); world.put(CELL, SHIP); world.put(TURRET+0x17, 1000)
            self.assertTrue(world.run(0x93BD9D, 0x93BDA2, EBX=CELL, EDI=TURRET))
            self.assertEqual((world.get(TURRET+0x17), world.reg("EAX")), (weight, weight))
            self.assertTrue(world.run(0x93BE6A, 0x93BE72, EBX=CELL, ESI=1000))
            self.assertEqual((world.get(SHIP+0xA8C), world.reg("ESI")), (cost, 1000))
            self.assertTrue(world.run(0x93C25F, 0x93C267, EBX=CELL, EAX=800))
            self.assertEqual(world.get(SHIP+0xAAC), ammo)


class LaserTests(unittest.TestCase):
    def test_lasers_need_research_and_are_stored_on_both_designs(self):
        for owned, requested, stored in (((), 3, 0), ((tree.LASERS,), 3, 3), ((tree.LASERS,), 20, railgun.MAX_LASERS)):
            world = World(owned); world.design(); world.design(ship=SHIP2)
            world.guard(SHIP, 0x100); world.guard(SHIP2)   # 0x100: another extension bit that must survive
            world.spin[LASERS] = requested
            world.call(world.at["laser_change"], FORM, LASERS)
            self.assertEqual((world.lasers(SHIP), world.lasers(SHIP2)), (stored, stored), owned)
            self.assertEqual(world.get(SHIP+extension.CLASSES["design"][1]) & 0x100, 0x100)
            messages = [e[1] for e in world.log if e[0] == "message"]
            self.assertEqual(bool(messages), not owned)
            if owned: self.assertIn("refresh", [e[0] for e in world.log])

    def test_refresh_shows_the_count_silently_and_enables_with_research(self):
        world = World((tree.LASERS,)); world.design(); world.guard(SHIP, 4)
        world.call(world.at["laser_sync"], FORM)
        self.assertIn(("spin", LASERS, 4, 0), world.log)   # OnChange cleared while setting
        self.assertEqual(world.get(LASERS+0x2E0), world.at["laser_change"])
        self.assertIn(("enabled", LASERS, 1), world.log)
        world = World(()); world.design(); world.guard(SHIP, 0)
        world.call(world.at["laser_sync"], FORM)
        self.assertIn(("enabled", LASERS, 0), world.log)

    def test_lasers_draw_power_weigh_and_cost(self):
        world = World(); world.guns = 0; world.design(fuel=4, hp=100000, calibre=0); world.guard(SHIP, 5)
        self.assertEqual((world.call(world.at["power"], SHIP, NATION), world.reg("EDX")), (5*railgun.LASER_MW, 18))
        world.put(CELL, SHIP)
        self.assertTrue(world.run(0x93C25F, 0x93C267, EBX=CELL, EAX=800))
        self.assertEqual((world.get(SHIP+0xAA4), world.get(SHIP+0xA8C)), (5*railgun.LASER_TONS, 5*railgun.LASER_COST))

    def test_legality_lists_laser_research_and_power(self):
        for owned, fuel, errors in (((), 4, ["Shipboard high-energy lasers"]), ((tree.LASERS,), 2, ["more power"]), ((tree.LASERS,), 4, [])):
            world = World(owned); world.design(fuel=fuel, hp=100000, calibre=0); world.guard(SHIP, 2)
            frame = STACK+0xA000; world.put(frame-0xC, ERRORS); world.put(frame-6, 1, 1); world.put(frame-5, 1, 1)
            self.assertTrue(world.run(railgun.SITES[1][1], 0x5D72B3, EBX=SHIP, ESI=FORM, EBP=frame))
            found = [e[1] for e in world.log if e[0] == "error"]
            self.assertEqual(len(found), len(errors), found)
            for text, part in zip(found, errors): self.assertIn(part, text)

    def test_laser_layer_before_ciws_with_weather_and_hypersonic_missiles(self):
        frame, missile = STACK+0xA000, DATA+0xB000
        precipitation, sea = DATA+0xC000, DATA+0xC010
        for lasers, rain, rough, hyper, roll, shot in ((4, 0, 0, 0, 59, True), (4, 0, 0, 0, 60, False), (8, 0, 0, 0, 59, True),
                                                       (4, 1, 0, 0, 29, True), (4, 1, 0, 0, 30, False), (4, 1, 1, 0, 14, True),
                                                       (4, 0, 0, 1, 17, True), (4, 0, 0, 1, 18, False), (0, 0, 0, 0, 0, False)):
            world = World(); world.design(); world.guard(SHIP, lasers)
            world.put(world.railgun_info["precipitation"], precipitation); world.put(precipitation, 3 if rain else railgun.CLEAR_WEATHER, 1)
            world.put(world.railgun_info["sea"], sea); world.put(sea, railgun.SEA_ROUGH if rough else 1)
            world.put(world.at["missile_table"]+0x40, missile if hyper else 0); world.put(world.at["missile_table"]+0x44, railgun.HYPER_BIT)
            world.rolls = [99, roll]; world.damage = 10
            stop = world.railgun_info["ciws_shot"] if shot else world.railgun_info["ciws_step"]
            self.assertTrue(world.run(0x8C1584, stop, ESI=SHIP, EBX=missile, EBP=frame), (lasers, rain, rough, hyper, roll))
            if shot: self.assertIn(("shot", " Incoming missile shot down by laser."), world.log)


class RailgunPointDefenceTests(unittest.TestCase):
    def test_dp_railguns_shoot_down_missiles_after_the_laser_layer(self):
        frame, missile, main = STACK+0xA000, DATA+0xB000, DATA+0xB800
        ident, percent, cap = tree.RAILGUN_POINT_DEFENCE
        sec, ter = railgun.SECONDARY_RAIL_BIT, railgun.TERTIARY_RAIL_BIT
        for owned, byte, dp, bits, hyper, roll, shot in (((ident,), 2, (1, 0, 0), 0, 0, 19, True),
                                                         ((ident,), 2, (1, 0, 0), 0, 0, 20, False),
                                                         ((ident,), 2, (0, 1, 1), sec | ter, 0, 39, True),   # 20+20
                                                         ((ident,), 2, (1, 1, 1), sec | ter, 0, 49, True),   # 60 capped at 50
                                                         ((ident,), 2, (1, 1, 1), sec | ter, 0, 50, False),
                                                         ((ident,), 2, (1, 1, 1), sec | ter, 1, 15, True),   # a third: 16
                                                         ((ident,), 2, (1, 1, 1), sec | ter, 1, 16, False),
                                                         ((), 2, (1, 0, 0), 0, 0, 0, False),
                                                         ((ident,), 1, (1, 0, 0), 0, 0, 0, False),           # guns, not railguns
                                                         ((ident,), 2, (0, 0, 0), sec, 0, 0, False)):        # not DP
            world = World(owned); world.design(railgun_byte=byte); world.guard(SHIP, bits); world.put(SHIP+0x14, 3)
            for battery, flag in enumerate(dp): world.put(SHIP+0x85+battery, flag, 1)
            world.put(world.railgun_info["main"], main); world.put(main, DATA+0xB900)
            world.stubs[world.railgun_info["nation"]] = lambda: NATION if world.reg("EDX") == 3 else 0
            world.put(world.at["missile_table"]+0x40, missile if hyper else 0); world.put(world.at["missile_table"]+0x44, railgun.HYPER_BIT)
            world.rolls = [roll]
            stop = world.railgun_info["ciws_shot"] if shot else world.railgun_info["ciws_step"]
            self.assertTrue(world.run(world.at["rail_layer"], stop, ESI=SHIP, EBX=missile, EBP=frame), (owned, byte, dp, bits, hyper, roll))
            if shot: self.assertIn(("shot", " Incoming missile shot down by railgun."), world.log)


class GeneratorTests(unittest.TestCase):
    def units(self, world, ship): return world.get(ship+extension.CLASSES["design"][1]) >> railgun.GEN_SHIFT & 0xFF

    def test_generators_need_research_and_are_stored_on_both_designs(self):
        power = tree.INTEGRATED_POWER[0]
        for owned, requested, stored in (((), 120, 0), ((power,), 125, 12), ((power,), 9000, 255), ((), 0, 0)):
            world = World(owned); world.design(); world.design(ship=SHIP2)
            world.guard(SHIP, railgun.HYPER_BIT | 3); world.guard(SHIP2, 0x7F0000)   # other bits and old units
            world.spin[GEN] = requested
            world.call(world.at["gen_change"], FORM, GEN)
            if not owned and requested:
                self.assertEqual(self.units(world, SHIP), 0)
                self.assertTrue(any(e[0] == "message" and "Integrated power system" in e[1] for e in world.log))
                continue
            self.assertEqual((self.units(world, SHIP), self.units(world, SHIP2)), (stored, stored), owned)
            self.assertEqual(world.get(SHIP+extension.CLASSES["design"][1]) & 0xFFFF, railgun.HYPER_BIT | 3)
            self.assertIn("refresh", [e[0] for e in world.log])

    def test_refresh_shows_the_mw_silently_and_enables_with_research(self):
        world = World((tree.INTEGRATED_POWER[0],)); world.design(); world.guard(SHIP, 7 << railgun.GEN_SHIFT)
        world.call(world.at["gen_sync"], FORM)
        self.assertIn(("spin", GEN, 70, 0), world.log)   # OnChange cleared while setting
        self.assertEqual(world.get(GEN+0x2E0), world.at["gen_change"])
        self.assertIn(("enabled", GEN, 1), world.log)
        world = World(()); world.design(); world.guard(SHIP, 0)
        world.call(world.at["gen_sync"], FORM)
        self.assertIn(("enabled", GEN, 0), world.log)

    def test_generators_add_spare_power_weight_and_cost_on_any_propulsion(self):
        for fuel, spare in ((4, 18), (2, 0)):   # gas turbine 100,000 hp spares 18 MW; oil-fired turbines nothing
            world = World(); world.guns = 0; world.design(fuel=fuel, hp=100000, calibre=0); world.guard(SHIP, 12 << railgun.GEN_SHIFT)
            self.assertEqual((world.call(world.at["power"], SHIP, NATION), world.reg("EDX")), (0, spare+120))
        world.put(CELL, SHIP)
        self.assertTrue(world.run(0x93C25F, 0x93C267, EBX=CELL, EAX=800))
        self.assertEqual((world.get(SHIP+0xAA4), world.get(SHIP+0xA8C)), (12*railgun.GEN_TONS, 12*railgun.GEN_COST))

    def test_legality_lists_generator_research(self):
        for owned, errors in (((), ["Integrated power system"]), ((tree.INTEGRATED_POWER[0],), [])):
            world = World(owned); world.design(fuel=2, hp=100000, calibre=0); world.guard(SHIP, 5 << railgun.GEN_SHIFT)
            frame = STACK+0xA000; world.put(frame-0xC, ERRORS); world.put(frame-6, 1, 1); world.put(frame-5, 1, 1)
            self.assertTrue(world.run(railgun.SITES[1][1], 0x5D72B3, EBX=SHIP, ESI=FORM, EBP=frame))
            found = [e[1] for e in world.log if e[0] == "error"]
            self.assertEqual(len(found), len(errors), found)
            for text, part in zip(found, errors): self.assertIn(part, text)


class HypersonicTests(unittest.TestCase):
    def test_box_needs_research_and_sets_the_bit_on_both_designs(self):
        data = lambda world, ship: world.get(ship+extension.CLASSES["design"][1])
        for owned in ((), (tree.HYPERSONIC,)):
            world = World(owned); world.design(); world.design(ship=SHIP2)
            world.guard(SHIP, 3); world.guard(SHIP2)                       # 3 lasers must survive
            world.checked[HYPER] = 1
            world.call(world.at["hyper_click"], FORM, HYPER)
            expected = (3 | railgun.HYPER_BIT, railgun.HYPER_BIT) if owned else (3, 0)
            self.assertEqual((data(world, SHIP), data(world, SHIP2)), expected, owned)
            self.assertEqual(bool([e for e in world.log if e[0] == "message"]), not owned)
            if not owned: self.assertIn(("checked", HYPER, 0, 0), world.log)   # unticked without firing OnClick
        world.checked[HYPER] = 0
        world.call(world.at["hyper_click"], FORM, HYPER)
        self.assertEqual((data(world, SHIP), data(world, SHIP2)), (3, 0))

    def test_refresh_mirrors_the_bit_and_enables_with_research(self):
        for owned, bit, editable, checked, enabled in (((), 0, 1, 0, 0), ((tree.HYPERSONIC,), 0, 1, 0, 1),
                                                       ((), railgun.HYPER_BIT, 1, 1, 1), ((tree.HYPERSONIC,), railgun.HYPER_BIT, 0, 1, 0)):
            world = World(owned); world.design(); world.guard(SHIP, bit); world.put(FORM+0xE67, editable, 1)
            world.checked[HYPER] = 1-checked
            world.call(world.at["hyper_sync"], FORM)
            self.assertIn(("checked", HYPER, checked, 0), world.log)
            self.assertEqual(world.get(HYPER+0x120), world.at["hyper_click"])
            self.assertIn(("enabled", HYPER, enabled), world.log, (owned, bit, editable))

    def test_legality_reports_missing_research(self):
        for owned, errors in (((), 1), ((tree.HYPERSONIC,), 0)):
            world = World(owned); world.design(); world.guard(SHIP, railgun.HYPER_BIT)
            frame = STACK+0xA000; world.put(frame-0xC, ERRORS); world.put(frame-6, 1, 1); world.put(frame-5, 1, 1)
            self.assertTrue(world.run(railgun.SITES[1][1], 0x5D72B3, EBX=SHIP, ESI=FORM, EBP=frame))
            found = [e[1] for e in world.log if e[0] == "error"]
            self.assertEqual(len(found), errors, found)
            if errors: self.assertIn("Hypersonic anti-ship missiles", found[0])

    def test_vls_ssm_cells_weigh_and_cost_more(self):
        mounts = ((4, 16), (6, 8), (5, 4), (2, 32), (5, 64))   # (MountType, Tubes): SSM VLS, SSM launcher, SAM VLS
        listing, items = DATA+0xD000, DATA+0xD100
        load = sum(railgun.CELL_COST[kind-1]*tubes for kind, tubes in mounts if tubes >= 8)   # every VLS cell's missile
        self.assertEqual(load, 100*16+30*8+40*32+60*64)
        for data, tons, cost in ((railgun.HYPER_BIT | 2, 20+5*16+1*8+2*64, 200+20*(16+8+64)+load), (2, 20, 200+load)):
            world = World(); world.design(); world.guard(SHIP, data); world.put(CELL, SHIP)
            world.put(SHIP+0x9E, listing); world.put(listing+4, items); world.put(listing+8, len(mounts))
            for i, (kind, tubes) in enumerate(mounts):
                mount = DATA+0xD200+0x20*i; world.put(items+4*i, mount); world.put(mount+4, tubes); world.put(mount+0xE, kind, 1)
            self.assertTrue(world.run(0x93C25F, 0x93C267, EBX=CELL, EAX=800))
            self.assertEqual((world.get(SHIP+0xAA4), world.get(SHIP+0xA8C), world.reg("EBX")), (tons, cost, CELL), hex(data))

    def test_launches_are_remembered_by_missile_and_keep_their_speed(self):
        frame, missile = STACK+0xA000, DATA+0xB000
        world = World(); world.guard(FIGHTER, railgun.HYPER_BIT, kind="fighting"); world.guard(SHIP2, kind="fighting")
        held = lambda: [world.get(world.at["missile_table"]+8*i) for i in range(railgun.HYPER_SLOTS)].count(missile)
        for site, ship, expected in ((0x878033, FIGHTER, 1), (0x8D4931, SHIP2, 0), (0x8782E8, FIGHTER, 1)):
            self.assertTrue(world.run(site, railgun.NATIVE["fire_ssm"], EBX=ship, EAX=0x11, ECX=0x22, EDX=0x33))
            self.assertEqual((world.reg("EAX"), world.reg("ECX"), world.reg("EDX"), world.get(world.reg("ESP"))),
                             (0x11, 0x22, 0x33, site+5))
            world.put(frame+0x14, 450)                                     # the same address again: a reused object
            self.assertTrue(world.run(0x8763DB, 0x8763E1, EBX=missile, EBP=frame))
            self.assertEqual((world.get(missile+0x14), held(), world.get(world.at["hyper_pending"])), (450, expected, 0))
        world.put(frame-0x18, FIGHTER)                                     # this launch keeps its ship in a local
        self.assertTrue(world.run(0x5ADBA1, railgun.NATIVE["fire_ssm"], EBP=frame))
        self.assertEqual(world.get(world.at["hyper_pending"]), railgun.HYPER_BIT)

    def test_a_researched_land_battery_launches_ballistic_missiles(self):
        import modern_tree as tree
        for owned, kind, guarded, expected in (({tree.ASBM}, 12, True, railgun.HYPER_BIT), (set(), 12, True, 0),
                                               ({tree.ASBM}, 4, True, 0), ({tree.ASBM}, 12, False, 0)):   # not a ship object
            world = World(); world.owned = owned; world.stubs[0x750040] = lambda: NATION   # GetBNation
            if guarded: world.guard(SHIP2, kind="fighting")
            world.put(SHIP2+0x9D3, kind, 1); world.put(SHIP2+0x14, 3)
            self.assertTrue(world.run(0x878033, railgun.NATIVE["fire_ssm"], EBX=SHIP2, EAX=0x11, ECX=0x22, EDX=0x33))
            self.assertEqual((world.reg("EAX"), world.reg("ECX"), world.reg("EDX"), world.get(world.at["hyper_pending"])),
                             (0x11, 0x22, 0x33, expected), (owned, kind, guarded))

    def test_late_aircraft_of_a_researched_nation_launch_hypersonic_missiles(self):
        missile, frame, main, formation, model = DATA+0xB000, STACK+0xA000, DATA+0xB800, DATA+0xD000, DATA+0xD100
        year = tree.HYPERSONIC_AIRCRAFT_YEAR
        for owned, built, hyper in (((tree.HYPERSONIC,), year, True), ((tree.HYPERSONIC,), year-1, False), ((), 2030, False)):
            world = World(owned); table = world.at["missile_table"]
            world.put(world.railgun_info["main"], main); world.put(main, DATA+0xB900)
            world.stubs[world.railgun_info["nation"]] = lambda: NATION if world.reg("EDX") == 3 else 0
            world.vm.mem_write(missile, bytes(0x60)); world.put(formation+0x10, model); world.put(model+0xC, built)
            world.put(frame-0x20, formation); world.put(frame-8, 3)
            world.put(table+0x10, missile); world.put(table+0x14, railgun.HYPER_BIT)       # an earlier missile's address
            self.assertTrue(world.run(0x849D37, 0x849D3E, EBX=missile, EBP=frame, ESI=0x1111, EDI=0x2222), (owned, built))
            self.assertEqual((world.get(missile+0x14), world.reg("EBX"), world.reg("ESI"), world.reg("EDI")),
                             (300, missile, 0x1111, 0x2222))
            entries = [(world.get(table+8*i), world.get(table+8*i+4)) for i in range(railgun.HYPER_SLOTS)]
            self.assertEqual([e for e in entries if e[0] == missile], [(missile, railgun.HYPER_BIT)] if hyper else [], (owned, built))

    def test_interception_layers_against_hypersonic_and_stealth_missiles(self):
        """30% of kills stand against a hypersonic missile (60% for the SAMs of a nation with hypersonic interceptors),
        then 67% of those left against an SSM of a nation with stealth missiles (the firer: missile +3Eh)."""
        missile, frame, main, n = DATA+0xB000, STACK+0xA000, DATA+0xB800, railgun.NATIVE
        attacker, defender = DATA+0xC000, DATA+0xC100
        stealth, (interceptors, sam_keep) = tree.STEALTH_SSM[0], tree.HYPERSONIC_SAM
        world = World()
        world.put(world.railgun_info["main"], main); world.put(main, DATA+0xB900)
        world.stubs[world.railgun_info["nation"]] = lambda: {3: attacker, 4: defender}.get(world.reg("EDX"), 0)
        world.vm.mem_write(missile, bytes(0x60)); world.put(missile+0x3E, 3); world.put(SHIP+0x14, 4)
        for site, kill, survive, sam in ((0x8C12A6, n["sam1_ok"], n["sam1_fail"], True),
                                         (0x8C1360, n["sam2_ok"], n["sam2_fail"], True),
                                         (0x8C140D, n["layer3_ok"], n["layer3_fail"], True),
                                         (0x8C160D, n["ciws_back"], n["ciws_fail"], False),
                                         (0x8C16F9, n["maa_back"], n["maa_fail"], False)):
            for owned, hyper, hit, rolls, expected in (
                    ((), 0, 1, [], kill), ((), 1, 1, [29], kill), ((), 1, 1, [30], survive), ((), 1, 0, [], survive),
                    (((defender, interceptors),), 1, 1, [sam_keep-1], kill if sam else survive),   # SAMs only
                    (((defender, interceptors),), 1, 1, [sam_keep], survive),
                    (((attacker, interceptors),), 1, 1, [30], survive),                            # the defender's
                    (((attacker, stealth),), 0, 1, [66], kill), (((attacker, stealth),), 0, 1, [67], survive),
                    (((defender, stealth),), 0, 1, [], kill),                                       # the firer's
                    (((attacker, stealth),), 1, 1, [29, 66], kill), (((attacker, stealth),), 1, 1, [29, 67], survive)):
                if not (sam or hit): continue                               # gun layers are hooked at the kill itself
                world.stubs[n["has_research"]] = lambda owned=owned: int((world.reg("EAX"), world.reg("EDX")) in owned)
                world.put(world.at["missile_table"]+8, missile if hyper else 0); world.put(world.at["missile_table"]+12, railgun.HYPER_BIT)
                world.rolls = list(rolls)
                self.assertTrue(world.run(site, expected, EAX=hit, EBX=missile, ESI=SHIP, EBP=frame),
                                (hex(site), owned, hyper, hit, rolls))
                self.assertEqual(world.rolls, [])
                if expected == kill and not sam: self.assertEqual(world.reg("EAX"), frame-4)   # message line replayed


class BattleTests(unittest.TestCase):
    def test_main_battery_range_doubles_only_for_railguns(self):
        world = World(); frame = STACK+0xA000
        for battery, branch in ((1, 0x90ABCC), (2, 0x90ABC4)):
            self.assertTrue(world.run(0x90ABBF, branch, EDX=battery))
            self.assertEqual(world.get(world.at["battery"]), battery)
        for railgun_byte, battery, expected in ((2, 1, 40000), (2, 2, 20000), (1, 1, 20000)):
            world.design(railgun_byte=railgun_byte); world.put(world.at["battery"], battery)
            world.put(frame-8, 20000); world.put(frame-4, SHIP)
            self.assertTrue(world.run(0x90ACF7, 0x90ACFC, EBP=frame))
            self.assertEqual(world.reg("EAX"), expected)

    def test_only_main_battery_shots_carry_the_railgun_flag_into_penetration(self):
        world = World(); frame = STACK+0xA000
        for railgun_byte, battery, passed in ((2, 1, 2), (2, 2, 1), (1, 1, 1), (0, 1, 0)):
            world.design(railgun_byte=railgun_byte); world.put(frame-0x24, SHIP); world.put(frame+0x18, battery)
            self.assertTrue(world.run(0x909946, 0x909950, EBP=frame))
            self.assertEqual(world.reg("EAX"), passed)
        for flag, calibre, yards in ((2, 12, 10000), (1, 8, 20000)):   # railgun: +4 inches at half the range
            sp = STACK+0x8000; world.put(sp+0xC, flag)
            self.assertTrue(world.run(0x91D898, 0x91D8A9, EAX=8, EDX=20000))
            self.assertEqual((world.get(world.reg("EBP")-4), world.reg("ESI")), (calibre, yards))

    def test_railgun_secondaries_and_tertiaries_double_range_and_carry_the_railgun_flag(self):
        world = World(); frame = STACK+0xA000; sec, ter = railgun.SECONDARY_RAIL_BIT, railgun.TERTIARY_RAIL_BIT
        for bits, battery, expected in ((sec, 2, 40000), (sec, 3, 20000), (ter, 3, 40000), (0, 2, 20000), (sec | ter, 1, 20000)):
            world.design(); world.guard(SHIP, bits); world.put(world.at["battery"], battery)
            world.put(frame-8, 20000); world.put(frame-4, SHIP)
            self.assertTrue(world.run(0x90ACF7, 0x90ACFC, EBP=frame))
            self.assertEqual(world.reg("EAX"), expected, (bits, battery))
        for bits, railgun_byte, battery, passed in ((sec, 0, 2, 2), (ter, 2, 2, 1), (ter, 0, 3, 2), (sec, 1, 1, 1), (0, 0, 3, 0)):
            world.design(railgun_byte=railgun_byte); world.guard(SHIP, bits)
            world.put(frame-0x24, SHIP); world.put(frame+0x18, battery)
            self.assertTrue(world.run(0x909946, 0x909950, EBP=frame))
            self.assertEqual(world.reg("EAX"), passed, (bits, railgun_byte, battery))

    def test_railgun_secondaries_weigh_and_cost_their_pulsed_power(self):
        world = World(); world.guns = 0; world.design(fuel=5, hp=100000, calibre=0)
        world.put(SHIP+0x71, 5); world.put(SHIP+0xAE, 8); world.guard(SHIP, railgun.SECONDARY_RAIL_BIT)   # 128 MW
        world.put(CELL, SHIP)
        self.assertTrue(world.run(0x93C25F, 0x93C267, EBX=CELL, EAX=800))
        self.assertEqual((world.get(SHIP+0xAA4), world.get(SHIP+0xA8C)), (128*railgun.RAIL_TONS_PER_MW, 128*railgun.RAIL_COST_PER_MW))

    def test_railguns_beyond_the_20_inch_table_keep_gaining_penetration(self):
        world, sp = World(), STACK+0x8000
        for kyd in range(1, 31): world.put(0xA23634+20*256+4*kyd-0x200, 100+10*kyd)   # native 20-inch vertical row
        def muldiv():   # kernel32 MulDiv(a, b, c), stdcall: the routine's import thunk
            top = world.reg("ESP"); a, b, c = (world.get(top+4*i) for i in (1, 2, 3)); world.pop_extra = 12
            return (a*b+c//2)//c
        world.stubs[0x317F0C] = muldiv
        def penetration(calibre, yards, flag):
            world.vm.mem_write(sp, bytes(0x18)); world.put(sp, STOP); world.put(sp+0xC, flag, 1); world.vm.mem_write(STOP, b"\xc3")
            self.assertTrue(world.run(0x91D898, STOP, EAX=calibre, EDX=yards, ECX=0, ESP=sp))
            self.assertEqual((world.reg("ESP"), world.reg("EBX")), (sp+0x18, 0x5151))   # ret 14h; registers kept
            return world.reg("EAX")
        world.vm.reg_write(UC_X86_REG_EBX, 0x5151)
        native20 = penetration(20, 5000, 0)
        self.assertGreater(native20, 0)
        for calibre, expected in ((16, native20), (17, native20*21//20), (18, native20*22//20), (20, native20*24//20)):
            self.assertEqual(penetration(calibre, 10000, 2), expected, calibre)   # railgun: +4 inches, half the range

    def test_inert_rounds_no_magazine_or_turret_flash_explosions(self):
        world = World(); frame = STACK+0xA000
        for railgun_byte, calibre, target in ((2, 8, 0x8F882C), (0, 8, 0x8F8721), (0, 4, 0x8F870B)):
            world.design(railgun_byte=railgun_byte, calibre=calibre); world.put(frame-8, SHIP)
            self.assertTrue(world.run(0x8F8702, target, EBP=frame), (railgun_byte, calibre))
        for railgun_byte, target in ((2, 0x8F7FEA), (0, 0x8F7F55)):
            world.design(railgun_byte=railgun_byte); world.put(frame-8, SHIP)
            self.assertTrue(world.run(0x8F7F4C, target, EBP=frame))
        for railgun_byte, chance, roll, target in ((2, 90, 10, 0x8F8D38), (0, 90, 10, 0x8F8C56), (0, 10, 90, 0x8F8D38)):
            world.design(railgun_byte=railgun_byte); world.put(frame-8, SHIP)
            self.assertTrue(world.run(0x8F8C4E, target, EBP=frame, ESI=chance, EAX=roll))


class SuperHeavyTests(unittest.TestCase):
    def test_box_needs_research_and_a_ca_bc_or_bb_hull(self):
        data = lambda world: world.get(SHIP+extension.CLASSES["design"][1])
        for owned, kind, ticked, refusal in (((), 3, False, "research"), ((tree.SUPER_HEAVY,), 9, False, "CA, BC or BB"),
                                             ((tree.SUPER_HEAVY,), 3, True, None), ((tree.SUPER_HEAVY,), 0, True, None),
                                             ((tree.SUPER_HEAVY,), 1, True, None)):
            world = World(owned); world.design(); world.design(ship=SHIP2); world.put(SHIP+0x9D3, kind, 1)
            world.guard(SHIP, railgun.HYPER_BIT | 2); world.guard(SHIP2)    # hypersonic and 2 lasers stay
            world.checked[SUPER] = 1
            world.call(world.at["super_click"], FORM, SUPER)
            self.assertEqual(data(world), railgun.HYPER_BIT | 2 | (railgun.SUPER_BIT if ticked else 0), (owned, kind))
            messages = [e[1] for e in world.log if e[0] == "message"]
            if refusal: self.assertEqual(len(messages), 1); self.assertIn(refusal, messages[0])
            else: self.assertEqual(messages, [])

    def test_legality_lists_research_and_hull(self):
        for owned, kind, errors in (((), 3, ["Effective cruise missiles"]), ((tree.SUPER_HEAVY,), 4, ["CA, BC or BB"]),
                                    ((), 9, ["Effective cruise missiles", "CA, BC or BB"]), ((tree.SUPER_HEAVY,), 1, [])):
            world = World(owned); world.design(); world.guard(SHIP, railgun.SUPER_BIT); world.put(SHIP+0x9D3, kind, 1)
            frame = STACK+0xA000; world.put(frame-0xC, ERRORS); world.put(frame-6, 1, 1); world.put(frame-5, 1, 1)
            self.assertTrue(world.run(railgun.SITES[1][1], 0x5D72B3, EBX=SHIP, ESI=FORM, EBP=frame))
            found = [e[1] for e in world.log if e[0] == "error"]
            self.assertEqual(len(found), len(errors), found)
            for text, part in zip(found, errors): self.assertIn(part, text)

    def test_heavy_ssm_mounts_weigh_twice_and_cost_more(self):
        mounts = ((4, 2, 100), (4, 64, 640), (5, 4, 50), (2, 32, 160))   # (MountType, Tubes, native weight)
        listing, items, hyper = DATA+0xD000, DATA+0xD100, (5*64, 20*64)   # hypersonic: the 64-cell heavy SSM bank
        load = railgun.CELL_COST[3]*64+railgun.CELL_COST[1]*32                              # the two VLS banks' missiles
        for data, tons, cost in ((railgun.SUPER_BIT, 740, 7400+load), (0, 0, load),
                                 (railgun.SUPER_BIT | railgun.HYPER_BIT, 740+hyper[0], 7400+hyper[1]+load)):
            world = World(); world.design(); world.guard(SHIP, data); world.put(CELL, SHIP)
            world.put(SHIP+0x9E, listing); world.put(listing+4, items); world.put(listing+8, len(mounts))
            for i, (kind, tubes, weight) in enumerate(mounts):
                mount = DATA+0xD200+0x20*i; world.put(items+4*i, mount); world.put(mount+4, tubes)
                world.put(mount+0xA, weight); world.put(mount+0xE, kind, 1)
            self.assertTrue(world.run(0x93C25F, 0x93C267, EBX=CELL, EAX=800))
            self.assertEqual((world.get(SHIP+0xAA4), world.get(SHIP+0xA8C), world.reg("EBX")), (tons, cost, CELL), hex(data))

    def test_heavy_ssm_range_doubles_at_firing_decisions(self):
        frame, world = STACK+0xA000, World()
        world.stubs[railgun.NATIVE["range"]] = lambda: 1000
        world.guard(FIGHTER, railgun.SUPER_BIT, kind="fighting"); world.guard(SHIP2, kind="fighting")
        world.put(frame-8, FIGHTER); world.put(frame+4, FIGHTER)          # [ebp-8], and [ebp-0Ch] of frame+0x10
        for site, ship, kind, expected in ((0x877E4E, dict(EBX=FIGHTER), 4, 2000), (0x877E4E, dict(EBX=FIGHTER), 5, 1000),
                                           (0x877E4E, dict(EBX=SHIP2), 4, 1000), (0x91B8B6, dict(EDI=FIGHTER), 4, 2000),
                                           (0x87746E, dict(EBP=frame), 4, 2000), (0x5AE54C, dict(EBP=frame+0x10), 4, 2000)):
            self.assertTrue(world.run(site, site+5, EDX=kind, **ship))
            self.assertEqual(world.reg("EAX"), expected, (hex(site), kind))

    def test_launch_record_doubles_heavy_ssm_range_and_keeps_flags(self):
        frame, missile, both = STACK+0xA000, DATA+0xB000, railgun.SUPER_BIT | railgun.HYPER_BIT
        for flags, kind, flight, stored in ((both, 31, 10000, both), (railgun.SUPER_BIT, 32, 5000, 0), (both, 33, 5000, railgun.HYPER_BIT)):
            world = World(); world.put(world.at["hyper_pending"], flags); world.put(frame+0xC, kind); world.put(frame+0x14, 450)
            self.assertTrue(world.run(0x8763DB, 0x8763E1, EBX=missile, EBP=frame, EDI=5000))
            table = world.at["missile_table"]
            kept = [world.get(table+8*i+4) for i in range(railgun.HYPER_SLOTS) if world.get(table+8*i) == missile] or [0]
            self.assertEqual((world.reg("EDI"), kept, world.get(missile+0x14)), (flight, [stored], 450), (flags, kind))

    def test_super_heavy_missiles_hit_as_40_inch_shells(self):
        missile = DATA+0xB000
        for flagged, expected in ((True, railgun.SUPER_CALIBRE), (False, 31)):
            world = World(); world.put(missile+0x28, 31); world.rolls = [99]   # nuclear_subs' mission-kill roll: no radar damage
            if flagged: world.put(world.at["missile_table"]+8, missile); world.put(world.at["missile_table"]+12, railgun.SUPER_BIT)
            self.assertTrue(world.run(0x8C1B4B, 0x8C1B54, EBX=missile))
            sp = world.reg("ESP"); self.assertEqual((world.get(sp), world.get(sp+4)), (0x1388, expected))


class HeavyAATests(unittest.TestCase):
    def test_dp_railgun_main_battery_counts_one_and_a_half_times_in_the_heavy_aa_factor(self):
        world = World(); frame = STACK+0xA000
        for railgun_byte, expected in ((2, 30), (1, 20), (0, 20)):
            world.design(railgun_byte=railgun_byte); world.put(SHIP+0x9A, 0x1234); world.put(frame-0x20, 20)
            self.assertTrue(world.run(0x917088, 0x91708E, ESI=SHIP, EBP=frame))
            self.assertEqual((world.get(frame-0x20), world.reg("EAX")), (expected, 0x1234), railgun_byte)


class GunDataTests(unittest.TestCase):
    def test_secondary_and_tertiary_gun_data_never_show_the_main_battery_bonus(self):
        world = World()
        for railgun_byte, shown in ((2, 1), (1, 1), (0, 0)):
            world.design(railgun_byte=railgun_byte)
            world.call(world.at["gun_data"], SHIP)
            self.assertEqual(world.reg("EDX"), shown)


if __name__ == "__main__":
    unittest.main()

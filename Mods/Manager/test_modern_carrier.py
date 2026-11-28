"""Ski-jump flight decks and VTOL light jet fighters (modern_carrier), executed on the built adapter."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import modern_carrier as carrier
import modern_research as modern
import modern_sensors as sensors
import modern_tree as tree

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
CODE, DATA, STACK, HEAP, STOP = 0x2000000, 0x1300000, 0x1500000, 0x1600000, 0x2030000
FORM, SHIP, SHIP2, LIST, ITEMS, BOX, GROUP, NATION, MAIN = (DATA+0x2000, DATA+0x3000, DATA+0x4000, DATA+0x5000,
                                                             DATA+0x5100, DATA+0x6000, DATA+0x7000, DATA+0x8000, DATA+0x9000)
UNIT, TYPE, CARRIER = DATA+0xA000, DATA+0xA400, DATA+0xA800
CHECKBOX = carrier.NATIVE["checkbox_vmt"]


def u32(address): return struct.unpack_from("<I", BLOB, address-0x301000)[0]


class World:
    def __init__(self, owned=()):
        self.vm = vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address, size in ((0, 0x1000), (0x300000, 0x800000), (DATA, 0x20000), (STACK, 0x10000), (HEAP, 0x10000),
                              (CODE, 0x40000)):
            vm.mem_map(address, size)
        vm.mem_write(0x301000, BLOB)
        details = modern.discover(BLOB, 0x301000)
        self.info = details["carrier"]
        blocks, plans, _ = modern.build(CODE, details)
        for item in blocks+[dict(address=p["address"], bytes=p["replacement"]) for p in plans]:
            vm.mem_write(item["address"], bytes.fromhex(item["bytes"]))
        self.at = {b["name"][10:]: b["address"] for b in blocks if b["name"].startswith("Ski jump: ")}
        self.plans = {p["label"]: p for p in plans if p["label"].startswith("Ski jump")}
        self.owned, self.log, self.checked, self.heap = set(owned), [], {}, HEAP
        n = self.info
        self.stubs = {n["has_research"]: lambda: int(self.reg("EAX") == NATION and self.reg("EDX") in self.owned),
                      n["nation"]: lambda: NATION if (self.reg("EAX"), self.reg("EDX")) == (MAIN, 3) else 0,
                      n["message"]: lambda: self.note("message", self.text(self.reg("EAX"))),
                      n["recompute"]: lambda: self.note("recompute", self.reg("EAX")),
                      n["update"]: lambda: self.note("update"), n["refresh"]: lambda: self.note("refresh"),
                      n["assign"]: lambda: (self.put(self.reg("EAX"), self.reg("EDX")), self.note("hint", self.text(self.reg("EDX"))))[1],
                      n["set_text"]: lambda: self.note("text", self.reg("EAX"), self.text(self.reg("EDX"))),
                      n["set_show_hint"]: lambda: self.note("show hint", self.reg("EAX")),
                      u32(CHECKBOX+0x3C): self.construct, u32(CHECKBOX+0xA0): lambda: self.note("parent", self.reg("EAX"), self.reg("EDX")),
                      u32(CHECKBOX+0x16C): lambda: self.checked.get(self.reg("EAX"), 0),
                      u32(CHECKBOX+0x170): self.set_checked,
                      u32(CHECKBOX+0x9C): lambda: self.note("enabled", self.reg("EAX"), self.reg("EDX") & 0xFF)}
        for name in ("set_left", "set_top", "set_width", "set_height"):
            self.stubs[n[name]] = lambda name=name: self.note(name, self.reg("EAX"), self.reg("EDX"))
        vm.hook_add(UC_HOOK_CODE, self.boundary)
        self.put(n["main"], DATA+0x200); self.put(DATA+0x200, MAIN)
        # The designer form: our box is its only component; two designs; nation; Flight installations group.
        for address, value in ((FORM+0x10, LIST), (LIST+4, ITEMS), (LIST+8, 1), (ITEMS, BOX), (BOX, CHECKBOX),
                               (BOX+0xC, carrier.MAGIC_SKI), (BOX+0x120, self.at["click"]), (BOX+0x124, FORM),
                               (FORM+0x94C, GROUP), (GROUP+0x58, carrier.GROUP_WIDTH),          # 100% display scaling
                               (FORM+0xC63, NATION), (FORM+0xC6B, SHIP2), (FORM+0xE6C, SHIP)):
            self.put(address, value)
        self.put(FORM+0xE67, 1, 1)

    def put(self, address, value, size=4): self.vm.mem_write(address, (value & (1 << 8*size)-1).to_bytes(size, "little"))
    def get(self, address, size=4): return int.from_bytes(self.vm.mem_read(address, size), "little")
    def reg(self, name): return self.vm.reg_read(globals()["UC_X86_REG_"+name])
    def text(self, pointer): return bytes(self.vm.mem_read(pointer, self.get(pointer-4)*2)).decode("utf-16-le") if pointer else ""
    def note(self, *entry): self.log.append(entry); return 0

    def construct(self):
        obj = self.heap; self.heap += 0x400; self.vm.mem_write(obj, bytes(0x400)); self.put(obj, CHECKBOX)
        self.note("create", self.reg("ECX")); return obj

    def set_checked(self):
        obj, value = self.reg("EAX"), self.reg("EDX") & 0xFF
        self.checked[obj] = value; self.note("checked", obj, value, self.get(obj+0x120)); return 0

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
        self.vm.emu_start(address, STOP, count=300000)
        assert self.reg("ESP") == sp+4 and (self.reg("EBX"), self.reg("ESI"), self.reg("EDI")) == (0x2345, 0x3456, 0x4567)

    def design(self, deck=1, jet=0):
        for ship in (SHIP, SHIP2):
            self.vm.mem_write(ship, bytes(0xC00)); self.put(ship+0x9D9, deck, 1); self.put(ship+0x9DF, jet, 1)


class SaveKeyTests(unittest.TestCase):
    def test_the_five_jetcapable_calls_write_and_read_an_integer(self):
        world = World()
        expected = {name: carrier.NATIVE[new] for name, _, _, new in carrier.KEYS}
        for name, target in expected.items():
            plan = world.plans["Ski jump: JetCapable "+name]
            code = bytes.fromhex(plan["replacement"])
            self.assertEqual((code[0], plan["address"]+5+struct.unpack_from("<i", code, 1)[0]), (0xE8, target), name)
            self.assertEqual(len(code), 5)


class DesignerTests(unittest.TestCase):
    def test_the_box_is_made_once_under_flight_deck(self):
        world = World(); world.put(LIST+8, 0); world.design()
        world.call(world.at["sync"], FORM)
        box = next(e[1] for e in world.log if e[0] == "parent")
        self.assertEqual([e for e in world.log if e[0] == "create"], [("create", FORM)])
        self.assertEqual(("parent", box, GROUP), next(e for e in world.log if e[0] == "parent"))
        self.assertEqual({e[0]: e[2] for e in world.log if e[0].startswith("set_") and e[1] == box},
                         dict(zip(("set_left", "set_top", "set_width", "set_height"), carrier.SKI_BOUNDS)))
        self.assertIn(("text", box, "Ski jump"), world.log)
        self.assertEqual((world.get(box+0xC), world.get(box+0x120), world.get(box+0x124)),
                         (carrier.MAGIC_SKI, world.at["click"], FORM))
        # Windows display scaling at 150%: the game's group is 1.5 times wider, and the box follows it.
        world = World(); world.put(LIST+8, 0); world.design(); world.put(GROUP+0x58, 470)
        world.call(world.at["sync"], FORM)
        box = next(e[1] for e in world.log if e[0] == "parent")
        self.assertEqual({e[0]: e[2] for e in world.log if e[0].startswith("set_") and e[1] == box},
                         dict(zip(("set_left", "set_top", "set_width", "set_height"), (36, 87, 135, 21))))

    def test_the_box_mirrors_the_design_quietly_and_is_enabled_by_research_and_a_flight_deck(self):
        for owned, deck, jet, editable, checked, enabled in (
                ((tree.SKI_JUMP[0],), 1, 3, 1, 1, 1), ((), 1, 1, 1, 0, 0), ((tree.SKI_JUMP[0],), 1, 1, 1, 0, 1),
                ((), 1, 3, 1, 1, 1), ((tree.SKI_JUMP[0],), 0, 0, 1, 0, 0), ((tree.SKI_JUMP[0],), 1, 3, 0, 1, 0)):
            world = World(owned); world.design(deck, jet); world.put(FORM+0xE67, editable, 1)
            world.call(world.at["sync"], FORM)
            sets = [e for e in world.log if e[0] == "checked"]
            self.assertEqual(sets, [("checked", BOX, 1, 0)] if checked else [], (owned, deck, jet))   # OnClick off
            self.assertEqual(world.get(BOX+0x120), world.at["click"])
            self.assertEqual([e for e in world.log if e[0] == "enabled"], [("enabled", BOX, enabled)], (owned, deck, jet, editable))

    def test_ticking_needs_research_and_a_flight_deck_then_makes_both_designs_jet_capable_with_a_ski_jump(self):
        for owned, deck, message in (((), 1, carrier.TEXT["research"]), ((tree.SKI_JUMP[0],), 0, carrier.TEXT["deck"])):
            world = World(owned); world.design(deck); world.checked[BOX] = 1
            world.call(world.at["click"], FORM, BOX)
            self.assertIn(("message", message), world.log)
            self.assertEqual((world.get(SHIP+0x9DF, 1), world.get(SHIP2+0x9DF, 1), world.checked[BOX]), (0, 0, 0))
        world = World((tree.SKI_JUMP[0],)); world.design(); world.checked[BOX] = 1
        world.call(world.at["click"], FORM, BOX)
        self.assertEqual((world.get(SHIP+0x9DF, 1), world.get(SHIP2+0x9DF, 1)), (3, 3))
        self.assertEqual([e[0] for e in world.log if e[0] in ("recompute", "update", "refresh")], ["recompute", "update", "refresh"])

    def test_unticking_keeps_jet_capable(self):
        world = World((tree.SKI_JUMP[0],)); world.design(jet=3); world.checked[BOX] = 0
        world.call(world.at["click"], FORM, BOX)
        self.assertEqual((world.get(SHIP+0x9DF, 1), world.get(SHIP2+0x9DF, 1)), (1, 1))


class VtolTests(unittest.TestCase):
    def run_site(self, name, jet, role, owned):
        """The three native JetCapable tests: (carrier register, unit register) per site; True when the jet is
        accepted (the native 'jet capable' branch)."""
        world = World(owned)
        world.vm.mem_write(UNIT, bytes(0x100)); world.vm.mem_write(TYPE, bytes(0x100)); world.vm.mem_write(CARRIER, bytes(0x200))
        world.put(UNIT+0x1C, 3); world.put(UNIT+0xC, TYPE); world.put(TYPE+0x81, role, 1); world.put(CARRIER+0xF3, jet, 1)
        site = next(s for s in world.info["sites"] if s["name"] == name)
        registers = dict(space=dict(EBX=UNIT, ESI=CARRIER), unit=dict(EDI=UNIT, ESI=CARRIER), type=dict(ESI=UNIT, EDI=CARRIER))[name]
        ok, back = (world.info[name+"_ok"], world.info[name+"_back"])
        values = dict(EAX=0x1111, ECX=0x2222, EDX=0x3333, EBX=0x4444, ESI=0x5555, EDI=0x6666, EBP=STACK+0xA000, ESP=STACK+0x8000)
        values.update(registers)
        for reg, value in values.items(): world.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
        stops = []
        world.vm.hook_add(UC_HOOK_CODE, lambda vm, address, size, unused: (stops.append(address), vm.emu_stop())
                          if address in (ok, back) else None)
        world.vm.emu_start(site["address"], 0, count=10000)
        self.assertEqual([world.reg(r) for r in values], list(values.values()), name)   # every register kept
        return stops[0] == ok

    def test_a_vtol_nation_flies_light_jets_from_any_carrier(self):
        vtol = {tree.VTOL}
        for name in ("space", "unit", "type"):
            self.assertTrue(self.run_site(name, 1, carrier.LIGHT_JET, ()), name)           # jet capable: native
            self.assertTrue(self.run_site(name, 0, carrier.LIGHT_JET, vtol), name)         # VTOL light jets
            self.assertFalse(self.run_site(name, 0, carrier.LIGHT_JET, ()), name)          # without the research
        for name in ("unit", "type"):
            self.assertFalse(self.run_site(name, 0, 11, vtol), name)                        # heavy jets are not VTOL


class StobarAndAiTests(unittest.TestCase):
    def test_heavy_jets_take_more_deck_space_on_a_ski_jump_deck_without_catapults(self):
        for tons, jet, catapults, penalty in ((30000, 1, 2, True), (50000, 3, 0, True), (50000, 3, 2, False),
                                              (50000, 1, 0, False), (50000, 0, 0, False)):
            world = World(); world.vm.mem_write(CARRIER, bytes(0x200))
            world.put(CARRIER+0x2B, tons); world.put(CARRIER+0xF3, jet, 1); world.put(CARRIER+0xEF, catapults)
            info = world.info
            stops = []
            world.vm.hook_add(UC_HOOK_CODE, lambda vm, address, size, unused: (stops.append(address), vm.emu_stop())
                              if address in (info["stobar_penalty"], info["stobar_skip"]) else None)
            site = next(s for s in info["sites"] if s["name"] == "stobar")
            for reg, value in dict(EAX=1, ECX=2, EDX=3, EBX=4, ESI=CARRIER, EDI=6, ESP=STACK+0x8000).items():
                world.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
            world.vm.emu_start(site["address"], 0, count=1000)
            self.assertEqual(stops[0] == info["stobar_penalty"], penalty, (tons, jet, catapults))

    def run_ai(self, owned, deck=1, jet=0, catapults=0, capacity=15):
        """The AI designer after its jet decision: [EDI] the design, [EBP-0Ch] the nation. The stubbed weight
        calculation leaves 100 - 10 per aircraft (jet capable: 12 per aircraft)."""
        world = World(owned); world.design(deck, jet)
        world.put(SHIP+0x9DB, catapults); world.put(SHIP+0x9E0, capacity)
        frame = STACK+0xA000; world.put(frame-0xC, NATION); world.put(DATA+0x100, SHIP)

        def recompute():
            per = 12 if world.get(SHIP+0x9DF, 1) & 1 else 10
            world.put(SHIP+0xB20, 100-per*world.get(SHIP+0x9E0)); world.note("recompute"); return 0
        world.stubs[world.info["recompute"]] = recompute
        site = next(s for s in world.info["sites"] if s["name"] == "ai")
        values = dict(EAX=1, ECX=2, EDX=3, EBX=4, ESI=5, EDI=DATA+0x100, EBP=frame, ESP=STACK+0x8000)
        for reg, value in values.items(): world.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
        world.vm.emu_start(site["address"], world.info["ai_back"], count=100000)
        self.assertEqual([world.reg(r) for r in values], list(values.values()))
        self.assertEqual(world.get(frame-0x30), 0x10)                       # the replaced native store
        return world.get(SHIP+0x9DF, 1), world.get(SHIP+0x9E0)

    def test_ai_carriers_get_a_ski_jump_with_the_research(self):
        ski, jets = tree.SKI_JUMP[0], carrier.AI_JETS
        self.assertEqual(self.run_ai({ski, jets}), (3, 8))                   # trimmed until 100-12n >= 0
        self.assertEqual(self.run_ai({ski, jets}, capacity=5), (3, 5))
        self.assertEqual(self.run_ai({ski}, jet=1), (3, 15))                 # a jet deck without catapults
        self.assertEqual(self.run_ai({ski}, jet=1, catapults=2), (1, 15))
        self.assertEqual(self.run_ai({jets}), (0, 15))                       # no ski-jump research
        self.assertEqual(self.run_ai({ski}), (0, 15))                        # no jets research
        self.assertEqual(self.run_ai({ski, jets}, deck=0), (0, 15))          # no flight deck


class AvTests(unittest.TestCase):
    def test_a_jet_capable_av_takes_vtol_fighters_besides_floatplanes(self):
        vtol = {tree.VTOL}
        for role, jet, owned, ok in ((3, 0, (), True), (10, 1, vtol, True), (10, 0, vtol, False), (10, 1, (), False),
                                     (11, 1, vtol, False), (13, 1, vtol, False)):
            world = World(owned); info = world.info
            world.vm.mem_write(UNIT, bytes(0x100)); world.vm.mem_write(CARRIER, bytes(0x200))
            world.put(UNIT+0x1C, 3); world.put(CARRIER+0x14, 8, 1); world.put(CARRIER+0xF3, jet, 1)
            stops = []
            world.vm.hook_add(UC_HOOK_CODE, lambda vm, address, size, unused: (stops.append(address), vm.emu_stop())
                              if address in (info["av_ok"], info["av_refuse"]) else None)
            values = dict(EAX=CARRIER, ECX=0x2222, EDX=0x3333, EBX=0x4400 | role, ESI=0x5555, EDI=UNIT, ESP=STACK+0x8000)
            for reg, value in values.items(): world.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
            site = next(s for s in info["sites"] if s["name"] == "av_rule")
            world.vm.emu_start(site["address"], 0, count=1000)
            self.assertEqual(stops[0] == info["av_ok"], ok, (role, jet, owned))
            self.assertEqual([world.reg(r) for r in values], list(values.values()))


class UavRequestTests(unittest.TestCase):
    DIALOG, LISTBOX, ITEMS, ITEMS_VMT, FRAME = DATA+0xB000, DATA+0xB400, DATA+0xB800, DATA+0xBC00, STACK+0xA000

    def string(self, world, address, text):
        world.vm.mem_write(address-12, struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0")
        return address

    def site(self, world, name): return next(s["address"] for s in world.info["sites"] if s["name"] == name)

    def run_from(self, world, start, stop, **registers):
        values = dict(dict(EAX=0, EBX=0x2345, ECX=0x1234, EDX=0x3456, ESI=0x4567, EDI=0x5678, EBP=self.FRAME,
                           ESP=STACK+0x8000), **registers)
        for reg, value in values.items(): world.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
        world.vm.emu_start(start, stop, count=100000)
        return values

    def test_the_dialog_lists_uav_after_the_native_roles_with_the_research(self):
        for owned, develops, listed in (((tree.UAVS,), True, True), ((), True, False), ((tree.UAVS,), False, False)):
            world = World(owned); n = world.info
            world.put(MAIN+0x3204, NATION)
            world.put(self.FRAME-4, self.DIALOG); world.put(self.DIALOG+0x448, self.LISTBOX)
            world.put(self.LISTBOX+0x2D8, self.ITEMS); world.put(self.ITEMS, self.ITEMS_VMT); world.put(self.ITEMS_VMT+0x3C, DATA+0xBF00)
            added, roles = [], []
            world.stubs[DATA+0xBF00] = lambda: added.append(world.text(world.reg("EDX"))) or 0
            world.stubs[n["add_role"]] = lambda: roles.append(world.reg("EAX") & 0xFF) or 0
            world.stubs[n["can_develop"]] = lambda: int(develops and (world.reg("EAX"), world.reg("EDX")) == (NATION, carrier.SCOUT))
            self.run_from(world, self.site(world, "request_list"), n["list_back"])
            self.assertEqual((roles, added), ([13], ["UAV"] if listed else []), owned)

    def test_uav_reads_as_a_floatplane_scout_for_the_checks_and_is_stored_as_role_16(self):
        world = World(); n = world.info
        world.stubs[n["role_from_name"]] = lambda: 99
        for text, role in (("UAV", carrier.SCOUT), ("Floatplane scout", 99), ("UA", 99)):
            world.put(STACK+0x8000-4, 0x6288E5)
            self.run_from(world, self.site(world, "request_role"), 0x6288E5, EAX=self.string(world, DATA+0xC000, text),
                          ESP=STACK+0x8000-4)
            self.assertEqual(world.reg("EAX"), role, text)
        for text, stored in (("UAV", carrier.UAV_ROLE), ("Floatplane scout", 3)):
            world.vm.mem_write(MAIN+carrier.REQUEST, b"\0")
            world.put(self.FRAME-4, self.string(world, DATA+0xC000, text))
            values = self.run_from(world, self.site(world, "request_store"), n["store_back"], EAX=MAIN, EBX=3)
            self.assertEqual(world.get(MAIN+carrier.REQUEST, 1), stored, text)
            self.assertEqual([world.reg(r) for r in ("EAX", "EBX", "ECX", "EDX")], [values[r] for r in ("EAX", "EBX", "ECX", "EDX")])

    def test_role_16_is_named_uav_and_the_others_keep_their_names(self):
        world = World(); names = []
        world.stubs[world.info["assign"]] = lambda: names.append(world.text(world.reg("EDX"))) or 0
        for role in (carrier.UAV_ROLE, 3, 10):
            world.call(0x970254, role, DATA+0xC100)
        self.assertEqual(names, ["UAV", "Floatplane scout", "Light jet fighter"])

    def test_a_uav_request_completes_as_a_flagged_floatplane_scout(self):
        flag = next(b["address"] for b in modern.build(CODE, modern.discover(BLOB, 0x301000))[0] if b["name"] == "UAV prototype")-0xF10+0xF02
        for requested, role_seen, flag_seen in ((carrier.UAV_ROLE, 3, 1), (5, 5, 0)):
            world = World(); n = world.info; seen = []
            world.stubs[n["complete"]] = lambda: seen.append((world.get(MAIN+carrier.REQUEST, 1), world.get(flag, 1), world.reg("EAX"))) or 0
            world.put(MAIN+carrier.REQUEST, requested, 1); world.put(flag, 0, 1)
            self.run_from(world, self.site(world, "request_done"), 0x7EBF8C, EAX=MAIN)   # the patched call returns here
            self.assertEqual(seen, [(role_seen, flag_seen, MAIN)], requested)
            self.assertEqual((world.get(flag, 1), world.reg("ESP")), (0, STACK+0x8000))

    def test_a_prototype_that_did_not_load_is_skipped_not_named(self):
        world = World(); n = world.info; asked = []
        world.stubs[n["name_taken"]] = lambda: asked.append((world.reg("EAX"), world.get(world.reg("ESP")+4))) or 0
        start = self.site(world, "prototype_nil")
        self.run_from(world, start, n["prototype_skip"], EBX=0)                # nil: no name check, not added
        self.assertEqual(asked, [])
        model = DATA+0xD000; world.put(model+4, DATA+0xD100)
        self.run_from(world, start, n["prototype_back"], EBX=model, EBP=STACK+0x9000)
        self.assertEqual(asked, [(DATA+0xD100, STACK+0x9000)])                # name check with the parent frame
        self.assertEqual(world.reg("ESP"), STACK+0x8000-4)                    # its frame argument left for POP ECX

    def test_uav_models_read_uav_in_the_aircraft_lists_and_a_uav_request_in_its_messages(self):
        world = World(); model = DATA+0xD000
        for role, mark, shown in ((3, sensors.UAV_MARK, carrier.UAV_ROLE), (3, 0, 3), (3, sensors.STEALTH_MARK, 3),
                                  (13, sensors.UAV_MARK, 13), (10, sensors.STEALTH_MARK, 10)):
            world.vm.mem_write(model, bytes(0x100)); world.put(model+0x81, role, 1); world.put(model+sensors.MARK, mark)
            for name, register in (("types_role", "ESI"), ("item_role", "EBX")):
                start = self.site(world, name)
                values = self.run_from(world, start, start+7, **{register: model})
                kept = ("EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP")
                self.assertEqual([world.reg("EAX")]+[world.reg(r) for r in kept], [shown]+[values[r] for r in kept],
                                 (name, role, mark))
        flag = next(b["address"] for b in modern.build(CODE, modern.discover(BLOB, 0x301000))[0] if b["name"] == "UAV prototype")-0xF10+0xF02
        world.put(MAIN+carrier.REQUEST, 3, 1)
        for requested, shown in ((1, carrier.UAV_ROLE), (0, 3)):
            world.put(flag, requested, 1)
            for name in ("ready_role", "none_role"):
                start = self.site(world, name)
                values = self.run_from(world, start, start+7, ESI=MAIN)
                self.assertEqual((world.reg("EAX"), world.reg("ESP")), (shown, values["ESP"]), (name, requested))


class DesignerTagTests(unittest.TestCase):
    def test_every_added_designer_control_has_its_own_tag(self):
        import modern_railgun as railgun
        tags = [v for module in (railgun, carrier) for k, v in vars(module).items() if k.startswith("MAGIC_")]
        self.assertEqual(len(tags), len(set(tags)), [hex(t) for t in tags])   # a shared tag finds the wrong box


class ElectronicWarfareTests(unittest.TestCase):
    UNITS, ITEMS, MODELS, FORMATION, LOG, LOG_VMT, LOGGED = (DATA+0xE000, DATA+0xE100, DATA+0xE200, DATA+0xE400,
                                                            DATA+0xE500, DATA+0xE600, DATA+0xE700)

    def execute(self, world, start, stop, **registers):
        values = dict(dict(EAX=0, EBX=0x2345, ECX=0x1234, EDX=0x3456, ESI=0x4567, EDI=0x5678, EBP=STACK+0xA000,
                           ESP=STACK+0x8000), **registers)
        for reg, value in values.items(): world.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
        world.vm.emu_start(start, stop, count=100000)
        return values

    def squadrons(self, world, *units):
        """The battle's air units: (carrier, mission, aircraft, aircraft role) each."""
        world.put(carrier.NATIVE["air_units"], self.UNITS); world.put(self.UNITS, self.UNITS+0x10)
        world.put(self.UNITS+0x18, len(units))
        for i, (ship, mission, count, role) in enumerate(units):
            unit, model = self.ITEMS+i*0x80, self.MODELS+i*0x100
            world.vm.mem_write(unit, bytes(0x80)); world.vm.mem_write(model, bytes(0x100))
            world.put(unit+0x4D, ship); world.put(unit+0x40, mission, 1); world.put(unit+0x18, count)
            world.put(unit+0x10, model); world.put(model+0x81, role, 1)
        world.stubs[carrier.NATIVE["list_get"]] = lambda: self.ITEMS+world.reg("EDX")*0x80
        world.stubs[carrier.NATIVE["special_min"]] = lambda: 6

    def test_jet_special_squadrons_jam_and_the_others_give_early_warning(self):
        other = CARRIER+0x100
        for units, aew, ew in ((((CARRIER, 7, 6, 2),), 1, 0),                       # a propeller squadron: AEW
                               (((CARRIER, 7, 6, 13),), 1, 0),                      # helicopters: AEW
                               (((CARRIER, 7, 6, 12),), 0, 1),                      # jets: EW
                               (((CARRIER, 7, 6, 12), (CARRIER, 7, 8, 2)), 1, 1),   # one of each: both
                               (((CARRIER, 7, 5, 2),), 0, 0),                       # under the native minimum
                               (((other, 7, 6, 2),), 0, 0), (((CARRIER, 3, 6, 12),), 0, 0)):   # not this carrier's special
            world = World(); world.vm.mem_write(CARRIER, bytes(0xA00)); self.squadrons(world, *units)
            for site, kind in carrier.SPECIAL:
                self.execute(world, site, site+5, EAX=CARRIER)
                self.assertEqual(world.reg("EAX") & 0xFF, aew if kind == carrier.AEW else ew, (hex(site), units))
                self.assertEqual([world.reg(r) for r in ("EBX", "ESI", "EDI", "EBP", "ESP")],
                                 [0x2345, 0x4567, 0x5678, STACK+0xA000, STACK+0x8000])

    def test_an_aew_squadron_no_longer_logs_cap_vectoring_every_intercept(self):
        world = World(); world.vm.mem_write(CARRIER, bytes(0xA00)); self.squadrons(world, (CARRIER, 7, 6, 2))
        self.execute(world, carrier.AEW_LOG, 0x962F5D, EAX=CARRIER)   # past the log call when the check says yes
        self.assertEqual(world.reg("EIP"), 0x962F5D)

    def test_the_nearest_enemy_air_formation_is_returned(self):
        # formations: (side, aircraft, distance); the native routine always returned none
        for formations, nearest in ((((5, 4, 9000), (5, 4, 3000), (6, 9, 100), (5, 1, 50)), 1),   # other side, too few
                                    (((6, 4, 100),), None), ((), None)):
            world = World(); items = [self.ITEMS+i*0x80 for i in range(len(formations))]
            world.put(0xA80108, self.UNITS); world.put(self.UNITS+8, len(formations))
            table = {}
            for item, (side, count, distance) in zip(items, formations):
                world.vm.mem_write(item, bytes(0x80)); world.put(item+0x38, side); table[item] = (count, distance)
            world.stubs.update({0x3B6D6C: lambda: items[world.reg("EDX")], 0x9666EC: lambda: table[world.reg("EAX")][0],
                                0x5733F4: lambda: table[world.reg("EDX")-0x2C][1]})
            world.put(STACK+0x8000-4, 0x300100); world.vm.mem_write(0x300100, b"\xc3")
            self.execute(world, 0x977788, 0x300100, EAX=5, EDX=2, ECX=DATA+0xF000, ESP=STACK+0x8000-4)
            self.assertEqual(world.reg("EAX"), items[nearest] if nearest is not None else 0, formations)
            self.assertEqual([world.reg(r) for r in ("EBX", "ESI", "EDI", "EBP")], [0x2345, 0x4567, 0x5678, STACK+0xA000])

    def test_sead_research_cuts_sam_effectiveness_against_the_formation(self):
        (arm, _, _), (harm, _, _), (pods, _, _) = tree.SEAD
        for owned, role, left, logged in ((set(), 12, 100, 0), ({arm}, 12, 75, 1), ({arm}, 2, 100, 0),
                                          ({arm, harm}, 11, 60, 1), ({arm, harm, pods}, 10, 48, 2),   # ARMs noted once
                                          ({arm, harm, pods}, 2, 80, 1), ({pods}, 13, 80, 1)):
            world = World(owned); texts = []
            world.vm.mem_write(SHIP, bytes(0xC00)); world.vm.mem_write(self.FORMATION, bytes(0x60))
            world.put(self.FORMATION+0x10, self.MODELS); world.vm.mem_write(self.MODELS, bytes(0x100))
            world.put(self.MODELS+0x81, role, 1); world.put(self.FORMATION+0x38, 3)
            world.put(carrier.NATIVE["battle_log"], self.LOG); world.put(self.LOG, self.LOG_VMT)
            world.put(self.LOG_VMT+0x40, self.LOGGED)
            world.stubs[self.LOGGED] = lambda: texts.append((world.text(world.reg("EDX")), world.reg("ECX"))) or 0
            world.put(STACK+0xA000-8, self.FORMATION)
            self.execute(world, 0x97D077, 0x97D07E, EBX=100, ESI=SHIP)
            self.assertEqual((world.reg("EBX"), len(texts), world.reg("ESI"), world.reg("EDI")), (left, logged, SHIP, 0x5678),
                             (owned, role))
            self.assertTrue(all(ship == SHIP for _, ship in texts))
            self.assertTrue(world.reg("EFLAGS") & 0x40)                               # the replayed radar test: not down
            self.execute(world, 0x97D077, 0x97D07E, EBX=100, ESI=SHIP)               # the next salvo at it
            self.assertEqual((world.reg("EBX"), len(texts)), (left, logged), (owned, role))   # cut again, not noted again


if __name__ == "__main__":
    unittest.main()

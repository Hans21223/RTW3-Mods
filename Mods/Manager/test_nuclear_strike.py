"""The battle's nuclear strike console in the emulator: availability, the target pick, LAUNCH (price, treaty, one a
battle, the blast), the controls FormShow makes and the map effect."""
from pathlib import Path
import math
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn.x86_const import *
from test_modern_combat import World, BLOB, CODE, NATION, DATA, STACK, FRAME
import modern_research as modern
import modern_tree as tree
import nuclear_strike as ns
import modern_extension as extension
import nuclear_subs as subs
import shell_doctrine as sd

DETAILS = modern.discover(BLOB, 0x301000)
INFO, SUBS = DETAILS["nuclear_strike"], DETAILS["subs"]
EXT = CODE+len(DETAILS["getters"])*0x1000+0x2000         # modern_extension's ext
FORM, COMPONENTS, ITEMS = DATA+0xC000, DATA+0xC800, DATA+0xC900
GLOBE, GLOBE_VMT, CANVAS, PEN, BRUSH = DATA+0xD000, DATA+0xD400, DATA+0xD800, DATA+0xD900, DATA+0xDA00
TOOLBAR, AUTORUN, LOG, LOG_VMT, YEAR = DATA+0xDC00, DATA+0xDD00, DATA+0xDE00, DATA+0xDF00, DATA+0xDF80
CONTROLS, SHIPS, AIR, BOATS = DATA+0xE000, DATA+0x10000, DATA+0x16000, DATA+0x16800
TEXT, LISTS, EXTDATA, STUBS = DATA+0x17000, DATA+0x18000, DATA+0x18800, DATA+0x1F000
BITMAPS, BITMAP_VMT = DATA+0x1A000, DATA+0x1B000
RETURN, PLAYER_SIDE, ENEMY_SIDE = 0x2FFFF0, 1, 2
TARGET = (100000, 200000, 0)                   # the mark: a place on the tests' plane of yards
SLOTS = dict(create=("create", "speed", "panel", "label", "image", "shape", "timer"),
             set_parent=("parent", "speed", "panel", "label", "image", "shape"),
             set_enabled=("enabled", "speed"), set_autosize=("autosize", "label"))
CONSOLE = ("backdrop", "gauge_target", "gauge_arm", "ssbns", "warhead", "target", "status", "info", "key1", "key2", "launch",
           "tgt", "cancel", "warhead_hit")
AFLOAT = 500                                    # every test ship's buoyancy before the strike
TOOLBAR_WIDTH = 1600


class StrikeTests(unittest.TestCase):
    def setUp(self):
        self.world = w = World({tree.SSBN})
        blocks = modern.build(CODE, DETAILS)[0]
        self.at = {b["name"][16:]: b["address"] for b in blocks if b["name"].startswith("Nuclear strike: ")}
        self.d = {k: self.at["state"]+v for k, v in ns.DATA.items()}
        self.used = w.doctrine+sd.SLOTS*8+4
        self.armageddon = self.used+4
        self.calls, self.messages, self.made, self.hits, self.losses, self.log = [], [], [], [], [], []
        for name in ("set_visible", "set_text", "set_show_hint", "assign", "font_color", "font_style", "brush_color",
                     "brush_style", "pen_color", "pen_width", "pen_style", "shape_type", "timer_enabled",
                     "timer_interval", "set_cursor", "image_picture", "image_stretch", "label_transparent",
                     "font_size", "font_name", "label_wrap"):
            self.stub(INFO[name], name=name)
        # The console's pictures: files that exist, TBitmaps whose LoadFromFile (a virtual slot) is recorded.
        self.files, self.bitmaps, self.loaded = True, [], []
        self.stub(INFO["file_exists"], lambda: int(self.files))
        def bitmap():
            made = BITMAPS+0x40*len(self.bitmaps); w.put(made, BITMAP_VMT); self.bitmaps.append(made); return made
        self.stub(INFO["bitmap_create"], bitmap)
        w.put(BITMAP_VMT+ns.LOAD_FROM_FILE, STUBS+0xC00)
        self.stub(STUBS+0xC00, lambda: self.loaded.append((w.reg("EAX"), self.text(w.reg("EDX")))))
        def number():   # IntToStr(EAX, EDX the result's variable)
            w.vm.mem_write(TEXT+0x400, subs.literal(str(w.reg("EAX")))); w.put(w.reg("EDX"), TEXT+0x40C)
        self.stub(INFO["int_to_str"], number)
        def joined():   # UStrCat3(EAX the result's variable, EDX, ECX)
            w.vm.mem_write(TEXT+0x500, subs.literal(self.text(w.reg("EDX"))+self.text(w.reg("ECX")))); w.put(w.reg("EAX"), TEXT+0x50C)
        self.stub(INFO["cat3"], joined)
        for field in ("left", "top", "width", "height"):                                            # the VCL stores them
            self.stub(INFO["set_"+field], lambda field=field: w.put(w.reg("EAX")+ns.CONTROL[field], w.reg("EDX")), name="set_"+field)
        for name, value in (("pen_get_color", 0x111), ("pen_get_width", 2), ("pen_get_style", 0),
                            ("brush_get_color", 0x222), ("brush_get_style", 0)):
            self.stub(INFO[name], lambda value=value: value)
        self.stub(INFO["message"], lambda: self.messages.append(self.text(w.reg("EAX"))))
        def create():   # TComponent.Create(form): the form's Components list gains it, as in the VCL
            control = CONTROLS+0x200*len(self.made); w.vm.mem_write(control, bytes(0x200)); w.put(control, w.reg("EAX"))
            count = w.get(COMPONENTS+8); w.put(ITEMS+4*count, control); w.put(COMPONENTS+8, count+1)
            self.made.append(control); return control
        for slot, (name, *kinds) in SLOTS.items():
            for kind in kinds: w.put(INFO[kind]+ns.CONTROL[slot], STUBS+ns.CONTROL[slot])
            self.stub(STUBS+ns.CONTROL[slot], dict(create=create).get(slot), name=name)
        # The form: Panel1, sbAutoRunBattle (28 px: 96 DPI), the globe with its renderer's pen and brush.
        w.put(FORM+ns.FORM["toolbar"], TOOLBAR); w.put(FORM+ns.FORM["last_button"], AUTORUN); w.put(FORM+ns.FORM["globe"], GLOBE)
        for field, value in (("top", 0), ("height", 39), ("width", TOOLBAR_WIDTH)): w.put(TOOLBAR+ns.CONTROL[field], value)
        for field, value in (("left", 1218), ("top", 5), ("width", 28), ("height", 28)): w.put(AUTORUN+ns.CONTROL[field], value)
        w.put(FORM+0x10, COMPONENTS); w.put(COMPONENTS+4, ITEMS); w.put(COMPONENTS+8, 0)
        w.put(GLOBE, GLOBE_VMT); w.put(GLOBE+ns.GLOBE["renderer"], CANVAS)
        w.put(CANVAS+ns.CANVAS["pen"], PEN); w.put(CANVAS+ns.CANVAS["brush"], BRUSH)
        for name in ("redraw", "circle", "polygon"): w.put(GLOBE_VMT+ns.GLOBE[name], STUBS+0x400+ns.GLOBE[name])
        self.stub(STUBS+0x400+ns.GLOBE["redraw"], name="redraw")
        self.stub(STUBS+0x400+ns.GLOBE["circle"], name="circle", args=1)
        self.stub(STUBS+0x400+ns.GLOBE["polygon"], name="polygon")
        w.put(INFO["battle_log"], LOG); w.put(LOG, LOG_VMT); w.put(LOG_VMT+0x40, STUBS+0x800)
        self.stub(STUBS+0x800, lambda: self.log.append((w.reg("ECX"), self.text(w.reg("EDX")))))
        # Globe units: the tests use yards. to_unit loads EAX, units returns its Extended argument.
        w.vm.mem_write(INFO["to_unit"], b"\x50\xdb\x04\x24\x58\xc3")
        w.vm.mem_write(INFO["units"], b"\xdb\x6c\x24\x04\x50\xdb\x1c\x24\x58\xc2\x0c\x00")
        self.boats([("George Washington SSBN", 0, 0)])

    def stub(self, address, handler=None, name=None, args=0):
        w = self.world
        def run():
            if name: self.calls.append((name, w.reg("EAX"), w.reg("EDX"), w.reg("ECX")))
            result = handler() if handler else 0
            if args:
                sp = w.reg("ESP"); w.put(sp+4*args, w.get(sp)); w.vm.reg_write(UC_X86_REG_ESP, sp+4*args)
            return result or 0
        w.stubs[address] = run

    def called(self, name, mask=0xFFFFFFFF): return [(c[1], c[2] & mask) for c in self.calls if c[0] == name]

    def text(self, pointer):
        w = self.world; return bytes(w.vm.mem_read(pointer, 2*w.get(pointer-4))).decode("utf-16-le")

    def call(self, address, **registers):
        w = self.world
        w.put(STACK+0x8000-4, RETURN)
        for name, value in dict(dict(EBX=0x2345, ESI=0x4567, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000-4), **registers).items():
            w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        w.vm.emu_start(address, RETURN, count=200000)
        self.assertEqual([w.reg(r) for r in ("EBX", "ESI", "EDI", "ESP")],
                         [registers.get("EBX", 0x2345), registers.get("ESI", 0x4567), registers.get("EDI", 0x5678), STACK+0x8000])
        return w.reg("EAX")

    def run_site(self, start, stop, **registers):
        w = self.world
        for name, value in dict(dict(EBP=FRAME, ESP=STACK+0x8000), **registers).items():
            w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        w.vm.emu_start(start, stop, count=200000)
        self.assertEqual((w.reg("EIP"), w.reg("ESP")), (stop, STACK+0x8000))

    def boats(self, boats):
        """The player's submarines: (name, sunk, months to complete), in the native layout: Sunk +1Ah, and InPlay
        +20h set, as it is for every boat of a campaign."""
        w = self.world
        records = []
        for i, (name, sunk, months) in enumerate(boats):
            record = BOATS+0x80*i; w.vm.mem_write(record, bytes(0x80)); w.vm.mem_write(TEXT+0x800+0x80*i, subs.literal(name))
            w.put(record+4, TEXT+0x80C+0x80*i); w.put(record+0x1A, sunk, 1); w.put(record+0x15, months)
            w.put(record+0x20, 1, 1)
            records.append(record)
        w.put(NATION+ns.NATION["subs"], BOATS+0x700); w.put(BOATS+0x708, len(records))
        self.stub(INFO["get_sub"], lambda: records[w.reg("EDX")] if w.reg("EAX") == NATION else 0)

    def controls(self):
        """Every console control on the form, found by class and tag (the timers are made when needed)."""
        w = self.world
        made = {}
        for i, (kind, vmt) in enumerate(ns.KINDS.items()):
            if vmt == "timer": continue
            control = DATA+0x1C000+0x200*i; w.vm.mem_write(control, bytes(0x200))
            w.put(control, INFO[vmt]); w.put(control+ns.CONTROL["tag"], ns.TAGS[kind]); made[kind] = control
            if vmt == "shape": w.put(control+ns.CONTROL["shape_brush"], control+0x1F0)   # its brush
        for i, control in enumerate(made.values()): w.put(ITEMS+4*i, control)
        w.put(COMPONENTS+8, len(made))
        return made

    def texts(self, control): return [self.text(t) for a, t in self.called("set_text") if a == control]
    def arm(self, value): self.world.put(self.d["armed"], value, 1)

    def battle(self, ships, formations=()):
        """ships: (side, yards east of the target or (east, north), kind, out of action[, the other side's sighting]);
        formations: (aircraft, destroyed, yards). Places are yards on a plane; ll_distance measures between them."""
        w, n = self.world, INFO
        objects, units = [], []
        def place(at, yards):
            east, north = yards if isinstance(yards, tuple) else (yards, 0)
            w.put(at, TARGET[0]+east); w.put(at+4, TARGET[1]+north); w.put(at+8, 0)
        for i, (side, yards, kind, out, *seen) in enumerate(ships):
            ship = SHIPS+0x1000*i; w.vm.mem_write(ship, bytes(0xE20))
            w.put(ship+ns.SHIP["side"], side); w.put(ship+ns.SHIP["nation"], 3 if side == PLAYER_SIDE else 5)
            w.put(ship+ns.SHIP["kind"], kind, 1); w.put(ship+ns.SHIP["out"], out, 1); w.put(ship+ns.SINK["buoyancy"], AFLOAT)
            if seen: w.put(ship+ns.SIGHTED[seen[0][0]], seen[0][1])
            place(ship+ns.SHIP["position"], yards); objects.append(ship)
        for i, (aircraft, destroyed, yards) in enumerate(formations):
            unit = AIR+0x100*i; w.vm.mem_write(unit, bytes(0x100))
            w.put(unit+ns.AIR["count"], aircraft); w.put(unit+ns.AIR["destroyed"], destroyed)
            place(unit+ns.AIR["position"], yards); units.append(unit)
        for i in range(len(objects)): w.vm.mem_write(EXTDATA+16*i, bytes(16))   # data, guard, battle dwords
        w.put(n["ships"], LISTS); w.put(LISTS, LISTS+0x10); w.put(LISTS+0x18, len(objects))
        w.put(n["air"], LISTS+0x40); w.put(LISTS+0x40, LISTS+0x50); w.put(LISTS+0x58, len(units))
        w.put(n["side"], LISTS+0x80); w.put(LISTS+0x80, PLAYER_SIDE)
        self.stub(n["list_get"], lambda: (objects if w.reg("EAX") == LISTS+0x10 else units)[w.reg("EDX")])
        def distance():   # between the two places (EAX, EDX), in yards
            a, b = (struct.unpack("<ii", w.vm.mem_read(w.reg(r), 8)) for r in ("EAX", "EDX"))
            return round(math.hypot(a[0]-b[0], a[1]-b[1]))
        self.stub(n["ll_distance"], distance)
        self.stub(EXT, lambda: EXTDATA+16*objects.index(w.reg("EAX")) if w.reg("EAX") in objects else 0)
        self.stub(SUBS["random"], lambda: 0x40 if w.reg("EAX") == 360 else 0)                   # the hit's bearing
        def hit():
            args = struct.unpack("<8I", w.vm.mem_read(w.reg("ESP")+4, 32))
            self.assertEqual(args[2], 0x40)                                                    # the bearing
            self.hits.append((w.reg("EAX"), args[4], args[7], self.text(w.reg("ECX"))))
        self.stub(SUBS["handle_hit"], hit, args=8)
        def loss(): self.losses.append((w.reg("EAX"), w.reg("EDX"), w.reg("ECX") & 0xFF, w.get(w.reg("ESP")+4)))
        self.stub(n["inflict"], loss, args=1)
        return objects, units

    def mark(self, warhead=0):
        w = self.world
        for i, value in enumerate(TARGET): w.put(self.d["target"]+4*i, value)
        w.put(self.d["has_target"], 1, 1); self.choose(warhead)

    def choose(self, warhead):   # as setkind leaves it: the warhead and its kill and hit radii
        _, _, kill, ring, _, _ = ns.WARHEADS[warhead]
        self.world.put(self.d["kind"], warhead, 1); self.world.put(self.d["kill"], kill); self.world.put(self.d["ring"], ring)

    def sinking(self, ships): return [(self.world.get(s+ns.SINK["buoyancy"]), self.world.get(s+ns.SINK["timer"])) for s in ships]

    def flags(self): return [self.world.get(self.d["pick"]) >> 8*i & 0xFF for i in range(3)]   # pick, target, active

    def test_the_submarine_fields_are_the_ones_the_game_saves(self):
        # TSubmarine.SaveMe: MOVZX EAX,[EBX+1Ah] before the "Sunk" key, MOV EAX,[EBX+15h] before "RemainingBuildTime"
        self.assertEqual(BLOB[0x82EDE9-0x301000:0x82EDED-0x301000], b"\x0f\xb6\x43"+bytes([ns.SUB["sunk"]]))
        self.assertEqual(BLOB[0x82ED7E-0x301000:0x82ED81-0x301000], b"\x8b\x43"+bytes([ns.SUB["months"]]))

    def test_the_strike_needs_the_ssbn_research_and_an_ssbn_in_service(self):
        w = self.world
        boats = [("Gato", 0, 0), ("Nautilus SSN", 0, 0), ("Ohio SSBN", 0, 3), ("Lafayette SSBN", 1, 0)]
        two = [("George Washington SSBN", 0, 0), ("Ethan Allen SSBN", 0, 0)]
        for fleet, owned, expected, count in ((boats+two, {tree.SSBN}, 1, 2),
                                              (boats, {tree.SSBN}, 0, 0),                        # building, gone
                                              (boats+two, set(), 0, 0)):
            self.boats(fleet); w.owned = owned
            self.assertEqual(self.call(self.at["available"], EAX=NATION) & 0xFF, expected, (fleet, owned))
            self.assertEqual(w.get(self.d["count"]), count)                                       # SSBNs ON STATION

    def test_nuke_starts_the_target_pick_once_a_battle(self):
        w, d = self.world, self.d
        ships, _ = self.battle([(PLAYER_SIDE, 9000, 0, 0)])
        c = self.controls()
        self.call(self.at["nuke"], EAX=FORM, EDX=c["nuke"])
        self.assertEqual((self.flags(), self.messages), ([1, 0, 0], []))
        self.assertEqual(self.called("set_cursor", 0xFFFF), [(GLOBE, ns.CROSS)])
        self.assertEqual([v for v in self.called("set_visible", 0xFF) if v[0] == c["console"]], [(c["console"], 1)])
        self.assertEqual(self.texts(c["info"]), [ns.TEXT["picking"]])
        self.assertEqual((self.texts(c["ssbns"]), self.texts(c["target"]), self.texts(c["status"])), (["1"], ["NONE"], ["SAFE"]))
        self.assertEqual(len(self.called("redraw")), 1)
        w.put(d["pick"], 0, 1); w.put(EXTDATA+extension.BATTLE_FLAGS, ns.STRIKE_BIT)            # struck this battle
        self.call(self.at["nuke"], EAX=FORM, EDX=c["nuke"])
        self.assertEqual((self.flags(), self.messages), ([0, 0, 0], [ns.TEXT["spent"]]))
        w.put(self.armageddon, 1)
        self.call(self.at["nuke"], EAX=FORM, EDX=c["nuke"])
        self.assertEqual((self.flags(), len(self.messages)), ([1, 0, 0], 1))
        w.owned = set(); w.put(d["pick"], 0, 1)
        self.call(self.at["nuke"], EAX=FORM, EDX=c["nuke"])
        self.assertEqual((self.flags(), self.messages[-1]), ([0, 0, 0], ns.TEXT["unavailable"]))
        w.owned = {tree.SSBN}; w.put(DATA+0x200, 0)                                               # no campaign loaded
        self.call(self.at["nuke"], EAX=FORM, EDX=c["nuke"])
        self.assertEqual((self.flags(), self.messages[-2:]), ([0, 0, 0], [ns.TEXT["unavailable"]]*2))

    def test_a_map_click_marks_the_target_only_while_picking(self):
        w, d, n = self.world, self.d, INFO
        c = self.controls()
        clicks = []
        def to_ll():
            clicks.append((w.reg("EAX"), w.reg("EDX"), w.reg("ECX")))
            out = w.get(w.reg("ESP")+4)
            for i, value in enumerate(TARGET): w.put(out+4*i, value)
            return 1
        self.stub(n["device_to_ll"], to_ll, args=1)
        w.put(GLOBE+ns.GLOBE["projection"], 0x7777); w.put(d["pick"], 1, 1)
        self.run_site(n["pick"], n["pick_done"], EBX=FORM, ESI=300, EDI=400)
        self.assertEqual(clicks, [(0x7777, 300, 400)])
        self.assertEqual(([w.get(d["target"]+4*i) for i in range(3)], self.flags()), (list(TARGET), [0, 1, 0]))
        self.assertEqual([w.reg(r) for r in ("EBX", "ESI", "EDI")], [FORM, 300, 400])
        self.assertEqual(self.called("set_cursor", 0xFFFF), [(GLOBE, 0)])
        self.assertEqual((self.texts(c["info"]), self.texts(c["target"])), ([ns.TEXT["ready"]], ["MARKED"]))
        self.assertEqual([v for v in self.called("set_visible", 0xFF) if v[0] == c["gauge_target"]], [(c["gauge_target"], 1)])
        w.put(FORM+0x7CC, 0, 1)                                                                    # native: nothing to pick
        self.run_site(n["pick"], n["pick_done"], EBX=FORM, ESI=300, EDI=400)
        w.put(FORM+0x7CC, 1, 1)                                                                    # the strike dialog's pick
        self.run_site(n["pick"], n["pick_native"], EBX=FORM, ESI=300, EDI=400)
        self.assertEqual(len(clicks), 1)

    def test_launch_pays_marks_the_battle_and_blasts_ships_and_aircraft_near_the_target(self):
        w, d = self.world, self.d
        ships, units = self.battle([(PLAYER_SIDE, 1500, 0, 0), (PLAYER_SIDE, 4000, 0, 0), (ENEMY_SIDE, 1999, 0, 0),
                                    (ENEMY_SIDE, 5001, 0, 0), (ENEMY_SIDE, 100, ns.LAND, 0), (ENEMY_SIDE, 100, 0, 1)],
                                   [(12, 2, 4999), (8, 8, 100), (6, 0, 6000)])
        c = self.controls()
        self.mark(); self.arm(1)
        funds, flags = w.get(NATION+sd.FUNDS), w.get(w.doctrine+4)
        self.call(self.at["launch"], EAX=FORM, EDX=c["launch"])
        self.assertEqual(self.messages, [])
        self.assertEqual((w.get(NATION+sd.FUNDS), w.get(self.used)), (funds-ns.PRICE, 1))
        self.assertEqual(w.get(w.doctrine+4), flags | sd.MISSILE << sd.CROSSED_SHIFT)          # no first use: crossed
        self.assertEqual(self.hits, [(s, 3, ns.NUCLEAR_CALIBRE, ns.TEXT["strike"]) for s in ships[:3]])
        self.assertEqual(self.sinking(ships[:4]), [(0, 1), (AFLOAT, 0), (0, 1), (AFLOAT, 0)])     # inside 2,000 yards they sink
        self.assertEqual(self.losses, [(units[0], 10, ns.DESTROYED, ns.AA_LOSS)])
        self.assertEqual([w.get(EXTDATA+16*i+extension.BATTLE_FLAGS) for i in range(len(ships))], [ns.STRIKE_BIT]*2+[0]*4)
        self.assertEqual(self.log, [(ships[0], ns.TEXT["log0"])])
        self.assertEqual(self.flags(), [0, 0, 1])
        self.assertEqual([w.get(d["step"]), w.get(d["blasts"]) & 0xFF]+[w.get(d["centres"]+4*i) for i in range(3)], [1, 1, *TARGET])
        timer, key_timer = self.made[-2:]                                                          # the effect; the key's
        self.assertEqual([(w.get(t), w.get(t+ns.CONTROL["tag"]), w.get(t+0x48), w.get(t+0x4C)) for t in (timer, key_timer)],
                         [(INFO["timer"], ns.TAGS["timer"], self.at["tick"], FORM),
                          (INFO["timer"], ns.TAGS["key_timer"], self.at["key_tick"], FORM)])
        self.assertEqual((self.called("timer_interval"), self.called("timer_enabled", 0xFF)),
                         ([(timer, ns.TIMER_MS), (key_timer, ns.KEY_MS)], [(timer, 1), (key_timer, 1)]))
        self.assertEqual((w.get(d["key_target"]) & 0xFFFF, w.get(d["glass_target"]) & 0xFF, self.called("enabled", 0xFF)),
                         (0, 0, [(c["nuke"], 0)]))                                      # keys to SAFE, glass shut
        self.assertEqual([v for v in self.called("set_visible", 0xFF) if v[0] == c["console"]], [(c["console"], 0)])
        self.mark()                                                                                # one a battle
        self.call(self.at["launch"], EAX=FORM, EDX=c["launch"])
        self.assertEqual((self.messages, w.get(NATION+sd.FUNDS), len(self.hits)), ([ns.TEXT["spent"]], funds-ns.PRICE, 3))
        w.put(self.armageddon, 1)                                                                  # Nuclear Armageddon
        self.call(self.at["launch"], EAX=FORM, EDX=c["launch"])
        self.assertEqual((w.get(NATION+sd.FUNDS), len(self.hits), self.called("enabled", 0xFF)[1:]), (funds-2*ns.PRICE, 6, []))

    def test_an_h_bomb_sinks_everything_within_6000_yards_and_costs_more(self):
        w = self.world
        ships, units = self.battle([(ENEMY_SIDE, 5900, 0, 0), (ENEMY_SIDE, 6100, 0, 0), (ENEMY_SIDE, 14000, 0, 0),
                                    (ENEMY_SIDE, 16000, 0, 0), (PLAYER_SIDE, 30000, 0, 0)], [(10, 0, 14000)])
        c = self.controls()
        self.mark(warhead=1); self.arm(1); funds = w.get(NATION+sd.FUNDS)
        self.call(self.at["launch"], EAX=FORM, EDX=c["launch"])
        self.assertEqual(([h[0] for h in self.hits], self.sinking(ships[:3])), (ships[:3], [(0, 1), (AFLOAT, 0), (AFLOAT, 0)]))
        self.assertEqual((w.get(NATION+sd.FUNDS), [u[0] for u in self.losses]), (funds-ns.WARHEADS[1][1], [units[0]]))
        self.assertEqual(self.log, [(ships[4], ns.TEXT["log1"])])

    def test_a_mirv_sends_its_warheads_to_enemy_ships_in_contact_near_the_mark(self):
        w, d = self.world, self.d
        radar, eye = ("radar", 2), ("visual", 2)
        ships, _ = self.battle([(PLAYER_SIDE, (0, 60000), 0, 0),
                                (ENEMY_SIDE, 10000, 0, 0, eye),              # a warhead of its own
                                (ENEMY_SIDE, 10500, 0, 0, radar),            # inside that warhead's kill radius
                                (ENEMY_SIDE, (0, 30000), 0, 0),              # no contact
                                (ENEMY_SIDE, (0, -39000), 0, 0, radar),      # a warhead of its own
                                (ENEMY_SIDE, 45000, 0, 0, eye),              # beyond MIRV_YARDS
                                (PLAYER_SIDE, (20000, 20000), 0, 0, eye)])   # a friend
        c = self.controls()
        self.mark(warhead=2); self.arm(1)
        self.call(self.at["launch"], EAX=FORM, EDX=c["launch"])
        centres = [struct.unpack("<3i", w.vm.mem_read(d["centres"]+12*i, 12)) for i in range(w.get(d["blasts"]) & 0xFF)]
        self.assertEqual(centres, [TARGET, (TARGET[0]+10000, TARGET[1], 0), (TARGET[0], TARGET[1]-39000, 0)])
        self.assertEqual(([h[0] for h in self.hits], self.sinking([ships[1], ships[2], ships[4]])),
                         ([ships[1], ships[2], ships[4]], [(0, 1)]*3))                  # each inside a warhead's reach
        self.assertEqual((w.get(NATION+sd.FUNDS) < 10**6, self.log[-1][1]), (True, ns.TEXT["log2"]))

    def test_warhead_cycles_through_what_the_year_allows(self):
        w, d = self.world, self.d
        c = self.controls()
        w.put(DETAILS["doctrine"]["year"], YEAR)
        def click(year):
            w.put(YEAR, year); del self.calls[:]
            self.call(self.at["warhead"], EAX=FORM, EDX=c["warhead_hit"])
            return w.get(d["kind"]) & 0xFF, w.get(d["kill"]), w.get(d["ring"])
        self.assertEqual(click(1965), (1, 6000, 15000))                                             # H-BOMB
        self.assertEqual((self.texts(c["info"]), self.texts(c["warhead"]), len(self.called("redraw"))),
                         ([ns.TEXT["about1"]], [ns.TEXT["name1"]], 1))
        self.assertEqual(click(1965), (0, ns.FULL_YARDS, ns.RING_YARDS))                           # no MIRV before 1970
        self.assertEqual([click(1975)[0] for _ in range(3)], [1, 2, 0])

    def test_a_strike_over_empty_sea_says_so_in_the_log(self):
        ships, _ = self.battle([(PLAYER_SIDE, 9000, 0, 0), (ENEMY_SIDE, 6000, 0, 0)], [(12, 0, 7000)])
        c = self.controls()
        self.mark(); self.arm(1)
        self.call(self.at["launch"], EAX=FORM, EDX=c["launch"])
        self.assertEqual((self.hits, self.losses, self.log), ([], [], [(ships[0], ns.TEXT["empty"])]))

    def test_launch_refuses_without_target_key_or_money_and_under_a_ban_treaty(self):
        w = self.world
        ships, _ = self.battle([(PLAYER_SIDE, 9000, 0, 0), (ENEMY_SIDE, 500, 0, 0)])
        c = self.controls()
        w.put(DETAILS["doctrine"]["year"], YEAR); w.put(w.doctrine+4, 3 | (1965-1900) << 8)       # banned to 1965
        launch = lambda: self.call(self.at["launch"], EAX=FORM, EDX=c["launch"])
        self.arm(1); launch()
        self.mark(); self.arm(0); launch()
        self.arm(1); w.put(YEAR, 1965); launch()
        w.put(YEAR, 1966); w.put(NATION+sd.FUNDS, ns.PRICE-1); launch()
        self.assertEqual(self.messages, [ns.TEXT[k] for k in ("no_target", "unarmed", "treaty", "funds")])
        self.assertEqual((self.hits, w.get(self.used), w.get(NATION+sd.FUNDS)), ([], 0, ns.PRICE-1))
        w.put(NATION+sd.FUNDS, ns.PRICE); launch()
        self.assertEqual((len(self.messages), [h[0] for h in self.hits], w.get(NATION+sd.FUNDS)), (4, [ships[1]], 0))

    def test_form_show_makes_the_button_and_the_console_over_its_pictures_once(self):
        w, at, d = self.world, self.at, self.d
        w.put(FORM+0x4A8, 0x4A84A8); w.put(d["pick"], 0x010101)                                   # a battle before
        for name in ("armed", "glass_frame", "glass_target"): w.put(d[name], 1, 1)
        w.put(d["key_frame"], 0x07070707)
        self.run_site(INFO["form_show"], INFO["form_show"]+6, EBX=FORM, ESI=0x4567, EDI=0x5678)
        self.assertEqual([w.reg(r) for r in ("EAX", "EBX", "ESI", "EDI")], [0x4A84A8, FORM, 0x4567, 0x5678])
        kinds = ("nuke", "console")+CONSOLE+("emcon", "sonar")
        made = dict(zip(kinds, self.made))
        self.assertEqual([w.get(m) for m in self.made], [INFO[ns.KINDS[k]] for k in kinds])
        self.assertEqual([w.get(made[k]+ns.CONTROL["tag"]) for k in kinds], [ns.TAGS[k] for k in kinds])
        self.assertEqual(self.called("parent"), [(made["nuke"], TOOLBAR), (made["console"], FORM)]+[(made[k], made["console"]) for k in CONSOLE]
                         +[(made["emcon"], TOOLBAR), (made["sonar"], TOOLBAR)])
        def first(name):   # each control's value from its first call of that setter: its place when made
            seen = {}
            for control, value in self.called(name): seen.setdefault(control, value)
            return seen
        places = [first(name) for name in ("set_left", "set_top", "set_width", "set_height")]
        bounds = {k: [setter[made[k]] for setter in places] for k in kinds}
        nuke_left = 1218+28+ns.NUKE_GAP
        self.assertEqual(bounds["nuke"], [nuke_left, 5, 56, 28])
        self.assertEqual(bounds["emcon"], [nuke_left+56+ns.NUKE_GAP, 5, 84, 28])                    # right of NUKE
        self.assertEqual(bounds["sonar"], [nuke_left+56+84+2*ns.NUKE_GAP, 5, 84, 28])               # right of EMCON
        self.assertEqual(bounds["console"], [nuke_left+28-ns.CONSOLE[0]//2, 39+ns.GAP, *ns.CONSOLE])   # centred under NUKE
        self.assertEqual({k: bounds[k] for k in ns.LAYOUT}, {k: list(v) for k, v in ns.LAYOUT.items()})
        x, y, _, h = ns.LAYOUT["gauge_arm"]                                                        # refresh: SAFE, no fill
        self.assertEqual(([v for a, v in self.called("set_height") if a == made["gauge_arm"]][-1],
                          [v for a, v in self.called("set_top") if a == made["gauge_arm"]][-1]), (0, y+h))
        self.assertEqual(self.loaded, [(self.bitmaps[i], ns.picture_path(name)) for i, name in enumerate(ns.PICTURES)])
        self.assertEqual(self.called("image_picture"), [(made["backdrop"], self.bitmaps[0]), (made["key1"], self.bitmaps[1]),
                                                        (made["key2"], self.bitmaps[1]), (made["launch"], self.bitmaps[ns.LAUNCH_PICTURE])])
        self.assertEqual(self.called("image_stretch", 0xFF), [(made[k], 1) for k in ("backdrop", "key1", "key2", "launch")])
        styled = ("ssbns", "warhead", "target", "status", "info")
        # the message line keeps its box and wraps in it: AutoSize off, WordWrap on, both before its font is set
        self.assertEqual((self.called("autosize", 0xFF), self.called("label_wrap", 0xFF)), ([(made["info"], 0)], [(made["info"], 1)]))
        order = [c[0] for c in self.calls if c[1] == made["info"]]                                # look() ends transparent
        self.assertLess(order.index("label_wrap"), order.index("label_transparent"))
        self.assertLess(order.index("autosize"), order.index("label_transparent"))
        self.assertEqual([a for a, _ in self.called("label_transparent")], [made[k] for k in styled])
        self.assertEqual([e for _, e in self.called("font_size")], [ns.LABEL_PT]*4+[ns.INFO_PT])
        self.assertEqual({self.text(e) for _, e in self.called("font_name")}, {ns.FONT})
        clicks = dict(nuke="nuke", key1="key1", key2="key2", launch="glass", tgt="nuke", cancel="cancel", warhead_hit="warhead",
                      emcon="emcon", sonar="sonar")
        self.assertEqual({k: (w.get(made[k]+ns.CONTROL["on_click"]), w.get(made[k]+ns.CONTROL["on_click"]+4)) for k in clicks},
                         {k: (at[h], FORM) for k, h in clicks.items()})
        self.assertEqual(self.called("set_cursor", 0xFFFF),
                         [(made[k], ns.HAND) for k in ("key1", "key2", "launch", "tgt", "cancel", "warhead_hit")])
        self.assertEqual((self.called("pen_style", 0xFF)[-3:], self.called("brush_style", 0xFF)[-3:]),   # the clear click areas
                         ([(0, 5)]*3, [(0, 1)]*3))
        self.assertEqual([(a, self.text(t)) for a, t in self.called("set_text")],
                         [(made["nuke"], "NUKE"), (made["info"], ns.TEXT["picking"]), (made["emcon"], "RADAR ON"),
                          (made["ssbns"], "1"), (made["target"], "NONE"), (made["status"], "SAFE"),
                          (made["warhead"], ns.TEXT["name0"]), (made["sonar"], "PASSIVE")])
        self.assertEqual((self.called("enabled", 0xFF), [v for v in self.called("set_visible", 0xFF) if v[0] == made["console"]]),
                         ([(made["nuke"], 1)], [(made["console"], 0)]))
        self.assertEqual([v for v in self.called("set_visible", 0xFF) if v[0] == made["emcon"]], [(made["emcon"], 0)])  # no radar
        self.assertEqual([v for v in self.called("set_visible", 0xFF) if v[0] == made["sonar"]], [(made["sonar"], 0)])  # no hydrophones
        self.assertEqual([w.get(d[k]) & 0xFF for k in ("pick", "has_target", "active", "armed", "glass_frame", "glass_target",
                                                        "kind")], [0]*7)
        self.assertEqual((w.get(d["kill"]), w.get(d["ring"])), ns.WARHEADS[0][2:4])                 # each battle: A-BOMB
        self.assertEqual(w.get(d["key_frame"]), 0)                                                 # both keys' frames, targets
        for i, control in enumerate(self.made): w.put(ITEMS+4*i, control)                       # the next battle finds them
        w.put(COMPONENTS+8, len(self.made)); w.owned = set(); del self.calls[:]
        self.run_site(INFO["form_show"], INFO["form_show"]+6, EBX=FORM)
        self.assertEqual((len(self.made), len(self.loaded), self.called("enabled", 0xFF)), (len(kinds), len(ns.PICTURES), [(made["nuke"], 0)]))
        self.assertEqual([v for v in self.called("set_visible", 0xFF) if v[0] == made["console"]], [(made["console"], 0)])

    def test_the_console_stays_inside_the_window(self):
        w = self.world
        w.put(TOOLBAR+ns.CONTROL["width"], 1400)                                                  # NUKE near the right edge
        self.run_site(INFO["form_show"], INFO["form_show"]+6, EBX=FORM, ESI=0x4567, EDI=0x5678)
        self.assertEqual([v for a, v in self.called("set_left") if a == self.made[1]], [1400-ns.CONSOLE[0]])

    def test_missing_pictures_leave_the_console_plain(self):
        self.files = False
        self.run_site(INFO["form_show"], INFO["form_show"]+6, EBX=FORM, ESI=0x4567, EDI=0x5678)
        self.assertEqual((self.bitmaps, self.loaded, [e for _, e in self.called("image_picture")]), ([], [], [0, 0, 0, 0]))

    def test_an_install_path_up_to_max_path_fits(self):   # a default Steam path (98 characters) overflowed a shared page
        from unittest import mock
        folder = "C:/"+"x"*230+"/nuke_console/"                # 247: with "launch0s.bmp" the 259 that MAX_PATH allows
        with mock.patch.object(ns, "picture_folder", return_value=folder):
            texts = next(b for b in modern.build(CODE, DETAILS)[0] if b["name"] == "Nuclear strike: texts")
        self.assertIn(ns.literal(folder), bytes.fromhex(texts["bytes"]))

    def test_emcon_switches_the_players_radars_off_and_back_on(self):
        w, d = self.world, self.d
        # the player's: a radar ship, one with a damaged radar (resumed from a save made under EMCON), one without
        # radar; an enemy radar ship
        ships, _ = self.battle([(PLAYER_SIDE, 1000, 0, 0), (PLAYER_SIDE, 2000, 0, 0), (PLAYER_SIDE, 3000, 0, 0),
                                (ENEMY_SIDE, 4000, 0, 0)])
        for ship, radar, down in zip(ships, (4, 4, 0, 4), (0, 30+tree.EMCON, 0, 0)):
            w.put(ship+ns.SEARCH_RADAR, radar); w.put(ship+ns.RADAR_DOWN, down)
        w.put(d["emcon"], 1, 1)
        self.run_site(INFO["form_show"], INFO["form_show"]+6, EBX=FORM, ESI=0x4567, EDI=0x5678)
        button = self.made[-2]                                                                     # then SONAR
        def down(): return [w.get(s+ns.RADAR_DOWN) for s in ships]
        self.assertEqual((w.get(button+ns.CONTROL["tag"]), down(), w.get(d["emcon"]) & 0xFF,
                          [v for v in self.called("set_visible", 0xFF) if v[0] == button]),
                         (ns.TAGS["emcon"], [0, 30, 0, 0], 0, [(button, 1)]))                      # each battle: radars on
        del self.calls[:]
        self.call(self.at["emcon"], EAX=FORM, EDX=button)
        self.assertEqual((down(), self.texts(button), w.get(d["emcon"]) & 0xFF, len(self.called("redraw"))),
                         ([tree.EMCON, 30+tree.EMCON, tree.EMCON, 0], ["EMCON"], 1, 1))           # damage kept under it
        w.put(ships[0]+ns.RADAR_DOWN, tree.EMCON+12)                                              # hit while off
        self.call(self.at["emcon"], EAX=FORM, EDX=button)
        self.assertEqual((down(), self.texts(button)[-1], w.get(d["emcon"]) & 0xFF), ([12, 30, 0, 0], "RADAR ON", 0))

    def test_sonar_switches_active_and_passive_and_each_battle_starts_passive(self):
        w, d = self.world, self.d
        self.battle([(PLAYER_SIDE, 1000, 0, 0)]); w.owned = {ns.HYDROPHONES}; w.put(d["sonar"], 1, 1)
        self.run_site(INFO["form_show"], INFO["form_show"]+6, EBX=FORM, ESI=0x4567, EDI=0x5678)
        button = self.made[-1]
        self.assertEqual((w.get(button+ns.CONTROL["tag"]), w.get(d["sonar"]) & 0xFF, self.texts(button),
                          [v for v in self.called("set_visible", 0xFF) if v[0] == button],
                          (w.get(button+ns.CONTROL["on_click"]), w.get(button+ns.CONTROL["on_click"]+4))),
                         (ns.TAGS["sonar"], 0, ["PASSIVE"], [(button, 1)], (self.at["sonar"], FORM)))
        self.assertEqual([self.text(t) for a, t in self.called("assign") if a == button+ns.CONTROL["hint"]], [ns.TEXT["sonar_hint"]])
        del self.calls[:]
        self.call(self.at["sonar"], EAX=FORM, EDX=button)
        self.assertEqual((w.get(d["sonar"]) & 0xFF, self.texts(button), len(self.called("redraw"))), (1, ["ACTIVE"], 1))
        self.call(self.at["sonar"], EAX=FORM, EDX=button)
        self.assertEqual((w.get(d["sonar"]) & 0xFF, self.texts(button)[-1]), (0, "PASSIVE"))

    def pictures(self):
        for i in range(len(ns.PICTURES)): self.world.put(self.d["pictures"]+4*i, 0xB000+i)        # backdrop, keys, LAUNCH

    def tick(self, times, timer):
        for _ in range(times): self.call(self.at["key_tick"], EAX=FORM, EDX=timer)

    def test_both_keys_turn_frame_by_frame_and_only_both_at_arm_arm(self):
        w, d = self.world, self.d
        c = self.controls(); self.pictures()
        self.call(self.at["key1"], EAX=FORM, EDX=c["key1"])                                        # KEY 1: turn to ARM
        timer = self.made[-1]
        self.assertEqual((w.get(d["key_target"]) & 0xFFFF, w.get(timer+ns.CONTROL["tag"]), self.called("timer_enabled", 0xFF)),
                         (1, ns.TAGS["key_timer"], [(timer, 1)]))
        del self.calls[:]; self.tick(ns.FRAMES-1, timer)
        x, y, _, h = ns.LAYOUT["gauge_arm"]
        steps = range(1, ns.FRAMES)
        self.assertEqual([e for a, e in self.called("image_picture") if a == c["key1"]], [0xB001+k for k in steps])
        self.assertEqual([e for a, e in self.called("image_picture") if a == c["key2"]], [0xB001]*len(steps))
        self.assertEqual([v for a, v in self.called("set_height") if a == c["gauge_arm"]], [h*k//(2*(ns.FRAMES-1)) for k in steps])
        self.assertEqual((w.get(d["key_frame"]) & 0xFFFF, w.get(d["armed"]) & 0xFF, self.texts(c["status"])[-1]),
                         (ns.FRAMES-1, 0, "SAFE"))                                                 # one key is not enough
        self.assertEqual(self.called("timer_enabled", 0xFF), [(timer, 0)])                         # it stops when there
        self.call(self.at["key2"], EAX=FORM, EDX=c["key2"]); del self.calls[:]                     # KEY 2 as well
        self.tick(ns.FRAMES-1, timer)
        self.assertEqual((w.get(d["key_frame"]) & 0xFFFF, w.get(d["armed"]) & 0xFF, self.texts(c["status"])[-1]),
                         ((ns.FRAMES-1)*0x101, 1, "ARMED"))
        self.assertEqual(([v for a, v in self.called("set_height") if a == c["gauge_arm"]][-1],
                          [e for a, e in self.called("image_picture") if a == c["launch"]][-1]), (h, 0xB000+ns.LAUNCH_PICTURE+1))
        self.call(self.at["key1"], EAX=FORM, EDX=c["key1"]); del self.calls[:]; self.tick(1, timer)   # KEY 1 back: SAFE
        self.assertEqual((w.get(d["armed"]) & 0xFF, self.texts(c["status"])[-1]), (0, "SAFE"))

    def test_the_glass_lifts_on_a_click_and_the_next_click_launches(self):
        w, d = self.world, self.d
        self.battle([(PLAYER_SIDE, 9000, 0, 0)])
        c = self.controls(); self.pictures()
        self.call(self.at["glass"], EAX=FORM, EDX=c["launch"])                                     # shut: it lifts
        timer = self.made[-1]
        self.assertEqual((w.get(d["glass_target"]) & 0xFF, self.messages, w.get(self.used)), (1, [], 0))
        del self.calls[:]; self.tick(ns.GLASS-1, timer)
        self.assertEqual([e for a, e in self.called("image_picture") if a == c["launch"]],
                         [0xB000+ns.LAUNCH_PICTURE+2*g for g in range(1, ns.GLASS)])               # dark: not armed
        self.assertEqual((w.get(d["glass_frame"]) & 0xFF, self.called("timer_enabled", 0xFF)), (ns.GLASS-1, [(timer, 0)]))
        self.call(self.at["glass"], EAX=FORM, EDX=c["launch"])                                     # open: LAUNCH
        self.assertEqual(self.messages, [ns.TEXT["no_target"]])
        self.mark(); self.call(self.at["glass"], EAX=FORM, EDX=c["launch"])
        self.assertEqual(self.messages[-1], ns.TEXT["unarmed"])
        self.arm(1); self.call(self.at["glass"], EAX=FORM, EDX=c["launch"])
        self.assertEqual((w.get(self.used), w.get(d["glass_target"]) & 0xFF), (1, 0))             # fired; the glass shuts

    def test_abort_clears_the_target_turns_the_keys_back_and_shuts_the_glass(self):
        w, d = self.world, self.d
        c = self.controls()
        self.mark(); w.put(d["pick"], 1, 1); w.put(d["key_target"], 0x0101, 2); w.put(d["glass_target"], 1, 1)
        self.call(self.at["cancel"], EAX=FORM, EDX=c["cancel"])
        self.assertEqual((self.flags()[:2], w.get(d["key_target"]) & 0xFFFF, w.get(d["glass_target"]) & 0xFF), ([0, 0], 0, 0))
        timer = self.made[-1]
        self.assertEqual((w.get(timer+ns.CONTROL["tag"]), self.called("timer_enabled", 0xFF)), (ns.TAGS["key_timer"], [(timer, 1)]))
        self.assertEqual(self.called("set_cursor", 0xFFFF), [(GLOBE, 0)])
        self.assertEqual([v for v in self.called("set_visible", 0xFF) if v[0] == c["console"]], [(c["console"], 0)])
        self.assertEqual(self.texts(c["target"]), ["NONE"])

    def test_the_map_shows_the_zones_then_the_fireball_and_shock_ring(self):
        w, d, n = self.world, self.d, INFO
        points, bearings = [], []
        def bearing(): bearings.append(struct.unpack("<f", w.vm.mem_read(w.reg("ESP")+4, 4))[0]); return len(bearings)
        def point(): points.append((w.reg("EAX"), w.reg("EDX"), w.reg("ECX")))
        self.stub(n["bearing"], bearing, args=1); self.stub(n["point_at"], point, args=1)
        w.put(FRAME-4, FORM); w.put(0x9F772C, 0x772C); self.mark()
        self.run_site(n["render"], n["render"]+5)
        self.assertEqual(w.reg("EAX"), 0x772C)                                                    # the replayed load
        self.assertEqual(self.called("circle"), [(GLOBE, d["target"]), (GLOBE, d["target"])])
        self.assertEqual([c[3] for c in self.calls if c[0] == "circle"], [ns.FULL_YARDS, ns.RING_YARDS])
        self.assertEqual(self.called("pen_style", 0xFF), [(PEN, 1), (PEN, 0)])                  # dashed, then restored
        self.assertEqual(self.called("pen_color"), [(PEN, ns.COLOURS["red"]), (PEN, 0x111)])
        self.assertEqual(self.called("brush_color"), [(BRUSH, 0x222)])
        del self.calls[:]
        w.put(d["has_target"], 0, 1); w.put(d["active"], 1, 1); w.put(d["step"], ns.FLASH)
        for i, value in enumerate(TARGET): w.put(d["centres"]+4*i, value)
        w.put(d["blasts"], 1, 1)
        self.run_site(n["render"], n["render"]+5)
        self.assertEqual([(c[2], c[3]) for c in self.calls if c[0] == "circle"], [(d["centre"], ns.RING_YARDS*ns.FLASH//ns.SHOCK)])
        self.assertEqual(self.called("polygon"), [(GLOBE, d["points"])])
        self.assertEqual([c[3] for c in self.calls if c[0] == "polygon"], [ns.POINTS-1])
        self.assertEqual(bearings, [float(10*k) for k in range(ns.POINTS)])
        self.assertEqual(points, [(d["centre"], k+1, ns.FULL_YARDS) for k in range(ns.POINTS)])
        self.assertEqual(self.called("brush_color"), [(BRUSH, ns.COLOURS["orange"]), (BRUSH, 0x222)])
        self.assertEqual(self.called("brush_style", 0xFF), [(BRUSH, 1), (BRUSH, 0), (BRUSH, 0)])
        del self.calls[:]; w.put(d["active"], 0, 1)
        self.run_site(n["render"], n["render"]+5)
        self.assertEqual(self.calls, [])                                                          # nothing to draw

    def test_the_timer_steps_the_effect_and_stops_at_its_end(self):
        w, d = self.world, self.d
        w.put(d["active"], 1, 1); w.put(d["step"], ns.GLOW-2)
        self.call(self.at["tick"], EAX=FORM, EDX=0x7171)
        self.assertEqual((w.get(d["step"]), self.flags()[2], self.called("timer_enabled")), (ns.GLOW-1, 1, []))
        self.call(self.at["tick"], EAX=FORM, EDX=0x7171)
        self.assertEqual((w.get(d["step"]), self.flags()[2], self.called("timer_enabled", 0xFF)), (ns.GLOW, 0, [(0x7171, 0)]))
        self.assertEqual(len(self.called("redraw")), 2)


if __name__ == "__main__":
    unittest.main()

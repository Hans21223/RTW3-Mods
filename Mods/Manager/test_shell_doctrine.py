"""Special shell doctrine: the player's choice, its cost, the save value and the nuclear blast, in the emulator."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn.x86_const import *
from test_modern_combat import World, NATION, MAIN, DATA, STACK, FRAME, SHIP, TARGET
import modern_research as modern
import modern_tree as tree
import shell_doctrine as sd

DETAILS = modern.discover(open(HERE/"native-designer-inspection.text.bin", "rb").read(), 0x301000)
INFO = DETAILS["doctrine"]
OTHER, FORM, GROUP, BUTTONS, ITEMS, CLOSE, ACADEMY = (DATA+0x10000+i*0x1000 for i in range(7))
LIST, NEAR, FAR, OUT = DATA+0x18000, DATA+0x19000, DATA+0x1A000, DATA+0x1B000
FUNDS = NATION+sd.FUNDS


def blocks_of(world):
    return {b["name"][16:]: b["address"] for b in modern.build(0x2000000, DETAILS)[0] if b["name"].startswith("Shell doctrine: ")}


class DoctrineTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.at = blocks_of(self.world)
        self.world.vm.mem_write(self.at["table"], bytes(sd.SLOTS*8+4))             # nobody has chosen yet
        self.world.put(FUNDS, 1000)

    def call(self, address, **registers):
        w = self.world
        w.put(STACK+0x8000-4, 0x2FFFF0)
        for name, value in dict(dict(EBX=0x2345, ESI=0x4567, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000-4), **registers).items():
            w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        w.vm.emu_start(address, 0x2FFFF0, count=200000)
        self.assertEqual((w.reg("ESP"), w.reg("EBX"), w.reg("EBP")), (STACK+0x8000, 0x2345, FRAME))
        return w.reg("EAX")

    def choose(self, nation, flags): self.call(self.at["store"], EAX=nation, EDX=flags)

    def test_the_table_keeps_a_choice_per_nation_and_reuses_rows(self):
        self.assertEqual(self.call(self.at["lookup"], EAX=NATION, ECX=7, EDX=9), 0)
        self.assertEqual((self.world.reg("ECX"), self.world.reg("EDX")), (7, 9))
        self.choose(NATION, 2); self.choose(OTHER, 1); self.choose(NATION, 3)
        self.assertEqual([self.call(self.at["lookup"], EAX=n) for n in (NATION, OTHER, DATA)], [3, 1, 0])
        for i in range(sd.SLOTS+2): self.choose(DATA+0x100+i, 1)                    # more nations than rows
        self.assertEqual(self.call(self.at["lookup"], EAX=DATA+0x100+sd.SLOTS+1), 1)

    def use(self, kind, player=NATION):
        self.world.put(MAIN+sd.PLAYER, player)
        _, _, entries = sd.build(self.at["lookup"], INFO)
        return self.call(entries[kind], EDX=3) & 0xFF

    def test_the_player_fires_what_is_chosen_and_pays(self):
        self.assertEqual((self.use("use_guided"), self.use("use_nuclear"), self.world.get(FUNDS)), (0, 0, 1000))
        self.choose(NATION, sd.GUIDED)
        self.assertEqual((self.use("use_guided"), self.use("use_nuclear")), (1, 0))
        self.assertEqual(self.world.get(FUNDS), 1000-sd.GUIDED_COST)
        self.choose(NATION, sd.GUIDED | sd.NUCLEAR)
        self.assertEqual((self.use("use_nuclear"), self.world.get(FUNDS)), (1, 1000-sd.GUIDED_COST-sd.NUCLEAR_COST))
        self.assertEqual((self.use("use_nuclear"), self.world.get(FUNDS)), (0, 1000-sd.GUIDED_COST-sd.NUCLEAR_COST))   # cannot pay

    def test_other_nations_fire_free_but_no_nuclear_weapon_first(self):
        kinds = ("use_nuclear", "use_torpedo", "use_missile", "may_nuclear")
        w = self.world; mine = w.stubs[INFO["nation"]]

        def theirs(kind):                                                            # another nation's ship fires
            w.stubs[INFO["nation"]] = lambda: OTHER
            try: return self.use(kind)
            finally: w.stubs[INFO["nation"]] = mine
        self.assertEqual([theirs(k) for k in ("use_guided",)+kinds], [1, 0, 0, 0, 0])
        self.choose(NATION, sd.NUCLEAR)
        self.assertEqual((self.use("may_nuclear"), self.use("use_guided"), theirs("use_nuclear")), (1, 0, 0))   # not fired
        self.assertEqual((self.use("use_nuclear"), self.call(self.at["lookup"], EAX=NATION)), (1, sd.NUCLEAR | sd.NUCLEAR << 4))
        self.assertEqual([theirs(k) for k in kinds]+[w.get(FUNDS)], [1, 0, 0, 1, 1000-sd.NUCLEAR_COST])   # in kind: shells
        w.put(INFO["year"], DATA+0x380); w.put(DATA+0x380, 1960); w.put(FUNDS, 5000)
        self.choose(NATION, self.call(self.at["lookup"], EAX=NATION) | sd.MISSILE | 1 << 8)   # with an old treaty's year
        self.assertEqual((self.use("use_missile"), [theirs(k) for k in kinds]), (1, [1, 0, 1, 1]))
        self.turn(0)                                                                 # still at war: they keep firing
        self.assertEqual(theirs("use_nuclear"), 1)
        self.turn(0, war=-1)                                                         # peace: none first again
        self.assertEqual((self.call(self.at["lookup"], EAX=NATION), [theirs(k) for k in kinds]),
                         (sd.NUCLEAR | sd.MISSILE | 1 << 8, [0, 0, 0, 0]))
        w.put(FUNDS, 1000)
        self.assertEqual(self.use("use_nuclear"), 1)                                 # the next war: the player fires again
        self.turn(1, roll=0, answer=6)                                               # a signed treaty: none first again,
        w.put(DATA+0x380, 1960+sd.TREATY_YEARS+1)                                    # also once it has run out
        self.assertEqual((self.call(self.at["lookup"], EAX=NATION) & 0xFF, theirs("use_nuclear")), (sd.NUCLEAR | sd.MISSILE, 0))

    def test_the_save_value_carries_the_choice_above_the_native_field(self):
        w = self.world
        sites = INFO["sites"]
        w.put(NATION+sd.STORED, 0xEE)
        w.vm.reg_write(UC_X86_REG_EBX, NATION); w.vm.reg_write(UC_X86_REG_EAX, 0x302); w.vm.reg_write(UC_X86_REG_ESP, STACK+0x8000)
        w.vm.emu_start(sites["read"], sites["read"]+6, count=2000)
        self.assertEqual((w.get(NATION+sd.STORED), w.reg("ESP")), (2, STACK+0x8000))
        w.vm.emu_start(sites["write"], sites["write"]+6, count=2000)
        self.assertEqual(w.reg("EAX"), 0x302)

    def form(self, made=()):
        """A doctrine form whose component list holds the given (address, tag) controls; returns the call log."""
        w, n = self.world, INFO
        calls = []
        def stub(name, result=0): w.stubs[n[name]] = lambda: calls.append((name, w.reg("EAX"), w.reg("EDX"))) or result
        for name in ("set_text", "set_left", "set_top", "set_width", "set_height"): stub(name)
        w.stubs[n["has_research"]] = lambda: int(w.reg("EDX") in self.owned and w.reg("EAX") == NATION)
        vmt, new = DATA+0x1E000, [BUTTONS+0x100*i for i in range(1, 7)]
        def create():
            control = new.pop(0); calls.append(("create", w.reg("EAX"), w.reg("ECX"), w.reg("EDX") & 0xFF)); w.put(control, vmt)
            return control
        virtual = {sd.VCL["create"]: create,
                   sd.VCL["set_parent"]: lambda: calls.append(("parent", w.reg("EAX"), w.reg("EDX"))) or 0,
                   sd.VCL["set_checked"]: lambda: calls.append(("checked", w.reg("EAX"), w.reg("EDX") & 0xFF)) or 0,
                   sd.VCL["set_enabled"]: lambda: calls.append(("enabled", w.reg("EAX"), w.reg("EDX") & 0xFF)) or 0,
                   sd.VCL["get_checked"]: lambda: int(w.reg("EAX") in self.ticked)}
        for slot, handler in virtual.items():
            w.put(vmt+slot, DATA+0x1F000+slot); w.stubs[DATA+0x1F000+slot] = handler
        for field in ("torpedoes", "heavy_aa"): w.put(FORM+sd.FORM[field], GROUP); w.put(GROUP, vmt)
        w.put(FORM+sd.FORM["priority"], CLOSE); w.put(FORM+sd.CONTROL["height"], 700); w.put(FORM+0x57C, NATION)
        for field, value in (("left", 8), ("top", 528), ("width", 273)): w.put(CLOSE+sd.CONTROL[field], value)
        w.put(FORM+sd.FORM["components"], LIST); w.put(LIST+4, ITEMS); w.put(LIST+8, len(made)+1); w.put(ITEMS, GROUP)
        for index, (control, tag) in enumerate(made):
            w.put(ITEMS+4+4*index, control); w.put(control, vmt); w.put(control+sd.CONTROL["tag"], tag)
        return calls

    def show(self):
        w, n = self.world, INFO
        w.put(NATION+sd.STORED, 0x77)
        for name, value in dict(EAX=NATION, EBX=FORM, ESI=0x4567, EDI=0x5678, ESP=STACK+0x8000).items():
            w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        w.vm.emu_start(n["sites"]["show"], n["sites"]["show"]+6, count=20000)
        self.assertEqual([w.reg(r) for r in ("EAX", "EBX", "EDX", "ESI", "EDI", "ESP")], [NATION, FORM, 0x77, 0x4567, 0x5678, STACK+0x8000])

    def test_the_form_gets_a_box_with_its_tick_boxes_once(self):
        w = self.world
        self.owned = {tree.GUIDED_SHELLS[0]}
        calls = self.form()
        box, guided, nuclear, torpedo, missile, conserve = (BUTTONS+0x100*i for i in range(1, 7))
        ticks = dict(guided=guided, nuclear=nuclear, torpedo=torpedo, missile=missile, conserve=conserve)
        self.show()
        self.assertEqual([c for c in calls if c[0] == "create"], [("create", DATA+0x1E000, FORM, 1)]*6)
        self.assertEqual([c for c in calls if c[0] == "parent"], [("parent", box, FORM)]+[("parent", t, box) for t in ticks.values()])
        self.assertEqual([w.get(c+sd.CONTROL["tag"]) for c in (box, *ticks.values())], [sd.TAGS[k] for k in ("box", *ticks)])
        placed = [c for c in calls if c[0].startswith("set_") and c[0] != "set_text"]
        self.assertEqual(placed[:6], [("set_left", box, 8), ("set_top", box, 528), ("set_width", box, 273),
                                      ("set_height", box, sd.BOX_HEIGHT), ("set_top", CLOSE, 528+sd.MOVE), ("set_height", FORM, 700+sd.MOVE)])
        self.assertEqual(placed[6:], [call for key, _, top in sd.BOXES for call in
                                      (("set_left", ticks[key], 16), ("set_top", ticks[key], top), ("set_width", ticks[key], 240))])
        text = lambda p: bytes(w.vm.mem_read(p, 2*w.get(p-4))).decode("utf-16-le")
        self.assertEqual([(c[1], text(c[2])) for c in calls if c[0] == "set_text"],
                         [(box, sd.TEXTS["caption"])]+[(ticks[key], sd.TEXTS[key]) for key in ticks])

    def test_the_tick_boxes_show_the_choice_and_grey_without_research(self):
        self.owned = {tree.NUCLEAR_SHELLS[0]}
        guided, nuclear = BUTTONS+0x200, BUTTONS+0x300
        calls = self.form([(BUTTONS+0x100, sd.TAGS["box"]), (guided, sd.TAGS["guided"]), (nuclear, sd.TAGS["nuclear"])])
        self.choose(NATION, sd.NUCLEAR)
        self.show()
        self.assertEqual(calls, [("checked", guided, 0), ("enabled", guided, 0), ("checked", nuclear, 1), ("enabled", nuclear, 1)])   # no SSN or SSBN boxes on this form

    def test_only_the_player_conserves_sams(self):
        _, _, entries = sd.build(self.at["lookup"], INFO)
        self.world.put(MAIN+sd.PLAYER, NATION)
        asked = lambda: self.call(entries["conserve"], EDX=3)
        self.assertEqual(asked(), 0)
        self.choose(NATION, sd.CONSERVE | sd.GUIDED); self.assertEqual(asked(), 1)
        self.choose(NATION, sd.GUIDED); self.assertEqual(asked(), 0)
        self.choose(NATION, sd.CONSERVE); self.world.put(MAIN+sd.PLAYER, OTHER); self.assertEqual(asked(), 0)

    def test_code_blocks_of_the_whole_adapter_do_not_overlap(self):
        spans = sorted((b["address"], b["address"]+len(b["bytes"])//2, b["name"]) for b in modern.build(0x2000000, DETAILS)[0])
        self.assertEqual([(a[2], b[2]) for a, b in zip(spans, spans[1:]) if a[1] > b[0]], [])

    def test_close_stores_the_ticks_and_leaves_the_native_field(self):
        w, n = self.world, INFO
        guided, nuclear = BUTTONS+0x200, BUTTONS+0x300
        self.owned = set()
        self.form([(guided, sd.TAGS["guided"]), (nuclear, sd.TAGS["nuclear"])])
        self.choose(NATION, 0x4B00)                                                   # a treaty year rides above the ticks
        for ticked, flags in (({guided}, 0x4B01), ({nuclear}, 0x4B02), ({guided, nuclear}, 0x4B03), (set(), 0x4B00)):
            self.ticked = ticked
            w.put(NATION+sd.STORED, 2)
            for name, value in dict(EAX=1, EBX=FORM, ESI=NATION, EBP=FRAME, ESP=STACK+0x8000).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
            w.vm.emu_start(n["sites"]["close"], n["sites"]["close"]+6, count=5000)
            self.assertEqual([w.reg(r) for r in ("EAX", "EBX", "ESI", "EBP", "ESP")], [1, FORM, NATION, FRAME, STACK+0x8000])
            self.assertEqual((self.call(self.at["lookup"], EAX=NATION), w.get(NATION+sd.STORED)), (flags, 2))

    def turn(self, used, roll=1, answer=7, year=1960, war=1):
        """One RandomTensionChanges entry; returns (tension changes, news, questions)."""
        w, n = self.world, INFO
        _, _, entries = sd.build(self.at["lookup"], INFO)
        changes, news, asked = [], [], []
        text = lambda p: bytes(w.vm.mem_read(p, 2*w.get(p-4))).decode("utf-16-le")
        nations = {i: DATA+0x400+0x200*i for i in range(1, 9)}
        w.put(nations[4]+0x1CC, 4, 1)
        w.put(n["year"], DATA+0x380); w.put(DATA+0x380, year); w.put(MAIN+sd.PLAYER, NATION)
        w.put(n["news_form"], DATA+0x390); w.put(DATA+0x390, 0x4E455753)
        battle = w.stubs[n["nation"]]
        w.stubs[n["nation"]] = lambda: nations.get(w.reg("EDX"), 0) if w.reg("EAX") == MAIN else 0
        def change():
            sp = w.reg("ESP"); changes.append((w.reg("EDX"), w.reg("ECX"), text(w.get(sp+4))))
            w.put(sp+4, w.get(sp)); w.vm.reg_write(UC_X86_REG_ESP, sp+4); return 0
        def tell():
            sp = w.reg("ESP"); news.append((w.reg("EAX"), text(w.reg("EDX")), w.reg("ECX"), w.get(sp+4)))
            w.put(sp+4, w.get(sp)); w.vm.reg_write(UC_X86_REG_ESP, sp+4); return 0
        def ask():
            sp = w.reg("ESP"); asked.append((text(w.reg("EAX")), w.reg("EDX") & 0xFF, w.reg("ECX")))
            w.put(sp+4, w.get(sp)); w.vm.reg_write(UC_X86_REG_ESP, sp+4); return answer
        w.stubs.update({n["change_tension"]: change, n["news"]: tell, n["message_dlg"]: ask, n["random"]: lambda: roll})
        w.put(entries["used"], used); w.put(n["war"], war & 0xFFFFFFFF)
        for name, value in dict(EAX=MAIN, EBX=0x2345, ECX=0x1234, ESI=0x4567, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000).items():
            w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        w.vm.emu_start(n["month"], n["month"]+8, count=20000)
        self.assertEqual([w.reg(r) for r in ("EAX", "EBX", "ECX", "ESI", "EDI", "EBP", "ESP")],
                         [MAIN, 0x2345, 0x17, 0x4567, 0x5678, STACK+0x8000-4, STACK+0x8000-4])
        self.assertEqual(w.get(entries["used"]), 0)
        w.stubs[n["nation"]] = battle
        return changes, news, asked

    def test_nuclear_weapons_raise_every_nations_tension_at_the_next_turn(self):
        self.assertEqual(self.turn(0), ([], [], []))
        changes, news, asked = self.turn(1)
        self.assertEqual(changes, [(DATA+0x400+0x200*i, sd.NUCLEAR_TENSION, sd.NEWS["reason"]) for i in (1, 2, 3, 5, 6, 7, 8)])
        self.assertEqual((news, asked), ([(0x4E455753, sd.NEWS["news"], INFO["picture"], 1)], []))

    def test_a_signed_treaty_stops_nuclear_weapons_for_its_years(self):
        self.choose(NATION, sd.GUIDED | sd.NUCLEAR)
        changes, news, asked = self.turn(1, roll=0, answer=7)                        # refused
        self.assertEqual((asked, self.call(self.at["lookup"], EAX=NATION)), ([(sd.NEWS["treaty"], 3, 3)], 3))
        self.turn(1, roll=0, answer=6)                                               # signed in 1960
        self.assertEqual(self.call(self.at["lookup"], EAX=NATION), 3 | (60+sd.TREATY_YEARS) << 8)
        self.assertEqual((self.use("use_nuclear"), self.use("use_guided")), (0, 1))
        native = self.world.stubs[INFO["nation"]]
        self.world.stubs[INFO["nation"]] = lambda: OTHER                             # another nation's ship fires
        self.assertEqual(self.use("use_nuclear"), 0)
        self.world.stubs[INFO["nation"]] = native
        _, _, entries = sd.build(self.at["lookup"], INFO)
        self.assertEqual(self.call(entries["may_nuclear"], EDX=3) & 0xFF, 0)
        self.world.put(DATA+0x380, 1960+sd.TREATY_YEARS+1)                           # the treaty has run out
        self.assertEqual(self.use("use_nuclear"), 1)

    def test_a_nuclear_hit_strikes_ships_near_the_target(self):
        w, n = self.world, INFO
        hits = []
        ships = [TARGET, SHIP, NEAR, FAR, OUT, 0]
        w.put(n["ships"], DATA+0x300); w.put(DATA+0x300, LIST); w.put(LIST+8, len(ships))
        w.stubs[n["list_get"]] = lambda: ships[w.reg("EDX")]
        ranges = {NEAR: 900, FAR: 1501, OUT: 100, SHIP: 50}
        w.stubs[n["ship_distance"]] = lambda: ranges.get(w.reg("EDX"), 7000) if w.reg("EAX") == TARGET else 12345
        w.stubs[n["ship_name"]] = lambda: w.put(w.reg("EDX"), 0x4E414D45) or 0
        def hit():
            sp = w.reg("ESP")
            hits.append((w.reg("EAX"), w.reg("EDX"), w.reg("ECX"), struct.unpack("<8I", w.vm.mem_read(sp+4, 32))))
            w.put(sp+32, w.get(sp)); w.vm.reg_write(UC_X86_REG_ESP, sp+32); return 0   # the callee drops its eight arguments
        w.stubs[n["handle_hit"]] = hit
        for ship in (TARGET, SHIP, NEAR, FAR, OUT): w.vm.mem_write(ship, bytes(0xE20))
        w.put(OUT+sd.SHIP["out"], 1, 1); w.put(SHIP+0x14, 3); w.put(SHIP+0x75+4, 0x51); w.put(SHIP+0x9A6, 1, 1)
        for offset, value in ((-0x24, SHIP), (-0x28, TARGET), (0x18, 1), (-4, 0x99), (-0x40, 0x40)): w.put(FRAME+offset, value)
        w.put(FRAME-0x49, 1, 1)
        _, _, entries = sd.build(self.at["lookup"], INFO)
        self.call(entries["blast"], ESI=0x4567, EDI=0x5678)
        self.assertEqual((w.reg("ESI"), w.reg("EDI")), (0x4567, 0x5678))
        self.assertEqual(hits, [(NEAR, 0x99, 0x4E414D45, (FRAME-0x20, 1, 0x40, 1, 3, 0x51, 12345, sd.BLAST_CALIBRE))])


if __name__ == "__main__": unittest.main(verbosity=2)

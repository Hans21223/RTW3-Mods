"""SSN and SSBN: the build list, the name mark, the salvo and the nuclear torpedo and missile hits, in the emulator."""
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
import nuclear_subs as subs
import shell_doctrine as sd

DETAILS = modern.discover(open(HERE/"native-designer-inspection.text.bin", "rb").read(), 0x301000)
INFO = DETAILS["subs"]
TEXT, SUB, SHOT, FORM, LIST, NEAR, FAR = (DATA+0x10000+i*0x1000 for i in range(7))
RETURN = 0x2FFFF0


class SubTests(unittest.TestCase):
    def setUp(self):
        self.world = w = World({tree.SSN, tree.SSBN})
        blocks = modern.build(0x2000000, DETAILS)[0]
        self.at = {b["name"][20:]: b["address"] for b in blocks if b["name"].startswith("Nuclear submarines: ")}
        self.used = next(b["address"] for b in blocks if b["name"] == "Shell doctrine: table")+sd.SLOTS*8+4
        w.put(w.doctrine+4, sd.TORPEDO | sd.MISSILE)                               # the player allows both

    def string(self, address, text):
        self.world.vm.mem_write(address, subs.literal(text)); return address+12

    def text(self, pointer):
        w = self.world; return bytes(w.vm.mem_read(pointer, 2*w.get(pointer-4))).decode("utf-16-le")

    def call(self, address, **registers):
        w = self.world
        w.put(STACK+0x8000-4, RETURN)
        for name, value in dict(dict(EBX=0x2345, ESI=0x4567, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000-4), **registers).items():
            w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        w.vm.emu_start(address, RETURN, count=200000)
        return w.reg("EAX")

    def test_a_nuclear_boat_is_built_with_a_better_class(self):
        w, site = self.world, INFO["sites"]["class"]["address"]
        for name, accuracy, built in (("U-1", 0, (49, 0)), ("U-1 SSN", 0, (49+subs.AVAILABILITY, 1)),
                                      ("U-1 SSN", 1, (49+subs.AVAILABILITY, 1)), ("U-1 SSBN", -2, (49+subs.AVAILABILITY, -2))):
            w.vm.mem_write(SUB, bytes(0x40)); w.put(SUB+4, self.string(TEXT, name)); w.put(SUB+8, 49); w.put(SUB+0xC, accuracy & 0xFFFFFFFF)
            w.put(NATION+0x111, 0x4C495354)
            for reg, value in dict(EAX=0x11, EBX=0x2345, ECX=0x22, EDX=0x33, ESI=NATION, EDI=SUB, ESP=STACK+0x8000).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
            w.vm.emu_start(site, site+6, count=5000)
            signed = lambda v: v-(1 << 32) if v >> 31 else v
            self.assertEqual((w.get(SUB+8), signed(w.get(SUB+0xC))), built, (name, accuracy))
            self.assertEqual([w.reg(r) for r in ("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "ESP")],
                             [0x4C495354, 0x2345, 0x22, 0x33, NATION, SUB, STACK+0x8000])

    def test_a_name_ending_in_the_mark_is_a_new_kind(self):
        for name, kind in (("S-12 SSN", 1), ("S-12 SSBN", 2), ("SS S-7", 0), ("SSN", 1), ("SN", 0), ("SSBN", 2), ("SSN-3", 0), ("", 0)):
            self.assertEqual(self.call(self.at["is_kind"], EAX=self.string(TEXT, name)), kind, name)
        self.assertEqual(self.call(self.at["is_kind"], EAX=0), 0)

    def test_the_list_text_gives_the_native_role_and_remembers_the_kind(self):
        w = self.world
        w.stubs[INFO["pos"]] = lambda: self.text(w.reg("EDX")).find(self.text(w.reg("EAX")))+1
        site = INFO["sites"]["kind"]["address"]
        for text, role, chosen in ((subs.TEXTS["list_ssn"], 3, 1), (subs.TEXTS["list_ssbn"], 4, 2), ("Missile submarine (SSG)", None, 0)):
            w.put(STACK+0x8000-4, RETURN)
            for name, value in dict(EAX=FORM, EDX=self.string(TEXT, text), EBX=0x2345, ESP=STACK+0x8000-4).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
            w.vm.emu_start(site, RETURN if role else site+5, count=5000)
            self.assertEqual(w.get(self.at["data"]), chosen, text)
            if role: self.assertEqual((w.reg("EAX"), w.reg("ESP"), w.reg("EBX")), (role, STACK+0x8000, 0x2345))
            else: self.assertEqual((w.reg("EAX"), w.reg("EDX"), w.reg("ESP")), (FORM, TEXT+12, STACK+0x8000-16))   # native prologue ran

    def order(self, site, role, roll, balance=500, owned=(tree.SSN, tree.SSBN), nation=NATION):
        """A computer nation's order through the hook: (role, name) that reach StartBuildingSubmarine."""
        w = self.world; got = []
        w.owned = set(owned); name = self.string(TEXT, "U-47")
        w.stubs[INFO["random"]] = lambda: roll
        w.stubs[INFO["monthly_balance"]] = lambda: balance
        w.stubs[INFO["asg"]] = lambda: w.put(w.reg("EAX"), w.reg("EDX")) or 0
        w.stubs[INFO["cat"]] = lambda: w.put(w.reg("EAX"), self.string(TEXT+0x400, self.text(w.get(w.reg("EAX")))+self.text(w.reg("EDX")))) or 0
        w.stubs[INFO["start"]] = lambda: got.append((w.reg("ECX") & 0xFF, self.text(w.get(w.reg("ESP")+4)), w.reg("EAX"), w.reg("EDX"))) or 0x777
        address = INFO["sites"][site]["address"]
        w.put(STACK+0x8000-4, name)                                                    # the stack argument
        for reg, value in dict(EAX=MAIN, EDX=nation, ECX=0xAB00 | role, EBX=0x2345, ESI=0x4567, EDI=0x5678, EBP=FRAME,
                               ESP=STACK+0x8000-4).items():
            w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
        w.vm.emu_start(address, address+5, count=20000)
        self.assertEqual((w.reg("EIP"), w.reg("EAX"), w.reg("EBX"), w.reg("ESI"), w.reg("EDI"), w.reg("EBP"), w.reg("ESP")),
                         (address+5, 0x777, 0x2345, 0x4567, 0x5678, FRAME, STACK+0x8000-4))
        self.assertEqual(got[0][2:], (MAIN, nation))
        return got[0][:2]

    def test_a_computer_nation_orders_the_new_kinds_with_the_research_and_a_surplus(self):
        plain = lambda role: (role, "U-47")
        for site in ("ai_sub1", "ai_sub2", "ai_sub3", "ai_first"):
            for role in (0, 3):
                self.assertEqual(self.order(site, role, subs.AI_SSBN-1), (4, "U-47 SSBN"))
                self.assertEqual(self.order(site, role, subs.AI_SSBN), (3, "U-47 SSN"))
                self.assertEqual(self.order(site, role, subs.AI_SSBN+subs.AI_SSN-1), (3, "U-47 SSN"))
                self.assertEqual(self.order(site, role, subs.AI_SSBN+subs.AI_SSN), plain(role))
                self.assertEqual(self.order(site, role, 0, owned=(tree.SSN,)), (3, "U-47 SSN"))   # no SSBN research
                self.assertEqual(self.order(site, role, 0, owned=()), plain(role))
            self.assertEqual(self.order(site, 4, subs.AI_MISSILE-1), (4, "U-47 SSBN"))
            self.assertEqual(self.order(site, 4, subs.AI_MISSILE), plain(4))
            self.assertEqual(self.order(site, 4, 0, owned=(tree.SSN,)), plain(4))
            for role in (1, 2): self.assertEqual(self.order(site, role, 0), plain(role))            # minelayer, coastal
            self.assertEqual(self.order(site, 0, 0, nation=0), plain(0))
            poor = self.order(site, 0, 20, balance=0)                                           # only the start ignores it
            self.assertEqual(poor, (3, "U-47 SSN") if site == "ai_first" else plain(0))

    def test_player_auto_build_marks_researched_long_range_and_missile_boats(self):
        w, built = self.world, []
        next_text = [TEXT+0x1000]

        def cat():
            slot, suffix = w.reg("EAX"), self.text(w.reg("EDX"))
            original = self.text(w.get(slot))
            pointer = self.string(next_text[0], original+suffix)
            next_text[0] += 0x100
            w.put(slot, pointer)
            return 0

        def start():
            sp = w.reg("ESP")
            built.append((w.reg("ECX") & 0xFF, self.text(w.get(sp+4))))
            return 0x777

        w.stubs[INFO["cat"]] = cat
        w.stubs[INFO["start"]] = start
        cases = (
            (3, {tree.SSN}, "S-1", "S-1 SSN"),
            (4, {tree.SSBN}, "S-2", "S-2 SSBN"),
            (3, {tree.SSBN}, "S-3", "S-3"),
            (4, {tree.SSN}, "S-4", "S-4"),
            (3, {tree.SSN}, "S-5 SSN", "S-5 SSN"),
            (1, {tree.SSN, tree.SSBN}, "S-6", "S-6"),
        )
        for index, (role, owned, name, expected) in enumerate(cases):
            w.owned = set(owned)
            pointer = self.string(TEXT+0x2000+index*0x100, name)
            w.put(FRAME-0xAC, pointer)
            w.put(STACK+0x8000-4, RETURN)
            w.put(STACK+0x8000, pointer)
            for reg, value in dict(EAX=MAIN, EDX=NATION, ECX=role, EBP=FRAME,
                                   ESP=STACK+0x8000-4).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
            w.vm.emu_start(self.at["player_auto"], RETURN, count=10000)
            self.assertEqual(built[-1], (role, expected))

    def test_modern_research_allocation_contains_every_generated_block(self):
        base = 0x2000000
        blocks, _, _ = modern.build(base, DETAILS)
        size = modern.runtime_allocation_size(DETAILS)
        modern.validate_runtime_blocks(blocks, base, size)
        self.assertEqual(size, 0x26000)   # with the nuclear strike console's pages, point defence's three, undersea's

    def test_the_list_gains_the_researched_kinds(self):
        w = self.world
        added = []
        items, vmt = DATA+0x1D000, DATA+0x1D100
        w.put(FORM+subs.LIST_ITEMS[0], LIST); w.put(LIST+subs.LIST_ITEMS[1], items); w.put(items, vmt); w.put(vmt+0x3C, DATA+0x1D200)
        w.stubs[DATA+0x1D200] = lambda: added.append((w.reg("EAX"), self.text(w.reg("EDX")))) or 0
        w.stubs[INFO["fill"]] = lambda: added.append(("native", w.reg("EAX"), w.reg("EDX"))) or 0
        for owned, expected in (({tree.SSN, tree.SSBN}, ["list_ssn", "list_ssbn"]), ({tree.SSBN}, ["list_ssbn"]), (set(), [])):
            w.owned = owned; del added[:]
            self.call(INFO["sites"]["list"]["address"], EAX=FORM, EDX=NATION)
            self.assertEqual(self.world.reg("EIP"), INFO["sites"]["list"]["address"]+5)
            self.assertEqual(added, [("native", FORM, NATION)]+[(items, subs.TEXTS[k]) for k in expected])

    def call(self, address, **registers):   # a call site returns after itself; anything else to RETURN
        w = self.world
        sites = {s["address"]: s["address"]+5 for s in INFO["sites"].values() if s["kind"] == "call"}
        stop = sites.get(address, RETURN)
        w.put(STACK+0x8000-4, RETURN)
        esp = STACK+0x8000 if address in sites else STACK+0x8000-4
        for name, value in dict(dict(EBX=0x2345, ESI=0x4567, EDI=0x5678, EBP=FRAME, ESP=esp), **registers).items():
            w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        w.vm.emu_start(address, stop, count=200000)
        return w.reg("EAX")

    def test_a_new_kind_s_name_gets_its_mark_at_the_build_call(self):
        w = self.world
        built = []
        def start():
            sp = w.reg("ESP"); built.append(self.text(w.get(sp+4)))
            w.put(sp+4, w.get(sp)); w.vm.reg_write(UC_X86_REG_ESP, sp+4); return 0x99
        def cat():   # UStrCat(var EAX, EDX): the native string append
            new = self.string(DATA+0x1C000+0x100*len(built), self.text(w.get(w.reg("EAX")))+self.text(w.reg("EDX")))
            w.put(w.reg("EAX"), new); return 0
        w.stubs[INFO["start"]] = start; w.stubs[INFO["cat"]] = cat
        for chosen, name in ((1, "S-4 SSN"), (2, "S-4 SSBN"), (0, "S-4")):
            w.put(self.at["data"], chosen); plain = self.string(TEXT, "S-4")
            w.put(FRAME-8, plain); w.put(STACK+0x8000-4, plain)
            site = INFO["sites"]["build"]["address"]
            for reg, value in dict(EAX=MAIN, EDX=NATION, ECX=3, EBP=FRAME, ESP=STACK+0x8000-4, EBX=0x2345).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
            w.vm.emu_start(site, site+5, count=5000)
            self.assertEqual((built[-1], w.reg("EAX"), w.reg("ESP"), w.reg("EBX")), (name, 0x99, STACK+0x8000, 0x2345))

    def test_an_ssbn_launches_several_missiles_where_a_missile_boat_launches_one(self):
        w = self.world
        arguments = (2, 0x1F, 0x71, 0x72, 90, TARGET, TEXT+0x800)
        for name, count in (("S-9 SSBN", subs.SSBN_MISSILES), ("S-9", 1)):
            launched = []
            def launch():
                sp = w.reg("ESP")
                launched.append((w.reg("EAX"), w.reg("EDX"), w.reg("ECX"), struct.unpack("<7I", w.vm.mem_read(sp+4, 28))))
                w.put(sp+28, w.get(sp)); w.vm.reg_write(UC_X86_REG_ESP, sp+28); return 0x99
            w.stubs[INFO["launch"]] = launch
            w.put(SUB+subs.SUB_NAME, self.string(TEXT, name)); w.put(SUB+8, 3); w.put(FRAME-4, 0xBA771E)
            w.vm.mem_write(STACK+0x8000-28, struct.pack("<7I", *arguments))
            site = INFO["sites"]["salvo"]["address"]
            for reg, value in dict(EAX=0xBA771E, EDX=3, ECX=SUB+0x14, EBX=SUB, ESI=0x4567, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000-28).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
            w.vm.emu_start(site, site+5, count=5000)
            self.assertEqual(launched, [(0xBA771E, 3, SUB+0x14, arguments)]*count, name)
            self.assertEqual([w.reg(r) for r in ("EAX", "EBX", "ESI", "EDI", "ESP")], [0x99, SUB, 0x4567, 0x5678, STACK+0x8000])

    def test_the_new_kinds_cost_more_to_build_and_keep(self):
        w = self.world
        asked = []
        def cost():   # the native routine: one stack argument
            sp = w.reg("ESP"); asked.append((w.reg("EAX"), w.reg("EDX"), w.reg("ECX") & 0xFF, w.get(sp+4)))
            w.put(sp+4, w.get(sp)); w.vm.reg_write(UC_X86_REG_ESP, sp+4); return 200
        w.stubs[INFO["cost"]] = cost
        for site, register in subs.COST_SITES.items():
            for name, chosen, expected in (("S-1 SSN", 1, 500), ("S-1 SSBN", 2, 800), ("S-1", 0, 200)):
                w.put(SUB+4, self.string(TEXT, name)); w.put(self.at["data"], chosen)
                address = INFO["sites"][site]["address"]
                w.put(STACK+0x8000-4, 1)                                             # the flag argument
                for reg, value in dict(EAX=MAIN, EDX=NATION, ECX=3, EBX=SUB, ESI=SUB, EDI=0x5678, ESP=STACK+0x8000-4).items():
                    w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
                w.vm.emu_start(address, address+5, count=5000)
                self.assertEqual((w.reg("EAX"), w.reg("ESP"), w.reg("EBX"), w.reg("ESI"), w.reg("EDI")),
                                 (expected, STACK+0x8000, SUB, SUB, 0x5678), (site, name))
        self.assertEqual(set(asked), {(MAIN, NATION, 3, 1)})

    def battle(self):
        """Target with a ship near and one far; returns the list HandleHit calls are recorded in."""
        w, n = self.world, INFO
        hits = []
        ships = [TARGET, NEAR, FAR]
        w.put(n["ships"], DATA+0x300); w.put(DATA+0x300, LIST); w.put(LIST+8, len(ships))
        for ship in ships: w.vm.mem_write(ship, bytes(0xE20))
        w.stubs[n["list_get"]] = lambda: ships[w.reg("EDX")]
        w.stubs[n["ship_distance"]] = lambda: {NEAR: 1200, FAR: 1600}[w.reg("EDX")]
        # GetIncomingBearing needs the firing ship in EDX, which a blast has not: the bearing is Random(360).
        w.stubs[0x8ECB84] = lambda: self.fail("strike asked GetIncomingBearing without a firing ship")
        def hit():
            sp = w.reg("ESP")
            hits.append((w.reg("EAX"), self.text(w.reg("ECX")), w.reg("EDX"), struct.unpack("<8I", w.vm.mem_read(sp+4, 32))))
            w.put(sp+32, w.get(sp)); w.vm.reg_write(UC_X86_REG_ESP, sp+32); return 0
        w.stubs[n["handle_hit"]] = hit
        self.roll, self.radar = 99, []
        w.stubs[n["random"]] = lambda: 0x40 if w.reg("EAX") == 360 else self.roll
        w.stubs[n["damage_radar"]] = lambda: self.radar.append(w.reg("EAX")) or 0
        return hits

    def test_a_missile_hit_damages_the_radar_more_often(self):
        w = self.world
        self.battle()
        w.put(SHOT+subs.SHOT_NAME, self.string(TEXT, "DD Fletcher")); w.put(SHOT+subs.SHOT_NATION, 3)
        for roll, damaged in ((subs.MISSION_KILL-1, [TARGET]), (subs.MISSION_KILL, [])):
            self.roll = roll; del self.radar[:]
            self.assertEqual(self.call(self.at["missile"], EBX=SHOT, ESI=TARGET) & 0xFF, 0)
            self.assertEqual((self.radar, w.reg("EBX"), w.reg("ESI")), (damaged, SHOT, TARGET))

    def test_one_missile_hit_of_an_ssbn_salvo_is_nuclear_and_blasts(self):
        w = self.world
        hits = self.battle()
        entry = self.at["missile"]
        self.assertEqual(entry & 0xFFF, subs.MISSILE_ENTRY)
        w.put(SHOT+subs.SHOT_NAME, self.string(TEXT, "SSG S-9 SSBN")); w.put(SHOT+subs.SHOT_NATION, 3)
        funds = w.get(NATION+sd.FUNDS)
        self.assertEqual(self.call(entry, EBX=SHOT, ESI=TARGET) & 0xFF, 1)
        self.assertEqual((w.reg("EBX"), w.reg("ESI"), w.reg("ESP")), (SHOT, TARGET, STACK+0x8000))
        record = self.at["data"]+0x40
        self.assertEqual(hits, [(NEAR, "SSG S-9 SSBN", 0, (record, 0, 0x40, 1, 3, 0, 0x1388, subs.BLAST_CALIBRE))])
        self.assertEqual((w.get(NATION+sd.FUNDS), w.get(self.used)), (funds-sd.MISSILE_COST, 1))
        w.put(SHOT+0x3000+subs.SHOT_NAME, w.get(SHOT+subs.SHOT_NAME)); w.put(SHOT+0x3000+subs.SHOT_NATION, 3)   # the same salvo
        self.assertEqual((self.call(entry, EBX=SHOT+0x3000, ESI=TARGET) & 0xFF, len(hits)), (0, 1))
        w.put(SHOT+0x1000+subs.SHOT_NAME, self.string(TEXT+0x100, "SSG S-9")); w.put(SHOT+0x1000+subs.SHOT_NATION, 3)
        self.assertEqual(self.call(entry, EBX=SHOT+0x1000, ESI=TARGET) & 0xFF, 0)                    # an ordinary boat
        w.put(w.doctrine+4, sd.TORPEDO); w.put(SHOT+0x2000+subs.SHOT_NAME, TEXT+12); w.put(SHOT+0x2000+subs.SHOT_NATION, 3)
        self.assertEqual(self.call(entry, EBX=SHOT+0x2000, ESI=TARGET) & 0xFF, 0)                    # not allowed

    def test_a_missile_counts_as_the_nation_of_its_launchers_side(self):
        w = self.world   # a missile holds its launcher's battle side (here 1), the doctrine and research want nations
        hits = self.battle()
        items = LIST+0x100
        for i, (ship, side) in enumerate(((TARGET, 0), (NEAR, 1), (FAR, 0))):
            w.put(items+4*i, ship); w.put(ship+0xA55, side)
        w.put(LIST+4, items); w.put(NEAR+0x14, 3)                                                  # side 1: nation 3
        w.put(SHOT+subs.SHOT_NAME, self.string(TEXT, "SSG S-9 SSBN")); w.put(SHOT+subs.SHOT_NATION, 1)
        self.assertEqual(self.call(self.at["missile"], EBX=SHOT, ESI=TARGET) & 0xFF, 1)         # nation 3 pays for it
        self.assertEqual(hits[0][3][4], 3)                                                       # and its blast is theirs

    def test_under_armageddon_every_ssbn_hit_and_heavy_ssm_hits_are_nuclear(self):
        w = self.world
        hits = self.battle()
        entry, armageddon = self.at["missile"], self.used+4
        w.owned = {tree.SSN, tree.SSBN, tree.NUCLEAR_SHELLS[0]}
        heavy = SHOT+0x2000
        w.put(heavy+subs.SHOT_NAME, self.string(TEXT+0x100, "CGN Kirov")); w.put(heavy+subs.SHOT_NATION, 3)
        w.put(heavy+subs.SHOT_KIND, subs.HEAVY_SSM)
        self.assertEqual(self.call(entry, EBX=heavy, ESI=TARGET) & 0xFF, 0)                          # without the sub-mod
        w.put(armageddon, 1)
        funds = w.get(NATION+sd.FUNDS)
        name = self.string(TEXT, "SSG S-9 SSBN")
        for shot in (SHOT, SHOT+0x1000):                                                            # two hits of one salvo
            w.put(shot+subs.SHOT_NAME, name); w.put(shot+subs.SHOT_NATION, 3)
            self.assertEqual(self.call(entry, EBX=shot, ESI=TARGET) & 0xFF, 1)
        for kind, expected in ((subs.HEAVY_SSM, 1), (32, 0), (30, 0)):
            w.put(heavy+subs.SHOT_KIND, kind)
            self.assertEqual(self.call(entry, EBX=heavy, ESI=TARGET) & 0xFF, expected, kind)
            self.assertEqual((w.reg("EBX"), w.reg("ESI"), w.reg("ESP")), (heavy, TARGET, STACK+0x8000))
        self.assertEqual((w.get(NATION+sd.FUNDS), w.get(self.used)), (funds-3*sd.MISSILE_COST, 1))
        self.assertEqual([h[0] for h in hits], [NEAR]*3)                                            # each one blasts
        w.put(heavy+subs.SHOT_KIND, subs.HEAVY_SSM); w.owned = {tree.SSN, tree.SSBN}
        self.assertEqual(self.call(entry, EBX=heavy, ESI=TARGET) & 0xFF, 0)                          # no warhead research
        w.owned = {tree.NUCLEAR_SHELLS[0]}; w.put(w.doctrine+4, sd.TORPEDO)
        self.assertEqual(self.call(entry, EBX=heavy, ESI=TARGET) & 0xFF, 0)                          # not chosen

    def test_an_ssn_torpedo_hit_is_nuclear_once(self):
        w = self.world
        hits = self.battle()
        site = INFO["sites"]["torpedo"]["address"]
        w.put(SHOT+subs.SHOT_NAME, self.string(TEXT, "SSL S-2 SSN")); w.put(SHOT+subs.SHOT_NATION, 3+2)
        w.put(TARGET+0xA55, 0x66)
        funds = w.get(NATION+sd.FUNDS)
        for expected in (2, 2):                                                    # the same torpedo again: nothing more
            for reg, value in dict(EBX=SHOT, ESI=TARGET, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
            w.vm.emu_start(site, site+6, count=20000)
            self.assertEqual((w.reg("EAX"), w.reg("EBX"), w.reg("ESI"), w.reg("ESP"), len(hits)), (0x66, SHOT, TARGET, STACK+0x8000, expected))
        self.assertEqual([(h[0], h[3][7], h[3][4]) for h in hits], [(TARGET, subs.NUCLEAR, 3), (NEAR, subs.BLAST_CALIBRE, 3)])
        self.assertEqual((w.get(NATION+sd.FUNDS), w.get(self.used)), (funds-sd.TORPEDO_COST, 1))


if __name__ == "__main__": unittest.main(verbosity=2)

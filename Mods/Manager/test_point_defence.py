"""Point defence (SeaRAM, gun-missile CIWS, RAM launchers, fire-control channels), executed on the native designer,
topside, weight and battle code with the whole modern-research build."""
import unittest
from test_modern_railgun import (World, SHIP, SHIP2, FORM, NATION, DATA, STACK, STOP, CELL, ERRORS, SPIN_VMT, LABEL_VMT,
                                 CHECKBOX, UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESI, UC_X86_REG_EBP)
import modern_extension as extension
import modern_railgun as railgun
import modern_tree as tree
import point_defence as pd

DESIGN_DATA, FIGHT_DATA = extension.CLASSES["design"][1], extension.CLASSES["fighting"][1]
BOX, MISSILE, FRAME, MAIN = DATA+0x11000, DATA+0xB000, STACK+0xA000, DATA+0xB800


def bits(searam=0, gm=0, spare=0, lasers=0, ram=False):
    return (searam << extension.SEARAM_SHIFT | gm << extension.GUN_MISSILE_SHIFT | spare << extension.SPARE_SHIFT
            | lasers | (extension.RAM_BIT if ram else 0))


def routine(world, address, **registers):   # call a routine that returns to STOP
    sp = STACK+0x8000; world.put(sp, STOP); world.vm.mem_write(STOP, b"\xc3")
    world.vm.reg_write(UC_X86_REG_ESP, sp)
    for name, value in registers.items(): world.vm.reg_write(globals()["UC_X86_REG_"+name], value)
    world.vm.emu_start(address, STOP, count=300000)
    return world.reg("EAX")


class DesignerTests(unittest.TestCase):
    def test_mount_boxes_need_research_and_are_stored_on_both_designs(self):
        for kind, m in pd.MOUNTS.items():
            for owned, requested, stored in (((), 2, 0), ((m["research"],), 2, 2), ((m["research"],), 20, m["mask"])):
                world = World(owned); world.design(); world.design(ship=SHIP2)
                world.guard(SHIP, 0x105); world.guard(SHIP2)                # other bits must survive
                world.spin[BOX] = requested
                world.call(world.pd[kind+"_change"], FORM, BOX)
                for ship in (SHIP, SHIP2):
                    self.assertEqual(world.get(ship+DESIGN_DATA) >> m["shift"] & m["mask"], stored, (kind, owned, requested))
                self.assertEqual(world.get(SHIP+DESIGN_DATA) & 0xFFFF, 0x105)
                self.assertEqual(bool([e for e in world.log if e[0] == "message"]), not owned)
                if owned: self.assertIn("refresh", [e[0] for e in world.log])

    def test_spare_missiles_need_mounts(self):
        for data, requested, stored in ((bits(), 2, 0), (bits(searam=1), 2, 2), (bits(gm=1), 9, pd.SPARE_MAX)):
            world = World(()); world.design(); world.guard(SHIP, data); world.spin[BOX] = requested
            world.call(world.pd["spare_change"], FORM, BOX)
            self.assertEqual(world.get(SHIP+DESIGN_DATA) >> extension.SPARE_SHIFT & 3, stored, hex(data))
            self.assertEqual(bool([e for e in world.log if e[0] == "message"]), not stored)

    def test_ram_box_needs_research_and_unticks(self):
        for owned, ticked, data, expected in (((), 1, 0, 0), ((tree.RAM,), 1, 0, extension.RAM_BIT),
                                               ((tree.RAM,), 0, extension.RAM_BIT, 0), ((), 0, extension.RAM_BIT, 0)):
            world = World(owned); world.design(); world.design(ship=SHIP2); world.guard(SHIP, data | 7); world.guard(SHIP2, data)
            world.put(BOX, CHECKBOX); world.checked[BOX] = ticked
            world.call(world.pd["ram_change"], FORM, BOX)
            self.assertEqual((world.get(SHIP+DESIGN_DATA), world.get(SHIP2+DESIGN_DATA)), (expected | 7, expected), (owned, ticked))

    def test_sync_mirrors_the_design_silently_and_enables_by_research_or_value(self):
        world = World((tree.SEARAM,)); world.design(); world.guard(SHIP, bits(searam=2, gm=0))
        world.call(world.pd["sync"], FORM)
        made = {world.get(e[1]+0xC): e[1] for e in world.log if e[0] == "spin"}
        searam = next(obj for obj in made.values() if world.get(obj+0xC) == pd.MAGIC["searam"])
        self.assertIn(("spin", searam, 2, 0), world.log)                         # OnChange cleared while setting
        self.assertEqual(world.get(searam+0x2E0), world.pd["searam_change"])
        self.assertEqual(world.get(searam+0x30C), 3)                              # MaxValue
        enabled = {world.get(e[1]+0xC): e[2] for e in world.log if e[0] == "enabled"}
        self.assertEqual((enabled[pd.MAGIC["searam"]], enabled[pd.MAGIC["gun_missile"]], enabled[pd.MAGIC["spare"]],
                          enabled[pd.MAGIC["ram"]]), (1, 0, 1, 0))                # spares: the design has mounts
        texts = [e[2] for e in world.log if e[0] == "text"]
        for caption in ("SeaRAM", "Gun-missile CIWS", "Spare missiles", "RAM launchers"): self.assertIn(caption, texts)

    def test_readout_counts_systems_channels_and_missiles(self):
        for owned, radar, directors, expected in (
                ({tree.PD_MAGAZINES[0]}, 6, 1, "Point defence: 4 systems / 4 channels.   Missiles: SeaRAM 44, gun-missile 64, ATT 8"),
                (set(), 0, 0, "Point defence: 4 systems / 2 channels - too few channels.   Missiles: SeaRAM 33, gun-missile 48, ATT 8"),
                (set(), 7, 5, "Point defence: 4 systems / 6 channels.   Missiles: SeaRAM 33, gun-missile 48, ATT 8")):
            world = World(owned); world.design()
            world.guard(SHIP, bits(searam=2, gm=1, spare=1, lasers=3) | 2 << extension.ATT_SHIFT)   # two ATT launchers
            world.put(SHIP+0x9F3, 1, 1); world.put(SHIP+0x9E6, 2)               # a gun CIWS
            world.put(SHIP+0xA0B, radar); world.put(SHIP+0x9EE, directors)
            world.call(world.pd["sync"], FORM)
            readout = [e for e in world.log if e[0] == "text" and world.get(e[1]+0xC) == pd.MAGIC["readout"]]
            self.assertEqual(readout[-1][2], expected, (owned, radar, directors))


class AttDesignerTests(unittest.TestCase):
    def test_att_box_needs_research_and_weighs_costs_and_loads_the_topside(self):
        for owned, requested, stored in (((), 2, 0), ((tree.ANTI_TORPEDO,), 2, 2), ((tree.ANTI_TORPEDO,), 9, 3)):
            world = World(owned); world.design(); world.design(ship=SHIP2); world.guard(SHIP, 0x105); world.guard(SHIP2)
            world.spin[BOX] = requested
            world.call(world.pd["att_change"], FORM, BOX)
            for ship in (SHIP, SHIP2):
                self.assertEqual(world.get(ship+DESIGN_DATA) >> extension.ATT_SHIFT & 3, stored, (owned, requested))
            self.assertEqual(world.get(SHIP+DESIGN_DATA) & 0xFFF, 0x105)
        world = World(); world.design(); world.guard(SHIP, 2 << extension.ATT_SHIFT); world.put(CELL, SHIP)
        self.assertTrue(world.run(0x93C25F, 0x93C267, EBX=CELL, EAX=800))
        self.assertEqual((world.get(SHIP+0xAA4), world.get(SHIP+0xA8C)), (2*pd.ATT["tons"], 2*pd.ATT["cost"]))
        world.stubs[pd.NATIVE["topside_points"]] = lambda: 99
        world.put(FRAME-4, SHIP); world.put(FRAME-0xC, 50); world.put(FRAME-0x10, 0)
        self.assertTrue(world.run(pd.TOPSIDE_SITE, 0x94B6BF, EBP=FRAME))
        self.assertEqual(world.get(FRAME-0xC), 50+2*pd.ATT["topside"])


class WeightTests(unittest.TestCase):
    def test_mounts_spares_and_ram_launchers_weigh_and_cost(self):
        listing, items = DATA+0xD000, DATA+0xD100
        mounts = ((3, 10), (3, 15), (4, 20))                                       # (MountType, weight): light SAMs, an SSM
        for data, tons, cost in ((bits(searam=2, gm=3, spare=2, lasers=1, ram=True), 20+16+45+12+30+5, 100+300+600+400+50),
                                 (bits(searam=1), 8, 150), (bits(ram=True), 5, 50), (bits(spare=3), 0, 0)):
            world = World(); world.design(); world.guard(SHIP, data); world.put(CELL, SHIP)
            world.put(SHIP+0x9E, listing); world.put(listing+4, items); world.put(listing+8, len(mounts))
            for i, (kind, weight) in enumerate(mounts):
                mount = DATA+0xD200+0x20*i; world.put(items+4*i, mount); world.put(mount+4, 1)
                world.put(mount+0xE, kind, 1); world.put(mount+0xA, weight)
            self.assertTrue(world.run(0x93C25F, 0x93C267, EBX=CELL, EAX=800))
            self.assertEqual((world.get(SHIP+0xAA4), world.get(SHIP+0xA8C)), (tons, cost), hex(data))

    def test_a_ski_jump_weighs_a_share_of_the_displacement_and_costs_with_the_armament(self):
        import modern_carrier as carrier
        for ski, tons, weight in ((True, 30000, 450), (True, 5000, carrier.SKI_MIN_TONS), (False, 30000, 0)):
            world = World(); world.design(); world.guard(SHIP, 0); world.put(CELL, SHIP)
            world.put(SHIP+0x2C, tons); world.put(SHIP+0x9DF, carrier.SKI_BIT if ski else 0, 1)
            self.assertTrue(world.run(0x93C25F, 0x93C267, EBX=CELL, EAX=800))
            self.assertEqual((world.get(SHIP+0xAA4), world.get(SHIP+0xA8C)), (weight, weight*carrier.SKI_COST_PER_TON),
                             (ski, tons))

    def test_topside_points_and_their_report_line(self):
        world = World()
        world.stubs[pd.NATIVE["topside_points"]] = lambda: 99
        world.stubs[pd.NATIVE["cat3"]] = lambda: (world.put(world.reg("EAX"), world.string(
            world.text(world.reg("EDX"))+world.text(world.reg("ECX")))), 0)[1]
        for data, report, load, lines in ((bits(searam=2, gm=1, lasers=3), ERRORS, 75, ["Point defence: 25"]),
                                          (bits(searam=2, gm=1, lasers=3), 0, 75, []), (bits(), ERRORS, 50, [])):
            world.log.clear(); world.design(); world.guard(SHIP, data)
            world.put(FRAME-4, SHIP); world.put(FRAME-0xC, 50); world.put(FRAME-0x10, report)
            self.assertTrue(world.run(pd.TOPSIDE_SITE, 0x94B6BF, EBP=FRAME))
            self.assertEqual((world.get(FRAME-0xC), world.reg("EAX")), (load, 99), hex(data))
            self.assertEqual([e[1] for e in world.log if e[0] == "error"], lines)


class BattleTests(unittest.TestCase):
    def world(self, data, owned=(), damage=10, radar=0, down=0, directors=0, handled=0, fired=0):
        world = World(owned)
        world.vm.mem_write(SHIP, bytes(FIGHT_DATA+12))
        world.guard(SHIP, data, kind="fighting"); world.put(SHIP+FIGHT_DATA+8, fired)
        for field, value in ((0x14, 3), (0xA0B, radar), (0xA0F, down), (0x9EE, directors), (0xE01, handled)):
            world.put(SHIP+field, value)
        world.put(world.railgun_info["main"], MAIN); world.put(MAIN, DATA+0xB900)
        world.stubs[world.railgun_info["nation"]] = lambda: NATION if world.reg("EDX") == 3 else 0
        world.damage, world.ranges = damage, []
        weather, sea = DATA+0xC000, DATA+0xC010                                    # clear and calm (lasers)
        world.put(world.railgun_info["precipitation"], weather); world.put(weather, railgun.CLEAR_WEATHER, 1)
        world.put(world.railgun_info["sea"], sea); world.put(sea, 1)
        world.stubs[world.railgun_info["random"]] = lambda: (world.ranges.append(world.reg("EAX")), world.rolls.pop(0))[1]
        return world

    def fight(self, world, rolls, outcome):
        world.rolls = list(rolls)
        stop = dict(shot=world.railgun_info["ciws_shot"], ciws=world.railgun_info["ciws_step"],
                    skipped=world.railgun_info["ciws_fail"])[outcome]
        self.assertTrue(world.run(0x8C1584, stop, ESI=SHIP, EBX=MISSILE, EBP=FRAME), (rolls, outcome))
        self.assertEqual(world.rolls, [], "every roll used")

    def shots(self, world): return [e[1] for e in world.log if e[0] == "shot"]
    def fired(self, world): return world.get(SHIP+FIGHT_DATA+8, 2), world.get(SHIP+FIGHT_DATA+10, 2)

    def test_channels_come_from_radar_and_directors(self):
        for radar, down, directors, channels in ((0, 0, 0, 2), (6, 0, 0, 3), (7, 0, 0, 4), (7, tree.EMCON, 0, 2),
                                                 (5, 0, 1, 3), (0, 0, 3, 4), (7, 0, 2, 6)):
            world = self.world(0, radar=radar, down=down, directors=directors)
            self.fight(world, [], "ciws")
            self.assertEqual(world.get(world.pd["channel"], 1), channels, (radar, down, directors))

    def test_searam_fires_two_missiles_with_chances_by_mounts_and_saturation(self):
        for mounts, handled, roll, kill in ((1, 0, 39, True), (1, 0, 40, False), (3, 0, 59, True), (3, 0, 60, False)):
            world = self.world(bits(searam=mounts), handled=handled)
            self.fight(world, [99, roll], "shot" if kill else "ciws")
            self.assertEqual(self.shots(world), [" Incoming missile shot down by SeaRAM."] if kill else [])
            self.assertEqual(self.fired(world), (2, 0))
            self.assertEqual(world.get(world.pd["channel"], 1), 1)
        world = self.world(bits(searam=1), handled=2)
        self.fight(world, [99, 39], "shot")
        self.assertEqual(world.ranges, [100, 160])                                    # random(100+30 per missile met)

    def test_magazines_run_dry_spares_and_research_add_missiles(self):
        load = pd.MOUNTS["searam"]["missiles"]
        world = self.world(bits(searam=1), fired=load)                                # all 11 fired: holds fire
        self.fight(world, [99], "ciws")
        self.assertEqual((self.fired(world), world.get(world.pd["channel"], 1)), ((load, 0), 2))   # no channel taken
        world = self.world(bits(searam=1), fired=load-1)                              # the last one
        self.fight(world, [99, 99], "ciws"); self.assertEqual(self.fired(world), (load, 0))
        for spare, owned, total in ((1, (), 16), (0, (tree.PD_MAGAZINES[0],), 16), (3, (tree.PD_MAGAZINES[0],), 33)):
            world = self.world(bits(searam=1, spare=spare), owned, fired=total-2)
            self.fight(world, [99, 99], "ciws"); self.assertEqual(self.fired(world), (total, 0), (spare, owned))

    def test_gun_missile_fires_missiles_then_guns_and_guns_when_dry(self):
        for rolls, fired, shot in (([99, 34], 0, " Incoming missile shot down by gun-missile CIWS."),
                                   ([99, 35, 19], 0, " Incoming missile shot down by gun-missile CIWS guns."),
                                   ([99, 35, 20], 0, None),
                                   ([99, 19], 32, " Incoming missile shot down by gun-missile CIWS guns.")):
            world = self.world(bits(gm=1), fired=fired << 16)
            self.fight(world, rolls, "shot" if shot else "ciws")
            self.assertEqual(self.shots(world), [shot] if shot else [], rolls)
            self.assertEqual(self.fired(world), (0, 32 if fired else 2))
            self.assertEqual(world.get(world.pd["channel"], 1), 1)

    def test_layers_past_the_channels_hold_fire_lasers_and_gun_ciws_included(self):
        # SeaRAM and gun-missile take both channels: the lasers roll for damage only, the gun CIWS is skipped.
        world = self.world(bits(searam=1, gm=1, lasers=4))
        self.fight(world, [99, 40, 99, 35, 20, 99], "skipped")
        self.assertEqual(self.shots(world), [])
        world = self.world(bits(searam=1, gm=1, lasers=4), radar=6)                   # a third channel: lasers fire
        self.fight(world, [99, 40, 99, 35, 20, 99, 59], "shot")
        self.assertEqual(self.shots(world), [" Incoming missile shot down by laser."])
        world = self.world(bits(searam=1, lasers=4))                                  # one each: the gun CIWS is skipped
        self.fight(world, [99, 40, 99, 60], "skipped")

    def test_a_layer_knocked_out_with_the_superstructure_takes_no_channel(self):
        world = self.world(bits(searam=1), damage=50)
        self.fight(world, [40], "ciws")
        self.assertEqual((self.fired(world), world.get(world.pd["channel"], 1)), ((0, 0), 2))


class RamTests(unittest.TestCase):
    def test_ram_light_sams_count_half_the_missiles_met(self):
        for kind, data, handled, counted in ((pd.LIGHT_SAM, bits(ram=True), 5, 2), (2, bits(ram=True), 5, 5),
                                             (pd.LIGHT_SAM, bits(), 5, 5)):
            world = World(); world.design(); world.guard(SHIP, data); world.put(SHIP+0xE01, handled)
            world.put(world.pd["ram_kind"], kind); world.put(FRAME+8, 31)             # a heavy SSM: no flight penalty
            self.assertTrue(world.run(0x91AE38, 0x91AE3E, ESI=SHIP, EBP=FRAME, EAX=0x11))
            self.assertEqual((world.reg("ECX"), world.reg("EAX")), (counted, 0x11), (kind, hex(data)))

    def test_the_sam_kind_fired_is_noted(self):
        world = World(); world.design(); world.put(world.pd["ram_kind"], 0)
        world.run(0x91ADF1, 0x91ADF7, ESI=SHIP, EBX=pd.LIGHT_SAM)
        self.assertEqual(world.get(world.pd["ram_kind"]), pd.LIGHT_SAM)


if __name__ == "__main__":
    unittest.main()

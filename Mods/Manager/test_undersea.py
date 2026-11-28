"""Undersea warfare (homing torpedoes, anti-torpedo torpedoes, moving submarines), executed on the native battle
code with the whole modern-research build."""
import struct
import unittest
from test_modern_railgun import World, SHIP, NATION, DATA, STACK
import modern_extension as extension
import modern_tree as tree
import undersea as sea
import nuclear_strike as strike

FIGHT = extension.CLASSES["fighting"][1]
TORP, TARGET, SUB, FRAME, MAIN, FORM, LOG = DATA+0xB000, DATA+0xC000, DATA+0xD000, STACK+0xA000, DATA+0xB800, DATA+0xE000, DATA+0xE800
N = sea.NATIVE


def fighting(world, ship, data=0, side=0):
    world.vm.mem_write(ship, bytes(FIGHT+16)); world.guard(ship, data, kind="fighting")
    world.put(ship+0xA55, side); world.put(ship+0x14, 3)


def battle(world):
    world.put(world.railgun_info["main"], MAIN); world.put(MAIN, DATA+0xB900)
    world.stubs[world.railgun_info["nation"]] = lambda: NATION if world.reg("EDX") in (0, 3) else 0


def sonar_flag(world):   # nuclear_strike's data page holds the player's sonar mode
    return world.named["Undersea: homing"]-0x1B000+0x15000+strike.SONAR


def tables(world):
    record = world.named["Modern combat: torpedo record"]
    return record+0xC, record+4, world.named["Undersea: targets"]          # torpedoes, cursor, targets


class HomingTests(unittest.TestCase):
    def move(self, world, torpedo, kind=18, afloat=1):
        world.vm.mem_write(torpedo, bytes(0x50)); world.put(torpedo+0x28, kind); world.put(torpedo+0x10, 5)
        world.stubs[N["afloat"]] = lambda: afloat
        world.stubs[N["bearing"]] = lambda: (world.note("bearing", world.reg("EAX"), world.reg("EDX")), 123)[1]
        self.assertTrue(world.run(0x925BE8, N["straight"], EAX=torpedo, EBP=FRAME))
        return world.get(torpedo+0x10)

    def test_a_recorded_torpedo_steers_at_its_afloat_target(self):
        world = World(); torpedoes, cursor, targets = tables(world)
        world.put(torpedoes+8, TORP); world.put(targets+8, TARGET)
        self.assertEqual(self.move(world, TORP), 123)
        self.assertIn(("bearing", TORP+4, TARGET+0xA1C), world.log)
        self.assertEqual(self.move(world, TORP, afloat=0), 5)                  # sunk: runs straight
        self.assertEqual(self.move(world, TORP+0x100), 5)                      # not guided: straight
        world.put(targets+8, 0)
        self.assertEqual(self.move(world, TORP), 5)                            # no target recorded

    def test_missiles_keep_the_native_aim(self):
        world = World()
        world.vm.mem_write(TORP, bytes(0x50)); world.put(TORP+0x28, 31); world.put(TORP+0x34, 0)
        self.assertTrue(world.run(0x925BE8, N["straight"], EAX=TORP, EBP=FRAME))   # no target: straight, natively


class LaunchTests(unittest.TestCase):
    def test_a_submarines_torpedo_is_recorded_with_its_target_when_its_side_has_the_research(self):
        for owned, recorded in (({tree.GUIDED_TORPEDOES[0]}, True), (set(), False)):
            world = World(owned); battle(world); torpedoes, cursor, targets = tables(world)
            world.vm.mem_write(SUB, bytes(0x50)); world.put(SUB+8, 0); world.put(SUB+0x3C, 7)
            world.vm.mem_write(TORP, bytes(0x50)); world.put(TORP+0x14, 7); world.put(FRAME-4, TARGET)
            self.assertTrue(world.run(0x8766B9, N["sub_back"], EBX=TORP, ESI=SUB, EBP=FRAME))
            self.assertEqual((world.get(torpedoes), world.get(targets)), (TORP, TARGET) if recorded else (0, 0))
            self.assertEqual(world.reg("EAX"), 7)                              # the replayed MOV/CMP
            self.assertTrue(world.reg("EFLAGS") & 0x40)                        # ZF: speeds equal

    def test_a_ships_torpedo_target_is_recorded_by_the_launch_hook(self):
        world = World({tree.GUIDED_TORPEDOES[0]}); battle(world); torpedoes, cursor, targets = tables(world)
        fighting(world, SHIP); world.put(FRAME-4, TARGET)
        site = next(p for p in world_plans(world) if p["label"] == "Modern combat: torpedo_launch")
        self.assertTrue(world.run(site["address"], 0x876520, EBX=TORP, ESI=SHIP, EBP=FRAME))
        self.assertEqual((world.get(torpedoes), world.get(targets)), (TORP, TARGET))


class AntiTorpedoTests(unittest.TestCase):
    def world(self, launchers, side=1, fired=0, rolls=()):
        world = World(); battle(world); fighting(world, SHIP, launchers << extension.ATT_SHIFT, side=0)
        world.put(SHIP+FIGHT+extension.BATTLE_FLAGS, fired)
        world.vm.mem_write(TORP, bytes(0x50)); world.put(TORP+0x3E, side); world.put(TORP+0x1C, 5000)
        world.put(FRAME-0xC, FORM); world.put(FORM+0x7F8, LOG); world.put(LOG, LOG+0x100); world.put(LOG+0x140, LOG+0x200)
        world.stubs[LOG+0x200] = lambda: world.note("log", world.text(world.reg("EDX")), world.reg("ECX"))
        world.stubs[N["name"]] = lambda: (world.put(world.reg("EDX"), world.string("Kirov")), 0)[1]
        world.rolls = list(rolls)
        return world

    def engage(self, world, yards=1000):
        world.put(FRAME-0x18, yards); world.put(FRAME-0x14, 60); world.vm.reg_write(sea_reg("ESP"), STACK+0x8000)
        gone, back = 0x8C29C8, 0x8C2A3A
        site = next(p for p in world_plans(world) if p["label"] == "Modern combat: torpedo_hit")
        hook = world.vm.hook_add(1 << 2, lambda vm, a, s, u: vm.emu_stop() if a in (gone, back) else None)   # UC_HOOK_CODE
        try: world.vm.emu_start(site["address"], 0, count=300000)
        finally: world.vm.hook_del(hook)
        world.vm.reg_write(sea_reg("ESI"), SHIP)
        return world.reg("EIP") == gone

    def test_an_att_destroys_an_enemy_torpedo_within_range_with_chance_by_launchers(self):
        for launchers, roll, destroyed in ((1, 39, True), (1, 40, False), (3, 59, True), (3, 60, False)):
            world = self.world(launchers, rolls=[roll])
            world.vm.reg_write(sea_reg("ESI"), SHIP); world.vm.reg_write(sea_reg("EBX"), TORP); world.vm.reg_write(sea_reg("EBP"), FRAME)
            self.assertEqual(self.engage(world), destroyed, (launchers, roll))
            self.assertEqual(world.get(SHIP+FIGHT+extension.BATTLE_FLAGS, 1), 1)          # one fired either way
            logs = [e for e in world.log if e[0] == "log"]
            self.assertEqual(logs, [("log", "7Kirov"+sea.TEXT["att"], SHIP)] if destroyed else [])

    def test_once_a_torpedo_only_in_range_only_enemies_only_while_atts_last(self):
        world = self.world(1, rolls=[40]); self.prime(world)
        self.assertFalse(self.engage(world)); self.assertFalse(self.engage(world))      # second look: no roll
        self.assertEqual(world.get(SHIP+FIGHT+extension.BATTLE_FLAGS, 1), 1)
        world.put(TORP+0x1C, 6000); world.rolls = [10]; self.assertTrue(self.engage(world))   # a new torpedo there
        for options, yards in ((dict(side=0), 1000), (dict(side=2), 1000), (dict(), 1600), (dict(fired=4), 1000),
                               (dict(launchers=0), 1000)):
            settings = dict(launchers=1); settings.update(options)
            world = self.world(**settings); self.prime(world)
            self.assertFalse(self.engage(world, yards), options)
            self.assertEqual(world.rolls, [])
        world = self.world(1, side=3, rolls=[0]); self.prime(world)                       # a side-1 submarine's
        self.assertTrue(self.engage(world))

    def prime(self, world):
        for name, value in (("ESI", SHIP), ("EBX", TORP), ("EBP", FRAME)): world.vm.reg_write(sea_reg(name), value)


class SubmarineTests(unittest.TestCase):
    def world(self, minute, distance, name="U-47", torpedo_range=6000, state=0, player_side=0, active=0):
        world = World(); battle(world)
        world.put(N["player_side"], DATA+0xF030); world.put(DATA+0xF030, player_side); world.put(sonar_flag(world), active, 1)
        clock, subs, ships, sub_list, ship_list = DATA+0xF000, DATA+0xF010, DATA+0xF020, DATA+0xF100, DATA+0xF200
        world.put(N["minute"], clock); world.put(clock, minute)
        world.put(N["submarines"], subs); world.put(subs, sub_list)
        world.put(sub_list+4, sub_list+0x40); world.put(sub_list+8, 1); world.put(sub_list+0x40, SUB)
        world.put(N["ships"], ships); world.put(ships, ship_list)
        world.put(ship_list+4, ship_list+0x40); world.put(ship_list+8, 2)
        world.put(ship_list+0x40, SHIP); world.put(ship_list+0x44, TARGET)
        fighting(world, SHIP, side=0); fighting(world, TARGET, side=1)
        world.vm.mem_write(SUB, bytes(0x50)); world.put(SUB+8, 0); world.put(SUB+0x10, state); world.put(SUB+0x40, torpedo_range)
        world.put(SUB+4, world.string(name))
        world.stubs[N["afloat"]] = lambda: 1
        world.stubs[N["distance"]] = lambda: distance if world.reg("EAX") == TARGET else 999999
        world.stubs[N["bearing"]] = lambda: 90

        def units():
            world.pop_extra = 12; return 777
        world.stubs[N["globe_units"]] = units

        def move():
            result = world.get(world.reg("ESP")+4); world.pop_extra = 4
            world.note("move", world.reg("EDX"), world.reg("ECX"))
            world.put(result, 0x111); world.put(result+4, 0x222); world.put(result+8, 0x333); return 0
        world.stubs[N["move"]] = move
        return world

    def run_pass(self, world):
        self.assertTrue(world.run(0x89F87A, N["pass_back"], EBP=FRAME))

    def test_a_submarine_closes_on_the_nearest_enemy_once_a_battle_minute(self):
        world = self.world(100, 10000); self.run_pass(world)                   # first call: the clock starts
        self.assertEqual([e for e in world.log if e[0] == "move"], [])
        world.put(DATA+0xF000, 102); self.run_pass(world)                      # two minutes at 8 knots
        self.assertEqual([e for e in world.log if e[0] == "move"], [("move", 90, 777)])
        self.assertEqual([world.get(SUB+0x14+4*i) for i in range(3)], [0x111, 0x222, 0x333])
        self.assertEqual(world.reg("EAX"), world.get(N["submarines"]))         # the native pass's MOV

    def test_it_holds_inside_its_torpedo_range_and_out_of_the_fight(self):
        for options in (dict(distance=3900), dict(distance=10000, state=0x7FFFFFFF)):
            world = self.world(100, **options); self.run_pass(world)
            world.put(DATA+0xF000, 101); self.run_pass(world)
            self.assertEqual([e for e in world.log if e[0] == "move"], [], options)


class HearingTests(unittest.TestCase):
    def test_submarines_hear_ships_within_reach_and_pinging_player_ships_twice_as_far(self):
        for distance, player_side, active, moves in ((11000, 0, 0, True), (13000, 0, 0, False), (13000, 1, 1, True),
                                                     (23000, 1, 1, True), (25000, 1, 1, False), (13000, 0, 1, False),
                                                     (13000, 1, 0, False)):
            world = SubmarineTests.world(self, 100, distance, player_side=player_side, active=active)
            SubmarineTests.run_pass(self, world); world.put(DATA+0xF000, 101); SubmarineTests.run_pass(self, world)
            self.assertEqual(bool([e for e in world.log if e[0] == "move"]), moves, (distance, player_side, active))


class SonarTests(unittest.TestCase):
    PLAYER, ENEMY = 3, 0   # nation indexes; battle sides 1 (the player's) and 0

    def world(self, distance, quiet=(), listen=(), active=0, kind=18):
        world = World(); battle(world)
        nations = {self.PLAYER: NATION, self.ENEMY: NATION+0x400}
        owned = {NATION: set(listen), NATION+0x400: set(quiet)}
        world.stubs[world.railgun_info["nation"]] = lambda: nations.get(world.reg("EDX"), 0)
        world.stubs[world.railgun_info["has_research"]] = lambda: int(world.reg("EDX") in owned.get(world.reg("EAX"), ()))
        fighting(world, SHIP, side=1); world.put(SHIP+0x14, self.PLAYER)
        ships, ship_list = DATA+0xF020, DATA+0xF200
        world.put(N["ships"], ships); world.put(ships, ship_list)
        world.put(ship_list+4, ship_list+0x40); world.put(ship_list+8, 1); world.put(ship_list+0x40, SHIP)
        world.put(N["player_side"], DATA+0xF030); world.put(DATA+0xF030, 1); world.put(sonar_flag(world), active, 1)
        world.vm.mem_write(TORP, bytes(0x50)); world.put(TORP+0x28, kind); world.put(TORP+0x3E, 0)
        world.stubs[N["afloat"]] = lambda: 1
        world.stubs[N["distance"]] = lambda: distance if world.reg("EAX") == SHIP else 999999
        return world

    def drawn(self, world):
        hook = world.vm.hook_add(1 << 2, lambda vm, a, s, u: vm.emu_stop() if a in (N["draw"], N["hide"]) else None)
        try:
            world.vm.reg_write(sea_reg("ESP"), STACK+0x8000)
            for name, value in (("EBX", TORP), ("EDI", DATA+0xE000)): world.vm.reg_write(sea_reg(name), value)
            world.vm.emu_start(0x89DDC1, 0, count=300000)
        finally: world.vm.hook_del(hook)
        self.assertEqual((world.reg("EBX"), world.reg("EDI")), (TORP, DATA+0xE000))
        return world.reg("EIP") == N["draw"]

    def test_enemy_torpedoes_are_drawn_once_seen_or_heard(self):
        for options, distance, seen in ((dict(), 1400, True), (dict(), 1600, False),                  # a steam wake
                                        (dict(quiet={916}), 1400, False), (dict(quiet={929}), 300, True),
                                        (dict(quiet={916}, listen={1107}), 900, True),             # hydrophones
                                        (dict(quiet={916}, listen={1107, 1113}), 1900, True),
                                        (dict(quiet={916}, listen={1113}), 2100, False),
                                        (dict(quiet={916}, listen={1113}, active=1), 2900, True),   # ACTIVE: +50%
                                        (dict(listen={1122, 1140}), 3900, True),
                                        (dict(kind=31), 999999, True)):                             # a missile
            world = self.world(distance, **options)
            self.assertEqual(self.drawn(world), seen, (options, distance))


def sea_reg(name):
    import unicorn.x86_const as x86
    return getattr(x86, "UC_X86_REG_"+name)


def world_plans(world):
    if not hasattr(world, "_plans"):
        import modern_research as modern
        from test_modern_railgun import BLOB, CODE
        world._details = modern.discover(BLOB, 0x301000)
        _, world._plans, _ = modern.build(CODE, world._details)
    return world._plans


def world_details(world):
    world_plans(world)
    return world._details["undersea"]


if __name__ == "__main__":
    unittest.main()

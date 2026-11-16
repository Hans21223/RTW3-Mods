"""AI designs and VLS cells: the pass after AIDesignShip's second weight adjustment, on the start's classes and
after AIDesignShip's hull trim (destroyers grow), run against stand-in game functions."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI,
                               UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP)
import vls_cells as vls
import modern_tree as tree

CODE, STUBS, DATA, STACK = 0x100000, 0x200000, 0x300000, 0x400000
PREDICATE, SITE = CODE+0x1000, STUBS+0x8000
DESIGN, NATION, LIST, ITEMS, MOUNTS, YEAR, SCRATCH, LIMIT, FRAME = (
    DATA, DATA+0x2000, DATA+0x3000, DATA+0x3100, DATA+0x4000, DATA+0x5000, DATA+0x6000, DATA+0x7000, DATA+0x8000)
MAIN, MOUNT_VMT, SAM, SSM, CL, NATION_INDEX = 0x77, 0x9339D4, 2, 5, 4, 3   # medium SAM, medium SSM
ALL = tuple(tree.VLS_CELLS.values())
DENSE = tree.VLS_DENSE[0][0]
NAMES = ("adjust_weights", "has_research", "centreline", "missile_allowed", "recalculate", "rescale", "get_nation",
         "monthly_balance", "modified_budget")
CA, CV = 3, 5
SAVED = (UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP)
REPLACED = "8b45e880b8bf0b000000"           # what the hook after the hull trim replaces
TWIN = [(SAM, 2, 10, 1), (SSM, 2, 3, 1)]    # a destroyer template's launchers


class AIVLSTests(unittest.TestCase):
    def design(self, launchers, *, tons=9000, spare=500, year=1985, research=ALL, banned=(), nation=NATION,
               kind=CL, mode=vls.CONVERT, dock=20000, limit=16000, cell=1, start=False, after_trim=False,
               knot=300, plate=200, budget=120000, balance=0, funds=50000, wing=100, plane=20):
        """launchers: (MountType, tubes, reloads, centreline). Weight left = spare + half the tons a hull has
        grown - cell tons a missile - knot tons a knot above 32 - plate tons a half inch of belt and deck.
        Returns the mounts' (tubes, reloads)."""
        at = {name: STUBS+0x10*i for i, name in enumerate(NAMES)}
        info = dict(at, year=YEAR, mount_vmt=MOUNT_VMT, dd_limit=LIMIT)
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address in (CODE, STUBS, DATA, STACK): vm.mem_map(address, 0x10000)
        site = dict(address=SITE, original=REPLACED)
        if after_trim: code = vls.ai_grow(CODE, site, info, CODE+vls.PASS, SCRATCH)
        elif mode == vls.CONVERT: code = vls.ai_vls(CODE, site, info, PREDICATE, SCRATCH)
        else: code = vls.ai_hook(CODE, site, at["adjust_weights"], CODE+vls.PASS, SCRATCH, mode, start and at["rescale"])
        self.assertLessEqual(len(code), vls.PASS+0x7C0)
        vm.mem_write(CODE, code)
        if mode != vls.CONVERT or after_trim: vm.mem_write(CODE+vls.PASS, vls.ai_pass(CODE+vls.PASS, info, PREDICATE, SCRATCH))
        vm.mem_write(PREDICATE, vls.is_vls(PREDICATE, {}))
        put = lambda address, value, size=4: vm.mem_write(address, value.to_bytes(size, "little", signed=True))
        get = lambda address: struct.unpack("<i", vm.mem_read(address, 4))[0]
        mounts = [MOUNTS+0x40*i for i in range(len(launchers))]
        for mount, (missile, tubes, reloads, centreline) in zip(mounts, launchers):
            put(mount, MOUNT_VMT); put(mount+4, tubes); put(mount+0xE, missile, 1); put(mount+0xF, reloads)
            put(mount+0x20, centreline, 1)       # what the centreline stand-in reports
        weight_left = lambda: (spare+(get(DESIGN+0x2C)-tons)//2-cell*sum(get(m+4)*(1+get(m+0xF)) for m in mounts)
                               - knot*(get(DESIGN+vls.DESIGN_SPEED)-32)-plate*get(DESIGN+vls.BELT)
                               - plane*(get(DESIGN+vls.AIR)-wing))
        for address, value in ((DESIGN+0x2C, tons), (DESIGN+0x9E, LIST), (DESIGN+0x1C, NATION_INDEX), (LIST+4, ITEMS),
                               (LIST+8, len(mounts)), (NATION+vls.DOCK, dock), (YEAR, YEAR+4), (YEAR+4, year),
                               (LIMIT, limit), (FRAME-0x18, DESIGN), (SCRATCH+0x10, 0x5555),
                               (DESIGN+vls.DESIGN_SPEED, 32), (DESIGN+vls.SPEED, 32), (DESIGN+vls.AIR, wing),
                               (NATION+vls.FUNDS, funds)):
            put(address, value)
        put(DESIGN+vls.TYPE, kind, 1); put(DESIGN+vls.WEIGHT_LEFT, weight_left())
        for i, mount in enumerate(mounts): put(ITEMS+4*i, mount)
        flag = lambda value: 0xABCDEF00 | value          # only AL carries a Boolean
        self.redrawn = []
        stand_ins = {
            at["adjust_weights"]: (MAIN, lambda eax, edx, ecx: calls.append((edx, ecx))),
            at["has_research"]: (nation, lambda eax, edx, ecx: flag(edx in research)),
            at["centreline"]: (None, lambda eax, edx, ecx: flag(vm.mem_read(eax+0x20, 1)[0])),
            at["missile_allowed"]: (nation, lambda eax, edx, ecx: flag(edx not in banned)),
            at["recalculate"]: (DESIGN, lambda eax, edx, ecx: put(DESIGN+vls.WEIGHT_LEFT, weight_left())),
            at["rescale"]: (DESIGN, lambda eax, edx, ecx: self.redrawn.append(edx)),
            at["get_nation"]: (MAIN, lambda eax, edx, ecx: nation if edx == NATION_INDEX else 0),
            at["monthly_balance"]: (nation, lambda eax, edx, ecx: balance),
            at["modified_budget"]: (nation, lambda eax, edx, ecx: budget),
        }
        calls, wrong = [], []

        def stand_in(uc, address, size, data):
            if address not in stand_ins: return
            expected, body = stand_ins[address]
            eax, edx, ecx = (uc.reg_read(r) for r in (UC_X86_REG_EAX, UC_X86_REG_EDX, UC_X86_REG_ECX))
            if expected is not None and eax != expected: wrong.append((NAMES[(address-STUBS)//0x10], hex(eax)))
            result = body(eax, edx, ecx)
            sp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EAX, 0x5EED0000 if result is None else result & 0xFFFFFFFF)
            uc.reg_write(UC_X86_REG_ECX, 0xDEAD0001); uc.reg_write(UC_X86_REG_EDX, 0xDEAD0002)   # volatile
            uc.reg_write(UC_X86_REG_ESP, sp+4); uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(sp, 4))[0])
        vm.hook_add(UC_HOOK_CODE, stand_in, begin=STUBS, end=STUBS+0x1000)
        saved = dict(zip(SAVED, (0x11111111, 0x22222222, MAIN if after_trim else 0x33333333,
                                 FRAME if after_trim else 0x44444444, STACK+0xF000)))
        for reg, value in {**saved, UC_X86_REG_EAX: MAIN, UC_X86_REG_EDX: DESIGN, UC_X86_REG_ECX: nation}.items():
            vm.reg_write(reg, value)
        end = SITE+(len(REPLACED)//2 if after_trim else 5)
        vm.emu_start(CODE, end, count=400000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP), end)
        self.assertEqual({reg: vm.reg_read(reg) for reg in SAVED}, saved)
        if after_trim: self.assertEqual((calls, wrong, vm.reg_read(UC_X86_REG_EAX)), ([], [], DESIGN))   # the replaced code ran
        else: self.assertEqual((calls, wrong), ([(DESIGN, nation)], []))   # the native call still runs first
        self.assertEqual(get(DESIGN+vls.WEIGHT_LEFT), weight_left())  # recalculated after every change and undo
        self.tons = get(DESIGN+0x2C)
        self.assertEqual(get(DESIGN+vls.SPEED), get(DESIGN+vls.DESIGN_SPEED))
        self.fit = get(DESIGN+vls.SPEED), get(DESIGN+vls.BELT), get(DESIGN+vls.DECK)
        self.wing = get(DESIGN+vls.AIR)
        return [(get(m+4), get(m+0xF)) for m in mounts]

    def test_a_launcher_becomes_the_smallest_bank_that_holds_its_whole_load(self):
        self.assertEqual(self.design([(SSM, 2, 3, 1), (SAM, 1, 11, 1)]), [(8, 0), (16, 0)])

    def test_a_load_beyond_the_researched_sizes_gets_the_largest_one(self):
        twin = [(SSM, 2, 9, 1)]                                                  # 20 missiles
        self.assertEqual(self.design(twin, research=ALL[:1]), [(8, 0)])
        self.assertEqual(self.design(twin, research=ALL[:2]), [(16, 0)])
        self.assertEqual(self.design(twin), [(32, 0)])

    def test_cells_per_ton_count_existing_banks_and_dense_research(self):
        twins = [(SSM, 2, 3, 1), (SSM, 2, 3, 1)]
        self.assertEqual(self.design(twins, tons=1200), [(8, 0), (2, 3)])                       # 15 cells
        self.assertEqual(self.design(twins, tons=1200, research=ALL+(DENSE,)), [(8, 0), (8, 0)])   # 18 cells
        self.assertEqual(self.design([(SAM, 64, 0, 1), (SSM, 2, 3, 1)], tons=5500), [(64, 0), (2, 3)])
        self.assertEqual(self.design([(SAM, 64, 0, 1), (SSM, 2, 3, 1)], tons=6000), [(64, 0), (8, 0)])

    def test_an_overweight_bank_is_undone(self):
        self.assertEqual(self.design([(SAM, 1, 3, 1)], spare=5), [(1, 3)])      # 4 missiles fit, 8 cells do not
        self.assertEqual(self.design([(SAM, 1, 3, 1)], spare=8), [(8, 0)])

    def test_side_mounts_need_a_large_hull_and_an_allowed_missile(self):
        side = [(SSM, 2, 3, 0)]
        self.assertEqual(self.design(side, tons=9000), [(2, 3)])
        self.assertEqual(self.design(side, tons=12000), [(8, 0)])
        self.assertEqual(self.design([(SSM, 2, 3, 1)], banned=(SSM,)), [(2, 3)])

    def test_only_missile_launchers_change(self):
        self.assertEqual(self.design([(0, 2, 3, 1), (7, 2, 3, 1)]), [(2, 3), (2, 3)])

    def test_an_early_nation_keeps_its_launchers_and_a_poor_one_does_not(self):
        for case in (dict(year=1959), dict(research=()), dict(nation=0)):
            self.assertEqual(self.design([(SSM, 2, 3, 1)], **case), [(2, 3)], case)
        self.assertEqual(self.design([(SSM, 2, 3, 1)]), [(8, 0)])               # no economy test any more

    def destroyer(self, **options):
        options = dict(dict(tons=3800, kind=vls.DD, year=2000, mode=vls.START), **options)
        return self.design(TWIN, **options), self.tons

    def test_a_destroyer_grows_for_the_largest_sam_bank_and_keeps_only_the_hull_its_cells_need(self):
        self.assertEqual(self.destroyer(), ([(64, 0), (8, 0)], 5800))              # 72 cells x 80 t: 5,760 t
        self.assertEqual(self.destroyer(research=ALL+(DENSE,)),
                         ([(64, 0), (8, 0)], -(-72*tree.VLS_DENSE[0][1]//100)*100))
        self.assertEqual(self.destroyer(cell=40, spare=1300), ([(64, 0), (8, 0)], 7100))   # the weight needs more hull
        self.assertEqual(self.destroyer(year=1980, research=ALL[:2]), ([(16, 0), (8, 0)], 3800))   # 6,000 t, given back
        self.assertEqual(self.destroyer(tons=2000), ([(32, 0), (8, 0)], 3200))     # a small template: 5,000 t, 62 cells

    def test_a_destroyer_grows_within_its_dock_class_limit_and_years(self):
        self.assertEqual(self.destroyer(dock=5000), ([(32, 0), (8, 0)], 3800))     # 62 cells at 5,000 t: no 64 bank
        self.assertEqual(self.destroyer(limit=3800), ([(32, 0), (8, 0)], 3800))    # the native class limit
        self.assertEqual(self.destroyer(year=1974), ([(32, 0), (8, 0)], 3800))     # before GROW: the usual rule
        self.assertEqual(self.destroyer(mode=vls.CONVERT), ([(32, 0), (8, 0)], 3800))
        self.assertEqual(self.destroyer(spare=-1), ([(2, 10), (2, 3)], 3800))      # an overweight template is left alone
        self.assertEqual(self.destroyer(tons=5000), ([(32, 0), (8, 0)], 5000))     # not a native-size template
        self.assertEqual(self.design(TWIN, tons=3800, year=2000, mode=vls.START, limit=3800), [(32, 0), (8, 0)])
        self.assertEqual(self.tons, 3800)                                          # a cruiser without large hulls

    def test_unused_weight_on_a_grown_destroyer_becomes_speed_then_armour_to_the_eras_limits(self):
        for year, fit in ((1975, (34, 1, 1)), (1985, (32, 2, 2)), (2000, (32, 3, 3))):   # 1,428 t unused at 5,800 t
            self.assertEqual((self.destroyer(year=year), self.fit), (([(64, 0), (8, 0)], 5800), fit), year)
        self.destroyer(year=1975, knot=800); self.assertEqual(self.fit, (33, 1, 1))     # a second knot does not fit
        self.destroyer(plate=600); self.assertEqual(self.fit, (32, 2, 2))               # nor a third half inch
        self.destroyer(dock=5000); self.assertEqual(self.fit, (32, 0, 0))               # the hull went back: untouched
        self.destroyer(mode=vls.CONVERT); self.assertEqual(self.fit, (32, 0, 0))

    def capital(self, **options):
        options = dict(dict(tons=20000, kind=CA, year=2000, after_trim=True, balance=2000, plate=1000, dock=200000),
                       **options)
        return self.design(TWIN, **options), self.tons, self.fit

    def test_another_type_grows_in_a_new_class_when_the_economy_carries_it(self):
        big = [(64, 0), (8, 0)]
        self.assertEqual(self.capital(), (big, 26500, (34, 3, 3)))                 # 140%: 28,000 t, the rest given back
        self.assertEqual(self.capital(funds=20000), (big, 22500, (34, 1, 1)))      # under three months in cash: 120%
        self.assertEqual(self.capital(balance=999), (big, 22500, (34, 1, 1)))      # a surplus under a tenth of a month
        self.assertEqual(self.capital(dock=22000), (big, 20500, (34, 0, 0)))
        self.assertEqual(self.capital(tons=30000)[1:], (34500, (34, 2, 2)))        # the CA class limit: 35,000 t
        for case in (dict(balance=0), dict(funds=9999), dict(limit=3800), dict(year=1959), dict(kind=2), dict(spare=-1),
                     dict(after_trim=False, mode=vls.CONVERT)):
            self.assertEqual(self.capital(**case)[1:], (20000, (32, 0, 0)), case)
        for economy in (dict(balance=0, funds=0), dict(balance=9999, funds=10**9)):   # the start: 120% whatever the funds
            self.assertEqual(self.capital(after_trim=False, mode=vls.START, start=True, **economy),
                             (big, 22500, (34, 1, 1)))
            self.assertEqual(self.redrawn, [20000])
        self.assertEqual(self.capital(after_trim=False, mode=vls.START, limit=3800), ([(32, 0), (8, 0)], 20000, (32, 0, 0)))

    def test_a_carrier_spends_the_larger_hull_on_aircraft_first(self):
        self.assertEqual((self.capital(kind=CV, tons=60000)[2], self.wing), ((34, 2, 2), 130))
        self.assertEqual((self.capital(kind=CV, tons=60000, plane=500)[2], self.wing), ((34, 1, 1), 120))   # 24 fit: 4 steps
        self.assertEqual((self.capital(kind=CA)[2], self.wing), ((34, 3, 3), 100))

    def test_the_start_redraws_a_grown_hull_and_the_pass_after_the_trim_touches_destroyers_only(self):
        self.assertEqual((self.destroyer(start=True), self.redrawn), (([(64, 0), (8, 0)], 5800), [3800]))
        self.assertEqual((self.destroyer(start=True, dock=3800), self.redrawn), (([(32, 0), (8, 0)], 3800), []))
        self.assertEqual(self.destroyer(after_trim=True), ([(64, 0), (8, 0)], 5800))
        self.assertEqual(self.design(TWIN, tons=3800, year=2000, after_trim=True), [(2, 10), (2, 3)])    # a cruiser


if __name__ == "__main__":
    unittest.main()

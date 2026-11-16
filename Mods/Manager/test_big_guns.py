"""Calibres 21-40 in on the reference build: the gun data table, each nation's gun levels, and what reaches them
(research, designer, battle), run through the game's own code where it matters."""
from functools import lru_cache
from pathlib import Path
import re
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
import capstone
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
                               UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_ESP)
import big_guns as guns
import modern_research as audit

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
BASE, NEW, ORD, PAGE = 0x301000, 0x1400000, 0x1403000, 0x1700000   # gun table, ordnance records, code page
ALLOC, HEAP, BACK, STACK = 0x1500100, 0x1600000, 0x1500000, 0x150F000
DATA = HERE.parent/"Library"/"big-guns"/"Files"/"Data"
MISSILE = 0x8C1B30   # a HandleHit return address inside ResolveMissileHit


def applied(blob, plans):
    data = bytearray(blob)
    for p in plans:
        at, old = p["address"]-BASE, bytes.fromhex(p["original"])
        assert bytes(data[at:at+len(old)]) == old, hex(p["address"])
        data[at:at+len(old)] = bytes.fromhex(p["replacement"])
    return bytes(data)


def everything(blob=BLOB, base=BASE):
    return (guns.plans(blob, base, NEW)+guns.ordnance_plans(blob, base, ORD)
            + guns.nation_plans(blob, base, PAGE+guns.CODE["allocator"])+guns.hook_plans(blob, base, PAGE))


@lru_cache(maxsize=1)
def patched():
    return applied(BLOB, everything())


def machine(blob, stubs=()):
    """The patched game image, the code page, a stack whose return address is BACK, and stubs."""
    vm = Uc(UC_ARCH_X86, UC_MODE_32)
    for at, size in ((0x300000, 0x800000), (NEW-0x1000, 0x8000), (BACK, 0x10000), (HEAP, 0x10000), (PAGE, 0x1000)):
        vm.mem_map(at, size)
    vm.mem_write(0x301000, blob)
    for name, body in guns.code(PAGE, BASE).items(): vm.mem_write(PAGE+guns.CODE[name], body)
    for at, body in stubs: vm.mem_write(at, body)
    vm.mem_write(STACK, struct.pack("<I", BACK)); vm.reg_write(UC_X86_REG_ESP, STACK)
    return vm


def run(vm, start, stops, count=5000):
    """Run from start until one of stops is reached; returns that address."""
    hit = []
    def stop(uc, address, size, data):
        if address in stops: hit.append(address); uc.emu_stop()
    handle = vm.hook_add(UC_HOOK_CODE, stop)
    vm.emu_start(start, 0xFFFFFFF0, count=count)
    vm.hook_del(handle)
    return hit[0] if hit else None


def native_blocks():
    """Stand-in for the native gun table read from the game: block c holds c in every slot."""
    return b"".join(struct.pack("<i", c)*(guns.BLOCK//4) for c in range(2, guns.NATIVE_MAX+1))


class GunTableTests(unittest.TestCase):
    def test_every_table_read_and_limit_is_patched(self):
        plans = guns.plans(BLOB, BASE, NEW)
        self.assertEqual(len(plans), len(guns.TABLE_REFS)+len(guns.LIMITS))
        for (site, native, at), p in zip(guns.TABLE_REFS, plans):
            old, new = bytes.fromhex(p["original"]), bytes.fromhex(p["replacement"])
            moved = struct.unpack_from("<I", new, at)[0]-NEW
            self.assertEqual(moved, struct.unpack_from("<I", old, at)[0]-guns.TABLE, hex(site))   # same field offset

    def accessor(self, calibre, yards, deck, caller=None):
        """Run the penetration accessor to its table read; EBX is the value it fetched. caller: the HandleHit
        caller when called the battle way (PenetrationCheck from HandleHit), else a designer-style call."""
        vm = machine(patched())
        vm.mem_write(NEW, guns.table(native_blocks(), DATA, factor=10, divisor=10.0))
        ret = BACK
        if caller is not None:   # fake PenetrationCheck and HandleHit frames
            vm.mem_write(0x1509000, struct.pack("<I", 0x1509100)); vm.mem_write(0x1509104, struct.pack("<I", caller))
            vm.reg_write(UC_X86_REG_EBP, 0x1509000); ret = guns.PENCHECK_RET
        vm.mem_write(STACK, struct.pack("<IIIII", ret, 0, 0, 0, deck))
        for reg, value in ((UC_X86_REG_EAX, calibre), (UC_X86_REG_EDX, yards), (UC_X86_REG_ECX, 0)):
            vm.reg_write(reg, value)
        self.assertEqual(run(vm, 0x91D898, {0x91D928}, count=300), 0x91D928)
        return vm.reg_read(UC_X86_REG_EBX)

    def test_penetration_reads_come_from_the_extended_table(self):
        verpen, horpen = guns.rows(DATA/"VerPen.dat"), guns.rows(DATA/"HorPen.dat")
        self.assertEqual(self.accessor(20, 10000, 0), 20)                 # native block, copied
        self.assertEqual(self.accessor(30, 10000, 0), verpen[30][2+10])   # 10,000 yd vertical (column 0 is the calibre)
        self.assertEqual(self.accessor(40, 25000, 1), horpen[40][2+25])   # 25,000 yd deck
        self.assertEqual(self.accessor(55, 10000, 0), verpen[40][2+10])   # clamped to 40 in

    def test_the_table_follows_the_native_loader_conversions(self):
        table = guns.table(native_blocks(), DATA, factor=10, divisor=10.0)
        self.assertEqual(len(table), (guns.MAX_CALIBRE-1)*guns.BLOCK)
        forty = table[(40-2)*guns.BLOCK:(40-1)*guns.BLOCK]
        self.assertEqual(struct.unpack_from("<i", forty, 0)[0], 50)          # VerPen header 50 * 10 / 10
        self.assertEqual(struct.unpack_from("<i", forty, 4)[0], 800)         # 1,000 yd: twice the 20 in value
        self.assertAlmostEqual(struct.unpack_from("<f", forty, 0xF4)[0], 0.3, places=5)
        self.assertEqual(struct.unpack_from("<i", forty, 0xFC)[0], 50)       # maximum range, thousand yards
        native = guns.rows(Path(r"D:\Games\RTW3\Data")/"VerPen.dat") if Path(r"D:\Games\RTW3\Data\VerPen.dat").exists() else None
        if native:   # the shipped files keep every native row
            self.assertEqual({c: native[c] for c in range(2, 21)}, {c: guns.rows(DATA/"VerPen.dat")[c] for c in range(2, 21)})

    def test_set_calibre_allows_forty_inches(self):
        for asked, stored in ((1, 2), (20, 20), (35, 35), (40, 40), (55, 40)):
            vm = machine(patched())
            for reg, value in ((UC_X86_REG_EAX, 0x1501000), (UC_X86_REG_ECX, 1), (UC_X86_REG_EDX, asked)):
                vm.reg_write(reg, value)
            vm.emu_start(0x916304, BACK, count=50)
            self.assertEqual(struct.unpack("<i", vm.mem_read(0x1501000+4+0x69, 4))[0], stored, asked)

    def test_changed_native_code_is_refused(self):
        changed = bytearray(BLOB); changed[0x91D904-BASE+3] ^= 1
        with self.assertRaises(ValueError): guns.plans(bytes(changed), BASE, NEW)
        changed = bytearray(BLOB); changed[0x916309-BASE+2] = 0x15
        with self.assertRaises(ValueError): guns.plans(bytes(changed), BASE, NEW)


class NationGunTests(unittest.TestCase):
    """Every nation's Guns[0..41] past its native fields, run through the game's own code."""

    def levels(self, vm, first=2, last=guns.MAX_CALIBRE):
        return struct.unpack(f"<{last-first+1}i", vm.mem_read(HEAP+guns.GUNS+4*first, 4*(last-first+1)))

    def test_every_nation_gun_access_moves_with_the_array(self):
        plans = guns.nation_plans(BLOB, BASE, ALLOC)
        self.assertEqual(len(plans), 1+len(guns.GUN_SITES)+len(guns.GUN_LOOPS))
        spans = sorted((p["address"], p["address"]+len(p["original"])//2) for p in everything())
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])))   # no two patches overlap
        cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for site, native in guns.GUN_SITES:
            old = next(cs.disasm(bytes.fromhex(native), site)); new = next(cs.disasm(guns.moved(bytes.fromhex(native)), site))
            disp = int(re.search(r"(0x1[0-9a-f]{2})\]", old.op_str)[1], 16)
            self.assertEqual((new.mnemonic, new.size), (old.mnemonic, old.size))
            self.assertEqual(new.op_str, old.op_str.replace(f"{disp:#x}]", f"{disp-guns.NATIVE_GUNS+guns.GUNS:#x}]"), hex(site))

    def test_new_nations_get_gun_levels_to_forty_inches(self):
        blob = applied(BLOB, guns.nation_plans(BLOB, BASE, ALLOC))
        get_mem = b"\xb8"+struct.pack("<I", HEAP)+b"\xc3"
        vm = machine(blob, ((ALLOC, guns.allocator(ALLOC, BASE)), (guns.GET_MEM, get_mem)))
        vm.mem_write(HEAP, b"\xcc"*0x10000)                                   # GetMem leaves memory dirty
        self.assertEqual(struct.unpack_from("<I", blob, guns.NATION_VMT-0x0C-BASE)[0], ALLOC)   # the class's NewInstance
        vm.reg_write(UC_X86_REG_EAX, guns.NATION_VMT)
        vm.emu_start(ALLOC, BACK, count=200000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EAX), HEAP)
        obj = bytes(vm.mem_read(HEAP, guns.GUNS+4*guns.GUN_SLOTS+4))
        self.assertEqual(struct.unpack_from("<I", obj)[0], guns.NATION_VMT)
        self.assertEqual(obj[0x11D:0x171], b"\0"*0x54)                          # native fields zeroed as before
        self.assertEqual(self.levels(vm, 0, guns.GUN_SLOTS-1), (9, 9)+(0,)*19+(9,)*21)
        self.assertEqual(obj[-4:], b"\xcc"*4)                                   # nothing written past the object

    def test_saves_hold_gun_levels_to_forty_inches(self):
        count, log = 0x1500F00, 0x1500E00
        read = b"\xa1"+struct.pack("<I", count)+b"\xff\x05"+struct.pack("<I", count)+b"\xc2\x04\x00"   # next number
        write = b"\x8b\x44\x24\x04\x8b\x15"+struct.pack("<I", log)+b"\x89\x02\x83\x05"+struct.pack("<I", log)+b"\x04\xc2\x04\x00"
        vm = machine(patched(), ((0x328C80, b"\xc3"), (0x30C694, b"\xc3"), (0x586FC8, read), (0x586EA4, write)))
        vm.mem_write(HEAP, b"\x55"*0x10000); vm.mem_write(count, struct.pack("<i", 1000))
        for reg, value in ((UC_X86_REG_EBX, HEAP), (UC_X86_REG_EBP, 0x150E000), (UC_X86_REG_ESI, 0), (UC_X86_REG_EDI, 0)):
            vm.reg_write(reg, value)
        vm.emu_start(0x7208DD, 0x720924, count=10000)                         # LoadMe: Guns2..Guns40
        self.assertEqual(self.levels(vm), tuple(range(1000, 1039)))
        self.assertEqual(bytes(vm.mem_read(HEAP, guns.GUNS)), b"\x55"*guns.GUNS)    # native fields untouched
        self.assertEqual(self.levels(vm, 41, 41), (0x55555555,))
        vm.mem_write(log, struct.pack("<I", 0x1501000))
        vm.emu_start(0x72520C, 0x725283, count=10000)                         # SaveMe writes them back
        self.assertEqual(struct.unpack("<39i", vm.mem_read(0x1501000, 39*4)), tuple(range(1000, 1039)))
        self.assertEqual(struct.unpack("<I", vm.mem_read(log, 4))[0], 0x1501000+39*4)

    def test_custom_battle_years_set_the_moved_levels(self):
        vm = machine(patched())
        vm.mem_write(0x9F7328, struct.pack("<I", 0xA231E0)); vm.mem_write(0xA231E0, struct.pack("<i", 1936))
        vm.mem_write(HEAP, b"\0"*0x10000); vm.mem_write(HEAP+0x1E9, b"\x01")
        vm.mem_write(HEAP+guns.GUNS+8, struct.pack("<i", 7)*19)
        vm.reg_write(UC_X86_REG_EDX, HEAP)
        vm.emu_start(0x6A9828, BACK, count=200)                                # fixed-calibre writes, no index
        expected = dict.fromkeys(range(2, 21), 7)
        expected.update(dict.fromkeys((8, 9, 10, 11, 12, 13, 14, 15, 16, 18), 0)); expected[6] = 1   # 1936 rules
        self.assertEqual(dict(zip(range(2, 21), self.levels(vm, 2, 20))), expected)
        self.assertEqual(bytes(vm.mem_read(HEAP+0x125, 19*4)), b"\0"*19*4)  # the native array stays unused

    def test_largest_gun_calibre_reaches_forty(self):
        vm = machine(patched())
        levels = [9, 9]+[0]*19+[9]*21
        levels[30] = 1
        vm.mem_write(HEAP+guns.GUNS, struct.pack(f"<{len(levels)}i", *levels)); vm.reg_write(UC_X86_REG_EAX, HEAP)
        vm.emu_start(0x71F044, BACK, count=500)
        self.assertEqual(vm.reg_read(UC_X86_REG_EAX), 30)

    def test_changed_nation_code_is_refused(self):
        for at in (0x79CB82+2, guns.NATION_VMT-0x34, guns.NATION_VMT-0x0C, guns.NEW_INSTANCE+7, 0x72091F+2):
            changed = bytearray(BLOB); changed[at-BASE] ^= 1
            with self.assertRaises(ValueError, msg=hex(at)): guns.nation_plans(bytes(changed), BASE, ALLOC)


class ReachTests(unittest.TestCase):
    """Research, the designer and battle for 21-40 in."""

    def test_ordnance_records_follow_the_native_loader(self):
        native = bytes(range(21))*guns.RECORD
        records = guns.ordnance(native, DATA/guns.ORDNANCE_FILE)
        self.assertEqual(len(records), guns.ORDNANCE_SLOTS*guns.RECORD)
        self.assertEqual(records[:len(native)], native)
        def at(c): return records[c*guns.RECORD:(c+1)*guns.RECORD]
        self.assertEqual(struct.unpack_from("<iHff", at(40)), (40, ord("H"), 1728.0, 3*1170.0))
        self.assertEqual(struct.unpack_from("<5i", at(40), 0x0E), (18000, -1, 520, 679, 849))   # SW, TFC 'x', TF1-3
        self.assertEqual(at(41), at(40)); self.assertEqual(at(42), at(40))
        row = guns.record("20\tH\t216\t475\t92\t120\t150\tx\t2250".split("\t"))   # the native 20 in row
        self.assertEqual(struct.unpack_from("<iHff5i", row), (20, ord("H"), 216.0, 1425.0, 2250, -1, 92, 120, 150))

    def test_designer_costs_read_the_extended_records(self):
        vm = machine(patched())
        vm.mem_write(ORD, guns.ordnance(bytes(21*guns.RECORD), DATA/guns.ORDNANCE_FILE))
        vm.mem_write(HEAP+4, struct.pack("<i", 3))                                # three barrels
        vm.reg_write(UC_X86_REG_EAX, HEAP); vm.reg_write(UC_X86_REG_EDX, 30)
        vm.emu_start(0x950AF8, BACK, count=500)                                    # GetGunsCost
        factor = struct.unpack_from("<f", BLOB, 0x950B30-BASE)[0]
        self.assertEqual(vm.reg_read(UC_X86_REG_EAX), round(3*3*805*factor))

    def test_research_waits_for_each_big_calibre_year(self):
        stops = {0x79C9EE: "too early", 0x79C9C3: "go on", 0x79C9C8: "17/19 roll"}
        for calibre, year, expected in ((21, 1942, "too early"), (21, 1943, "go on"), (40, 1999, "too early"),
                                        (40, 2000, "go on"), (17, 1900, "17/19 roll"), (18, 1900, "go on")):
            vm = machine(patched(), ((guns.YEAR_GATE, b"\xc3"),))                   # research speed 100%: same year
            vm.mem_write(0x1508000, struct.pack("<i", year))
            vm.reg_write(UC_X86_REG_EBX, calibre); vm.reg_write(UC_X86_REG_EDI, 0x1508000)
            self.assertEqual(stops[run(vm, 0x79C9BE, set(stops))], expected, (calibre, year))

    def test_research_list_reads_dispersion_flags_only_to_20_inches(self):
        for calibre, expected in ((7, 0x5AA236), (8, 0x5AA213), (20, 0x5AA213), (21, 0x5AA236), (40, 0x5AA236)):
            vm = machine(patched()); vm.reg_write(UC_X86_REG_EBX, calibre)
            self.assertEqual(run(vm, 0x5AA20E, {0x5AA213, 0x5AA236}), expected, calibre)

    def hit(self, start, stops, calibre, caller, code=0):
        """HandleHit frame at 0x1509000: [ebp+4] caller, [ebp+24h] calibre, [ebp-4] hit code."""
        vm = machine(patched(), ((guns.INT_TO_STR, b"\xa3\x00\x0f\x50\x01\xc3"),))   # IntToStr: note EAX
        vm.mem_write(0x1509000-4, struct.pack("<iI", code, 0))
        vm.mem_write(0x1509004, struct.pack("<I", caller)); vm.mem_write(0x1509024, struct.pack("<i", calibre))
        vm.reg_write(UC_X86_REG_EBP, 0x1509000)
        where = run(vm, start, stops)
        return where, struct.unpack("<i", vm.mem_read(0x1509000-4, 4))[0], struct.unpack("<i", vm.mem_read(0x1500F00, 4))[0]

    def test_only_fired_shells_take_the_table_path_above_20_inches(self):
        table, other = 0x8F71FB, 0x8F728A
        for calibre, caller, expected in ((12, MISSILE, table), (20, guns.FIREGUNS_RET, table), (30, guns.FIREGUNS_RET, table),
                                          (40, guns.FIREGUNS_RET, table), (30, MISSILE, other), (40, MISSILE, other),
                                          (41, guns.FIREGUNS_RET, other)):
            self.assertEqual(self.hit(0x8F71F1, {table, other}, calibre, caller)[0], expected, (calibre, hex(caller)))
        for calibre, caller, code in ((12, guns.FIREGUNS_RET, 12), (34, guns.FIREGUNS_RET, 20), (31, MISSILE, 31), (40, MISSILE, 40)):
            self.assertEqual(self.hit(0x8F72A9, {0x8F72AF}, calibre, caller)[:2], (0x8F72AF, code), calibre)

    def test_damage_log_names_the_shell_calibre(self):
        for code, calibre, shown in ((20, 34, 34), (20, 20, 20), (31, 32, 31), (12, 12, 12)):   # 31: missile, now 32 in
            where, _, text = self.hit(0x901CEC, {0x901CF4}, calibre, guns.FIREGUNS_RET, code)
            self.assertEqual((where, text), (0x901CF4, shown), (code, calibre))

    def test_penetration_keeps_missiles_at_20_inches(self):
        verpen = guns.rows(DATA/"VerPen.dat")
        accessor = GunTableTests().accessor
        self.assertEqual(accessor(30, 10000, 0, caller=guns.FIREGUNS_RET), verpen[30][2+10])   # fired shell
        self.assertEqual(accessor(32, 10000, 0, caller=MISSILE), 20)                            # missile: 20 in block
        self.assertEqual(accessor(12, 10000, 0, caller=MISSILE), 12)

    def test_crew_and_overgunned_minimums_grow_past_20_inches(self):
        for calibre, crew in ((2, 4), (20, 56), (21, 58), (30, 76), (40, 96), (41, 10)):
            vm = machine(patched()); vm.reg_write(UC_X86_REG_EAX, calibre)
            vm.emu_start(0x93E6D4, BACK, count=50)
            self.assertEqual(vm.reg_read(UC_X86_REG_EAX), crew, calibre)
        for calibre, switch, tons in ((21, 21, 34000), (40, 41, 74000), (20, 21, 5000)):   # 20 in +1: native default
            vm = machine(patched()); vm.mem_write(HEAP+0x6D, struct.pack("<i", calibre))
            for reg, value in ((UC_X86_REG_EAX, switch), (UC_X86_REG_EDI, HEAP), (UC_X86_REG_ESI, 5000)):
                vm.reg_write(reg, value)
            self.assertEqual(run(vm, 0x947827, {0x947907}), 0x947907)
            self.assertEqual(vm.reg_read(UC_X86_REG_ESI), tons, calibre)

    def test_gun_improvements_reach_developed_big_guns(self):
        levels = [9, 9]+[0]*19+[9]*9+[-1]+[2]*11                                   # 30 in improvable, 31-41 at best
        for roll, native, expected in ((b"\x31\xc0\xc3", 15, (0x79D249, 30)),        # the 1-in-4 roll: improve 30 in
                                       (b"\xb8\x01\x00\x00\x00\xc3", 15, (0x79D212, 15)),   # the native pick
                                       (b"\xb8\x01\x00\x00\x00\xc3", 5, (0x79D249, 5))):
            vm = machine(patched(), ((guns.RANDOM, roll),))
            vm.mem_write(HEAP+guns.GUNS, struct.pack("<42i", *levels))
            vm.mem_write(0x1509000-4, struct.pack("<I", HEAP)); vm.reg_write(UC_X86_REG_EBP, 0x1509000)
            vm.reg_write(UC_X86_REG_EDI, native); vm.reg_write(UC_X86_REG_EBX, 77)
            where = run(vm, 0x79D20D, {0x79D249, 0x79D212})
            self.assertEqual((where, vm.reg_read(UC_X86_REG_EDI)), expected, (roll.hex(), native))
            self.assertEqual(vm.reg_read(UC_X86_REG_EBX), 77)                          # kept for the native code
        vm = machine(patched(), ((guns.RANDOM, b"\x31\xc0\xc3"),))                       # nothing to improve
        vm.mem_write(HEAP+guns.GUNS, struct.pack("<42i", *([9, 9]+[0]*19+[9]*10+[2]*11)))
        vm.mem_write(0x1509000-4, struct.pack("<I", HEAP)); vm.reg_write(UC_X86_REG_EBP, 0x1509000); vm.reg_write(UC_X86_REG_EDI, 15)
        self.assertEqual(run(vm, 0x79D20D, {0x79D249, 0x79D212}), 0x79D212)

    def test_ai_upsizes_past_16_inches_only_when_it_can_afford_it(self):
        design, go_on, stop = HEAP+0x2000, 0x77936E, 0x7794AB
        for calibre, balance, funds, expected in ((12, -5, 0, go_on),               # below 16 in: native
                                                  (16, 100, 20000, go_on),          # two months of 120,000 a year
                                                  (20, 100, 19999, stop), (20, -5, 10**6, stop), (30, 1, 50000, go_on)):
            vm = machine(patched(), ((guns.MONTHLY_BALANCE, b"\xb8"+struct.pack("<i", balance)+b"\xc3"),
                                     (guns.MODIFIED_BUDGET, b"\xb8"+struct.pack("<i", 120000)+b"\xc3")))
            vm.mem_write(design+0x6D, struct.pack("<i", calibre)); vm.mem_write(HEAP+guns.FUNDS, struct.pack("<i", funds))
            vm.mem_write(0x1509000-0xC, struct.pack("<I", HEAP)); vm.reg_write(UC_X86_REG_EBP, 0x1509000)
            vm.reg_write(UC_X86_REG_EBX, design)
            self.assertEqual(run(vm, 0x779364, {go_on, stop}), expected, (calibre, balance, funds))
            self.assertEqual(vm.reg_read(UC_X86_REG_EBX), design)
        self.assertEqual(struct.unpack_from("<i", patched(), 0x957E75+1-BASE)[0], 40)   # AI battleship cap
        self.assertEqual(patched()[0x957CFA+2-BASE], 40)                                  # AI calibre setter range

    def test_ship_type_rules_count_big_guns_by_firepower(self):
        blob, design = patched(), HEAP+0x2000
        for site, _ in guns.FIREPOWER_CALLS:   # every CountGuns call in SuggestShipType
            self.assertEqual(site+5+struct.unpack_from("<i", blob, site+1-BASE)[0], PAGE+guns.CODE["firepower"], hex(site))
        for calibre, guns_fitted, counted in ((16, 1, 1), (20, 9, 9), (39, 1, 7), (39, 2, 14), (40, 1, 8), (21, 7, 8)):
            vm = machine(blob, ((guns.COUNT_GUNS, b"\xb8"+struct.pack("<i", guns_fitted)+b"\xc3"),))
            vm.mem_write(design+0x6D, struct.pack("<i", calibre)); vm.reg_write(UC_X86_REG_EAX, design)
            vm.emu_start(PAGE+guns.CODE["firepower"], BACK, count=50)
            self.assertEqual(vm.reg_read(UC_X86_REG_EAX), counted, (calibre, guns_fitted))   # battleship: more than 7

    def test_switch_defaults_follow_20_inches(self):
        blob = patched()
        def target(site): return site+6+struct.unpack_from("<i", blob, site+2-BASE)[0]
        self.assertEqual(target(0x732957), struct.unpack_from("<I", BLOB, 0x732964+4*20-BASE)[0])     # GunPosOK
        group = BLOB[0x5D6EFD+20-BASE]
        self.assertEqual(target(0x5D6EE9), struct.unpack_from("<I", BLOB, 0x5D6F12+4*group-BASE)[0])  # ammo note

    def test_changed_phase_three_code_is_refused(self):
        for at, build in ((0x8F71F1+3, guns.hook_plans), (0x732957+2, guns.hook_plans), (0x950B17+3, guns.ordnance_plans),
                          (0x949794+3, guns.ordnance_plans), (0x94979F+1, guns.ordnance_plans)):
            changed = bytearray(BLOB); changed[at-BASE] ^= 1
            with self.assertRaises(ValueError, msg=hex(at)): build(bytes(changed), BASE, PAGE)

    def test_relocated_game_patches_and_other_audits_still_match(self):
        delta = 0x510000
        moved = bytearray(BLOB)
        for offset in audit.text_relocations():
            struct.pack_into("<I", moved, offset, (struct.unpack_from("<I", moved, offset)[0]+delta) & 0xffffffff)
        plans = everything(bytes(moved), BASE+delta)
        slot = [p for p in plans if p["address"] == guns.NATION_VMT-0x0C+delta]
        self.assertEqual(bytes.fromhex(slot[0]["original"]), struct.pack("<I", guns.NEW_INSTANCE+delta))
        live = bytearray(moved)
        for p in plans:
            at = p["address"]-delta-BASE; live[at:at+len(p["original"])//2] = bytes.fromhex(p["replacement"])
        normal = bytearray(audit.normalize(bytes(live), BASE+delta))
        for site, native, _ in guns.TABLE_REFS+guns.ORDNANCE_REFS+(guns.ORDNANCE_TOP,):   # addresses: not audited
            normal[site-BASE:site-BASE+len(native)//2] = bytes.fromhex(native)
        normal[guns.NATION_VMT-0x0C-BASE:guns.NATION_VMT-0x08-BASE] = struct.pack("<I", guns.NEW_INSTANCE)
        self.assertEqual(bytes(normal), BLOB)              # every other change reads back as native code

    def test_other_adapters_still_recognise_the_patched_code(self):
        blob = patched()
        import campaign_qol, campaign_security, research_budget, research_cheats, research_traits
        for module in (audit, campaign_qol, campaign_security, research_budget, research_traits):
            module.discover(blob, BASE)
        native, now = research_cheats.discover(BLOB, BASE), research_cheats.discover(blob, BASE)
        self.assertEqual(native, now)
        self.assertEqual(struct.unpack_from("<I", blob, now["gun_read"]-BASE)[0], guns.GUNS)


class AttachTests(unittest.TestCase):
    """attach/detach against a fake title-screen game built from the reference image."""

    def test_attach_installs_everything_and_detach_restores_it(self):
        import tempfile
        from unittest import mock
        import native_designer, week_display, weekly_runtime as rt
        memory = {0x300000: bytearray(0x800000), PAGE: bytearray(0x4000), HEAP: bytearray(0x10000)}
        def locate(address, size):
            for start, data in memory.items():
                if start <= address and address+size <= start+len(data): return data, address-start
            raise OSError(hex(address))
        def read(handle, address, size): data, at = locate(address, size); return bytes(data[at:at+size])
        def write(handle, address, data): buf, at = locate(address, len(data)); buf[at:at+len(data)] = data
        def write_code(handle, address, original, replacement):
            self.assertEqual(read(None, address, len(original)), original); write(None, address, replacement)
        write(None, 0x301000, BLOB)
        write(None, guns.TABLE, native_blocks()); write(None, guns.VERPEN_FACTOR, struct.pack("<i", 10))
        write(None, guns.ORDNANCE, bytes(21*guns.RECORD))
        form, spin = HEAP+0x100, HEAP+0x1000                                  # designer form and its calibre box
        write(None, HEAP, struct.pack("<I", form)); write(None, form+0x670, struct.pack("<I", spin))
        write(None, spin, struct.pack("<I", guns.SPIN_VMT)); write(None, spin+guns.SPIN_MAX, struct.pack("<i", 20))
        game = DATA.parent
        kernel = mock.Mock(); kernel.OpenProcess.return_value = 1; kernel.VirtualAllocEx.return_value = PAGE
        with tempfile.TemporaryDirectory() as temp, mock.patch.multiple(
                rt, K=kernel, GAME=game, configure_api=mock.DEFAULT, report_is_current=mock.Mock(return_value=True),
                process_candidates=mock.Mock(return_value=[(77, game/"RTW3.exe")]), module_info=mock.Mock(return_value=(0x300000, 0)),
                text_section=mock.Mock(return_value=(BASE, BLOB)), read=read, write_code=write_code), \
                mock.patch.object(week_display, "configure"), mock.patch.object(week_display, "write", write), \
                mock.patch.object(native_designer, "discover", return_value=dict(slot=HEAP, fields=dict(seMainCal=0x670))), \
                mock.patch.object(guns, "REPORT", Path(temp)/"report.json"):
            saved = guns.attach(wait=0)
            self.assertEqual(read(None, guns.NATION_VMT-0x0C, 4), struct.pack("<I", PAGE+guns.LAYOUT["code"]))
            self.assertEqual(read(None, spin+guns.SPIN_MAX, 4), struct.pack("<i", 40))
            self.assertEqual(read(None, PAGE+guns.LAYOUT["ordnance"]+40*guns.RECORD, 4), struct.pack("<i", 40))
            self.assertEqual(read(None, 0x8F71F1, 1), b"\xe9")
            self.assertEqual(guns.attach(wait=0)["patches"], saved["patches"])    # attaching again changes nothing
            guns.detach()                                                          # main global still 0: title screen
            self.assertEqual(bytes(memory[0x300000][0x1000:0x1000+len(BLOB)]), BLOB)   # every code byte native again
            self.assertEqual(read(None, spin+guns.SPIN_MAX, 4), struct.pack("<i", 20))
            write(None, 0xA23000, struct.pack("<I", HEAP+0x2000)); write(None, HEAP+0x2000+guns.NATIONS, struct.pack("<I", HEAP+0x3000))
            write(None, HEAP+0x3008, struct.pack("<i", 3))                       # a loaded campaign: three nations
            guns.REPORT.unlink()
            with self.assertRaisesRegex(ValueError, "before a campaign"): guns.attach(wait=0)


if __name__ == "__main__":
    unittest.main()

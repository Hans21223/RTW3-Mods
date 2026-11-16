"""Frigate type 15 (frigate_type.py): every type read rerouted, identity reads kept, the text case and designer item."""
from pathlib import Path
import random
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
from test_modern_combat import World, BLOB, STACK, DATA, SHIP
from test_modern_recon import call
import frigate_type as ff
import modern_research as modern

ALLOCATION = 0x2400000
FLAGS = 0x8D5                       # CF PF AF ZF SF OF
REGS = ("EAX", "ECX", "EDX", "EBX", "EBP", "ESI", "EDI")


def built(owned=()):
    info = ff.discover(BLOB, ff.BASE, owned)
    image, plans = ff.build(ALLOCATION, info)
    return info, image, plans


class SiteTests(unittest.TestCase):
    def test_the_site_list_matches_the_reference_code_and_every_read_is_supported(self):
        sites = ff.sites()
        self.assertEqual(len(sites), 1637)
        for address, code in sites:
            self.assertEqual(BLOB[address-ff.BASE:address-ff.BASE+len(code)], code, hex(address))
            ff.decode(code)
        self.assertTrue(set(ff.IDENTITY) <= {address for address, _ in sites})

    def test_all_but_identity_and_owned_reads_are_rerouted(self):
        info, image, plans = built(owned=[(0x950090, 7), (0x813ED5, 5)])
        rerouted = {address for address, _ in info["reroute"]}
        self.assertEqual((len(rerouted), info["skipped"], len(ff.IDENTITY)), (1637-14-2, [0x813ED5, 0x950090], 14))
        self.assertFalse(rerouted & set(ff.IDENTITY))
        reads = [p for p in plans if p["label"] == "Frigate type: read"]
        self.assertEqual(len(reads), len(rerouted))
        for plan in reads:   # a call into the routines, padded to the instruction's length
            new = bytes.fromhex(plan["replacement"])
            self.assertEqual((new[0], len(new)), (0xE8, len(bytes.fromhex(plan["original"]))))
            self.assertTrue(ALLOCATION+0x1000 <= plan["address"]+5+struct.unpack_from("<i", new, 1)[0] < ALLOCATION+len(image))

    def test_each_routine_gives_the_native_result_and_reads_a_frigate_as_a_corvette(self):
        rng = random.Random(7)
        site, routine, data, stack = 0x10000, 0x20000, 0x30000, 0x40000
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address in (site, routine, data, stack): vm.mem_map(address, 0x10000)

        def run(start, length, value, regs, flags):
            vm.mem_write(data+ff.TYPE, bytes([value]))
            for name, number in regs.items(): vm.reg_write(globals()["UC_X86_REG_"+name], number)
            vm.reg_write(UC_X86_REG_ESP, stack+0x8000); vm.reg_write(UC_X86_REG_EFLAGS, flags | 2)
            vm.emu_start(start, start+length, count=100)
            return [vm.reg_read(globals()["UC_X86_REG_"+n]) for n in REGS+("ESP",)], vm.reg_read(UC_X86_REG_EFLAGS) & FLAGS
        forms = sorted({code for _, code in ff.sites()})
        for index, (code, seen) in enumerate((c, s) for c in forms for s in (ff.KE, ff.DD)):
            form, reg, base, imm = ff.decode(code)
            # code written once at its own addresses: the emulator keeps translated blocks across runs
            native, hooked, thunk = site+0x20*index, site+0x8000+0x20*index, routine+0x40*index
            vm.mem_write(native, code); vm.mem_write(thunk, ff.thunk(code, seen))
            vm.mem_write(hooked, b"\xe8"+struct.pack("<i", thunk-hooked-5)+b"\x90"*(len(code)-5))
            for value in (0, 3, 9, 10, 12, 14, 15):
                regs = {name: rng.getrandbits(32) for name in REGS}
                regs[REGS[(0, 1, 2, 3, None, 4, 5, 6)[base]]] = data
                flags = rng.choice((0, FLAGS))
                expected = run(native, len(code), seen if value == ff.FF else value, regs, flags)
                self.assertEqual(run(hooked, len(code), value, regs, flags), expected, (code.hex(), value, seen))

    def test_the_picture_reads_draw_a_frigate_as_a_destroyer(self):
        sites = dict(ff.sites())
        self.assertTrue(set(ff.VISUAL) <= set(sites) and not set(ff.VISUAL) & set(ff.IDENTITY))
        reroute = [(a, sites[a]) for a in sorted(ff.VISUAL)]+[(0x90D911, sites[0x90D911])]   # the outline type stays KE
        native = dict.fromkeys(("table", "default_case", "case_tail", "ke_rule", "suggest", "torpedoes", "class_ok",
                                "class_error", "auto", "auto_done"), 0x200000)
        image, _ = ff.build(0x100000, dict(delta=0, reroute=reroute, native=dict(native, open=[])))
        self.assertEqual(image[0x1000:], b"".join(ff.thunk(c, ff.DD if a in ff.VISUAL else ff.KE) for a, c in reroute))


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.world = w = World()
        w.vm.mem_map(ALLOCATION, 0x20000)
        info, image, self.plans = built()
        w.vm.mem_write(ALLOCATION, image)
        for plan in self.plans: w.vm.mem_write(plan["address"], bytes.fromhex(plan["replacement"]))
        blocks = {b["name"]: b["address"] for b in modern.build(0x2000000, modern.discover(BLOB, 0x301000))[0]}
        self.slots = [blocks[name] for name in ff.SLOTS]
        w.stubs[0x30BCCC] = lambda: w.put(w.reg("EAX"), w.reg("EDX")) or 0           # UStrAsg without the heap
        w.put(0x9F7328, STACK+0x200); w.put(STACK+0x200, 1990)                         # the campaign year

    def text(self, kind):
        w = self.world; w.put(STACK+0x100, 0)
        call(w, 0x9514E0, EAX=kind, EDX=STACK+0x100)
        pointer = w.get(STACK+0x100)
        return bytes(w.vm.mem_read(pointer, 2*w.get(pointer-4))).decode("utf-16-le")

    def read(self, value):
        w = self.world; address = DATA+0x10000
        w.vm.mem_write(address-12, struct.pack("<HHiI", 1200, 2, -1, len(value))+value.encode("utf-16-le")+b"\0\0")
        return call(w, 0x9518FC, EAX=address) & 0xFF

    def test_type_15_reads_ff_and_ff_reads_15_once_the_slots_are_set(self):
        self.assertEqual((self.text(ff.FF), self.text(ff.KE), self.read("FF"), self.text(9)), ("FF", "FF", ff.KE, "DD"))
        for slot, value in zip(self.slots, ff.SLOT_VALUES): self.world.put(slot, value)
        self.assertEqual((self.text(ff.FF), self.text(ff.KE), self.read("FF"), self.read("KE")), ("FF", "KE", ff.FF, ff.KE))

    def test_a_rerouted_read_sees_a_corvette_and_an_identity_read_the_frigate(self):
        w = self.world; w.vm.mem_write(SHIP, bytes(0xA00)); w.put(SHIP+ff.TYPE, ff.FF, 1)
        address, code = next((a, c) for a, c in ff.sites() if c.hex() == "80bbd309000009")   # cmp byte [ebx+9D3h], 9
        w.run(address, address+len(code), EBX=SHIP)
        self.assertFalse(w.reg("EFLAGS") & 0x40)                                   # not a destroyer
        address, code = next((a, c) for a, c in ff.sites() if c.hex() == "80bbd30900000a")   # ... KE
        w.run(address, address+len(code), EBX=SHIP)
        self.assertTrue(w.reg("EFLAGS") & 0x40)                                    # a corvette for the rules
        w.run(0x93F595, 0x93F59C, EDI=SHIP)                                        # the ShipType key: FF
        self.assertEqual(w.reg("EAX"), ff.FF)

    def test_the_designer_list_gains_the_frigate_item_once_when_the_designer_opens(self):
        w = self.world; form, items, vmt, added = DATA+0x11000, DATA+0x12000, DATA+0x12100, []
        w.put(form+ff.CB_TYPE, DATA+0x12200); w.put(DATA+0x12200+ff.ITEMS, items); w.put(items, vmt)
        w.put(vmt+ff.ADD, 0x300800)                                            # mapped, empty
        w.stubs[0x300800] = lambda: added.append((w.reg("EAX"), self.string(w.reg("EDX")))) or 1
        for site in ff.OPEN_SITES:
            for year in (1900, 2000):                                          # the year test still decides
                w.put(STACK+0x300, year)
                w.run(site, site+6, EAX=STACK+0x300, ESI=form, EBX=0x1111, EDI=0x2222)
                self.assertEqual((bool(w.reg("EFLAGS") & 0x40), w.reg("EFLAGS") & 0x80 == (w.reg("EFLAGS") >> 4) & 0x80),
                                 (False, year > 1920))
                self.assertEqual((w.reg("EAX"), w.reg("ESI"), w.reg("EBX"), w.reg("EDI")), (STACK+0x300, form, 0x1111, 0x2222))
        self.assertEqual(added, [(items, ff.ITEM)])

    def string(self, pointer):
        return bytes(self.world.vm.mem_read(pointer, 2*self.world.get(pointer-4))).decode("utf-16-le")

    def test_auto_design_makes_a_listed_frigate_as_a_destroyer_and_hands_it_over_as_a_frigate(self):
        w = self.world; form, design = DATA+0x13000, DATA+0x14000
        for listed, designed, retyped in ((ff.FF, 9, ff.FF), (9, 9, 9), (12, 12, 9)):
            w.run(0x5E284A, 0x5E284F, EAX=listed)                                  # the type read from the list
            flags = w.reg("EFLAGS")
            self.assertEqual((w.reg("EBX"), not flags & 0x41), (designed, designed > 10), listed)   # JA: refused
            w.vm.mem_write(design, bytes(0xA00)); w.put(design+ff.TYPE, 9, 1); w.put(form+0xE6C, design)
            w.run(0x5E29AD, 0x5E29B3, ESI=form, EAX=0x4444)                         # the AI's design, handed over
            self.assertEqual((w.reg("EBX"), w.reg("EAX"), w.get(design+ff.TYPE) & 0xFF), (design, 0x4444, retyped), listed)


class ClassRuleTests(unittest.TestCase):
    """The designer's KE class rule: Historical Hulls (torpedoes from 1950), then this mod (KE and FF sizes)."""
    HULLS = 0x2800000

    def world(self, frigate):
        import hull_rules
        w = World(); w.vm.mem_map(self.HULLS, 0x10000)
        plans, strings = hull_rules.class_patches(BLOB, ff.BASE, self.HULLS)
        w.vm.mem_write(self.HULLS+0x8000, strings)
        for plan in plans: w.vm.mem_write(plan["address"], bytes.fromhex(plan["replacement"]))
        if frigate:
            w.vm.mem_map(ALLOCATION, 0x20000)
            info = ff.discover(bytes(w.vm.mem_read(ff.BASE, len(BLOB))), ff.BASE)   # with Historical Hulls in place
            image, plans = ff.build(ALLOCATION, info)
            w.vm.mem_write(ALLOCATION, image)
            for plan in plans: w.vm.mem_write(plan["address"], bytes.fromhex(plan["replacement"]))
        w.put(0x9F7328, STACK+0x200)
        return w

    def rule(self, w, kind, tons, year, torpedoes):
        """-> None when the design passes, else the message."""
        w.vm.mem_write(SHIP, bytes(0xA00)); w.put(SHIP+0x2C, tons); w.put(SHIP+ff.TYPE, kind, 1); w.put(STACK+0x200, year)
        w.stubs[0x9471E4] = lambda: torpedoes                                       # HasTorpedoes
        stops = (0x5E301E, 0x5E3084)
        hook = w.vm.hook_add(UC_HOOK_CODE, lambda vm, address, size, data: vm.emu_stop() if address in stops else None)
        try:
            for name, value in dict(ESI=SHIP, EBX=1, EBP=STACK+0x9000, ESP=STACK+0x8000).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+name], value)
            w.vm.emu_start(0x5E2FF8, 0, count=10000)
        finally: w.vm.hook_del(hook)
        if w.reg("EIP") == 0x5E3084: return None
        self.assertEqual(w.reg("EIP"), 0x5E301E)
        pointer = w.reg("EDX")
        return bytes(w.vm.mem_read(pointer, 2*w.get(pointer-4))).decode("utf-16-le")

    def test_modern_corvettes_may_carry_torpedoes(self):
        w = self.world(frigate=False)
        self.assertIn("before 1950 have no torpedoes", self.rule(w, ff.KE, 1500, 1949, True))
        self.assertEqual([self.rule(w, ff.KE, 1500, 1950, True), self.rule(w, ff.KE, 7000, 1990, False)], [None, None])
        self.assertIn("between 200 and 8000 tons", self.rule(w, ff.KE, 8100, 1990, False))

    def test_with_the_frigate_a_corvette_is_small_and_a_frigate_large(self):
        w = self.world(frigate=True)
        ke, frigate = (text.format(*size) for text, size in zip(ff.SIZE_TEXT, (ff.KE_SIZE, ff.FF_SIZE)))
        for kind, tons, year, torpedoes, expected in (
                (ff.KE, 8000, 1990, True, None), (ff.KE, 8001, 1990, False, ke), (ff.KE, 199, 1990, False, ke),
                (ff.FF, 1499, 1990, False, frigate), (ff.FF, 1500, 1990, True, None), (ff.FF, 12000, 1990, True, None),
                (ff.FF, 12001, 1990, False, frigate), (ff.FF, 4000, 1940, True, frigate), (ff.KE, 1000, 1940, True, ke)):
            self.assertEqual(self.rule(w, kind, tons, year, torpedoes), expected, (kind, tons, year, torpedoes))

    def test_the_type_suggestion_keeps_a_chosen_corvette_or_frigate_of_its_size(self):
        w = self.world(frigate=True)
        for kind, tons, suggested, kept in ((ff.FF, 5000, 9, ff.KE), (ff.FF, 13000, 9, 9), (ff.FF, 1000, 9, 9),
                                            (ff.KE, 2000, 9, ff.KE), (ff.KE, 9000, 4, 4), (9, 2000, 4, 4)):
            w.vm.mem_write(SHIP, bytes(0xA00)); w.put(SHIP+0x2C, tons); w.put(SHIP+ff.TYPE, kind, 1)
            w.run(0x5E22E4, 0x5E22E9, EAX=0x12345600 | suggested, ESI=SHIP, ECX=0x1111, EDX=0x2222)
            self.assertEqual((w.reg("EBX") & 0xFF, w.reg("ECX"), w.reg("EDX")), (kept, 0x1111, 0x2222), (kind, tons))
            self.assertEqual(bool(w.reg("EFLAGS") & 0x40), kept == 0x11)


if __name__ == "__main__":
    unittest.main()

"""Native size-lookup emulation and designer draw/menu ABI checks, without RTW3."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import designer_visuals as visuals
import hull_rules
import modern_research as audit

BASE, CODE, DATA, STACK, EXTRA = 0x301000, 0x10000000, 0x20000000, 0x30000000, 0x40000000
END = CODE+0xfff0
FORM, SHIP, GLOBE, POPUP, MENU = [DATA+i*0x2000 for i in range(1, 6)]


class VisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.info = visuals.discover(cls.blob, BASE)
        cls.product = visuals.build(CODE, cls.info)

    def machine(self, patched=True):
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        vm.mem_map(BASE, 0x800000); vm.mem_write(BASE, self.blob)
        vm.mem_map(CODE, 0x10000); vm.mem_map(DATA, 0x20000); vm.mem_map(STACK, 0x10000)
        for block in self.product["blocks"]:
            vm.mem_write(block["address"], bytes.fromhex(block["bytes"]))
        if patched:
            for item in self.product["patches"]:
                vm.mem_write(item["address"], bytes.fromhex(item["replacement"]))
        return vm

    @staticmethod
    def put(vm, address, value): vm.mem_write(address, struct.pack("<I", value & 0xffffffff))

    @staticmethod
    def get(vm, address): return int.from_bytes(vm.mem_read(address, 4), "little")

    def execute(self, vm, entry, eax=0, edx=0, ecx=0, stop=END):
        for reg, value in [(UC_X86_REG_EAX, eax), (UC_X86_REG_EDX, edx), (UC_X86_REG_ECX, ecx),
                           (UC_X86_REG_EBX, 0x11111111), (UC_X86_REG_ESI, 0x22222222),
                           (UC_X86_REG_EDI, 0x33333333), (UC_X86_REG_EBP, STACK+0x9000),
                           (UC_X86_REG_ESP, STACK+0x8000), (UC_X86_REG_EFLAGS, 0x246)]:
            vm.reg_write(reg, value & 0xffffffff)
        self.put(vm, STACK+0x8000, END)
        vm.emu_start(entry, stop, count=10000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP), stop)
        return vm.reg_read(UC_X86_REG_EAX)

    def test_native_range_exactly_preserved_for_every_class(self):
        old, new = self.machine(False), self.machine()
        for kind in range(16):
            for tons in (200, 2000, 5000, 10000, 15000, 25000, 50000, 89900, 90000, 99900, 100000, 100900):
                self.assertEqual(self.execute(new, self.info["scale"], kind, tons),
                                 self.execute(old, self.info["scale"], kind, tons), (kind, tons))
        self.assertEqual(new.reg_read(UC_X86_REG_EBX), 0x11111111)
        self.assertEqual(new.reg_read(UC_X86_REG_ESI), 0x22222222)
        self.assertEqual(new.reg_read(UC_X86_REG_EDI), 0x33333333)
        self.assertEqual(new.reg_read(UC_X86_REG_ESP), STACK+0x8004)

    def test_reproduces_original_cliff_and_extends_without_shrinking(self):
        old, new = self.machine(False), self.machine()
        self.assertEqual(self.execute(old, self.info["scale"], 0, 100900), 27)
        self.assertEqual(self.execute(old, self.info["scale"], 0, 101000), 20)
        for kind, anchor in enumerate(visuals.ANCHORS):
            self.assertEqual(self.execute(old, self.info["scale"], kind, 100900), anchor)
            values = [self.execute(new, self.info["scale"], kind, tons)
                      for tons in range(100900, 280001, 100)]
            self.assertEqual(values, sorted(values), kind)
            self.assertGreater(values[-1], anchor)
        self.assertEqual(self.execute(new, self.info["scale"], 0, 200000), 34)
        self.assertEqual(self.execute(new, self.info["scale"], 0, 280000), 38)

    def test_bounds_and_special_nonship_types_preserve_native_fallback(self):
        old, new = self.machine(False), self.machine()
        for kind in (12, 13, 14, 15, 127):
            for tons in (101000, 200000, 280000):
                self.assertEqual(self.execute(new, self.info["scale"], kind, tons),
                                 self.execute(old, self.info["scale"], kind, tons))
        self.assertEqual(self.execute(new, self.info["scale"], 0, 0x7fffffff), 38)
        for kind in (0, 1, 3):
            self.assertEqual(self.execute(new, self.info["scale"], kind, -1),
                             self.execute(old, self.info["scale"], kind, -1))

    def test_native_outline_builder_is_idempotent_and_keeps_fittings(self):
        vm = self.machine()
        vm.mem_write(SHIP, b"\x55"*0x1100)
        self.put(vm, SHIP+0x2c, 200000); vm.mem_write(SHIP+0x9d3, b"\x00")
        original = bytes(vm.mem_read(SHIP, 0x1100))
        for i in range(29):
            self.put(vm, 0xa78f60+i*8, i*10)
            self.put(vm, 0xa78f60+i*8+4, 200+i*20)
        self.execute(vm, self.info["reset_outline"], SHIP)
        first = bytes(vm.mem_read(SHIP, 0x1100))
        for i in range(29):
            self.assertEqual(self.get(vm, SHIP+0x5db+i*8), i*10)
            self.assertEqual(self.get(vm, SHIP+0x5df+i*8), (200+i*20)*34//20)
        self.assertEqual(first[:0x5db], original[:0x5db])
        self.assertEqual(first[0x5db+29*8:], original[0x5db+29*8:])
        self.execute(vm, self.info["reset_outline"], SHIP)
        self.assertEqual(bytes(vm.mem_read(SHIP, 0x1100)), first)

    def stubbed(self, vm, stubs):
        def callback(machine, address, size, _):
            if address not in stubs: return
            stubs[address]()
            sp = machine.reg_read(UC_X86_REG_ESP)
            machine.reg_write(UC_X86_REG_EIP, self.get(machine, sp))
            machine.reg_write(UC_X86_REG_ESP, sp+4)
        return vm.hook_add(UC_HOOK_CODE, callback)

    def test_designer_redraw_is_after_all_graphics_and_preserves_native_return(self):
        vm = self.machine(); calls = []
        def native():
            calls.append(("all graphics", vm.reg_read(UC_X86_REG_EAX), vm.reg_read(UC_X86_REG_EDX)))
            for reg, value in [(UC_X86_REG_EAX, 0xaabbccdd), (UC_X86_REG_ECX, 17), (UC_X86_REG_EDX, 19), (UC_X86_REG_EFLAGS, 0x247)]: vm.reg_write(reg, value)
        stubs = {self.info["render"]: native}
        def draw(name):
            def record():
                calls.append((name, vm.reg_read(UC_X86_REG_EAX), vm.reg_read(UC_X86_REG_EDX), vm.reg_read(UC_X86_REG_ECX)))
                vm.reg_write(UC_X86_REG_EAX, 0xdead); vm.reg_write(UC_X86_REG_EFLAGS, 0x202)
            return record
        for name in ("main_guns", "secondary_guns", "tertiary_guns", "equipment_guns", "missiles"): stubs[self.info[name]] = draw(name)
        self.stubbed(vm, stubs)
        self.execute(vm, self.product["locations"]["foreground"], SHIP, GLOBE)
        self.assertEqual(calls[0], ("all graphics", SHIP, GLOBE))
        # Visuals over the layers, funnels and torpedo mounts; missiles, then guns over the visuals. Casemates
        # (secondary pass 1) are not redrawn: the native picture draws them before superstructure layer 1.
        self.assertEqual([c[0] for c in calls[1:]], ["equipment_guns"]*6+["missiles", "main_guns", "secondary_guns",
                                                                         "tertiary_guns"])
        self.assertTrue(all(c[1:3] == (SHIP, GLOBE) for c in calls[1:]))
        self.assertEqual([c[3] for c in calls[1:7]], list(range(1, 7)))
        self.assertEqual([c[3] & 0xff for c in calls[8:10]], [0, 0])   # main and secondary turret/shield passes
        for reg, expected in [(UC_X86_REG_EAX, 0xaabbccdd), (UC_X86_REG_ECX, 17), (UC_X86_REG_EDX, 19),
                              (UC_X86_REG_EBX, 0x11111111), (UC_X86_REG_ESI, 0x22222222),
                              (UC_X86_REG_EDI, 0x33333333), (UC_X86_REG_EFLAGS, 0x247), (UC_X86_REG_ESP, STACK+0x8004)]:
            self.assertEqual(vm.reg_read(reg), expected)
        # No battle renderer is patched to expose hidden ships or their weapons.
        self.assertEqual([p["address"] for p in self.product["patches"] if p["label"].endswith("above graphics")], [0x5ce444])

    def test_menu_constructed_once_with_correct_owner_and_draft_reset_contract(self):
        vm = self.machine(); calls = []
        self.put(vm, FORM+0x7dc, POPUP); self.put(vm, POPUP+0x44, POPUP+0x100)
        self.put(vm, FORM+0xe6c, SHIP); vm.mem_write(FORM+0xe67, b"\x01"); self.put(vm, SHIP+0x2c, 200000)
        def create():
            self.assertEqual(vm.reg_read(UC_X86_REG_EAX), self.info["menu_vmt"])
            self.assertEqual(vm.reg_read(UC_X86_REG_ECX), FORM)
            calls.append("create"); vm.reg_write(UC_X86_REG_EAX, MENU)
        def caption():
            at = vm.reg_read(UC_X86_REG_EDX); size = self.get(vm, at-4)
            self.assertIn("keep fitted weapons", bytes(vm.mem_read(at, size*2)).decode("utf-16-le"))
        def add():
            self.assertEqual(vm.reg_read(UC_X86_REG_EAX), POPUP+0x100)
            self.assertEqual(vm.reg_read(UC_X86_REG_EDX), MENU)
        enabled = []
        def is_enabled(): enabled.append(vm.reg_read(UC_X86_REG_EDX) & 0xff)
        def reset():
            calls.append("reset"); self.assertEqual(vm.reg_read(UC_X86_REG_EAX), SHIP)
        def sync():
            calls.append("sync"); self.assertEqual(vm.reg_read(UC_X86_REG_EAX), FORM)
            self.assertEqual(vm.reg_read(UC_X86_REG_EDX) & 0xff, 1)
        def refresh(): calls.append("refresh")
        self.stubbed(vm, {self.info["menu_create"]: create, self.info["menu_caption"]: caption,
                          self.info["menu_add"]: add, self.info["menu_enabled"]: is_enabled,
                          self.info["reset_outline"]: reset, self.info["sync_preview"]: sync,
                          self.info["refresh"]: refresh})
        self.execute(vm, self.product["locations"]["ensure"], FORM)
        self.execute(vm, self.product["locations"]["ensure"], FORM)
        self.assertEqual(calls, ["create"]); self.assertEqual(enabled, [1, 1])
        self.assertEqual(self.get(vm, MENU+0x98), self.product["locations"]["reset"])
        self.assertEqual(self.get(vm, MENU+0x9c), FORM)
        self.execute(vm, self.product["locations"]["reset"], FORM)
        self.assertEqual(calls[-3:], ["reset", "sync", "refresh"])
        self.put(vm, SHIP+0x2c, 100900)
        self.execute(vm, self.product["locations"]["ensure"], FORM)
        self.assertEqual(enabled[-1], 0)
        calls.clear(); self.execute(vm, self.product["locations"]["reset"], FORM)
        self.assertEqual(calls, [])

    TEMPLATE = ("﻿[Data]\r\nDisplacement={tons}\r\nShipType={kind}\r\nBuildYear={year}\r\n[HullPoints]\r\n"
                "HullPoint0Angle=0\r\nHullPoint0Distance={bow}\r\n[Funnels]\r\nFunnel1Angle={year}\r\n"
                "Funnel1Distance=1200\r\nFunnel1Oval=1\r\n[Superstructure0]\r\nPoint0Angle={tons}\r\n"
                "Point0Distance=3000\r\nIsLine=1\r\nColor=$00C8C8C8\r\n[Superstructure5]\r\nPoint24Angle=-7\r\n"
                "Point24Distance=600\r\nColor=clLightgray\r\n")

    def templates(self):
        import tempfile
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        for name, kind, year, tons, bow in (("DD1", "DD", 1910, 1000, 5000), ("DD2", "DD", 1940, 2000, 6000),
                                            ("CA1", "CA", 1940, 10000, 9000), ("KE1", "KE", 1950, 1500, 5500),
                                            ("CV1", "CV", 1940, 20000, 9000)):
            (Path(folder.name)/f"{name}.tdf").write_text(self.TEMPLATE.format(kind=kind, year=year, tons=tons, bow=bow),
                                                        encoding="utf-8")
        cache = Path(folder.name)/"cache.bin"
        table, has = visuals.superstructure_templates(folder.name, cache)
        self.assertEqual(visuals.superstructure_templates(folder.name, cache), (table, has))   # from the cache
        return table, has

    def auto_machine(self, table, has):
        product = visuals.build(CODE, self.info, EXTRA, (table, has))
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        vm.mem_map(BASE, 0x800000); vm.mem_write(BASE, self.blob)
        vm.mem_map(CODE, 0x10000); vm.mem_map(DATA, 0x20000); vm.mem_map(STACK, 0x10000); vm.mem_map(EXTRA, 0x10000)
        for block in product["blocks"]: vm.mem_write(block["address"], bytes.fromhex(block["bytes"]))
        vm.mem_write(product["locations"]["templates"], table)
        self.put(vm, FORM+0xe6c, SHIP); vm.mem_write(FORM+0xe67, b"\x01")
        self.put(vm, product["locations"]["auto_state"], FORM)     # the menu item belongs to this form
        self.calls = []
        def default_hull(): self.calls.append("default hull"); self.put(vm, SHIP+0x5df, 5000)
        self.stubbed(vm, {self.info["reset_outline"]: default_hull,
                          self.info["sync_preview"]: lambda: self.calls.append("sync"),
                          self.info["refresh"]: lambda: self.calls.append("refresh")})
        return vm, product

    def test_templates_skip_carriers_and_serve_frigates_from_corvettes(self):
        table, has = self.templates()
        self.assertEqual(struct.unpack_from("<I", table)[0], 5)            # DD1, DD2, CA1, KE1 and KE1 as FF
        self.assertEqual([i for i in range(16) if has[i]], [3, 9, 10, 15])
        kind, year, tons, bow = struct.unpack_from("<B3xiii", table, 4+2*visuals.ENTRY)   # by name: CA1, DD1, DD2
        self.assertEqual((kind, year, tons, bow), (9, 1940, 2000, 6000))
        entry = table[4+2*visuals.ENTRY:4+3*visuals.ENTRY]
        self.assertEqual(struct.unpack_from("<ii", entry, 16), (2000, 3000))                 # layer 0 point 0
        self.assertEqual(struct.unpack_from("<ii", entry, 16+(5*25+24)*8), (-7, 600))       # layer 5 point 24
        self.assertEqual(entry[0x4C0:0x4C6], b"\x01\0\0\0\0\0")                            # IsLine
        self.assertEqual(struct.unpack_from("<6I", entry, 0x4C8), (0xC8C8C8,)+(0xC0C0C0,)*4+(0xD3D3D3,))
        self.assertEqual(struct.unpack_from("<2i", entry, 0x4E0), (1940, 1200)); self.assertEqual(entry[0x500], 1)

    def run_auto(self, vm, product, kind=9, tons=2100, year=1938, built=1912, bow=6600):
        self.calls.clear()
        vm.mem_write(SHIP+0x9d3, bytes([kind])); self.put(vm, SHIP+0x2c, tons); self.put(vm, SHIP+0xe4, built)
        self.put(vm, SHIP+0x5df, bow)
        self.put(vm, self.info["year"], DATA+0x1f000 if year else 0); self.put(vm, DATA+0x1f000, year)
        self.execute(vm, product["locations"]["auto"], FORM)
        for reg, expected in [(UC_X86_REG_EBX, 0x11111111), (UC_X86_REG_ESI, 0x22222222),
                              (UC_X86_REG_EDI, 0x33333333), (UC_X86_REG_ESP, STACK+0x8004)]:
            self.assertEqual(vm.reg_read(reg), expected)
        return list(self.calls)

    def test_auto_superstructure_takes_the_nearest_template_scaled_to_the_hull(self):
        vm, product = self.auto_machine(*self.templates())
        self.assertEqual(self.run_auto(vm, product), ["sync", "refresh"])
        # 1938, 2100 t: DD2 (1940, 2000 t) scores 2*4+4, DD1 (1910, 1000 t) 28*4+52
        self.assertEqual((self.get(vm, SHIP+0x10d), self.get(vm, SHIP+0x111)), (2000, 3000*6600//6000))
        self.assertEqual((self.get(vm, SHIP+0x10d+(5*25+24)*8) - (1 << 32), self.get(vm, SHIP+0x111+(5*25+24)*8)),
                         (-7, 600*6600//6000))
        self.assertEqual((self.get(vm, SHIP+0xe9), self.get(vm, SHIP+0xed)), (1940, 1200*6600//6000))
        self.assertEqual(bytes(vm.mem_read(SHIP+0x109, 1)), b"\x01")
        self.assertEqual(bytes(vm.mem_read(SHIP+0x5bd, 6)), b"\x01\0\0\0\0\0")
        self.assertEqual(self.get(vm, SHIP+0x5c3), 0xC8C8C8); self.assertEqual(self.get(vm, SHIP+0x5c3+20), 0xD3D3D3)
        # Outside a campaign the design's own build year decides: DD1.
        self.assertEqual(self.run_auto(vm, product, year=0), ["sync", "refresh"])
        self.assertEqual((self.get(vm, SHIP+0x10d), self.get(vm, SHIP+0xe9)), (1000, 1910))
        # No hull drawn yet: the class default outline first, then the scale from it.
        self.assertEqual(self.run_auto(vm, product, bow=0), ["default hull", "sync", "refresh"])
        self.assertEqual(self.get(vm, SHIP+0x111), 3000*5000//6000)
        # A frigate uses the corvette templates.
        self.run_auto(vm, product, kind=15, year=1950, tons=1500)
        self.assertEqual(self.get(vm, SHIP+0x10d), 1500)

    def test_auto_superstructure_menu_only_for_types_with_templates(self):
        vm, product = self.auto_machine(*self.templates())
        self.put(vm, FORM+0x7dc, POPUP); self.put(vm, POPUP+0x44, POPUP+0x100)
        enabled = []
        self.stubbed(vm, {self.info["menu_create"]: lambda: vm.reg_write(UC_X86_REG_EAX, MENU),
                          self.info["menu_caption"]: lambda: None, self.info["menu_add"]: lambda: None,
                          self.info["menu_enabled"]: lambda: enabled.append(vm.reg_read(UC_X86_REG_EDX) & 0xff)})
        self.put(vm, product["locations"]["auto_state"], 0)
        for kind in (9, 15, 5, 14, 3):
            vm.mem_write(SHIP+0x9d3, bytes([kind]))
            self.execute(vm, product["locations"]["auto_ensure"], FORM)
        self.assertEqual(enabled, [1, 1, 0, 0, 1])
        self.assertEqual(self.get(vm, MENU+0x98), product["locations"]["auto"])
        vm.mem_write(SHIP+0x9d3, b"\x05"); self.put(vm, SHIP+0x5df, 9000)   # a carrier: no template, no change
        self.execute(vm, product["locations"]["auto"], FORM)
        self.assertEqual(self.calls, [])
        # The popup builds both items.
        import capstone
        popup = next(b for b in product["blocks"] if b["name"] == "popup")
        calls = [int(i.op_str, 16) for i in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
                 bytes.fromhex(popup["bytes"]), popup["address"]) if i.mnemonic == "call"]
        self.assertEqual(calls, [product["locations"]["ensure"], product["locations"]["auto_ensure"]])

    def test_code_refusal_and_no_overlap_with_extended_machinery(self):
        for address, _, _ in visuals.WINDOWS:
            changed = bytearray(self.blob); changed[address-BASE] ^= 1
            with self.assertRaisesRegex(ValueError, "refuses changed"):
                visuals.discover(changed, BASE)
        ranges = [(b["address"], b["address"]+len(bytes.fromhex(b["bytes"]))) for b in self.product["blocks"]]
        _, class_code = hull_rules.classification_patch(self.blob, BASE, CODE)
        _, strings = hull_rules.class_patches(self.blob, BASE, CODE)
        start = CODE+hull_rules.SUGGESTION_OFFSET
        ranges += [(CODE+0x100, CODE+0x110), (start, start+len(class_code)), (CODE+0x8000, CODE+0x8000+len(strings)),
                   (CODE+0x1000, CODE+0x8000), (CODE+0xf000, CODE+0xf010)]
        ranges.sort()
        self.assertTrue(all(left[1] <= right[0] for left, right in zip(ranges, ranges[1:])))

    def test_aslr_relocated_native_build_is_accepted(self):
        delta = 0x200000
        relocated = bytearray(self.blob)
        for offset in audit.text_relocations():
            value = struct.unpack_from("<I", relocated, offset)[0]
            struct.pack_into("<I", relocated, offset, (value+delta) & 0xffffffff)
        info = visuals.discover(bytes(relocated), BASE+delta)
        self.assertEqual(info["scale"], self.info["scale"]+delta)
        self.assertEqual(info["sites"][1]["address"], 0x5ce444+delta)


if __name__ == "__main__": unittest.main(verbosity=2)

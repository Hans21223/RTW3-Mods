"""Super-superfiring turrets: the Add turret list, the placement and the main gun list labels, run against stand-in
game routines, and the sites found in the game code."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI,
                               UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP)
import mod_loader
import runtime_registry
import super_superfiring as feature

CODE, STUBS, DATA, STACK = 0x100000, 0x200000, 0x300000, 0x400000
DESIGNER, DESIGN, LIST, ITEMS, DIALOG, LISTBOX, STRINGS, VMT = (DATA+0x100, DATA+0x2000, DATA+0x3000, DATA+0x3100,
                                                                 DATA+0x4000, DATA+0x5000, DATA+0x6000, DATA+0x6100)
TURRETS, TEXT, FRAME, BACK = DATA+0x7000, DATA+0x9000, STACK+0x9000, STUBS+0x800
INFO = dict(add_item=STUBS, name=STUBS+0x10, location=STUBS+0x20, assign=STUBS+0x30, designer=DATA, limit=STUBS+0x50)
ITEMS_ADD = STUBS+0x40
SPOTS = {"A": 3000, "B": 2000, "X": 1500, "Y": 2500}     # default distances the location stand-in hands out


class SuperSuperfiringTests(unittest.TestCase):
    def setUp(self):
        self.vm = vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address in (CODE, STUBS, DATA, STACK):
            vm.mem_map(address, 0x10000)
        self.texts, data = feature.literals(CODE)
        vm.mem_write(CODE, data)
        self.put(DATA, DATA+0x80); self.put(DATA+0x80, DESIGNER)   # [0x9F7A34] holds the form variable's address
        self.put(DESIGNER+feature.DESIGN, DESIGN); self.put(DESIGN+feature.TURRETS, LIST)
        self.put(LIST+4, ITEMS)
        self.put(DIALOG+feature.POSITIONS, LISTBOX); self.put(LISTBOX+feature.ITEMS, STRINGS)
        self.put(STRINGS, VMT); self.put(VMT+0x3C, ITEMS_ADD)
        self.calls = []
        vm.hook_add(UC_HOOK_CODE, self.stand_in, begin=STUBS, end=STUBS+0x100)

    def put(self, address, value, size=4): self.vm.mem_write(address, (value & (1 << 8*size)-1).to_bytes(size, "little"))
    def get(self, address): return struct.unpack("<i", self.vm.mem_read(address, 4))[0]
    def reg(self, r): return self.vm.reg_read(r)

    def text(self, address):
        length = self.get(address-4)
        return self.vm.mem_read(address, 2*length).decode("utf-16-le")

    def stand_in(self, vm, address, size, data):
        eax, edx, sp = self.reg(UC_X86_REG_EAX), self.reg(UC_X86_REG_EDX), self.reg(UC_X86_REG_ESP)
        pop = 4
        if address == INFO["add_item"]:
            self.calls.append(("native line", eax, edx))
        elif address == ITEMS_ADD:
            self.calls.append(("added", self.text(edx)))
        elif address == INFO["name"]:
            self.calls.append(("name", eax & 0xFFFF))
        elif address == INFO["limit"]:
            vm.reg_write(UC_X86_REG_EAX, 7)                           # the game: 7 on any ship over 1,200 t
        elif address == INFO["assign"]:
            self.calls.append(("assign", eax, self.text(edx)))
        elif address == INFO["location"]:
            out = self.get(sp+4)
            self.put(out, 0); self.put(out+4, SPOTS[chr(edx & 0xFFFF)])
            self.calls.append(("spot", eax, chr(edx & 0xFFFF), self.reg(UC_X86_REG_ECX))); pop = 12
        else:
            return
        for r in (UC_X86_REG_ECX, UC_X86_REG_EDX):
            vm.reg_write(r, 0xDEAD)                                    # volatile
        vm.reg_write(UC_X86_REG_EIP, self.get(sp)); vm.reg_write(UC_X86_REG_ESP, sp+pop)

    def turrets(self, *letters):
        out = []
        for i, letter in enumerate(letters):
            turret = TURRETS+0x40*i; out.append(turret)
            self.vm.mem_write(turret, bytes(0x40)); self.put(turret+feature.CODE, ord(letter), 2)
            self.put(turret+feature.GUNS, 2); self.put(ITEMS+4*i, turret)
        self.put(LIST+8, len(letters))
        return out

    def emulate(self, start, stop, **registers):
        regs = dict(EAX=0, EBX=0x1111, ECX=0, EDX=0, ESI=0x2222, EDI=0x3333, EBP=FRAME, ESP=STACK+0x8000)
        regs.update(registers)
        for name, value in regs.items():
            self.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        self.vm.emu_start(start, stop, count=20000)
        self.assertEqual(self.reg(UC_X86_REG_EIP), stop)

    def call(self, code, at=CODE+0x800, **registers):
        """Calls code (built for at) as the patched call site would; returns once it comes back. Different code
        goes to a different address: the emulator keeps what it translated at an address."""
        self.vm.mem_write(at, code)
        sp = registers.pop("ESP", STACK+0x8000)
        self.put(sp-4, BACK)
        self.emulate(at, BACK, ESP=sp-4, **registers)

    def test_the_list_offers_bb_and_bbb_after_one_and_two_b_turrets(self):
        code = feature.list_thunk(CODE+0x800, INFO, "B", self.texts)
        for letters, added in (("AY", []), ("ABY", ["BB - Forward super-superfiring"]),
                               ("ABXBY", ["BBB - Forward super-superfiring"]), ("ABBBY", [])):
            self.calls = []; self.turrets(*letters)
            self.call(code, EAX=DIALOG, EDX=0x7777)
            self.assertEqual(self.calls, [("native line", DIALOG, 0x7777)] + [("added", t) for t in added], letters)
            self.assertEqual([self.reg(r) for r in (UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP)],
                             [0x1111, 0x2222, 0x3333, FRAME])
        code = feature.list_thunk(CODE+0xA00, INFO, "X", self.texts)
        self.calls = []; self.turrets("A", "X", "Y")
        self.call(code, at=CODE+0xA00, EAX=DIALOG, EDX=0x7777)
        self.assertEqual(self.calls[1:], [("added", "XX - Aft super-superfiring")])

    def place(self, line, letter, distance):
        turret = self.turrets(letter)[0]
        self.vm.mem_write(TEXT, line.encode("utf-16-le")+b"\0\0"); self.put(FRAME-0x10, TEXT)
        self.put(FRAME-0x18, 77); self.put(FRAME-0x14, distance)            # the default spot the game computed
        self.vm.mem_write(CODE+0xE00, feature.place_thunk(CODE+0xE00, INFO, BACK))
        self.calls = []
        self.emulate(CODE+0xE00, BACK, EBX=turret, ESI=DESIGNER)
        self.assertEqual((self.get(turret+0xA), self.reg(UC_X86_REG_ESP)), (77, STACK+0x8000))
        return self.get(turret+feature.DISTANCE)

    def test_a_copy_lands_one_or_two_spacings_towards_midships(self):
        self.assertEqual(self.place("B - Forward superimposed", "B", 2000), 2000)
        self.assertEqual(self.place("BB - Forward super-superfiring", "B", 2000), 1000)     # A 3000, B 2000
        self.assertEqual(self.calls, [("spot", DESIGN, "A", 2)])
        self.assertEqual(self.place("BBB - Forward super-superfiring", "B", 2000), 1)       # 0 would mean "no spot"
        self.assertEqual(self.place("XX - Aft super-superfiring", "X", 1500), 500)          # Y 2500, X 1500
        self.assertEqual(self.place("Y - Aft", "Y", 2500), 2500)

    def label(self, turret):
        sp = STACK+0x8000
        self.put(sp-4, 0x5EB); self.put(sp-8, 0xC0DE)                    # pushed: the letter's text, " - "
        self.calls = []
        self.call(feature.label_thunk(CODE+0xC00, INFO, self.texts), at=CODE+0xC00, EAX=self.get(turret+feature.CODE) & 0xFFFF,
                  EDX=FRAME-0x14, EBX=turret, ESP=sp-8)
        letter_text = self.get(sp-4)
        return (self.text(letter_text) if letter_text != 0x5EB else None), [c for c in self.calls if c[0] == "assign"]

    def test_the_second_and_third_b_and_x_read_bb_bbb_xx(self):
        b1, x1, b2, b3, x2, a = self.turrets("B", "X", "B", "B", "X", "A")
        self.assertEqual(self.label(b1), (None, []))
        self.assertEqual(self.label(b2), ("BB", [("assign", FRAME-0x14, "Forward super-superfiring")]))
        self.assertEqual(self.label(b3), ("BBB", [("assign", FRAME-0x14, "Forward super-superfiring")]))
        self.assertEqual(self.label(x2), ("XX", [("assign", FRAME-0x14, "Aft super-superfiring")]))
        self.assertEqual(self.label(a), (None, []))

    def test_the_sites_are_found_in_the_game_code(self):
        blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        info = feature.discover(blob, feature.BASE)
        self.assertEqual(info["sites"], {"list_B": 0x5B92CC, "list_X": 0x5B958E, "place": 0x5CCA32, "label": 0x5CCC27,
                                         "weight": 0x950C7D, "crowd": 0x94897A})
        self.assertEqual(info["designer"], 0x9F7A34)
        blocks, plans = feature.build(0x10000000, info)
        self.assertEqual([len(bytes.fromhex(p["replacement"])) for p in plans], [5, 5, 12, 5, 5, 5])
        self.assertEqual([bytes.fromhex(p["replacement"])[0] for p in plans], [0xE8, 0xE8, 0xE9, 0xE8, 0xE9, 0xE8])
        changed = bytearray(blob); changed[0x5CCA35-feature.BASE] ^= 1
        with self.assertRaisesRegex(ValueError, "changed native code: place"):
            feature.discover(bytes(changed), feature.BASE)

    def test_bb_and_bbb_weigh_one_and_two_more_barbette_steps(self):
        b1, b2, b3, x1, x2, a = self.turrets("B", "B", "B", "X", "X", "A")
        stray = TURRETS+0x400                                              # a turret not in the design's list yet
        self.vm.mem_write(stray, bytes(0x40)); self.put(stray+feature.CODE, ord("B"), 2)
        self.vm.mem_write(CODE+0x1000, feature.weight_thunk(CODE+0x1000, BACK))
        for turret, weight, expected in ((b1, 1100, 1100), (b2, 1100, 1200), (b3, 1100, 1300), (x1, 1050, 1050),
                                         (x2, 1050, 1100), (a, 1000, 1000), (stray, 1100, 1100)):
            self.put(turret+feature.WEIGHT, weight)
            self.emulate(CODE+0x1000, BACK, EBX=turret, EDI=DESIGN)
            self.assertEqual(self.get(turret+feature.WEIGHT), expected, hex(turret))
            self.assertEqual([self.reg(r) for r in (UC_X86_REG_EBX, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP)],
                             [turret, DESIGN, FRAME, STACK+0x8000])

    def test_bigger_ships_allow_more_centreline_mounts(self):
        code = feature.crowd_thunk(CODE+0x1200, INFO)
        for tons, allowed in ((5000, 7), (24999, 7), (25000, 8), (39999, 8), (40000, 9), (200000, 12)):
            self.put(DESIGN+feature.TONS, tons)
            self.call(code, at=CODE+0x1200, EAX=DESIGN)
            self.assertEqual(self.reg(UC_X86_REG_EAX), allowed, tons)

    def test_package_wiring(self):
        package = mod_loader.read_manifest(HERE.parent/"Library"/"super-superfiring-turret")
        self.assertEqual((package["runtime"]["adapter"], package["files"]), ("super-superfiring-turret", []))
        self.assertIn("super-superfiring-turret", [s["adapter"] for s in runtime_registry.plan(["super-superfiring-turret"])])


if __name__ == "__main__":
    unittest.main()

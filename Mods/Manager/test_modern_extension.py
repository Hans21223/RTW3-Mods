"""Per-ship extension data: guards, design-to-battle copy and save formats, on the native code."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import modern_extension as extension
import modern_research as modern

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
CODE, DATA, STACK, HEAP, STOP = 0x2000000, 0x1300000, 0x1500000, 0x1600000, 0x2010000
DESIGN_VMT, FIGHTING_VMT = extension.NATIVE["design_vmt"], extension.NATIVE["fighting_vmt"]
DESIGN, FIGHTING, OLD, LIST = DATA+0x1000, DATA+0x3000, DATA+0x6000, DATA+0x9000
DESIGN_SIZE, FIGHTING_SIZE = extension.CLASSES["design"][1], extension.CLASSES["fighting"][1]


class World:
    def __init__(self):
        self.vm = vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address, size in ((0, 0x1000), (0x300000, 0x800000), (DATA, 0x20000), (STACK, 0x10000),
                              (HEAP, 0x10000), (CODE, 0x30000)):
            vm.mem_map(address, size)
        vm.mem_write(0x301000, BLOB)
        details = modern.discover(BLOB, 0x301000)
        blocks, plans, _ = modern.build(CODE, details)
        for item in blocks+[dict(address=p["address"], bytes=p["replacement"]) for p in plans]:
            vm.mem_write(item["address"], bytes.fromhex(item["bytes"]))
        self.at = {b["name"][16:]: b["address"] for b in blocks if b["name"].startswith("Ship extension: ")}
        self.plans = {p["label"][16:]: p for p in plans if p["label"].startswith("Ship extension: ")}
        self.lines, self.heap = [], HEAP
        n = extension.NATIVE
        self.stubs = {n["int_to_str"]: self.int_to_str, n["clear"]: lambda: 0, DATA+0x8F00: self.add}
        self.put(LIST, DATA+0x8E00); self.put(DATA+0x8E00+0x3C, DATA+0x8F00)   # TStrings with Add
        vm.hook_add(UC_HOOK_CODE, self.boundary)

    def put(self, address, value, size=4): self.vm.mem_write(address, (value & (1 << 8*size)-1).to_bytes(size, "little"))
    def get(self, address, size=4): return int.from_bytes(self.vm.mem_read(address, size), "little")
    def reg(self, name): return self.vm.reg_read(globals()["UC_X86_REG_"+name])
    def text(self, pointer): return bytes(self.vm.mem_read(pointer, self.get(pointer-4)*2)).decode("utf-16-le")

    def int_to_str(self):
        text = str(self.reg("EAX")); body = struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"
        self.vm.mem_write(self.heap, body); self.put(self.reg("EDX"), self.heap+12); self.heap += 64; return 0

    def add(self): self.lines.append(self.text(self.reg("EDX"))); return 0

    def boundary(self, vm, address, size, unused):
        if address in self.stubs:
            result = self.stubs[address]()
            sp = vm.reg_read(UC_X86_REG_ESP)
            vm.reg_write(UC_X86_REG_EAX, result); vm.reg_write(UC_X86_REG_EIP, self.get(sp)); vm.reg_write(UC_X86_REG_ESP, sp+4)

    def ship(self, address, vmt, size, data=None, elevation=0):
        self.vm.mem_write(address, bytes(size+extension.EXTRA)); self.put(address, vmt); self.put(address+0x9A6, elevation, 1)
        if data is not None:
            self.put(address+size, data); self.put(address+size+4, extension.MAGIC ^ (address+size))
        return address

    def ext(self, obj):
        sp = STACK+0x8000; self.put(sp, STOP); self.vm.mem_write(STOP, b"\xc3")
        for name, value in (("EAX", obj), ("EDX", 0x1234), ("ESP", sp)): self.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        self.vm.emu_start(self.at["ext"], STOP, count=1000)
        assert self.reg("EDX") == 0x1234
        return self.reg("EAX")

    def run(self, start, stop, **registers):
        self.vm.reg_write(UC_X86_REG_ESP, STACK+0x8000)
        for name, value in registers.items(): self.vm.reg_write(globals()["UC_X86_REG_"+name], value)
        self.vm.emu_start(start, stop, count=10000)
        return self.reg("EIP") == stop


class ExtensionTests(unittest.TestCase):
    def test_ship_classes_allocate_extension_bytes_but_keep_their_instance_size(self):
        # The RTL frees a monitor it finds at InstanceSize-4 (0x30A73C): a guard there corrupted the heap.
        world = World(); block, requested = HEAP+0x8000, []
        self.assertEqual((world.get(0x9358BC), world.get(0x8E40F0)), (DESIGN_SIZE, FIGHTING_SIZE))
        self.assertEqual((world.get(0x9358E4), world.get(0x8E4118)), (world.at["new_instance"],)*2)
        def get_mem():   # FastMM hands back dirty memory
            requested.append(world.reg("EAX")); world.vm.mem_write(block, b"\xaa"*0x2000); return block
        world.stubs[extension.NATIVE["get_mem"]] = get_mem
        for vmt, size in ((DESIGN_VMT, DESIGN_SIZE), (FIGHTING_VMT, FIGHTING_SIZE)):
            sp = STACK+0x8000; world.put(sp, STOP); world.vm.mem_write(STOP, b"\xc3")
            world.vm.reg_write(UC_X86_REG_ESP, sp); world.vm.reg_write(UC_X86_REG_EAX, vmt)
            world.vm.emu_start(world.at["new_instance"], STOP, count=100000)
            self.assertEqual((world.reg("EAX"), requested[-1], world.get(block)), (block, size+extension.EXTRA, vmt))
            self.assertEqual((world.get(block+size-4), world.get(block+size), world.get(block+size+4)), (0, 0, 0))

    def test_constructors_stamp_a_guard_and_lookup_needs_it(self):
        world = World()
        world.ship(DESIGN, DESIGN_VMT, DESIGN_SIZE); world.put(DESIGN+DESIGN_SIZE, 0x777)
        sp = STACK+0x8000; world.put(sp, 0x1111); world.put(sp+4, 0x2222); world.put(sp+8, STOP); world.vm.mem_write(STOP, b"\xc3")
        world.vm.reg_write(UC_X86_REG_ESP, sp); world.vm.reg_write(UC_X86_REG_ESI, DESIGN)
        world.vm.emu_start(0x948D99, STOP, count=1000)                     # TDesignShip.Create exit
        self.assertEqual((world.reg("EAX"), world.reg("ESI"), world.reg("EBX")), (DESIGN, 0x1111, 0x2222))
        self.assertEqual(world.get(DESIGN+DESIGN_SIZE), 0)
        self.assertEqual(world.ext(DESIGN), DESIGN+DESIGN_SIZE)
        world.ship(FIGHTING, FIGHTING_VMT, FIGHTING_SIZE)
        self.assertTrue(world.run(0x8EC795, 0x8EC79A, EBX=FIGHTING))      # TFightingShip.Create exit
        self.assertEqual(world.ext(FIGHTING), FIGHTING+FIGHTING_SIZE)
        world.ship(OLD, DESIGN_VMT, DESIGN_SIZE)                           # allocated before the mod: no guard
        for obj in (OLD, 0, LIST):                                         # no guard, null, not a ship
            self.assertEqual(world.ext(obj), 0, hex(obj))

    def test_design_copy_carries_the_data_only_between_guarded_ships(self):
        world = World(); world.ship(DESIGN, DESIGN_VMT, DESIGN_SIZE, data=0x104)
        for target, guarded, expected in ((FIGHTING, True, 0x104), (OLD, False, 0x55)):
            world.ship(target, FIGHTING_VMT, FIGHTING_SIZE, data=0x55 if guarded else None)
            world.put(target+FIGHTING_SIZE, 0x55)
            frame = STACK+0xA000
            self.assertTrue(world.run(0x83C3A0, 0x83C3A5, ESI=DESIGN, EBX=target, EBP=frame))
            self.assertEqual(world.get(target+FIGHTING_SIZE), expected)

    def test_campaign_save_writes_elevation_with_data_and_reads_it_back(self):
        world = World(); parent = STACK+0xB000; world.put(parent-4, LIST)
        for elevation, data, line in ((1, 0, "1"), (0, 0, "0"), (2, 0, "2"), (1, 4, "1025"), (0, 0x104, "66560")):
            world.lines.clear(); world.ship(DESIGN, DESIGN_VMT, DESIGN_SIZE, data=data, elevation=elevation)
            sp = STACK+0x8000; world.put(sp, STOP); world.put(sp+4, parent); world.vm.mem_write(STOP, b"\xc3")
            for name, value in (("ESP", sp), ("EAX", elevation), ("EBX", DESIGN)): world.vm.reg_write(globals()["UC_X86_REG_"+name], value)
            world.vm.emu_start(world.at["big_save"], STOP, count=10000)
            self.assertEqual(world.lines, [line], (elevation, data))
        for value, elevation, data in ((1025, 1, 4), (66560, 0, 0x104), (2, 2, 0)):
            world.ship(DESIGN, DESIGN_VMT, DESIGN_SIZE, data=0xFFFF)
            for start, stop in ((0x94DC50, 0x94DC56), (0x9430EF, 0x9430F5), (0x8EDF10, 0x8EDF16)):
                self.assertTrue(world.run(start, stop, EAX=value, EBX=DESIGN))
                self.assertEqual((world.get(DESIGN+0x9A6, 1), world.get(DESIGN+DESIGN_SIZE)), (elevation, data))
        world.ship(OLD, DESIGN_VMT, DESIGN_SIZE); world.put(OLD+DESIGN_SIZE, 0x99)
        self.assertTrue(world.run(0x94DC50, 0x94DC56, EAX=1025, EBX=OLD))     # unguarded: elevation only
        self.assertEqual((world.get(OLD+0x9A6, 1), world.get(OLD+DESIGN_SIZE)), (1, 0x99))

    def test_design_files_push_elevation_with_data_and_switch_to_integer_keys(self):
        world = World()
        for elevation, data, pushed in ((2, 0, 2), (1, 0x104, 0x10401), (0, 0, 0)):
            world.ship(DESIGN, DESIGN_VMT, DESIGN_SIZE, data=data, elevation=elevation)
            self.assertTrue(world.run(0x93FFB6, 0x93FFBE, EDI=DESIGN))
            self.assertEqual(world.get(world.reg("ESP")), pushed)
        n = extension.NATIVE
        for name, target in (("big_load", n["int_reader"]), ("ini_save", n["ini_int_writer"]), ("ini_load", n["ini_int_reader"]),
                             ("ini_load2", n["ini_int_reader"]), ("big_save", world.at["big_save"])):
            plan = world.plans[name]; code = bytes.fromhex(plan["replacement"])
            self.assertEqual((code[0], plan["address"]+5+struct.unpack_from("<i", code, 1)[0]), (0xE8, target), name)


if __name__ == "__main__":
    unittest.main()

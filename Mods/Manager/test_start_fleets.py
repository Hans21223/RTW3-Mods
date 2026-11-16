"""Historical starting fleets: the hook in AIBuildInitialFleet, executed in the emulator."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import start_fleets as fleets

BLOB = (HERE/"native-designer-inspection.text.bin").read_bytes()
BASE, PAGE, DATA, STACK = 0x301000, 0x2000000, 0x1300000, 0x1500000
NATION, MAIN, NAME = DATA+0x1000, DATA+0x2000, DATA+0x3000


class FleetTests(unittest.TestCase):
    def run_site(self, nation, year, funds=5000):
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address, size in ((0x300000, 0x800000), (PAGE, 0x4000), (DATA, 0x10000), (STACK, 0x10000)): vm.mem_map(address, size)
        vm.mem_write(BASE, BLOB)
        info = fleets.discover(BLOB, BASE)
        blocks, plans = fleets.build(PAGE, info)
        plans = [p for p in plans if "historical" in p["label"]]
        for item in blocks+[dict(address=p["address"], bytes=p["replacement"]) for p in plans]:
            vm.mem_write(item["address"], bytes.fromhex(item["bytes"]))
        vm.mem_write(NAME, fleets.literal(nation)); vm.mem_write(NATION+fleets.NAME, struct.pack("<I", NAME+12))
        vm.mem_write(NATION+fleets.FUNDS, struct.pack("<i", funds))
        frame, sp = STACK+0x9000, STACK+0x8000
        vm.mem_write(frame-4, struct.pack("<i", year))
        built, stops = [], {info["tail"]: "tail", info["early"]: "early", info["late"]: "late"}

        def code(vm, address, size, _):
            if address == info["build"]:
                esp = vm.reg_read(UC_X86_REG_ESP)
                back, flag, count = struct.unpack("<3I", vm.mem_read(esp, 12))
                self.assertEqual((vm.reg_read(UC_X86_REG_EAX), vm.reg_read(UC_X86_REG_EDX), flag), (MAIN, NATION, 0))
                self.assertEqual(struct.unpack("<i", vm.mem_read(NATION+fleets.FUNDS, 4))[0], 0x3FFFFFFF)   # never short
                built.append((vm.reg_read(UC_X86_REG_ECX) & 0xFF, count))
                vm.mem_write(NATION+fleets.FUNDS, struct.pack("<i", 7))                                    # spent
                vm.reg_write(UC_X86_REG_ESP, esp+12); vm.reg_write(UC_X86_REG_EIP, back)
            elif address in stops:
                self.stop = stops[address]; vm.emu_stop()
        vm.hook_add(UC_HOOK_CODE, code)
        regs = {UC_X86_REG_EBX: NATION, UC_X86_REG_ESI: MAIN, UC_X86_REG_EDI: 0x4567, UC_X86_REG_EBP: frame, UC_X86_REG_ESP: sp}
        for reg, value in regs.items(): vm.reg_write(reg, value)
        vm.emu_start(info["site"], 0xFFFFFFFF, count=200000)
        for reg, value in regs.items(): self.assertEqual(vm.reg_read(reg), value)
        return self.stop, built, struct.unpack("<i", vm.mem_read(NATION+fleets.FUNDS, 4))[0]

    def test_a_listed_nation_gets_its_classes_then_the_native_tail_with_its_funds_back(self):
        for year in (2000, 1999):                                          # the builder may get the year before
            stop, built, funds = self.run_site("United States", year)
            self.assertEqual((stop, funds), ("tail", 5000))
            self.assertEqual(built, fleets.classes(fleets.FLEETS[2000]["United States"]))
            self.assertEqual(sum(n for kind, n in built if kind == fleets.CV), 12)
            self.assertTrue(all(0 < n <= fleets.CLASS for _, n in built))

    def test_other_nations_and_years_keep_the_native_builder(self):
        self.assertEqual(self.run_site("United States", 1935), ("late", [], 5000))
        self.assertEqual(self.run_site("USA", 1920), ("early", [], 5000))
        self.assertEqual(self.run_site("USA", 1960), ("late", [], 5000))               # a native name: not a bloc
        self.assertEqual(self.run_site("European NATO", 1960)[0], "tail")

    def test_a_nation_that_cannot_pay_for_its_home_battery_is_skipped(self):
        info = fleets.discover(BLOB, BASE)
        blocks, plans = fleets.build(PAGE, info)
        for index, (site, after) in enumerate(info["batteries"]):
            for fort in (0, DATA+0x4000):
                vm = Uc(UC_ARCH_X86, UC_MODE_32)
                for address, size in ((0x300000, 0x800000), (PAGE, 0x4000), (DATA, 0x10000)): vm.mem_map(address, size)
                vm.mem_write(BASE, BLOB)
                for item in blocks+[dict(address=p["address"], bytes=p["replacement"]) for p in plans]:
                    vm.mem_write(item["address"], bytes.fromhex(item["bytes"]))
                vm.reg_write(UC_X86_REG_EAX, fort)
                vm.emu_start(site, after if not fort else site+6, count=50)
                self.assertEqual(vm.reg_read(UC_X86_REG_EIP), site+6 if fort else after)
                self.assertEqual(vm.reg_read(UC_X86_REG_ESI), fort)
                if fort: self.assertEqual(vm.mem_read(fort+0x41, 1), b"\x01")

    def test_fleets_stay_inside_the_ai_ship_cap_and_name_real_nations(self):
        import coldwar_data as cold
        import superstates_data as blocs
        for year, nations in fleets.FLEETS.items():
            for nation, fleet in nations.items():
                self.assertLessEqual(sum(n for _, n in fleet), 200, (year, nation))
            self.assertEqual(set(nations), set(blocs.BY_NAME if year == 2000 else cold.BY_NAME))


if __name__ == "__main__": unittest.main(verbosity=2)

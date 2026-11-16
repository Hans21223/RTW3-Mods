"""Native oversized-DD fuel initialization; all writes stay inside Unicorn."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / "vendor"), str(HERE.parent / "CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
    UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP,
    UC_X86_REG_EIP,
    UC_X86_REG_FPCW,
)
import destroyer_fuel as fuel
import modern_research as audit
import weekly_runtime as rt

BASE = 0x301000
SHIP = 0x200000
YEAR = 0x204000
STACK = 0x108000
DONE = 0x100F00


class DestroyerFuelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE / "native-designer-inspection.text.bin").read_bytes()
        cls.plans, cls.info = fuel.discover(cls.blob, BASE, 10000)

    def machine(self, patched=True, limit=10000, recovery=False):
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        vm.mem_map(0x100000, 0x10000)
        vm.mem_map(SHIP, 0x10000)
        vm.mem_map(0x300000, 0x800000)
        vm.mem_write(BASE, self.blob)
        vm.mem_write(0x9F7328, struct.pack("<I", YEAR))
        if patched:
            plans, _ = fuel.discover(self.blob, BASE, limit)
            for plan in plans:
                vm.mem_write(plan["address"], bytes.fromhex(plan["replacement"]))
            if recovery:
                _, info = fuel.discover(self.blob, BASE, limit)
                built = fuel.build(0x100000, info)
                for block in built["blocks"]:
                    vm.mem_write(block["address"], bytes.fromhex(block["bytes"]))
                for plan in built["patches"]:
                    vm.mem_write(plan["address"], bytes.fromhex(plan["replacement"]))
        vm.reg_write(UC_X86_REG_FPCW, 0x37F)
        return vm

    def initialize(self, vm, tons, kind=9, year=1946, percent=100, prior_capacity=0, prior_fuel=0):
        before = bytearray(b"\xA5" * 0x1000)
        before[0x2C:0x30] = struct.pack("<I", tons)
        before[0x9D3] = kind
        before[0xA4C:0xA54] = struct.pack("<2I", prior_fuel, prior_capacity)
        vm.mem_write(SHIP, bytes(before))
        vm.mem_write(YEAR, struct.pack("<I", year))
        vm.mem_write(STACK, struct.pack("<I", DONE))
        values = {UC_X86_REG_EAX: SHIP, UC_X86_REG_EDX: percent,
                  UC_X86_REG_EBX: 0x12345678, UC_X86_REG_ECX: 0xABCDEF,
                  UC_X86_REG_ESI: 0x34567890, UC_X86_REG_EDI: 0x45678901,
                  UC_X86_REG_EBP: 0x109000, UC_X86_REG_ESP: STACK}
        for reg, value in values.items():
            vm.reg_write(reg, value)
        vm.emu_start(fuel.METHOD, DONE, count=1000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP), DONE)
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP), STACK + 4)
        for reg in (UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP):
            self.assertEqual(vm.reg_read(reg), values[reg])
        after = bytes(vm.mem_read(SHIP, len(before)))
        self.assertEqual(after[:0xA4C], bytes(before[:0xA4C]))
        self.assertEqual(after[0xA54:], bytes(before[0xA54:]))
        return struct.unpack_from("<2I", after, 0xA4C)

    def test_reproduces_7000t_zero_capacity_and_fixes_it(self):
        self.assertEqual(self.initialize(self.machine(False), 7000), (0, 0))
        self.assertEqual(self.initialize(self.machine(), 7000), (100000, 100000))
        self.assertEqual(self.initialize(self.machine(), 7000, percent=50), (50000, 100000))

    def test_native_curve_and_year_rules_preserved_through_5000t(self):
        original, patched = self.machine(False), self.machine()
        # Include every native transition and the reported original class cap.
        tons_values = sorted(set(range(200, 5001, 100)) | {
            200, 201, 209, 210, 309, 310, 409, 410, 509, 510,
            809, 810, 999, 1000, 3799, 3800, 3801, 4999, 5000})
        for tons in tons_values:
            for year in (1890, 1909, 1910, 1946):
                for percent in (0, 15, 50, 100):
                    with self.subTest(tons=tons, year=year, percent=percent):
                        self.assertEqual(self.initialize(patched, tons, year=year, percent=percent),
                                         self.initialize(original, tons, year=year, percent=percent))

    def test_extended_range_uses_last_native_band_and_starting_percentage(self):
        vm = self.machine()
        for tons in (5001, 5100, 7000, 9900, 10000):
            for percent in (0, 15, 50, 75, 100):
                self.assertEqual(self.initialize(vm, tons, percent=percent),
                                 (1000 * percent, 100000))
                self.assertEqual(self.initialize(vm, tons, year=1909, percent=percent),
                                 (660 * percent, 66000))

    def test_configured_ceiling_and_native_fallback_retained(self):
        for limit in (3800, 5000, 7000, 15000, 280000):
            vm = self.machine(limit=limit)
            ceiling = max(5000, limit)
            self.assertEqual(self.initialize(vm, ceiling), (100000, 100000))
            self.assertEqual(self.initialize(vm, ceiling+1), (0, 0))
            self.assertEqual(self.initialize(vm, ceiling+100), (0, 0))

    def test_other_native_ship_classes_unchanged(self):
        original, patched = self.machine(False), self.machine()
        for kind in range(16):
            if kind == 9:
                continue
            for tons in (200, 3800, 7000, 200000):
                for year in (1909, 1910, 1980):
                    self.assertEqual(self.initialize(patched, tons, kind, year, 75),
                                     self.initialize(original, tons, kind, year, 75))

    def test_unsupported_or_modified_native_code_refused(self):
        for offset in (fuel.METHOD-BASE, fuel.SITE-BASE, fuel.METHOD-BASE+fuel.SIZE-1,
                       fuel.STARTING_METHOD-BASE, fuel.STARTING_SITE-BASE,
                       fuel.STARTING_METHOD-BASE+fuel.STARTING_SIZE-1):
            blob = bytearray(self.blob)
            blob[offset] ^= 1
            with self.assertRaises(ValueError):
                fuel.discover(bytes(blob), BASE, 10000)
        for invalid in (True, 3799, 280001, 7000.0, "7000"):
            with self.assertRaises(ValueError):
                fuel.discover(self.blob, BASE, invalid)

    def test_aslr_relocated_build_discovered(self):
        delta = 0x400000
        relocated = bytearray(self.blob)
        for offset in audit.text_relocations():
            value = struct.unpack_from("<I", relocated, offset)[0]
            struct.pack_into("<I", relocated, offset, (value+delta) & 0xFFFFFFFF)
        plans, info = fuel.discover(bytes(relocated), BASE+delta, 15000)
        self.assertEqual(plans[0]["address"], fuel.SITE+delta)
        self.assertEqual(plans[1]["address"], fuel.STARTING_SITE+delta)
        self.assertEqual(bytes.fromhex(plans[0]["replacement"]),
                         b"\x2d"+struct.pack("<I", 15000-999))
        self.assertEqual(info["extended_max_tons"], 15000)

    def test_initialization_patch_and_loaded_recovery_metadata(self):
        self.assertEqual(len(self.plans), 2)
        self.assertEqual(self.plans[0]["address"], fuel.SITE)
        self.assertEqual(self.plans[1]["address"], fuel.STARTING_SITE)
        self.assertEqual(len(bytes.fromhex(self.plans[0]["replacement"])), 5)
        self.assertFalse(self.info["fuel_consumption_changed"])
        self.assertFalse(self.info["other_classes_changed"])
        self.assertTrue(self.info["existing_zero_capacity_battle_records_rewritten"])
        manifest = json.loads((HERE.parent/"Library/large-hulls/mod.json").read_text())
        self.assertGreaterEqual(tuple(map(int, manifest["version"].split("."))), (0, 3, 1))
        self.assertEqual(hashlib.sha256(self.blob[fuel.METHOD-BASE:fuel.METHOD-BASE+fuel.SIZE]).hexdigest(),
                         fuel.DIGEST)

    def loaded(self, vm, tons=10000, kind=9, current=0, capacity=0, year=1946,
               sunk=0, sinking=0, machinery=100, side=0):
        vm.mem_write(SHIP, b"\0"*0x1000)
        for offset, value in ((0x2c, tons), (0x38, 37), (0xA4C, current),
                              (0xA50, capacity), (0xB2A, machinery),
                              (0xB35, sinking), (0xA55, side)):
            vm.mem_write(SHIP+offset, struct.pack("<I", value))
        vm.mem_write(SHIP+0x9D3, bytes([kind]))
        vm.mem_write(SHIP+0xA9F, bytes([sunk]))
        vm.mem_write(YEAR, struct.pack("<I", year))

    def query(self, vm, method):
        vm.mem_write(STACK, struct.pack("<I", DONE))
        for reg, value in ((UC_X86_REG_EAX, SHIP), (UC_X86_REG_EDX, 27),
                           (UC_X86_REG_ECX, 0xABCDEF), (UC_X86_REG_EBX, 0x12345678),
                           (UC_X86_REG_ESI, 0x34567890), (UC_X86_REG_EDI, 0x45678901),
                           (UC_X86_REG_EBP, 0x109000), (UC_X86_REG_ESP, STACK)):
            vm.reg_write(reg, value)
        before = bytes(vm.mem_read(SHIP, 0x1000))
        vm.emu_start(method, DONE, count=10000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP), DONE)
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP), STACK+4)
        for reg, value in ((UC_X86_REG_EBX, 0x12345678), (UC_X86_REG_ESI, 0x34567890),
                           (UC_X86_REG_EDI, 0x45678901), (UC_X86_REG_EBP, 0x109000)):
            self.assertEqual(vm.reg_read(reg), value)
        after = bytes(vm.mem_read(SHIP, 0x1000))
        self.assertEqual(after[:0xA4C], before[:0xA4C])
        self.assertEqual(after[0xA54:], before[0xA54:])
        return vm.reg_read(UC_X86_REG_EAX), struct.unpack_from("<2I", after, 0xA4C)

    def test_loaded_10000t_dd_real_max_speed_no_longer_capped_at_five(self):
        vm = self.machine()
        self.loaded(vm)
        self.assertEqual(self.query(vm, 0x9040C0), (5, (0, 0)))
        vm = self.machine(recovery=True)
        self.loaded(vm)
        self.assertEqual(self.query(vm, 0x9040C0), (37, (100000, 100000)))
        # Recovery does not run again after a ship consumes fuel.
        vm.mem_write(SHIP+0xA4C, struct.pack("<I", 12345))
        self.assertEqual(self.query(vm, 0x9040C0), (37, (12345, 100000)))

    def test_loaded_recovery_preserves_genuine_empty_tanks_damage_and_other_classes(self):
        vm = self.machine(recovery=True)
        for args in (dict(current=0, capacity=100000), dict(current=1, capacity=0),
                     dict(tons=5000), dict(tons=10001), dict(kind=8),
                     dict(sunk=1), dict(sinking=1)):
            self.loaded(vm, **args)
            fuel_before = bytes(vm.mem_read(SHIP+0xA4C, 8))
            self.query(vm, 0x9040C0)
            self.assertEqual(bytes(vm.mem_read(SHIP+0xA4C, 8)), fuel_before)
        self.loaded(vm, machinery=50)
        self.assertEqual(self.query(vm, 0x9040C0), (18, (100000, 100000)))

    def test_loaded_fuel_display_repairs_before_native_percentage_calculation(self):
        vm = self.machine(recovery=True)
        for side in (0, 1):
            for year, capacity in ((1909, 66000), (1910, 100000), (1946, 100000)):
                self.loaded(vm, side=side, year=year)
                self.assertEqual(self.query(vm, 0x9145FC), (100, (capacity, capacity)))
                vm.mem_write(SHIP+0xA4C, struct.pack("<I", capacity//2))
                self.assertEqual(self.query(vm, 0x9145FC), (50, (capacity//2, capacity)))

    def test_range_wrapper_preserves_speed_argument_and_original_frame(self):
        vm = self.machine(recovery=True)
        self.loaded(vm)
        vm.mem_write(STACK, struct.pack("<I", DONE))
        for reg, value in ((UC_X86_REG_EAX, SHIP), (UC_X86_REG_EDX, 27),
                           (UC_X86_REG_ECX, 123), (UC_X86_REG_ESP, STACK),
                           (UC_X86_REG_EBP, 0x109000)):
            vm.reg_write(reg, value)
        vm.emu_start(0x914634, 0x91463A, count=1000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP), 0x91463A)
        self.assertEqual(vm.reg_read(UC_X86_REG_EAX), SHIP)
        self.assertEqual(vm.reg_read(UC_X86_REG_EDX), 27)
        self.assertEqual(vm.reg_read(UC_X86_REG_ECX), 123)
        self.assertEqual(vm.reg_read(UC_X86_REG_EBP), STACK-4)
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP), STACK-20)
        self.assertEqual(struct.unpack("<2I", vm.mem_read(SHIP+0xA4C, 8)), (100000, 100000))

    def test_loaded_recovery_code_tampering_refused(self):
        for _, address, _, _, _ in fuel.RECOVERY_WINDOWS:
            blob = bytearray(self.blob)
            blob[address-BASE+12] ^= 1
            with self.assertRaisesRegex(ValueError, "recovery refuses changed"):
                fuel.discover(bytes(blob), BASE, 10000)

    def test_loaded_recovery_executes_in_relocated_native_build(self):
        delta = 0x400000
        relocated = bytearray(self.blob)
        for offset in audit.text_relocations():
            value = struct.unpack_from("<I", relocated, offset)[0]
            struct.pack_into("<I", relocated, offset, (value+delta) & 0xFFFFFFFF)
        plans, info = fuel.discover(bytes(relocated), BASE+delta, 15000)
        vm = self.machine(False)
        vm.mem_map(0xB00000, 0x400000)
        vm.mem_write(BASE+delta, bytes(relocated))
        vm.mem_write(0x9F7328+delta, struct.pack("<I", YEAR))
        built = fuel.build(0x100000, info)
        for block in built["blocks"]:
            vm.mem_write(block["address"], bytes.fromhex(block["bytes"]))
        for plan in plans+built["patches"]:
            vm.mem_write(plan["address"], bytes.fromhex(plan["replacement"]))
        for tons in (5001, 7000, 10000, 15000):
            self.loaded(vm, tons=tons)
            self.assertEqual(self.query(vm, 0x9040C0+delta), (37, (100000, 100000)))

    def starting(self, vm, percent=95, range_=3, extra=1, raw=False):
        # Execute the complete second initializer, including native range and
        # starting-percentage arithmetic. Only external string/log UI is stubbed.
        try: vm.mem_map(0, 0x1000)
        except Exception: pass  # A reused test VM already has its SEH chain.
        for address in (0x9045A8, 0x328C80, 0x30B93C): vm.mem_write(address, b"\xc3")
        vm.mem_write(0x30C71C, b"\xc2\x0c\x00")
        vm.mem_write(0x307834, b"\xb8\x63\x00\x00\x00\xc3")
        vm.mem_write(SHIP+0x9AD, bytes([range_]))
        vm.mem_write(STACK, struct.pack("<II", DONE, int(raw)))
        for reg, value in ((UC_X86_REG_EAX, SHIP), (UC_X86_REG_EDX, percent),
                           (UC_X86_REG_ECX, extra), (UC_X86_REG_ESP, STACK),
                           (UC_X86_REG_EBP, 0x109000), (UC_X86_REG_EBX, 0x1234),
                           (UC_X86_REG_ESI, 0x2345), (UC_X86_REG_EDI, 0x3456)):
            vm.reg_write(reg, value)
        vm.emu_start(fuel.STARTING_METHOD, DONE, count=10000)
        self.assertEqual(vm.reg_read(UC_X86_REG_EIP), DONE)
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP), STACK+8)
        for reg,value in ((UC_X86_REG_EBP,0x109000),(UC_X86_REG_EBX,0x1234),
                          (UC_X86_REG_ESI,0x2345),(UC_X86_REG_EDI,0x3456)):
            self.assertEqual(vm.reg_read(reg),value)
        return struct.unpack("<2i", vm.mem_read(SHIP+0xA4C,8))

    def test_second_initializer_reproduces_actual_180_million_capacity_overflow(self):
        old=self.machine();self.loaded(old,current=100000,capacity=100000)
        old.mem_write(fuel.STARTING_SITE,b"\x2d\xa1\x0f\x00\x00")
        current,capacity=self.starting(old)
        self.assertEqual(capacity,180000000)
        self.assertLess(current,0)
        fixed=self.machine();self.loaded(fixed,current=100000,capacity=100000)
        self.assertEqual(self.starting(fixed),(171000,180000))

    def test_second_initializer_native_sizes_ranges_percentages_and_raw_fuel_preserved(self):
        old=self.machine(False);fixed=self.machine()
        for tons in (200,500,1000,3800,5000):
            for range_ in range(4):
                for extra in (0,1):
                    for percent,raw in ((0,False),(50,False),(95,False),(100,False),(12345,True)):
                        self.loaded(old,tons=tons,current=100000,capacity=100000)
                        self.loaded(fixed,tons=tons,current=100000,capacity=100000)
                        self.assertEqual(self.starting(fixed,percent,range_,extra,raw),
                                         self.starting(old,percent,range_,extra,raw))

    def test_second_initializer_extended_sizes_ignore_prior_capacity_and_remain_finite(self):
        vm=self.machine()
        for tons in (5001,7000,10000):
            for prior in (0,100000,180000000):
                self.loaded(vm,tons=tons,current=0,capacity=prior)
                self.assertEqual(self.starting(vm),(171000,180000))
        # Repeated calls recalculate instead of multiplying an existing capacity.
        self.assertEqual(self.starting(vm),(171000,180000))
        self.assertEqual(self.starting(vm,12345,raw=True),(12345,180000))

    def test_second_initializer_other_classes_and_configured_limits(self):
        old=self.machine(False);fixed=self.machine()
        for kind in range(16):
            if kind==9:continue
            for range_ in range(4):
                for vm in (old,fixed):self.loaded(vm,kind=kind,capacity=100000)
                self.assertEqual(self.starting(fixed,range_=range_),self.starting(old,range_=range_))
        for limit in (15000,280000):
            vm=self.machine(limit=limit);self.loaded(vm,tons=limit,capacity=100000)
            self.assertEqual(self.starting(vm),(171000,180000))

    def test_loaded_inflated_capacity_repaired_once_with_native_speed_and_percentage(self):
        vm=self.machine(recovery=True)
        for current,expected in ((0,180000),(-798691,180000),(9100654,180000),(65000,65000)):
            self.loaded(vm,current=current&0xFFFFFFFF,capacity=180000000)
            self.assertEqual(self.query(vm,0x9040C0),(37,(expected,180000)))
            vm.mem_write(SHIP+0xA4C,struct.pack("<I",0))
            self.assertEqual(self.query(vm,0x9040C0),(5,(0,180000)))
        self.loaded(vm,current=0,capacity=120000000)
        self.assertEqual(self.query(vm,0x9145FC),(100,(120000,120000)))

    def test_inflated_recovery_rejects_other_sizes_damage_states_and_nonmatching_capacity(self):
        vm=self.machine(recovery=True)
        for args in (dict(tons=5000),dict(tons=10001),dict(kind=8),dict(sunk=1),dict(sinking=1),
                     dict(capacity=180000),dict(capacity=180000001),dict(capacity=120000001)):
            fields=dict(current=0,capacity=180000000);fields.update(args);self.loaded(vm,**fields)
            before=bytes(vm.mem_read(SHIP+0xA4C,8));self.query(vm,0x9040C0)
            self.assertEqual(bytes(vm.mem_read(SHIP+0xA4C,8)),before)

    def test_recovery_blocks_fit_unused_hull_allocation(self):
        import designer_visuals
        import destroyer_torpedoes
        allocation = 0x10000000
        built = fuel.build(allocation, self.info)
        visuals = designer_visuals.build(allocation, designer_visuals.discover(self.blob, BASE))
        torpedoes = destroyer_torpedoes.build(allocation, destroyer_torpedoes.discover(self.blob, BASE, 10000))
        ranges = [(b["address"], b["address"]+len(bytes.fromhex(b["bytes"])))
                  for b in built["blocks"]+visuals["blocks"]+torpedoes["blocks"]]
        ranges += [(allocation, allocation+0x400),
                   (allocation+0x1000, allocation+0x8000),
                   (allocation+0x8000, allocation+0x9000)]
        ranges.sort()
        for left,right in zip(ranges,ranges[1:]): self.assertLessEqual(left[1],right[0])
        self.assertLessEqual(ranges[-1][1], allocation+65536)


if __name__ == "__main__":
    unittest.main()

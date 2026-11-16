"""Read-only research capacity investigation for the retained RTW3 build.

Executes native lookup and INI serialization loops in Unicorn with synthetic
data. No game attachment, process writes, campaign edits or mod activation.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(HERE / "vendor"), str(HERE.parent / "CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
    UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP,
    UC_X86_REG_EIP,
)
import modern_research as audit
import modern_tree as tree
import weekly_runtime as rt

BASE = 0x301000
NATION = 0x200000
STACK = 0x108000
FRAME = 0x109000
DONE = 0x100F00
AREA_COUNT = 0xA1C924
TABLE = 0xA1C9F0
FLAGS = 0x336
NATION_START = 0x325
NATION_STRIDE = 53
TABLE_STRIDE = 1044
LEVELS = 36
CAPACITY = 25


def u32(vm, address):
    return struct.unpack("<I", vm.mem_read(address, 4))[0]


def put(vm, address, value):
    vm.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))


def machine(blob, count):
    vm = Uc(UC_ARCH_X86, UC_MODE_32)
    for address, size in ((0, 0x1000), (0x100000, 0x20000),
                          (NATION, 0x10000), (0x300000, 0x800000),
                          (0x1000000, 0x400000)):
        vm.mem_map(address, size)
    vm.mem_write(BASE, blob)
    put(vm, AREA_COUNT, count)
    for reg, value in ((UC_X86_REG_EAX, NATION), (UC_X86_REG_EBX, 0xBEEF),
                       (UC_X86_REG_ESI, 0x1234), (UC_X86_REG_EDI, 0x5678),
                       (UC_X86_REG_EBP, FRAME), (UC_X86_REG_ESP, STACK)):
        vm.reg_write(reg, value)
    put(vm, STACK, DONE)
    return vm


def call(vm, address, edx=0):
    preserved = {reg: vm.reg_read(reg) for reg in (
        UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP)}
    before = bytes(vm.mem_read(NATION, 0x10000))
    vm.reg_write(UC_X86_REG_EAX, NATION)
    vm.reg_write(UC_X86_REG_EDX, edx)
    vm.reg_write(UC_X86_REG_ECX, 0)
    vm.reg_write(UC_X86_REG_ESP, STACK)
    put(vm, STACK, DONE)
    vm.emu_start(address, DONE, count=2000000)
    assert vm.reg_read(UC_X86_REG_EIP) == DONE
    assert vm.reg_read(UC_X86_REG_ESP) == STACK + 4
    assert all(vm.reg_read(reg) == value for reg, value in preserved.items())
    assert bytes(vm.mem_read(NATION, 0x10000)) == before
    return vm.reg_read(UC_X86_REG_EAX)


def lookup_probes(blob):
    has = rt.method_address(blob, BASE, "HasResearchId")
    highest = rt.method_address(blob, BASE, "GetHighestResearchLevel")
    count = rt.method_address(blob, BASE, "CountResearchLevels")
    results = []
    for regular in (22, 23, 24):
        vm = machine(blob, regular)
        for area in range(regular):
            for level in range(LEVELS):
                ident = 10000 + area * 100 + level
                put(vm, TABLE + area * TABLE_STRIDE + level * 29 + 21, ident)
                vm.mem_write(NATION + FLAGS + area * NATION_STRIDE + level, b"\1")
        for area in range(regular):
            for level in (0, 35):
                ident = 10000 + area * 100 + level
                assert call(vm, has, ident) == 1
                vm.mem_write(NATION + FLAGS + area * NATION_STRIDE + level, b"\0")
                assert call(vm, has, ident) == 0
                vm.mem_write(NATION + FLAGS + area * NATION_STRIDE + level, b"\1")
            assert call(vm, highest, area) == 35
            assert call(vm, count, area) == 36
        assert call(vm, has, 999999) == 0
        for calibre in range(2, 21):
            put(vm, NATION + 0x11D + calibre * 4, 1)
        assert call(vm, count, regular) == 57
        results.append(dict(regular_areas=regular,
                            owned_and_unowned_ids_checked=regular * 4,
                            all_regular_counts=36, highest_slot=35,
                            gun_area_index=regular, gun_quality=1,
                            gun_count=57, passed=True))
    return results


class IniHarness:
    """Minimal Delphi string/INI boundary; native loops remain unmodified."""
    def __init__(self, vm, values=None):
        self.vm = vm
        self.heap = 0x1001000
        self.values = {} if values is None else dict(values)
        self.calls = 0
        self.handlers = {
            0x328C80: self.int_string, 0x30C71C: self.concat_many,
            0x30C694: self.concat_two, 0x586DF0: self.write,
            0x586EA4: self.write, 0x586FC8: self.read, 0x58738C: self.read,
        }
        vm.hook_add(UC_HOOK_CODE, self.hook)

    def string(self, value):
        if not value:
            return 0
        encoded = value.encode("utf-16-le")
        at = self.heap
        self.heap += (12 + len(encoded) + 15) & ~15
        assert self.heap < 0x1400000
        self.vm.mem_write(at, struct.pack("<iI", -1, len(value)) + encoded + b"\0\0")
        return at + 8

    def text(self, pointer):
        return (bytes(self.vm.mem_read(pointer, u32(self.vm, pointer - 4) * 2))
                .decode("utf-16-le") if pointer else "")

    def finish(self, argument_bytes=0):
        sp = self.vm.reg_read(UC_X86_REG_ESP)
        self.vm.reg_write(UC_X86_REG_EIP, u32(self.vm, sp))
        self.vm.reg_write(UC_X86_REG_ESP, sp + 4 + argument_bytes)

    def hook(self, vm, address, size, unused):
        handler = self.handlers.get(address)
        if handler:
            handler()

    def int_string(self):
        value = self.vm.reg_read(UC_X86_REG_EAX)
        put(self.vm, self.vm.reg_read(UC_X86_REG_EDX), self.string(str(value)))
        self.finish()

    def concat_many(self):
        count = self.vm.reg_read(UC_X86_REG_EDX)
        sp = self.vm.reg_read(UC_X86_REG_ESP)
        text = "".join(self.text(u32(self.vm, sp + 4 + i * 4))
                       for i in reversed(range(count)))
        put(self.vm, self.vm.reg_read(UC_X86_REG_EAX), self.string(text))
        self.finish(count * 4)

    def concat_two(self):
        value = self.text(self.vm.reg_read(UC_X86_REG_EDX)) + self.text(self.vm.reg_read(UC_X86_REG_ECX))
        put(self.vm, self.vm.reg_read(UC_X86_REG_EAX), self.string(value))
        self.finish()

    def write(self):
        key = self.text(self.vm.reg_read(UC_X86_REG_ECX))
        value = u32(self.vm, self.vm.reg_read(UC_X86_REG_ESP) + 4)
        assert key not in self.values
        self.values[key] = value
        self.calls += 1
        self.finish(4)

    def read(self):
        key = self.text(self.vm.reg_read(UC_X86_REG_ECX))
        assert key in self.values, key
        self.vm.reg_write(UC_X86_REG_EAX, self.values[key])
        self.calls += 1
        self.finish(4)


def persistence_probe(blob, regular):
    vm = machine(blob, regular)
    expected = bytearray()
    for area in range(regular + 1):
        record = bytes([area % 2]) + struct.pack("<4I", 1 + area % 3, 17 + area,
                                                area % 36, 100000 + area)
        record += bytes((area + level) % 2 for level in range(36))
        assert len(record) == NATION_STRIDE
        expected.extend(record)
    vm.mem_write(NATION + NATION_START, bytes(expected))
    ini = IniHarness(vm)
    vm.reg_write(UC_X86_REG_EBX, NATION)
    vm.reg_write(UC_X86_REG_ESI, 0x210000)
    vm.reg_write(UC_X86_REG_EDI, 0)  # Nation0 section
    vm.emu_start(0x724F0E, 0x72520C, count=500000)
    assert vm.reg_read(UC_X86_REG_EIP) == 0x72520C
    assert vm.reg_read(UC_X86_REG_ESP) == STACK
    assert ini.calls == (regular + 1) * 41
    assert f"Research{regular}Level35" in ini.values
    other = machine(blob, regular)
    other.mem_write(NATION + NATION_START - 8, b"\xA5" * 8)
    other.mem_write(NATION + NATION_START + len(expected), b"\xA5" * 8)
    restore = IniHarness(other, ini.values)
    put(other, FRAME - 4, restore.string("Nation0"))
    other.reg_write(UC_X86_REG_EBX, NATION)
    other.reg_write(UC_X86_REG_ESI, 0x210000)
    other.emu_start(0x7206E2, 0x7208DD, count=500000)
    assert other.reg_read(UC_X86_REG_EIP) == 0x7208DD
    assert other.reg_read(UC_X86_REG_ESP) == STACK
    assert restore.calls == ini.calls
    assert bytes(other.mem_read(NATION + NATION_START, len(expected))) == bytes(expected)
    assert bytes(other.mem_read(NATION + NATION_START - 8, 8)) == b"\xA5" * 8
    assert bytes(other.mem_read(NATION + NATION_START + len(expected), 8)) == b"\xA5" * 8
    return dict(regular_areas=regular, serialized_records=regular + 1,
                fields_round_tripped=ini.calls, byte_exact_research_round_trip=True,
                neighboring_bytes_preserved=True, native_file_io_executed=False)


def capacity_rows(raw):
    return [dict(area=a["area"], name=a["name"], used=len(a["rows"]),
                 free=36 - len(a["rows"])) for a in tree.parse(raw)]


def run():
    if not __debug__:
        raise ValueError("Run this audit without Python optimization; its checks must execute.")
    snapshot = HERE / "native-designer-inspection.text.bin"
    blob = snapshot.read_bytes()
    details = audit.discover(blob, BASE)  # authenticates audited research bodies
    assert details["max_levels"] == LEVELS
    assert details["table_stride"] == TABLE_STRIDE
    assert details["nation_stride"] == NATION_STRIDE
    # Native table names and pictures each reserve 25 pointers. The following
    # table contains 25 records of 36 technologies each; loader allows <=24
    # ordinary branches and appends gun manufacture at that count index.
    assert (0xA1C98C - 0xA1C928) // 4 == CAPACITY
    assert (TABLE - 0xA1C98C) // 4 == CAPACITY
    assert TABLE_STRIDE == LEVELS * 29
    assert NATION_STRIDE == 17 + LEVELS
    assert blob[0x7605B8 - BASE:0x7605BB - BASE] == b"\x83\xFE\x23"
    assert blob[0x760813 - BASE:0x76081A - BASE] == bytes.fromhex("833d24c9a10018")
    vanilla = capacity_rows(tree.BASELINE.read_bytes())
    active_raw = (ROOT / "Data/ResearchAreas3.dat").read_bytes()
    modern_raw, nodes = tree.render()
    modern = capacity_rows(modern_raw)
    report = dict(
        schema=1, scope="local authenticated RTW3 1.01.44 retained native image",
        snapshot_sha256=hashlib.sha256(blob).hexdigest(),
        executable_sha256=hashlib.sha256((ROOT / "RTW3.exe").read_bytes()).hexdigest(),
        snapshot_code_base=hex(BASE),
        layout=dict(regular_areas=22, max_regular_areas=24,
                    total_reserved_branch_records=25, current_gun_index=22,
                    levels_per_area=36, table_record_bytes=29,
                    table_area_bytes=TABLE_STRIDE, nation_area_bytes=NATION_STRIDE,
                    nation_metadata_bytes=17, nation_flag_base=hex(FLAGS),
                    nation_record_base=hex(NATION_START),
                    global_count=hex(AREA_COUNT), table_base=hex(TABLE)),
        vanilla=dict(technologies=sum(a["used"] for a in vanilla),
                     empty_slots=sum(a["free"] for a in vanilla), areas=vanilla),
        active_data=dict(sha256=hashlib.sha256(active_raw).hexdigest(),
                         technologies=sum(a["used"] for a in capacity_rows(active_raw)),
                         equals_vanilla=active_raw == tree.BASELINE.read_bytes()),
        modern_package=dict(technologies=sum(a["used"] for a in modern),
                            added=len(nodes), empty_slots=sum(a["free"] for a in modern),
                            empty_excluding_airships=sum(a["free"] for a in modern if a["area"] != 16),
                            areas=modern),
        capacity_totals=dict(existing_regular_slots=22 * 36,
                             expanded_regular_slots=24 * 36,
                             extra_slots_from_two_branches=72,
                             modern_to_24_area_full_capacity=24 * 36 - sum(a["used"] for a in modern)),
        lookup_probes=lookup_probes(blob),
        persistence_probes=[persistence_probe(blob, n) for n in (22, 23, 24)],
        overflow=dict(flag_36_aliases_next_branch_advantage=True,
                      table_row_36_aliases_next_branch_row_zero=True,
                      raising_loop_limit_alone_safe=False),
        native_ui_campaign_and_ai_gameplay_verified=False,
        executable_modified=False, personal_saves_modified=False,
        runtime_patches_installed=False, mod_selections_changed=False,
        persistence_boundary="native research serialization loops; Delphi string and INI calls mocked; no disk save/load",
    )
    target = HERE / "research-slot-audit.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps({key: result[key] for key in (
        "layout", "capacity_totals", "lookup_probes", "persistence_probes",
        "native_ui_campaign_and_ai_gameplay_verified", "personal_saves_modified")}, indent=2))

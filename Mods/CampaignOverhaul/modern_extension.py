"""Per-ship extension data for modern systems (laser mounts, hypersonic VLS missiles).

RTW3's ship classes have no spare saved field, so TDesignShip and TFightingShip
objects get 8 bytes after their native fields: a data dword and a guard (MAGIC
xor its own address) written by the constructors. The classes' NewInstance
slots allocate and zero those bytes; InstanceSize stays native, because the
Delphi RTL keeps a hidden monitor field at InstanceSize-4 and frees whatever it
finds there (a guard in that slot corrupted the heap). Objects allocated before
the mod attached have no valid guard and are never written. The design-to-battle
copy carries the data.

Saving rides on the main battery's Increased elevation key, which this module
also switches from Boolean to integer (railguns store 2 there): files hold
elevation | data << 8, so ships without extension data save exactly as before.
The elevation value is 0..2, so the integer's bits 2-7 carry data bits 24-29
(point_defence); older files have zeros there.
Every ship also gets a third and a fourth dword, zeroed with the object and never
saved or copied: a battle ship's state. The third (BATTLE_PD) counts the missiles
its SeaRAM and gun-missile mounts fired (low and high word); the fourth
(BATTLE_FLAGS) holds the anti-torpedo torpedoes fired (low byte) and this battle's
nuclear shell and strike marks (modern_navy, nuclear_strike).
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct
import weekly_runtime as rt
from hull_rules import patch

BASE = 0x301000
MAGIC = 0x5854584D
CLASSES = dict(design=(0x9358F0, 0xBC8), fighting=(0x8E4124, 0xE10))   # VMT, native InstanceSize
EXTRA = 16                                     # data, guard, two battle dwords: allocated past InstanceSize
BATTLE_PD, BATTLE_FLAGS = 8, 12                # offsets of the battle dwords from the data dword
LASERS_MASK, HYPERSONIC_BIT, SUPER_HEAVY_BIT = 0xFF, 0x100, 0x200      # data dword layout
SECONDARY_RAIL_BIT, TERTIARY_RAIL_BIT = 0x400, 0x800                   # railgun secondary/tertiary batteries
# Bits 16-23 are extra generators (modern_railgun). Bits 12-13 were battle flags until 1.46.0 (never saved).
SPARE_SHIFT, SEARAM_SHIFT, GUN_MISSILE_SHIFT, RAM_BIT = 14, 24, 26, 1 << 29   # point_defence: 2, 2 and 3 bits
ATT_SHIFT = 12                                 # point_defence: anti-torpedo torpedo launchers, 2 bits
HIGH_SHIFT, HIGH_MASK = 24, 0x3F               # data bits 24-29: saved in the integer's bits 2-7

WINDOWS = (
    (0x9358E4, 4, "c28b879758b381be63f5af692b2d122f5baf42e9f8bd3e70dd75a0a811da1414"),   # TDesignShip NewInstance slot
    (0x8E4118, 4, "c28b879758b381be63f5af692b2d122f5baf42e9f8bd3e70dd75a0a811da1414"),   # TFightingShip NewInstance slot
    (0x3099B4, 0x16, "e0c60bb81a60809556580ee626396bf9117ab2c836afeaf0bed3585f374d3717"),   # TObject.NewInstance
    (0x948D84, 0x1A, "305b2c9d93fcd4288b06fc5f4db192edc44b9d2e5b5f90b002465c1ec38f96b5"),   # TDesignShip.Create exit
    (0x8EC77E, 0x20, "0e62ea84ab00afd3e93f8b40a3d99ec05fd6e20ffd90bf05a9c8d97f22b8e18d"),   # TFightingShip.Create exit
    (0x83C37C, 0x2F, "db7b0261b47e3b3c7700d2f667765310c07ef71283ed700a9b685f2df0a1d6a5"),   # design copy exit
    (0x94CE90, 0x20, "dc03a210a9da7b5b14a87ccb36134ffb4dcaf7a8c1dc98a27f66d63ed67b53d7"),   # campaign save writer
    (0x94DC3C, 0x20, "70a2017a3cdf899bc748c5b7711ecc47c32c1f079cd80e1f98fa301e43ca301d"),   # campaign save reader
    (0x93FF96, 0x40, "3854ba3727707f3e87626c8f3524ac2b2f4235297de53dd35ec761daffcde9a4"),   # design file writer
    (0x9430D0, 0x26, "e028ebc0b28ddaf4a7b8686b1a507373cee64f0731d4d1969d58fb32f3f14a4b"),   # design file reader
    (0x8EDEFE, 0x18, "2c4231da28b4767fa7dcdb8bae9e3a5e6d4a52b516476f2a0ffea0056ce306e2"),   # second design file reader
)
NATIVE = dict(bool_writer=0x94C64C, int_reader=0x94D4EC, ini_int_writer=0x845C68, ini_int_reader=0x846B48,
              int_to_str=0x328C80, clear=0x30B8DC, design_vmt=0x9358F0, fighting_vmt=0x8E4124,
              fighting_exit=0x8EC79A, copy_back=0x83C3A5, ini_push_back=0x93FFBE,
              big_store_back=0x94DC56, ini_store_back=0x9430F5, ini2_store_back=0x8EDF16,
              get_mem=0x306EB0, init_instance=0x309AE0)   # as TObject.NewInstance calls them
SITES = (("design_alloc", 0x9358E4, 4), ("fighting_alloc", 0x8E4118, 4),
         ("design_exit", 0x948D99, 5), ("fighting_exit_hook", 0x8EC795, 5), ("copy", 0x83C3A0, 5),
         ("big_save", 0x94CEA7, 5), ("big_load", 0x94DC4A, 5), ("big_store", 0x94DC50, 6),
         ("ini_push", 0x93FFB6, 8), ("ini_save", 0x93FFCA, 5),
         ("ini_load", 0x9430EA, 5), ("ini_store", 0x9430EF, 6), ("ini_load2", 0x8EDF0B, 5), ("ini_store2", 0x8EDF10, 6))


def discover(blob, base, normalized):
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Ship extension refuses changed native code at "+hex(address)+".")
    for name, (vmt, size) in CLASSES.items():
        if struct.unpack_from("<i", normalized, vmt-0x34-BASE)[0] != size:
            raise ValueError("Unsupported native ship class size: "+name)
    for name, address in (("LoadMeFromBigFile", 0x94D570), ("SaveMeToBigFile", 0x94C73C)):
        if rt.method_address(blob, base, name) != address+base-BASE:
            raise ValueError("Unsupported native save method: "+name)
    delta = base-BASE
    info = {k: v+delta for k, v in NATIVE.items()}
    info["sites"] = [dict(name=name, address=address+delta, original=blob[address-BASE:address-BASE+size].hex())
                     for name, address, size in SITES]
    return info


def build(page, info):
    """Code in one page; returns blocks, patches and the ext helper address."""
    from campaign_security import Code   # imported late: campaign_security imports modern_research
    at = dict(ext=page, design_exit=page+0x80, fighting_exit_hook=page+0xC0, copy=page+0x100, big_save=page+0x140,
              big_store=page+0x1C0, ini_push=page+0x200, ini_store=page+0x240, ini_store2=page+0x280,
              new_instance=page+0x2C0)
    limits = dict(ext=0x80, big_save=0x80)
    n, code = info, {}

    # NewInstance(EAX class): TObject.NewInstance with EXTRA more bytes, zeroed (GetMem leaves them dirty).
    c = Code(at["new_instance"])
    c.emit(b"\x53\x8b\xd8\x8b\x43\xcc\x83\xc0"+bytes([EXTRA])); c.branch(b"\xe8", n["get_mem"])
    c.emit(b"\x8b\x53\xcc\x33\xc9\x89\x0c\x10\x89\x4c\x10\x04\x89\x4c\x10\x08\x89\x4c\x10\x0c")   # [+0..+12] := 0
    c.emit(b"\x8b\xd0\x8b\xc3"); c.branch(b"\xe8", n["init_instance"]); c.emit(b"\x5b\xc3")
    code["new_instance"] = c.finish()

    # ext(EAX ship) -> EAX address of the data dword, or 0 when the ship has none. Keeps other registers.
    c = Code(at["ext"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "none"); c.emit(b"\x52\x8b\x10")
    for key, label in (("design_vmt", "design"), ("fighting_vmt", "fighting")):
        c.emit(b"\x81\xfa"); c.u32(n[key]); c.branch(b"\x0f\x84", label)
    c.branch(b"\xe9", "zero")
    for label, size in (("design", CLASSES["design"][1]), ("fighting", CLASSES["fighting"][1])):
        c.mark(label); c.emit(b"\x05"); c.u32(size); c.branch(b"\xe9", "check")
    c.mark("check"); c.emit(b"\x8b\xd0\x81\xf2"); c.u32(MAGIC); c.emit(b"\x39\x50\x04"); c.branch(b"\x0f\x85", "zero")
    c.emit(b"\x5a\xc3")
    c.mark("zero"); c.emit(b"\x5a")
    c.mark("none"); c.emit(b"\x33\xc0\xc3")
    code["ext"] = c.finish()

    def stamp(c, size):   # EAX object: data := 0, guard := MAGIC xor data address
        c.emit(b"\x8d\x90"); c.u32(size); c.emit(b"\xc7\x02"); c.u32(0)
        c.emit(b"\x8b\xca\x81\xf1"); c.u32(MAGIC); c.emit(b"\x89\x4a\x04")

    c = Code(at["design_exit"])   # TDesignShip.Create: mov eax, esi; pop esi; pop ebx; ret
    c.emit(b"\x8b\xc6"); stamp(c, CLASSES["design"][1]); c.emit(b"\x5e\x5b\xc3")
    code["design_exit"] = c.finish()
    c = Code(at["fighting_exit_hook"])   # TFightingShip.Create: mov eax, ebx; pop edi; pop esi; pop ebx
    c.emit(b"\x8b\xc3"); stamp(c, CLASSES["fighting"][1]); c.emit(b"\x5f\x5e\x5b"); c.branch(b"\xe9", n["fighting_exit"])
    code["fighting_exit_hook"] = c.finish()

    c = Code(at["copy"])   # design copy: ESI source, EBX destination
    c.emit(b"\x60\x8b\xc6"); c.branch(b"\xe8", at["ext"]); c.emit(b"\x8b\xf8\x8b\xc3"); c.branch(b"\xe8", at["ext"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done"); c.emit(b"\x85\xff"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x0f\x89\x08")
    c.mark("done"); c.emit(b"\x61\x0f\xb6\x45\xff\x5f"); c.branch(b"\xe9", n["copy_back"])
    code["copy"] = c.finish()

    def pack(c):   # EAX data, [esp] elevation: [esp] := elevation | data << 8 | data bits 24-29 << 2
        c.emit(b"\x8b\xd0\xc1\xea"+bytes([HIGH_SHIFT])+b"\x83\xe2"+bytes([HIGH_MASK])+b"\xc1\xe2\x02\x09\x14\x24")
        c.emit(b"\xc1\xe0\x08\x09\x04\x24")

    # Campaign save line: AL elevation byte, EBX ship, [esp+4] the saver's frame (list at [frame-4]).
    c = Code(at["big_save"])
    c.emit(b"\x0f\xb6\xc0\x50\x8b\xc3"); c.branch(b"\xe8", at["ext"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "plain")
    c.emit(b"\x8b\x00"); pack(c)
    c.mark("plain"); c.emit(b"\x58\x83\xf8\x01"); c.branch(b"\x0f\x86", n["bool_writer"])
    c.emit(b"\x55\x8b\xec\x6a\x00\x8d\x55\xfc"); c.branch(b"\xe8", n["int_to_str"])
    c.emit(b"\x8b\x45\x08\x8b\x40\xfc\x8b\x55\xfc\x8b\x08\xff\x51\x3c\x8d\x45\xfc"); c.branch(b"\xe8", n["clear"])
    c.emit(b"\x8b\xe5\x5d\xc3")
    code["big_save"] = c.finish()

    def unpack(c, back):   # EAX integer read, EBX ship: elevation byte (bits 0-1) and extension data
        c.emit(b"\x50\x52\x51\x8b\xc8\x24\x03\x88\x83"); c.u32(0x9A6)
        c.emit(b"\x8b\xd1\xc1\xea\x08\xc1\xe9\x02\x83\xe1"+bytes([HIGH_MASK])+b"\xc1\xe1"+bytes([HIGH_SHIFT])+b"\x0b\xd1")
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["ext"])
        c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "skip"); c.emit(b"\x89\x10")
        c.mark("skip"); c.emit(b"\x59\x5a\x58"); c.branch(b"\xe9", back)

    for name, back in (("big_store", "big_store_back"), ("ini_store", "ini_store_back"), ("ini_store2", "ini2_store_back")):
        c = Code(at[name]); unpack(c, n[back]); code[name] = c.finish()

    c = Code(at["ini_push"])   # design file: EDI ship; pushes the packed integer
    c.emit(b"\x0f\xb6\x87"); c.u32(0x9A6); c.emit(b"\x50\x8b\xc7"); c.branch(b"\xe8", at["ext"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done"); c.emit(b"\x8b\x00"); pack(c)
    c.mark("done"); c.branch(b"\xe9", n["ini_push_back"])
    code["ini_push"] = c.finish()

    blocks = []
    for name, body in code.items():
        if len(body) > limits.get(name, 0x40):
            raise ValueError("Ship extension code exceeds its reservation: "+name)
        blocks.append(dict(name="Ship extension: "+name, address=at[name], bytes=body.hex()))
    calls = dict(big_save=at["big_save"], big_load=n["int_reader"], ini_save=n["ini_int_writer"],
                 ini_load=n["ini_int_reader"], ini_load2=n["ini_int_reader"])
    plans = []
    for site in info["sites"]:
        old, name = bytes.fromhex(site["original"]), site["name"]
        if name in ("design_alloc", "fighting_alloc"):   # VMT slot: absolute address of the allocator
            new = struct.pack("<I", at["new_instance"])
        elif name in calls:
            new = b"\xe8"+struct.pack("<i", calls[name]-site["address"]-5)+b"\x90"*(len(old)-5)
        else:
            new = b"\xe9"+struct.pack("<i", at[name]-site["address"]-5)+b"\x90"*(len(old)-5)
        plans.append(patch("Ship extension: "+name, site["address"], old, new))
    return blocks, plans, at["ext"]

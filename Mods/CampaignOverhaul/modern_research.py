"""Guarded, symmetric effects for the modern research package.

Also converts older saves at load: their gun-manufacture record moves from 22
to 24 and the two new branches start empty (see modern_tree.NEW_AREAS).
"""
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import time
import weekly_runtime as rt
import modern_tree as tree
from hull_rules import patch, unique

REPORT = Path(__file__).with_name("modern_research_report.json")
# Audited bodies of the managed Steam build at the reference snapshot's base.
# PE HIGHLOW relocations are normalized before hashing. Code changes are still
# refused; ordinary Windows address randomization is not a different build.
AUDITED = {
    "HasResearchId": "8bae88abf05e42ab80b6639970f8ed049f88e96a89b0ba6389929eec3e64791b",
    "CountResearchLevels": "a81e26c7a988cfa5c6a545e3ef1d4b242d9ea14acfa530d96d464598688af733",
    "LoadGlobalResearchAreas": "1a3d6cbdb76a8560850686b5906d802fc57be980979d31c53cbd5153d8b17522",
    "GetROFMod": "2c2d4256c56908f4a13b48453429e8ba76d0d3834bce6b9fbf31321b9487509c",
    "GetDamageControlMod": "ae2177887d07a4793a77576d81a9870ebd8b142aeebe481ae6e326aba4e406bf",
    "GetSAMQ": "f5b06e13c0a34595ffcc265e37301ea62bdfa734c156ecdc83339212292bc00c",
    "GetSSMQ": "ecef23c8752351d4141b9ca5cd897287ecb70f78703ba684a291e81927cad257",
    "GetAntiMissile": "b5d638437e4492bef2fa085b3f2b90b4af897b7971c88f2a40d2025f2f23c599",
    "GetAirborneECMLevel": "811415bbef789d716529c4b2056bc8d2b5afc587cb3460d3900a53a1746525db",
    "GetSubAccuracy": "74cc43dd03e2323b39870b382e8adc6939a028f7e4cd1ebf6ddedcc7ef734582",
    "GetLAAQ": "8508ae01eea76aa2e499986606ebc8baf3c9187ef9db104a62bda2b384dcbfda",
    "GetMAAQ": "be9dd94b51e6156afaf15a3446882cc8e17f5e7e1f58dff6166cf7eb794185a5",
    "GetHAAQ": "33dd25b75b940ccec642a2377cfbe36c06c3e21096b8f22799030d711df2c0e0",
}
SIZES = dict(zip(AUDITED, (102, 263, 1587, 262, 117, 208, 129, 147, 62, 127, 154, 328, 311)))
REFERENCE_TEXT_BASE = 0x301000
# Native nation loader: count+1 research records, six Research<N> key builds.
LOOP, LOOP_SIZE = 0x7206e2, 0x1fb
LOOP_DIGEST = "1ce2f1393e15fad7242d2289b09079eadc9565ddc78979d1a6d62f7ea1e4ff28"
RECORD_KEYS = (0x720704, 0x72074d, 0x720796, 0x7207df, 0x720828, 0x720876)
READ_INTEGER, INT_TO_STR = 0x586fc8, 0x328c80
OLD_SAVE = -7777
# Record -> key read from an older save; 99/98 do not exist, so native defaults.
REMAP = {22: 99, 23: 98, 24: 22}


def text_relocations():
    """Read relocation metadata, never code, from the authenticated disk image."""
    path = (rt.GAME/"RTW3.exe").resolve()
    stat = path.stat()
    identity = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
    return _cached_relocations(str(path), identity)


@lru_cache(maxsize=2)
def _cached_relocations(path, identity):
    data = Path(path).read_bytes()
    stat = Path(path).stat()
    if identity != (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino):
        raise ValueError("Game image changed while reading relocation metadata.")
    return _parse_relocations(data)


def _parse_relocations(data):
    if data[:2] != b"MZ": raise ValueError("Invalid game PE header.")
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    if data[pe:pe+4] != b"PE\0\0" or struct.unpack_from("<H", data, pe+24)[0] != 0x10b:
        raise ValueError("Unsupported research-engine PE format.")
    count = struct.unpack_from("<H", data, pe+6)[0]
    optional = struct.unpack_from("<H", data, pe+20)[0]
    rva, size = struct.unpack_from("<II", data, pe+24+96+5*8)
    if not 1 <= count <= 96 or not 8 <= size <= 4_000_000:
        raise ValueError("Invalid research-engine relocation directory.")
    sections = []
    for i in range(count):
        at = pe+24+optional+i*40
        virtual_size, start, raw_size, raw = struct.unpack_from("<4I", data, at+8)
        sections.append((data[at:at+8].rstrip(b"\0"), start, virtual_size, raw, raw_size))
    text = [s for s in sections if s[0] == b".text"]
    owner = [s for s in sections if s[1] <= rva and rva+size <= s[1]+s[4]]
    if len(text) != 1 or len(owner) != 1: raise ValueError("Cannot locate native text relocations.")
    start = owner[0][3]+rva-owner[0][1]
    directory = data[start:start+size]
    if len(directory) != size: raise ValueError("Truncated native relocations.")
    offset, locations = 0, []
    while offset < size:
        page, length = struct.unpack_from("<II", directory, offset)
        if length < 8 or length % 2 or offset+length > size:
            raise ValueError("Invalid native relocation block.")
        for at in range(offset+8, offset+length, 2):
            item = struct.unpack_from("<H", directory, at)[0]
            kind, address = item >> 12, page+(item & 0xfff)
            if kind not in (0, 3): raise ValueError("Unsupported native relocation type.")
            if kind == 3 and text[0][1] <= address and address+4 <= text[0][1]+text[0][2]:
                locations.append(address-text[0][1])
        offset += length
    if len(set(locations)) != len(locations) or len(locations) < 10000:
        raise ValueError("Unexpected native relocation coverage.")
    # Immutable metadata only. Live code and signature checks are never cached.
    return tuple(locations)


def normalize(blob, base):
    import big_guns   # its in-place gun-level and calibre patches read back as native for every audit
    if base == REFERENCE_TEXT_BASE: return big_guns.native_bytes(blob)
    delta = base-REFERENCE_TEXT_BASE
    result = bytearray(blob)
    for offset in text_relocations():
        if offset+4 > len(blob): raise ValueError("Relocation exceeds the native text image.")
        value = struct.unpack_from("<I", result, offset)[0]
        struct.pack_into("<I", result, offset, (value-delta) & 0xffffffff)
    return big_guns.native_bytes(bytes(result))


def native_body(blob, base, name, normalized=None):
    sys.path.insert(0, str(rt.GAME/"Mods/Manager/vendor"))
    import capstone
    address = rt.method_address(blob, base, name)
    normalized = normalize(blob, base) if normalized is None else normalized
    start, length = address-base, SIZES[name]
    body = blob[start:start+length]
    # Some Delphi SEH routines embed handler data before the final epilogue.
    # Disassembling until an apparent RET can mistake a relocated data byte for
    # code. The complete audited size and digest verify the boundary instead.
    if not body.endswith(b"\xc3") or hashlib.sha256(normalized[start:start+length]).hexdigest() != AUDITED[name]:
        raise ValueError("Native research method differs from the audited build: "+name)
    instructions = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(body, address))
    return address, body, instructions


def discover(blob, base):
    normalized = normalize(blob, base)
    start = LOOP-REFERENCE_TEXT_BASE
    if hashlib.sha256(normalized[start:start+LOOP_SIZE]).hexdigest() != LOOP_DIGEST:
        raise ValueError("Modern research refuses changed native research loading code.")
    methods = {name: native_body(blob, base, name, normalized) for name in AUDITED}
    has = methods["HasResearchId"][1]
    matches = list(re.finditer(rb"\xc7\x44\x24\x08(.{4})", has, re.DOTALL))
    if len(matches) != 1: raise ValueError("Cannot verify native research table pointer.")
    id_base = struct.unpack("<I", matches[0].group(1))[0]
    flag_at = unique(has, b"\x6b\xdf\x35\x8d\x1c\x18\x80\xbc\x33", "nation research flag layout")
    flag_base = struct.unpack_from("<I", has, flag_at+9)[0]
    if flag_base != 0x336 or b"\x83\xfe\x24" not in has or b"\x81\x44\x24\x08\x14\x04\x00\x00" not in has:
        raise ValueError("Unsupported native research capacity or area stride.")
    layout = dict(table_id_base=id_base, flag_base=flag_base, nation_stride=0x35,
                  table_stride=0x414, record_stride=0x1d, max_levels=36)
    _, nodes = tree.render()
    getters = []
    for name in tree.LABELS:
        address, body, instructions = methods[name]
        # These reviewed integer getters retain the owning nation in EBX until
        # their single return. Capture EAX before touching stack/flags, then
        # replay exactly the original register pops and RET.
        tail = bytes.fromhex("8b04245a5bc3") if name in ("GetLAAQ", "GetDamageControlMod") else (
            bytes.fromhex("8b065a5e5bc3") if name in ("GetMAAQ", "GetHAAQ") else bytes.fromhex("8bc65e5bc3"))
        if not body.endswith(tail) or b"\x8b\xd8" not in body[:12]:
            raise ValueError("Unsupported research result/owner registers: "+name)
        site = address+len(body)-len(tail)
        for ins in instructions:
            if ins.mnemonic.startswith("j") and ins.op_str.startswith("0x") and site < int(ins.op_str, 16) < site+len(tail):
                raise ValueError("A native branch enters the middle of a research result hook.")
        contributions = [dict(id=node["id"], flag=flag_base+node["area"]*0x35+node["slot"],
                              table=id_base+node["area"]*0x414+node["slot"]*0x1d)
                         for node in nodes if name in node["effects"]]
        if not contributions: raise ValueError("A research hook has no owned technologies.")
        getters.append(dict(name=name, method=address, address=site, original=tail.hex(),
                            capture=tail[:3 if tail.startswith(b"\x8b\x04") else 2].hex(),
                            contributions=contributions, maximum_bonus=len(contributions)))
    delta = base-REFERENCE_TEXT_BASE
    loader = dict(site=LOOP+delta, original=blob[start:start+5].hex(),
                  count=struct.unpack_from("<I", blob, start+1)[0],
                  read_integer=READ_INTEGER+delta, int_to_str=INT_TO_STR+delta,
                  record_keys=[{"address": at+delta, "original": blob[at-REFERENCE_TEXT_BASE:at-REFERENCE_TEXT_BASE+5].hex()}
                               for at in RECORD_KEYS])
    import modern_sensors   # imported late: keeps this module's import order free
    sensors = modern_sensors.discover(blob, base, normalized)
    import modern_propulsion
    propulsion = modern_propulsion.discover(blob, base, normalized)
    import modern_railgun
    railgun = modern_railgun.discover(blob, base, normalized)
    import modern_extension
    extension = modern_extension.discover(blob, base, normalized)
    import modern_combat
    combat = modern_combat.discover(blob, base, normalized)
    import modern_recon
    recon = modern_recon.discover(blob, base, normalized)
    import modern_navy
    navy = modern_navy.discover(blob, base, normalized)
    import ai_modern
    ai = ai_modern.discover(blob, base, normalized)
    import shell_doctrine
    doctrine = shell_doctrine.discover(blob, base, normalized)
    import nuclear_subs
    subs = nuclear_subs.discover(blob, base, normalized)
    import modern_defence
    defence = modern_defence.discover(blob, base, normalized)
    import modern_carrier
    carrier = modern_carrier.discover(blob, base, normalized)
    import modern_air_defence
    air = modern_air_defence.discover(blob, base, normalized)
    import nuclear_strike
    strike = nuclear_strike.discover(blob, base, normalized)
    import point_defence
    pd = point_defence.discover(blob, base, normalized)
    import undersea
    sea = undersea.discover(blob, base, normalized)
    return {**layout, "getters": getters, "loader": loader, "sensors": sensors, "propulsion": propulsion, "railgun": railgun,
            "extension": extension, "combat": combat, "recon": recon, "navy": navy, "ai": ai, "doctrine": doctrine, "subs": subs, "defence": defence, "carrier": carrier, "air": air,
            "nuclear_strike": strike, "point_defence": pd, "undersea": sea, "new_technologies": len(nodes),
            "applies_to": "all nations; only their own completed research flags",
            "save_format_changed": "older saves load with gun manufacture moved to record 24",
            "new_weapon_types": False, "campaign_balance_verified": False}


def effect_thunk(site):
    capture, original = bytes.fromhex(site["capture"]), bytes.fromhex(site["original"])
    code = bytearray(capture+b"\x9c")
    for contribution in site["contributions"]:
        # A table-ID guard on every contribution prevents the wrong bonus if
        # research slots do not match the appended tree in a loaded session.
        code.extend(b"\x81\x3d"+struct.pack("<II", contribution["table"], contribution["id"]))
        code.extend(b"\x75\x0c")
        code.extend(b"\x80\xbb"+struct.pack("<I", contribution["flag"])+b"\x01")
        code.extend(b"\x75\x03\x83\xc0\x01")
    code.extend(b"\x9d"+original[len(capture):])
    return bytes(code)


def probe_thunk(address, loader, flag, key):
    """Per nation: remap only when 24 branches are loaded and Research24Prio is absent."""
    from campaign_security import Code   # imported late: campaign_security imports this module
    c = Code(address)
    c.emit(b"\x9c\x60\xc6\x05"); c.u32(flag); c.emit(b"\x00")
    c.emit(b"\xa1"); c.u32(loader["count"]); c.emit(b"\x83\xf8\x18"); c.branch(b"\x0f\x85", "done")
    # ReadInteger(EAX=ini ESI, EDX=section [EBP-4], ECX=key, default on stack; RET 4).
    c.emit(b"\x68"); c.u32(OLD_SAVE & 0xffffffff)
    c.emit(b"\xb9"); c.u32(key); c.emit(bytes.fromhex("8b55fc8bc6"))
    c.branch(b"\xe8", loader["read_integer"])
    c.emit(b"\x3d"); c.u32(OLD_SAVE & 0xffffffff); c.branch(b"\x0f\x85", "done")
    c.emit(b"\xc6\x05"); c.u32(flag); c.emit(b"\x01")
    c.mark("done"); c.emit(b"\x61\x9d"+bytes.fromhex(loader["original"]))
    c.branch(b"\xe9", loader["site"]+5)
    return c.finish()


def remap_thunk(address, loader, flag):
    """Replaces IntToStr(EAX=record) only where the loader builds Research<N> keys."""
    from campaign_security import Code
    c = Code(address)
    c.emit(b"\x80\x3d"); c.u32(flag); c.emit(b"\x00"); c.branch(b"\x0f\x84", "native")
    for old, key in REMAP.items():
        c.emit(b"\x83\xf8"+bytes([old])); c.branch(b"\x0f\x85", f"not{old}")
        c.emit(b"\xb8"); c.u32(key); c.branch(b"\xe9", "native")
        c.mark(f"not{old}")
    c.mark("native"); c.branch(b"\xe9", loader["int_to_str"])
    return c.finish()


def build(allocation, details):
    """Getter pages first (check_modern_runtime reads them by index), then the loader page."""
    blocks, plans = [], []
    for index, getter in enumerate(details["getters"]):
        at = allocation+index*0x1000
        code = effect_thunk(getter)
        if len(code) > 0x1000: raise ValueError("Research effect exceeds its reserved code page.")
        blocks.append(dict(name=getter["name"], address=at, bytes=code.hex()))
        old = bytes.fromhex(getter["original"])
        plans.append(patch("Modern research: "+getter["name"], getter["address"], old,
                           b"\xe9"+struct.pack("<i", at-getter["address"]-5)+b"\x90"*(len(old)-5)))
    page, loader = allocation+len(details["getters"])*0x1000, details["loader"]
    flag, key, text = page+0x300, page+0x20c, "Research24Prio"
    literal = struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"
    blocks += [dict(name="older-save key", address=key-12, bytes=literal.hex()),
               dict(name="older-save probe", address=page, bytes=probe_thunk(page, loader, flag, key).hex()),
               dict(name="older-save remap", address=page+0x100, bytes=remap_thunk(page+0x100, loader, flag).hex())]
    if any(len(bytes.fromhex(b["bytes"])) > 0xf4 for b in blocks[-3:]):
        raise ValueError("Modern research loader code exceeds its reservation.")
    plans.append(patch("Modern research: older-save probe", loader["site"], bytes.fromhex(loader["original"]),
                       b"\xe9"+struct.pack("<i", page-loader["site"]-5)))
    for item in loader["record_keys"]:
        plans.append(patch("Modern research: record key", item["address"], bytes.fromhex(item["original"]),
                           b"\xe8"+struct.pack("<i", page+0x100-item["address"]-5)))
    import modern_sensors
    sensor_blocks, sensor_plans = modern_sensors.build(page, details["sensors"], page+0xD000, page+0x10200)   # AESA: the last page
    import modern_propulsion   # its own page after the loader page
    nuclear_blocks, nuclear_plans = modern_propulsion.build(page+0x1000, details["propulsion"])
    sensor_blocks += nuclear_blocks; sensor_plans += nuclear_plans
    import modern_extension   # its own page after the propulsion page
    extension_blocks, extension_plans, ext = modern_extension.build(page+0x2000, details["extension"])
    sensor_blocks += extension_blocks; sensor_plans += extension_plans
    import modern_air_defence   # drones, hypervelocity AA and nuclear SAMs: the page after the auto-build bridge
    air_page = page+0x13000
    air = {name: air_page+offset for name, offset in modern_air_defence.OFFSETS.items()}
    import modern_carrier   # ski jump and VTOL: the page after the missile-flight page
    carrier_blocks, carrier_plans, carrier_sync = modern_carrier.build(page+0x11000, details["carrier"],
                                                                       uav_request=page+modern_sensors.UAV_REQUEST,
                                                                       aew=air["aew"])
    sensor_blocks += carrier_blocks; sensor_plans += carrier_plans
    import modern_railgun   # six pages after it
    import nuclear_subs
    import modern_defence
    import modern_recon   # its side_nation helper: missiles hold a battle side, research and doctrine need nations
    side_nation, arm_lock = page+0xA000+modern_recon.SIDE_NATION, page+0xA000+modern_recon.ARM_LOCK
    import point_defence   # SeaRAM, gun-missile CIWS, RAM: two code pages and a text page after the nuclear strike pages
    pd = point_defence.addresses(page+0x18000)
    railgun_blocks, railgun_plans = modern_railgun.build(page+0x3000, details["railgun"], ext, page+0xD400,
                                                         carrier_sync=carrier_sync,
                                                         propulsion_sync=page+0x1000+modern_propulsion.RANGE_SYNC,
                                                         nuclear_missile=page+0xF000+nuclear_subs.MISSILE_ENTRY,
                                                         cell_cost_at=page+0xFB00,   # free room in the submarines' page
                                                         asbm=page+0x10000+modern_defence.ASBM,
                                                         point_defence=pd, side_nation=side_nation,
                                                         carrier_weight=page+0x11000+modern_carrier.SKI_WEIGHT)
    sensor_blocks += railgun_blocks; sensor_plans += railgun_plans
    pd_blocks, pd_plans = point_defence.build(page+0x18000, details["point_defence"], details["railgun"], page+0x3000, ext)
    sensor_blocks += pd_blocks; sensor_plans += pd_plans
    import designer_names   # in the AESA page, after its code and texts
    sensor_blocks += designer_names.build(page+0xD400, details["railgun"])
    import shell_doctrine   # the last page: the player's choice to fire guided and nuclear shells
    doctrine_blocks, doctrine_plans, doctrine = shell_doctrine.build(page+0xE000, details["doctrine"])
    sensor_blocks += doctrine_blocks; sensor_plans += doctrine_plans
    import nuclear_subs   # one more page: SSN and SSBN
    subs_blocks, subs_plans = nuclear_subs.build(page+0xF000, details["subs"], doctrine, page+0x10300,
                                                  page+0x12000, nuclear_ssm=air["nuclear_ssm"],
                                                  side_nation=side_nation)
    sensor_blocks += subs_blocks; sensor_plans += subs_plans
    import modern_defence   # in the nuclear submarines' page, after their data and texts
    defence_blocks, defence_plans = modern_defence.build(page+0xFC00, details["defence"], doctrine, page+0x10000,
                                                         drones=air["drone_ship"], nuclear_sam=air["nuclear_sam"],
                                                         side_nation=side_nation, arm_lock=arm_lock,
                                                         ram_sam=pd["ram_sam"], ram_kind=pd["ram_kind"])
    sensor_blocks += defence_blocks; sensor_plans += defence_plans
    air_blocks, air_plans = modern_air_defence.build(air_page, details["air"], page+0x11000+modern_carrier.HAS_SPECIAL,
                                                     doctrine, side_nation=side_nation)
    sensor_blocks += air_blocks; sensor_plans += air_plans
    import nuclear_strike   # the battle's nuclear strike console: code, data, console code and text pages after the air defence page
    import undersea   # its page holds the SONAR button's code; the flag lives in the strike data page
    strike_blocks, strike_plans = nuclear_strike.build(page+0x14000, page+0x15000, details["nuclear_strike"], doctrine, ext,
                                                       page+0xF000+nuclear_subs.STRIKE_ENTRY, page+0xF000, page+0x16000,
                                                       page+0x17000, sonar=undersea.addresses(page+0x1B000)["sonar_button"])
    sensor_blocks += strike_blocks; sensor_plans += strike_plans
    import modern_combat   # one page after the railgun pages
    import undersea   # homing torpedoes, anti-torpedo torpedoes, moving submarines: the page after point defence's
    sea = undersea.addresses(page+0x1B000)
    combat_blocks, combat_plans = modern_combat.build(page+0x9000, details["combat"], page+0x3000+modern_railgun.IS_HYPER, ext,
                                                      doctrine, targets=sea["targets"], att=sea["att"])
    sensor_blocks += combat_blocks; sensor_plans += combat_plans
    sea_blocks, sea_plans, _ = undersea.build(page+0x1B000, details["undersea"], page+0x9000, ext, side_nation,
                                              page+0xF000,   # nuclear_subs' is_kind starts its page
                                              sonar=page+0x15000+nuclear_strike.SONAR)
    sensor_blocks += sea_blocks; sensor_plans += sea_plans
    import modern_recon   # one page after combat
    recon_blocks, recon_plans = modern_recon.build(page+0xA000, details["recon"])
    sensor_blocks += recon_blocks; sensor_plans += recon_plans
    import modern_navy   # one page after recon
    navy_blocks, navy_plans = modern_navy.build(page+0xB000, details["navy"], ext, doctrine, drones=air["drone_ship"])
    sensor_blocks += navy_blocks; sensor_plans += navy_plans
    import ai_modern   # one page after navy: AI designs use the options above
    ai_blocks, ai_plans = ai_modern.build(page+0xC000, details["ai"], ext, page+0x3000+modern_railgun.POWER)
    sensor_blocks += ai_blocks; sensor_plans += ai_plans
    return blocks+sensor_blocks, plans+sensor_plans, flag


def structure(raw):
    """What the patches rely on: the branches and, in order, each technology's ID and prerequisite. Years, costs,
    chances, names and texts may differ (a research-speed sub-mod)."""
    return [[(row["id"], row["prerequisite"]) for row in area["rows"]] for area in tree.parse(raw)]


def check_payload():
    expected, _ = tree.render()
    current = (rt.GAME/"Data/ResearchAreas3.dat").read_bytes()
    if current != expected:
        try:
            same = structure(current) == structure(expected)
        except ValueError as error:   # includes a non-ASCII file
            raise ValueError(f"Data/ResearchAreas3.dat can't be read: {error}")
        if not same:
            raise ValueError("Apply Expanded Timeline in the manager before launching. The research table differs from "
                             "this adapter: a technology was added, removed, moved or given another prerequisite "
                             "(years, costs and chances may change).")
    return hashlib.sha256(current).hexdigest()


def verify(handle, plans, key):
    for item in plans:
        data = bytes.fromhex(item[key])
        if rt.read(handle, item["address"], len(data)) != data:
            raise ValueError("The modern research attachment changed; operation refused.")


def runtime_allocation_size(details):
    # Existing fixed runtime pages, the player SSN/SSBN auto-build bridge, the air defence page, the four
    # nuclear strike console pages (code, data, the console's code, its texts), point defence's three and undersea's.
    return 0x1000*(len(details["getters"])+28)


def validate_runtime_blocks(blocks, allocation, size):
    end = allocation+size
    for block in blocks:
        address = block["address"]
        block_end = address+len(bytes.fromhex(block["bytes"]))
        if address < allocation or block_end > end:
            raise ValueError(f"Modern research block exceeds its reserved memory: {block['name']} at {address:#x}.")


def attach(wait=30):
    import ai_runtime
    import live_cheats as live
    import week_display as memory
    payload_hash = check_payload()
    memory.configure()
    deadline = time.monotonic()+wait
    while True:
        games = [(pid, path) for pid, path in rt.process_candidates() if path == rt.GAME/"RTW3.exe"]
        if len(games) == 1: break
        if time.monotonic() >= deadline: raise ValueError("Open the local game through Play with mods first.")
        time.sleep(0.5)
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle: raise rt.win_error("Cannot open the local research engine")
    try:
        module, _ = rt.module_info(pid)
        if REPORT.exists():
            saved = json.loads(REPORT.read_text(encoding="utf-8"))
            if saved.get("attached") and saved.get("pid") == pid and saved.get("base") == module and rt.report_is_current(REPORT, pid):
                verify(handle, saved["patches"], "replacement")
                return saved
        # Attaches after research-traits (it hashes a record-key call) and may follow live-cheats.
        module, base, blob = live.unhooked_text(pid, handle)
        details = discover(blob, base)
        campaign = live.discover(blob, base)
        ai_runtime.require_title_screen(handle, campaign)
        size = runtime_allocation_size(details)
        allocation = rt.K.VirtualAllocEx(handle, None, size, 0x3000, 0x40)
        if not allocation: raise rt.win_error("Cannot allocate modern research effects")
        applied = []
        try:
            blocks, plans, flag = build(allocation, details)
            validate_runtime_blocks(blocks, allocation, size)
            import modern_sensors
            plans += modern_sensors.limit_box(lambda at, n: rt.read(handle, at, n), blob, base)
            for block in blocks: memory.write(handle, block["address"], bytes.fromhex(block["bytes"]))
            rt.K.FlushInstructionCache(handle, allocation, size)
            verify(handle, plans, "original")
            for plan in plans:
                rt.write_code(handle, plan["address"], bytes.fromhex(plan["original"]), bytes.fromhex(plan["replacement"]))
                applied.append(plan)
            verify(handle, plans, "replacement")
            saved = {"pid": pid, "base": module, "attached": True, "allocation": allocation,
                     "patches": plans, "code_blocks": blocks, "remap_flag": flag, "details": details,
                     "research_sha256": payload_hash, "personal_saves_modified": False,
                     "campaign_guard": {key: campaign[key] for key in ("main_slot", "player_field")}}
            REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
            return saved
        except Exception:
            for plan in reversed(applied):
                rt.write_code(handle, plan["address"], bytes.fromhex(plan["replacement"]), bytes.fromhex(plan["original"]))
            if not applied: rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise
    finally: rt.K.CloseHandle(handle)


def detach():
    import ai_runtime
    rt.configure_api()
    saved = json.loads(REPORT.read_text(encoding="utf-8"))
    if not saved.get("attached"): return saved
    if dict(rt.process_candidates()).get(saved["pid"]) != rt.GAME/"RTW3.exe":
        raise ValueError("The modern research session has ended.")
    handle = rt.K.OpenProcess(0x438, False, saved["pid"])
    if not handle: raise rt.win_error("Cannot open the local research engine")
    try:
        if rt.module_info(saved["pid"])[0] != saved["base"]: raise ValueError("The game session changed.")
        ai_runtime.require_title_screen(handle, saved["campaign_guard"])
        verify(handle, saved["patches"], "replacement")
        for plan in reversed(saved["patches"]):
            rt.write_code(handle, plan["address"], bytes.fromhex(plan["replacement"]), bytes.fromhex(plan["original"]))
        saved["attached"] = False
        REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
        return saved
    finally: rt.K.CloseHandle(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attach", "detach"))
    args = parser.parse_args()
    try: print(json.dumps(attach() if args.command == "attach" else detach()))
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "message": str(error)})); raise SystemExit(1)

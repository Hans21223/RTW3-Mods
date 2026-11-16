"""Nuclear propulsion: designer propulsion type 5, "Nuclear", gated by research.

Native types: 0 Coal + VTE, 1 Coal + Turbine, 2 Oil + Turbine, 3 Diesel,
4 Gas turbine. Type 5 falls through every native propulsion branch (baseline
machinery, oil-like rules elsewhere). This adds the designer list entry and its
research gate, heavier and costlier reactor machinery (less heavy once the designing
nation has thorium reactors), no bunker fuel at any range setting, and no
oil-supply shortage, low-fuel state or battle fuel burn. Part of the
modern-research adapter; imported lazily to keep its import order free.
"""
import hashlib
import struct
import weekly_runtime as rt
import modern_tree as tree
from hull_rules import patch

BASE = 0x301000
NUCLEAR = 5
# Reactor, shielding and steam plant: Long Beach and Enterprise carried far
# heavier machinery than oil-fired sisters and cost about twice as much.
WEIGHT_PERCENT, COST_PERCENT = 160, 300
RANGE_FACTOR = 70   # native fuel factor: 100 = Medium, Short 76-86, Very long up to 160
WINDOWS = (
    (0x5CCFA8, 24, "c0a0dec6485bbd0df24bc1e37197543c26d119de4e54df87cee542d02494572d"),   # designer FormShow
    (0x5EBEE4, 56, "1d0bf5d960a90a68235835c270b105547b6b012699e45764be17a6000adb3f25"),   # cbFuelTypeChange
    (0x939040, 96, "789744905b4219e2e1de0144329df6e77125b2b584ba48cdede6a3f5cc5586b7"),   # machinery by type
    (0x939CAA, 392, "18aac4f70561aa2db243ace71719347eb2a8053eea6ad6294a8a9f00831c2e92"),  # fuel/range factor
    (0x7472D4, 28, "3999b1ab292b64c4944c51b3f0d877516ae3ddad465a5b1c38acc6674123baf2"),   # FuelShortageCheckForShip
    # GetFuelPercentage after its prologue: Large Hulls (DD fuel repair) owns the first 5 bytes.
    (0x914601, 44, "c1c452dcc83d8a13ba6ab531c4189a74df62c5257686261076d605fd4fadb200"),
    # GetResults reads the designing nation through the designer form global; the machinery hook does too.
    (0x93BE1D, 0x12, "686f48f769dd170a03dc9e128e09985b7c55191169f2c7b1aafe33b38982e390"),
    # A division's battle fuel turn: each ship burns fuel by speed, then "at minimum fuel level", 5 knots.
    (0x923EF1, 0xCB, "875434e7b87058ee2b7aeaff0818757b6cd01beb64690c5608eb3ae43c4223ac"),
)
ADDRESSES = dict(form_show=0x5CCFA8, fuel_change=0x5EBF05, machinery=0x93907C, range_factor=0x939D6A,
                 shortage=0x7472D5, fuel_percent=0x914606, range_skip=0x939E32, shortage_back=0x7472DC,
                 has_research=0x729FA4, message=0x4D7124, burn=0x923EFA, burn_skip=0x923FBC)
SITES = (("form_show", 5), ("fuel_change", 6), ("machinery", 7), ("range_factor", 8), ("shortage", 7), ("fuel_percent", 6),
         ("burn", 6))
TEXT = "Nuclear propulsion needs research: Naval nuclear propulsion (1961, Machinery). Set to Oil + Turbine."


def discover(blob, base, normalized):
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Nuclear propulsion refuses changed native code at "+hex(address)+".")
    delta = base-BASE
    for name, address in (("cbFuelTypeChange", 0x5EBEE4), ("FuelShortageCheckForShip", 0x7472D4),
                          ("GetFuelPercentage", 0x9145FC), ("HasResearchId", 0x729FA4)):
        if rt.method_address(blob, base, name) != address+delta:
            raise ValueError("Unsupported native propulsion method: "+name)
    info = {k: v+delta for k, v in ADDRESSES.items()}
    info["design_form"] = struct.unpack_from("<I", blob, 0x93BE1E-BASE)[0]   # live address of that global
    info["sites"] = [dict(name=name, address=ADDRESSES[name]+delta,
                          original=blob[ADDRESSES[name]-BASE:ADDRESSES[name]-BASE+size].hex()) for name, size in SITES]
    return info


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def build(page, info):
    """Code in its own page; returns blocks and patches."""
    from campaign_security import Code   # imported late: campaign_security imports modern_research
    at = dict(form_show=page, fuel_change=page+0x100, machinery=page+0x200, range_factor=page+0x300,
              shortage=page+0x380, fuel_percent=page+0x400, burn=page+0x480, name=page+0x500, text=page+0x600)
    original = {site["name"]: bytes.fromhex(site["original"]) for site in info["sites"]}
    code = {}
    c = Code(at["form_show"])   # EAX designer form: add "Nuclear" once, before any design is shown
    c.emit(bytes.fromhex("608b80640500008b80040300008bd88b08ff511483f805")); c.branch(b"\x0f\x85", "done")
    c.emit(b"\x8b\xc3\xba"); c.u32(at["name"]+12); c.emit(bytes.fromhex("8b08ff513c"))   # Items.Add
    c.mark("done"); c.emit(b"\x61"+original["form_show"]); c.branch(b"\xe9", info["form_show"]+5)
    code["form_show"] = c.finish()
    c = Code(at["fuel_change"])   # AL list index, EBX form, ESI design
    c.emit(b"\x3c"+bytes([NUCLEAR])); c.branch(b"\x0f\x85", "store")
    c.emit(b"\x50\x8b\x83"); c.u32(0xC63); c.emit(b"\xba"); c.u32(tree.NUCLEAR_PROPULSION)
    c.branch(b"\xe8", info["has_research"]); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x85", "store")
    c.emit(b"\x60\xb8"); c.u32(at["text"]+12); c.emit(bytes.fromhex("83caff83c9ff")); c.branch(b"\xe8", info["message"])
    c.emit(b"\x8b\x83"); c.u32(0x564); c.emit(bytes.fromhex("ba020000008b08ff9170010000"))   # ItemIndex := 2
    c.emit(b"\x61\xb0\x02")
    c.mark("store"); c.emit(original["fuel_change"]); c.branch(b"\xe9", info["fuel_change"]+6)
    code["fuel_change"] = c.finish()
    c = Code(at["machinery"])   # EBX design: after type-specific machinery weight [+A60] and cost [+A80]
    c.emit(b"\x80\xbb"); c.u32(0x9D4); c.emit(bytes([NUCLEAR])); c.branch(b"\x0f\x85", "native")
    c.emit(b"\x50\x51\x52\xa1"); c.u32(info["design_form"]); c.emit(b"\x8b\x00\x85\xc0"); c.branch(b"\x0f\x84", "weigh")
    c.emit(b"\x8b\x80"); c.u32(0xC63); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "weigh")   # designing nation
    c.emit(b"\xba"); c.u32(tree.THORIUM[0]); c.branch(b"\xe8", info["has_research"])
    c.mark("weigh")   # AL: thorium reactors (EAX is 0 without a designer form or nation)
    c.emit(b"\xb9"); c.u32(WEIGHT_PERCENT); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "percent")
    c.emit(b"\xb9"); c.u32(tree.THORIUM[1])
    c.mark("percent"); c.emit(b"\x8b\x83"); c.u32(0xA60); c.emit(b"\x0f\xaf\xc1\xb9"); c.u32(100)
    c.emit(b"\x99\xf7\xf9\x89\x83"); c.u32(0xA60)
    c.emit(b"\x8b\x83"); c.u32(0xA80); c.emit(b"\x69\xc0"); c.u32(COST_PERCENT)
    c.emit(b"\x99\xf7\xf9\x89\x83"); c.u32(0xA80)
    c.emit(b"\x5a\x59\x58")
    c.mark("native"); c.emit(original["machinery"]); c.branch(b"\xe9", info["machinery"]+7)
    code["machinery"] = c.finish()
    c = Code(at["range_factor"])   # EBX design, ESI fuel factor for the chosen range
    c.emit(b"\x80\xbb"); c.u32(0x9D4); c.emit(bytes([NUCLEAR])); c.branch(b"\x0f\x85", "native")
    c.emit(b"\xbe"); c.u32(RANGE_FACTOR); c.branch(b"\xe9", info["range_skip"])
    c.mark("native"); c.emit(b"\x3c\x01"); c.branch(b"\x0f\x86", info["range_skip"]); c.branch(b"\xe9", info["range_factor"]+8)
    code["range_factor"] = c.finish()
    c = Code(at["shortage"])   # EDX ship; nuclear ships leave like coal ships: no oil-supply effect
    c.emit(original["shortage"]+b"\x3c"+bytes([NUCLEAR])); c.branch(b"\x0f\x85", "native")
    c.emit(b"\x31\xc0\x5b\xc3")
    c.mark("native"); c.branch(b"\xe9", info["shortage_back"])
    code["shortage"] = c.finish()
    c = Code(at["fuel_percent"])   # EBX ship, EAX already 100: no capacity reads as full
    c.emit(b"\x80\xbb"); c.u32(0x9D4); c.emit(bytes([NUCLEAR])); c.branch(b"\x0f\x85", "native")
    c.emit(b"\x31\xf6"); c.branch(b"\xe9", info["fuel_percent"]+6)
    c.mark("native"); c.emit(original["fuel_percent"]); c.branch(b"\xe9", info["fuel_percent"]+6)
    code["fuel_percent"] = c.finish()
    c = Code(at["burn"])   # EBX ship in its division's battle fuel turn: a reactor stays full and burns nothing
    c.emit(b"\x80\xbb"); c.u32(0x9D4); c.emit(bytes([NUCLEAR])); c.branch(b"\x0f\x85", "native")
    c.emit(b"\x8b\x83"); c.u32(0xA50); c.emit(b"\x89\x83"); c.u32(0xA4C); c.branch(b"\xe9", info["burn_skip"])
    c.mark("native"); c.emit(original["burn"]); c.branch(b"\xe9", info["burn"]+6)
    code["burn"] = c.finish()
    blocks = [dict(name="Nuclear list entry", address=at["name"], bytes=literal("Nuclear").hex()),
              dict(name="Nuclear research text", address=at["text"], bytes=literal(TEXT).hex())]
    plans = []
    for site in info["sites"]:
        body = code[site["name"]]
        limit = 0x80 if site["name"] in ("range_factor", "shortage", "burn") else 0x100
        if len(body) > limit: raise ValueError("Nuclear propulsion code exceeds its reservation: "+site["name"])
        blocks.append(dict(name="Nuclear propulsion: "+site["name"], address=at[site["name"]], bytes=body.hex()))
        old = original[site["name"]]
        plans.append(patch("Nuclear propulsion: "+site["name"], site["address"], old,
                           b"\xe9"+struct.pack("<i", at[site["name"]]-site["address"]-5)+b"\x90"*(len(old)-5)))
    return blocks, plans

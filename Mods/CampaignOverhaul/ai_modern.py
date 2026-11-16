"""AI ship designs use the modern options their nation has researched and its economy can carry.

The designer's modern options (Nuclear propulsion, railgun main batteries, lasers, hypersonic and super heavy
SSMs) are player choices; the AI's template designs never pick them. After AIDesignShip's weight passes, the
first recompute of its hull-trim loop runs this pass once per AI design, with the designer's own legality rules
(research, hull, drive, power) and the economy deciding:

- tier 0, the nation spends more than it earns or holds less than a month of budget in cash: nothing;
- tier 1, it earns more than it spends and holds a month of budget: hypersonic SSMs on SSM ships, and lasers
  (half the tier-2 count) where the plant has spare power;
- tier 2, a surplus of at least a tenth of its monthly budget and three months in cash: also Nuclear propulsion
  for capital ships and carriers of NUCLEAR_TONS or more, railgun main batteries on gas-turbine or nuclear ships
  with the power for them, super heavy SSMs on CA, BC and BB hulls that carry heavy SSMs, and the full laser fit.

Every option is undone if the design comes out overweight; the trim loop then gives the rest of the spare weight
back as hull. CHANCE keeps fleets varied. Part of the modern-research adapter; imported lazily.
"""
import hashlib
import modern_extension as extension
import modern_propulsion as propulsion
import modern_railgun as railgun
import modern_tree as tree

BASE = 0x301000
SITE, SITE_BYTES = 0x7B6B03, "e8f02a1800"     # AIDesignShip: call RecomputeValues, first in the trim loop (ESI = pass)
WINDOW = (0x7B6AFE, 0x2F, "5ae25c7f1767d8587651bcce5f1d5d89319c235bad74b03e0864a50d9b1585da")
NATIVE = dict(recompute=0x9395F8, get_nation=0x750040, has_research=0x729FA4, monthly_balance=0x72D2EC,
              modified_budget=0x71F06C, random=0x307834, count_missiles=0x94F890)
FUNDS, WEIGHT_LEFT, TYPE, DRIVE, ELEVATION = 0x1B5, 0xB20, 0x9D3, 0x9D4, 0x9A6   # nation and design fields
NUCLEAR_TONS, NUCLEAR_TYPES = 20000, (0, 1, 3, 5, 6)     # BB, BC, CA, CV, CVL of at least this displacement
LASER_FIT = ((8000, 2), (20000, 4), (None, railgun.MAX_LASERS))   # displacement below -> lasers (tier 2)
CHANCE = dict(nuclear=60, railgun=50, super=60, hyper=80)          # percent of eligible designs
ANY_SSM = 0xE                                                       # CountMissileLaunchers: any SSM mount


def discover(blob, base, normalized):
    at, size, digest = WINDOW
    if hashlib.sha256(normalized[at-BASE:at-BASE+size]).hexdigest() != digest:
        raise ValueError("AI modern designs refuse changed native code in AIDesignShip.")
    delta = base-BASE
    if blob[SITE+delta-base:SITE+delta-base+5].hex() != SITE_BYTES:
        raise ValueError("Unsupported AI design recompute call.")
    return dict(site=SITE+delta, original=SITE_BYTES, **{k: v+delta for k, v in NATIVE.items()})


def build(page, info, ext, power):
    """One page: the hook and the pass. ext: modern_extension's lookup; power: modern_railgun's power()."""
    from campaign_security import Code   # imported late: campaign_security imports modern_research
    from hull_rules import patch
    n, c = info, Code(page)

    def research(ident):    # ESI nation; returns from the option without it
        c.emit(b"\x8b\xc6\xba"); c.u32(ident); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "ret")

    def chance(percent):
        c.emit(b"\xb8"); c.u32(100); c.branch(b"\xe8", n["random"]); c.emit(b"\x83\xf8"+bytes([percent])); c.branch(b"\x0f\x8d", "ret")

    def recompute():
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["recompute"])

    def overweight(back):   # recompute, then to back when the weight left is negative
        recompute(); c.emit(b"\x83\xbb"); c.u32(WEIGHT_LEFT); c.emit(b"\x00"); c.branch(b"\x0f\x8c", back)

    def one_of(field, values, target):
        c.emit(b"\x0f\xb6\x83"); c.u32(field)
        for value in values: c.emit(b"\x3c"+bytes([value])); c.branch(b"\x0f\x84", target)
        c.branch(b"\xe9", "ret")

    def missiles(kind):     # the design carries SSM mounts of kind
        c.emit(b"\x8b\xc3\xb2"+bytes([kind])+b"\x33\xc9"); c.branch(b"\xe8", n["count_missiles"])
        c.emit(b"\x85\xc0"); c.branch(b"\x0f\x8e", "ret")

    def powered(back):      # railgun and laser MW needed must not exceed the spare MW
        c.emit(b"\x8b\xc3\x8b\xd6\x33\xc9"); c.branch(b"\xe8", power); c.emit(b"\x3b\xc2"); c.branch(b"\x0f\x87", back)

    def flag(bit, name):    # set an extension bit, kept only if the design still floats
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "ret")
        c.emit(b"\xf7\x00"); c.u32(bit); c.branch(b"\x0f\x85", "ret")
        c.emit(b"\x81\x08"); c.u32(bit); c.emit(b"\x50"); overweight(f"{name}_back"); c.emit(b"\x58\xc3")
        c.mark(f"{name}_back"); c.emit(b"\x58\x81\x20"); c.u32(~bit & 0xffffffff); recompute(); c.emit(b"\xc3")

    # Hook (EAX design, ESI trim-loop pass, EDI main): the pass runs once, before the first recompute.
    c.emit(b"\x85\xf6"); c.branch(b"\x0f\x85", "recompute")
    c.emit(b"\x60\x8b\xd8\x8b\x53\x1c\x8b\xc7"); c.branch(b"\xe8", n["get_nation"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "restore"); c.emit(b"\x8b\xf0"); c.branch(b"\xe8", "pass")
    c.mark("restore"); c.emit(b"\x61")
    c.mark("recompute"); c.branch(b"\xe9", n["recompute"])

    # Pass (EBX design, ESI nation): EDI = economy tier from the monthly balance and cash in months of budget.
    c.mark("pass")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["modified_budget"])
    c.emit(b"\x33\xd2\xb9\x0c\x00\x00\x00\xf7\xf1\x50\x8b\xc6"); c.branch(b"\xe8", n["monthly_balance"])   # push month
    c.emit(b"\x59\x33\xff\x85\xc0"); c.branch(b"\x0f\x8e", "tiered")
    c.emit(b"\x8b\x96"); c.u32(FUNDS); c.emit(b"\x3b\xd1"); c.branch(b"\x0f\x8c", "tiered")
    c.emit(b"\x47\x6b\xc0\x0a\x3b\xc1"); c.branch(b"\x0f\x8c", "tiered")              # tier 1; balance*10 vs month
    c.emit(b"\x6b\xc9\x03\x3b\xd1"); c.branch(b"\x0f\x8c", "tiered"); c.emit(b"\x47")  # three months: tier 2
    c.mark("tiered"); c.emit(b"\x85\xff"); c.branch(b"\x0f\x84", "ret")
    c.emit(b"\x83\xff\x02"); c.branch(b"\x0f\x8c", "cheap")
    for name in ("nuclear", "railgun", "super"): c.branch(b"\xe8", name)
    c.mark("cheap"); c.branch(b"\xe8", "hyper"); c.branch(b"\xe8", "lasers")
    c.mark("ret"); c.emit(b"\xc3")

    c.mark("nuclear")
    c.emit(b"\x80\xbb"); c.u32(DRIVE); c.emit(bytes([propulsion.NUCLEAR])); c.branch(b"\x0f\x84", "ret")
    c.emit(b"\x81\x7b\x2c"); c.u32(NUCLEAR_TONS); c.branch(b"\x0f\x8c", "ret")
    one_of(TYPE, NUCLEAR_TYPES, "nuclear_hull")
    c.mark("nuclear_hull"); research(tree.NUCLEAR_PROPULSION); chance(CHANCE["nuclear"])
    c.emit(b"\x0f\xb6\x83"); c.u32(DRIVE); c.emit(b"\x50\xc6\x83"); c.u32(DRIVE); c.emit(bytes([propulsion.NUCLEAR]))
    overweight("nuclear_back"); c.emit(b"\x58\xc3")
    c.mark("nuclear_back"); c.emit(b"\x58\x88\x83"); c.u32(DRIVE); recompute(); c.emit(b"\xc3")

    c.mark("railgun")
    c.emit(b"\x83\x7b\x6d\x00"); c.branch(b"\x0f\x8e", "ret")
    c.emit(b"\x80\xbb"); c.u32(ELEVATION); c.emit(bytes([railgun.RAILGUN])); c.branch(b"\x0f\x84", "ret")
    one_of(DRIVE, railgun.ELECTRIC, "railgun_drive")
    c.mark("railgun_drive"); research(tree.RAILGUN); chance(CHANCE["railgun"])
    c.emit(b"\x0f\xb6\x83"); c.u32(ELEVATION); c.emit(b"\x50\xc6\x83"); c.u32(ELEVATION); c.emit(bytes([railgun.RAILGUN]))
    powered("railgun_back"); overweight("railgun_back"); c.emit(b"\x58\xc3")
    c.mark("railgun_back"); c.emit(b"\x58\x88\x83"); c.u32(ELEVATION); recompute(); c.emit(b"\xc3")

    c.mark("super")
    one_of(TYPE, railgun.SUPER_TYPES, "super_hull")
    c.mark("super_hull"); missiles(railgun.HEAVY_SSM_MOUNT); research(tree.SUPER_HEAVY); chance(CHANCE["super"])
    flag(extension.SUPER_HEAVY_BIT, "super")

    c.mark("hyper")
    missiles(ANY_SSM); research(tree.HYPERSONIC); chance(CHANCE["hyper"]); flag(extension.HYPERSONIC_BIT, "hyper")

    c.mark("lasers")        # as many as LASER_FIT gives (half in tier 1) and the plant can power
    research(tree.LASERS)
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "ret")
    c.emit(b"\x80\x38\x00"); c.branch(b"\x0f\x85", "ret"); c.emit(b"\x50")
    for index, (tons, count) in enumerate(LASER_FIT):
        c.emit(b"\xb9"); c.u32(count)
        if tons is not None: c.emit(b"\x81\x7b\x2c"); c.u32(tons); c.branch(b"\x0f\x8c", "laser_tier")
    c.mark("laser_tier"); c.emit(b"\x83\xff\x02"); c.branch(b"\x0f\x8d", "laser_try"); c.emit(b"\xd1\xe9")
    c.mark("laser_try"); c.emit(b"\x8b\x04\x24\x88\x08\x51\x8b\xc3\x8b\xd6\x33\xc9"); c.branch(b"\xe8", power)
    c.emit(b"\x59\x3b\xc2"); c.branch(b"\x0f\x86", "laser_fits"); c.emit(b"\x49"); c.branch(b"\x0f\x85", "laser_try")
    c.emit(b"\x58\xc6\x00\x00"); c.branch(b"\xe9", "laser_none")
    c.mark("laser_fits"); overweight("laser_drop"); c.emit(b"\x58\xc3")
    c.mark("laser_drop"); c.emit(b"\x58\xc6\x00\x00")
    c.mark("laser_none"); recompute(); c.emit(b"\xc3")

    code = c.finish()
    if len(code) > 0x1000: raise ValueError("AI modern design code exceeds its page.")
    plan = patch("AI designs use modern options", n["site"], bytes.fromhex(n["original"]),
                 b"\xe8"+(page-n["site"]-5).to_bytes(4, "little", signed=True))
    return [dict(name="AI modern designs", address=page, bytes=code.hex())], [plan]

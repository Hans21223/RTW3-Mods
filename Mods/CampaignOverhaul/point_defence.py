"""Point defence: SeaRAM and gun-missile CIWS mounts, RAM launchers and fire-control channels.

Designer, a strip under the armament tabs beside Topside load: SeaRAM mounts (0-3, modern_tree.SEARAM), Gun-missile
CIWS mounts (0-7, tree.GUN_MISSILE), Spare missiles (0-3 reload steps, for designs with either), a RAM launchers tick
box (tree.RAM) and a readout line: the point-defence systems fitted against the fire-control channels the design has,
and the missiles its mounts carry. The values live in modern_extension's data dword (SPARE_SHIFT, SEARAM_SHIFT,
GUN_MISSILE_SHIFT, RAM_BIT; bits 24-29 are saved in the elevation integer's spare bits).
- Weight and cost, counted with the armament (modern_railgun's ammunition hook calls weight): MOUNTS tons and cost a
  mount, spare_tons and SPARE_COST a spare step and mount; RAM: light SAM launchers weigh RAM_PERCENT% more, at
  RAM_COST_PER_TON for the added tons.
- Topside load (GetTopsideLoad, before its capacity test): MOUNTS topside points a mount and LASER_TOPSIDE a laser,
  with a report line.
- Battle (ResolveMissileHit, after SAMs and decoys, before lasers): a ship has CHANNELS fire-control channels, +1 for
  each AA director up to DIRECTORS, +1 with a working Aegis search radar (class 6), +2 with AESA (class 7). Each
  layer that engages an incoming missile uses one, in order: SeaRAM, gun-missile, lasers (modern_railgun), the native
  gun CIWS; layers past the channels hold fire. A layer knocked out with the superstructure uses none. Railgun point
  defence is gunfire and needs none. SeaRAM fires SALVO missiles; gun-missile fires SALVO missiles, then its guns.
  Chances grow with mounts, fall as the native CIWS's with the missiles already met this turn (random(100+30 each)),
  and pass modern_railgun's kill-stands rules (hypersonic and low-observable SSMs). A mount carries MOUNTS missiles
  x (2 + spare steps + 1 with tree.PD_MAGAZINES) / 2; a battle ship counts the ones fired in its third extension
  dword (SeaRAM low word, gun-missile high word).
- RAM: modern_defence calls ram_sam at the SAM saturation count, and a RAM ship's light SAMs count half of it.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct
import modern_tree as tree
from modern_extension import SPARE_SHIFT, SEARAM_SHIFT, GUN_MISSILE_SHIFT, RAM_BIT, ATT_SHIFT

BASE = 0x301000
MOUNTS = dict(   # chances in percent: one mount, each more mount, the cap
    searam=dict(shift=SEARAM_SHIFT, mask=3, tons=8, cost=150, topside=5, missiles=11, spare_tons=3,
                research=tree.SEARAM, chance=40, step=10, cap=60),
    gun_missile=dict(shift=GUN_MISSILE_SHIFT, mask=7, tons=15, cost=200, topside=6, missiles=32, spare_tons=5,
                     research=tree.GUN_MISSILE, chance=35, step=5, cap=50, gun=20, gun_step=5, gun_cap=35))
PD_BITS = sum(m["mask"] << m["shift"] for m in MOUNTS.values())
SPARE_MAX, SPARE_COST, LASER_TOPSIDE = 3, 40, 3
SALVO, SATURATION = 2, 30
CHANNELS, DIRECTORS, RADAR_CHANNELS = 2, 2, (6, 7)   # each radar class reached adds a channel
RAM_PERCENT, RAM_COST_PER_TON, LIGHT_SAM = 20, 10, 3
# Anti-torpedo torpedo launchers (tree.ANTI_TORPEDO; the battle rule is undersea's): per launcher.
ATT = dict(shift=ATT_SHIFT, mask=3, tons=6, cost=120, topside=2, load=4, research=tree.ANTI_TORPEDO)
SHIP = dict(nation=0x14, mounts=0x9E, ciws=0x9E6, directors=0x9EE, ciws_flag=0x9F3, radar=0xA0B, radar_down=0xA0F,
            weight=0xAA4, cost=0xA8C, handled=0xE01)
# 96-DPI bounds on the designer form (it is 1359 x 739; this strip is under Topside load, left of Save and finish).
BOUNDS = dict(searam=((680, 684), (722, 680, 41, 22)), gun_missile=((776, 684), (868, 680, 41, 22)),
              spare=((920, 684), (994, 680, 41, 22)), ram=(1048, 683, 104, 17), att=((1160, 684), (1186, 680, 41, 22)),
              readout=(680, 710))
MAGIC = {name: 0x50444E30+index for index, name in enumerate(
    ("searam", "searam_label", "gun_missile", "gun_missile_label", "spare", "spare_label", "ram", "readout",
     "att", "att_label"))}
CONTROLS = ("searam", "gun_missile", "spare", "ram", "att")   # each: sync, create, its label's create, change
CONTROL_ROOM = dict(sync=0x100, create=0xB0, label=0x80, change=0xE0)
TOPSIDE_SITE, TOPSIDE_ORIGINAL = 0x94B6B7, "8b45fce8d90d0000"   # mov eax,[ebp-4]; call GetTopsidePoints
WINDOW = (0x94B6B7, 0x17, "59fbf83f629df24900a573132b29bb284cb9f4b6ee33672c679591afc6090d9f")   # to the flag store
NATIVE = dict(topside_points=0x94C498, topside_back=0x94B6BF, cat3=0x30C694)
S, G = MOUNTS["searam"], MOUNTS["gun_missile"]
TEXT = dict(
    searam_caption="SeaRAM",
    searam_hint=f"SeaRAM: {S['missiles']}-missile launcher with its own radar. {S['tons']} t, {S['topside']} topside "
                "points each.",
    searam_research="SeaRAM mounts need research: SeaRAM self-contained launchers (2008, Vertical launch systems).",
    gun_missile_caption="Gun-missile CIWS",
    gun_missile_hint=f"Gun-missile CIWS (Kashtan): missiles, then 30 mm guns. {G['missiles']} missiles, "
                     f"{G['tons']} t, {G['topside']} topside points each.",
    gun_missile_research="Gun-missile CIWS mounts need research: Gun-missile close-in weapon systems (1989, Vertical "
                         "launch systems).",
    spare_caption="Spare missiles",
    spare_hint=f"Reload missiles for SeaRAM and gun-missile mounts: +50% each step, {S['spare_tons']}-"
               f"{G['spare_tons']} t per mount.",
    spare_research="Spare missiles are reloads for SeaRAM or gun-missile mounts: fit some first.",
    ram_caption="RAM launchers",
    ram_hint=f"RAM launchers: light SAMs cope better with many missiles at once. Light SAMs {RAM_PERCENT}% heavier.",
    ram_research="RAM launchers need research: Rolling airframe missiles (1991, Vertical launch systems).",
    att_caption="ATT",
    att_hint=f"Anti-torpedo torpedoes: may destroy enemy torpedoes close in. {ATT['load']} per launcher, "
             f"{ATT['tons']} t, {ATT['topside']} topside points each.",
    att_research="ATT launchers need research: Anti-torpedo torpedoes (2013, Vertical launch systems).",
    att=", ATT ",
    readout_hint=f"Each point-defence system needs a fire-control channel. Channels: {CHANNELS}, +1 per AA "
                 f"director (up to {DIRECTORS}), +1 Aegis radar, +2 AESA.",
    pd="Point defence: ", systems=" systems / ", channels=" channels", short=" - too few channels",
    missiles=".   Missiles: SeaRAM ", gm=", gun-missile ", topside="Point defence: ",
    searam_shot=" Incoming missile shot down by SeaRAM.",
    gun_missile_shot=" Incoming missile shot down by gun-missile CIWS.",
    gun_missile_gun_shot=" Incoming missile shot down by gun-missile CIWS guns.")
# Offsets in the first code page: entry points other modules call, and battle data.
OFFSETS = dict(layer=0x0, weight=0x300, ram_sam=0x4C0, sync=0x500, channel=0x540, ram_kind=0x544)


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def addresses(page):
    """Entry points and data for modern_railgun (layer, channel, weight, sync) and modern_defence (ram_sam, ram_kind)."""
    return {name: page+offset for name, offset in OFFSETS.items()}


def discover(blob, base, normalized):
    at, size, digest = WINDOW
    if hashlib.sha256(normalized[at-BASE:at-BASE+size]).hexdigest() != digest:
        raise ValueError("Point defence refuses changed native code in GetTopsideLoad.")
    delta = base-BASE
    if blob[TOPSIDE_SITE-BASE:TOPSIDE_SITE-BASE+8].hex() != TOPSIDE_ORIGINAL:
        raise ValueError("Unsupported topside load code.")
    info = {k: v+delta for k, v in NATIVE.items()}
    info["topside"] = TOPSIDE_SITE+delta
    return info


def build(page, info, railgun_info, railgun_page, ext):
    """Three pages: code at page and page+0x1000, texts at page+0x2000. railgun_info: modern_railgun's discovery
    (VCL and battle addresses); railgun_page: its first page (find, scale, stands, laser layer)."""
    from campaign_security import Code   # imported late: campaign_security imports modern_research
    from hull_rules import patch
    import modern_combat as combat
    import modern_railgun as railgun
    n, r, F, V = info, railgun_info, railgun.FORM, railgun.VCL
    at = addresses(page)
    at.update(attempt_sam=page+0x280, attempt_gun=page+0x2C0, topside=page+0x400, readout=page+0x580,
              create_readout=page+0x800, find=railgun_page+railgun.FIND, scale=railgun_page+railgun.SCALE,
              laser_layer=railgun_page+railgun.LASER_LAYER, sam_stands=railgun_page+railgun.SAM_STANDS,
              gun_stands=railgun_page+railgun.GUN_STANDS)
    base, R = page+0x1000, CONTROL_ROOM
    for name in CONTROLS:
        at.update({name+"_sync": base, "create_"+name: base+R["sync"], "create_"+name+"_label": base+R["sync"]+R["create"],
                   name+"_change": base+R["sync"]+R["create"]+R["label"]})
        base += sum(R.values())
    assert base <= page+0x2000
    texts, blocks = {}, []
    areas = [(page+0x2000, page+0x3000), (page+0x880, page+0x1000)]   # after the code
    offset, end = areas.pop(0)
    for key, text in TEXT.items():
        body = literal(text)
        while offset+len(body) > end:
            if not areas: raise ValueError("Point defence texts exceed their pages.")
            offset, end = areas.pop(0)
        texts[key] = offset+12
        blocks.append(dict(name="Point defence text: "+key, address=offset, bytes=body.hex()))
        offset += (len(body)+15) & ~15
    code, chan = {}, at["channel"]

    def call_slot(c, slot): c.emit(b"\x8b\x08\xff\x91"); c.u32(slot)   # mov ecx,[eax]; call [ecx+slot]

    def channels(c):   # ESI ship or design -> ECX its fire-control channels; clobbers EAX
        c.emit(b"\xb9"); c.u32(CHANNELS)
        c.emit(b"\x83\xbe"); c.u32(SHIP["radar_down"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "no_radar")
        c.emit(b"\x8b\x86"); c.u32(SHIP["radar"])
        for level in RADAR_CHANNELS:
            c.emit(b"\x83\xf8"+bytes([level])); c.branch(b"\x0f\x8c", "no_radar"); c.emit(b"\x41")
        c.mark("no_radar"); c.emit(b"\x8b\x86"); c.u32(SHIP["directors"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x8e", "no_directors")
        c.emit(b"\x83\xf8"+bytes([DIRECTORS])); c.branch(b"\x0f\x8e", "directors"); c.emit(b"\xb8"); c.u32(DIRECTORS)
        c.mark("directors"); c.emit(b"\x03\xc8")
        c.mark("no_directors")

    def mounts_of(c, kind, register=b"\x07"):   # EAX := mounts of kind from the data at [EDI] (\xc6: ESI, \xc7: EDI)
        m = MOUNTS[kind]
        c.emit(b"\x8b"+register+b"\xc1\xe8"+bytes([m["shift"]])+b"\x83\xe0"+bytes([m["mask"]]))

    def capped(c, chance, step, cap):   # EAX mounts -> EAX chance; clobbers nothing else
        c.emit(b"\x48\x6b\xc0"+bytes([step])+b"\x83\xc0"+bytes([chance])+b"\x83\xf8"+bytes([cap]))
        c.branch(b"\x0f\x8e", f"capped{chance}"); c.emit(b"\xb8"); c.u32(cap); c.mark(f"capped{chance}")

    # ResolveMissileHit, entered from modern_railgun's site before lasers: ESI target ship, EBX incoming missile,
    # EBP frame. Sets the channels, then SeaRAM and gun-missile layers; the laser layer follows.
    c = Code(at["layer"]); c.emit(b"\x60"); channels(c); c.emit(b"\x88\x0d"); c.u32(chan)
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "out"); c.emit(b"\x8b\xf8")
    for index, kind in enumerate(MOUNTS):
        m = MOUNTS[kind]
        mounts_of(c, kind); c.branch(b"\x0f\x84", f"next_{kind}")
        c.emit(b"\x80\x3d"); c.u32(chan); c.emit(b"\x00"); c.branch(b"\x0f\x84", "out")
        c.emit(b"\x50\xb8\x64\x00\x00\x00"); c.branch(b"\xe8", r["random"])                 # [esp] mounts
        c.emit(b"\x50\x8b\xc6"); c.branch(b"\xe8", r["superstructure"]); c.emit(b"\x5a\x3b\xd0")
        c.branch(b"\x0f\x8e", f"skip_{kind}")                                               # knocked out
        combat.researched(c, r, b"\x8b\x56"+bytes([SHIP["nation"]]), tree.PD_MAGAZINES[0], f"asked_{kind}")
        c.emit(b"\x0f\xb6\xc8\x8b\x17\xc1\xea"+bytes([SPARE_SHIFT])+b"\x83\xe2"+bytes([SPARE_MAX])+b"\x8d\x4c\x11\x02")
        c.emit(b"\x8b\x04\x24\x6b\xc0"+bytes([m["missiles"]])+b"\x0f\xaf\xc1\xd1\xe8")      # the load
        c.emit(b"\x0f\xb7\x4f"+bytes([8+2*index])+b"\x2b\xc1"); c.branch(b"\x0f\x8e", f"dry_{kind}")
        c.emit(b"\xfe\x0d"); c.u32(chan)                                                     # it fires: a channel
        c.emit(b"\x83\xf8"+bytes([SALVO])); c.branch(b"\x0f\x8e", f"salvo_{kind}"); c.emit(b"\xb8"); c.u32(SALVO)
        c.mark(f"salvo_{kind}"); c.emit(b"\x66\x01\x47"+bytes([8+2*index]))
        c.emit(b"\x8b\x04\x24"); capped(c, m["chance"], m["step"], m["cap"])
        c.branch(b"\xe8", at["attempt_sam"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", f"kill_{kind}")
        if "gun" in m:   # then the guns, also when the missiles are spent (that takes the channel then)
            c.branch(b"\xe9", f"guns_{kind}")
            c.mark(f"dry_{kind}"); c.emit(b"\xfe\x0d"); c.u32(chan)
            c.mark(f"guns_{kind}"); c.emit(b"\x8b\x04\x24"); capped(c, m["gun"], m["gun_step"], m["gun_cap"])
            c.branch(b"\xe8", at["attempt_gun"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", f"kill_{kind}_gun")
        else: c.mark(f"dry_{kind}")                                                           # spent: holds fire
        c.mark(f"skip_{kind}"); c.emit(b"\x58")
        c.mark(f"next_{kind}")
    c.mark("out"); c.emit(b"\x61"); c.branch(b"\xe9", at["laser_layer"])
    for label, text in (("kill_searam", "searam_shot"), ("kill_gun_missile", "gun_missile_shot"),
                        ("kill_gun_missile_gun", "gun_missile_gun_shot")):
        c.mark(label); c.emit(b"\x83\xc4\x04\x61\x8d\x45\xfc\xba"); c.u32(texts[text]); c.branch(b"\xe8", r["lstr_asg"])
        c.branch(b"\xe9", r["ciws_shot"])
    code["layer"] = c.finish()
    # attempt(EAX chance; ESI ship, EBX missile) -> AL 1 when the shot kills and the kill stands.
    for name, stands in (("attempt_sam", "sam_stands"), ("attempt_gun", "gun_stands")):
        c = Code(at[name]); c.emit(b"\x50\x6b\x86"); c.u32(SHIP["handled"]); c.emit(bytes([SATURATION])+b"\x83\xc0\x64")
        c.branch(b"\xe8", r["random"]); c.emit(b"\x5a\x3b\xc2"); c.branch(b"\x0f\x8d", "miss"); c.branch(b"\xe9", at[stands])
        c.mark("miss"); c.emit(b"\x33\xc0\xc3")
        code[name] = c.finish()

    # weight(EDX design): armament weight and cost of the mounts, their spares and RAM launchers. Keeps every register.
    c = Code(at["weight"]); c.emit(b"\x60\x8b\xda\x8b\xc2"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x30\x8b\xfe\xc1\xef"+bytes([SPARE_SHIFT])+b"\x83\xe7"+bytes([SPARE_MAX]))   # ESI data, EDI steps
    c.emit(b"\x8b\xc6\xc1\xe8"+bytes([ATT["shift"]])+b"\x83\xe0"+bytes([ATT["mask"]]))          # ATT launchers
    c.emit(b"\x6b\xc8"+bytes([ATT["tons"]])+b"\x01\x8b"); c.u32(SHIP["weight"])
    c.emit(b"\x6b\xc8"+bytes([ATT["cost"]])+b"\x01\x8b"); c.u32(SHIP["cost"])
    for kind, m in MOUNTS.items():
        mounts_of(c, kind, b"\xc6")
        c.emit(b"\x6b\xc8"+bytes([m["tons"]])+b"\x01\x8b"); c.u32(SHIP["weight"])
        c.emit(b"\x69\xc8"); c.u32(m["cost"]); c.emit(b"\x01\x8b"); c.u32(SHIP["cost"])
        c.emit(b"\x0f\xaf\xc7\x6b\xc8"+bytes([m["spare_tons"]])+b"\x01\x8b"); c.u32(SHIP["weight"])
        c.emit(b"\x6b\xc8"+bytes([SPARE_COST])+b"\x01\x8b"); c.u32(SHIP["cost"])
    c.emit(b"\xf7\xc6"); c.u32(RAM_BIT); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x83"); c.u32(SHIP["mounts"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x48\x08\x8b\x50\x04\x33\xed")
    c.mark("mount"); c.emit(b"\x49"); c.branch(b"\x0f\x88", "sum")
    c.emit(b"\x8b\x04\x8a\x80\x78\x0e"+bytes([LIGHT_SAM])); c.branch(b"\x0f\x85", "mount")
    c.emit(b"\x03\x68\x0a"); c.branch(b"\xe9", "mount")
    c.mark("sum"); c.emit(b"\x6b\xc5"+bytes([RAM_PERCENT])+b"\x33\xd2\xb9\x64\x00\x00\x00\xf7\xf1\x01\x83"); c.u32(SHIP["weight"])
    c.emit(b"\x6b\xc0"+bytes([RAM_COST_PER_TON])+b"\x01\x83"); c.u32(SHIP["cost"])
    c.mark("done"); c.emit(b"\x61\xc3")
    code["weight"] = c.finish()

    # GetTopsideLoad before its capacity test: [ebp-4] design, [ebp-0Ch] load points, [ebp-10h] report list or nil.
    c = Code(at["topside"]); c.emit(b"\x8b\x45\xfc"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x8b\x00\x0f\xb6\xc8\x6b\xc9"+bytes([LASER_TOPSIDE]))
    for m in list(MOUNTS.values())+[ATT]:
        c.emit(b"\x8b\xd0\xc1\xea"+bytes([m["shift"]])+b"\x83\xe2"+bytes([m["mask"]])+b"\x6b\xd2"+bytes([m["topside"]])+b"\x03\xca")
    c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "native"); c.emit(b"\x01\x4d\xf4\x83\x7d\xf0\x00"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x8b\xc1\x8d\x95\x88\xfe\xff\xff"); c.branch(b"\xe8", r["int_to_str"])         # the native line's strings
    c.emit(b"\x8b\x8d\x88\xfe\xff\xff\x8d\x85\x8c\xfe\xff\xff\xba"); c.u32(texts["topside"]); c.branch(b"\xe8", n["cat3"])
    c.emit(b"\x8b\x95\x8c\xfe\xff\xff\x8b\x45\xf0\x8b\x08\xff\x51\x3c")
    c.mark("native"); c.emit(b"\x8b\x45\xfc"); c.branch(b"\xe8", n["topside_points"]); c.branch(b"\xe9", n["topside_back"])
    code["topside"] = c.finish()

    # ram_sam(ESI ship) -> AL 1 when the SAM fired (modern_defence notes its kind) is light and the ship has RAM.
    c = Code(at["ram_sam"]); c.emit(b"\x83\x3d"); c.u32(at["ram_kind"]); c.emit(bytes([LIGHT_SAM])); c.branch(b"\x0f\x85", "no")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\xf7\x00"); c.u32(RAM_BIT); c.emit(b"\x0f\x95\xc0\xc3")
    c.mark("no"); c.emit(b"\x33\xc0\xc3")
    code["ram_sam"] = c.finish()

    # sync(EAX form), from modern_railgun's refresh chain: every control, then the readout.
    c = Code(at["sync"]); c.emit(b"\x53\x8b\xd8")
    for name in CONTROLS+("readout",):
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at.get(name+"_sync", at["readout"]))
    c.emit(b"\x5b\xc3")
    code["sync"] = c.finish()

    def create(c, vmt, magic, bounds, hint):   # EAX form -> ESI new control on the form, EBX form
        c.emit(b"\x53\x56\x8b\xd8\x8b\xcb\xb2\x01\xb8"); c.u32(vmt); c.emit(b"\xff\x50"+bytes([V["create"]]))
        c.emit(b"\x8b\xf0\xc7\x46"+bytes([V["tag"]])); c.u32(magic)
        c.emit(b"\x8b\xd3\x8b\xc6"); call_slot(c, V["set_parent"])
        for setter, value in zip(("set_left", "set_top", "set_width", "set_height"), bounds):
            c.emit(b"\xba"); c.u32(value); c.branch(b"\xe8", at["scale"]); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", r[setter])
        c.emit(b"\x8d\x86"); c.u32(V["hint"]); c.emit(b"\xba"); c.u32(texts[hint]); c.branch(b"\xe8", r["assign"])
        c.emit(b"\xb2\x01\x8b\xc6"); c.branch(b"\xe8", r["set_show_hint"])

    def find_or_create(c, vmt, magic, creator, label):   # EBX form -> EAX the control
        c.emit(b"\x8b\xc3\xba"); c.u32(vmt); c.emit(b"\xb9"); c.u32(magic); c.branch(b"\xe8", at["find"])
        c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", label); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", creator)
        c.mark(label)

    def has_mounts(c):   # ESI design -> AL 1 when it has SeaRAM or gun-missile mounts
        c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no_mounts")
        c.emit(b"\xf7\x00"); c.u32(PD_BITS); c.emit(b"\x0f\x95\xc0")
        c.mark("no_mounts")

    def allowed(c, research):   # EBX form, ESI design -> AL 1 when a value above zero may be set
        if research: c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(research); c.branch(b"\xe8", r["has_research"])
        else: has_mounts(c)

    def store(c, mask, shift):   # EBP value << shift; ESI design, EBX form: the design and its working copy
        c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "resync")
        keep = 0xFFFFFFFF ^ (mask << shift)
        c.emit(b"\x8b\x08\x81\xe1"); c.u32(keep); c.emit(b"\x0b\xcd\x89\x08")
        c.emit(b"\x8b\x83"); c.u32(F["ship2"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "stored")
        c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "stored")
        c.emit(b"\x8b\x08\x81\xe1"); c.u32(keep); c.emit(b"\x0b\xcd\x89\x08")
        c.mark("stored"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", r["recompute"])
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", r["update"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", r["refresh"])
        c.emit(b"\x61\xc3")

    def spin(name, shift, mask, maximum, research):
        """A count box and its caption: name_sync(EAX form), create_name, create_name_label, name_change."""
        label_bounds, spin_bounds = BOUNDS[name]
        c = Code(at[name+"_sync"]); c.emit(b"\x53\x56\x57\x8b\xd8")
        find_or_create(c, r["spin_vmt"], MAGIC[name], at["create_"+name], "have_spin"); c.emit(b"\x8b\xf8")
        find_or_create(c, r["label_vmt"], MAGIC[name+"_label"], at["create_"+name+"_label"], "have_label")
        c.emit(b"\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "done")
        c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "have_value")
        c.emit(b"\x8b\x00\xc1\xe8"+bytes([shift])+b"\x83\xe0"+bytes([mask]))
        c.mark("have_value"); c.emit(b"\x50\x8b\xc7"); c.branch(b"\xe8", r["spin_get"]); c.emit(b"\x3b\x04\x24"); c.branch(b"\x0f\x84", "value_ok")
        c.emit(b"\xff\xb7"); c.u32(V["on_change"]); c.emit(b"\xc7\x87"); c.u32(V["on_change"]); c.u32(0)
        c.emit(b"\x8b\xc7\x8b\x54\x24\x04"); c.branch(b"\xe8", r["spin_set"]); c.emit(b"\x8f\x87"); c.u32(V["on_change"])
        c.mark("value_ok"); c.emit(b"\x33\xd2\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "set_enabled")
        c.emit(b"\xb2\x01\x83\x3c\x24\x00"); c.branch(b"\x0f\x85", "set_enabled")
        allowed(c, research); c.emit(b"\x8b\xd0")
        c.mark("set_enabled"); c.emit(b"\x8b\xc7"); call_slot(c, V["set_enabled"]); c.emit(b"\x58")
        c.mark("done"); c.emit(b"\x5f\x5e\x5b\xc3")
        code[name+"_sync"] = c.finish()

        c = Code(at["create_"+name]); create(c, r["spin_vmt"], MAGIC[name], spin_bounds, name+"_hint")
        c.emit(b"\xc7\x86"); c.u32(V["spin_min"]); c.u32(0); c.emit(b"\xc7\x86"); c.u32(V["spin_max"]); c.u32(maximum)
        c.emit(b"\xc7\x86"); c.u32(V["on_change"]); c.u32(at[name+"_change"]); c.emit(b"\x89\x9e"); c.u32(V["on_change"]+4)
        c.emit(b"\x8b\xc6\x5e\x5b\xc3")
        code["create_"+name] = c.finish()
        c = Code(at["create_"+name+"_label"]); create(c, r["label_vmt"], MAGIC[name+"_label"], label_bounds, name+"_hint")
        c.emit(b"\xba"); c.u32(texts[name+"_caption"]); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", r["set_text"])
        c.emit(b"\x8b\xc6\x5e\x5b\xc3")
        code["create_"+name+"_label"] = c.finish()

        c = Code(at[name+"_change"])   # OnChange(EAX form, EDX box)
        c.emit(b"\x60\x8b\xd8\x8b\xfa\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "resync")
        c.emit(b"\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "resync")
        c.emit(b"\x8b\xc7"); c.branch(b"\xe8", r["spin_get"]); c.emit(b"\x8b\xe8\x83\xfd"+bytes([maximum]))
        c.branch(b"\x0f\x86", "in_range"); c.emit(b"\xbd"); c.u32(maximum)
        c.mark("in_range"); c.emit(b"\x85\xed"); c.branch(b"\x0f\x84", "store")
        allowed(c, research); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", "store")
        c.emit(b"\xb8"); c.u32(texts[name+"_research"]); c.emit(b"\x83\xca\xff\x83\xc9\xff"); c.branch(b"\xe8", r["message"])
        c.branch(b"\xe9", "resync")
        c.mark("store"); c.emit(b"\xc1\xe5"+bytes([shift])); store(c, mask, shift)
        c.mark("resync"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at[name+"_sync"]); c.emit(b"\x61\xc3")
        code[name+"_change"] = c.finish()

    for kind, m in MOUNTS.items():
        spin(kind, m["shift"], m["mask"], m["mask"], m["research"])
    spin("spare", SPARE_SHIFT, SPARE_MAX, SPARE_MAX, None)
    spin("att", ATT["shift"], ATT["mask"], ATT["mask"], ATT["research"])

    # The RAM launchers tick box: ram_sync, create_ram, ram_change (its OnClick).
    c = Code(at["ram_sync"]); c.emit(b"\x53\x56\x57\x8b\xd8")
    find_or_create(c, r["checkbox_vmt"], MAGIC["ram"], at["create_ram"], "have_box"); c.emit(b"\x8b\xf8")
    c.emit(b"\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x33\xd2\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "have_flag")
    c.emit(b"\xf7\x00"); c.u32(RAM_BIT); c.emit(b"\x0f\x95\xc2")
    c.mark("have_flag"); c.emit(b"\x52\x8b\xc7"); call_slot(c, V["get_checked"]); c.emit(b"\x5a\x52\x3a\xc2"); c.branch(b"\x0f\x84", "state_ok")
    c.emit(b"\xff\xb7"); c.u32(V["on_click"]); c.emit(b"\xc7\x87"); c.u32(V["on_click"]); c.u32(0)
    c.emit(b"\x8b\xc7"); call_slot(c, V["set_checked"]); c.emit(b"\x8f\x87"); c.u32(V["on_click"])
    c.mark("state_ok"); c.emit(b"\x5a\x84\xd2"); c.branch(b"\x0f\x85", "editable")       # ticked: editable designs may untick
    c.emit(b"\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "set_enabled")
    allowed(c, tree.RAM); c.emit(b"\x8b\xd0"); c.branch(b"\xe9", "set_enabled")
    c.mark("editable"); c.emit(b"\x8a\x93"); c.u32(F["editable"])
    c.mark("set_enabled"); c.emit(b"\x8b\xc7"); call_slot(c, V["set_enabled"])
    c.mark("done"); c.emit(b"\x5f\x5e\x5b\xc3")
    code["ram_sync"] = c.finish()
    c = Code(at["create_ram"]); create(c, r["checkbox_vmt"], MAGIC["ram"], BOUNDS["ram"], "ram_hint")
    c.emit(b"\xba"); c.u32(texts["ram_caption"]); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", r["set_text"])
    c.emit(b"\xc7\x86"); c.u32(V["on_click"]); c.u32(at["ram_change"]); c.emit(b"\x89\x9e"); c.u32(V["on_click"]+4)
    c.emit(b"\x8b\xc6\x5e\x5b\xc3")
    code["create_ram"] = c.finish()
    c = Code(at["ram_change"])   # OnClick(EAX form, EDX box)
    c.emit(b"\x60\x8b\xd8\x8b\xfa\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x33\xed\x8b\xc7"); call_slot(c, V["get_checked"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "store")
    allowed(c, tree.RAM); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", "tick")
    c.emit(b"\xb8"); c.u32(texts["ram_research"]); c.emit(b"\x83\xca\xff\x83\xc9\xff"); c.branch(b"\xe8", r["message"])
    c.branch(b"\xe9", "resync")
    c.mark("tick"); c.emit(b"\xbd"); c.u32(RAM_BIT)
    c.mark("store"); store(c, 1, RAM_BIT.bit_length()-1)
    c.mark("resync"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["ram_sync"]); c.emit(b"\x61\xc3")
    code["ram_change"] = c.finish()

    # readout(EAX form): "Point defence: S systems / C channels.   Missiles: SeaRAM n, gun-missile n, ATT n".
    # Locals: six strings [ebp-4]..[ebp-18h] (systems, channels, SeaRAM, gun-missile, ATT, the line), the label.
    c = Code(at["readout"]); c.emit(b"\x55\x8b\xec\x83\xec\x1c\x53\x56\x57\x8b\xd8\x33\xc0")
    for local in (4, 8, 0xC, 0x10, 0x14, 0x18): c.emit(b"\x89\x45"+bytes([0x100-local]))  # the strings := nil
    find_or_create(c, r["label_vmt"], MAGIC["readout"], at["create_readout"], "have_label"); c.emit(b"\x89\x45\xe4")
    c.emit(b"\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "finish")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x33\xff\x85\xc0"); c.branch(b"\x0f\x84", "have_data"); c.emit(b"\x8b\x38")
    c.mark("have_data"); c.emit(b"\x33\xc0")                                              # EDI data; EAX systems
    for bits in [m["mask"] << m["shift"] for m in MOUNTS.values()]+[0xFF]:                 # mounts, lasers
        c.emit(b"\xf7\xc7"); c.u32(bits); c.branch(b"\x0f\x84", f"none{bits}"); c.emit(b"\x40"); c.mark(f"none{bits}")
    c.emit(b"\x80\xbe"); c.u32(SHIP["ciws_flag"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "counted")   # a gun CIWS
    c.emit(b"\x83\xbe"); c.u32(SHIP["ciws"]); c.emit(b"\x00"); c.branch(b"\x0f\x8e", "counted"); c.emit(b"\x40")
    c.mark("counted"); c.emit(b"\x50\x8d\x55\xfc"); c.branch(b"\xe8", r["int_to_str"])
    channels(c); c.emit(b"\x51\x8b\xc1\x8d\x55\xf8"); c.branch(b"\xe8", r["int_to_str"])
    c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.PD_MAGAZINES[0]); c.branch(b"\xe8", r["has_research"])
    c.emit(b"\x0f\xb6\xc8\x8b\xd7\xc1\xea"+bytes([SPARE_SHIFT])+b"\x83\xe2"+bytes([SPARE_MAX])+b"\x8d\x4c\x11\x02\x51")
    for (kind, m), local in zip(MOUNTS.items(), (0xC, 0x10)):
        mounts_of(c, kind, b"\xc7"); c.emit(b"\x6b\xc0"+bytes([m["missiles"]])+b"\x0f\xaf\x04\x24\xd1\xe8")
        c.emit(b"\x8d\x55"+bytes([0x100-local])); c.branch(b"\xe8", r["int_to_str"])
    c.emit(b"\x8b\xc7\xc1\xe8"+bytes([ATT["shift"]])+b"\x83\xe0"+bytes([ATT["mask"]])+b"\x6b\xc0"+bytes([ATT["load"]]))
    c.emit(b"\x8d\x55\xec"); c.branch(b"\xe8", r["int_to_str"])                          # ATTs carried
    c.emit(b"\x59\x59\x58")                                                               # ECX channels, EAX systems
    c.emit(b"\x68"); c.u32(texts["pd"]); c.emit(b"\xff\x75\xfc\x68"); c.u32(texts["systems"]); c.emit(b"\xff\x75\xf8\x68"); c.u32(texts["channels"])
    c.emit(b"\x3b\xc1"); c.branch(b"\x0f\x8e", "enough"); c.emit(b"\x68"); c.u32(texts["short"]); c.branch(b"\xe9", "warned")
    c.mark("enough"); c.emit(b"\x6a\x00")
    c.mark("warned"); c.emit(b"\x68"); c.u32(texts["missiles"]); c.emit(b"\xff\x75\xf4\x68"); c.u32(texts["gm"]); c.emit(b"\xff\x75\xf0")
    c.emit(b"\x68"); c.u32(texts["att"]); c.emit(b"\xff\x75\xec")
    c.emit(b"\x8d\x45\xe8\xba\x0c\x00\x00\x00"); c.branch(b"\xe8", r["cat_n"])
    c.emit(b"\x8b\x45\xe4\x8b\x55\xe8"); c.branch(b"\xe8", r["set_text"])
    c.mark("finish"); c.emit(b"\x8d\x45\xe8\xba\x06\x00\x00\x00"); c.branch(b"\xe8", r["clear_n"])
    c.emit(b"\x5f\x5e\x5b\x8b\xe5\x5d\xc3")
    code["readout"] = c.finish()
    c = Code(at["create_readout"]); create(c, r["label_vmt"], MAGIC["readout"], BOUNDS["readout"], "readout_hint")
    c.emit(b"\x8b\xc6\x5e\x5b\xc3")
    code["create_readout"] = c.finish()

    limits = dict(layer=0x280, attempt_sam=0x40, attempt_gun=0x40, weight=0x100, topside=0xC0, ram_sam=0x40, sync=0x40,
                  readout=0x280, create_readout=0x80)
    for name in CONTROLS:
        limits.update({name+"_sync": R["sync"], "create_"+name: R["create"], "create_"+name+"_label": R["label"],
                       name+"_change": R["change"]})
    for name, body in code.items():
        if len(body) > limits[name]: raise ValueError(f"Point defence code exceeds its reservation: {name} ({len(body):#x})")
        blocks.append(dict(name="Point defence: "+name, address=at[name], bytes=body.hex()))
    blocks.append(dict(name="Point defence: channel", address=chan, bytes="00000000"))
    blocks.append(dict(name="Point defence: ram_kind", address=at["ram_kind"], bytes="00000000"))
    plans = [patch("Point defence: topside", n["topside"], bytes.fromhex(TOPSIDE_ORIGINAL),
                   b"\xe9"+struct.pack("<i", at["topside"]-n["topside"]-5)+b"\x90"*3)]
    return blocks, plans

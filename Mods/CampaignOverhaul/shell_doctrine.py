"""Special shell doctrine: the player chooses whether to fire guided and nuclear shells, and pays for them.

Screen: the Doctrine and training form gets a "Special shells" box between Torpedo usage options and AP shell
design priority (which moves down, on a taller form) with two tick boxes, greyed until their research is done
like the torpedo ones. The box and tick boxes are made the first time the form is set up (a TGroupBox and two
TCheckBox, of the classes of the form's own GroupBox3 and cbHeavyAA) and found again by their Tag.
Storage: the choice (bit 0 guided, bit 1 nuclear) lives in a small table by nation object and rides in the save
file on the nation's UseMissileTorps key, whose own value (a hidden native option battles still read) is kept:
files hold UseMissileTorps | flags << 8 (a save made without the choice is unchanged).
Use: modern_combat (guided hit chance) and modern_navy (nuclear shell) ask use_guided / use_nuclear with the
firer's nation index. The player's ships fire a kind only when its flag is set and the nation has the money,
which is then spent: GUIDED_COST a firing battery's salvo, NUCLEAR_COST a shell. Other nations fire as their
research allows, free, but no nuclear weapon first and only in kind: a shell, torpedo or missile only once the
player has paid for one of that kind (its bit << CROSSED_SHIFT on the
player's row, saved with the choice, cleared at the first turn of peace (the save's War counter, a global, is
not above 0) and when a ban treaty is signed).
Blast: a nuclear shell's hit also hits every other ship within BLAST_YARDS of the target (the firer excepted; nuclear_subs.py does the same for nuclear torpedoes and missiles)
with a BLAST_CALIBRE-inch hit through the native HandleHit, from inside FireGuns' own frame. Against aircraft
a ship that may fire nuclear shells has a large heavy AA bonus instead (modern_navy.NUCLEAR_HAA, may_nuclear).
Aftermath: firing a nuclear weapon sets a flag. At the next turn (CheckTurnEvents' entry, every turn: until
2026-11-22 it was RandomTensionChanges, which the turn events only call on some turns) every nation's tension
rises by NUCLEAR_TENSION with a news item, and one time in TREATY_ODDS the powers propose a treaty banning nuclear
weapons for TREATY_YEARS years, which the player signs or refuses. While it runs nobody fires nuclear weapons
(use_nuclear and may_nuclear answer no). Its last year rides with the player's choice: table value bits 8-15,
years after 1900.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct
from hull_rules import dpi_scale_routine

BASE = 0x301000
GUIDED, NUCLEAR, TORPEDO, MISSILE, CONSERVE = 1, 2, 4, 8, 16   # the choice's bits; 2, 4 and 8 are nuclear weapons
CROSSED_SHIFT, CROSSED = 4, 0xE0      # on the player's row: the nuclear kinds (bit << 4) the player has fired
GUIDED_COST, NUCLEAR_COST, TORPEDO_COST, MISSILE_COST = 1, 500, 800, 1500
BLAST_YARDS, BLAST_CALIBRE = 1500, 12
NUCLEAR_TENSION, TREATY_ODDS, TREATY_YEARS = 3, 3, 15
SLOTS = 16
ARMAGEDDON_BLOCK, MISSILE_TEXT_BLOCK = "Shell doctrine: armageddon", "Shell doctrine: missile"   # nuclear_armageddon finds them
WINDOWS = (
    (0x6084E0, 0x18, None),   # doctrine form: load the group's index
    (0x609752, 0x18, None),   # doctrine form, Close: store it
    (0x71FF86, 0x18, None),   # nation reader: UseMissileTorps
    (0x723C97, 0x10, None),   # nation writer
    (0x6084F7, 0x20, None),   # doctrine form: research greys a tick box (SetEnabled, slot 9Ch)
    (0x909909, 0x70, None),   # FireGuns: the HandleHit call
    (0x8761E3, 0x30, None),   # the battle's ship list
    (0x751100, 0xF8, None),   # RandomTensionChanges: entry, the speech's tension change and news
    (0x6097B2, 0x30, None),   # a Yes/No MessageDlg (doctrine form)
)
MONTH = (0x7B30F0, "558bec33c9515151")   # CheckTurnEvents (EAX the campaign): push ebp / mov ebp,esp / xor ecx,ecx / push ecx x3
SITES = (("show", 0x6084E6, "8b9095000000"), ("close", 0x60975E, "898695000000"),
         ("read", 0x71FF95, "898395000000"), ("write", 0x723C9C, "8b8395000000"))
NATIVE = dict(set_left=0x450EF0, set_top=0x450F24, set_width=0x450F5C, set_height=0x450F90, set_text=0x451CA0,
              has_research=0x729FA4,
              list_get=0x3B6D6C, nation=0x750040, change_tension=0x816A3C, news=0x5AB1D0, random=0x307834,
              message_dlg=0x4D6C50, ship_distance=0x8ECD20, ship_name=0x9045A8, handle_hit=0x8F7068)
SHIPS_LOAD, MAIN_LOAD, YEAR_LOAD, NEWS_LOAD, PICTURE = 0x8761E3, 0x8ED02C, 0x91AC81, 0x751181, 0x7532BC
WAR_LOAD = 0x75E901                                               # the save writer: mov eax,[War] / push eax / mov ecx,"War"
FORM = dict(components=0x10, torpedoes=0x4CC, heavy_aa=0x4C4, priority=0x520)   # TdlgDoctrine: GroupBox3, cbHeavyAA, GroupBox5
CONTROL = dict(tag=0xC, left=0x50, top=0x54, width=0x58, height=0x5C)
VCL = dict(create=0x3C, set_enabled=0x9C, set_parent=0xA0, get_checked=0x16C, set_checked=0x170)   # virtual slots
TAGS = dict(box=0x5348454C, guided=0x5348454D, nuclear=0x5348454E, torpedo=0x5348454F, missile=0x53484550,
            conserve=0x53484551)
BOX_HEIGHT, MOVE = 145, 150                                         # the new box; how far the form grows (96 DPI)
GROUP5_WIDTH = 273   # GroupBox5 at 96 DPI: the display-scaling reference for the sizes above and the BOXES
STORED, FUNDS, PLAYER = 0x95, 0x1B5, 0x3204                       # nation field, nation funds, main's player nation
SHIP = dict(kind=0x9D3, out=0xA9F)                                # type (12: not a ship), out of action
NEWS = dict(reason="on account of the use of nuclear weapons.",
            news="Nuclear weapons have been used at sea. The world is appalled and tensions rise!",
            treaty=f"The powers propose a treaty banning the use of nuclear weapons for {TREATY_YEARS} years. "
                   "Do you want to sign it?")
TEXTS = dict(caption="Special shells (paid for when fired)", guided=f"Use guided shells ({GUIDED_COST} a salvo)",
             nuclear=f"Use nuclear shells ({NUCLEAR_COST} each)",
             torpedo=f"Use nuclear torpedoes on SSN ({TORPEDO_COST} each)",
             missile=f"Use nuclear missiles on SSBN ({MISSILE_COST} each)",
             conserve="Fire one SAM at each incoming missile")
# tick box, its flag, its top in the box
BOXES = (("guided", GUIDED, 22), ("nuclear", NUCLEAR, 46), ("torpedo", TORPEDO, 70), ("missile", MISSILE, 94),
         ("conserve", CONSERVE, 118))


def digests(blob):
    import modern_research as audit
    normal = audit.normalize(blob, BASE)
    return [hashlib.sha256(normal[a-BASE:a-BASE+n]).hexdigest() for a, n, _ in WINDOWS]


DIGESTS = (
    "5dd28314e9497b4bb364840e291f98c2c77b009d20ee750c2aac7c3dfacc865d",
    "6ece150b060d6550ed0a75dbfd26a68862f4672acd8377c3dbf71f1f69133e5f",
    "8102952f3d2f413f142e5d7804bb248e44e46cb2ba269927c0a5f3f830438c3c",
    "db6bb7cdde17e53373a78999a37dccd31e8d887381580fc99abddf81f7421ebf",
    "bb2d3de2fc31797a682aa672fe34bb24de2dba1eeb06f5a6e3b6192bc66a9e97",
    "f64374d11f28aa46e4598e61f05fa9040f31089f013d996013cca78255dd0286",
    "96c1a0cce939841cf00524c6c02e327f070292d1e29a6584e637aa7e7c6c895a",
    "aad29eb661a28a270181c422623fb8b0826b45edb70a996cdaf504654ad7dd50",
    "fdbde716a6126ab26f2d35d55054384721fffec3b54a89b73b3d671990d283ce",
)


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def discover(blob, base, normalized):
    for (address, size, _), digest in zip(WINDOWS, DIGESTS):
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Shell doctrine refuses changed native code at "+hex(address)+".")
    for name, address, original in SITES:
        if blob[address-BASE:address-BASE+6].hex() != original: raise ValueError("Shell doctrine refuses changed native code.")
    delta = base-BASE
    info = {k: v+delta for k, v in NATIVE.items()}
    info["ships"] = struct.unpack_from("<I", blob, SHIPS_LOAD-BASE+1)[0]
    info["main"] = struct.unpack_from("<I", blob, MAIN_LOAD-BASE+1)[0]
    if blob[YEAR_LOAD-BASE] != 0xA1 or blob[NEWS_LOAD-BASE] != 0xA1 or blob[MONTH[0]-BASE:MONTH[0]-BASE+8].hex() != MONTH[1]:
        raise ValueError("Shell doctrine refuses changed native code.")
    if blob[WAR_LOAD-BASE] != 0xA1 or blob[WAR_LOAD-BASE+5:WAR_LOAD-BASE+7] != b"\x50\xb9":
        raise ValueError("Shell doctrine refuses changed native code.")
    info["war"] = struct.unpack_from("<I", blob, WAR_LOAD-BASE+1)[0]
    info["year"] = struct.unpack_from("<I", blob, YEAR_LOAD-BASE+1)[0]
    info["news_form"] = struct.unpack_from("<I", blob, NEWS_LOAD-BASE+1)[0]
    info["picture"], info["month"] = PICTURE+delta, MONTH[0]+delta
    info["sites"] = {name: address+delta for name, address, _ in SITES}
    return info


def build(page, info):
    """One page: code, then the table and texts. Returns blocks, patches and the entry points
    (use_guided, use_nuclear: EDX nation index -> AL; blast: inside FireGuns' frame)."""
    from campaign_security import Code
    from hull_rules import patch
    import modern_tree as tree
    at = dict(lookup=page, store=page+0x40, use=page+0xC00, blast=page+0x100, show=page+0x200, close=page+0x500,
              read=page+0xE00, write=page+0xE40, find=page+0xE80, table=page+0x680, cursor=page+0x680+SLOTS*8,
              used=page+0x684+SLOTS*8, armageddon=page+0x688+SLOTS*8, texts=page+0x800, month=page+0xD00)
    at.update(close=page+0xF00)                                  # four tick boxes: Close reads them at the page's end
    research = dict(guided=tree.GUIDED_SHELLS[0], nuclear=tree.NUCLEAR_SHELLS[0], torpedo=tree.SSN, missile=tree.SSBN)
    at["conserve"] = page+0xEC0
    n, code, texts, cursor = info, {}, {}, at["texts"]
    blocks = [dict(name="Shell doctrine: table", address=at["table"], bytes="00"*(SLOTS*8+8)),
              # Nuclear Armageddon (nuclear_armageddon.py) sets it: nuclear weapons without the one-a-battle limits,
              # and nuclear heavy SAMs and SSMs (modern_navy, nuclear_subs, modern_air_defence).
              dict(name=ARMAGEDDON_BLOCK, address=at["armageddon"], bytes="00"*4)]
    for key, text in {**TEXTS, **NEWS}.items():
        body = literal(text); texts[key] = cursor+12
        blocks.append(dict(name="Shell doctrine: "+key, address=cursor, bytes=body.hex())); cursor += (len(body)+3) & ~3
    if cursor > page+0xC00: raise ValueError("Shell doctrine texts exceed their page.")

    # lookup: EAX nation -> EAX flags (0 when unknown). Keeps ECX, EDX.
    c = Code(at["lookup"]); c.emit(b"\x51\x52\xba"); c.u32(at["table"]); c.emit(b"\xb9"); c.u32(SLOTS)
    c.mark("row"); c.emit(b"\x39\x02"); c.branch(b"\x0f\x84", "found"); c.emit(b"\x83\xc2\x08\x49"); c.branch(b"\x0f\x85", "row")
    c.emit(b"\x33\xc0"); c.branch(b"\xe9", "done")
    c.mark("found"); c.emit(b"\x8b\x42\x04"); c.mark("done"); c.emit(b"\x5a\x59\xc3")
    code["lookup"] = c.finish()

    # store: EAX nation, EDX flags. Keeps every register. A full table reuses rows in turn.
    c = Code(at["store"]); c.emit(b"\x51\x56\xbe"); c.u32(at["table"]); c.emit(b"\xb9"); c.u32(SLOTS)
    c.mark("row"); c.emit(b"\x39\x06"); c.branch(b"\x0f\x84", "found"); c.emit(b"\x83\xc6\x08\x49"); c.branch(b"\x0f\x85", "row")
    c.emit(b"\x8b\x0d"); c.u32(at["cursor"]); c.emit(b"\x83\xe1"+bytes([SLOTS-1])+b"\x8d\x34\xcd"); c.u32(at["table"])
    c.emit(b"\xff\x05"); c.u32(at["cursor"]); c.emit(b"\x89\x06")
    c.mark("found"); c.emit(b"\x89\x56\x04\x5e\x59\xc3")
    code["store"] = c.finish()

    # No first use, called from use ([esp+4] its kind's bit). The player paid (EDX nation): a nuclear weapon
    # marks the row. other (ECX main) -> AL: another nation may fire the kind, a nuclear one only after that.
    at["first"] = page+0x80
    c = first = Code(at["first"]); c.emit(b"\xf6\x44\x24\x04"+bytes([NUCLEAR | TORPEDO | MISSILE])); c.branch(b"\x0f\x84", "ret")
    c.emit(b"\x8b\xc2"); c.branch(b"\xe8", at["lookup"]); c.emit(b"\x8b\x4c\x24\x04\xc1\xe1"+bytes([CROSSED_SHIFT])+b"\x0b\xc1\x92")
    c.branch(b"\xe8", at["store"])
    c.mark("ret"); c.emit(b"\xc3")
    c.mark("other"); c.emit(b"\xf6\x44\x24\x04"+bytes([NUCLEAR | TORPEDO | MISSILE])); c.branch(b"\x0f\x84", "free")
    c.emit(b"\x8b\x81"); c.u32(PLAYER); c.branch(b"\xe8", at["lookup"])
    c.emit(b"\x8b\x4c\x24\x04\xc1\xe1"+bytes([CROSSED_SHIFT])+b"\x85\xc1\x0f\x95\xc0\xc3")
    c.mark("free"); c.emit(b"\xb0\x01\xc3")
    c.mark("peace")                                                                # EBX main, once a turn
    c.emit(b"\x83\x3d"); c.u32(n["war"]); c.emit(b"\x00"); c.branch(b"\x0f\x8f", "war")      # peace: no first use again
    c.emit(b"\x8b\x83"); c.u32(PLAYER); c.branch(b"\xe8", at["lookup"]); c.emit(b"\xa8"+bytes([CROSSED])); c.branch(b"\x0f\x84", "war")
    c.emit(b"\x24"+bytes([0xFF & ~CROSSED])+b"\x8b\xd0\x8b\x83"); c.u32(PLAYER); c.branch(b"\xe8", at["store"])
    c.mark("war"); c.emit(b"\xc3")
    code["first"] = c.finish()

    # use_guided / use_nuclear: EDX nation index -> AL. Clobbers EAX, ECX, EDX.
    c = Code(at["use"]); c.emit(b"\x68"); c.u32(GUIDED_COST); c.emit(b"\x6a"+bytes([GUIDED])); c.branch(b"\xe9", "common")
    c.mark("may"); c.emit(b"\x68"); c.u32(0); c.emit(b"\x6a"+bytes([NUCLEAR])); c.branch(b"\xe9", "common")   # asked, not fired
    c.mark("torpedo"); c.emit(b"\x68"); c.u32(TORPEDO_COST); c.emit(b"\x6a"+bytes([TORPEDO])); c.branch(b"\xe9", "common")
    c.mark("missile"); c.emit(b"\x68"); c.u32(MISSILE_COST); c.emit(b"\x6a"+bytes([MISSILE])); c.branch(b"\xe9", "common")
    c.mark("nuclear")
    c.emit(b"\x68"); c.u32(NUCLEAR_COST); c.emit(b"\x6a"+bytes([NUCLEAR]))
    c.mark("common")                                                               # nuclear: not under a ban treaty
    c.emit(b"\xf6\x04\x24"+bytes([NUCLEAR | TORPEDO | MISSILE])); c.branch(b"\x0f\x84", "free")
    c.emit(b"\xa1"); c.u32(n["main"]); c.emit(b"\x8b\x00\x8b\x80"); c.u32(PLAYER); c.branch(b"\xe8", at["lookup"])
    c.emit(b"\xc1\xe8\x08\x25"); c.u32(0xFF); c.branch(b"\x0f\x84", "free")
    c.emit(b"\x05"); c.u32(1900); c.emit(b"\x8b\x0d"); c.u32(n["year"]); c.emit(b"\x3b\x01"); c.branch(b"\x0f\x8d", "no")
    c.mark("free"); c.emit(b"\xa1"); c.u32(n["main"]); c.emit(b"\x8b\x00\x50"); c.branch(b"\xe8", n["nation"]); c.emit(b"\x59")
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x3b\x81"); c.u32(PLAYER); c.branch(b"\x0f\x85", "other")               # another nation: free
    c.emit(b"\x8b\xd0"); c.branch(b"\xe8", at["lookup"]); c.emit(b"\x85\x04\x24"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x8b\x4c\x24\x04\x85\xc9"); c.branch(b"\x0f\x84", "yes")
    c.emit(b"\x39\x8a"); c.u32(FUNDS); c.branch(b"\x0f\x8c", "no")                 # cannot pay
    c.emit(b"\x29\x8a"); c.u32(FUNDS)
    c.branch(b"\xe8", at["first"]); c.branch(b"\xe9", "yes")
    c.mark("other"); c.branch(b"\xe8", at["first"]+first.labels["other"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no")
    c.mark("yes"); c.emit(b"\xb0\x01"); c.branch(b"\xe9", "out")
    c.mark("no"); c.emit(b"\x33\xc0"); c.mark("out"); c.emit(b"\x8d\x64\x24\x08\xc3")     # drop bit and cost
    code["use"] = c.finish()
    entries = dict(conserve=at["conserve"], used=at["used"], use_torpedo=at["use"]+c.labels["torpedo"], use_missile=at["use"]+c.labels["missile"],
                   use_guided=at["use"], use_nuclear=at["use"]+c.labels["nuclear"], may_nuclear=at["use"]+c.labels["may"],
                   blast=at["blast"], armageddon=at["armageddon"],
                   lookup=at["lookup"], first=at["first"], year=n["year"])   # nuclear_strike pays by itself

    # blast: in FireGuns ([ebp-24h] firer, [ebp-28h] target, [ebp+18h] battery), before the nuclear hit lands.
    c = Code(at["blast"]); c.emit(b"\x60\x6a\x00")
    c.mark("ship"); c.emit(b"\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x8b\x0c\x24\x3b\x48\x08"); c.branch(b"\x0f\x8d", "end")
    c.emit(b"\x8b\xd1"); c.branch(b"\xe8", n["list_get"]); c.emit(b"\x8b\xd8\x85\xdb"); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x3b\x5d\xd8"); c.branch(b"\x0f\x84", "next"); c.emit(b"\x3b\x5d\xdc"); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x80\xbb"); c.u32(SHIP["kind"]); c.emit(b"\x0c"); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x80\xbb"); c.u32(SHIP["out"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x8b\x45\xd8\x8b\xd3"); c.branch(b"\xe8", n["ship_distance"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x88", "next"); c.emit(b"\x3d"); c.u32(BLAST_YARDS); c.branch(b"\x0f\x8f", "next")
    c.emit(b"\x6a"+bytes([BLAST_CALIBRE])+b"\x8b\xd3\x8b\x45\xdc"); c.branch(b"\xe8", n["ship_distance"]); c.emit(b"\x50")
    c.emit(b"\x8b\x45\xdc\x8b\x55\x18\xff\x74\x90\x75\xff\x70\x14\x0f\xb6\x45\xb7\x50\xff\x75\xc0")
    c.emit(b"\x8b\x45\xdc\x0f\xb6\x80\xa6\x09\x00\x00\x50\x8d\x45\xe0\x50")
    c.emit(b"\x8d\x95\x08\xfe\xff\xff\x8b\x45\xdc"); c.branch(b"\xe8", n["ship_name"])
    c.emit(b"\x8b\x8d\x08\xfe\xff\xff\x8b\x55\xfc\x8b\xc3"); c.branch(b"\xe8", n["handle_hit"])
    c.mark("next"); c.emit(b"\xff\x04\x24"); c.branch(b"\xe9", "ship")
    c.mark("end"); c.emit(b"\x83\xc4\x04\x61\xc3")
    code["blast"] = c.finish()

    # find: EBX form, EDX tag -> EAX the form's component with that Tag, or 0. Keeps the other registers.
    c = Code(at["find"]); c.emit(b"\x51\x56\x8b\x73"+bytes([FORM["components"]])+b"\x85\xf6"); c.branch(b"\x0f\x84", "none")
    c.emit(b"\x8b\x4e\x08\x8b\x76\x04")
    c.mark("row"); c.emit(b"\x49"); c.branch(b"\x0f\x88", "none"); c.emit(b"\x8b\x04\x8e\x39\x50"+bytes([CONTROL["tag"]]))
    c.branch(b"\x0f\x85", "row"); c.branch(b"\xe9", "out")
    c.mark("none"); c.emit(b"\x33\xc0"); c.mark("out"); c.emit(b"\x5e\x59\xc3")
    code["find"] = c.finish()

    def make(c, like, tag):       # EAX := a new component of the class of the form's [like] control, owned by the form
        c.emit(b"\x8b\x83"); c.u32(like); c.emit(b"\x8b\x00\x8b\xcb\xb2\x01\xff\x50"+bytes([VCL["create"]]))
        c.emit(b"\xc7\x40"+bytes([CONTROL["tag"]])); c.u32(tag)

    def setter(c, register, name, value):   # control in ESI (0xC6) or EDI (0xC7); value: immediate or loading bytes
        c.emit(value if isinstance(value, bytes) else b"\xba"+value.to_bytes(4, "little"))
        c.emit(b"\x8b"+bytes([register])); c.branch(b"\xe8", n[name])

    # Doctrine form set-up, EBX form, EAX nation: make the box once, then show the nation's choice and research.
    c = Code(at["show"]); c.emit(b"\x60\xba"); c.u32(TAGS["box"]); c.branch(b"\xe8", at["find"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "made")
    make(c, FORM["torpedoes"], TAGS["box"]); c.emit(b"\x8b\xf0\x8b\xd3\x8b\x08\xff\x91"); c.u32(VCL["set_parent"])
    c.emit(b"\x8b\xbb"); c.u32(FORM["priority"])                                   # EDI: AP shell design priority
    for name, field in (("set_left", "left"), ("set_top", "top"), ("set_width", "width")):
        setter(c, 0xC6, name, b"\x8b\x57"+bytes([CONTROL[field]]))
    def scaled(value):   # EDX := a 96-DPI size on screen (the routine at the end)
        c.emit(b"\xba"); c.u32(value); c.branch(b"\xe8", "scale")
        return b""
    setter(c, 0xC6, "set_height", scaled(BOX_HEIGHT)); setter(c, 0xC6, "set_text", texts["caption"])
    setter(c, 0xC7, "set_top", scaled(MOVE)+b"\x03\x57"+bytes([CONTROL["top"]]))
    c.emit(scaled(MOVE)+b"\x03\x53"+bytes([CONTROL["height"]])+b"\x8b\xc3"); c.branch(b"\xe8", n["set_height"])
    for key, _, top in BOXES:
        make(c, FORM["heavy_aa"], TAGS[key]); c.emit(b"\x8b\xf8\x8b\xd6\x8b\x08\xff\x91"); c.u32(VCL["set_parent"])
        setter(c, 0xC7, "set_left", scaled(16)); setter(c, 0xC7, "set_top", scaled(top))
        setter(c, 0xC7, "set_width", scaled(240))
        setter(c, 0xC7, "set_text", texts[key])
    c.mark("made")
    for key, flag, _ in BOXES:                                                       # [esp+1Ch]: the nation
        c.emit(b"\xba"); c.u32(TAGS[key]); c.branch(b"\xe8", at["find"]); c.emit(b"\x8b\xf8\x85\xff"); c.branch(b"\x0f\x84", "no_"+key)
        c.emit(b"\x8b\x44\x24\x1c"); c.branch(b"\xe8", at["lookup"]); c.emit(b"\x33\xd2\xa8"+bytes([flag])+b"\x0f\x95\xc2")
        c.emit(b"\x8b\xc7\x8b\x08\xff\x91"); c.u32(VCL["set_checked"])
        if key in research:
            c.emit(b"\x8b\x44\x24\x1c\xba"); c.u32(research[key]); c.branch(b"\xe8", n["has_research"])
            c.emit(b"\x8b\xd0\x8b\xc7\x8b\x08\xff\x91"); c.u32(VCL["set_enabled"])
        c.mark("no_"+key)
    c.emit(b"\x61"+bytes.fromhex(SITES[0][2])); c.branch(b"\xe9", n["sites"]["show"]+6)
    c.mark("scale"); c.emit(dpi_scale_routine(FORM["priority"], GROUP5_WIDTH))
    code["show"] = c.finish()

    # Close, EBX form, ESI nation: the tick boxes are the nation's choice; the native field keeps its value.
    c = Code(at["close"]); c.emit(b"\x60\x8b\xc6"); c.branch(b"\xe8", at["lookup"]); c.emit(b"\x83\xe0\xe0\x8b\xe8")   # keep the treaty
    for key, flag, _ in BOXES:
        c.emit(b"\xba"); c.u32(TAGS[key]); c.branch(b"\xe8", at["find"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no_"+key)
        c.emit(b"\x8b\x10\xff\x92"); c.u32(VCL["get_checked"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no_"+key)
        c.emit(b"\x83\xcd"+bytes([flag])); c.mark("no_"+key)
    c.emit(b"\x8b\xc6\x8b\xd5"); c.branch(b"\xe8", at["store"]); c.emit(b"\x61"); c.branch(b"\xe9", n["sites"]["close"]+6)
    code["close"] = c.finish()

    # Reader, EBX nation, EAX the file's value: flags above the native value.
    c = Code(at["read"]); c.emit(b"\x50\x52\x8b\xd0\xc1\xea\x08\x81\xe2"); c.u32(0xFFFF); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["store"])
    c.emit(b"\x5a\x58\x25"); c.u32(0xFF); c.emit(b"\x89\x83"); c.u32(STORED); c.branch(b"\xe9", n["sites"]["read"]+6)
    code["read"] = c.finish()

    # Writer, EBX nation -> EAX the file's value.
    c = Code(at["write"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["lookup"]); c.emit(b"\xc1\xe0\x08\x0b\x83"); c.u32(STORED)
    c.branch(b"\xe9", n["sites"]["write"]+6)
    code["write"] = c.finish()

    # conserve: EDX nation index -> EAX 1 when it is the player's and the box is ticked (modern_defence).
    c = Code(at["conserve"]); c.emit(b"\xa1"); c.u32(n["main"]); c.emit(b"\x8b\x00\x50"); c.branch(b"\xe8", n["nation"]); c.emit(b"\x59")
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "zero"); c.emit(b"\x3b\x81"); c.u32(PLAYER); c.branch(b"\x0f\x85", "zero")
    c.branch(b"\xe8", at["lookup"]); c.emit(b"\x83\xe0"+bytes([CONSERVE])+b"\x0f\x95\xc0\x0f\xb6\xc0\xc3")
    c.mark("zero"); c.emit(b"\x33\xc0\xc3")
    code["conserve"] = c.finish()

    # RandomTensionChanges (EAX the campaign), once a turn: the aftermath of nuclear weapons fired since the last.
    c = Code(at["month"]); c.emit(b"\x60\x8b\xd8"); c.branch(b"\xe8", at["first"]+first.labels["peace"])
    c.emit(b"\x83\x3d"); c.u32(at["used"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "out")
    c.emit(b"\xc7\x05"); c.u32(at["used"]); c.u32(0); c.emit(b"\xbe\x01\x00\x00\x00")
    c.mark("nation"); c.emit(b"\x8b\xd6\x8b\xc3"); c.branch(b"\xe8", n["nation"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x80\xb8\xcc\x01\x00\x00\x04"); c.branch(b"\x0f\x84", "next")            # as the native speech does
    c.emit(b"\x68"); c.u32(texts["reason"]); c.emit(b"\x8b\xd0\xb9"); c.u32(NUCLEAR_TENSION); c.emit(b"\x8b\xc3")
    c.branch(b"\xe8", n["change_tension"])
    c.mark("next"); c.emit(b"\x46\x83\xfe\x09"); c.branch(b"\x0f\x85", "nation")
    c.emit(b"\x6a\x01\xba"); c.u32(texts["news"]); c.emit(b"\xa1"); c.u32(n["news_form"]); c.emit(b"\x8b\x00\xb9"); c.u32(n["picture"])
    c.branch(b"\xe8", n["news"])
    c.emit(b"\xb8"); c.u32(TREATY_ODDS); c.branch(b"\xe8", n["random"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "out")
    c.emit(b"\x6a\x00\xb9\x03\x00\x00\x00\xb2\x03\xb8"); c.u32(texts["treaty"]); c.branch(b"\xe8", n["message_dlg"])
    c.emit(b"\x83\xf8\x06"); c.branch(b"\x0f\x85", "out")                               # Yes: banned until that year
    c.emit(b"\xa1"); c.u32(n["year"]); c.emit(b"\x8b\x00\x2d"); c.u32(1900-TREATY_YEARS); c.emit(b"\x25"); c.u32(0xFF)
    c.emit(b"\xc1\xe0\x08\x8b\xf0\x8b\x83"); c.u32(PLAYER); c.branch(b"\xe8", at["lookup"]); c.emit(b"\x25"); c.u32(0xFF & ~CROSSED)
    c.emit(b"\x0b\xc6\x8b\xd0\x8b\x83"); c.u32(PLAYER); c.branch(b"\xe8", at["store"])
    c.mark("out"); c.emit(b"\x61"+bytes.fromhex(MONTH[1])); c.branch(b"\xe9", n["month"]+8)
    code["month"] = c.finish()

    room = dict(first=0x80, month=0x100, lookup=0x40, store=0x40, use=0x100, blast=0x100, show=0x480, close=0x100, conserve=0x40, read=0x40, write=0x40, find=0x40)
    for name, body in code.items():
        if len(body) > room[name]: raise ValueError("Shell doctrine code exceeds its reservation: "+name)
        blocks.append(dict(name="Shell doctrine: "+name, address=at[name], bytes=body.hex()))
    plans = [patch("Shell doctrine: "+name, n["sites"][name], bytes.fromhex(original),
                   b"\xe9"+struct.pack("<i", at[name]-n["sites"][name]-5)+b"\x90")
             for name, _, original in SITES]
    plans.append(patch("Shell doctrine: nuclear aftermath", n["month"], bytes.fromhex(MONTH[1]),
                       b"\xe9"+struct.pack("<i", at["month"]-n["month"]-5)+b"\x90"*3))
    return blocks, plans, entries

"""Later campaign starts: 1947, 1960, 1980 and 2000 (ten superstates, superstates_data.py) beside the native 1890,
1900, 1920 and 1935.

The year screen (TfrmSelectNation2.pn00OR20) loads Images\\StartYears.jpg, the native picture with a second row
of boxed years, and puts four transparent labels over the new boxes; without the picture it stays native. A later
year takes the native 1935 path with its own year:
- the year screen sets that date and year, the Europe 1920 map and the 1935 options (no slow-aircraft or
  historical-resources choice);
- LoadBuilderNations and LoadAndDisplayMap read Data\\BNat<year>.dat and Data\\MapData<year>.dat (nations and
  possessions on 1 January of that year, written by start_years_data.py) where the game would read BNat1935.dat
  and MapData1920.dat;
- the start runs SetTechForYear with the start year itself, and marks seen the two one-time notices a 1935 start
  has had (first ship of a new kind completed; the military's smaller share of growing spending). The 1920 and
  1935 Versailles and Soviet fleet rules stay with those years;
- fleets, aircraft and coastal batteries come from the native builders' year-generic path (the custom-battle
  one): templates of design years up to 15 years before the start, kept in their last era by timeline_2030's
  year tables.
"""
import hashlib
import struct

import modern_research as audit

BASE = 0x301000
YEARS = (1947, 1960, 1980, 2000)
SUPERSTATES = 2000                     # ten fictional blocs: superstates_data.py
MAGIC = 0x53590000                     # a new label's Tag: 'SY' in the high word, its year in the low word
PICTURE = "\\Images\\StartYears.jpg"
WIDTH, HEIGHT = 139, 61                # year-panel hit areas: the native columns, and the picture's middle box
PLACES = {1947: (76, 16), 1960: (324, 16), 1980: (559, 16), 2000: (794, 16)}
WINDOWS = (
    (0x69C6C4, 0x21C, "e9841ac2787163887bae16da1b9df7f8f22d9e2c1bf104d43adf3f736b53f612"),   # lb1900Click
    (0x69C458, 0x57, "27eed16a2641d470d238310d6aa927e1028ececcff7e4436718da12d9b9630b4"),    # lbTNewGameClick
    (0x698E80, 0x71, "c81c242d442f53c70fe4687a8b1667e0d8be24c60045e99da5089016413b7e2c"),    # bnNewGameClick
    (0x6995A6, 0x29, "f90fa6c95487b68dda3adcb4b4001d6b56306983c79e04250c93b1bb2e7357b1"),    # start: 1935 flags
    (0x6997D9, 0x51, "e05254179c36b96214703c9b5b4b33ee7db5e61df49e4d146410c9c073bbd653"),    # start: tech by year
    (0x748DF4, 0x81, "8e0f3cfbfadae79c7625afa04f39a333d9421a8d34f0288c86ee3fae4960273f"),    # LoadBuilderNations
    (0x7B7860, 0x41, "59673e95b3242dc31ec931cb86d6e67eefc77ff1f55b7d5a19f5966d248e36a1"),    # LoadAndDisplayMap
)
NATIVE = dict(encode_date=0x32CB18, cat3=0x30C694, clear=0x30B93C, assign=0x30BCCC, file_exists=0x3298A0,
              load_picture=0x423E54, set_left=0x450EF0, set_top=0x450F24, set_width=0x450F5C,
              set_height=0x450F90, set_show_hint=0x451DCC, label_vmt=0x467348,
              year=0x9F7328, date=0x9F7AA4, game_dir=0x9F78CC,       # globals holding pointers
              native_1935=0x69C810, after_year=0x69C82F, no_year=0x69C865,
              after_image=0x69C47F, after_button=0x698EC1, flags_1935=0x6995BD, after_flags=0x699620,
              bnat_1935=0x74923C, after_nations=0x748E70, mapdata_1920=0x7B7A0C, after_map=0x7B7881)
FORM = dict(components=0x10, panel=0x4D4, image=0x4D8, lb1935=0x578)   # TfrmSelectNation2 and TComponent
VCL = dict(tag=0xC, hint=0x90, on_click=0x120, create=0x3C, set_parent=0xA0, picture=0x1E0)
MAIN = dict(first_completion_seen=0x4A4B, spending_share_seen=0x4A51)
SITES = (("open_image", 0x69C479, "8b83d4040000"), ("open_button", 0x698EBB, "8b83d4040000"),
         ("year_click", 0x69C808, "3b93780500007555"), ("start_flags", 0x6995B5, "81388f0700007563"),
         ("nations", 0x748E68, "8d45fcb93c927400"), ("map", 0x7B7879, "8d45ecb90c7a7b00"))   # reference bytes
FILES = dict(nations=("\\Data\\BNat{}.dat", "bnat_1935", 0xFC, "after_nations"),           # name, native file,
             map=("\\Data\\MapData{}.dat", "mapdata_1920", 0xEC, "after_map"))             # [ebp+n] of the result
# In place: the 1935 option set and SetTechForYear(main, 1935) also serve later years (JNE -> JL), the latter
# with the year itself (mov edx,[eax] before mov eax,[edi], instead of mov edx,1935).
IN_PLACE = (("year options", 0x69C8CD, "7536", "7c36"),
            ("tech for the start year", 0x6997FF, "750e8b07ba8f070000", "7c0e8b108b07909090"))


def published(blob, base, vmt, name):
    """Setter of a published property from the class RTTI (walking parents): ('static', address) or ('virtual', slot)."""
    u32 = lambda address: struct.unpack_from("<I", blob, address-base)[0]
    while vmt:
        info = u32(vmt-0x48)
        p = info+2+blob[info+1-base]                                   # kind, name
        p += 10; p += 1+blob[p-base]                                     # class, parent, count, unit name
        count = struct.unpack_from("<H", blob, p-base)[0]; p += 2
        for _ in range(count):                                           # type, get, set, stored, index, default,
            setter, n = u32(p+8), blob[p+26-base]                        # name index, name

            if blob[p+27-base:p+27+n-base] == name.encode():
                if setter >> 24 == 0xFE: return "virtual", setter & 0xFFFF
                if base <= setter < base+len(blob): return "static", setter
                raise ValueError("Unsupported VCL property setter: "+name)
            p += 27+n
        parent = u32(vmt-0x30)
        vmt = u32(parent) if parent else 0
    raise ValueError("Missing VCL property: "+name)


def discover(blob, base):
    normal = audit.normalize(blob, base)
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normal[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Start years refuse changed native code at "+hex(address))
    delta = base-BASE
    info = {k: v+delta for k, v in NATIVE.items()}
    name = struct.unpack_from("<I", normal, NATIVE["label_vmt"]-0x38-BASE)[0]-BASE
    if normal[name:name+7] != b"\x06TLabel":
        raise ValueError("Unsupported VCL label class.")
    import weekly_runtime as rt
    info["click"] = rt.method_address(blob, base, "lb1900Click")
    if info["click"] != 0x69C6C4+delta: raise ValueError("Unsupported native start-year handler.")
    kind, info["set_transparent"] = published(blob, base, info["label_vmt"], "Transparent")
    auto = published(blob, base, info["label_vmt"], "AutoSize")
    if kind != "static" or auto[0] != "virtual": raise ValueError("Unsupported VCL label setters.")
    info["set_auto_size"] = auto[1]
    info["sites"] = []
    for name, address, reference in SITES:     # file-name sites hold relocated addresses: compare normalized
        size = len(reference)//2
        if normal[address-BASE:address-BASE+size].hex() != reference:
            raise ValueError("Start years refuse changed native code at "+hex(address))
        info["sites"].append(dict(name=name, address=address+delta, original=blob[address-BASE:address-BASE+size].hex()))
    return info


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def build(page, info):
    """Code in page (0x1000): setup, the two panel openers, the year click, the start flags and the two file
    names; strings after."""
    from campaign_security import Code     # imported late: campaign_security imports modern_research
    from hull_rules import patch
    at = dict(setup=page, open_image=page+0x400, open_button=page+0x440, year_click=page+0x480,
              start_flags=page+0x500, nations=page+0x580, map=page+0x640)
    n, blocks, cursor, texts = info, [], page+0x700, {}
    strings = [("picture", PICTURE)]+[(year, f"Start a game in {year}: "+("ten superstates" if year == SUPERSTATES else "Cold War blocs")) for year in YEARS]
    strings += [((kind, year), name.format(year)) for kind, (name, *_) in FILES.items() for year in YEARS]
    for key, text in strings:
        data = literal(text)
        blocks.append(dict(name=str(key), address=cursor, bytes=data.hex()))
        texts[key] = cursor+12; cursor += (len(data)+3) & ~3
    if cursor > page+0x1000: raise ValueError("Start-year strings exceed their page.")

    # setup(EAX form): once per form, with the picture present: load it and make the four labels.
    c = Code(at["setup"])
    c.emit(b"\x55\x8b\xec\x6a\x00\x53\x56\x57\x8b\xd8")                    # [ebp-4] = path; EBX form
    c.emit(b"\x8b\x43"); c.emit(bytes([FORM["components"]])); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "fresh")
    c.emit(b"\x8b\x48\x08\x8b\x50\x04")
    c.mark("scan"); c.emit(b"\x49"); c.branch(b"\x0f\x88", "fresh")
    c.emit(b"\x8b\x34\x8a\x81\x3e"); c.u32(n["label_vmt"]); c.branch(b"\x0f\x85", "scan")
    c.emit(b"\x81\x7e"); c.emit(bytes([VCL["tag"]])); c.u32(MAGIC | YEARS[0]); c.branch(b"\x0f\x85", "scan")
    c.branch(b"\xe9", "done")                                               # made already
    c.mark("fresh")
    c.emit(b"\xa1"); c.u32(n["game_dir"]); c.emit(b"\x8b\x10\x8d\x45\xfc\xb9"); c.u32(texts["picture"])
    c.branch(b"\xe8", n["cat3"])
    c.emit(b"\x8b\x45\xfc\xb2\x01"); c.branch(b"\xe8", n["file_exists"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x83"); c.u32(FORM["image"]); c.emit(b"\x8b\x80"); c.u32(VCL["picture"])
    c.emit(b"\x8b\x55\xfc"); c.branch(b"\xe8", n["load_picture"])
    for year, (left, top) in PLACES.items():
        c.emit(b"\x8b\xcb\xb2\x01\xb8"); c.u32(n["label_vmt"]); c.emit(b"\xff\x50"); c.emit(bytes([VCL["create"]]))
        c.emit(b"\x8b\xf0\xc7\x46"); c.emit(bytes([VCL["tag"]])); c.u32(MAGIC | year)
        c.emit(b"\x8b\x93"); c.u32(FORM["panel"]); c.emit(b"\x8b\xc6\x8b\x08\xff\x91"); c.u32(VCL["set_parent"])
        c.emit(b"\x33\xd2\x8b\xc6\x8b\x08\xff\x91"); c.u32(n["set_auto_size"])
        c.emit(b"\xb2\x01\x8b\xc6"); c.branch(b"\xe8", n["set_transparent"])
        for setter, value in (("set_left", left), ("set_top", top), ("set_width", WIDTH), ("set_height", HEIGHT)):
            c.emit(b"\xba"); c.u32(value); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n[setter])
        c.emit(b"\x8d\x86"); c.u32(VCL["hint"]); c.emit(b"\xba"); c.u32(texts[year]); c.branch(b"\xe8", n["assign"])
        c.emit(b"\xb2\x01\x8b\xc6"); c.branch(b"\xe8", n["set_show_hint"])
        c.emit(b"\xc7\x86"); c.u32(VCL["on_click"]); c.u32(n["click"])
        c.emit(b"\x89\x9e"); c.u32(VCL["on_click"]+4)
    c.mark("done"); c.emit(b"\x8d\x45\xfc\xba\x01\x00\x00\x00"); c.branch(b"\xe8", n["clear"])
    c.emit(b"\x5f\x5e\x5b\x8b\xe5\x5d\xc3")
    code = dict(setup=c.finish())

    for name, back in (("open_image", n["after_image"]), ("open_button", n["after_button"])):   # EBX form
        c = Code(at[name])
        c.emit(b"\x60\x8b\xc3"); c.branch(b"\xe8", at["setup"]); c.emit(b"\x61\x8b\x83"); c.u32(FORM["panel"])
        c.branch(b"\xe9", back)
        code[name] = c.finish()

    # lb1900Click, after the native years (EBX form, EDX Sender, ESI year pointer): a new label's year takes the
    # 1935 branch from its year store on.
    c = Code(at["year_click"])
    c.emit(b"\x3b\x93"); c.u32(FORM["lb1935"]); c.branch(b"\x0f\x84", n["native_1935"])
    c.emit(b"\x85\xd2"); c.branch(b"\x0f\x84", n["no_year"])
    c.emit(b"\x81\x3a"); c.u32(n["label_vmt"]); c.branch(b"\x0f\x85", n["no_year"])
    c.emit(b"\x8b\x42"); c.emit(bytes([VCL["tag"]])); c.emit(b"\x8b\xc8\x81\xe1\x00\x00\xff\xff\x81\xf9"); c.u32(MAGIC)
    c.branch(b"\x0f\x85", n["no_year"])
    c.emit(b"\x0f\xb7\xc0\x50\x66\xb9\x01\x00\x66\xba\x01\x00"); c.branch(b"\xe8", n["encode_date"])   # 1 January
    c.emit(b"\xa1"); c.u32(n["date"]); c.emit(b"\xdd\x18\x9b\x58\x89\x06"); c.branch(b"\xe9", n["after_year"])
    code["year_click"] = c.finish()

    # The start (EAX year pointer, [EDI] main): 1935 keeps its block; later years only mark the notices seen.
    c = Code(at["start_flags"])
    c.emit(b"\x81\x38\x8f\x07\x00\x00"); c.branch(b"\x0f\x84", n["flags_1935"]); c.branch(b"\x0f\x8c", n["after_flags"])
    c.emit(b"\x8b\x07\xc6\x80"); c.u32(MAIN["first_completion_seen"]); c.emit(b"\x01\xc6\x80")
    c.u32(MAIN["spending_share_seen"]); c.emit(b"\x01"); c.branch(b"\xe9", n["after_flags"])
    code["start_flags"] = c.finish()

    # The nation and possession files (EDX the game folder, kept): a later year's own file, else the native one.
    for kind, (_, native, local, back) in FILES.items():
        c = Code(at[kind])
        c.emit(b"\x8b\x0d"); c.u32(n["year"]); c.emit(b"\x8b\x09")
        for year in YEARS:
            c.emit(b"\x81\xf9"); c.u32(year); c.branch(b"\x0f\x84", f"y{year}")
        c.emit(b"\xb9"); c.u32(n[native]); c.branch(b"\xe9", "load")
        for year in YEARS:
            c.mark(f"y{year}"); c.emit(b"\xb9"); c.u32(texts[(kind, year)]); c.branch(b"\xe9", "load")
        c.mark("load"); c.emit(b"\x8d\x45"+bytes([local])); c.branch(b"\xe9", n[back])   # lea eax,[ebp-n]
        code[kind] = c.finish()

    for name, body in code.items():
        limit = 0x400 if name == "setup" else 0x40 if name.startswith("open") else 0xC0 if name in FILES else 0x80
        if len(body) > limit: raise ValueError("Start-year code exceeds its slot: "+name)
        blocks.append(dict(name=name, address=at[name], bytes=body.hex()))
    plans = []
    for site in info["sites"]:
        old = bytes.fromhex(site["original"])
        new = b"\xe9"+struct.pack("<i", at[site["name"]]-site["address"]-5)+b"\x90"*(len(old)-5)
        plans.append(patch("Start years: "+site["name"], site["address"], old, new))
    delta = info["click"]-0x69C6C4
    for label, address, old, new in IN_PLACE:
        plans.append(patch("Start years: "+label, address+delta, bytes.fromhex(old), bytes.fromhex(new)))
    return blocks, plans

"""Date-led historical self-government and independence for RTW3 possessions.

The game has no native country-creation slot for most outcomes. Its later-start
maps represent many independent territories as Neutral, so this adapter uses
that representation and the native ownership-transfer routine. It also blocks
random native secession for core regions and territories with a dated release.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import time

import ai_runtime
import live_cheats as live
import week_display as memory
import weekly_runtime as rt
from hull_rules import patch

REPORT = Path(__file__).with_name("decolonization_report.json")
BASE = 0x301000
TURN_CHECK_OFFSET = 0x774  # CheckTurnEvents -> CheckForPossessionEvent
START_YEAR = 0x4AA4        # campaign +4AA4h: the start year (the save's CampaignStartYear)

# Value-200 home regions in the shipped start maps, plus the extra U.S. core
# regions split across separate map areas. These are never valid random
# independence outcomes while the campaign is running.
CORE_POSSESSIONS = (
    "Argentina", "Austria-Hungary", "Brazil", "Eastern Germany", "Eastern Spain",
    "Eastern USA", "Germany", "Gulf coast", "India", "Italian East Coast",
    "Italian West Coast", "Japan", "Java", "Northern China", "Northern Russia",
    "Northwestern Spain", "Persia", "Russian Far East", "South Afriica",
    "Southern China", "Southern France", "Southeastern seaboard", "Turkey",
    "United Kingdom", "Western France", "Western Russia", "Western Soviet Union",
    "Western USA", "Soviet Unionn Far East",
)
# (year, possession, governments which administered that possession)
# Names and dates follow the game's MapData possession model and historical
# constitutional or independence milestones. When the campaign's current owner
# no longer matches, this rule leaves it untouched. Each release happens in its
# year, or in the first year of a campaign that starts later, and never again:
# a territory the old power takes back afterwards stays with it.
RELEASES = (
    (1922, "Ireland", ("Great Britain", "European NATO")),
    (1931, "Nova Scotia", ("Great Britain", "European NATO")),
    (1931, "New Brunswick", ("Great Britain", "European NATO")),
    (1931, "British Columbia", ("Great Britain", "European NATO")),
    (1931, "South Afriica", ("Great Britain", "European NATO")),
    (1942, "Western Australia", ("Great Britain", "European NATO")),
    (1942, "Eastern Australia", ("Great Britain", "European NATO")),
    (1946, "The Philippines", ("USA", "United States of America", "United States")),
    (1946, "Syria", ("France", "European NATO")),
    (1947, "India", ("Great Britain", "European NATO")),
    (1947, "Pakistan", ("Great Britain", "European NATO")),
    (1947, "New Zealand", ("Great Britain", "European NATO")),
    (1948, "Burma", ("Great Britain", "European NATO")),
    (1948, "Ceylon", ("Great Britain", "European NATO")),
    (1949, "Newfoundland", ("Great Britain", "European NATO")),
    (1951, "Libya", ("Italy", "European NATO")),
    (1954, "Cochin China", ("France", "European NATO")),
    (1954, "Annam", ("France", "European NATO")),
    (1954, "Tonkin", ("France", "European NATO")),
    (1956, "Egypt", ("Great Britain", "European NATO")),
    (1956, "Sudan", ("Great Britain", "European NATO")),
    (1956, "Tunisia", ("France", "European NATO")),
    (1956, "Morocco", ("France", "European NATO")),
    (1957, "Malaya", ("Great Britain", "European NATO")),
    (1960, "Cyprus", ("Great Britain", "European NATO")),
    (1960, "Nigeria", ("Great Britain", "European NATO")),
    (1960, "Somalia", ("Italy", "European NATO")),
    (1960, "Somaliland", ("Great Britain", "European NATO")),
    (1960, "Senegal", ("France", "European NATO")),
    (1960, "Cameroon", ("France", "European NATO")),
    (1960, "Middle Congo", ("France", "European NATO")),
    (1960, "Madagascar", ("France", "European NATO")),
    (1961, "Sierra Leone", ("Great Britain", "European NATO")),
    (1961, "Tanganyika", ("Great Britain", "European NATO")),
    (1961, "Kuwait", ("Great Britain", "European NATO")),
    (1962, "Algeria", ("France", "European NATO")),
    (1962, "Jamaica", ("Great Britain", "European NATO")),
    (1962, "Trinidad", ("Great Britain", "European NATO")),
    (1963, "Kenya", ("Great Britain", "European NATO")),
    (1963, "Zanzibar", ("Great Britain", "European NATO")),
    (1964, "Malta", ("Great Britain", "European NATO")),
    (1965, "Singapore", ("Great Britain", "European NATO")),
    (1967, "Yemen", ("Great Britain", "European NATO")),
    (1971, "East Bengal", ("Great Britain", "European NATO", "Pakistan")),
    (1971, "Trucial States", ("Great Britain", "European NATO")),
    (1975, "Papua", ("Great Britain", "European NATO", "Australia")),
    (1977, "Djibouti", ("France", "European NATO")),
    (1980, "New Hebrides", ("France", "Great Britain", "European NATO")),
)
PROTECTED_POSSESSIONS = tuple(sorted(set(CORE_POSSESSIONS) | {row[1] for row in RELEASES}))


def discover(blob, text_base):
    """Find reviewed event, rebellion, and ownership routines."""
    check_turn = rt.method_address(blob, text_base, "CheckTurnEvents")
    possession_event = rt.method_address(blob, text_base, "CheckForPossessionEvent")
    get_possession = rt.method_address(blob, text_base, "GetPossessionWithName")
    get_nation = rt.method_address(blob, text_base, "GetBNationWithName")
    change_owner = rt.method_address(blob, text_base, "ChangePossessionOwner")
    rebellion = rt.method_address(blob, text_base, "DoRebellion")
    load = rt.method_address(blob, text_base, "LoadBuildCampaign") - text_base
    if blob[load+0x264:load+0x26D].hex() != "8b55d88982" + struct.pack("<I", START_YEAR).hex():
        raise ValueError("Unknown campaign start-year field.")   # mov edx,[ebp-28h]; mov [edx+4AA4h],eax
    site = check_turn + TURN_CHECK_OFFSET
    offset = site - text_base
    if not 0 <= offset <= len(blob) - 5 or blob[offset] != 0xE8:
        raise ValueError("Historical decolonization refuses an unknown campaign event call.")
    target = site + 5 + struct.unpack_from("<i", blob, offset + 1)[0]
    if target != possession_event:
        raise ValueError("Campaign event call no longer targets CheckForPossessionEvent.")
    if blob[get_possession-text_base:get_possession-text_base+9].hex() != "558bec83c4ec535657":
        raise ValueError("Unknown GetPossessionWithName routine.")
    if blob[get_nation-text_base:get_nation-text_base+9].hex() != "558bec83c4f8535657":
        raise ValueError("Unknown GetBNationWithName routine.")
    if blob[change_owner-text_base:change_owner-text_base+9].hex() != "558bec83c4f0535657":
        raise ValueError("Unknown ChangePossessionOwner routine.")
    rebellion_original = blob[rebellion-text_base:rebellion-text_base+7]
    change_owner_original = blob[change_owner-text_base:change_owner-text_base+6]
    if rebellion_original.hex() != "558bec6a006a00":
        raise ValueError("Unknown DoRebellion entry; no rebellion filter installed.")
    if change_owner_original.hex() != "558bec83c4f0":
        raise ValueError("Unknown ownership-transfer entry; no secession filter installed.")
    if b"\xc2\x04\x00" not in blob[change_owner-text_base:change_owner-text_base+0x400]:
        raise ValueError("Unknown ChangePossessionOwner argument cleanup.")
    return dict(site=site, original=blob[offset:offset+5], check_turn=check_turn,
                possession_event=possession_event, get_possession=get_possession,
                get_nation=get_nation, change_owner=change_owner, rebellion=rebellion,
                rebellion_original=rebellion_original,
                change_owner_original=change_owner_original,
                year_pointer=0x9F7328 + (text_base - BASE),
                releases=len(RELEASES), changes_campaign_data=True,
                changes_executable_file=False, random_rolls_added=False,
                native_possession_upheaval_event_preserved=True,
                protected_possessions=list(PROTECTED_POSSESSIONS),
                native_core_rebellions_suppressed=True,
                native_random_independence_suppressed_for_protected=True)


def delphi_string(value):
    return struct.pack("<HHiI", 1200, 2, -1, len(value)) + value.encode("utf-16-le") + b"\0\0"


def release_processor(address, data_base, literals, info):
    """EAX=campaign object; inspect each dated possession without random rolls, in the release year or a later
    campaign start's first year (ECX = the later of the two)."""
    from campaign_security import Code
    c = Code(address)
    c.emit(bytes.fromhex("5356578bd8"))  # preserve nonvolatile registers; EBX = campaign
    for index, (year, possession, owners) in enumerate(RELEASES):
        c.emit(b"\xb9"); c.u32(year); c.emit(b"\x8b\x83"); c.u32(START_YEAR)   # ECX = year, EAX = start year
        c.emit(bytes.fromhex("3bc17e028bc8"))                                  # cmp eax,ecx; jle; mov ecx,eax
        c.emit(b"\xa1"); c.u32(info["year_pointer"]); c.emit(bytes.fromhex("8b003bc1"))
        c.branch(b"\x0f\x85", f"next_{index}")
        c.emit(bytes.fromhex("8bc3ba")); c.u32(literals[(possession, None)])
        c.branch(b"\xe8", info["get_possession"])
        c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", f"next_{index}")
        c.emit(bytes.fromhex("8bf0"))         # ESI = possession; EBP remains caller-owned
        c.emit(bytes.fromhex("8b7e61"))       # EDI = current owner
        c.emit(b"\x85\xff"); c.branch(b"\x0f\x84", f"next_{index}")
        for owner in owners:
            c.emit(bytes.fromhex("8bc331c9ba")); c.u32(literals[(possession, owner)])
            c.branch(b"\xe8", info["get_nation"])
            c.emit(bytes.fromhex("3bc7")); c.branch(b"\x0f\x84", f"release_{index}")
        c.branch(b"\xe9", f"next_{index}")
        c.mark(f"release_{index}")
        c.emit(bytes.fromhex("8bc38bd631c96a00"))
        c.branch(b"\xe8", info["change_owner"])
        c.mark(f"next_{index}")
    c.emit(bytes.fromhex("5f5e5bc3"))
    return c.finish()


def turn_event_thunk(address, processor, info):
    """Run the native upheaval event unchanged, then apply dated transfers."""
    from campaign_security import Code
    c = Code(address)
    c.emit(b"\x50")                         # save campaign object
    c.branch(b"\xe8", info["possession_event"])
    c.emit(b"\x50\x8b\x44\x24\x04")       # save native result; reload campaign object
    c.branch(b"\xe8", processor)
    c.emit(bytes.fromhex("5883c404c3"))
    return c.finish()


def relative_jump(address, destination):
    return b"\xe9" + struct.pack("<i", destination - address - 5)


def entry_trampoline(address, original, resume):
    return original + relative_jump(address + len(original), resume)


def protected_possession_guard(address, trampoline, info, literals, *, owner_guard=False,
                               processor_start=0, processor_end=0):
    """Skip random secession for protected names; scheduled releases bypass the owner guard.

    The rebellion guard covers every protected name. The owner guard covers only core home regions: the game also
    hands possessions to Neutral after a war (ReturnTakenPossessionsAfterWar) and for Chinese concessions, which
    must keep working for colonies, while a home region becoming Neutral is always a rebellion's outcome."""
    from campaign_security import Code
    c = Code(address)
    c.emit(b"\x9c\x60")  # preserve incoming flags and all registers
    if owner_guard:
        # ChangePossessionOwner: ECX is the new owner, EDX is the target,
        # and the native routine returns with RET 4.
        c.emit(bytes.fromhex("837c241800"))
        c.branch(b"\x0f\x85", "native")  # only guard transfers to Neutral
        c.emit(bytes.fromhex("8b4424243d")); c.u32(processor_start)
        c.branch(b"\x0f\x82", "guard")   # called from below the release processor: the game's own code
        c.emit(b"\x3d"); c.u32(processor_end)
        c.branch(b"\x0f\x82", "native")  # dated release processor is allowed
        c.mark("guard")
    for name in (CORE_POSSESSIONS if owner_guard else PROTECTED_POSSESSIONS):
        c.emit(bytes.fromhex("8b44241c31c9ba")); c.u32(literals[("guard", name)])
        c.branch(b"\xe8", info["get_possession"])
        c.emit(bytes.fromhex("3b442414"))  # compare result with original EDX target
        c.branch(b"\x0f\x84", "blocked")
    c.mark("native")
    c.emit(b"\x61\x9d")
    c.branch(b"\xe9", trampoline)
    c.mark("blocked")
    c.emit(b"\x61\x9d")
    c.emit(b"\xc2\x04\x00" if owner_guard else b"\xc3")
    return c.finish()


def entry_jump_patch(label, address, original, destination):
    replacement = relative_jump(address, destination) + b"\x90" * (len(original) - 5)
    return patch(label, address, original, replacement)


def attach(wait=30):
    memory.configure()
    deadline = time.monotonic() + wait
    while True:
        games = [(pid, path) for pid, path in rt.process_candidates()
                 if path.resolve() == (rt.GAME / "RTW3.exe").resolve()]
        if len(games) == 1:
            break
        if time.monotonic() >= deadline:
            raise ValueError("Open this local RTW3 copy through Play with mods first.")
        time.sleep(0.5)
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle:
        raise rt.win_error("Cannot open the local game for historical decolonization")
    try:
        module, _ = rt.module_info(pid)
        if REPORT.exists():
            prior = json.loads(REPORT.read_text(encoding="utf-8"))
            if (prior.get("attached") and prior.get("pid") == pid and prior.get("base") == module
                    and rt.report_is_current(REPORT, pid)):
                ai_runtime.verify(handle, prior["patches"], "replacement")
                return prior
        _, text_base, blob = live.unhooked_text(pid, handle)
        info = discover(blob, text_base)
        layout = live.discover(blob, text_base)
        ai_runtime.require_title_screen(handle, layout)
        allocation = rt.K.VirtualAllocEx(handle, None, 0x7000, 0x3000, 0x40)
        if not allocation:
            raise rt.win_error("Cannot allocate the historical decolonization rules")
        allocation = int(allocation)
        try:
            literal_base = allocation + 0x4000
            literal_cursor = literal_base
            literals = {}
            content = bytearray()

            def add_literal(key, value):
                nonlocal content
                if key in literals:
                    return
                while len(content) % 4:
                    content.append(0)
                literals[key] = literal_cursor + len(content) + 12
                content.extend(delphi_string(value))

            for year, possession, owners in RELEASES:
                for key, value in [( (possession, None), possession),
                                   *[((possession, owner), owner) for owner in owners]]:
                    add_literal(key, value)
            for possession in PROTECTED_POSSESSIONS:
                add_literal(("guard", possession), possession)
            if literal_cursor + len(content) > allocation + 0x7000:
                raise ValueError("Historical decolonization names exceed the reserved memory.")
            memory.write(handle, literal_cursor, bytes(content))
            processor_address = allocation + 0x400
            processor = release_processor(processor_address, literal_base, literals, info)
            if len(processor) > 0x2000:
                raise ValueError("Historical decolonization rules exceed their reserved code area.")
            thunk_address = allocation + 0x100
            thunk = turn_event_thunk(thunk_address, processor_address, info)
            rebellion_guard_address = allocation + 0x2400
            owner_guard_address = allocation + 0x2C00
            rebellion_trampoline_address = allocation + 0x3600
            owner_trampoline_address = allocation + 0x3620
            rebellion_trampoline = entry_trampoline(
                rebellion_trampoline_address, info["rebellion_original"],
                info["rebellion"] + len(info["rebellion_original"]))
            owner_trampoline = entry_trampoline(
                owner_trampoline_address, info["change_owner_original"],
                info["change_owner"] + len(info["change_owner_original"]))
            rebellion_guard = protected_possession_guard(
                rebellion_guard_address, rebellion_trampoline_address, info, literals)
            owner_guard = protected_possession_guard(
                owner_guard_address, owner_trampoline_address, info, literals, owner_guard=True,
                processor_start=processor_address, processor_end=processor_address + len(processor))
            if len(rebellion_guard) > owner_guard_address - rebellion_guard_address:
                raise ValueError("Core-region rebellion guard exceeds its reserved code area.")
            if owner_guard_address + len(owner_guard) > rebellion_trampoline_address:
                raise ValueError("Neutral-transfer guard exceeds its reserved code area.")
            if literal_cursor + len(content) > allocation + 0x7000:
                raise ValueError("Historical decolonization literals exceed their reserved area.")
            memory.write(handle, processor_address, processor)
            memory.write(handle, thunk_address, thunk)
            memory.write(handle, rebellion_trampoline_address, rebellion_trampoline)
            memory.write(handle, owner_trampoline_address, owner_trampoline)
            memory.write(handle, rebellion_guard_address, rebellion_guard)
            memory.write(handle, owner_guard_address, owner_guard)
            for address, code in ((processor_address, processor), (thunk_address, thunk),
                                  (rebellion_trampoline_address, rebellion_trampoline),
                                  (owner_trampoline_address, owner_trampoline),
                                  (rebellion_guard_address, rebellion_guard),
                                  (owner_guard_address, owner_guard)):
                rt.K.FlushInstructionCache(handle, address, len(code))
            replacement = b"\xe8" + struct.pack("<i", thunk_address - info["site"] - 5)
            plans = [patch("Historical decolonization after native turn events", info["site"],
                           info["original"], replacement),
                     entry_jump_patch("Block random rebellions in core and dated-release territories",
                                      info["rebellion"], info["rebellion_original"],
                                      rebellion_guard_address),
                     entry_jump_patch("Block random neutral secession from protected territories",
                                      info["change_owner"], info["change_owner_original"],
                                      owner_guard_address)]
            ai_runtime.verify(handle, plans, "original")
            applied = []
            try:
                for item in plans:
                    rt.write_code(handle, item["address"], bytes.fromhex(item["original"]),
                                  bytes.fromhex(item["replacement"]))
                    applied.append(item)
                ai_runtime.verify(handle, plans, "replacement")
                report_info = {key: value.hex() if isinstance(value, bytes) else value
                               for key, value in info.items()}
                saved = dict(adapter="historical-decolonization", attached=True, pid=pid, base=module,
                             allocation=allocation, patches=plans, details=report_info,
                             campaign_gameplay_verified=False,
                             ownership_rule="release to Neutral in the scheduled year (or a later-starting campaign's first year) while the historical administering power owns it",
                             native_possession_upheaval_event_preserved=True,
                             protected_possessions=list(PROTECTED_POSSESSIONS),
                             native_core_rebellions_suppressed=True,
                             native_random_independence_suppressed_for_protected=True,
                             scheduled_release_transfer_exempt=True)
                REPORT.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
                return saved
            except Exception:
                for item in reversed(applied):
                    rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]),
                                  bytes.fromhex(item["original"]))
                raise
        except Exception:
            # The allocation is session-only and disappears when RTW3 closes.
            if rt.read(handle, info["site"], 5) == info["original"]:
                rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise
    finally:
        rt.K.CloseHandle(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attach",))
    args = parser.parse_args()
    try:
        print(json.dumps(attach()))
    except (OSError, ValueError) as error:
        print(json.dumps(dict(ok=False, message=str(error))))
        raise SystemExit(1)

"""Raise the ship designer's added-graphics limit from 25 to 100 while retaining each graphic's native format.

The designer's Add, Mirror and Copy commands refuse a 26th graphic, and both design-file loaders (LoadMe: INI
sections [Equipment0]...) read only 25 sections, although saving writes every graphic. Campaign saves store the
list's own count. All five limits become 100, so a design file keeps its graphics when it is loaded again.
"""
import json
from pathlib import Path
import re
import weekly_runtime as rt
import week_display as memory

REPORT = Path(__file__).with_name("ship_visual_layers_report.json")
ADAPTER_VERSION = 2
NATIVE_LIMIT = 25
MAX_VISUALS = 100
# Add, Mirror and Copy: the form's design [+0xE6C], its graphics list [+0xAA], Count [+8] < 25.
ADD_GUARD = re.compile(rb"\x8b\x83\x6c\x0e\x00\x00\x8b\x80\xaa\x00\x00\x00(\x83\x78\x08\x19)\x7c", re.S)
# Both LoadMe loops: graphics.Add(item); inc esi; cmp esi, 25; jne next section.
LOAD_LOOP = re.compile(rb"\x8b\x83\xaa\x00\x00\x00(?:\x8b\xd7|\x8b\x55\xfc)\xe8....\x46(\x83\xfe\x19)\x0f\x85", re.S)
LIMITS = (("add", ADD_GUARD, 3), ("load", LOAD_LOOP, 2))


def discover(blob, text_base):
    """Locate the three add guards and the two design-file load loops by their exact native bytes."""
    sites = []
    for kind, pattern, count in LIMITS:
        found = list(pattern.finditer(blob))
        if len(found) != count:
            raise ValueError(f"Cannot verify the native 25-graphic {kind} limits ({len(found)} of {count} found).")
        for match in found:
            original = match.group(1)
            sites.append({"kind": kind, "address": text_base + match.start(1), "original": original.hex(),
                          "replacement": (original[:-1] + bytes([MAX_VISUALS])).hex()})
    return {"sites": sites, "native_limit": NATIVE_LIMIT, "visual_limit": MAX_VISUALS}


def attach(pid):
    memory.configure()
    candidates = dict(rt.process_candidates())
    if candidates.get(pid) != rt.GAME / "RTW3.exe":
        raise ValueError("The graphics extension can attach only to this RTW3 copy.")
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle:
        raise rt.win_error("Cannot open RTW3 to extend ship graphics")

    def reads(site, key):
        return rt.read(handle, site["address"], len(site[key]) // 2).hex() == site[key]
    try:
        base, _ = rt.module_info(pid)
        if REPORT.exists():
            previous = json.loads(REPORT.read_text(encoding="utf-8"))
            if (previous.get("adapter_version") == ADAPTER_VERSION and previous.get("pid") == pid
                    and previous.get("base") == base and rt.report_is_current(REPORT, pid)):
                if all(reads(site, "replacement") for site in previous["sites"]):
                    return previous
                raise ValueError("The existing ship-graphics attachment has unexpected changes.")
        text_base, blob = rt.text_section(handle, base)
        item = discover(blob, text_base)
        if not all(reads(site, "original") for site in item["sites"]):
            raise ValueError("RTW3 changed during ship-graphics preparation. Nothing was applied.")
        written = []
        try:
            for site in item["sites"]:
                rt.write_code(handle, site["address"], bytes.fromhex(site["original"]),
                              bytes.fromhex(site["replacement"]))
                written.append(site)
                if not reads(site, "replacement"):
                    raise ValueError("The ship-graphics limit did not verify after patching.")
        except Exception:
            for site in reversed(written):
                rt.write_code(handle, site["address"], bytes.fromhex(site["replacement"]),
                              bytes.fromhex(site["original"]))
            raise
        item.update(adapter_version=ADAPTER_VERSION, pid=pid, base=base, attached=True,
                    note="100 Equipment graphics per design, also when a design file is loaded; each native "
                         "graphic retains its original point format.")
        REPORT.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
        return item
    finally:
        rt.K.CloseHandle(handle)

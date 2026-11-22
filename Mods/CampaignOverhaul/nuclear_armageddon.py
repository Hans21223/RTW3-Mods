"""Nuclear Armageddon: unlimited nuclear weapons at the same prices, and nuclear warheads for heavy SAMs and SSMs.

A switch in Expanded Timeline's runtime (the modern-research adapter, attached first): it sets the shell doctrine's
armageddon flag and renames the doctrine's nuclear missiles tick box. The rules live with the weapons they change:
- modern_navy: a main battery of 16 inches or more fires a nuclear shell with every hit, not its first of a battle;
- nuclear_subs: every missile hit of an SSBN's salvo may be nuclear, not one;
- modern_air_defence and nuclear_subs: a heavy SSM, and a heavy SAM, of a nation with the warhead research
  (modern_tree.NUCLEAR_SHELLS) may be nuclear, as the doctrine's nuclear missiles.
Each weapon still needs the player's tick box and costs what it did (shell_doctrine); computer nations still fire
none first, and the tension, the news and the ban treaty follow as before. Light and medium SAMs and SSMs, smaller
guns and the torpedoes of boats other than SSNs stay conventional.
Closing RTW3 ends it with the rest of the runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import time

import shell_doctrine as doctrine
import week_display as memory
import weekly_runtime as rt

REPORT = Path(__file__).with_name("nuclear_armageddon_report.json")
ADAPTER_VERSION = 1
CAPTION = f"Use nuclear SSBN, SSM, SAM ({doctrine.MISSILE_COST} each)"


def plan(blocks):
    """[(address, original, replacement)] from Expanded Timeline's code blocks (name -> block): the flag, the caption."""
    flag, text = blocks.get(doctrine.ARMAGEDDON_BLOCK), blocks.get(doctrine.MISSILE_TEXT_BLOCK)
    if not flag or not text:
        raise ValueError("Nuclear Armageddon needs Expanded Timeline 1.44.0 or later.")
    old, new = bytes.fromhex(text["bytes"]), doctrine.literal(CAPTION)
    if len(new) > len(old):
        raise ValueError("Nuclear Armageddon's tick box caption does not fit.")
    return [(flag["address"], bytes.fromhex(flag["bytes"]), struct.pack("<I", 1)),
            (text["address"], old[:len(new)], new)]


def expanded_timeline(pid, module):
    import modern_research
    saved = json.loads(modern_research.REPORT.read_text(encoding="utf-8")) if modern_research.REPORT.exists() else {}
    if not (saved.get("attached") and saved.get("pid") == pid and saved.get("base") == module):
        raise ValueError("Nuclear Armageddon needs Expanded Timeline attached first.")
    return {block["name"]: block for block in saved.get("code_blocks", [])}


def attach(wait=30):
    memory.configure()
    rt.configure_api()
    deadline = time.monotonic()+wait
    while True:
        games = [(pid, path) for pid, path in rt.process_candidates() if path == rt.GAME/"RTW3.exe"]
        if len(games) == 1:
            break
        if time.monotonic() >= deadline:
            raise ValueError("Open the local game through Play with mods first.")
        time.sleep(0.5)
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle:
        raise rt.win_error("Cannot open RTW3 for Nuclear Armageddon")
    try:
        module, _ = rt.module_info(pid)
        writes = plan(expanded_timeline(pid, module))
        if REPORT.exists():
            prior = json.loads(REPORT.read_text(encoding="utf-8"))
            if (prior.get("adapter_version") == ADAPTER_VERSION and prior.get("attached") and prior.get("pid") == pid
                    and prior.get("base") == module and rt.report_is_current(REPORT, pid)
                    and all(rt.read(handle, address, len(new)) == new for address, _, new in writes)):
                return prior
        for address, old, _ in writes:
            if rt.read(handle, address, len(old)) != old:
                raise ValueError("Expanded Timeline's nuclear doctrine changed; Nuclear Armageddon refused.")
        for address, _, new in writes:
            memory.write(handle, address, new)
        saved = {"adapter": "nuclear-armageddon", "adapter_version": ADAPTER_VERSION, "attached": True, "pid": pid,
                 "base": module, "writes": [dict(address=address, original=old.hex(), replacement=new.hex())
                                            for address, old, new in writes],
                 "caption": CAPTION, "campaign_gameplay_verified": False}
        REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
        return saved
    finally:
        rt.K.CloseHandle(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attach",))
    args = parser.parse_args()
    try:
        print(json.dumps(attach()))
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"ok": False, "message": str(error)}))
        raise SystemExit(1)

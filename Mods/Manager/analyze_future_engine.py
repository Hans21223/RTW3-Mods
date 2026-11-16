"""Read-only diagnostics for submarine and post-1970 engine extension work.

Reads the normally authenticated local game. Never patches code or campaign data.
"""
import argparse
import json
from pathlib import Path
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor"))
sys.path.insert(0, str(HERE.parent / "CampaignOverhaul"))
import capstone
import weekly_runtime as runtime


def methods(blob, base):
    found = {}
    for match in re.finditer(rb"[\x02-\x40][A-Za-z_][A-Za-z0-9_]{1,63}", blob):
        at = match.start()
        size = blob[at]
        value = blob[at+1:at+1+size]
        if at < 6 or len(value) != size or not re.fullmatch(rb"[A-Za-z_][A-Za-z0-9_]*", value):
            continue
        length, address = struct.unpack_from("<HI", blob, at-6)
        if 7+size <= length < 1200 and base <= address < base+len(blob):
            found.setdefault(address, []).append(value.decode())
    return {address: sorted(set(names)) for address, names in found.items()}


def diagnostics(blob, base, targets):
    named = methods(blob, base)
    ordered = sorted(named)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    def context(at):
        start = blob.rfind(b"\x55\x8b\xec", max(0, at-0x1800), at+1)
        if start < 0: start = max(0, at-32)
        insns = list(md.disasm(blob[start:at+96], base+start))
        near = [i for i in insns if base+at-20 <= i.address <= base+at+48]
        previous = next((address for address in reversed(ordered) if address <= base+at), None)
        return {"address": hex(base+at), "nearest_named": named.get(previous, []),
                "named_distance": base+at-previous if previous else None,
                "instructions": [f"{i.address:x} {i.mnemonic} {i.op_str}" for i in near]}

    strings = []
    for match in re.finditer(rb"(?:[\x20-\x7e]\x00){8,}", blob):
        at = match.start()
        if at < 4: continue
        length = struct.unpack_from("<I", blob, at-4)[0]
        if not 8 <= length <= 800 or match.end()-at < length*2: continue
        value = blob[at:at+length*2].decode("utf-16-le")
        if not re.search(r"submarine|1970|retire|end of (?:the )?game|continue playing|campaign end", value, re.I): continue
        address = struct.pack("<I", base+at)
        refs = [context(m.start()) for m in re.finditer(re.escape(address), blob)]
        strings.append({"text": value, "references": refs[:12]})
    refs = {}
    for value in targets:
        packed = struct.pack("<I", value)
        refs[hex(value)] = [context(m.start()) for m in re.finditer(re.escape(packed), blob)]
    return {"methods": {hex(a): n for a,n in named.items() if any(re.search(r"sub|depth|dive|endgame|retir", x, re.I) for x in n)},
            "strings": strings, "references": refs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", action="append", default=[])
    args = parser.parse_args()
    runtime.configure_api()
    games = [(p, path) for p,path in runtime.process_candidates() if path == runtime.GAME/"RTW3.exe"]
    if len(games) != 1: raise ValueError("Open exactly one local RTW3 game for read-only inspection.")
    pid,path = games[0]
    handle = runtime.K.OpenProcess(0x410, False, pid)
    if not handle: raise runtime.win_error("Cannot inspect game")
    try:
        module_base,_ = runtime.module_info(pid)
        base,blob = runtime.text_section(handle,module_base)
        result = diagnostics(blob,base,[int(v,0) for v in args.reference])
        result.update(pid=pid, executable=str(path), module_base=hex(module_base), memory_modified=False)
        output = HERE/"future-engine-diagnostics.json"
        output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"report": str(output), "strings":len(result["strings"]),
                          "reference_counts":{k:len(v) for k,v in result["references"].items()}, "memory_modified":False}))
    finally:
        runtime.K.CloseHandle(handle)


if __name__ == "__main__":
    main()

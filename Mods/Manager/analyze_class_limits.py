"""Read-only search for displacement error messages and their code references."""
import bisect
import json
from pathlib import Path
import re
import struct
import sys
sys.path.insert(0, str(Path(__file__).parent / "vendor"))
sys.path.insert(0, str(Path(__file__).parent.parent / "CampaignOverhaul"))
import capstone
import weekly_runtime as rt


def symbols(blob, base):
    out = {}
    for match in re.finditer(rb"[\x02-\x40][A-Za-z_][A-Za-z0-9_]{1,63}", blob):
        off = match.start()
        length = blob[off]
        value = blob[off+1:off+1+length]
        if len(value) != length or not re.fullmatch(rb"[A-Za-z_][A-Za-z0-9_]*", value) or off < 6:
            continue
        record_length, address = struct.unpack_from("<HI", blob, off-6)
        if 7+length <= record_length < 1200 and base <= address < base+len(blob):
            out.setdefault(address, []).append(value.decode())
    return out


def main():
    rt.configure_api()
    pid, path = [game for game in rt.process_candidates() if game[1] == rt.GAME/"RTW3.exe"][0]
    handle = rt.K.OpenProcess(0x410, False, pid)
    try:
        base, size = rt.module_info(pid)
        text_base, blob = rt.text_section(handle, base)
        syms = symbols(blob, text_base)
        starts = sorted(syms)
        expression = sys.argv[1] if len(sys.argv)>1 else r"displace|too (large|small)|destroyer.*(size|ton)|cruiser.*(size|ton)"
        rows = []
        for match in re.finditer(rb"(?:(?:[\x09\x0a\x0d\x20-\x7e])\x00){5,}", blob):
            off = match.start()
            if off < 4:
                continue
            value = match.group().decode("utf-16-le")
            length, = struct.unpack_from("<I", blob, off-4)
            if length != len(value) or not re.search(expression, value, re.I):
                continue
            address = text_base+off
            refs=[]
            pointer=struct.pack("<I",address)
            search=0
            while True:
                found=blob.find(pointer,search)
                if found<0: break
                owner=bisect.bisect_right(starts,text_base+found)-1
                refs.append({"operand":hex(text_base+found),"near_method":syms.get(starts[owner],[]) if owner>=0 else []})
                search=found+4
            rows.append({"address":hex(address),"message":value,"references":refs})
        print(json.dumps(rows,indent=2))
        (Path(__file__).parent/"class-limit-messages.json").write_text(json.dumps(rows,indent=2)+"\n",encoding="utf-8")
    finally:
        rt.K.CloseHandle(handle)


if __name__ == "__main__": main()

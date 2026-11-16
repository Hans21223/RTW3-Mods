"""Read-only method diagnostics for the local RTW3 runtime."""
import json
import re
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).parent / "vendor"))
sys.path.insert(0, str(Path(__file__).parent.parent / "CampaignOverhaul"))
import capstone
import weekly_runtime as runtime


def main():
    runtime.configure_api()
    games = [(pid, path) for pid, path in runtime.process_candidates() if path == runtime.GAME / "RTW3.exe"]
    if len(games) != 1:
        raise ValueError("Open the local RTW3 copy first.")
    pid, path = games[0]
    handle = runtime.K.OpenProcess(0x410, False, pid)
    try:
        base, size = runtime.module_info(pid)
        text_base, blob = runtime.text_section(handle, base)
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        wanted = sys.argv[1:] or ["UpdateBudgetNumbers", "GetMonthlyBalance"]
        if wanted and wanted[0] == "--controls":
            data = path.read_bytes()
            key = b"seDisplacement"
            offset = 0
            while True:
                offset = data.find(key, offset)
                if offset < 0:
                    break
                snippet = data[max(0,offset-70):offset+500]
                print(hex(offset), repr(snippet))
                offset += len(key)
            return
        if wanted and wanted[0] == "--names":
            expression = wanted[1]
            names = set()
            for match in re.finditer(rb"[\x02-\x40][A-Za-z_][A-Za-z0-9_]{1,63}", blob):
                off = match.start()
                length = blob[off]
                value = blob[off+1:off+1+length]
                if len(value) != length or not re.fullmatch(rb"[A-Za-z_][A-Za-z0-9_]*", value) or off < 6:
                    continue
                record_length, address = struct.unpack_from("<HI", blob, off-6)
                name = value.decode()
                if 7+length <= record_length < 1200 and text_base <= address < text_base+len(blob) and re.search(expression, name, re.I):
                    names.add((name, hex(address)))
            print(json.dumps(sorted(names), indent=2))
            return
        result = []
        for name in wanted:
            custom_range = name.startswith("@") and ":" in name
            address = int(name[1:].split(":")[0], 16) if name.startswith(("@", "~")) else runtime.method_address(blob, text_base, name)
            size = int(name.split(":")[1], 16) if custom_range else 0x900
            if name.startswith("~"):
                target = int(name[1:], 16)
                offset = blob.rfind(b"\x55\x8b\xec", max(0,target-text_base-0x3000), target-text_base)
                address = text_base+offset
                size = 0x4000
            result.append(f"\n{name} @ {address:#x}")
            for ins in md.disasm(blob[address-text_base:address-text_base+size], address):
                line = f"{ins.address:08x} {ins.mnemonic:7} {ins.op_str}"
                if ins.mnemonic == "mov" and ins.op_str.startswith(("eax, 0x", "edx, 0x", "ecx, 0x")):
                    pointer = int(ins.op_str.split(", ")[1], 16)
                    if text_base + 12 <= pointer < text_base + len(blob) - 4:
                        off = pointer - text_base
                        length = struct.unpack_from("<I", blob, off - 4)[0]
                        if 0 < length < 150:
                            value = blob[off:off+length*2].decode("utf-16-le", errors="replace")
                            if all(ord(c) >= 32 for c in value):
                                line += "  ; " + repr(value)
                result.append(line)
                if ins.mnemonic == "ret" and not custom_range:
                    break
        output = "\n".join(result)
        print(output)
        (Path(__file__).parent / "campaign-diagnostics.txt").write_text(output, encoding="utf-8")
    finally:
        runtime.K.CloseHandle(handle)


if __name__ == "__main__":
    main()

"""Read-only scan of the running RTW3 for damaged VCL controls.

The exit crash "Access violation ... Read of address 58000023" is TControl.GetAction reading a control's action
link (+0x78) that holds garbage; VCL calls it for every control of a form when one of the form's components is
freed. This walks Application's forms and their owned components and lists every control whose action link is
neither nil nor an action-link object, and every component pointer that is not a live object. Nothing is written.

Run with the game open (the crash dialog may be showing):  python Mods/Manager/scan_controls.py
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/"CampaignOverhaul"))
import weekly_runtime as rt

CLASS_NAME, PARENT, SELF = -0x38, -0x30, -0x58          # VMT fields (Delphi XE+ 32-bit)
COMPONENTS, NAME, OWNER, ACTION_LINK = 0x10, 0x8, 0x4, 0x78
PARENT_FIELD = 0x40                                        # TControl.FParent (read only for the report)


class Game:
    def __init__(self):
        rt.configure_api()
        games = [g for g in rt.process_candidates() if g[1] == rt.GAME/"RTW3.exe"]
        if len(games) != 1: raise SystemExit("Open RTW3 first (exactly one running copy).")
        self.pid = games[0][0]
        self.handle = rt.K.OpenProcess(0x410, False, self.pid)       # query + read only
        if not self.handle: raise rt.win_error("Cannot open the game for reading")
        self.module, _ = rt.module_info(self.pid)
        header = self.read(self.module, 0x1000)
        pe = struct.unpack_from("<I", header, 0x3C)[0]
        count, optional = struct.unpack_from("<H", header, pe+6)[0], struct.unpack_from("<H", header, pe+20)[0]
        self.sections = []
        for i in range(count):
            at = pe+24+optional+40*i
            name = header[at:at+8].rstrip(b"\0").decode("latin-1")
            size, rva, flags = struct.unpack_from("<II", header, at+8)+(struct.unpack_from("<I", header, at+36)[0],)
            self.sections.append((name, self.module+rva, size, flags))
        self.low = self.module
        self.high = max(start+size for _, start, size, _ in self.sections)
        self.cache = {}

    def read(self, address, size):
        try: return rt.read(self.handle, address, size)
        except Exception: return None

    def u32(self, address):
        data = self.read(address, 4)
        return None if data is None or len(data) < 4 else struct.unpack("<I", data)[0]

    def is_vmt(self, vmt):
        return vmt is not None and self.low <= vmt < self.high and self.u32(vmt+SELF) == vmt

    def class_name(self, vmt):
        if not self.is_vmt(vmt): return f"<not an object: {vmt or 0:#x}>"
        at = self.u32(vmt+CLASS_NAME)
        data = self.read(at, 64) if at else None
        return data[1:1+data[0]].decode("latin-1") if data else "?"

    def descends(self, vmt, ancestor):
        for _ in range(40):
            if vmt == ancestor: return True
            parent = self.u32(vmt+PARENT)
            vmt = self.u32(parent) if parent else None
            if not vmt: return False
        return False

    def text(self, pointer):
        if not pointer: return ""
        length = self.u32(pointer-4)
        data = self.read(pointer, 2*min(length or 0, 80))
        return data.decode("utf-16-le", "replace") if data else "?"

    def section(self, start, size):
        if start not in self.cache: self.cache[start] = self.read(start, size) or b""
        return self.cache[start]

    def find_class(self, name):
        """VMT of a class by name, searched in the image's sections."""
        needle = bytes([len(name)])+name.encode()
        for _, start, size, _ in self.sections:
            data = self.section(start, size)
            at = data.find(needle)
            while at >= 0:
                name_address = start+at
                for section_name, s2, z2, _ in self.sections:
                    block = self.section(s2, z2)
                    ref = block.find(struct.pack("<I", name_address))
                    while ref >= 0:
                        vmt = s2+ref-CLASS_NAME
                        if self.is_vmt(vmt): return vmt
                        ref = block.find(struct.pack("<I", name_address), ref+1)
                at = data.find(needle, at+1)
        raise SystemExit("Cannot find class "+name)

    def application(self, vmt):
        """Objects of that class referenced from the image's writable sections (the Application global)."""
        found = set()
        for name, start, size, flags in self.sections:
            if not flags & 0x80000000: continue                             # writable sections only
            data = self.section(start, size)
            for offset in range(0, len(data)-3, 4):
                pointer = struct.unpack_from("<I", data, offset)[0]
                if pointer > 0x10000 and not (self.low <= pointer < self.high) and self.u32(pointer) == vmt:
                    found.add(pointer)
        return sorted(found)


def neighbours(game, address, reach=0x600):
    """Objects starting near a damaged control (their VMT pointers), to tell an overflow from the block before."""
    data = game.read(address-reach, 2*reach) or b""
    out = []
    for offset in range(0, len(data)-3, 4):
        vmt = struct.unpack_from("<I", data, offset)[0]
        if game.low <= vmt < game.high and game.is_vmt(vmt):
            out.append(f"{offset-reach:+#06x} {game.class_name(vmt)}")
    return out


def scan(game, verbose=False):
    """(scanned count, problem lines, damaged control addresses)."""
    if not hasattr(game, "classes"):                         # once per game session
        game.classes = game.find_class("TControl"), game.find_class("TBasicActionLink")
        game.apps = game.application(game.find_class("TApplication"))
    (control, link), apps = game.classes, game.apps
    if not apps: raise SystemExit("Cannot find the Application object.")
    problems, seen, scanned, damaged = [], set(), 0, []

    def walk(owner, depth):
        nonlocal scanned
        components = game.u32(owner+COMPONENTS)
        if not components: return
        items, count = game.u32(components+4), game.u32(components+8)
        if items is None or count is None or count > 100000:
            problems.append(f"{game.class_name(game.u32(owner))} {game.text(game.u32(owner+NAME))!r}: unreadable component list"); return
        for index in range(count):
            item = game.u32(items+4*index)
            vmt = game.u32(item) if item else None
            if not game.is_vmt(vmt):
                problems.append(f"{game.class_name(game.u32(owner))} {game.text(game.u32(owner+NAME))!r}: component {index} at "
                                f"{item or 0:#x} is not a live object (first dword {vmt or 0:#x})")
                continue
            if item in seen: continue
            seen.add(item); scanned += 1
            if game.descends(vmt, control):
                action = game.u32(item+ACTION_LINK)
                if action and not (action & 3 == 0 and game.is_vmt(game.u32(action))
                                   and game.descends(game.u32(action), link)):
                    parent = game.u32(item+PARENT_FIELD)
                    problems.append(f"{game.class_name(vmt)} {game.text(game.u32(item+NAME))!r} at {item:#x} (owner "
                                    f"{game.class_name(game.u32(owner))} {game.text(game.u32(owner+NAME))!r}, parent "
                                    f"{game.class_name(game.u32(parent)) if parent else '-'} "
                                    f"{game.text(game.u32(parent+NAME)) if parent else ''!r}, tag "
                                    f"{game.u32(item+0xC):#x}): action link {action:#x}")
                    raw = game.read(item, 0x100) or b""
                    problems.append("  first 0x100 bytes: "+raw.hex(" ", 4))
                    problems.extend("  near: "+line for line in neighbours(game, item))
                    damaged.append(item)
            walk(item, depth+1)

    for app in apps: walk(app, 0)
    return scanned, problems, damaged


def main():
    import time
    if "--watch" not in sys.argv:
        game = Game()
        scanned, problems, _ = scan(game)
        print(f"RTW3 pid {game.pid}, module {game.module:#x}: {scanned} components scanned")
        print("\n".join(problems) if problems else "No damaged controls found.")
        return
    # --watch: wait for the game, rescan every few seconds, stop at the first damaged control (or after 4 hours).
    deadline, game, scans = time.monotonic()+4*3600, None, 0
    while time.monotonic() < deadline:
        try:
            if game is None: game = Game()
            scanned, problems, _ = scan(game); scans += 1
            if problems:
                print(time.strftime("%H:%M:%S"), f"RTW3 pid {game.pid}, module {game.module:#x}, scan {scans}, "
                      f"{scanned} components")
                print("\n".join(problems)); return
        except SystemExit:
            game = None                                      # not running (yet): wait for it
        except Exception as error:                           # the game closed mid-scan
            print(time.strftime("%H:%M:%S"), "scan failed:", error); game = None
        time.sleep(5)
    print("No damaged control seen in 4 hours.")


if __name__ == "__main__":
    main()

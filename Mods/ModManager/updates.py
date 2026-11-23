"""Auto-update from the GitHub releases of Hans21223/RTW3-Mods (adapted from the Sprocket Mod Manager's updates.py).

The newest release ZIP that has a .sha256 is offered when it is newer than this install. The download must match its
SHA-256; then it is laid over the game folder: changed files only, and files the previous release shipped that this
one no longer has are removed (Mods/ModManager/release-files.txt lists a release's files). Saves, the loader's state,
baseline and backups are never in a release, so they stay.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import urllib.request
import zipfile

VERSION = "2026.11.23"   # this release; the GitHub tag and the ZIP name carry the same number
REPO = "Hans21223/RTW3-Mods"
ASSET = r"RTW3-Mods-Beta-([\d.]+)\.zip"
MANIFEST = "Mods/ModManager/release-files.txt"


def version(text):
    parts = [int(p) for p in re.findall(r"\d+", text)][:4]
    return tuple(parts + [0]*(4-len(parts)))


def fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": "RTW3-Mod-Manager/" + VERSION})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def newest(releases, current=VERSION):
    """(version, ZIP URL, .sha256 URL, notes) of the newest release newer than `current`, or None. Pre-releases
    count (the alpha is published as one); drafts don't."""
    best = None
    for release in releases:
        if release.get("draft"):
            continue
        assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
        for name, url in assets.items():
            found = re.fullmatch(ASSET, name)
            if found and name+".sha256" in assets and version(found.group(1)) > version(best[0] if best else current):
                best = (found.group(1), url, assets[name+".sha256"], release.get("body") or "")
    return best


def check():
    return newest(json.loads(fetch(f"https://api.github.com/repos/{REPO}/releases?per_page=10")))


def download(url, sha_url):
    expected = fetch(sha_url).decode("utf-8", "replace").split()[0].lower()
    data = fetch(url, timeout=600)
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("The update didn't match its checksum, so nothing was changed. Try again later.")
    return data


def safe(name):
    """A release file: inside Mods/ (or the README), never an absolute path or a step outside the game folder."""
    path = PurePosixPath(name)
    if (path.is_absolute() or ".." in path.parts or ":" in name or "\\" in name
            or not (path.parts[0] == "Mods" or name == "README.txt")):
        raise RuntimeError(f"The update contains a file outside the mods folder ({name}), so nothing was changed.")


def replace(path, data):
    """Writes a file; one in use (the running manager's own runtime) moves aside to .old first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".new")
    temporary.write_bytes(data)
    try:
        os.replace(temporary, path)
    except PermissionError:
        aside = path.with_name(path.name + ".old")
        aside.unlink(missing_ok=True)
        os.replace(path, aside)
        os.replace(temporary, path)


def remove(path, game):
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        aside = path.with_name(path.name + ".old")
        aside.unlink(missing_ok=True)
        os.replace(path, aside)
    folder = path.parent
    # An emptied mod folder goes; Mods' own top folders (Library, Manager, ...) stay.
    while (game/"Mods") in folder.parent.parents and folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()
        folder = folder.parent


def install(data, game):
    """Lays a verified release ZIP (bytes) over the game folder. Returns (written, removed) counts."""
    game = Path(game)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = [info for info in archive.infolist() if not info.is_dir()]
        names = {info.filename for info in files}
        for name in names:
            safe(name)
        if MANIFEST not in names:
            raise RuntimeError("This isn't an RTW3 mods release, so nothing was changed.")
        listed = game/MANIFEST
        previous = set(listed.read_text(encoding="utf-8").splitlines()) if listed.is_file() else set()
        written = 0
        for info in files:
            target, content = game/info.filename, archive.read(info)
            if target.is_file() and target.stat().st_size == len(content) and target.read_bytes() == content:
                continue
            replace(target, content)
            written += 1
    dropped = sorted(name for name in previous - names if name)
    for name in dropped:
        safe(name)
        remove(game/name, game)
    return written, len(dropped)

"""One startup host with byte-range ownership, timings and read-only diagnostics.

Adapters retain their own transactions. A later adapter failure requires a game
restart; this host deliberately does not pretend to undo another adapter's state.
"""
import datetime as dt
import json
from pathlib import Path
import time

import runtime_registry as registry
import weekly_runtime as rt

REPORT = Path(__file__).with_name("runtime_host_report.json")


def write_report(path, report):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def session(pid):
    """Creation time prevents a recycled process ID from reviving an old report."""
    rt.configure_api()
    games = [(p, path.resolve()) for p, path in rt.process_candidates()
             if path.resolve() == (rt.GAME/"RTW3.exe").resolve()]
    if games != [(pid, (rt.GAME/"RTW3.exe").resolve())]:
        raise ValueError("The local game session changed. Restart through Play with mods.")
    created = rt.process_created(pid)
    base, _ = rt.module_info(pid)
    return {"pid": pid, "path": str(games[0][1]), "base": base, "created_filetime": created}


def wait_session(pid, timeout=60):
    deadline = time.monotonic() + timeout
    while True:
        try:
            return session(pid)
        except (OSError, ValueError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


class HookLedger:
    """Guard writes through rt.write_code; allow exact owner rollback only."""
    def __init__(self, writer, reader):
        self.writer, self.reader = writer, reader
        self.owner = None
        self.hooks = []

    def write(self, handle, address, original, replacement):
        size = len(original)
        if not self.owner or not size or size != len(replacement) or not 0 < address < address+size <= 0x100000000:
            raise ValueError("Invalid owned native patch.")
        overlaps = [item for item in self.hooks if address < item["address"]+item["size"] and item["address"] < address+size]
        undo = None
        if overlaps:
            item = overlaps[0]
            if (len(overlaps) == 1 and item["owner"] == self.owner and item["address"] == address
                    and item["size"] == size and item["original"] == replacement.hex()
                    and item["replacement"] == original.hex()):
                undo = item
            else:
                raise ValueError(f"Hook conflict at {address:#x}: {self.owner} overlaps {item['owner']}. No conflicting write performed.")
        item = undo or {"owner": self.owner, "address": address, "size": size,
                        "original": original.hex(), "replacement": replacement.hex()}
        if undo is None:
            self.hooks.append(item)
        # Retain an uncertain range if a native write fails part-way through.
        item["state"] = "uncertain"
        self.writer(handle, address, original, replacement)
        if self.reader(handle, address, size) != replacement:
            raise ValueError(f"Hook readback failed at {address:#x} for {self.owner}.")
        if undo:
            self.hooks.remove(undo)
        else:
            item["state"] = "active"


def verify_hooks(identity, hooks, reader=None):
    """No writable process handle, no repairs or reattachment."""
    rt.configure_api()
    handle = rt.K.OpenProcess(0x410, False, identity["pid"])
    if not handle:
        raise rt.win_error("Cannot inspect loaded hooks")
    try:
        read = reader or rt.read
        mismatches = []
        for hook in hooks:
            expected = bytes.fromhex(hook["replacement"])
            if read(handle, hook["address"], len(expected)) != expected:
                mismatches.append({"adapter": hook["owner"], "address": hook["address"]})
        return mismatches
    finally:
        rt.K.CloseHandle(handle)


def run(selected, settings, pid, *, invoker=None, session_reader=None, verifier=None, report_path=None, clock=None):
    # Preflight settings and adapter ordering before any native write.
    ordered = registry.plan(selected, settings)
    invoker = invoker or registry.invoke
    session_reader = session_reader or session
    verifier = verifier or verify_hooks
    clock = clock or time.perf_counter
    report_path = REPORT if report_path is None else report_path
    start = clock()
    report = {"schema": 1, "framework_api": registry.API_VERSION, "ok": False, "state": "attaching",
              "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "session": None,
              "plan": ordered, "adapters": [], "hooks": [], "requires_restart": False, "elapsed_ms": 0,
              "scope": "Startup hook writes only; adapter-owned allocations and game simulation are not profiled."}
    ledger = HookLedger(rt.write_code, rt.read)
    original_writer = rt.write_code
    try:
        report["session"] = session_reader(pid)
        write_report(report_path, report)
        rt.write_code = ledger.write
        for step in ordered:
            ident = step["adapter"]
            item = {"adapter": ident, "state": "attaching", "settings": step["settings"]}
            report["adapters"].append(item)
            began = clock()
            try:
                if session_reader(pid) != report["session"]:
                    raise ValueError("Game session changed during attachment.")
                ledger.owner = ident
                result = invoker(ident, step["settings"], pid)
                if not isinstance(result, dict) or not (result.get("attached") is True or result.get("ok") is True):
                    raise ValueError("Adapter did not confirm attachment: " + ident)
                if result.get("pid", pid) != pid:
                    raise ValueError("Adapter attached to a different game session: " + ident)
                item.update(state="loaded", hooks=sum(hook["owner"] == ident for hook in ledger.hooks))
            except Exception as error:
                item.update(state="failed", error=str(error))
                raise
            finally:
                item["elapsed_ms"] = round((clock()-began)*1000, 3)
                report["hooks"] = list(ledger.hooks)
                write_report(report_path, report)
        if session_reader(pid) != report["session"]:
            raise ValueError("Game session ended before final hook verification.")
        mismatches = verifier(report["session"], ledger.hooks)
        if mismatches:
            raise ValueError("Final hook readback failed: " + json.dumps(mismatches))
        report.update(ok=True, state="ready", hooks_verified=len(ledger.hooks))
    except Exception as error:
        report.update(state="failed", error=str(error), requires_restart=True)
    finally:
        rt.write_code = original_writer
        report["hooks"] = list(ledger.hooks)
        report["elapsed_ms"] = round((clock()-start)*1000, 3)
        write_report(report_path, report)
    return report


def diagnostics(selected, settings, *, report_path=None, session_reader=None, verifier=None):
    ordered = registry.plan(selected, settings)
    result = {"ok": True, "framework_api": registry.API_VERSION, "plan": ordered,
              "session_state": "no-report", "warnings": [], "last_launch": None, "mismatches": []}
    path = REPORT if report_path is None else report_path
    if not path.exists():
        result["warnings"].append("Launch through Play with mods to record startup diagnostics.")
        return result
    if path.stat().st_size > 4*1024*1024:
        raise ValueError("Runtime report is too large; inspect it before retrying.")
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved.get("schema") != 1 or saved.get("framework_api") != registry.API_VERSION:
        raise ValueError("Unsupported runtime report version.")
    result["last_launch"] = saved
    if saved.get("plan") != ordered:
        result["warnings"].append("Enabled mods/settings differ from the last launch. Restart to load the current selection.")
    identity = saved.get("session")
    if not isinstance(identity, dict) or not identity.get("created_filetime"):
        result["session_state"] = "unverified"
        result["warnings"].append("The last launch did not identify its game session.")
        return result
    try:
        current = (session_reader or session)(identity["pid"])
    except (OSError, ValueError) as error:
        result["session_state"] = "ended-or-unavailable"
        result["warnings"].append("Last launch is historical: " + str(error))
        return result
    if current != identity:
        result["session_state"] = "stale"
        result["warnings"].append("The saved report belongs to another game session.")
        return result
    result["session_state"] = "current"
    result["mismatches"] = (verifier or verify_hooks)(identity, saved.get("hooks", []))
    if result["mismatches"]:
        result["warnings"].append("Loaded hook bytes changed. Close the game when safe and restart with mods.")
    if not saved.get("ok"):
        result["warnings"].append("Last startup is incomplete or failed. Earlier adapters may remain installed; restart before playing.")
    return result

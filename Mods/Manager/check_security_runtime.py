"""Read-only startup check; never loads a campaign, advances a turn or edits a save."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/"CampaignOverhaul"))
import weekly_runtime as rt
import live_cheats as live
import campaign_security as security
import ai_runtime


def check():
    live.memory.configure(); ai_runtime.checked_game()
    saved = json.loads(security.REPORT.read_text(encoding="utf-8"))
    if not saved.get("attached") or dict(rt.process_candidates()).get(saved["pid"]) != rt.GAME/"RTW3.exe":
        raise ValueError("No current campaign-security session.")
    handle = rt.K.OpenProcess(0x410, False, saved["pid"])
    if not handle: raise rt.win_error("Cannot inspect startup")
    try:
        if rt.module_info(saved["pid"])[0] != saved["base"]: raise ValueError("The security session changed.")
        ai_runtime.verify(handle, saved["patches"], "replacement")
        for offset, factory in ((0, security.budget_thunk), (0x400, security.spy_thunk)):
            expected = factory(saved["allocation"]+offset, saved["state"], saved["details"])
            if rt.read(handle, saved["allocation"]+offset, len(expected)) != expected:
                raise ValueError("Security code page differs.")
        expected = security.yard_thunk(saved["allocation"]+0x800, saved["details"])
        if rt.read(handle, saved["allocation"]+0x800, len(expected)) != expected:
            raise ValueError("Yard guard code differs.")
        dispatcher, live_handle = live.session(saved["pid"])
        try:
            if dispatcher.get("dispatcher_version") != 2 or dispatcher["layout"].get("records_offset") != 0x1000:
                raise ValueError("Bulk dispatcher is not current.")
            ai_runtime.require_title_screen(handle, dispatcher["layout"])
        finally: rt.K.CloseHandle(live_handle)
        result = dict(ok=True, pid=saved["pid"], base=saved["base"], security_hooks=len(saved["patches"]),
                      security_code_readback=True, counterintelligence_percent=live.integer(handle, saved["state"]),
                      last_extra_cost=live.integer(handle, saved["state"]+4),
                      bulk_dispatcher_version=2, bulk_capacity=dispatcher["layout"]["max_edits"],
                      campaign_loaded=False, turns_advanced=0, personal_saves_modified=False,
                      campaign_gameplay_verified=False)
        (Path(__file__).parent/"campaign-security-validation.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
        return result
    finally: rt.K.CloseHandle(handle)


if __name__ == "__main__":
    try: print(json.dumps(check()))
    except (OSError, ValueError) as error:
        print(json.dumps(dict(ok=False, message=str(error)))); raise SystemExit(1)

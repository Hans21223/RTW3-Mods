"""Read-only x86 boundary checks for the discovered native campaign end gate."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/"vendor"))
sys.path.insert(0,str(HERE.parent/"CampaignOverhaul"))
import weekly_runtime as rt
import timeline_2030 as timeline
from test_timeline_2030 import TimelineTests


def main():
    rt.configure_api()
    saved=json.loads(timeline.REPORT.read_text(encoding="utf-8"))
    if dict(rt.process_candidates()).get(saved["pid"]) != rt.GAME/"RTW3.exe":
        raise ValueError("The inspected game session ended.")
    handle=rt.K.OpenProcess(0x410,False,saved["pid"])
    if not handle: raise rt.win_error("Cannot inspect local game")
    try:
        module_base,_=rt.module_info(saved["pid"])
        if module_base != saved["base"]: raise ValueError("Game session changed.")
        base,blob=rt.text_section(handle,module_base)
        original=bytearray(blob)
        for item in saved["patches"]:
            expected=bytes.fromhex(item["replacement"] if saved["attached"] else item["original"])
            if rt.read(handle,item["address"],len(expected)) != expected:
                raise ValueError("Runtime bytes do not match the timeline report.")
            at=item["address"]-base
            original[at:at+len(expected)]=bytes.fromhex(item["original"])
        plans,_=timeline.discover(bytes(original),base,saved["end_offer_year"])
        # the end gate comes first; year tables, start years and month records follow (each read back above)
        if plans != saved["patches"][:len(plans)]: raise ValueError("Native discovery and attachment differ.")
        tests=TimelineTests()
        rows=[]
        for year in (1890,1900,1970,1989,1990,2000,2029,2030,2031,2050,2051,2100):
            row={"year":year,"vanilla_playable":bool(tests.run_gate(bytes.fromhex(plans[0]["original"]),year)),
                 "extended_playable":bool(tests.run_gate(bytes.fromhex(plans[0]["replacement"]),year))}
            if row["vanilla_playable"] != (year<1990) or row["extended_playable"] != (year<=saved["last_playable_year"]):
                raise ValueError("Native year boundary check failed.")
            rows.append(row)
        report={"ok":True,"pid":saved["pid"],"native_patches_verified":len(saved["patches"]),"year_boundaries":rows,
                "read_only_process_access":True,"personal_saves_modified":False,"full_campaign_gameplay_tested":False}
        output=HERE/"timeline-runtime-test.json"
        output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report))
    finally: rt.K.CloseHandle(handle)


if __name__=="__main__": main()

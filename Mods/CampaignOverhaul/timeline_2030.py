"""Allow campaign turns through 2030 without altering the executable on disk.

This is a calendar/end-check extension, not an implementation of modern weapons.
"""
import argparse
import json
from pathlib import Path
import re
import struct
import time
import weekly_runtime as rt
from hull_rules import patch, unique

REPORT = Path(__file__).with_name("timeline_2030_report.json")
END_YEAR = 2030
NOTICE = "It is the end of year 1970. The game is over!"
CONTINUE = ("The regular game is over! If you want to, you can continue playing, but technical "
            "development will level out. There will be a hard cutoff at 1990.")
REFERENCE = 0x301000
# Year switches (case statements on the campaign or a design year) whose last range ends in 1991-2001. The
# native campaign stops in 1990; later years fell into each switch's default branch, the value for years
# before the table: aircraft development time 12 -> 6 months, colonial income 4 -> 25 per value point,
# peacetime maintenance x1.25 -> x1, AI build odds, tech adjustments, design weights and battle rules reset.
# Each entry: the chain's first ADD/SUB, its bytes through the last range's Jcc, the offset of that range's
# SUB reg,imm8 and its first year. The last range is stretched past the campaign: its imm8 when 127 years
# reach, otherwise a jump to SUB reg,imm32 in a small code cave. Years before 1991 keep their native branch.
YEAR_TABLES = (
    (0x6289B2, "056cf8ffff83e806724d83e80a725b83e805726983e8277277", 20, 1961),   # bnOKClick
    (0x650F89, "0585f8ffff83e819721a83e80b721c83e831721e", 15, 1951),   # GetWpDistText
    (0x6A7343, "056bf8ffff83e806724b83e80a724f83e82b7253", 15, 1957),   # NationIdx1Click
    (0x6B03EB, "0565f8ffff83e8040f828c00000083e8050f828b00000083e8050f828a00000083e8270f8289000000", 32, 1961),
    (0x6B3491, "057ff8ffff83e805725783e809726a83e841727d", 15, 1935),
    (0x6BCD83, "059ef8ffff83e81e720783e8507212", 10, 1920),
    (0x6C4200, "0588f8ffff83e802724183e802724883e803724f83e8487256", 20, 1919),
    (0x6C45B2, "058ef8ffff83e803722483e804722b83e8577232", 15, 1913),
    (0x6C465D, "0588f8ffff83e802724183e802724883e803724f83e8517256", 20, 1919),
    (0x6C4938, "0584f8ffff83e803725483e80c725883e83c725c", 15, 1931),
    (0x71F87B, "0557f8ffff83e805725483e805726683e81d7278", 15, 1971),   # GetTotalMonthlyMaintenanceCost
    (0x72C517, "055ff8ffff83e808721483e805721283e8227212", 15, 1966),   # GetSubBuildTime
    (0x7350DD, "2d93070000720c83e807721a83e8367228", 12, 1946),   # GetTotalNavalAirCost
    (0x735916, "0553f8ffff83e804723283e807724083e818724e", 15, 1976),   # ApplyAirMaintenanceModifiers
    (0x739024, "81c27af8ffff83ea05723383ea05723483ea407235", 16, 1936),   # SetArmorModifierForYear
    (0x74AED0, "059ef8ffff83e829720c83e80f720e83e8367210", 15, 1946),   # ReduceTimeLimits
    (0x74B01A, "057ff8ffff83e80a721a83e80a721c83e83b721e", 15, 1941),   # ReduceTimeLimits
    (0x774F1D, "059ef8ffff83e80b721183e805721583e805721783e859721b", 20, 1911),   # AIBuildInitialCA
    (0x774F5D, "058ef8ffff83e802720c83e802721583e85a721e", 15, 1910),   # AIBuildInitialCA
    (0x77E983, "0594f8ffff83e807721183e80e722183e80f723183e8407241", 20, 1936),   # AIBuildShip
    (0x7C6493, "0571f8ffff83e80a722783e806722b83e831722f", 15, 1951),   # CheckForceOnForeignStations
    (0x7DDE5C, "0583f8ffff83e802724783e806724883e80b724983e837724a", 20, 1936),   # GetDesiredSpeedPerYear
    (0x7DE8B0, "2da00700000f84870000004883e82f0f8283000000", 12, 1953),   # GetPossessionMultiplier
    (0x7DF221, "0592f8ffff83e805721183e80c721083e80c721a83e83c721a", 20, 1931),   # AdjustTechs
    (0x7DF2A1, "057df8ffff83e806721983e80c721983e83b7219", 15, 1941),   # AdjustTechs
    (0x7DF322, "056af8ffff83e805721483e809721483e82c7214", 15, 1956),   # AdjustTechs
    (0x7DF42F, "81c188f8ffff83e909722483e90a722783e9457229", 16, 1931),   # AdjustTechs
    (0x7EC520, "0557f8ffff83e805722d83e805722f83e80a723183e8137233", 20, 1981),   # CheckAircraftDevelopment
    (0x7EC8AA, "055cf8ffff83e805721b83e814721b83e813721b", 15, 1981),   # CheckAircraftDevelopment
    (0x7ED0DF, "0570f8ffff83e805722683e805722883e805722a83e831722c", 20, 1951),   # GetAircraftDevelopmentTime
    (0x7F5DAA, "057ff8ffff83e80a721e83e80a722283e83b7226", 15, 1941),   # CheckForPrivateShipbuildingExpansion
    (0x813A5D, "81c188f8ffff83e902722183e902722383e94b7225", 16, 1916),   # GetStrenghPointsForShip
    (0x813B96, "0575f8ffff83e805722683e805722883e805722a83e836722c", 20, 1946),   # GetStrenghPointsForShip
    (0x813C29, "0575f8ffff83e805722683e805722883e805722a83e836722c", 20, 1946),   # GetStrenghPointsForShip
    (0x816BD4, "0566f8ffff83e80a721e83e80a721f83e8227220", 15, 1966),   # TensionChangeWithMessage
    (0x864D84, "058af8ffff83e802724883e802724d83e8567252", 15, 1914),   # Status1Click
    (0x865000, "058af8ffff83e802725c83e802726183e8567266", 15, 1914),   # Status1Click
    (0x866C40, "05c6f8ffff83e84d721183e80a721583e807721983e838721d", 20, 1944),   # GetDistanceToClosestEnemyShipFromPoint
    (0x86B95F, "0575f8ffff83e805725083e805725f83e802726e83e839727d", 20, 1943),
    (0x886246, "057af8ffff83e80d722183e809722383e8347225", 15, 1948),   # richLogMouseUp
    (0x888059, "058bf8ffff83e802724283e802724683e857724a", 15, 1913),   # bnFireClick
    (0x88886B, "058ef8ffff83e804722c83e804723083e802723483e8547238", 20, 1916),   # bnFireClick
    (0x88A637, "0579f8ffff83e807723683e807723783e83b7238", 15, 1941),   # bnFireClick
    (0x88B709, "058ef8ffff83e804722c83e804723083e802723483e8547238", 20, 1916),
    (0x88EB84, "058bf8ffff83e805722783e807722b83e84f722f", 15, 1921),
    (0x88EC76, "059ef8ffff83e80b720c83e80a721083e8597214", 15, 1911),
    (0x89128D, "058af8ffff83e804722783e80f722b83e847722f", 15, 1929),
    (0x8BDC2B, "0575f8ffff83e80a722183e80a722383e8317225", 15, 1951),   # bnTestClick
    (0x8D01D2, "81c26bf8ffff83ea05723683ea05723883ea31723a", 16, 1951),   # DrawTempSearchSector
    (0x8D1DD8, "0589f8ffff83e813721883e80a721983e83c721a", 15, 1940),   # GetdistancetoClosestEnemyBase
    (0x90E127, "0576f8ffff83e806721183e805720f83e805720f83e836720f", 20, 1946),   # ChangeSpeed
    (0x9185DB, "81c383f8ffff83eb03722a83eb03722f83eb4e7234", 16, 1923),   # IsAging
    (0x939A7E, "057af8ffff83e8080f82c500000083e8070f82d700000083e83b0f82e9000000", 23, 1941),   # RecomputeValues
    (0x93A05C, "0575f8ffff83e80a726783e80a727d83e8310f828f000000", 15, 1951),   # RecomputeValues
    (0x93B78B, "057df8ffff83e80d720c83e80a721c83e836722c", 15, 1946),   # GetResults
    (0x93C815, "057df8ffff83e80e720c83e809722483e836723c", 15, 1946),   # GetArmamentWeights
    (0x945B58, "0583f8ffff83e804721183e80a722783e814723d83e8317253", 20, 1951),   # LoadMe
    (0x9464FA, "057af8ffff83e807723683e818723883e82b723a", 15, 1957),   # ComputeAmmoWeight
    (0x95282D, "057ff8ffff83e808722383e809722483e807722583e8377226", 20, 1945),   # IsSubmerged
    (0x9534DD, "81ea88070000721183ea0c721283ea0a721383ea327214", 18, 1950),   # IsSubmerged
    (0x95835C, "81c673f8ffff83ee07727d83ee140f828500000083ee280f828d000000", 20, 1960),
    (0x958494, "81c664f8ffff83ee080f82bd00000083ee070f82c500000083ee250f82cd000000", 24, 1963),
    (0x9585BE, "81c683f8ffff83ee0a724783ee17725383ee0a725f83ee28726b", 21, 1960),
    (0x9586E3, "055ef8ffff83e8070f829b00000083e8040f82a000000083e8230f82a5000000", 23, 1965),
    (0x958881, "0562f8ffff83e8080f82da00000083e8070f82e200000083e8230f82ea000000", 23, 1965),
    (0x9589DD, "81c675f8ffff83ee0b724783ee12725383ee05725f83ee23726b", 21, 1965),
    (0x958A99, "81c66ef8ffff83ee07723183ee06723d83ee317249", 16, 1951),
    (0x958B2E, "81c66df8ffff83ee06723183ee0a723d83ee2d7249", 16, 1955),
    (0x975A07, "056af8ffff83e803722783e810722b83e827722f", 15, 1961),   # StartLaunchProcess
    (0x979840, "0570f8ffff83e806721a83e809721c83e831721e", 15, 1951),   # RandomizeTargetPoint
    (0x97B713, "0594f8ffff83e82e721183e80a721283e809721383e8237214", 20, 1965),   # RandomizeTargetPoint
)
YEAR_MARGIN = 10   # research-speed-adjusted years run a little ahead of the calendar


def discover(blob, base, end_year=END_YEAR, cutoff_year=None):
    """end_year: December end offer (native 1970). cutoff_year: forced stop (native 1990)."""
    cutoff_year = end_year+1 if cutoff_year is None else cutoff_year
    # Four-digit years keep both native notices at their original lengths.
    if not 1890 <= end_year < cutoff_year <= 9999:
        raise ValueError("The end-offer year must come before the cutoff year, both from 1890 to 9999.")
    function = rt.method_address(blob, base, "CheckEndOfGame")
    start = function-base
    body = blob[start:start+0x180]
    # Original forced stop: (year - 1900) > 89. Do not encode 130 as a signed
    # imm8: that would turn the comparison negative. Compare the full year.
    old = b"\x2d\x6c\x07\x00\x00\x83\xf8\x59"
    gate = unique(body, old, "native 1990 cutoff")
    if body[gate+len(old):gate+len(old)+1] != b"\x7e":
        raise ValueError("Unsupported forced-end branch.")
    plans = [patch(f"Campaign allowed through {cutoff_year-1}", function+gate, old,
                   b"\x3d"+struct.pack("<I", cutoff_year-1)+b"\x90"*3)]
    year_load = list(re.finditer(rb"\xa1(.{4})\x8b\x00"+re.escape(old), body, re.DOTALL))
    if len(year_load) != 1: raise ValueError("Cannot verify native end-year source.")
    year_slot, = struct.unpack("<I", year_load[0].group(1))
    soft = b"\xa1"+struct.pack("<I", year_slot)+b"\x81\x38\xb2\x07\x00\x00"
    off = unique(body, soft, "native 1970 end-year offer")
    if body[off+len(soft):off+len(soft)+2] != b"\x0f\x85":
        raise ValueError("Unsupported end-year offer branch.")
    plans.append(patch(f"End-year offer in December {end_year}", function+off+7,
                       struct.pack("<I",1970),struct.pack("<I",end_year)))
    for text, replacement in ((NOTICE, NOTICE.replace("1970",str(end_year))),
                              (CONTINUE, CONTINUE.replace("1990",str(cutoff_year)))):
        encoded, changed = text.encode("utf-16-le"), replacement.encode("utf-16-le")
        at = unique(blob, encoded+b"\0\0", "native end notice")
        if struct.unpack_from("<I",blob,at-4)[0] != len(text):
            raise ValueError("Unsupported native Unicode end notice.")
        pointer = struct.pack("<I",base+at)
        if b"\xba"+pointer not in body:
            raise ValueError("End notice is not owned by verified campaign end check.")
        plans.append(patch(f"{end_year} end notice" if text==NOTICE else f"{cutoff_year} cutoff notice",
                           base+at,encoded,changed))
    return plans, year_slot


def year_tables(blob, base, last_year, cave=None):
    """Plans (and the code for cave) that keep each YEAR_TABLES switch in its last range through
    last_year+YEAR_MARGIN. Nothing when the campaign stops by 1990."""
    if last_year <= 1990: return [], b""
    horizon, delta, plans, code = last_year+YEAR_MARGIN, base-REFERENCE, [], bytearray()
    for address, chain, sub_off, start in YEAR_TABLES:
        at, old = address+delta, bytes.fromhex(chain)
        if blob[at-base:at-base+len(old)] != old:
            raise ValueError(f"Unsupported native year table at {address:#x}.")
        site, modrm, jcc = at+sub_off, old[sub_off+1], old[sub_off+3:]
        label = f"Year table at {address:#x}: {start} range continues"
        if start+126 >= horizon:
            plans.append(patch(label, site+2, old[sub_off+2:sub_off+3], b"\x7f"))
            continue
        if cave is None: raise ValueError("Year tables need a code cave.")
        after = site+3+len(jcc)
        target = after+(struct.unpack("<b", jcc[1:2])[0] if jcc[0] == 0x72 else struct.unpack("<i", jcc[2:6])[0])
        here = cave+len(code)
        code += b"\x81"+bytes([modrm])+struct.pack("<I", horizon+1-start)              # SUB reg,imm32
        code += b"\x0f\x82"+struct.pack("<i", target-(here+12))+b"\xe9"+struct.pack("<i", after-(here+17))
        plans.append(patch(label, site, old[sub_off:sub_off+3+len(jcc)],
                           b"\xe9"+struct.pack("<i", here-(site+5))+b"\x90"*(len(jcc)-2)))
    return plans, bytes(code)


def native_year_bytes(normalized):
    """Undo the year-table changes in a normalized .text copy, so other adapters' audited windows still match
    when this adapter attached first."""
    for address, chain, sub_off, _ in YEAR_TABLES:
        old = bytes.fromhex(chain)
        at, size = address-REFERENCE+sub_off, len(old)-sub_off
        if normalized[at+2] == 0x7f or normalized[at] == 0xe9:
            normalized[at:at+size] = old[sub_off:sub_off+size]
    return normalized


def attach(wait=30, end_year=END_YEAR, cutoff_year=None):
    rt.configure_api()
    deadline = time.monotonic()+wait
    while True:
        games = [g for g in rt.process_candidates() if g[1] == rt.GAME/"RTW3.exe"]
        if len(games)==1: break
        if time.monotonic()>=deadline: raise ValueError("Open the local game first.")
        time.sleep(0.5)
    pid,_ = games[0]
    handle = rt.K.OpenProcess(0x438,False,pid)
    if not handle: raise rt.win_error("Cannot open local game")
    try:
        module_base,_ = rt.module_info(pid)
        if REPORT.exists():
            saved=json.loads(REPORT.read_text(encoding="utf-8"))
            if saved.get("attached") and saved.get("pid")==pid and saved.get("base")==module_base and rt.report_is_current(REPORT,pid):
                verify_patches(handle,saved["patches"],"replacement")
                return saved
        while True:
            try:
                base,blob=rt.text_section(handle,module_base)
                plans,year_slot=discover(blob,base,end_year,cutoff_year)
                break
            except (OSError,ValueError):
                if time.monotonic()>=deadline: raise
                time.sleep(0.5)
        stop=cutoff_year or end_year+1
        cave=rt.K.VirtualAllocEx(handle,None,0x1000,0x3000,0x40) if stop-1>1990 else None
        if stop-1>1990 and not cave: raise rt.win_error("Cannot allocate the year-table code")
        tables,code=year_tables(blob,base,stop-1,cave)
        if code:
            import week_display as memory
            memory.configure(); memory.write(handle,cave,code); rt.K.FlushInstructionCache(handle,cave,len(code))
        starts,start_page,start_years=start_year_plans(handle,blob,base)
        records,records_table=month_record_plans(handle,blob,base) if stop-1>1990 else ([],None)
        plans=plans+tables+starts+records
        verify_patches(handle,plans,"original")
        applied=[]
        try:
            for item in plans:
                rt.write_code(handle,item["address"],bytes.fromhex(item["original"]),bytes.fromhex(item["replacement"]))
                applied.append(item)
            verify_patches(handle,plans,"replacement")
            saved={"pid":pid,"base":module_base,"attached":True,"patches":plans,"year_slot":year_slot,
                   "year_tables_extended":len(tables),"year_table_code":cave,
                   "end_offer_year":end_year,"last_playable_year":stop-1,"forced_stop_year":stop,
                   "start_years":start_years,"start_year_code":start_page,"month_records_table":records_table,
                   "modern_weapons_implemented":False,"long_campaign_gameplay_verified":False,
                   "personal_saves_modified":False}
            REPORT.write_text(json.dumps(saved,indent=2)+"\n",encoding="utf-8")
            return saved
        except Exception:
            for item in reversed(applied):
                rt.write_code(handle,item["address"],bytes.fromhex(item["replacement"]),bytes.fromhex(item["original"]))
            raise
    finally: rt.K.CloseHandle(handle)


def start_year_plans(handle, blob, base):
    """Later start years (start_years.py): (plans, code page, years), or ([], None, why not) on other game code,
    so the calendar never depends on them."""
    import start_years
    try:
        info = start_years.discover(blob, base)
    except ValueError as error:
        return [], None, str(error)
    page = rt.K.VirtualAllocEx(handle, None, 0x3000, 0x3000, 0x40)
    if not page: raise rt.win_error("Cannot allocate the start-year code")
    blocks, plans = start_years.build(page, info)
    import start_fleets   # historical starting fleets, in the two pages after
    try:
        fleet_blocks, fleet_plans = start_fleets.build(page+0x1000, start_fleets.discover(blob, base))
        blocks += fleet_blocks; plans += fleet_plans
    except ValueError:
        pass   # other game code: the native fleet builder stays
    import week_display as memory
    memory.configure()
    for block in blocks: memory.write(handle, block["address"], bytes.fromhex(block["bytes"]))
    rt.K.FlushInstructionCache(handle, page, 0x3000)
    return plans, page, list(start_years.YEARS)


def month_record_plans(handle, blob, base):
    """The month-record table moved out of the campaign window for years past 1990 (month_records.py) into a new,
    zeroed allocation: (plans, table). Nothing is copied: at the title screen no campaign is loaded, and the records
    hold strings that the window's own cleanup still owns. A campaign past 1990 needs it, so failures raise."""
    import month_records as records
    info = records.discover(blob, base)
    main = struct.unpack("<I", rt.read(handle, info["main"], 4))[0]
    if not main or struct.unpack("<I", rt.read(handle, main, 4))[0] != info["vmt"]:
        raise ValueError("The campaign window does not exist yet.")
    page = rt.K.VirtualAllocEx(handle, None, records.ALLOCATION, 0x3000, 0x04)
    if not page: raise rt.win_error("Cannot allocate the month records")
    return records.plans(info, main, page+records.MARGIN), page+records.MARGIN


def verify_patches(handle,plans,key):
    for item in plans:
        expected=bytes.fromhex(item[key])
        if rt.read(handle,item["address"],len(expected)) != expected:
            raise ValueError("The timeline attachment changed; operation refused.")


def detach():
    rt.configure_api()
    saved=json.loads(REPORT.read_text(encoding="utf-8"))
    if not saved.get("attached"): return saved
    if dict(rt.process_candidates()).get(saved["pid"]) != rt.GAME/"RTW3.exe":
        raise ValueError("The attached game session ended.")
    handle=rt.K.OpenProcess(0x438,False,saved["pid"])
    if not handle: raise rt.win_error("Cannot open local game")
    try:
        if rt.module_info(saved["pid"])[0] != saved["base"]: raise ValueError("Game session changed.")
        verify_patches(handle,saved["patches"],"replacement")
        for item in reversed(saved["patches"]):
            rt.write_code(handle,item["address"],bytes.fromhex(item["replacement"]),bytes.fromhex(item["original"]))
        verify_patches(handle,saved["patches"],"original")
        saved["attached"]=False
        REPORT.write_text(json.dumps(saved,indent=2)+"\n",encoding="utf-8")
        return saved
    finally: rt.K.CloseHandle(handle)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("attach","detach"))
    parser.add_argument("--settings",default="{}",help='JSON mod.json settings, for example {"end_year": 1950}')
    args=parser.parse_args()
    try: print(json.dumps(attach(**json.loads(args.settings)) if args.command=="attach" else detach()))
    except (OSError,ValueError,TypeError) as error:
        print(json.dumps({"ok":False,"message":str(error)})); raise SystemExit(1)

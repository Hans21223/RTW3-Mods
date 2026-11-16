"""Post-1970 aircraft performance rows for the modern research package.

The native lookup reads Data/AircraftBasicData3.dat by type and year: the row for
that year or the year before, else the last row plus 1%. Vanilla rows stop in
1970, so later prototypes stay 1970 aircraft. This appends a row every two years
to 2030, interpolating between historical anchors (F-16/F/A-18, F-14/F-15/F-22,
A-7 to F-35C strike, SH-60/NH90, Tu-22M class). Native parser columns: 1 max
speed (mph), 2 cruise, 5-7 endurance in minutes (light/medium/heavy load),
8 firepower, 9 manoeuvrability, 10 toughness, 14-16 bomb loads. Other columns
repeat the 1970 row.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE/"vanilla/AircraftBasicData3.dat"
PACKAGE = HERE.parent/"Library/timeline-2030"   # merged Expanded Timeline package
YEARS = range(1972, 2031, 2)
# Section -> column -> {year: value}; the 1970 value comes from the vanilla row.
ANCHORS = {
    "LIGHT JET FIGHTER": {1: {1980: 1250, 1990: 1300, 2005: 1320}, 2: {1980: 560, 2000: 590, 2030: 610},
                          5: {1980: 190, 2000: 210, 2030: 230}, 6: {1980: 160, 2000: 175, 2030: 190},
                          7: {1980: 125, 2000: 140, 2030: 150}, 8: {1980: 21, 1990: 24, 2005: 27, 2030: 30},
                          9: {1980: 19, 1990: 21, 2010: 23, 2030: 24}, 10: {1980: 15, 2000: 16, 2030: 17},
                          14: {1980: 5, 2000: 6, 2030: 7}, 15: {1980: 9, 2000: 11, 2030: 12},
                          16: {1980: 16, 2000: 18, 2030: 20}},
    "HEAVY JET FIGHTER": {1: {1980: 1450, 1990: 1500}, 2: {1980: 570, 2005: 650, 2030: 700},
                          5: {1980: 240, 2000: 260, 2030: 280}, 6: {1980: 200, 2000: 215, 2030: 230},
                          7: {1980: 165, 2000: 180, 2030: 190}, 8: {1980: 23, 1990: 26, 2005: 30, 2030: 32},
                          9: {1980: 17, 1990: 19, 2005: 21, 2030: 22}, 10: {1980: 17, 2000: 18, 2030: 19},
                          14: {1980: 8, 2000: 9, 2030: 10}, 15: {1980: 16, 2000: 18, 2030: 20},
                          16: {1980: 30, 2000: 34, 2030: 36}},
    "JET ATTACK": {1: {1980: 780, 1990: 1000, 2000: 1100, 2030: 1200}, 2: {1990: 520, 2000: 540, 2030: 570},
                   5: {1990: 260, 2030: 290}, 6: {1990: 215, 2030: 240}, 7: {1990: 180, 2030: 200},
                   9: {1990: 13, 2030: 16}, 10: {2000: 18, 2030: 20},
                   14: {1990: 11, 2030: 13}, 15: {1990: 22, 2030: 26}, 16: {1990: 42, 2030: 48}},
    "HELICOPTER": {1: {1980: 180, 2000: 185, 2030: 200}, 2: {1980: 125, 2000: 135, 2030: 145},
                   5: {2030: 320}, 6: {1980: 250, 2030: 270}, 8: {1980: 3, 2000: 4},
                   9: {2000: 9}, 10: {1990: 8, 2030: 9}},
    "MEDIUM BOMBER": {1: {1980: 900, 1990: 1100, 2030: 1150}, 2: {1990: 560, 2030: 600},
                      5: {2030: 780}, 6: {2030: 650}, 7: {2030: 540}, 8: {2000: 9},
                      10: {2000: 15, 2030: 16}, 14: {2030: 8}, 15: {2030: 16}, 16: {2030: 32}},
}


# Stealth models (modern_sensors names the section for prototypes developed from
# 1990 by a nation with the stealth tech): the same jet with internal weapon bays
# and shaping. Column -> percent of the normal model's value, or +points.
STEALTH_YEARS = range(1990, 2031, 2)
STEALTH = {"LIGHT JET FIGHTER": "STEALTH LIGHT JET FIGHTER", "HEAVY JET FIGHTER": "STEALTH HEAVY JET FIGHTER",
           "JET ATTACK": "STEALTH JET ATTACK"}
STEALTH_PERCENT = {1: 95, 14: 75, 15: 75, 16: 75}   # speed; light/medium/heavy bomb loads
STEALTH_PLUS = {8: 2, 10: 1}                          # firepower (first look), toughness
# Unmanned strike aircraft (X-47B, MQ-25 class): the stealth jet attack without a pilot. No cockpit and no
# crew endurance limit: half as long again in the air; a remote pilot dogfights worse.
UCAV, UCAV_YEARS = "UNMANNED JET ATTACK", range(2020, 2031, 2)
# Shipborne UAVs (ScanEagle 2005; Fire Scout MQ-8B 2009, MQ-8C 2014 with a search radar): from the floatplane scout's
# last row, slower, two to three times the endurance (minutes, three loads), radar (R), no bombs, a weak target.
UAV, UAV_YEARS = "SHIPBORNE UAV", range(2004, 2031, 2)
UAV_ANCHORS = {1: {2004: 120, 2014: 140, 2030: 150}, 2: {2004: 85, 2014: 115, 2030: 125},
               5: {2004: 600, 2014: 720, 2030: 900}, 6: {2004: 540, 2014: 660, 2030: 840},
               7: {2004: 480, 2014: 600, 2030: 780}, 8: {2004: 1}, 9: {2004: 4}, 10: {2004: 3}}
UAV_FIXED = {14: "-", 15: "-", 16: "-", 19: "R"}
UCAV_PERCENT = {5: 150, 6: 150, 7: 150, 9: 80}      # endurance (three loads), manoeuvrability


def value(points, year):
    """Linear between anchors, constant after the last one."""
    years = sorted(points)
    if year >= years[-1]: return points[years[-1]]
    upper = next(y for y in years if y >= year)
    lower = max(y for y in years if y <= year)
    if upper == lower: return points[upper]
    return round(points[lower]+(points[upper]-points[lower])*(year-lower)/(upper-lower))


def render(raw=None):
    raw = BASELINE.read_bytes() if raw is None else raw
    lines = raw.decode("ascii").split("\r\n")
    output, section, extended = [], None, set()
    for index, line in enumerate(lines):
        output.append(line)
        if line.startswith("["): section = line[1:-1]
        nxt = lines[index+1] if index+1 < len(lines) else ""
        if section in ANCHORS and line.startswith("1970;") and nxt.startswith("["):
            base = line.split(";"); extended.add(section)
            for year in YEARS:
                fields = [str(year)]+base[1:]
                for column, points in ANCHORS[section].items():
                    start = int(base[column])   # anchored columns are numeric in 1970
                    fields[column] = str(value({1970: start, **points}, year))
                output.append(";".join(fields))
    if extended != set(ANCHORS):
        raise ValueError("Unsupported aircraft data layout.")
    rows = {}
    for line in output:
        if line.startswith("["): section = line[1:-1]
        elif line[:4].isdigit(): rows[section, int(line[:4])] = line.split(";")
    end = output.index("[END]")
    stealth = []
    for base_section, name in STEALTH.items():
        stealth.append(f"[{name}]")
        for year in STEALTH_YEARS:
            fields = list(rows[base_section, year])
            for column, percent in STEALTH_PERCENT.items():
                fields[column] = str(int(fields[column])*percent//100)
            for column, plus in STEALTH_PLUS.items():
                if fields[column] != "-": fields[column] = str(int(fields[column])+plus)
            stealth.append(";".join(fields))
    stealth.append(f"[{UCAV}]")
    manned = {line.split(";")[0]: line.split(";") for line in stealth[stealth.index("[STEALTH JET ATTACK]")+1:-1]}
    for year in UCAV_YEARS:
        fields = list(manned[str(year)])
        for column, percent in UCAV_PERCENT.items(): fields[column] = str(int(fields[column])*percent//100)
        stealth.append(";".join(fields))
    stealth.append(f"[{UAV}]")
    scout = rows["FLOATPLANE SCOUT", max(y for s, y in rows if s == "FLOATPLANE SCOUT")]
    for year in UAV_YEARS:
        fields = [str(year)]+scout[1:]
        for column, points in UAV_ANCHORS.items(): fields[column] = str(value(points, year))
        for column, text in UAV_FIXED.items(): fields[column] = text
        stealth.append(";".join(fields))
    output[end:end] = stealth
    return "\r\n".join(output).encode("ascii")


def build():
    payload = render()
    target = PACKAGE/"Files/Data/AircraftBasicData3.dat"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {"sections": sorted(ANCHORS)+sorted(STEALTH.values())+[UCAV, UAV], "years": [YEARS[0], YEARS[-1]],
            "sha256": hashlib.sha256(payload).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(build()))

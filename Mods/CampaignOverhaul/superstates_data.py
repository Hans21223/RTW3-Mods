"""The 2000 start: ten fictional blocs (superstates) in the game's ten nation slots.

Writes, for the Expanded Timeline package:
- Data/BNat2000.dat and Data/MapData2000.dat (nations and possession owners, like the other later starts), from
  the historical 2000 state in start_years_data.py;
- Data/<bloc>WarInfo20.dat and WarInfo.dat (battles against eight other blocs), <bloc>Names.txt (officers),
  <bloc>ShipNames20.dat and ShipNames.dat (ship and aircraft names): the game keys these files by nation name, which
  is why every bloc has a new name, the three unchanged powers too (their native war files name Germany, Japan...);
- Flags/<bloc flag>.bmp.

A home area is a possession of value 200 (GetHomeProvince). Each bloc has one, which Campaign QoL keeps closed to
invasion; its other big regions are worth less and can be invaded. The base map's Optional home areas (Turkey,
Persia, Northern and Southern China, Argentina, Brazil) are used.
A campaign holds nine nations: the player and the eight enemies its war file names (DisplayNationInfo). Asian
players' files leave out the South American Union, the others' the Southeast Asian Union, so that bloc exists
only when an Asian bloc is played; its land is neutral otherwise.

Run:  python superstates_data.py <game folder> <package Files folder> [flag picture folder]
"""
from pathlib import Path
import re
import sys

import start_years_data as years
import superstates_names as pools

YEAR = 2000
# Economies: members' summed output (PPP, 2000) against the United States' 100,000; GGP=1 (1% more growth a year)
# for the fast-growing ones.
GROWING = ("People's Republic of China", "India", "Southeast Asian Union")
ASIAN = ("India", "Southeast Asian Union", "East Asian Federation", "People's Republic of China")
# What a bloc's regions other than its home area are worth (native home regions are 200, big colonies 10-40).
VALUES = {"United Kingdom": 100, "Western France": 100, "Northwestern Spain": 40, "Italian West Coast": 80,
          "Southern France": 60, "Eastern Spain": 40, "Italian East Coast": 40, "Eastern Germany": 60,
          "Austria-Hungary": 40, "Southeastern seaboard": 80, "Gulf coast": 80, "Western USA": 100,
          "Russian Far East": 60, "Southern China": 100, "Southern Korea": 80, "Singapore": 40, "The Philippines": 40,
          "Persia": 80, "Egypt": 60, "Nigeria": 40, "Kenya": 20, "Argentina": 60, "Chile": 30, "India": 200}
ENGLISH_RANKS = dict(AdmiralRank="Admiral", AirUnitName="Squadron",
                     OfficerRankName0="Commander", OfficerRankAbbreviation0="Cdr",
                     OfficerRankName1="Captain", OfficerRankAbbreviation1="Capt",
                     OfficerRankName2="Rear Admiral", OfficerRankAbbreviation2="RAdm",
                     OfficerRankName3="Admiral", OfficerRankAbbreviation3="Adm")
# Sea points for battles: (name, longitude, latitude), east and north positive.
# slot nation (BNat2000 section): bloc.
BLOCS = {
    "Germany": dict(
        name="European Union", adjective="European", flag="EuropeanUnion.bmp", government=0, leader="President",
        parliament="the European Parliament", admiral="Di Paola", resources=74000, budget=6, dock=70000,
        area="Northern Europe", trouble="in the Balkans", friend="United States", enemies=(),
        neighbours=("Norway", "Iceland", "Albania"),
        home=("Germany",),
        other=("United Kingdom", "Western France", "Northwestern Spain", "Italian West Coast", "Southern France",
               "Eastern Spain", "Italian East Coast", "Eastern Germany", "Austria-Hungary", "Ireland", "Malta", "Cyprus", "Gibraltar", "Sardinia", "Corsica", "Sicily", "Greece", "Rhodes", "Finland",
               "Baltic States", "Antilles", "New Caledonia", "Polynesia", "Falkland Islands", "Bermuda", "Macedonia",
               "Crete", "The Netherlands", "ABC Islands"),
        sea=(("North Sea", 3.0, 56.0), ("Bay of Biscay", -6.0, 46.0), ("Western Mediterranean", 5.0, 39.0),
             ("Ionian Sea", 18.0, 36.5)), names="merge"),
    "Austria-Hungary": dict(
        name="India", adjective="Indian", flag="IndiaNavy.bmp", government=0, leader="Prime Minister",
        parliament="the Lok Sabha", admiral="Prakash", resources=17000, budget=6, dock=45000,
        area="Indian Ocean", trouble="in Kashmir", friend="Russian Federation", enemies=("People's Republic of China",),
        neighbours=("Burma", "Yemen", "Sumatra"), home=("India",),
        other=("Ceylon", "Pakistan", "East Bengal", "Andaman Islands", "Maldives"), bases={"India": 500},
        sea=(("Arabian Sea", 68.0, 17.0), ("Bay of Bengal", 86.0, 15.0), ("Laccadive Sea", 78.0, 5.0)), ranks=True),
    "Great Britain": dict(
        name="Southeast Asian Union", adjective="Southeast Asian", flag="SoutheastAsia.bmp", government=1,
        leader="Secretary-General", parliament="the Union Assembly", admiral="Sondakh", resources=18000, budget=5,
        dock=40000, area="Southeast Asia", trouble="in the South China Sea", friend="United States",
        enemies=("People's Republic of China",), neighbours=("Papua", "Hainan", "Western Australia"),
        home=("Java",),
        other=("Singapore", "The Philippines", "Malaya", "Sumatra", "Borneo", "Cochin China", "Annam", "Tonkin", "Celebes and Moluccas", "Burma"),
        bases={"Java": 400, "Singapore": 400, "The Philippines": 300},
        sea=(("South China Sea", 112.0, 10.0), ("Java Sea", 112.0, -5.5), ("Philippine Sea", 128.0, 13.0),
             ("Andaman Sea", 95.5, 10.0)), ranks=True),
    "France": dict(
        name="United African States", adjective="African", flag="AfricanUnion.bmp", government=1, leader="Chairperson",
        parliament="the Pan-African Parliament", admiral="Mudimu", resources=10000, budget=4, dock=30000,
        area="Southern Africa", trouble="in the Sahel", friend=None, enemies=(),
        neighbours=("Morocco", "Yemen", "Egypt"), home=("South Afriica",),
        other=("Nigeria", "Kenya", "Senegal", "Cameroon", "Sierra Leone", "Angola", "Middle Congo", "Madagascar", "Mozambique", "Tanganyika",
               "Zanzibar", "Southwest Africa", "Djibouti", "Eritrea", "Somalia", "Somaliland", "Sudan"),
        bases={"South Afriica": 400, "Nigeria": 300, "Kenya": 200},
        sea=(("Gulf of Guinea", 2.0, 1.0), ("off the Cape of Good Hope", 17.0, -36.5), ("Mozambique Channel", 41.0, -17.0),
             ("off Somalia", 52.0, 3.0)), ranks=True),
    "Italy": dict(
        name="Middle East Federation", adjective="Middle Eastern", flag="MiddleEast.bmp", government=2, leader="President",
        parliament="the Federal Council", admiral="Sayyari", resources=23000, budget=6, dock=40000,
        area="The Mediterranean", trouble="in the Gulf", friend=None, enemies=(),
        neighbours=("Cyprus", "Greece", "Rhodes"), home=("Turkey",),
        other=("Persia", "Egypt", "Libya", "Tunisia", "Algeria", "Morocco", "Yemen", "Iraq", "Arabia", "Syria",
               "Palestine", "Northern Anatolia", "Cilicia", "Kuwait", "Al-Ahsa", "Trucial States", "Oman",
               "Egyptian Red Sea Coast"), bases={"Egypt": 300},
        sea=(("Eastern Mediterranean", 30.0, 33.5), ("Gulf of Oman", 61.0, 23.5), ("Gulf of Aden", 48.0, 12.5),
             ("Black Sea", 36.0, 42.7)), ranks=True),
    "Soviet Union": dict(
        name="Russian Federation", adjective="Russian", flag="Russia.bmp", government=1, leader="President",
        parliament="the Duma", admiral="Masorin", resources=14000, budget=10, dock=70000,
        area="The Baltic", trouble="in the Caucasus", friend="India", enemies=(),
        neighbours=("Finland", "Norway", "Baltic States"), home=("Western Russia",), other=("Southern Russia",),
        source="Soviet Union",
        sea=(("Barents Sea", 36.0, 72.0), ("Baltic Sea", 19.0, 57.0), ("Sea of Japan", 135.0, 41.0),
             ("North Pacific", 160.0, 50.0), ("Black Sea", 34.0, 43.3))),
    "Japan": dict(
        name="East Asian Federation", adjective="East Asian", flag="EastAsia.bmp", government=0, leader="Prime Minister",
        parliament="the Federal Diet", admiral="Saito", resources=44000, budget=5, dock=100000,
        area="Northeast Asia", trouble="on the Korean peninsula", friend="United States",
        enemies=("People's Republic of China",), neighbours=("Northern Korea", "Sakhalin", "Hainan"),
        home=("Japan",), other=("Southern Korea", "Hokkaido", "Formosa"), bases={"Southern Korea": 400},
        sea=(("Philippine Sea", 137.0, 30.0), ("Sea of Japan", 133.0, 38.0), ("East China Sea", 126.5, 30.5)), source="Japan"),
    "USA": dict(
        name="United States", adjective="American", flag="USN.bmp", government=0, leader="President",
        parliament="Congress", admiral="Mullen", resources=100000, budget=12, dock=110000,
        area="North American East Coast", trouble="in the Caribbean", friend="European Union", enemies=(),
        neighbours=("Nova Scotia", "Grand Bahama", "British Columbia"), home=("Eastern USA",), other=(), source="USA",
        sea=(("Western Atlantic", -68.0, 36.0), ("Gulf of Mexico", -90.0, 25.0), ("Eastern Pacific", -125.0, 33.0),
             ("off Hawaii", -160.0, 23.5))),
    "Spain": dict(
        name="South American Union", adjective="South American", flag="SouthAmerica.bmp", government=0, leader="President",
        parliament="the Union Congress", admiral="Carvalho", resources=22000, budget=4, dock=45000,
        area="South American East Coast", trouble="in the Andes", friend=None, enemies=(),
        neighbours=("Grand Bahama", "New Providence", "Falkland Islands"), home=("Brazil",),
        other=("Argentina", "Chile", "Peru", "Venezuela", "Trinidad", "Panama", "Cuba", "Haiti", "Dominican Republic",
               "Jamaica"), bases={"Chile": 200, "Cuba": 100, "Panama": 100},
        sea=(("South Atlantic", -35.0, -18.0), ("Argentine Sea", -55.0, -40.0), ("off Valparaiso", -76.0, -33.0),
             ("Southern Caribbean", -66.0, 13.0)), ranks=True),
    "China": dict(
        name="People's Republic of China", adjective="Chinese", flag="PRC.bmp", government=5, leader="President",
        parliament="the National People's Congress", admiral="Zhang Dingfa", resources=40000, budget=9, dock=80000,
        area="Northeast Asia", trouble="in the Taiwan Strait", friend=None,
        enemies=("United States", "East Asian Federation"), neighbours=("Northern Korea", "Formosa", "Tonkin"),
        home=("Northern China",),
        other=("Southern China", "Shanghai", "Hong Kong", "Hainan", "Kiautschou Bay", "Weihaiwei", "Liaotung Peninsula", "Kwang-Chou-Wan"),
        sea=(("East China Sea", 124.5, 29.0), ("South China Sea", 115.0, 19.0), ("Yellow Sea", 123.0, 36.0)), source="China"),
}
BY_NAME = {b["name"]: b for b in BLOCS.values()}
RENAMED = {slot: b["name"] for slot, b in BLOCS.items()}
# Overseas land the 2000 owners keep: old owner -> bloc (the rest of each bloc is listed above).
LEGACY = {"Great Britain": "European Union", "France": "European Union", "Italy": "European Union",
          "Germany": "European Union", "Spain": "European Union", "USA": "United States",
          "Soviet Union": "Russian Federation", "Russia": "Russian Federation", "China": "People's Republic of China",
          "Japan": "East Asian Federation", "Austria-Hungary": "Neutral", "Optional": "Neutral"}
# A world: its blocs and the rules the writers below need. coldwar_data.py holds the 1947-1980 one.
MODERN = dict(blocs=BLOCS, values=VALUES, legacy=LEGACY, asian=ASIAN, growing=GROWING, colonies=0,
              skip=("South American Union", "Southeast Asian Union"))   # left out of Asian / other players' war files


def at(world, year):
    """The world in one year: every bloc with its at[year] changes."""
    return {**world, "blocs": {slot: {**b, **b.get("at", {}).get(year, {})} for slot, b in world["blocs"].items()}}


# Battle kinds as the native war files set them: title, BattleSize, MaxShipType, DeclinePenalty.
KINDS = (("Fleet battle", 0, 0, 200), ("Cruiser battle", 1, 3, 120), ("Action with light forces", 2, 9, 40))
MISSION_KEYS = """Title Location DeclinePenalty AttackingSide WeatherZone Colonies Destroyers BDR FirstYear LastYear
MaxShipType BattleSize CenterPoint MeetAtCenterPoint DefenderSurprised StartPoints0 HomePoints0 CarrierStartPoints0
StartpointRndDir0 StartpointRndDist0 StartPoints1 HomePoints1 CarrierStartPoints1 StartpointRndDir1 StartpointRndDist1
WaypointLL WaypointRndDir WaypointRndDist Objectives0 ObjectivesB0 ObjectiveValue0 ObjectiveType0 Objectives1 ObjectivesB1
ObjectiveValue1 ObjectiveType1 CruiserPatrolPoints0 CruiserPatrolPoints1 CruiserPatrolPoints2 CruiserPatrolPoints3
PatrolWaypoints0 PatrolWaypoints1 PatrolWaypoints2 PatrolWaypoints3 SubmarinePoints0 SubmarinePoints1 SubmarinePoints2
SubmarinePoints3 SubmarinePoints4 SubmarinePoints5 SubmarinePoints6 SubmarinePoints7 MerchantShipPoints0
MerchantShipPoints1 MerchantShipPoints2 MerchantShipPoints3 LocalBaseName0 LocalBaseLocation0 LocalBaseExitNavPoint0
LocalBaseName1 LocalBaseLocation1 LocalBaseExitNavPoint1""".split()
NOWHERE = "00000E 00000N"
POINT_KEYS = ("Point", "Objectives", "Waypoint", "LocalBaseLocation")
SHIP_SECTIONS = ("BB", "BC", "CA", "CL", "DD", "DDPrefix", "SSPrefix", "KE", "AMC", "CV", "CVL", "XX",
                 "Aircraft manufacturers", "Helicopter manufacturers", "Aircraft names")
EUROPE = ("Great Britain", "Germany", "France", "Italy", "Spain")
ENCODING = "cp1252"   # war files are read as plain INI files: no UTF-8 mark


def position(lon, lat):
    """The game's DDDMMSS[EW] DDMMSS[NS] text."""
    def dms(value):   # at least five digits: the game refuses "4500N" for 0 deg 45 min
        seconds = round(abs(value)*3600)
        return f"{seconds//3600*10000+seconds//60 % 60*100+seconds % 60:05d}"
    return f"{dms(lon)}{'E' if lon >= 0 else 'W'} {dms(lat)}{'N' if lat >= 0 else 'S'}"


def nations(text, w=MODERN):
    """BNat<year>.dat from that year's historical nations; a bloc keeps what it does not set from its slot."""
    out = []
    for header, lines in years.sections(text):
        if header is not None:
            b = w["blocs"][years.nation_name(lines)]
            enemies = list(b["enemies"])+[None, None]
            leading = b["name"].startswith("United States")
            changes = dict(
                Name=b["name"], Name2=b["adjective"], GovernmentType=b["government"], GovernmentChange=0,
                Leader=b["leader"], LeaderF=b["leader"], LeaderC=b["leader"], LeaderR=b["leader"],
                ParliamentName=b["parliament"], BuildAreaName=b["area"],
                TroubleRegion=b["trouble"], Friend=b["friend"], Enemy1=enemies[0], Enemy2=enemies[1],
                FlagFileName=b["flag"], FlagFileNameF=b["flag"], FlagFileNameC=b["flag"], FlagFileNameR=b["flag"],
                GlobalNavalPower=int(leading or b.get("global", False)), IP="Panama" if leading else None,
                **{f"BKT{i+1}": name for i, name in enumerate(b["neighbours"])},
                **{f"PAL{i+1}": None for i in range(6)}, **(ENGLISH_RANKS if b.get("ranks") else {}))
            for key, field in (("admiral", "AdmiralName"), ("budget", "BudgetModifier"), ("dock", "DockSize")):
                if key in b: changes[field] = b[key]
            if "resources" in b: changes.update(BaseResources=b["resources"], HBR=b["resources"]//1000)
            changes["Colonies"] = int(b.get("colonies", False)) if w["colonies"] is None else w["colonies"]
            if w["growing"] is not None: changes["GGP"] = int(b["name"] in w["growing"])
            if "growing" in b: changes["GGP"] = int(b["growing"])
            if any(line.startswith("Possession0=") for line in lines):   # the Spain and China slots own these outright
                changes.update(Possession0=b["home"][0], Possession1=(b["other"] or b["home"])[0])
            lines = years.edit(lines, changes)
            out.append(header)
        out.extend(lines)
    return "\r\n".join(out)+"\r\n"


def owner_of(name, historical, w=MODERN):
    for b in w["blocs"].values():
        if name in b["home"] or name in b["other"]: return b["name"]
    return w["legacy"].get(historical, historical)


def possessions(base, state2000, w=MODERN):
    """MapData<year>.dat: every possession of the base map (Data/MapData.dat), in its own area and order;
    state2000 is that year's historical map (owners)."""
    BLOCS, VALUES = w["blocs"], w["values"]
    at2000 = {m.group(2).strip(): m.group(1).strip() for m in re.finditer(r"Possession\d+Owner=(.*)\r?\nMapArea\d+Possession\d+Name=(.*)", state2000)}
    field = {(int(a), int(p), k): v.strip() for a, p, k, v in
             re.findall(r"^MapArea(\d+)Possession(\d+)(Owner|Name|Value|Oil|BaseValue)=(.*)$", base, flags=re.M)}
    areas = sorted({a for a, _, _ in field})
    listed = {field[a, p, "Name"] for a, p, k in field if k == "Name"}
    wanted = {n for b in BLOCS.values() for n in b["home"]+b["other"]+b["neighbours"]}
    if wanted-listed: raise ValueError("Unknown possessions: "+", ".join(sorted(wanted-listed)))
    homes = {n for b in BLOCS.values() for n in b["home"]}
    bases = {n: v for b in BLOCS.values() for n, v in b.get("bases", {}).items()}
    out = ["[MapAreas]", f"MapAreaCount={len(areas)}"]
    for a in areas:
        count = 1+max(p for x, p, _ in field if x == a)
        out += [f"MapArea{a}MineLevel{i}=0" for i in range(7)]+[f"MapArea{a}PossessionCount={count}"]
        for p in range(count):
            name = field[a, p, "Name"]; key = f"MapArea{a}Possession{p}"
            owner = owner_of(name, at2000.get(name, field[a, p, "Owner"]), w)
            value = 200 if name in homes else VALUES.get(name, field[a, p, "Value"])
            if value == "200": value = 20                            # an unused native home area is ordinary land
            out += [f"{key}Owner={owner}", f"{key}Name={name}", f"{key}Value={value}", f"{key}Oil={field[a, p, 'Oil']}",
                    f"{key}BaseValue={bases.get(name, field[a, p, 'BaseValue'])}", f"{key}Rebellion=0", f"{key}Invaded=-1",
                    f"{key}InvasionSupport=0", f"{key}BuildingBase=0", f"{key}TakenFrom=-1"]
    return "\r\n".join(out)+"\r\n"


def mission(kind=None, place=None):
    values = dict.fromkeys(MISSION_KEYS, "0")
    values.update(Title="", Location="", LocalBaseName0="", LocalBaseName1="", FirstYear="1890", LastYear="1999")
    values.update({k: NOWHERE for k in MISSION_KEYS if any(part in k for part in POINT_KEYS) and "Rnd" not in k})
    if kind:
        title, size, ships, penalty = kind; name, lon, lat = place
        values.update(Title=title, Location=name, DeclinePenalty=penalty, AttackingSide=99, Destroyers=1, LastYear=2099,
                      WeatherZone=2 if abs(lat) < 23.5 else 0 if abs(lat) > 45 else 1, MaxShipType=ships, BattleSize=size,
                      CenterPoint=position(lon, lat), MeetAtCenterPoint=1,
                      StartPoints0=position(lon+0.35, lat-0.25), StartpointRndDir0=90, StartpointRndDist0=30,
                      StartPoints1=position(lon-0.35, lat+0.25), StartpointRndDir1=270, StartpointRndDist1=40)
    return [f"{k}={values[k]}" for k in MISSION_KEYS]


def distance(a, b):
    return ((a[1]-b[1]+180) % 360-180)**2+(a[2]-b[2])**2


def war_info(bloc, w=MODERN):
    """Eight enemies, eleven missions each: meeting engagements in the two blocs' nearest home waters."""
    out = []
    skip = w["skip"][bloc["name"] not in w["asian"]]
    enemies = [b for b in w["blocs"].values() if b is not bloc and b["name"] != skip]
    if len(enemies) != 8: raise ValueError("A war file holds eight enemies.")
    for index, enemy in enumerate(enemies, 1):
        mine = sorted(bloc["sea"], key=lambda p: min(distance(p, q) for q in enemy["sea"]))[:2]
        theirs = sorted(enemy["sea"], key=lambda p: min(distance(p, q) for q in bloc["sea"]))[:2]
        places = [mine[0], theirs[0], mine[1], theirs[1]]
        out += [f"[Nation{index}]", f"NationName={enemy['name']}", f"BreakoutPoint={position(*mine[0][1:])}",
                "BreakoutPointRndDir=0", "BreakoutPointRndDist=100"]
        plans = [(KINDS[(i+j) % 3], place) for j in range(2) for i, place in enumerate(places)]
        for number in range(11):
            out += [f"[Nation{index}Mission{number}]"]+(mission(*plans[number]) if number < len(plans) else mission())
    return "\r\n".join(out)+"\r\n"


def ship_names(text):
    """{section: [names]} of a native ship-name file; names before the first section are dropped."""
    out, current = {}, None
    for line in text.splitlines():
        if line.startswith("["): current = out.setdefault(line.strip()[1:-1], [])
        elif current is not None and line.strip(): current.append(line.strip())
    return out


def render_ships(lists):
    return "".join(f"[{name}]\r\n"+"".join(n+"\r\n" for n in lists.get(name, [])) for name in SHIP_SECTIONS)


def native(data, nation, *kinds):
    for kind in kinds:
        path = data/(nation+kind)
        if path.exists():   # the game's own files are ANSI or UTF-8 with a mark
            raw = path.read_bytes()
            return raw.decode("utf-8-sig") if raw[:3] == bytes((0xEF, 0xBB, 0xBF)) else raw.decode(ENCODING)
    raise ValueError(f"No {kinds[0]} file for {nation}.")


def merged(lists):
    """One list taking names from each in turn, without repeats."""
    out = []
    for i in range(max(map(len, lists), default=0)):
        out += [names[i] for names in lists if i < len(names) and names[i] not in out]
    return out


def bloc_names(data, bloc):
    """(ship name lists, officer names) of a bloc."""
    generic = ship_names(native(data, "USA", "ShipNames20.dat"))
    if bloc.get("names") == "merge":
        files = [ship_names(native(data, n, "ShipNames20.dat", "ShipNames.dat")) for n in EUROPE]
        ships = {s: merged([f.get(s, []) for f in files]) for s in SHIP_SECTIONS}
        ships.update(DDPrefix=["D"], SSPrefix=["S-"])
        officers = merged([native(data, n, "Names.txt").split() for n in EUROPE])
    elif "source" in bloc:
        ships = ship_names(native(data, bloc["source"], "ShipNames20.dat", "ShipNames.dat"))
        officers = native(data, bloc["source"], "Names.txt").splitlines()
        if bloc["name"] == "East Asian Federation":
            for section, extra in pools.EAST_ASIA_EXTRA.items(): ships[section] = merged([ships.get(section, []), extra])
            officers = merged([officers, pools.EAST_ASIA_OFFICERS])
    else:
        pool = pools.POOLS[bloc.get("pool", bloc["name"])]
        ships = dict(BB=pool["big"][0::3], BC=pool["big"][1::3], CV=pool["big"][2::3], CA=pool["medium"][0::3],
                     CL=pool["medium"][1::3], CVL=pool["medium"][2::3], DD=pool["small"], KE=pool["small"][::-1],
                     AMC=pool["medium"][::-1], DDPrefix=["D"], SSPrefix=["S-"], XX=generic["XX"])
        ships.update({"Aircraft manufacturers": pool["makers"], "Helicopter manufacturers": pool["helicopters"],
                      "Aircraft names": pool["aircraft"]})
        officers = pool["officers"]
    for section in SHIP_SECTIONS:
        if not ships.get(section): ships[section] = generic[section]
    for section, first in pools.HISTORIC.get(bloc["name"], {}).items():           # real post-war ships lead
        ships[section] = merged([first])+[n for n in ships[section] if n not in first]
    return ships, [n for n in officers if n.strip()]


def flags(pictures, target):
    """60x40 ensigns: downloaded organisation flags, and two drawn ones."""
    from PIL import Image, ImageDraw
    sources = {"EuropeanUnion.bmp": "Flag_of_Europe.png", "IndiaNavy.bmp": "Naval_Ensign_of_India.png",
               "AfricanUnion.bmp": "Flag_of_the_African_Union.png", "MiddleEast.bmp": "Flag_of_the_Arab_League.png",
               "SouthAmerica.bmp": "Flag_of_UNASUR.png"}
    target.mkdir(parents=True, exist_ok=True)
    for name, source in sources.items():
        picture = Image.open(pictures/source).convert("RGBA")
        flat = Image.new("RGB", picture.size, (255, 255, 255)); flat.paste(picture, mask=picture.split()[3])
        flat.resize((60, 40), Image.LANCZOS).save(target/name)
    big = Image.new("RGB", (240, 160), (0, 56, 147)); d = ImageDraw.Draw(big)      # ASEAN colours, own emblem
    d.ellipse((60, 20, 180, 140), fill=(255, 255, 255)); d.ellipse((66, 26, 174, 134), fill=(206, 17, 38))
    for i in range(10): d.rectangle((84+i*8, 50+abs(i-4.5)*5, 87+i*8, 110-abs(i-4.5)*5), fill=(249, 229, 0))
    big.resize((60, 40), Image.LANCZOS).save(target/"SoutheastAsia.bmp")
    big = Image.new("RGB", (240, 160), (255, 255, 255)); d = ImageDraw.Draw(big)   # East Asian Federation: drawn
    d.rectangle((0, 0, 240, 22), fill=(0, 71, 160)); d.rectangle((0, 138, 240, 160), fill=(0, 71, 160))
    d.ellipse((80, 40, 160, 120), fill=(190, 0, 38))
    d.pieslice((80, 40, 160, 120), 0, 180, fill=(0, 71, 160))
    big.resize((60, 40), Image.LANCZOS).save(target/"EastAsia.bmp")


def write(game, files, pictures=None, world=MODERN, when=(YEAR,)):
    import map_ports
    """Nation and map files for each year of a world, and its blocs' war and name files (one set: the game finds
    them by name, whatever the year)."""
    game, files = Path(game), Path(files)
    data, out = game/"Data", files/"Data"
    made = {}
    base = (files.parents[1]/"campaign-qol/Files/Data/MapData.dat").read_text(encoding="utf-8-sig", errors="replace")
    for year in when:
        w = at(world, year)
        historical = years.nations((data/"BNat1935.dat").read_text(encoding="utf-8-sig"), year)
        made[f"BNat{year}.dat"] = nations(historical, w).encode("utf-8-sig")
        native = map_ports.year_map((data/"MapData1920.dat").read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
                                    .replace("\n", "\r\n"))          # with the mod's new possessions, installed or not
        state = years.possessions(native, year)
        made[f"MapData{year}.dat"] = possessions(base, state, w).encode("utf-8-sig")
    for bloc in world["blocs"].values():
        war = war_info(bloc, world).encode(ENCODING)
        ships, officers = bloc_names(data, bloc)
        ships = render_ships(ships).encode("utf-8-sig")
        made[bloc["name"]+"WarInfo20.dat"] = made[bloc["name"]+"WarInfo.dat"] = war
        made[bloc["name"]+"ShipNames20.dat"] = made[bloc["name"]+"ShipNames.dat"] = ships
        made[bloc["name"]+"Names.txt"] = "".join(n+"\r\n" for n in officers).encode("utf-8-sig")
    for name, body in made.items(): (out/name).write_bytes(body)
    if pictures: flags(Path(pictures), files/"Flags")
    return sorted(made)


def write_names(game, files, world=MODERN):
    """Only the blocs' ship name files (after a change to the name pools)."""
    made = {}
    for bloc in world["blocs"].values():
        ships = render_ships(bloc_names(Path(game)/"Data", bloc)[0]).encode("utf-8-sig")
        made[bloc["name"]+"ShipNames20.dat"] = made[bloc["name"]+"ShipNames.dat"] = ships
    for name, body in made.items(): (Path(files)/"Data"/name).write_bytes(body)
    return sorted(made)


if __name__ == "__main__":
    print("\n".join(write(*sys.argv[1:])))

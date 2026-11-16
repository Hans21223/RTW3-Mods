"""More ports on the campaign map: fills unused base slots of existing possessions in Campaign QoL's Data/MapData.dat.

A possession has six base slots (name "Error" when unused). Each new port gets a position, a sea exit point just
offshore and a size; positions are from real coordinates, not checked in-game. Running it again changes nothing.

New sea areas (AREAS) follow the native sixteen: the Black Sea, linked to The Mediterranean, as the community
Ottoman mod does. The map file holds its own area count and the game keeps its areas in a list, so a seventeenth
needs no code; a save loads its areas by number and their possessions by name in list order, so new areas and
possessions only ever go last. New possessions (REGIONS) go at the end of their areas: the Black Sea coasts, the
Levant, Iraq, Arabia, Pakistan, East Bengal, the Andamans and the Maldives, then the regions of the Ottoman mod
(Macedonia, Crete, Cilicia, the Gulf and Red Sea coasts, the Horn of Africa, the Netherlands and the ABC islands, and
the Black Sea split into Odessa, Kuban, Georgia, Donbass and Rostov, with Southern Russia left as Crimea). Each is a
copy of Chile's block (a possession with one plain meeting battle). A port moves to its new region: saves keep
regions by name, never ports (coastal batteries too), so MOVED takes native ports out of their old possession. Year
maps name the possessions they change; the 1920 one (also the 1935 start's) gets the Russian ones as Soviet.

Run:  python map_ports.py <MapData.dat> [<native MapData1920.dat> <output MapData1920.dat>]
"""
from pathlib import Path
import re
import sys

from superstates_data import position

SIZE = 3
# possession: (port, longitude, latitude, exit longitude, exit latitude), east and north positive
PORTS = {
    "India": (("Calcutta", 88.33, 22.55, 88.20, 21.30), ("Cochin", 76.25, 9.97, 76.00, 9.92),
              ("Vizagapatam", 83.30, 17.68, 83.58, 17.58), ("Goa", 73.80, 15.42, 73.65, 15.40)),
    "Ceylon": (("Galle", 80.22, 6.03, 80.15, 5.85),),
    "Persia": (("Bushehr", 50.84, 28.97, 50.75, 28.95),),
    "Egypt": (("Mersa Matruh", 27.23, 31.35, 27.25, 31.60),),
    "Turkey": (("Marmaris", 28.27, 36.85, 28.33, 36.67), ("Canakkale", 26.41, 40.15, 26.32, 40.06)),
    "Yemen": (("Hodeida", 42.95, 14.80, 42.67, 14.75), ("Mukalla", 49.12, 14.53, 49.17, 14.33)),
    "Singapore": (("Changi", 103.98, 1.38, 104.15, 1.30),),
    "Java": (("Semarang", 110.42, -6.95, 110.42, -6.67),),
    "Sumatra": (("Belawan", 98.68, 3.78, 98.92, 3.92), ("Padang", 100.35, -0.95, 100.08, -1.00)),
    "Borneo": (("Brunei", 115.07, 5.02, 115.00, 5.33), ("Kuching", 110.35, 1.57, 110.33, 1.92)),
    "Malaya": (("Kuantan", 103.43, 3.97, 103.75, 4.00),),
    "Burma": (("Akyab", 92.90, 20.13, 92.67, 20.00), ("Moulmein", 97.62, 16.48, 97.33, 16.25)),
    "Cochin China": (("Saigon", 106.72, 10.77, 107.08, 10.25),),
}


# Native ports that move to a new region (with their native position, exit and size there)
MOVED = {"Greece": ("Heraklion", "Thessaloniki"), "Turkey": ("Alexandretta",)}
WEATHER = {"Northern Europe": 0, "The Caribbean": 2}   # the template's zone (1) elsewhere

TEMPLATE, NOWHERE = "Chile", "00000E 00000N"
# name: box (west, north) and (east, south), sea points the game uses (IP), neighbour; Russia is its sensitive power
AREAS = (("Black Sea", dict(UL=(26.5, 47.8), LR=(42.5, 40.4), points=((31.0, 43.4), (34.6, 43.0), (38.8, 42.6)),
                            neighbour="The Mediterranean", sensitive="Russia")),)
# New possessions: area, name, owner on the base map (the 1890 world), owner in 1920, (longitude, latitude), value,
# oil, base value, battle (name, longitude, latitude), ports (as above, with a size).
REGIONS = (
    ("Black Sea", "Southern Russia", "Russia", "Soviet Union", (34.0, 45.3), 12, 0, 200, ("Black Sea", 33.0, 43.8),
     (("Sevastopol", 33.52, 44.62, 33.35, 44.64, 2), ("Eupatoria", 33.37, 45.19, 33.37, 45.12, 1),
      ("Feodosia", 35.38, 45.03, 35.48, 45.00, 1), ("Kerch", 36.47, 45.35, 36.53, 45.31, 1))),
    ("Black Sea", "Romania", "Neutral", "Neutral", (28.65, 44.17), 4, 1, 30, ("Black Sea", 30.0, 43.9),
     (("Constanta", 28.65, 44.17, 28.85, 44.15, 3),)),
    ("Black Sea", "Bulgaria", "Neutral", "Neutral", (27.92, 43.2), 3, 0, 20, ("Black Sea", 29.2, 42.9),
     (("Varna", 27.92, 43.20, 28.15, 43.18, 3), ("Burgas", 27.47, 42.50, 27.80, 42.48, 3))),
    ("Black Sea", "Northern Anatolia", "Neutral", "Neutral", (36.3, 41.0), 6, 0, 40, ("Off Sinop", 35.6, 42.4),
     (("Sinop", 35.15, 42.02, 35.30, 41.95, 3), ("Samsun", 36.33, 41.29, 36.45, 41.42, 3),
      ("Trabzon", 39.72, 41.00, 39.75, 41.15, 3), ("Eregli", 31.42, 41.28, 31.40, 41.36, 2),
      ("Constantinople", 28.98, 41.02, 29.12, 41.26, 3))),
    ("The Mediterranean", "Syria", "Neutral", "France", (36.0, 35.0), 3, 0, 20, ("Off the Levant", 34.8, 34.6),
     (("Latakia", 35.78, 35.52, 35.60, 35.50, 3), ("Beirut", 35.50, 33.90, 35.35, 33.92, 3))),
    ("The Mediterranean", "Palestine", "Neutral", "Great Britain", (35.0, 32.0), 3, 0, 30, ("Off Haifa", 33.9, 32.6),
     (("Haifa", 35.00, 32.82, 34.90, 32.92, 3),)),
    ("Indian Ocean", "Iraq", "Neutral", "Great Britain", (47.8, 30.5), 4, 1, 20, ("Persian Gulf", 50.5, 28.3),
     (("Fao", 48.48, 29.98, 48.75, 29.75, 3),)),
    ("Indian Ocean", "Arabia", "Neutral", "Neutral", (45.0, 24.0), 4, 1, 20, ("Red Sea", 38.0, 20.5),
     (("Jeddah", 39.17, 21.48, 38.95, 21.45, 3), ("Yanbu", 38.06, 24.09, 37.95, 24.02, 1),
      ("Al-Qunfudhah", 41.08, 19.13, 40.98, 19.10, 1))),
    ("Indian Ocean", "Pakistan", "Great Britain", "Great Britain", (67.0, 25.5), 6, 0, 60, ("Off Karachi", 65.5, 23.8),
     (("Karachi", 66.98, 24.83, 66.83, 24.58, 3), ("Ormara", 64.63, 25.20, 64.65, 25.02, 3))),
    ("Indian Ocean", "East Bengal", "Great Britain", "Great Britain", (90.5, 23.0), 4, 0, 30, ("Bay of Bengal", 90.5, 20.5),
     (("Chittagong", 91.80, 22.33, 91.65, 22.10, 3),)),
    ("Indian Ocean", "Andaman Islands", "Great Britain", "Great Britain", (92.7, 12.0), 1, 0, 10, ("Andaman Sea", 91.5, 11.0),
     (("Port Blair", 92.73, 11.67, 92.76, 11.60, 3),)),
    ("Indian Ocean", "Maldives", "Great Britain", "Great Britain", (73.2, 0.5), 1, 0, 5, ("Off the Maldives", 74.5, 1.0),
     (("Gan", 73.15, -0.69, 73.30, -0.60, 3),)),
    # from the community Ottoman mod (its Ottoman Empire is Neutral here; Hejaz is Arabia, South Yemen is Yemen)
    ("Black Sea", "Odessa", "Russia", "Soviet Union", (31.0, 47.0), 6, 0, 100, ("Off Odessa", 31.2, 45.8),
     (("Odessa", 30.73, 46.48, 30.90, 46.35, 3), ("Nikolaev", 31.99, 46.97, 31.35, 46.52, 3),
      ("Kherson", 32.62, 46.64, 31.40, 46.48, 1))),
    ("Black Sea", "Kuban", "Russia", "Soviet Union", (39.5, 45.0), 4, 1, 60, ("Off Novorossiysk", 37.6, 44.3),
     (("Novorossiysk", 37.78, 44.72, 37.85, 44.60, 3), ("Sochi", 39.73, 43.58, 39.66, 43.53, 1))),
    ("Black Sea", "Georgia", "Russia", "Soviet Union", (42.3, 42.2), 2, 1, 30, ("Off Batum", 40.8, 41.9),
     (("Batum", 41.64, 41.65, 41.45, 41.68, 3), ("Poti", 41.67, 42.15, 41.55, 42.15, 2),
      ("Sukhum", 41.02, 43.00, 40.95, 42.95, 1))),
    ("Black Sea", "Donbass", "Russia", "Soviet Union", (37.8, 47.6), 6, 0, 30, ("Sea of Azov", 36.5, 46.1),
     (("Mariupol", 37.55, 47.10, 37.55, 46.98, 2), ("Berdyansk", 36.78, 46.76, 36.80, 46.68, 1))),
    ("Black Sea", "Rostov", "Russia", "Soviet Union", (40.2, 46.9), 4, 0, 30, ("Sea of Azov", 37.6, 46.4),
     (("Taganrog", 38.93, 47.21, 38.90, 47.12, 2), ("Yeysk", 38.27, 46.71, 38.20, 46.75, 1))),
    ("The Mediterranean", "Macedonia", "Neutral", "Neutral", (23.5, 41.0), 5, 0, 40, ("North Aegean", 24.3, 39.6),
     (("Thessaloniki", 22.9506, 40.6128, 22.7822, 40.4850, 3), ("Kavala", 24.41, 40.94, 24.40, 40.88, 2),
      ("Dedeagach", 25.87, 40.85, 25.87, 40.78, 1))),
    ("The Mediterranean", "Cilicia", "Neutral", "Neutral", (35.3, 37.0), 4, 0, 35, ("Off Cilicia", 34.9, 36.2),
     (("Mersin", 34.63, 36.80, 34.67, 36.58, 3), ("Alexandretta", 36.1061, 36.5558, 35.5261, 36.4158, 3))),
    ("The Mediterranean", "Crete", "Neutral", "Neutral", (24.9, 35.2), 4, 0, 80, ("Off Crete", 25.0, 35.8),
     (("Heraklion", 25.1597, 35.3281, 25.2019, 35.4144, 3), ("Souda Bay", 24.08, 35.49, 24.25, 35.50, 3))),
    ("Indian Ocean", "Kuwait", "Great Britain", "Great Britain", (47.7, 29.3), 3, 1, 10, ("Off Kuwait", 48.8, 29.0),
     (("Kuwait", 47.98, 29.38, 48.20, 29.45, 3),)),
    ("Indian Ocean", "Al-Ahsa", "Neutral", "Neutral", (49.4, 25.6), 3, 1, 10, ("Off Dammam", 50.9, 26.8),
     (("Dammam", 50.20, 26.50, 50.45, 26.65, 3), ("Jubail", 49.66, 27.01, 49.80, 27.05, 1))),
    ("Indian Ocean", "Trucial States", "Great Britain", "Great Britain", (54.4, 24.2), 5, 1, 25,
     ("Off the Trucial Coast", 54.5, 25.6),
     (("Abu Dhabi", 54.37, 24.47, 54.30, 24.60, 2), ("Dubai", 55.30, 25.27, 55.20, 25.36, 1),
      ("Bahrain", 50.60, 26.22, 50.85, 26.35, 3), ("Doha", 51.53, 25.29, 51.65, 25.32, 1))),
    ("Indian Ocean", "Oman", "Great Britain", "Great Britain", (57.0, 22.5), 3, 1, 10, ("Gulf of Oman", 59.0, 24.0),
     (("Muscat", 58.58, 23.62, 58.75, 23.78, 3),)),
    ("Indian Ocean", "Somalia", "Italy", "Italy", (45.0, 3.5), 4, 0, 25, ("Off Mogadishu", 46.5, 2.0),
     (("Mogadishu", 45.34, 2.04, 45.45, 1.98, 2), ("Kismayo", 42.54, -0.36, 42.62, -0.42, 1))),
    ("Indian Ocean", "Somaliland", "Great Britain", "Great Britain", (45.5, 9.5), 2, 0, 25, ("Gulf of Aden", 45.5, 11.2),
     (("Berbera", 45.01, 10.44, 45.00, 10.52, 2),)),
    ("Indian Ocean", "Sudan", "Great Britain", "Great Britain", (36.4, 19.0), 3, 0, 10, ("Off Port Sudan", 37.8, 19.8),
     (("Port Sudan", 37.22, 19.62, 37.35, 19.62, 2), ("Suakin", 37.33, 19.11, 37.45, 19.12, 1))),
    ("Indian Ocean", "Egyptian Red Sea Coast", "Great Britain", "Great Britain", (33.6, 26.5), 3, 0, 10,
     ("Red Sea", 36.2, 25.0),
     (("Suez", 32.55, 29.95, 32.58, 29.75, 3), ("Hurghada", 33.84, 27.26, 33.95, 27.22, 1),
      ("Quseir", 34.28, 26.10, 34.38, 26.08, 1))),
    ("The Caribbean", "ABC Islands", "Neutral", "Neutral", (-68.95, 12.15), 4, 0, 20, ("Off Curacao", -68.6, 12.7),
     (("Willemstad", -68.93, 12.11, -68.93, 12.04, 2), ("Oranjestad", -70.03, 12.52, -70.06, 12.47, 1),
      ("Kralendijk", -68.27, 12.15, -68.32, 12.15, 1))),
    ("Northern Europe", "The Netherlands", "Neutral", "Neutral", (5.6, 52.3), 10, 0, 60, ("Off the Dutch coast", 3.8, 52.9),
     (("Den Helder", 4.76, 52.96, 4.70, 52.98, 3), ("Rotterdam", 4.48, 51.92, 4.02, 52.00, 3),
      ("Vlissingen", 3.57, 51.44, 3.50, 51.42, 2))),
)


def area_of(lines, name):
    return next(line.split("Name=")[0] for line in lines if line == f"{line.split('Name=')[0]}Name={name}"
                and "Possession" not in line)


def areas(lines):
    """Append AREAS after the last area (in the native key order of an empty one) and link each to its neighbour."""
    count_at = lines.index(next(line for line in lines if line.startswith("MapAreaCount=")))
    count = int(lines[count_at].split("=")[1])
    for name, a in AREAS:
        if any(line.endswith("Name="+name) and "Possession" not in line for line in lines): continue
        key = f"MapArea{count}"
        slots = [(a["neighbour"] if s == 0 else "", NOWHERE, NOWHERE) for s in range(5)]
        new = [f"[{key}]", f"{key}Name={name}", f"{key}SensitiveName={a['sensitive']}", f"{key}UL={position(*a['UL'])}",
                  f"{key}LR={position(*a['LR'])}", f"{key}TP={NOWHERE}", f"{key}Climate=1"]
        for s, (neighbour, lp0, lp1) in enumerate(slots):
            new += [f"{key}AdjacentAreaNames{s}={neighbour}", f"{key}AdjacentArea{s}LP0={lp0}", f"{key}AdjacentArea{s}LP1={lp1}"]
        new += [f"{key}IP{i}={position(*p)}" for i, p in enumerate(a["points"])]+[f"{key}PossessionCount=0"]
        end = len(lines)-1 if lines[-1] == "" else len(lines)                     # before the file's last line break
        lines[end:end] = new
        other = area_of(lines, a["neighbour"])
        free = next(i for i, line in enumerate(lines) if re.fullmatch(rf"{other}AdjacentAreaNames\d=", line))
        lines[free] += name
        count += 1
    lines[count_at] = f"MapAreaCount={count}"
    return lines


def regions(lines):
    """Append AREAS, then REGIONS to their areas (copies of TEMPLATE's block)."""
    lines = areas(lines)
    have = {line.split("=", 1)[1] for line in lines if re.match(r"MapArea\d+Possession\d+Name=", line)}
    source = next(line.split("Name=")[0] for line in lines if re.match(rf"MapArea\d+Possession\d+Name={TEMPLATE}$", line))
    block = [line[len(source):] for line in lines if line.startswith(source) and not line[len(source)].isdigit()]
    for area_name, name, owner, _, place, value, oil, base, battle, ports in REGIONS:
        if name in have: continue
        area = area_of(lines, area_name)
        count_at = next(i for i, line in enumerate(lines) if line.startswith(f"{area}PossessionCount="))
        count = int(lines[count_at].split("=")[1])
        last = max([i for i, line in enumerate(lines) if re.match(rf"{area}Possession{count-1}\D", line)] or [count_at])
        title, lon, lat = battle
        values = dict(Owner=owner, Location=position(*place), Name=name, Value=value, Oil=oil, BaseValue=base,
                      **({"WeatherZone": WEATHER[area_name]} if area_name in WEATHER else {}),
                      WM0Location=title, WM0CenterPoint=position(lon, lat),
                      WM0StartPoints0=position(lon+0.4, lat-0.2), WM0StartPoints1=position(lon-0.4, lat+0.2))
        for slot in range(6):
            port = ports[slot] if slot < len(ports) else None
            values.update({f"BaseLocs{slot}": position(*port[1:3]) if port else NOWHERE,
                           f"BaseENP{slot}": position(*port[3:5]) if port else NOWHERE,
                           f"BaseNames{slot}": port[0] if port else "Error", f"BaseSizes{slot}": port[5] if port else 0})
        for gun in range(8):
            values[f"CAPositions{gun}"] = position(*ports[gun][1:3]) if gun < len(ports) else NOWHERE
        new = [f"{area}Possession{count}{k}={values.get(k, v)}" for k, v in (line.split("=", 1) for line in block)]
        lines[last+1:last+1] = new
        lines[count_at] = f"{area}PossessionCount={count+1}"
    return lines


def year_map(text):
    """A short-format year map (MapData1920.dat) with REGIONS appended under their 1920 owners. Year maps name the
    possessions they change, so the area is found by a native possession of it."""
    lines = text.split("\r\n")
    native = {"The Mediterranean": "Malta", "Indian Ocean": "Ceylon", "The Caribbean": "Jamaica", "Northern Europe": "Norway"}
    for index, (name, _) in enumerate(AREAS):                     # new areas after the native sixteen (0-15)
        native[name] = key = f"MapArea{16+index}"
        if not any(line.startswith(key) for line in lines):
            lines[-1:-1] = [f"{key}MineLevel{i}=0" for i in range(7)]+[f"{key}PossessionCount=0"]
    for area_name, name, _, owner, place, value, oil, base, battle, ports in REGIONS:
        if any(line.endswith("Name="+name) for line in lines): continue
        area = native[area_name] if native[area_name].startswith("MapArea") else \
            next(line.split("Possession")[0] for line in lines if line.endswith("Name="+native[area_name]))
        count_at = next(i for i, line in enumerate(lines) if line.startswith(f"{area}PossessionCount="))
        count = int(lines[count_at].split("=")[1])
        last = max([i for i, line in enumerate(lines) if re.match(rf"{area}Possession{count-1}\D", line)] or [count_at])
        key = f"{area}Possession{count}"
        lines[last+1:last+1] = [f"{key}Owner={owner}", f"{key}Name={name}", f"{key}Value={value}",
                                f"{key}Oil={oil}", f"{key}BaseValue={base}", f"{key}Rebellion=0", f"{key}Invaded=-1",
                                f"{key}InvasionSupport=0", f"{key}BuildingBase=0", f"{key}TakenFrom=-1"]
        lines[count_at] = f"{area}PossessionCount={count+1}"
    return "\r\n".join(lines)


def add(text):
    lines = regions(text.split("\r\n"))
    index = {line.split("=", 1)[0]: i for i, line in enumerate(lines) if "=" in line}
    keys = {line.split("=", 1)[1]: line.split("Name=")[0] for line in lines if re.match(r"MapArea\d+Possession\d+Name=", line)}
    fields = lambda slot: ["BaseLocs", "BaseENP", "BaseEP", *(f"BaseNP{slot}{n}" for n in range(4)), "BaseNames", "BaseSizes"]
    for possession, gone in MOVED.items():
        key = keys[possession]
        slot_of = lambda slot: [lines[index[f"{key}{f}{slot}" if not f.startswith("BaseNP") else key+f]].split("=", 1)[1]
                                for f in fields(slot)]
        kept = [slot_of(s) for s in range(6) if slot_of(s)[-2] not in gone+("Error",)]
        empty = [NOWHERE]*7+["Error", "0"]
        for slot in range(6):
            for f, value in zip(fields(slot), kept[slot] if slot < len(kept) else empty):
                name = f"{key}{f}{slot}" if not f.startswith("BaseNP") else key+f
                lines[index[name]] = f"{name}={value}"
    for possession, ports in PORTS.items():
        key = keys[possession]
        names = [lines[index[f"{key}BaseNames{slot}"]].split("=", 1)[1] for slot in range(6)]
        for port, lon, lat, exit_lon, exit_lat in ports:
            if port in names: continue
            slot = names.index("Error"); names[slot] = port
            for field, value in (("BaseLocs", position(lon, lat)), ("BaseENP", position(exit_lon, exit_lat)),
                                 ("BaseNames", port), ("BaseSizes", SIZE)):
                lines[index[f"{key}{field}{slot}"]] = f"{key}{field}{slot}={value}"
    return "\r\n".join(lines)


if __name__ == "__main__":
    path = Path(sys.argv[1])
    path.write_bytes(add(path.read_bytes().decode("latin-1")).encode("latin-1"))   # byte for byte: mixed encodings
    if len(sys.argv) > 2:
        Path(sys.argv[3]).write_bytes(year_map(Path(sys.argv[2]).read_bytes().decode("latin-1")).encode("latin-1"))

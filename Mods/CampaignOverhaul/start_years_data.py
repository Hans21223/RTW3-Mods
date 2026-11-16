"""Nation (Data/BNat<year>.dat) and possession (Data/MapData<year>.dat) files for the later start years, written
from the game's own 1935 nations and 1920 possessions with the state of each nation on 1 January of that year.

Nations: governments (0 liberal democracy, 1 limited democracy, 2 autocracy, 4 fascist, 5 communist), leaders,
parliaments, ensigns (a republic with HadRevolution=1 flies its FlagFileNameR), naval chiefs, economy
(BaseResources) and the navy's share of it (BudgetModifier), largest docks, Cold War friends and enemies. In 2000
the Soviet Union is the Russian Federation (Russian, President, Duma, St Andrew's ensign) but keeps its name:
nation names key the game's per-nation files (<name>WarInfo20.dat, ship and officer names) and every other
nation's war data, and the game's RussiaWarInfo20.dat is incomplete. Austria-Hungary stays the game's own
alternate-history state.
Possessions: owners after the post-war settlements and decolonisation; "Neutral" is independent. Dominions
(Canada, Australia, New Zealand, South Africa) stay British, as in the game's 1935 world, until 1960.

The package files are written from these by coldwar_data.py (1947-1980: Cold War blocs) and superstates_data.py
(2000: superstates), which put fictional blocs in the nation slots.
"""
import re

YEARS = (1947, 1960, 1980, 2000)
DEFEATED = ("Germany", "Italy", "Japan")
POSTWAR = {   # every later year
    "Germany": dict(GovernmentType=0, GovernmentChange=0, Leader="Chancellor", ParliamentName="the Bundestag",
                    HadRevolution=1, FlagFileNameR="GermanyR2.bmp", LiberalDemocracy=1, Autocracy=0, IP=None),
    "Italy": dict(GovernmentType=0, GovernmentChange=0, Leader="Prime Minister", HadRevolution=1,
                  FlagFileNameR="ItalyR.bmp", LiberalDemocracy=1, IP=None),
    "Japan": dict(GovernmentType=0, GovernmentChange=0, Leader="Prime Minister", HadRevolution=1,
                  FlagFileNameR="JapanR.bmp", LiberalDemocracy=1, Kamikaze=0, Colonies=0, IP=None),
    "France": dict(GovernmentChange=0),
    "Great Britain": dict(IP=None),
    "Austria-Hungary": dict(Enemy1=None, Enemy2=None),
}
# year: nation: changes. Economies scale with each nation's share of world output (the leading navy near 60,000-
# 95,000, the range natural campaigns reach); BudgetModifier is the navy's share (minimum 3).
NATIONS = {
    1947: {
        "Germany": dict(AdmiralName="Ruge", BaseResources=12000, BudgetModifier=3, HBR=12, DockSize=40000),
        "Italy": dict(AdmiralName="Ferreri", BaseResources=12000, BudgetModifier=5, HBR=12, DockSize=45000),
        "Japan": dict(AdmiralName="Nomura", BaseResources=10000, BudgetModifier=3, HBR=10, DockSize=70000),
        "Great Britain": dict(AdmiralName="Cunningham", BaseResources=32000, BudgetModifier=14, HBR=32,
                              DockSize=50000, GlobalNavalPower=1, Friend="USA"),
        "France": dict(AdmiralName="Lemonnier", BaseResources=20000, BudgetModifier=10, HBR=20, DockSize=40000,
                       Friend="Great Britain"),
        "Soviet Union": dict(AdmiralName="Yumashev", BaseResources=35000, BudgetModifier=8, HBR=35, DockSize=40000,
                             ParliamentName="the Supreme Soviet", Enemy1="USA", Enemy2="Great Britain"),
        "USA": dict(AdmiralName="Nimitz", BaseResources=60000, BudgetModifier=12, HBR=60, DockSize=60000,
                    GlobalNavalPower=1, Friend="Great Britain", Enemy1="Soviet Union"),
        "Spain": dict(GovernmentType=4, GovernmentChange=1, LeaderF="Generalissimo", FlagFileNameF="SpainF.bmp",
                      AdmiralName="Regalado", BaseResources=6000, BudgetModifier=8, HBR=6, DockSize=15000),
        "China": dict(GovernmentType=2, GovernmentChange=5, Leader="Generalissimo", FlagFileName="Kuomintang.bmp",
                      AdmiralName="Chen Shaokuan", BaseResources=12000, BudgetModifier=6, HBR=12, DockSize=10000,
                      Friend="USA", Enemy1=None),
        "Austria-Hungary": dict(BaseResources=8000, HBR=8),
    },
    1960: {
        "Germany": dict(AdmiralName="Ruge", BaseResources=34000, BudgetModifier=5, HBR=34, DockSize=40000,
                        Friend="USA", Enemy1="Soviet Union"),
        "Italy": dict(AdmiralName="Pecori Giraldi", BaseResources=24000, BudgetModifier=7, HBR=24, DockSize=45000,
                      Friend="USA"),
        "Japan": dict(AdmiralName="Nagasawa", BaseResources=28000, BudgetModifier=4, HBR=28, DockSize=70000,
                      Friend="USA"),
        "Great Britain": dict(AdmiralName="Lambe", BaseResources=34000, BudgetModifier=12, HBR=34, DockSize=55000,
                              GlobalNavalPower=1, Friend="USA", Enemy1="Soviet Union"),
        "France": dict(AdmiralName="Cabanier", BaseResources=28000, BudgetModifier=11, HBR=28, DockSize=45000,
                       Friend="USA"),
        "Soviet Union": dict(AdmiralName="Gorshkov", BaseResources=50000, BudgetModifier=10, HBR=50, DockSize=50000,
                             LeaderC="First Secretary", ParliamentName="the Supreme Soviet", Friend="China",
                             Enemy1="USA", Enemy2="Germany"),
        "USA": dict(AdmiralName="Burke", BaseResources=75000, BudgetModifier=12, HBR=75, DockSize=90000,
                    GlobalNavalPower=1, Friend="Great Britain", Enemy1="Soviet Union", Enemy2="China"),
        "Spain": dict(GovernmentType=4, GovernmentChange=1, LeaderF="Generalissimo", FlagFileNameF="SpainF.bmp",
                      AdmiralName="Abarzuza", BaseResources=9000, BudgetModifier=7, HBR=9, DockSize=20000,
                      Friend="USA"),
        "China": dict(GovernmentType=5, LeaderC="Chairman", ParliamentName="the National People's Congress",
                      FlagFileNameC="PRC.bmp", AdmiralName="Xiao Jinguang", BaseResources=25000, BudgetModifier=6,
                      HBR=25, DockSize=15000, Friend="Soviet Union", Enemy1="USA", Enemy2="Japan"),
        "Austria-Hungary": dict(BaseResources=10000, HBR=10),
    },
    1980: {
        "Germany": dict(AdmiralName="Bethge", BaseResources=42000, BudgetModifier=5, HBR=42, DockSize=40000,
                        Friend="USA", Enemy1="Soviet Union"),
        "Italy": dict(AdmiralName="Torrisi", BaseResources=32000, BudgetModifier=7, HBR=32, DockSize=45000,
                      Friend="USA"),
        "Japan": dict(AdmiralName="Yada", BaseResources=50000, BudgetModifier=5, HBR=50, DockSize=100000,
                      Friend="USA", Enemy1="Soviet Union"),
        "Great Britain": dict(AdmiralName="Leach", BaseResources=32000, BudgetModifier=11, HBR=32, DockSize=55000,
                              GlobalNavalPower=0, Friend="USA", Enemy1="Soviet Union"),
        "France": dict(AdmiralName="Lannuzel", BaseResources=36000, BudgetModifier=10, HBR=36, DockSize=50000,
                       Colonies=0, Friend="Germany", IP=None),
        "Soviet Union": dict(AdmiralName="Gorshkov", BaseResources=60000, BudgetModifier=12, HBR=60, DockSize=70000,
                             ParliamentName="the Supreme Soviet", GlobalNavalPower=1, Enemy1="USA", Enemy2="China"),
        "USA": dict(AdmiralName="Hayward", BaseResources=85000, BudgetModifier=12, HBR=85, DockSize=100000,
                    GlobalNavalPower=1, Friend="Great Britain", Enemy1="Soviet Union"),
        "Spain": dict(GovernmentType=0, GovernmentChange=0, Leader="Prime Minister", LiberalDemocracy=1,
                      FlagFileName="Spain.bmp", AdmiralName="Arevalo", BaseResources=15000, BudgetModifier=7,
                      HBR=15, DockSize=30000, Friend="USA"),
        "China": dict(GovernmentType=5, LeaderC="Chairman", ParliamentName="the National People's Congress",
                      FlagFileNameC="PRC.bmp", AdmiralName="Ye Fei", BaseResources=35000, BudgetModifier=6, HBR=35,
                      DockSize=30000, Friend=None, Enemy1="Soviet Union", Enemy2=None),
        "Austria-Hungary": dict(BaseResources=12000, HBR=12),
    },
    2000: {
        "Germany": dict(AdmiralName="Lussow", BaseResources=42000, BudgetModifier=4, HBR=42, DockSize=40000,
                        Friend="France"),
        "Italy": dict(AdmiralName="Guarnieri", BaseResources=34000, BudgetModifier=6, HBR=34, DockSize=45000,
                      Friend="USA"),
        "Japan": dict(AdmiralName="Ishikawa", BaseResources=52000, BudgetModifier=5, HBR=52, DockSize=100000,
                      Friend="USA", Enemy1="China"),
        "Great Britain": dict(AdmiralName="Boyce", BaseResources=38000, BudgetModifier=10, HBR=38, DockSize=65000,
                              GlobalNavalPower=0, Friend="USA"),
        "France": dict(AdmiralName="Battet", BaseResources=38000, BudgetModifier=9, HBR=38, DockSize=50000,
                       Colonies=0, Friend="Germany", IP=None),
        "Soviet Union": dict(Name2="Russian", GovernmentType=1, GovernmentChange=2, Leader="President",
                             ParliamentName="the Duma", HadRevolution=1, FlagFileNameR="Russia.bmp",
                             AdmiralName="Kuroyedov", BaseResources=30000, BudgetModifier=7, HBR=30, DockSize=70000,
                             GlobalNavalPower=0, Friend=None, Enemy1=None, Enemy2=None, IP=None),
        "USA": dict(AdmiralName="Johnson", BaseResources=95000, BudgetModifier=12, HBR=95, DockSize=110000,
                    GlobalNavalPower=1, Friend="Great Britain", Enemy1=None),
        "Spain": dict(GovernmentType=0, GovernmentChange=0, Leader="Prime Minister", LiberalDemocracy=1,
                      FlagFileName="Spain.bmp", AdmiralName="Moreno Barbera", BaseResources=20000, BudgetModifier=6,
                      HBR=20, DockSize=40000, Friend="USA"),
        "China": dict(GovernmentType=5, LeaderC="President", ParliamentName="the National People's Congress",
                      FlagFileNameC="PRC.bmp", AdmiralName="Shi Yunsheng", BaseResources=60000, BudgetModifier=8,
                      HBR=60, DockSize=70000, Friend=None, Enemy1="USA", Enemy2="Japan"),
        "Austria-Hungary": dict(BaseResources=12000, HBR=12),
    },
}
# Economies from each nation's share of world output that year (Maddison GDP, the USA's value as the anchor), and
# the game's own growth modifier: GGP=1 adds 1% a year (HandleEconomicGrowth) for the fast-growing economies of
# the time. These replace the BaseResources above; BudgetModifier (the navy's share) stays.
ECONOMY = {   # nation: (BaseResources, GGP)
    1947: {"USA": (60000, 0), "Soviet Union": (17000, 1), "Great Britain": (15400, 0), "France": (7000, 1),
           "Germany": (8900, 1), "Italy": (6500, 1), "Japan": (5600, 1), "China": (11000, 0), "Spain": (2600, 0)},
    1960: {"USA": (70000, 0), "Soviet Union": (28800, 1), "Great Britain": (15500, 0), "France": (11800, 1),
           "Germany": (21800, 1), "Italy": (10100, 1), "Japan": (12800, 1), "China": (15100, 0), "Spain": (3400, 1)},
    1980: {"USA": (85000, 0), "Soviet Union": (34300, 0), "Great Britain": (14600, 0), "France": (16300, 0),
           "Germany": (25100, 0), "Italy": (14900, 0), "Japan": (31500, 1), "China": (21000, 1), "Spain": (6000, 1)},
    2000: {},   # the superstates set their own (superstates_data.py)
}
# Possession owners on 1 January, each year from the game's 1920 map. Later years build on earlier ones.
OWNERS = {1947: {
    "East Prussia": "Soviet Union", "Baltic States": "Soviet Union", "Sakhalin": "Soviet Union",
    "Liaotung Peninsula": "Soviet Union", "Northern Korea": "Soviet Union", "Southern Korea": "USA",
    "Libya": "Great Britain", "Eritrea": "Great Britain", "Rhodes": "Neutral", "The Philippines": "Neutral",
    "Formosa": "China", "Kiautschou Bay": "China", "Weihaiwei": "China", "Shanghai": "China", "Hainan": "China",
    "Kwang-Chou-Wan": "China", "Northern Marianas": "USA", "Caroline Islands": "USA", "Marshall Islands": "USA",
    "Haiti": "Neutral", "Syria": "Neutral", "Iraq": "Neutral"}}
OWNERS[1960] = {**OWNERS[1947], **dict.fromkeys((
    "India", "Burma", "Ceylon", "Libya", "Eritrea", "Egypt", "Tunisia", "Morocco", "Malaya", "Cochin China", "Annam",
    "Tonkin", "Northern Korea", "Southern Korea", "Formosa", "Cameroon", "Palestine", "Pakistan", "East Bengal",
    "Sudan", "Egyptian Red Sea Coast"),
    "Neutral"), "Liaotung Peninsula": "China"}
OWNERS[1980] = {**OWNERS[1960], **dict.fromkeys((
    "Senegal", "Middle Congo", "Madagascar", "Algeria", "Djibouti", "Nigeria", "Sierra Leone", "Tanganyika", "Kenya",
    "Zanzibar", "Yemen", "Singapore", "Cyprus", "Malta", "Jamaica", "Trinidad", "Grand Bahama", "New Providence",
    "Fiji", "Papua", "Solomon Islands", "Samoa", "Bismarck Archipelago", "Bougainville", "South Afriica",
    "Southwest Africa", "Western Australia", "Eastern Australia", "New Zealand", "British Columbia", "Nova Scotia",
    "New Brunswick", "Newfoundland", "Maldives", "Somalia", "Somaliland", "Kuwait", "Trucial States", "Oman"), "Neutral")}
OWNERS[2000] = {**OWNERS[1980], **dict.fromkeys((
    "Panama", "Baltic States", "Caroline Islands", "Marshall Islands", "New Hebrides", "Odessa", "Donbass", "Georgia"),
    "Neutral"), "Hong Kong": "China"}


def sections(text):
    """[(header line, [lines])] in file order; the part before the first header has header None."""
    out, header, lines = [], None, []
    for line in text.splitlines():
        if line.startswith("["):
            out.append((header, lines)); header, lines = line, []
        else:
            lines.append(line)
    out.append((header, lines))
    return out


def nation_name(lines):
    return next(line.split("=", 1)[1] for line in lines if line.startswith("Name="))


def edit(lines, changes):
    """Set every occurrence of each key (None removes it); keys the section lacks go after Name2."""
    out, done = [], set()
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else None
        if key in changes:
            done.add(key)
            if changes[key] is not None: out.append(f"{key}={changes[key]}")
            continue
        out.append(line)
    extra = [f"{k}={v}" for k, v in changes.items() if k not in done and v is not None]
    at = next((i+1 for i, line in enumerate(out) if line.startswith("Name2=")), len(out))
    return out[:at]+extra+out[at:]


def nations(text, year):
    """BNat<year>.dat from BNat1935.dat."""
    out = []
    for header, lines in sections(text):
        if header is not None:
            name = nation_name(lines)
            changes = {**POSTWAR.get(name, {}), **NATIONS[year].get(name, {})}
            if name in ECONOMY[year]:
                resources, growth = ECONOMY[year][name]
                changes.update(BaseResources=resources, HBR=resources//1000, GGP=growth)
            lines = edit(lines, changes)
            out.append(header)
        out.extend(lines)
    return "\r\n".join(out)+"\r\n"


def possessions(text, year):
    """MapData<year>.dat from MapData1920.dat: owners on 1 January of that year."""
    lines, owners = text.splitlines(), OWNERS[year]
    names = {m.group(1): line.split("=", 1)[1] for line in lines
             for m in [re.match(r"(MapArea\d+Possession\d+)Name=", line)] if m}
    unknown = set(owners)-set(names.values())
    if unknown: raise ValueError("Unknown possessions: "+", ".join(sorted(unknown)))
    out = []
    for line in lines:
        m = re.match(r"(MapArea\d+Possession\d+)Owner=(.*)", line)
        if m:
            line = f"{m.group(1)}Owner={owners.get(names[m.group(1)], m.group(2))}"
        out.append(line)
    return "\r\n".join(out)+"\r\n"

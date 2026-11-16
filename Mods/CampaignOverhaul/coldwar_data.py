"""The 1947, 1960 and 1980 starts: Cold War blocs and five minor powers in the game's ten nation slots.

Western Europe's navies are one bloc (European NATO: Britain, France, West Germany, Italy, Spain, with Greece,
Turkey, Norway and Iceland) and the Soviet Union and its allies another (Warsaw Pact). The five slots that frees
hold minor naval powers: India, Indonesia, Brazil, Argentina and Iran. The names stand for all three years, though
NATO dates from 1949 and the Warsaw Pact from 1955: the game finds a nation's war, ship-name and officer files by
its name alone, so a bloc has one name and one set of files (which is also why the United States, China and Japan
are named differently from the native nations and from the 2000 superstates).

superstates_data.py writes the files (see it for the rules: one home area a bloc, nine nations in a campaign).
Asian players' war files leave out Argentina, the others' Indonesia.
Land a bloc does not list follows that year's historical owner (start_years_data.py): colonies of the European
members belong to European NATO until they become independent.

Run:  python coldwar_data.py <game folder> <package Files folder>
"""
from pathlib import Path
import sys

import superstates_data as blocs

YEARS = (1947, 1960, 1980)
US, NATO, PACT, CHINA, JAPAN = "United States of America", "European NATO", "Warsaw Pact", "Communist China", "State of Japan"
INDIA, INDONESIA, BRAZIL, ARGENTINA, IRAN = "Republic of India", "Indonesia", "Brazil", "Argentina", "Iran"
ASIAN = (CHINA, JAPAN, INDIA, INDONESIA, IRAN)
VALUES = {**blocs.VALUES, "Germany": 100, "Turkey": 60}
LEGACY = {"Great Britain": NATO, "France": NATO, "Italy": NATO, "Germany": NATO, "Spain": NATO, "USA": US,
          "Soviet Union": PACT, "Russia": PACT, "China": CHINA, "Japan": JAPAN, "Austria-Hungary": "Neutral",
          "Optional": "Neutral"}
# slot nation: bloc. Economies (resources) are shares of world output against the USA's 60,000 / 70,000 / 85,000;
# a bloc without them keeps its slot's (start_years_data.ECONOMY), as it does admirals, docks and the navy's share.
BLOCS = {
    "USA": dict(
        name=US, adjective="American", flag="USN.bmp", government=0, leader="President", parliament="Congress",
        area="North American East Coast", trouble="in the Caribbean", friend=NATO, enemies=(PACT,),
        neighbours=("Cuba", "Grand Bahama", "Dominican Republic"), home=("Eastern USA",), other=(), source="USA", colonies=True,
        sea=blocs.BLOCS["USA"]["sea"], at={1960: dict(enemies=(PACT, CHINA))}),
    "Great Britain": dict(
        name=NATO, adjective="Allied", flag="NATO.bmp", government=0, leader="Secretary General",
        parliament="the North Atlantic Council", area="Northern Europe", trouble="in Berlin", friend=US,
        enemies=(PACT,), neighbours=("Albania", "Finland", "Dalmatia"), home=("United Kingdom",),
        other=("Norway", "Iceland", "Greece", "Turkey", "Northern Anatolia", "Macedonia", "Crete", "Cilicia",
               "The Netherlands", "ABC Islands"),
        sea=blocs.BLOCS["Germany"]["sea"]+(("Black Sea", 31.5, 42.6),), names="merge",
        **{"global": True}, colonies=True, resources=40000, growing=True,
        at={1960: dict(resources=62000), 1980: dict(resources=77000, growing=False)}),
    "Soviet Union": dict(
        name=PACT, adjective="Soviet", flag="Soviet Union.bmp", government=5, leader="General Secretary",
        parliament="the Supreme Soviet", area="The Baltic", trouble="in Hungary", friend=None, enemies=(US, NATO),
        neighbours=("Finland", "Norway", "Turkey"), home=("Western Russia",),
        other=("Eastern Germany", "East Prussia", "Baltic States", "Southern Russia", "Romania", "Bulgaria"),
        source="Soviet Union",
        sea=blocs.BLOCS["Soviet Union"]["sea"], resources=21000, growing=True,
        at={1960: dict(resources=35000, friend=CHINA), 1980: dict(resources=42000, growing=False,
                                                                  **{"global": True})}),
    "China": dict(
        name=CHINA, adjective="Chinese", flag="PRC.bmp", government=5, leader="Chairman",
        parliament="the National People's Congress", area="Northeast Asia", trouble="in the Taiwan Strait",
        friend=PACT, enemies=(), neighbours=("Northern Korea", "Formosa", "Tonkin"), home=("Northern China",),
        other=("Southern China",), source="China", sea=blocs.BLOCS["China"]["sea"],
        at={1960: dict(enemies=(US, JAPAN)), 1980: dict(friend=None, enemies=(PACT,))}),
    "Japan": dict(
        name=JAPAN, adjective="Japanese", flag="JapanR.bmp", government=0, leader="Prime Minister",
        parliament="the Diet", area="Northeast Asia", trouble="on the Korean peninsula", friend=US, enemies=(),
        neighbours=("Southern Korea", "Sakhalin", "Formosa"), home=("Japan",), other=("Hokkaido",), source="Japan",
        sea=blocs.BLOCS["Japan"]["sea"], at={1980: dict(enemies=(PACT,))}),
    "Austria-Hungary": dict(
        name=INDIA, adjective="Indian", flag="IndiaNavy.bmp", government=0, leader="Prime Minister",
        parliament="the Lok Sabha", admiral="Katari", resources=9000, growing=False, budget=4, dock=20000, area="Indian Ocean",
        trouble="in Kashmir", friend=None, enemies=(), neighbours=("Ceylon", "Burma", "Yemen"), home=("India",),
        other=("Andaman Islands",), bases={"India": 300}, sea=blocs.BLOCS["Austria-Hungary"]["sea"], ranks=True,
        pool="India",
        at={1960: dict(resources=11000, enemies=(CHINA,)),
            1980: dict(resources=13000, admiral="Pereira", dock=40000, friend=PACT, enemies=(CHINA,))}),
    "Germany": dict(
        name=INDONESIA, adjective="Indonesian", flag="Indonesia.bmp", government=2, leader="President",
        parliament="the People's Consultative Assembly", admiral="Subyakto", resources=2700, growing=False, budget=4, dock=10000,
        area="Southeast Asia", trouble="in Borneo", friend=None, enemies=(),
        neighbours=("Malaya", "Papua", "Singapore"), home=("Java",),
        other=("Sumatra", "Borneo", "Celebes and Moluccas"), bases={"Java": 200},
        sea=(("Java Sea", 112.0, -5.5), ("Celebes Sea", 122.0, 3.0), ("Banda Sea", 128.0, -5.5),
             ("off Sumatra", 97.0, -1.5)), ranks=True,
        at={1960: dict(resources=3300, admiral="Martadinata", friend=PACT, enemies=(NATO,)),
            1980: dict(resources=5500, admiral="Walujo", dock=20000, growing=True)}),
    "Spain": dict(
        name=BRAZIL, adjective="Brazilian", flag="Brazil.bmp", government=1, leader="President",
        parliament="the National Congress", admiral="Guillobel", resources=3700, budget=5, dock=30000,
        area="South American East Coast", trouble="on the River Plate", friend=US, enemies=(),
        neighbours=("Venezuela", "Trinidad", "Falkland Islands"), home=("Brazil",), other=(),
        sea=(("South Atlantic", -35.0, -18.0), ("off Recife", -32.5, -8.0), ("off Rio Grande", -49.0, -33.0)),
        ranks=True, growing=True,
        at={1960: dict(resources=5700, admiral="Matoso Maia"),
            1980: dict(resources=12800, admiral="Fonseca", government=2, dock=40000)}),
    "France": dict(
        name=ARGENTINA, adjective="Argentine", flag="Argentina.bmp", government=1, leader="President",
        parliament="the National Congress", admiral="Anadon", resources=3500, growing=False, budget=6, dock=30000,
        area="South American East Coast", trouble="in the Beagle Channel", friend=None, enemies=(),
        neighbours=("Falkland Islands", "Chile", "Peru"), home=("Argentina",), other=(),
        sea=(("Argentine Sea", -55.0, -40.0), ("off the River Plate", -54.0, -36.5), ("off Patagonia", -62.0, -47.0)),
        ranks=True,
        at={1960: dict(resources=3900, admiral="Vago"),
            1980: dict(resources=4700, admiral="Lambruschini", government=2, enemies=(NATO,))}),
    "Italy": dict(
        name=IRAN, adjective="Iranian", flag="Iran.bmp", government=2, leader="Shah", parliament="the Majlis",
        admiral="Bayandor", resources=2500, growing=False, budget=4, dock=10000, area="Indian Ocean", trouble="in the Gulf",
        friend=US, enemies=(), neighbours=("Yemen", "Egypt", "Ceylon"), home=("Persia",), other=(),
        sea=(("Gulf of Oman", 61.0, 23.5), ("off Makran", 62.5, 24.3), ("Arabian Sea", 64.0, 20.0)), ranks=True,
        at={1960: dict(admiral="Rasai", growing=True),
            1980: dict(resources=3100, growing=False, admiral="Madani", dock=30000, leader="President", friend=None, enemies=(US,))}),
}
BY_NAME = {b["name"]: b for b in BLOCS.values()}
WORLD = dict(blocs=BLOCS, values=VALUES, legacy=LEGACY, asian=ASIAN, growing=None, colonies=None,
             skip=(ARGENTINA, INDONESIA))


def flags(target):
    """60x40 ensigns drawn for the mod (national colours and simple emblems)."""
    from PIL import Image, ImageDraw
    target.mkdir(parents=True, exist_ok=True)

    def canvas(colour):
        picture = Image.new("RGB", (240, 160), colour)
        return picture, ImageDraw.Draw(picture)

    def save(picture, name):
        picture.resize((60, 40), Image.LANCZOS).save(target/name)

    p, d = canvas((0, 73, 144))                                              # NATO: white compass on blue
    d.ellipse((85, 45, 155, 115), outline=(255, 255, 255), width=5)
    d.polygon(((120, 20), (130, 80), (120, 140), (110, 80)), fill=(255, 255, 255))
    d.polygon(((60, 80), (120, 70), (180, 80), (120, 90)), fill=(255, 255, 255))
    save(p, "NATO.bmp")
    p, d = canvas((255, 255, 255)); d.rectangle((0, 0, 240, 80), fill=(206, 17, 38))   # Indonesia: red over white
    save(p, "Indonesia.bmp")
    p, d = canvas((0, 156, 59))                                              # Brazil
    d.polygon(((120, 14), (222, 80), (120, 146), (18, 80)), fill=(255, 223, 0))
    d.ellipse((84, 44, 156, 116), fill=(0, 39, 118)); d.arc((70, 62, 176, 150), 200, 320, fill=(255, 255, 255), width=6)
    save(p, "Brazil.bmp")
    p, d = canvas((255, 255, 255))                                           # Argentina
    d.rectangle((0, 0, 240, 53), fill=(116, 172, 223)); d.rectangle((0, 107, 240, 160), fill=(116, 172, 223))
    d.ellipse((104, 64, 136, 96), fill=(246, 180, 14))
    save(p, "Argentina.bmp")
    p, d = canvas((255, 255, 255))                                           # Iran: green, white, red
    d.rectangle((0, 0, 240, 53), fill=(35, 159, 64)); d.rectangle((0, 107, 240, 160), fill=(218, 0, 0))
    d.ellipse((106, 66, 134, 94), fill=(218, 165, 32))
    save(p, "Iran.bmp")


def write(game, files):
    made = blocs.write(game, files, world=WORLD, when=YEARS)
    flags(Path(files)/"Flags")
    return made


if __name__ == "__main__":
    print("\n".join(write(*sys.argv[1:])))

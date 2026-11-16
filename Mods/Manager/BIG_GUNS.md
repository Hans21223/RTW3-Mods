# Big Guns: calibres to 40 inches

Runtime adapter `big-guns` (`CampaignOverhaul/big_guns.py`), attached through Play with mods at the title screen.
It refuses to attach once a campaign or nation is loaded, and stays attached while nations exist.

## What changes

- **Gun data.** The battle table (penetration, rate of fire, maximum range) moves to a block for 2-40 in. Rows
  21-40 come from `Data/Gundata.dat`, `VerPen.dat` and `HorPen.dat`, converted the way the native loader does.
- **Nations.** Each nation's gun level per calibre (-2..2 developed, 9 not yet) moves past the native object to
  hold 2-40. Saves write `Guns2`-`Guns40`; older saves read 21-40 as 9.
- **Research.** The first undeveloped calibre is researched as before. Above 20 in it also waits for
  1943 + 3 per inch above 21, through the game's research-speed year scaling (40 in: 2000). The treaty limit
  and the native 13-16 in gates still apply. Buying technology and the AI's largest-calibre choice reach 40.
  Live Cheats' Research ALL maximizes 2-40 in. One gun improvement in four goes to a developed 21-40 in gun below
  the best quality (the native picks stop at 17 in). Spies steal 2-40 in gun quality where theft is on (Campaign
  Security turns it off).
- **AI design.** AI battleships upsize their main guns one inch at a time past the native 16 in stop only while the
  nation's monthly balance is positive and its cash holds two months of budget; spare tonnage, development, quality
  and treaty checks stay native, and the AI calibre setter and battleship cap go to 40.
- **Designer.** The main calibre box goes to 40. Gun and turret weight, cost and shell weight for 21-40 come from
  `Data/OrdnanceTable40.dat` (same columns as `OrdnanceTable.dat`; the native loader warns about rows above 20,
  so they live apart). Crew per gun, the overgunned and wing-position minimum displacements and the
  low-ammunition note treat 21-40 in as bigger than 20 in instead of falling to their defaults. The ship type
  rules (a battleship needs 3+ main turrets or 8+ main guns) count a gun above 20 in as (calibre/20)^3 guns, its
  shell weight against a 20 in gun: one 39 in gun counts as 7, two as 14, so two big guns make a battleship.
- **Battle.** The game uses calibres 30-33 as missile codes, and the railgun adapter's super-heavy missile hits
  as 40. Only shells fired by FireGuns use the extended tables above 20 in; missiles and bombs keep the native
  20 in penetration clamp and code conversion, and the damage log names a big shell's real calibre.
- Other adapters' audits read these changes back as native code (`modern_research.normalize`), and the
  live-cheats research button finds the gun levels wherever they are.

## Not changed

Dispersion problems exist for 8-20 in only. Secondary and tertiary calibres keep their
native maximums. The HE penetration helper gives shells above 20 in the missile warhead bonus when a nation has
it. Turret pictures, long campaigns and AI designs with 21-40 in guns are unverified in play.

## Tests

`Manager/test_big_guns.py` runs the game's own code in an emulator: the table reads and clamps, nation creation,
save and load to 40 in, custom-battle years, the largest-calibre lookup, research year gates, the designer cost,
crew and overgunned rules, the battle hooks for shells against missiles, and other adapters' audits.

# Research, aircraft and campaign quality of life

## In-game research display and cheats

With **Live Cheats** enabled, launch using **Play with mods**. The floating
**CHEATS / F10** control shows completed / installed technologies and a progress
bar. It refreshes about every eight seconds while the game is active, without
scanning fleets or changing campaign data. This is a companion overlay, not a
replacement native research screen.

Open F10 and refresh after loading a campaign. The technology card also has a
branch selector with completed / total counts and percentages. Gun quality is
separate from this invention count. Only populated native technology slots are
counted; unused research slots are not inventions. Native randomized years and
slot ordering are supported.

- **Research ALL technologies**: immediately grants the player's nation all
  installed inventions, including future-dated inventions, and quality +2 for
  2-20 inch guns. It covers the 572-invention baseline or 655-invention expanded
  pack when that pack is installed and loaded. It does not enable disabled mods,
  grant inventions to opponents, change existing ships or aircraft, or create
  simulation mechanics for unsupported weapons. Existing research priorities
  and points remain intact; the engine advances its normal research cursors.
- **Fast aircraft requests (1 turn)**: immediately sets an existing request
  countdown and developing player-owned aircraft prototypes to one remaining
  campaign turn. Opponent aircraft and already completed models are unchanged.
  It does not create a request, choose a prototype, or eliminate native random
  delays. Advance the campaign normally to process completion.

These buttons apply only their own action: no extra Apply click is needed and
unrelated pending edits remain pending. Use a separate test save, then save
normally in RTW3 if you want to retain changes. No save file is edited directly.
Research ALL is live-only; the saved-game advanced editor still treats invention
flags as read-only. An already-attached version-2 live session can use these
actions after reopening the updated panel; older dispatchers need a restart.

## Specific prompt automation

The optional **Campaign QoL - Automatic Prompts and Bounded AI Shipbuilding**
package requires a restart through **Play with mods** before loading a campaign.

- The final air-strike target adjustment confirmation automatically takes
  **No**, keeping the strike's existing target location.
- When AI ship or class name suggestions are exhausted, the native generated
  fallback name is accepted, as if the user pressed OK. The game supplies the
  nation/type/fleet-count name; this mod does not invent a new naming database.

Only these exact native call sites are automated. Other confirmations, manual
target selection, player naming dialogs and aircraft choices remain interactive.
Disable the package and restart to restore those prompts.

## Mouse wheel in the ship designer

Point at a box in the ship designer and turn the mouse wheel; no click is
needed, and the box only changes while the pointer is over it:

- number boxes (displacement, speed, calibres, gun counts and the others) step
  by the box's own step;
- the drop-down lists step one item: the armour lists (belt, deck, conning
  tower, turrets and the others) one thickness, and the text lists too
  (accommodation, freeboard, range, belt coverage, propulsion, engine priority,
  fire control, turret era and style);
- small up/down arrow buttons (500-ton displacement steps, flight deck armour,
  sponson radius, the superstructure editor) click once per notch.

Up when the wheel turns away from you; hold **Shift** for ten steps. Changes go
through the control itself, so the game's limits apply and the design
recalculates as if you had clicked. Over the ship picture the wheel still zooms.
Ship type and nation ignore it: changing them rebuilds the design, so a stray
turn of the wheel never does. The designer installs the
handler each time it opens, unless the form already has another one.

Hold the **middle mouse button** and drag over the ship picture to pan it (the
picture is a globe view; this turns on its own drag-rotation for the middle
button). The wheel still zooms there.

## Invasions

With `invade_possessions` at 1 (the default), the invasion buttons accept any
possession except a nation's main home region: United Kingdom, Germany, Western
France, Northwestern Spain, Italian West Coast, Austria-Hungary, Japan, Western
Russia, Eastern USA, Northern China, Turkey, Argentina, Brazil and Persia.
Natively every possession worth 10 or more (all home regions and the big
colonies) was closed. Second home regions (Southern France, Western USA, the
Russian Far East and others) can now be invaded, and invading a home area no
longer needs your nation to be blockaded. The invasion range check, which also
closed possessions worth more than 10, follows the same rule for the two
invasion buttons; the distance limit, the already-invaded check and the AI's
own invasion planning stay native. The possession window's "Set invasion
target" button and the monthly invasion check (which dropped any target worth
more than 15) follow the same rule.

**Peace terms.** After a won war, the "Select possessions as part of peace
agreement" list natively offered only possessions worth 10 or less, so big
colonies such as Western Australia (15) never appeared. It now offers the same
possessions you may invade: any but a main home region. The game's other rules
stay: the area must be next to your own possessions, and the total value you
pick must fit what the peace allows.

**Colonising.** Neutral possessions can be set as invasion targets too (the
button was greyed out for them). Each turn the landing needs good weather, the
native blockade rule, more than the native minimum naval force in the sea area,
and more strength there than any enemy fleets. There is no owner fleet to fight,
so no invasion battle. On landing the possession becomes yours outright (owner
and saved owner name, so it stays yours after loading), and you can build bases
and forts there. The landing message calls it a "Local possession"; that is the
game's own word for unowned land.

Set `invade_possessions` to 0 in the package manifest for the native rules.

**Invasions fit the owner** (always on, 0.12.1). The game turned a battle with
no ships on one side into an invasion of the battle's possession whoever owned
it, and the turn's land fighting treated every possession an enemy attacked as
yours. An East Asian Federation player was told "With our fleet unable to
interfere, enemy troops invade Weihaiwei!" for a Chinese possession; China then
fought itself there ("Chinese troops are resisting attacks by Chinese forces"),
and a Chinese win would have cost the player the defeat's unrest. Now the enemy
lands (unopposed or after winning a battle) only on your possessions, you are
offered a surprise landing only at a possession of a nation at war with you,
and an enemy's land fight at a possession you do not own ends at the next turn,
which also clears such fights in existing saves.

**New possessions.** The South American West Coast sea area had no
possessions. The package's `Data/MapData.dat` adds two neutral ones there:
Chile (bases Valparaiso and Talcahuano, value 6) and Peru (base Callao, value 5,
oil). Each has coastal fort positions and one generic battle setup, like
Argentina and Brazil. Saves name possessions rather than numbering them, so
running campaigns get them too, as neutral land you can colonise. The map
positions are hand-placed from real coordinates and have not been checked
in-game yet.

**More ports.** Unused base slots of existing possessions hold new ports
(`map_ports.py`): Calcutta, Cochin, Vizagapatam and Karachi in India, Galle in
Ceylon, Bushehr with Persia, Mersa Matruh in Egypt, Marmaris and Canakkale in
Turkey, Hodeida and Mukalla in Yemen, Changi, Semarang,
Belawan, Padang, Brunei, Kuching, Kuantan, Akyab, Moulmein and Saigon in
Southeast Asia. Positions are from real coordinates, not checked in-game.

**The Black Sea.** Since Campaign QoL 0.10.0 it is its own seventeenth sea
area, linked to the Mediterranean, the way the community Ottoman mod adds it.
The map file holds its own area count and the game keeps its areas in a list,
so no code changes; the Mediterranean is back to its native box. Its regions
(`map_ports.py`, copies of Chile's data block with one plain meeting battle
each):

- Southern Russia, now the Crimea: Sevastopol, Eupatoria, Feodosia, Kerch.
  Russian in the 1890 and 1900 starts, Soviet in 1920 and 1935 (the package
  ships `MapData1920.dat` with it), Warsaw Pact in 1947-1980, Russian
  Federation in 2000.
- From 0.11.0, as in the Ottoman mod: Odessa (Odessa, Nikolaev, Kherson), Kuban
  (Novorossiysk, Sochi), Georgia (Batum, Poti, Sukhum), Donbass (Mariupol,
  Berdyansk) and Rostov (Taganrog, Yeysk), the last two on the Sea of Azov.
  Russian, Soviet and Warsaw Pact like Southern Russia; in 2000 Kuban and
  Rostov are the Russian Federation's, Odessa, Donbass and Georgia neutral.
- Romania (Constanta) and Bulgaria (Varna, Burgas): neutral, Warsaw Pact in
  1947-1980.
- Northern Anatolia (Sinop, Samsun, Trabzon, Eregli, Constantinople): neutral
  until 1935, then with Turkey: European NATO in 1947-1980, the Middle East
  Federation in 2000.

The Warsaw Pact, Russian Federation, European NATO and Middle East Federation
battle files have Black Sea meetings. The native nations' battle files do not,
so in the 1890-1935 starts the Black Sea has bases, invasions and the
regions' own battle, but no scripted fleet actions. Ships move between the
Black Sea and the Mediterranean like between any two neighbouring areas; the
Turkish straits are not modelled.

Saves: a save loads its areas by number and their regions by name in list
order. A region a save does not have yet gets its 1890 owner, and the game
itself turns an owner name that no nation of that campaign has into Neutral
("Russia" becomes the Soviet Union first). So in older 1890-1935 campaigns the
new regions have their 1890 owners, and in older Cold War and 2000 campaigns
they are neutral. The Mediterranean's Syria and Palestine keep their saved
owners only if the save never had the old Black Sea regions (those were made
between 12 and 13 November 2026).

**More regions in the Middle East and South Asia** (same method as the Black
Sea ones): Syria (Latakia, Beirut) and Palestine (Haifa) in the Mediterranean;
Iraq (Fao), Arabia (Jeddah, Yanbu, Al-Qunfudhah), Pakistan (Karachi, Ormara), East
Bengal (Chittagong), the Andaman Islands (Port Blair) and the Maldives (Gan)
in the Indian Ocean. India's sixth port is now Goa. Owners: neutral or British
in 1890-1900; in 1920 Syria is French and Palestine and Iraq British; later
years follow independence; in 2000 the Middle East Federation and India hold
them.

**Regions from the Ottoman mod** (Campaign QoL 0.11.0, same method; the
community mod's Ottoman Empire is Neutral here, its Hejaz is Arabia and its
South Yemen is Yemen). Macedonia (Thessaloniki, Kavala, Dedeagach), Cilicia
(Mersin, Alexandretta) and Crete (Heraklion, Souda Bay) in the Mediterranean;
Kuwait, Al-Ahsa (Dammam, Jubail), the Trucial States (Abu Dhabi, Dubai,
Bahrain, Doha), Oman (Muscat), Somalia (Mogadishu, Kismayo), Somaliland
(Berbera), Sudan (Port Sudan, Suakin) and the Egyptian Red Sea Coast (Suez,
Hurghada, Quseir) in the Indian Ocean; the ABC Islands (Willemstad,
Oranjestad, Kralendijk) in the Caribbean; the Netherlands (Den Helder,
Rotterdam, Vlissingen) in Northern Europe; and the Black Sea ones above.
Owners in 1890: neutral, except the British Gulf, Somaliland, Sudan and Red
Sea coasts and Italian Somalia. Later years follow independence; in the Cold
War European NATO holds the Greek, Turkish and Dutch ones, in 2000 the
European Union, the Middle East Federation and the United African States.
Ports a region takes leave their old possession (Greece's Heraklion and
Thessaloniki, Turkey's Alexandretta, and the earlier Kuwait, Dammam, Bahrain,
Muscat, Suez and Mersin), so no port is on the map twice. Saves keep regions
and coastal batteries by name, not ports, so moving a port is safe.

**Dock size.** The Build button next to Dock size works until the dock is
200,000 tons (the game stops at 90,000). One compare in the dock builder is
changed; cost and time per step are the game's own.

**Home areas.** A main home region is closed to invasion only while it is a
home area (possession value 200). India, Java and South Africa join the list
for the 2000 superstates, where each bloc has one home area.

## Bounded AI shipbuilding

The same QoL package limits normal AI procurement evaluations to once every
28 campaign days. This avoids running the entire monthly purchasing routine on
every seven-day calendar turn. Emergency replacement paths retain their native
cadence but share the new-order caps below.

New AI construction orders are refused while that nation has any of:

- 400 or more non-sunk/non-scrapped ships, including ships under construction;
- 24 or more active construction or major-rebuild projects;
- negative funds.

Existing ships are not removed, and existing yard projects continue normally.
The player and the native initial-fleet construction routine are exempt.
An already oversized AI fleet must shrink naturally before new orders resume.
Ordinary repairs/refits do not count as new construction projects. This is a
bounded procurement rule, not a full economic rebalance or a measured guarantee
of campaign balance/performance. Other weekly economy/research timers remain
per-turn unless another mod explicitly changes them.

**Government building programme.** The government sets a programme: a number
of ships of one type (or group: B, BB or BC; CL or CA) to have under
construction when it is reviewed, with praise if you do and a reprimand and
prestige loss if not. The game counted any ship of the type, so a token hull
of a few thousand tons satisfied it. Since 0.12.0 a ship counts only if it
displaces at least `build_programme_min_percent` (60) percent of the average
displacement of that type's ships in service in the whole world, rounded down
to 100 t, and never more than 90% of your largest dock. The review, the
warning a month before and the main screen line use the same rule; the line
shows the minimum, for example " Must have 2 B, BB or BC (24,000 t or more)
building". Submarines count as before. Cancelled and refitting ships count as
natively. Computer nations have no programme.

Defaults are configurable in `Mods/Library/campaign-qol/mod.json` under `runtime`:

| Setting | Default | Allowed range |
| --- | ---: | --- |
| `max_active_ships` | 400 | 50-10000 |
| `max_building_ships` | 24 | 1-1000 |
| `min_procurement_days` | 28 | 1-90 |
| `invade_possessions` | 1 | 0-1 |
| `build_programme_min_percent` | 60 | 0-100 (0: native rule) |

Settings take effect on the next launch. Disable the package and restart to
restore native purchasing. Hooks are session-only and refuse unknown code.
Neither this package nor the cheats change the executable on disk or the
separate official Steam installation.

## Verification boundary

Isolated emulator tests cover full-tree atomic transactions, stale guards,
player-only aircraft countdowns, procurement cadence, caps, initial-fleet and
player exemptions, relocated addresses and both prompt stack contracts. UI
fixtures test direct button actions, pending-edit preservation and progress
rendering. A title-screen startup check also verified all five installed QoL
hooks, all three generated rule-code blocks, the research/aircraft layout and
the existing security hooks by readback. No campaign was loaded or cheat sent.
Real campaign cheats are not applied during verification; aircraft
completion, multi-year AI balance and battle prompt behavior still need gameplay
testing in a separate campaign.

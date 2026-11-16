# Frigate Type (Test) - New Ship Type 15

A separate, experimental test mod. It adds the **Frigate (FF)** as a true new ship
type number, 15, next to the game's fifteen types (BB 0 ... SS 14). It needs
Expanded Timeline 1.31.0 or later and attaches after every other runtime mod.

## What you get

- **Designer.** The Ship type list gains **FF - Frigate**. A design of that type
  is stored with type 15 and saved as `ShipType=FF`.
- **Its own name.** Type 15 reads **FF** on the ship window, in two ship lists, in
  four kinds of news text and in saved designs and ships.
- **Corvettes stay corvettes.** Expanded Timeline's renaming of KE to FF from 1975
  is switched off while this mod runs, so KE always reads KE.
- **Sizes.** A corvette (KE) must be 200 to 8,000 tons (as with Historical Hulls
  alone), a frigate (FF) 1,500 to 12,000 tons. Both may carry torpedoes from 1950 (with Historical
  Hulls; before that the game's ban on torpedoes for KE applies to both). The
  designer keeps a chosen KE or FF of its size instead of offering another type.
- **Looks.** A frigate's ship picture uses the destroyer's (DD) default hull
  outline and proportions, not the corvette's: frigates are destroyer-sized.
  The twelve reads behind the picture report a frigate as DD (the outline reset
  and the picture's size curve); the drawn hull itself already treats DD and KE
  alike.
- **Roles.** In battle and in the AI's plans a frigate is still an escort like a
  corvette; the difference is size: a frigate has room for more sensors,
  missiles, a helicopter and range, a corvette is a small coastal escort.

## How it works, and its limits

The game reads a ship's type byte in 1,637 places. Each read is rerouted
through a small routine that reports a frigate as a **corvette (KE)**, so the
game's rules, costs, AI, battle and campaign code treat a frigate exactly like a
corvette, except the class sizes above and its picture. Fourteen reads
keep the real number: the type texts above, the designer's class warning, its list selection, and
three places that copy one ship's type into another (the designer's working
copy and two ship copies).

- Everything else that shows a type (some lists, battle labels) may still show
  **KE** for a frigate: those screens take the type from copies the game keeps.
- The computer never designs or builds frigates.
- The designer's **AI design** button designs a frigate as the game's AI
  designs a destroyer (DD) for that year and nation, then makes it a frigate. A
  destroyer outside the frigate's 1,500-12,000 tons gets the designer's usual
  type suggestion instead. The template tools still decline type 15.
- Expanded Timeline's own hooks that look at a ship's type see 15: the ASW
  bonuses (ASW torpedoes, VL-ASW, quiet hybrid drive) count FF with the escorts;
  the BBV carrier rule does not apply to frigates.
- A save with frigates loads them as corvettes if this mod is turned off. With it
  on, corvettes that a 1975-or-later save wrote as `FF` (the old rename) load as
  frigates.

**Tested in the game (13 November 2026):** it attaches after the 18 other
runtime mods (1,624 hooks); a June 2000 campaign whose 16 corvettes were saved
as `FF` loads with them as frigates and runs; the designer offers **FF -
Frigate** and computes it exactly as a corvette (same hull weight, cost, crew
and building time). Not yet tried: building, refitting or fighting with a
frigate, or saving and loading one.

Use a separate test campaign. Tests: `Manager/test_frigate_type.py` (every
rerouted read is emulated against the original instruction for every type).

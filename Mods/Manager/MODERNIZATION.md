# Submarine and modern-era extension work

## Current capabilities - 23 October 2026

| Feature | Status |
| --- | --- |
| Native campaign end checks moved to 2030/2031 | Implemented as an optional experimental runtime mod |
| Existing submarine campaign and tactical records inspected | Read-only investigation completed |
| Submarine mode in the original Ship design screen | Implemented as an experimental native-screen extension; visual/lifecycle validation in progress |
| Native ordering with class label, availability and accuracy | Hook implemented and emulated; real campaign construction not yet verified |
| Custom native displacement, propulsion, speed, depth and armament | Not implemented; these blueprint fields are projections only |
| Player-controlled tactical submarine movement/depth/attacks | Not implemented |
| Post-1978 research progression to 2030 | Implemented as an optional 83-technology, 21-branch native-compatible expansion; gameplay balance unverified |
| Post-1970 aircraft performance progression | Implemented in Modern Research: jet, attack, helicopter and medium bomber rows to 2030 (data table) |
| Railgun main batteries | Implemented in Modern Research (research 2020, electric drive and power budget; range, penetration, inert ammunition) |
| Ship lasers | Implemented in Modern Research (research 2022, 0-8 mounts, power budget; anti-missile layer with weather limits) |
| Hypersonic anti-ship missiles | Implemented in Modern Research (research 2023, designer option; SAM/CIWS/AA/laser kills cut to 30%, heavier VLS cells; five times native flight speed) |
| AESA radar | Implemented in Modern Research (research 2002; search radar class 7 on hulls from 2002 with radar limit 7: +20% over Aegis, enemy stealth halved) |
| Extra generators | Implemented in Modern Research (Integrated power system; designer box, 10 MW steps for railgun and laser power) |
| Guided shells and torpedoes | Implemented in Modern Research (research 2012 and 1977; guns up to 6 inches hit twice as often, larger guns 1.5 times from 2026; torpedoes hit from 2.5 times as far) |
| Longer missile and SAM ranges | Implemented in Modern Research (research 1978, 1981, 2013, 2014) |
| Satellites, over-the-horizon fixes | Implemented in Modern Research (research 1976; spotting beyond radar range for missile targeting) |
| UAV scouts | Implemented in Modern Research (research 2005; floatplanes launch and recover without stopping) |
| Railgun secondaries, railgun point defence | Implemented in Modern Research (research 2027, 2029) |
| ASW torpedoes, VL-ASROC | Implemented in Modern Research (research 1966, 1993) |
| Composite superstructures | Implemented in Modern Research (research 1996) |
| USVs | Implemented in Modern Research (research 2024; MTB squadrons) |
| Nuclear shells | Implemented in Modern Research (research 1958; one per main battery of 16 in+ per battle) |
| Frigates (FF) | Implemented in Modern Research (KE reads FF from 1975) |
| EMALS | Implemented in Modern Research (research 2017; new carriers 4 spot per catapult, heavy jets from 24,000 tons) |
| Super heavy anti-ship missiles | Implemented in Modern Research (Effective cruise missiles; CA/BC/BB option: heavy SSMs twice the range and about twice the damage, mounts twice the weight) |
| Aegis-type search radar and ship radar stealth | Implemented in Modern Research (radar class 6; design-year stealth) |
| Nuclear propulsion | Implemented in Modern Research (designer propulsion type, research-gated from 1961) |

The requested submarine designer and direct battle control are complementary,
not mutually exclusive. One persistent submarine class should supply both the
strategic boat and its deployed tactical instance. This document is an
implementation boundary, not a claim that the unimplemented features are playable.

## Expanded Timeline: research to 2030, campaign to 2050

Refresh the manager's mod list, select **Expanded Timeline - Modern Research to 2030, Campaign to 2050**, and launch with **Play with
mods**. It merges the former Campaign Through 2030, Modern Research Through 2030
and VLS Cells packages; their adapters still load in the same order.

The original native `CheckEndOfGame` function offers an end in December 1970 and
forcibly ends at the beginning of 1990. The package moves that offer to December
2050 and the forced stop to 2051, so the full year 2050 remains playable at the
end-check level. Research still ends in 2030. Aircraft developed after 2030 reuse
the 2030 performance row plus 1%, the game's own fallback past its last row. The
original end-of-game behavior and loss conditions remain. Its two native notices
are updated consistently in memory.

**Year tables.** 71 of the game's year switches end between 1991 and 2001,
because the native campaign stops in 1990. Past their end, a year fell into
the switch's default branch, which holds the value for years before the table.
For example, aircraft development time dropped from 12 months to 6 in 2000,
colonial income rose from 4 to 25 per value point, and peacetime maintenance lost
its ×1.25. The same happened to AI build odds, tech adjustments, design weights
and some battle rules. The package keeps each switch in its last range through
2060 instead: one byte for 52 of them, and a small jump to a wider comparison
for the 19 whose last range starts before 1934. Years before each table's end
behave exactly as before.

The adapter checks the named function, year source, exact instructions, branch
types, Unicode string lengths and notice ownership before applying the four
calendar patches, and the exact native bytes of each year switch before
stretching it. On failure it restores already-applied changes. Attach is idempotent;
detach checks every patch before restoring anything. It never modifies RTW3.exe
on disk, a personal save, or the separate Steam installation.

This does **not** add technology beyond the current research tree, change the
calendar cadence, or validate 60 additional years of economics, officer aging,
AI design and aircraft development. The existing weekly calendar is independent
and still unbalanced. Use a separate test campaign. Keep the timeline mod enabled
when continuing a save beyond 1989: loading it in the unmodified engine restores
the original retirement check on a subsequent turn.

The same package appends the modern technologies without moving original
IDs/slots, and supplies researched effects to native calculations for both
player and AI. See `MODERN_TECH_TREE.md` for branches, effects, save
compatibility, sources and the remaining limitations.

## In-game Submarine Designer

The designer is no longer a Mod Manager tab or a separate top-level designer
window. Enable **In-game Submarine Designer - Experimental** and its **Live
Cheats** dependency, then use **Play with mods**. Open **Design Ship** and choose
**SS - Submarine class** under **Ship type**. F11 opens the same native screen
and requests SS mode in a loaded campaign. The manager only enables the module.

The extension binds RTW3's original Delphi `TfrmDesignMain2` form, its original
Class name, Displacement and Speed inputs, equipment tab strip, and Save and
finish control. New gray/Tahoma subsystem panels and a class layout drawing
are embedded as child controls in that screen. They are not new Delphi engine
components or a new native submarine hull simulation. Close RTW3 before replacing
the DLL. Starting RTW3.exe directly does not load the module.

The equipment tabs become Machinery / hull, Armament / sensors and Submarine
classes. Choose a fictional layout in Submarine classes; edit the original
Class name, Displacement and Speed controls on the left (Speed means surfaced
speed). **Save and finish** saves the blueprint and closes the designer without
creating a surface ship, .ds surface design, or writing a campaign file.
**Save and order** saves the class, closes the designer, and opens the original
submarine build dialog. Select the matching native role. The game retains
its own research gates, price, quantity and cancellation behavior. Only matching
player boats created during that one manual dialog receive the class-name suffix,
availability and accuracy. No AI or unrelated later construction is changed.
Save normally in RTW3 to retain these native boat fields.

The other 12 inputs describe an estimated layout; they do **not** add native
reactors, batteries, custom hull displacement, speed, diving depth, missile cells
or manual attacks. Costs and build times remain native. This is a limited class
prototype, not a completed component-based submarine simulator.

Saved classes are kept in `Mods/Manager/submarine-blueprints.json` with revision
checks and backups before edits. In-game ordering does not open or write a .bcs
file. The older offline bridge remains a backend utility, not the in-game workflow.

Implementation: `in_game_submarines.py` hosts the fixed reviewed local module;
`submarine_factory.py` verifies the native constructor and build handler. The
module publishes a guarded request to the existing UI-thread idle dispatcher.
That thread opens the original Ship design / submarine build dialog. Native
surface-type conversion, surface-save events and surface editing shortcuts are
guarded while SS mode is active; original handlers and UI state are restored on
return to surface-ship mode. A temporary active class packet
applies only to the current player, current campaign, matching role and eligible
design year; nested idle messages cannot repeat the order. No authentication
code, disk executable or separate Steam installation is patched.

## Submarine bridge findings

The native code has different campaign and tactical submarine objects:

- Campaign boats persist name, availability, accuracy, one of five native roles,
  construction time, active/sunk state and deployment areas.
- Tactical boats have position, side, availability, attack downtime, accuracy,
  type, fate and loss time. They participate in native aircraft ASW, coastal
  patrol attacks, mine interactions and submarine attacks.
- `TransferCampaignSubSunk` transfers tactical losses back to the campaign.
  Its matching includes the native type/name string; a new class system must
  preserve this identity across saves and battles.
- Native type mapping was verified from `SubTypeFromListText`: 0 medium, 1
  minelayer, 2 coastal, 3 long range, 4 missile. These are not new designer slots.

The inspected tactical records do not establish a ready-made player movement,
depth or component-design interface. A controller must be implemented and tested,
not inferred from the existence of a position field. Remote coordinate edits
alone would not deliver a complete tactical submarine system.

The next integration needs a persistent class identity and component schema,
validated strategic production/cost rules, tactical deployment with that identity,
course/speed/depth and attack orders, ASW/detection interactions, AI behavior and
save/reload/loss reconciliation. No controls are advertised as working before
their effects are integrated.

## Modern systems boundaries

Appending a technology label or renaming an existing weapon does not implement
a new combat system. Lasers need line-of-sight, dwell time, weather and power
limits; railguns need projectile flight and launch-energy/reload limits; reduced
signatures need detection and targeting changes rather than invisibility.
These remain planned engine extensions, not effects supplied by the calendar mod.

For real-world grounding, [ATLA's official 2025 equipment publication](https://www.mod.go.jp/atla/en/policy/pdf/defense_equipment_DSEIJ2025.pdf)
describes railguns as research toward deployment, a laser demonstrator for
counter-drone use, and low-signature naval designs. Projected 2030 capabilities
should be marked experimental rather than presented as established history.

## Verification boundary

The timeline has isolated x86 branch tests and read-only native-code checks at
1890, 1900, 1970, 1989, 1990, 2000, 2029, 2030, 2031 and 2100. Live hook
attachment/readback and full restoration were tested on a normally authenticated
local title-screen instance. No campaign turn was advanced for these tests.
An actual long campaign through 2030 remains unverified.

Version 0.3 replaces the former separate popup with an extension of the original
ship-design screen. The full suite has 77 passing isolated tests. They cover CLR
hosting, register/stack preservation, class/player/role/year/range guards,
re-entrant native dialog dispatch, native event suppression and relocation of
original surface-save calls. All enabled mods and the new module were loaded
together through the manager; 17 native event hooks attached successfully.

Three subsystem component pages were rendered and visually reviewed in a clearly
labelled non-game layout harness. This found and fixed an initial page-switching
bug. These renders are NOT screenshots or verification of the native game screen.
The computer-use helper did not expose a targetable RTW3 window, so actual native
control binding, SS selection, finish/save behavior and restoration of surface
mode remain unverified. Earlier popup-ownership tests do not verify version 0.3.

No campaign boat was ordered or turn advanced by these tests. Full native-screen
interaction, build/cancel/save/reload/battle testing remain outstanding; tactical
controls and modern weapon simulation are not delivered. Use a test campaign.

# Expanding RTW3 research slots

The two reserved branches are now used by Modern Research Through 2030; see
`MODERN_TECH_TREE.md`. The assessment below is unchanged.

Investigation: 3 November 2026. Scope: this local RTW3 1.01.44 build and its
existing mod framework. This is an implementation assessment, not an installed
capacity expansion. The game executable, saves and enabled mods were unchanged.

## Findings

There are two separate capacities: research **branches** and technologies
**inside each branch**. Technology IDs and the final year are separate limits.

| Quantity | Confirmed value |
| --- | ---: |
| Ordinary branches in the current tree | 22, numbered 0-21 |
| Technologies supported per ordinary branch | 36, numbered 0-35 |
| Current ordinary-branch capacity | 792 |
| Technologies in the vanilla/currently installed table | 572 |
| Unfilled positions in that table | 220 |
| Technologies in the optional Modern Research pack | 655: original 572 + 83 |
| Unfilled positions after that pack | 137 |
| Remaining after excluding the airship branch | 109 |
| Native branch records reserved, including gun manufacture | 25 |
| Largest ordinary-branch count accepted by the native loader | 24 |
| Capacity with 24 ordinary branches at 36 technologies | 864 |
| Extra positions contributed by two new branches | 72 |
| Unfilled ordinary positions compared with the Modern pack, after adding two branches | 209 |

The current manager selection has Modern Research and Timeline 2030 disabled;
the installed research data is vanilla. A read-only observation of running PID
23008 also found ordinary branch count 22, with gun manufacture at index 22.
This is a point-in-time observation, not a change to the user's selections.

**Index 22 is currently gun manufacture, not an unused branch.** The engine
generates that branch after loading the ordinary branches. With one new ordinary
branch it moves to 23; with two it moves to 24.

## Available approaches

| Approach | Capacity gained | What must change | Assessment |
| --- | --- | --- | --- |
| Append within the existing branches | Up to 220 positions over vanilla, or 137 after Modern Research | Definitions, stable IDs/prerequisites, actual effects and balance | Closest to the existing working framework; preserves original positions |
| Add the two reserved ordinary branches | 72 positions; 864 ordinary positions total | Definitions, loader/cheat validation, effects, traits, UI checks and save migration | Strongest native expansion candidate; lookup and serialization loops tested offline |
| Put overflow technologies in less crowded branches | Uses existing empty positions; no increase in total capacity | ID-based effects and careful filtering of legacy branch-level calculations | Can work, but may make the tree confusing and change unrelated native bonuses |
| Repurpose an existing branch | Up to that branch's existing 36 positions; no net increase | Replace historical content, audit hardcoded ID users and migrate old saves | Suitable for a separate total-conversion/new-campaign pack, not an invisible update |
| Widen native branch technology arrays | For illustration, 24 x 64 = 1,536 or 24 x 128 = 3,072 ordinary positions | Relocate definitions and nation research storage; rewrite all readers, writers, bounds, UI and save handling | Real expansion, but substantial native work; no working patch demonstrated |
| Add more than 24 ordinary branches | Depends on replacement storage | Replace names/pictures/definition arrays, per-nation state, count bounds, special gun handling and all relevant consumers | Shares most work with widening; cannot be achieved by changing one maximum |
| Build a supplemental mod research system | A configurable number independent of native 24/36 limits | Research storage, budget/progress processing, prerequisites, AI, persistence, original Research-screen integration and effect hooks | Best long-term route for a large modern tree; requires a real subsystem |
| Page different technologies through native positions | More lifetime technologies than simultaneously active positions | Persistent ID-to-page mapping; archived ownership; ID/count/prerequisite/save/AI interception | Feasible design, but substantially more fragile than stable mod-owned storage |
| Use repeatable technology levels | Extended progression in one position | Persistent repeat count, costs, UI, completion reset and bounded effect calculations | Useful for incremental upgrades; does not add separate selectable technology nodes |
| Make one technology unlock several systems | More effects per position | Multiple reviewed effect hooks and appropriate designer unlocks | Good for integrated combat systems; does not add independently researched nodes |
| Use era- or campaign-specific technology banks | Different trees over a campaign's lifetime, not simultaneously | Explicit migration and an external ownership ledger; campaign-specific data identity | Possible with substantial support; swapping data files alone misidentifies saved flags |
| Reclaim the generated gun-manufacture record | At most one additional record's 36 definition positions inside existing allocation | Move gun progression elsewhere and rewrite the count/sentinel semantics and inclusive/exclusive loops | Theoretical intermediate route, not another free ordinary branch |
| Change the engine source, with legitimate access, or replace the research subsystem in a new engine | Chosen design capacity | Source-level data structures, gameplay and save/UI migration | Broadest control; game source is not available in this workspace |

These are architecture choices rather than mutually exclusive alternatives.
For example, stable native historical research can coexist with a supplemental
modern research bank shown in the original Research window.

### 1. Fill the existing positions

This is already how Modern Research adds its 83 technologies. Appending preserves
original branch positions and saved flags. Original and released IDs/positions
must stay stable. The most constrained Modern branches are machinery, fire
control, ship design, light forces, torpedoes and fleet tactics, all at 36/36.

Spare positions after Modern Research:

| Branch | Used | Free |
| --- | ---: | ---: |
| Machinery | 36 | 0 |
| Armour | 32 | 4 |
| Hull construction | 31 | 5 |
| Fire control | 36 | 0 |
| Subdivision and damage control | 28 | 8 |
| Turrets and gun mountings | 33 | 3 |
| Ship design | 36 | 0 |
| AP projectiles | 31 | 5 |
| Light forces and torpedo warfare | 36 | 0 |
| Torpedo technology | 36 | 0 |
| Submarines | 34 | 2 |
| Anti-submarine warfare | 28 | 8 |
| Explosive shells | 30 | 6 |
| Fleet tactics | 36 | 0 |
| Anti-aircraft artillery | 33 | 3 |
| Radar and electronics | 30 | 6 |
| Lighter-than-air aviation | 8 | 28 |
| Heavier-than-air aviation | 32 | 4 |
| Shipboard aircraft operation | 30 | 6 |
| Missile technology | 32 | 4 |
| Amphibious operations | 13 | 23 |
| Missile countermeasures | 14 | 22 |

Unused airship positions are not inherently appropriate places for unrelated
modern technologies. Native branch-level getters count completed flags, so
adding unrelated entries can accidentally improve the original branch's effects.
An ID-based effect map and filtered legacy counts are needed if mixing content.

### 2. Use the two reserved native branches

The loader's regular-branch count can reach 24, and its name and image arrays
each reserve 25 pointers. Definitions likewise use fixed blocks of 36 records.
Gun manufacture occupies the record at the regular-branch count index.

The native HasResearchId, GetHighestResearchLevel and CountResearchLevels routines
successfully handled synthetic branches 22 and 23. Gun manufacture continued to
use its special calculation at the new final index 24. Native research save/load
loops used the variable branch count and processed all 25 records.

Implementation requirements:

1. Keep original ordinary branches 0-21 and every released technology position
   stable. Add branches at 22 and 23 and choose globally unique IDs. Each branch
   needs its own real effects; a new name alone creates no combat capability.
2. Generalize `modern_tree.parse`, its fixed 22-area check, capacity reporting and
   the Modern pack builder. The current parser deliberately rejects extra areas.
3. Update Modern Research's exact payload validation and effect definitions;
   update research-all, in-game progress and any fixture/manager schema that
   assumes 22 branches. The audited native instruction layout can remain the same
   for this route; loaded definitions and table-dependent guards still change.
4. Update the research-traits adapter's `max_area_index=22`; otherwise ordinary
   branch 23 and moved gun manufacture 24 miss its bonus. Check other mods for
   numerical branch assumptions and overlapping hooks.
5. Audit new-campaign initialization, per-nation advantages/priorities,
   availability, budget allocation, AI selection, research distribution and
   breakthrough effects. Most inspected paths use the variable count; this is
   not proof that all paths are correct.
6. Verify the original Research screen, detail windows, result notifications,
   scrolling and category pictures. Inspected list builders use a variable
   branch count; actual expanded UI has not been tested.
7. Migrate existing saves explicitly. Copy the old gun-manufacture research
   metadata from `Research22...` to `Research24...` and initialize the two new
   ordinary records, preserving separate `GunQuality...` fields. Preserve any
   existing nonzero flags according to a documented schema rather than blindly
   clearing them. Migration must cover every nation and autosaves.
8. Keep the expanded pack identified with the campaign. Loading the expanded
   save with a 22-branch table can interpret new branch 22 as gun state and lose
   the extra records on a later save. Refuse mismatches or provide a deliberate
   conversion. Never overwrite the sole original campaign.

Suggested content split: modern sensors/electronic warfare and advanced naval
systems. This is a layout proposal, not confirmation that lasers, railguns or
signature physics are implemented.

### 3. Expand native storage and bounds

Each native technology definition is 29 bytes. A branch block is
`36 * 29 = 1,044` bytes. The per-nation research branch is 53 bytes:

| Offset within a branch | Contents |
| --- | --- |
| 0 | Advantage byte |
| 1-4 | Priority |
| 5-8 | TSL |
| 9-12 | Current project index |
| 13-16 | Research points |
| 17-52 | 36 completed-technology flag bytes |

**Flag 36 writes the next branch's advantage byte. Definition 36 aliases the
next branch's first definition.** Raising a loop maximum alone is not safe.

A real widening must move research state to larger allocations and redirect
all relevant access paths. Expanding the entire native nation object would
also move later unrelated fields and require auditing their uses, constructors,
copies and serialization. Keeping extra research in mod-owned allocations and
leaving existing nation fields in place is a more contained architecture.

Required paths include definition load/cleanup; nation initialization/reset;
ID lookup/set; level counts/highest level; research budgets/current project;
year, chance and prerequisite checks; completion, missed research and diffusion;
AI choices/effects; research UI; save/load/autosave/copy; progress and cheats;
and detach/version compatibility. Save-file fields are text, but the in-memory
arrays and loops impose the limits.

### 4. Supplemental research bank in the original screen

For a much larger tree, preserve historical native data and add mod-owned state
keyed by stable technology ID and nation/campaign identity. Integrate its
categories and detail controls into the existing Research form, following the
game's visual style. The manager should enable/configure the module.

The system needs a real portion of the research budget, national priorities and
traits, prerequisites/year gates, deterministic progress, breakthroughs and AI
choices. Apply it once per campaign turn with a turn/campaign identity guard,
so idle callbacks or weekly/monthly paths cannot award progress twice.

Persist it with native campaign save/load hooks, including autosave, Copy game,
save-slot changes and older save revisions. A companion file is possible, but it
must be tied to the exact campaign save revision; merely naming it Game4.json
would mix state after rollback or slot copying. Stage both files, keep matching
backups and recover cleanly from an interrupted write. Another option is a
versioned extension section in a copied `.bcs`, but native preservation/ordering
and unknown-key behavior must first be verified. Do not assume unknown keys
survive a stock native save.

All nations should use the same research rules. Actual effects need reviewed
calculation/designer/combat hooks. This architecture can unlock new subsystems,
but researching a label does not implement a laser firing model, railgun power
system or radar-signature simulation.

### 5. Paging, repeatables and bundled unlocks

Paging can keep only the current set of projects in native positions and archive
completed IDs externally. It still needs stable ownership, original-ID lookup,
counts, prerequisites, AI and save migration. Native positional flags alone do
not identify which historical page a completion belongs to. It saves active
table space but does not remove the need for an extended research subsystem.

Repeatables are useful for gradual refinements with increasing costs and bounded
bonuses. Bundled unlocks are useful for integrated systems that belong together.
Neither gives the player additional independently researched nodes.

## Changes that do not expand capacity

- Raising `MAX_LEVELS` in `modern_tree.py` only removes a Python guard. It does
  not resize native arrays, serialization or UI loops.
- Raising the native 24-branch error threshold leaves the fixed allocations and
  the generated gun branch unchanged. Header/row writes occur before the final
  count check, so the error is not a safe capacity allocator.
- Larger technology IDs do not allocate more slots. ID lookup scans table
  records; the conventional branch-times-100 numbering is not extra storage.
- Extra `Research23...` or `Research0Level36...` save keys do not expand the game.
  Native save/load loops determine which keys exist and where values are stored.
- ResearchAreas.dat and ResearchAreas2.dat are not additional simultaneous trees.
  This native loader reads ResearchAreas3.dat. A new filename still has the same
  storage limits unless the loader and consumers are changed.
- Renaming entries, changing their year/chance/cost/prerequisite, enabling the
  calendar extension, increasing the budget or accelerating research changes
  progression/content, not the number of positions.
- The native research editor and cheats use the same underlying records. Their
  presence is not evidence of a larger hidden technology bank.
- Overwriting a completed position with a new ID makes its old flag apply to a
  different technology unless an explicit ID-based migration system intervenes.

## Performance plan

Native HasResearchId linearly scans `(ordinary branches + gun branch) * 36`
definition positions. Bigger arrays multiply work in frequently called getters.
An extension should build an ID-to-location map once, keep per-nation ownership
and derived bonuses cached by research revision, and update UI/progress only
when research changes. Avoid reading every definition on every frame or idle
callback. Put bounds on repeatable effects and memory; extensible does not mean
unbounded safe numeric bonuses.

## Recommended implementation order

1. Introduce an explicit research-capacity/schema description, stable ID registry
   and effect registry. Make validators, cheats and progress use that schema.
2. Deliver the two reserved native branches with a separate-save migrator,
   original Research-screen integration, actual effects and matching AI rules.
   This supplies 72 genuine new positions without enlarging native records.
3. For hundreds more technologies or more categories, implement the supplemental
   research bank and its native UI/save lifecycle. Reuse the ID/effect registry.
4. Consider widening/replacing native arrays only if a demonstrated requirement
   cannot be met by that system. Paging/recycling is a fallback with more state
   reconciliation work, not a shortcut around persistence.

## Evidence and verification limits

`research_slot_audit.py` is a repeatable offline investigation. It authenticates
the retained research code using the current adapter's audited native hashes,
then executes native code in Unicorn against synthetic data.

- Native lookup, highest-level and count routines tested with 22, 23 and 24
  ordinary branches, every branch's first/last technology, positive/negative
  ownership and missing IDs.
- Native research serialization loops round-tripped **943, 984 and 1,025 fields**
  for 23, 24 and 25 total branch records. Research bytes matched exactly and
  neighboring bytes were unchanged.
- The serialization harness replaces Delphi string and INI functions. It does
  not open a `.bcs` or execute full native campaign save/load.
- Native UI, initialization, complete turn processing, AI gameplay, research
  breakthrough effects and save migrations for additional branches remain
  unverified. No capacity expansion was installed in the running game.

Reference addresses below belong to the retained image at code base 0x301000;
running addresses vary with ASLR.

| Native path | Reference address | Relevant behavior |
| --- | --- | --- |
| LoadGlobalResearchAreas | 0x7603e4 | Definition loading and generated gun branch |
| Row guard | 0x7605b8 | Last accepted row index 35 |
| Area guard | 0x760813 | Ordinary count <=24 |
| HasResearchId | 0x729fa4 | Variable branch count; 36 definitions per record |
| CountResearchLevels | 0x71e0e8 | Gun manufacture identified by variable final index |
| GetHighestResearchLevel | 0x71eb68 | 36 flags per branch |
| Native research load loop | 0x7206e2-0x7208dd | Count+1 records; 36 flags per record |
| Native research save loop | 0x724f0e-0x72520c | Same count/layout |
| DoResearch | 0x76225c | Fixed branch record strides and current-project bounds |
| DoGunResearch | 0x79c970 | Uses the variable final index |
| CheckMissedResearch | 0x7a3a50 | Fixed 36-level loop |
| Original research list | 0x5a9e70 | Branch count through global indirection |
| Research detail list | 0x6069fc | Fixed 36-level loop |

Machine-readable evidence: `research-slot-audit.json`. Additional native method
and instruction listings are in `research-slot-native-methods.json`,
`research-slot-native-inspection.txt`, `research-slot-support-inspection.txt`
and `research-slot-loop-inspection.txt`.

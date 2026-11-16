# Research Budget Scaling - No Stalled Projects

Enable **Research Budget Scaling - No Stalled Projects** and restart through
**Play with mods** before loading a campaign. The same native `DoResearch`
path runs for the player and every AI nation, so all nations get these rules.

## Why research stalled

Three native rules capped what money could buy:

1. **Halving setbacks.** While a technology is ahead of its year, each turn has
   an 8% chance to halve the project's accumulated points, and a further
   "research problems" event can halve it again. Halving scales with progress,
   so a project settles at an equilibrium below its cost and can sit there for
   hundreds of turns. A 1930 save showed 1933-1935 projects at 15-60% of cost
   with 400-600 turns on the same technology.
2. **A hard 20% limit.** One turn can add at most cost/5 to a technology.
   Effort above that, however large the budget, was discarded.
3. **32-bit wrap.** The national point total is `points x 140 x ResearchSpeed`
   in 32-bit integers. An extreme budget or research speed wraps it negative,
   which stops research entirely.

## What changes

| Rule | Native | With this mod |
| --- | --- | --- |
| Ahead-of-era 8% setback | Halves the project | That turn's gain is lost |
| Research problems event | Halves the project, reduces that turn | Only reduces that turn |
| Turn limit per technology | `min(effort, cost/5)` | Effort above cost/5 counts at 50%, up to 60% of cost |
| National point total | Wraps past 2^31 | Saturates at 20,000,000 |

Native era penalties (slower progress the further a technology is ahead of its
year), the hold that can keep a technology more than two years ahead at
cost-1, prerequisites, priorities, national traits, random modifiers and all
setback messages are unchanged. Research still slows sharply far ahead of the
calendar; it just no longer stops.

The 20,000,000 total is far above what any area can use under the turn ceiling.
It also bounds the native round-robin distribution loop.

## Settings

In `Mods/Library/research-budget/mod.json` under `runtime`:

| Setting | Default | Allowed range |
| --- | ---: | --- |
| `overflow_percent` | 50 | 0-100 |
| `max_turn_progress_percent` | 60 | 20-100 |

`overflow_percent: 0` or `max_turn_progress_percent: 20` restores the native
turn limit while keeping the setback and overflow fixes. Restart after edits.

## Verification

`test_research_budget.py` runs the generated code and the native code side by
side in an x86 emulator: identical results at or below the native limit and
for identity settings, the 50%/60% curve above it, native-equal point totals
until the limit, saturation where native wraps negative, preserved registers,
flags and FPU stack, the three setback sites keeping progress, relocation and
changed-code refusal. No campaign was loaded or advanced; multi-year balance
needs playtesting. Runtime report: `Mods/CampaignOverhaul/research_budget_report.json`.

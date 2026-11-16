# Stronger Research Advantages and Technical Excellence

Enable **Stronger Research Advantages and Technical Excellence** in the manager
and restart through **Play with mods** before loading a campaign. The default
extra bonuses are:

| Native trait | Extra research effort |
| --- | ---: |
| `ResearchNAdvantage` enabled | +50% in that research branch |
| `TechnicalExcellence=1` | +25% in all research branches, including gun research |
| Both apply to a branch | +75% (additive, not compounded) |

For example, a positive allocation of 100 becomes 150, 125 or 175 respectively.
This is an extra bonus on top of the existing national-trait mechanics, not
the complete effective research multiplier or a promise of that percentage
reduction in completion time. Remaining native random modifiers, priorities,
era penalties, prerequisites, progress limits and completion checks still run.
Small values are rounded down to whole effort points. Zero/negative allocations
receive no new research effort.

## Scope

The same reviewed native research path handles player and AI nations. A nation
without the corresponding native flags receives no extra bonus. Research
advantages remain branch-specific; an advantage in one branch does not help
another. Nonzero advantage flags follow the existing native boolean behavior.
No flag is enabled automatically, and existing campaigns use their saved trait
values. Changing a starting-nation data file alone is not a save conversion.

The mod changes a local research-effort calculation, not the saved national
traits, research priorities, budget allocation pool, research-speed setting,
completed inventions, technology costs or data tables. Existing Technical
Excellence effects on gun/aircraft quality, industry and other systems are left
intact, not multiplied or claimed to be newly improved by this research mod.

It works with the baseline or expanded research pack because it does not depend
on specific invention IDs or years. Existing native ahead-of-era and prerequisite
rules stay in place. It does not rebalance the separate weekly-calendar economy.

## Adjust the strength

In `Mods/Library/research-traits/mod.json`, the `runtime` settings are:

| Setting | Default | Allowed range |
| --- | ---: | --- |
| `research_advantage_bonus_percent` | 50 | 0-300 |
| `technical_excellence_bonus_percent` | 25 | 0-200 |

Values are extra percentages. Set both to zero to get the original effort
calculation, while retaining the game's original trait effects. Restart after
changing settings. Disable the package and restart to remove its hook entirely.

## Verification

Isolated x86 tests exercise all four trait combinations, multiple nations and
branches (including gun research), neighboring-branch isolation, zero/negative
effort, integer rounding, invalid area bounds, 64-bit boost arithmetic with
saturation, register/flag/stack preservation, native progress-clamp execution,
address randomization and changed-code/settings refusal. The boost itself never
unlocks an invention or writes the nation/allocation pool.

Attachment is permitted only at the title screen of the authenticated managed
build. Code is session-only; neither `RTW3.exe` on disk nor the separate official
Steam installation is modified. Saving normal play can retain the resulting
research progress; disabling the mod does not undo progress already earned.

Runtime diagnostics: `Mods/CampaignOverhaul/research_traits_report.json`.
Startup readback is separate from real campaign balance. No personal campaign
is loaded, advanced or saved as part of verification.

All 180 manager/runtime checks passed. A title-screen startup check verified the
research hook, its generated code and configured 50% / 25% bonuses, together
with Battle AI and the existing security/campaign/live-cheat tools. No research
call or cheat request was run during that startup check; campaign balance still
needs normal playtesting.

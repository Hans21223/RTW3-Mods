# Custom Campaign Decisions

The live campaign tools open **Decisions** while RTW3 is running. Definitions
are read from `Mods/CampaignOverhaul/custom_decisions.json`; edit that file to
add or change choices, then use **Reload decisions** in the panel.

## One-time decision

```json
{
  "id": "naval-grant",
  "name": "Emergency Naval Grant",
  "mode": "instant",
  "description": "Trade prestige for immediate funds.",
  "effects": { "funds": 25000, "prestige": -1 }
}
```

## Multi-year project

```json
{
  "id": "colonial-infrastructure",
  "name": "Invest in Colonial Infrastructure",
  "mode": "annual",
  "description": "Pay 50,000 funds per year for five years.",
  "duration_years": 5,
  "annual_effects": { "funds": -50000 },
  "completion_effects": { "income_resources": 1000 }
}
```

Supported effect fields are `funds`, `income_level`, `income_resources`,
`prestige`, and `unrest`. Values are changes, not target values. The first
annual payment is made when a project starts. Later payments are made with
**Apply annual installment** after the campaign year advances. If several
years passed, the tool catches up the due installments in one guarded update.
Progress is stored in `Mods/Manager/custom-decisions-state.json` under the
campaign profile name shown in the panel. Use a different profile name for a
different campaign. Save in RTW3 to keep the changed campaign values.

Keep JSON valid, use unique lowercase IDs, and set `duration_years` from 1 to
30. The manager checks field limits and the live campaign snapshot before it
applies an effect.

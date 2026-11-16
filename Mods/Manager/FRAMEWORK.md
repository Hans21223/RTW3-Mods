# Mod framework 2

Use **Diagnostics** on the manager's Mods & Launcher page to inspect the applied
selection, startup order, per-mod loading time and loaded hook checks. Reopen the
manager after an update. Launch through **Play with mods** to use the new host.
Your enabled selection is preserved; this update does not enable optional mods.

## What changed

- One reviewed adapter registry defines settings, launch flags, dependencies and
  ordering. Adding an adapter no longer needs separate routing tables in the
  manager backend and launcher.
- One Python startup host loads the selected runtime adapters. It does not start
  a separate Python interpreter for each mod. The F10 companion remains separate.
- Every write through `weekly_runtime.write_code` has an owning adapter and a
  byte range. An overlap is refused before the conflicting write. An adapter can
  undo its own exact patch during rollback. Another adapter cannot overwrite it.
- New patches are read back immediately and checked again at the end of startup.
  A report records loaded/failed adapters, ownership, settings and elapsed time.
- Reports identify the process by executable path, PID, module base **and creation
  time**. Old reports are historical evidence, never proof of a current session.
- The modern-research relocation reader caches only immutable PE relocation
  offsets within the host, keyed on file identity, size and timestamps. It still
  checks native method signatures and reads fresh live code for each adapter.

These changes improve startup overhead, observability and extension maintenance.
They do not replace the proprietary engine, add arbitrary native mod APIs or
establish a battle frame-rate improvement. The report times startup work; it does
not profile the game simulation, rendering or native hook execution.

## Diagnostics and recovery

`Mods/CampaignOverhaul/runtime_host_report.json` is the last startup record.
It is replaced atomically as startup proceeds. **Diagnostics** reads it and, for
the same live session, checks the recorded hook bytes through a read-only process
handle. It does not attach mods, change game state or repair hooks.

If a later adapter fails, the host stops loading more adapters. Earlier adapters
may remain active. Save anything already in progress, close the game when safe,
resolve the reported conflict and launch again before loading a campaign. There
is no promise of a transaction across all adapters: each adapter owns its native
allocations and rollback. A failed write is retained as uncertain in the report.

The ownership guard covers startup writes routed through `write_code`. It does
not arbitrate arbitrary external injectors, data mailboxes, native allocations,
injected UI changes made later, or the old standalone adapter commands. Use Play
with mods for coordinated loading. Signature checks remain required everywhere.

Read-only command-line interfaces:

```powershell
python Mods/Manager/mod_loader.py runtime-plan
python Mods/Manager/mod_loader.py runtime-diagnostics
```

Both return JSON. `ok` means the diagnostic request succeeded. Check
`session_state`, `warnings`, `mismatches` and `last_launch.ok` for game health.
Diagnostics shows the applied selection; unapplied checkbox changes are not a
running configuration.

## Authoring a package

Existing schema-1 packages remain supported. Imports contain approved content or
select a reviewed adapter; importing a ZIP does not execute Python or DLLs. A
runtime tuning package, for example, can contain only this `mod.json`:

```json
{
  "schema": 1,
  "id": "research-traits-tuning",
  "name": "Research traits tuning",
  "version": "1.0.0",
  "description": "Tuned bonuses for the reviewed national research adapter.",
  "kind": "runtime",
  "experimental": true,
  "requires": [],
  "conflicts": ["research-traits"],
  "files": [],
  "runtime": {
    "adapter": "research-traits",
    "research_advantage_bonus_percent": 75,
    "technical_excellence_bonus_percent": 30
  }
}
```

Do not enable two packages using the same adapter. Numeric settings must be whole
numbers within its registry bounds. Package dependencies still use package IDs;
the runtime registry separately verifies required adapters are present. Neither
can be replaced with unchecked module paths in a manifest.

## Adding a reviewed adapter to the framework

1. Implement a trusted module in `Mods/CampaignOverhaul/` with `attach`. Keep
   executable authentication, exact native signatures, one-local-game discovery,
   title-screen checks, readback, rollback and handle cleanup in the adapter.
   Return a dict with `attached: true` and `pid` after success; raise on failure.
2. Route native hook-site writes through `weekly_runtime.write_code(handle,
   address, original_bytes, replacement_bytes)`. Never bypass signature checks
   or deliberately chain another adapter's patch. Shared dispatcher features
   must have an explicitly reviewed installation order.
3. Add one `Adapter` entry in `runtime_registry.py`. Invocation styles are
   `plain` (`attach()`), `kwargs` (`attach(**settings)`), `settings`
   (`attach(settings=settings)`), `mode` (AI mode plus settings), and `pid`.
   Only reviewed framework code controls imports.
4. Declare bounded settings, adapter dependencies and `after` ordering. A
   dependency means the adapter must be selected; `after` means it attaches
   earlier when selected. These differ because security extends the dispatcher
   before live-cheats installs it. Stable ordering does not depend on checkbox
   order. Cycles, unknown settings and missing dependencies stop before launch.
5. Add a schema-1 package and meaningful offline discovery/emulator tests, then
   run the manager tests. Check startup at the title screen using a test session.
   Verify gameplay separately; startup and byte readback do not prove balance.

Framework regression command:

```powershell
python -m unittest discover -s Mods/Manager -p 'test_*.py' -q
```

The framework is a maintained extension layer over the authenticated Steam build.
A new game build requires reviewing signatures and adapter compatibility.

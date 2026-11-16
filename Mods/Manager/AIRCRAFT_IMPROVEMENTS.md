# Improve aircraft model

Enable **Aircraft - Improve Model in Right-click Menu**, then restart using
**Play with mods**. Open **Aircraft types**, right-click a current player model,
and choose **Improve aircraft model...**.

The original aircraft request dialog opens with that model's role selected and
fixed. Both priority groups have exactly the normal request choices. Cancel
creates no model and queues no request. The normal aircraft industry,
manufacturer and role-research checks remain active.

On confirmation the native variant routine copies the selected aircraft family,
advances its native designation, and makes the game's ordinary improvements.
The native priority routine then applies the selected priorities. Development
takes the original request delay plus the game's development time for that role.
The successor appears as a developing aircraft, rather than becoming available
immediately. The ordinary completion event finishes it. Fast aircraft requests
also recognizes this prototype through its existing native countdown.

The source aircraft remains usable. Its native superseded-version marker prevents
repeated branches from that same generation. Once development completes, use the
new model for further improvements. The native five-variant limit remains.

The action is disabled for no selection, foreign aircraft, obsolete models,
prototypes, superseded or final-version models, and while another normal request
is pending. It creates no ships, planes in service or free stockpile aircraft.
Normal new-aircraft requests and automatic player/AI improvements retain their
original paths.

## Persistence and implementation

The menu item is a genuine VCL menu item owned by the original Aircraft types
form. There is no separate designer window or overlay. All work runs on the
native UI thread. Only the explicit menu action scopes the native variant hooks.

The new prototype goes directly into the game's saved aircraft list, not its
temporary end-of-turn variant list. The model, role, priorities already applied,
native version and remaining development turns use the existing save format.
Save normally after ordering. No background pointer or mod sidecar is needed to
continue an existing prototype after reloading. Disabling the mod removes the
menu on the next launch; native prototypes remain ordinary game data.

The authenticated executable on disk is unchanged. Installation requires the
title screen and exact reviewed native code. Runtime patch ownership and timings
are available under the manager's **Diagnostics** button.

Verification evidence is recorded in `aircraft-improvements-validation.json`.
Offline emulation, startup, actual menu/dialog interaction and full campaign
save/reload are separate checks; a passing startup is not proof of gameplay.

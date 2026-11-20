# Super-Superfiring Turret Position

Enable **Super-Superfiring Turret Positions (Z/F/G/H/I)** alongside **Historical and Paper Hulls (Large Hulls)**, then restart the game using **Play with mods**. The ship designer will list five extra positions: `Z - Super-superfiring`, plus `F`, `G`, `H` and `I` as additional super-superfiring positions. Set each mount's location as usual.

RTW3's turret data only has a raised/not-raised flag. The mod gives each added code its own selectable mount position and treats all five as raised, while preserving native B, V and X behavior. It cannot create a numerically higher third deck level or separate third-height firing behavior in the base engine.

The mod manager applies the `Data/gunpos.txt` change through its normal backup and restore path. The runtime hook patches the game process in memory for that session, before a campaign is loaded; it does not write to the on-disk executable or save files.

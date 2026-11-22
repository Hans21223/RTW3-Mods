# Nuclear Armageddon (unlimited nuclear weapons)

Enable **Nuclear Armageddon (unlimited nuclear weapons)** together with Expanded Timeline and restart through
**Play with mods**. It changes what Expanded Timeline's nuclear weapons may do; everything else about them stays
(MODERN_TECH_TREE.md: Special shell doctrine; Nuclear submarines, aftermath and the ban treaty).

## What changes

| Weapon | Expanded Timeline alone | With Nuclear Armageddon | Price |
| --- | --- | --- | ---: |
| Main battery of 16 inches or more | its first hit of a battle is nuclear | every hit is | 500 a shell |
| SSBN missiles | one hit of a salvo is nuclear | every hit is | 1,500 a missile |
| SSN torpedoes | every torpedo that reaches a ship | unchanged | 800 a torpedo |
| Heavy SSMs (and super heavy) | conventional | every hit may be nuclear | 1,500 a missile |
| Heavy SAMs | conventional | every engagement may be nuclear | 1,500 a missile |
| Nuclear strike console (NUKE button in battle) | one strike a battle | any number | by warhead: A-bomb 1,500, H-bomb 4,000, MIRV 6,000 |

Not every weapon has a nuclear warhead: light and medium SSMs and SAMs, guns under 16 inches, aircraft weapons and
the torpedoes of other boats and ships stay conventional.

- **Nuclear heavy SSM.** The hit lands as a nuclear shell's (a 64-inch hit through the game's damage, which wrecks
  almost any ship), and every other ship within 1,500 yards, friend or foe, takes a 12-inch hit.
- **Nuclear heavy SAM against an incoming missile.** The missile is shot down; jamming and decoys on the missile
  no longer matter.
- **Nuclear heavy SAM against an air strike.** A hit destroys or damages up to 10 aircraft of the formation (the
  native two otherwise), as many as it has left, and the battle log says "Nuclear SAM detonates among the attacking
  aircraft".

Heavy SSMs and SAMs need the **Nuclear gun projectiles** research (2334, 1958: the warhead), like the shells.

## The doctrine

Doctrine and training, Special shells: the fourth tick box now reads **Use nuclear SSBN, SSM, SAM (1500 each)**.
It covers the three kinds of nuclear missile; the shells and SSN torpedoes keep their own boxes. Without the
money a weapon fires conventionally.

Everything else stands:

- **No first use.** Computer nations fire none until you have fired one, and then in kind: your nuclear shell frees
  their shells, your SSN torpedo their torpedoes, your nuclear missile (SSBN, SSM or SAM) their missiles. They pay
  nothing.
- **Aftermath.** Any nuclear use raises every nation's tension by 3 at the next turn, with a news item, and one time
  in three the powers propose a 15-year ban treaty. While a signed treaty runs nobody fires nuclear weapons.

Expect battles between nuclear powers to end quickly, and your budget too.

## How it works

The rules are in Expanded Timeline's runtime (`modern_navy.py`, `nuclear_subs.py`, `modern_air_defence.py`,
`nuclear_strike.py`), off
by default behind one flag in the shell doctrine's data. This mod's adapter (`Mods/CampaignOverhaul/nuclear_armageddon.py`)
attaches after Expanded Timeline, sets the flag and writes the new tick box caption. Closing RTW3 ends it. Saves
are not changed.

Tested in the emulator (`Manager/test_nuclear_armageddon.py`, and the armageddon cases in `test_modern_navy.py`,
`test_nuclear_subs.py`, `test_air_defence.py` and `test_nuclear_strike.py`); not yet played in a campaign.

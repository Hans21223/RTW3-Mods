"""Electromagnetic railgun main batteries (designer checkbox, power budget, battle effects).

A railgun main battery is stored as 2 in the main battery's Increased elevation byte
(Tship+0x9A6). Every native consumer tests that byte as a Boolean (audited for build
1.01.44: range, spotting, accuracy, penetration, copies, refit compare, checkbox
setter), so a railgun keeps increased elevation natively. Design files and campaign
saves write and read that one key as an integer instead of a Boolean, which keeps
0/1 files byte-identical. Part of the modern-research adapter; imported lazily.

Designer: a "Railgun" checkbox in the main-gun panel and a Power readout (MW the
main battery would need / MW the plant can spare). Needs research 2312, Nuclear or
Gas turbine propulsion, and enough power; the legality check reports each failure.
Mounts weigh 50% more and cost 2.5x, ammunition weighs half (no propellant).
Battle: main-battery range x2, penetration as a gun 4 inches larger, and a railgun
ship's main magazines and turrets neither flash nor explode (inert rounds).
"""
import hashlib
import struct
import weekly_runtime as rt
import modern_tree as tree
from hull_rules import patch, dpi_scale_routine
from modern_extension import HYPERSONIC_BIT as HYPER_BIT, SUPER_HEAVY_BIT as SUPER_BIT, SECONDARY_RAIL_BIT, TERTIARY_RAIL_BIT

BASE = 0x301000
RAILGUN = 2                        # Increased elevation byte value for a railgun battery
ELECTRIC = (4, 5)                  # Gas turbine, Nuclear (modern_propulsion.NUCLEAR)
DIESEL = 3                         # electric like a gas turbine with tree.HYBRID research (diesel generators)
MW_PER_GUN_5IN = 16                # US Navy 32 MJ gun at ~10 rounds/min with pulsed-power losses; scales with calibre^2
# Spare MW = horsepower x 0.746 kW x share. Gas-turbine generators are sized to propulsion (Zumwalt
# could feed about one railgun): 25%. Reactors run at full output indefinitely and nuclear ships
# carry big generating plants (Ford: about 3x Nimitz): modern_tree.NUCLEAR_SPARE, more with newer
# reactor generations (modern_tree.REACTOR_GENERATIONS).
GAS_TURBINE_SPARE = 25
MOUNT_WEIGHT = 150                      # railgun mount weight %, lighter with modern_tree.LIGHTER_MOUNTS
SPARE_DIVISOR = 4000000                 # hp x (746 x percent/25) / 4,000,000 = MW
CHECKBOX_BOUNDS = (226, 318, 80, 17)   # main-gun group, right of DP
LABEL_BOUNDS = (440, 432)              # left of the hull data, below the Turret top row
MAGIC_CHECKBOX, MAGIC_LABEL = 0x52474E31, 0x52474E32   # Tag values of the two controls
# Lasers (count in modern_extension's data, low byte): HELIOS/DragonFire-class mounts, about 1 MW each
# with cooling, 10 t and 100 cost per mount. Against an incoming missile: 15% per mount, at most 60%,
# halved in rain or mist and again in heavy seas, and only 30% of that against hypersonic missiles.
MAX_LASERS, LASER_MW, LASER_TONS, LASER_COST = 8, 1, 20, 100   # topside points and channels: point_defence
LASER_PERCENT, LASER_CAP, SEA_ROUGH, CLEAR_WEATHER = 15, 60, 4, 2
SPIN_BOUNDS, LASER_LABEL_BOUNDS = (92, 114, 49, 22), (8, 118)   # AA group, below AA directors
MAGIC_LASERS, MAGIC_LASER_LABEL = 0x52474E33, 0x52474E34
# Hypersonic SSMs (modern_extension's HYPERSONIC_BIT): SAMs, CIWS, radar-guided AA and lasers keep only
# HYPER_KEEP% of their kills against the SSMs such a ship fires. Flight speed stays native: the battle
# moves missiles in steps tuned to native speeds and a 5x faster one could step past its target.
# Launches are remembered by missile object address (HYPER_SLOTS most recent).
# Against the SAMs of a nation with modern_tree.HYPERSONIC_SAM that row's percent stands instead. Then an SSM of a
# nation with modern_tree.STEALTH_SSM survives some of the kills left (lasers track by heat, railguns keep their odds).
HYPER_KEEP, HYPER_SLOTS = 30, 64
HYPER_CELL_TONS = (5, 2, 1)             # heavy, medium, light SSM VLS cell: about +50% (vls_cells.CELL_TENTHS)
HYPER_CELL_COST, VLS_SIZES, SSM_TYPES = 20, (8, 16, 32, 64), (4, 5, 6)
# The missile in a VLS cell, by MountType 1-6 (heavy/medium/light SAM, heavy/medium/light SSM): cost added per cell.
# A bank's native cost follows its weight alone (about 10 a ton: 50 for a heavy SAM cell); this is the load.
CELL_COST = (60, 40, 25, 100, 60, 30)
HYPER_BOUNDS = (336, 594, 170, 16)      # Additional armament panel, under the Missile launchers group
MAGIC_HYPER = 0x52474E35
# Super heavy SSMs (modern_extension's SUPER_HEAVY_BIT; P-500 Bazalt, Kirov's P-700 Granit): CA, BC and BB hulls,
# from Effective cruise missiles. That ship's heavy SSMs reach twice as far (firing decisions and flight) and hit
# as a 40-inch shell instead of 32 (HandleHit damage grows with calibre cubed: about 2x); heavy SSM mounts weigh
# twice as much. HandleHit compares a missile's calibre only against 20 and below, so 40 changes damage alone.
SUPER_TYPES, SUPER_CALIBRE, HEAVY_SSM_MISSILE, HEAVY_SSM_MOUNT = (0, 1, 3), 40, 31, 4
SUPER_COST_PER_TON = 10   # shortcut: about the native armament cost per ton; no missile-specific figure found
SUPER_BOUNDS = (496, 594, 140, 16)      # right of Hypersonic SSMs
MAGIC_SUPER = 0x52474E36
# Extra generators (modern_extension data bits 16-23, in GEN_STEP_MW units): gas-turbine generator sets of the
# Zumwalt and Type 45 kind, about 4 t per MW with switchgear, adding railgun and laser power on any drive.
# They need Integrated power system research. Weight and cost count as armament, beside the lasers.
GEN_SHIFT, GEN_STEP_MW, GEN_MAX_UNITS, GEN_TONS, GEN_COST = 16, 10, 255, 40, 200   # tons and cost per step
GEN_SPIN_BOUNDS, GEN_LABEL_BOUNDS = (550, 448, 64, 22), (440, 452)                  # below the Power readout
MAGIC_GEN, MAGIC_GEN_LABEL = 0x52474E37, 0x52474E38
IS_HYPER = 0x2A80   # page offset of is_hyper (modern_combat speeds up hypersonic missiles)
POWER = 0xA00       # page offset of power(design, nation, flag) (ai_modern sizes AI railguns and lasers by it)
# Page offsets point_defence uses: find, scale, the laser layer it enters and the kill-stands rules.
FIND, SCALE, LASER_LAYER, SAM_STANDS, GUN_STANDS = 0x2C0, 0x4380, 0x2340, 0x2880, 0x2940
# Railgun secondaries and tertiaries (extension bits; research tree.RAILGUN_SECONDARIES): MW per gun as the main
# battery, plus pulsed-power storage per MW counted with the armament. Battle: twice the range and the railgun
# penetration for that battery. Batteries: (bit, calibre field, gun count field, battle battery number).
RAIL_BATTERIES = ((SECONDARY_RAIL_BIT, 0x71, 0xAE, 2), (TERTIARY_RAIL_BIT, 0x75, 0xB2, 3))
RAIL_TONS_PER_MW, RAIL_COST_PER_MW = 1, 50
SEC_RAIL_BOUNDS, TER_RAIL_BOUNDS = (16, 594, 145, 16), (166, 594, 145, 16)   # Additional armament, bottom left
MAGIC_SEC_RAIL, MAGIC_TER_RAIL = 0x52474E39, 0x52474E3A

# (address, size, digest) over normalized reference text.
WINDOWS = (
    (0x5EB13B, 0x27, "bfdcd0cd90aa8d3651af4e733b430a49a5853c5c374dbab3cb4c837d6a6a5195"),   # refresh epilogue
    (0x5D7290, 0x30, "a8f7507ec8396132cfc0563bc0235d699355ebcf92b363205063c8e7bdefa5b1"),   # legality: after the last check
    (0x93BE1D, 0x12, "686f48f769dd170a03dc9e128e09985b7c55191169f2c7b1aafe33b38982e390"),   # designer nation lookup
    (0x93BD8F, 0x20, "a43de25fa5895406ef393542b6b3497b77c6a9fa6545ba0821fe55203783c8da"),   # main turret weight
    (0x93BE5D, 0x20, "16048518728f090629f04328c810cd160e86e348d19c34653c00bd8f16ed769a"),   # main turret cost
    (0x93C24B, 0x2C, "1a5e932ac3efd9e3d1348dd24471e8d7bfbb7e8d080e6e318ea950c27f09e81f"),   # ammunition weights
    (0x6D66C8, 0x70, "dea24e450577071d24debf6585266765ad23afe276733c55fcc848cde16c50ad"),   # secondary/tertiary gun data
    (0x90AB88, 0x40, "f5194b40d390f4a3968d6188d25693d2e10c119d7113b732fa184dc677e27cba"),   # GetMaxRange entry
    (0x90ACEC, 0x14, "2bfa994e3846591e7fa0012d01f2c7ff67f865a7a5317a1112094f297b7d213c"),   # GetMaxRange exit
    (0x90990B, 0x6A, "adb469cc482decbad8326f52b60c1899182ffa8deb8e96a91710dbc14e72a3fe"),   # FireGuns hit arguments
    (0x91D898, 0x60, "5028b282c4d5ce7edb7c5f14d3d655d1c4e7003d669b98a9caca5f5f153921a9"),   # penetration
    (0x8F86E0, 0x50, "81d81df407cf32a2a049379e125f0424816a49fee91feef97297965196b2f029"),   # magazine hit
    (0x8F7F20, 0x50, "91bc6adc9f0b5bce28a0abbe57c40449db413e15dccad7fd7ff53c336e2425cd"),   # diving shell magazine
    (0x8F8C2C, 0x30, "d59dabedac2e4415ed85ff47f84ffd611542d2b0e227260a1377cdb6ea9c0573"),   # turret flash fire
    (0x8C1570, 0x40, "cda763c9c025fa55a792da604b8847d31f78253ee46a410ae0390d4525d44577"),   # ResolveMissileHit: CIWS step (laser layer goes first)
    (0x917075, 0x20, "e74017db7cac9d65ac2772a95fa26a393f1e33e70a6ed579c917357205fb9e71"),   # heavy AA factor: main DP guns
    (0x8763C9, 0x20, "778b86a20835f56062d500d44ed2f1f3679ecd3a0f09f57530ed13afd1295046"),   # FireSSM: the new missile's speed store
    (0x878024, 0x14, "0ff7c08ab3eb917a174df8a252261eed7dabb1abe5978387ae75b89ff713cb7c"),   # automatic SSM fire: FireSSM call
    (0x8782D9, 0x14, "3eb7205e4069e7c6adf7fbb0bbd6899793d3dd7f736e68008088f04139c5f550"),   # automatic SSM fire, second path: FireSSM call
    (0x8D4922, 0x14, "c76dc3e448364098e9328d4394744b6f1ded613f177682c2f7d9ac547b270b83"),   # Fire salvo: FireSSM call
    (0x5ADB88, 0x1E, "ae52a0bfb9603d2e5eb99667125efc9e4ebd18c983b09de582a9441863dd42b0"),   # another ship SSM launch (ship in [ebp-18h])
    (0x8C1290, 0x20, "c836737c3ee9c575b61d949b2e734715404e5105375513751b3c2a5b6e4c8d9e"),   # first SAM layer result
    (0x8C1350, 0x20, "c8b8c0e5d61b69b7815dd069dd297fa7654fa52d302e58fa63e597d1cd5f7c35"),   # second SAM layer result
    (0x8C1400, 0x18, "58fd90fa1ac356c6baf69ceadb64ee861863565c1f8be0ec107e7d2d8c93d9f1"),   # third interception layer result
    (0x8C1600, 0x18, "5a298b721e941a848bc9e1f4c32d607aa676087132fed2419096eb23379b8aca"),   # CIWS kill
    (0x8C16E8, 0x20, "83c09aee845b2037d7e07e5d953b42e4dd04bd3628485e67cebba67b4b2672d8"),   # radar-guided AA kill
    (0x877E42, 0x18, "e9110264d74a44c7dceb3f455a56306c464d5ed3af0a538530801988f2be9710"),   # automatic SSM fire: range check
    (0x87815F, 0x18, "4b3601fdd28bbc062f44690d0aa026b406ed13b7f6d4aa4f0658feb627968363"),   # automatic SSM fire, second path: range check
    (0x8D47BB, 0x18, "6edc1b5270d5b6775fa9fb38a72a89652c08ad7e40467509e7729dcd712d0b52"),   # Fire salvo: range check
    (0x91B8AF, 0x24, "8faecdfaacce81b36770219c2897a180e9d64008e321035a9eab0861dfc7301b"),   # longest SSM range of a ship
    (0x877463, 0x18, "290ca16722ce8b3af662d5bdfe682f3abbedcdd19de3af84085e0206b881080c"),   # AI heavy SSM range check
    (0x5AE542, 0x18, "277fce9171c433ed7aaf2809674b0bf77524b8ec5069fccc91fc2678f8e396e3"),   # battle screen SSM range check
    (0x5AE590, 0x18, "5fb050e09f37120d593ab92625a26140bc0adeb4b6ad7016a837e7623d7ed783"),   # battle screen SSM range check, second path
    (0x8C1B40, 0x18, "b73f35ffb1e0734437e33e7a5ee21e8210eb35d5883a74e6ea3bb8a6ab22b28e"),   # missile hit: HandleHit type
    (0x849D2C, 0x20, "82cf52c92040aa5243cb7731b51be0fa80a0698e67796927f1eac3230a923123"),   # air-launched ASM: its speed store
)
# Native routines called by the thunks, and VCL classes created at runtime.
NATIVE = dict(has_research=0x729FA4, message=0x4D7124, recompute=0x9395F8, update=0x5CCB88, refresh=0x5E9D88,
              count_guns=0x94F564, int_to_str=0x328C80, cat_n=0x30C71C, clear_n=0x30B93C, assign=0x30BCCC,
              set_text=0x451CA0, set_left=0x450EF0, set_top=0x450F24, set_width=0x450F5C, set_height=0x450F90,
              set_show_hint=0x451DCC, checkbox_vmt=0x46EF68, label_vmt=0x467348,
              range_one=0x90ABCC, range_two=0x90ABC4, range_out=0x90ACFC, fire_back=0x909950, pen_back=0x91D89E,
              no_magazine=0x8F882C, magazine_calibre=0x8F8721, magazine_small=0x8F870B,
              no_diving=0x8F7FEA, diving_back=0x8F7F55, no_flash=0x8F8D38, flash=0x8F8C56,
              legality_show=0x5D72B3, legality_skip=0x5D7508, weight_back=0x93BDA2, cost_back=0x93BE72, ammo_back=0x93C267,
              spin_vmt=0x58F214, spin_get=0x590C6C, spin_set=0x590CC4, random=0x307834, superstructure=0x910D2C,
              lstr_asg=0x30BD14, ciws_shot=0x8C161A, ciws_step=0x8C158E, precipitation=0x9F7B3C, sea=0x9F7ADC,
              fire_ssm=0x876374, record_back=0x8763E1, sam1_ok=0x8C12AE, sam1_fail=0x8C134D, sam2_ok=0x8C1368,
              sam2_fail=0x8C13FD, layer3_ok=0x8C1415, layer3_fail=0x8C14B8, ciws_back=0x8C1615, ciws_fail=0x8C16A9,
              maa_back=0x8C1701, maa_fail=0x8C1795, haa_back=0x91708E, range=0x91ACCC, hit_back=0x8C1B54,
              air_back=0x849D3E)
SITES = (("refresh", 0x5EB15B, 7), ("legality", 0x5D72A9, 10), ("turret_weight", 0x93BD9D, 5), ("turret_cost", 0x93BE6A, 8),
         ("ammo", 0x93C25F, 8), ("sec_data", 0x6D66E4, 7), ("ter_data", 0x6D6729, 7),
         ("range_entry", 0x90ABBF, 5), ("range_exit", 0x90ACF7, 5), ("fire_ie", 0x909946, 10),
         ("penetration", 0x91D898, 6), ("magazine", 0x8F8702, 9), ("diving", 0x8F7F4C, 9), ("flash", 0x8F8C4E, 8),
         ("laser_layer", 0x8C1584, 10), ("hyper_record", 0x8763DB, 6), ("launch_auto", 0x878033, 5),
         ("launch_auto2", 0x8782E8, 5), ("launch_salvo", 0x8D4931, 5), ("launch_other", 0x5ADBA1, 5),
         ("sam1", 0x8C12A6, 8), ("sam2", 0x8C1360, 8), ("layer3", 0x8C140D, 8), ("ciws_hyper", 0x8C160D, 8),
         ("maa_hyper", 0x8C16F9, 8), ("haa", 0x917088, 6), ("range_auto", 0x877E4E, 5), ("range_auto2", 0x87816B, 5),
         ("range_salvo", 0x8D47C7, 5), ("range_longest", 0x91B8B6, 5), ("range_longest2", 0x91B8C7, 5),
         ("range_ai", 0x87746E, 5), ("range_screen", 0x5AE54C, 5), ("range_screen2", 0x5AE59A, 5), ("super_hit", 0x8C1B4B, 9),
         ("air_record", 0x849D37, 7))
# Saving the value 2 is modern_extension's: it writes and reads this byte as an integer.
# Form fields (TfrmDesignMain2 RTTI) and VCL layout (TControl/TComponent RTTI, VMT slots).
FORM = dict(group_main=0x64C, group_aa=0x9F0, panel_additional=0x618, elevation=0x6A0, nation=0xC63, ship2=0xC6B, editable=0xE67, design=0xE6C,
            group_flight=0x94C)
GROUP_WIDTH = 313   # the Flight installations group at 96 DPI (the *_BOUNDS are 96-DPI): the display-scaling reference
VCL = dict(components=0x10, tag=0xC, hint=0x90, on_click=0x120, create=0x3C, set_parent=0xA0, set_enabled=0x9C,
           get_checked=0x16C, set_checked=0x170, list_add=0x3C, spin_min=0x308, spin_max=0x30C, on_change=0x2E0,
           spin_increment=0x310)
TEXT = dict(
    caption="Railgun",
    hint="Railgun main battery: double range, better penetration, no magazine explosions. Heavier, costlier "
         "mounts. Needs electric drive and power.",
    power_hint="Power: MW needed by railguns and lasers / MW the plant can spare.",
    gen_caption="Generators (MW)",
    gen_hint="Extra generators for railguns and lasers: 40 t and 200 cost per 10 MW.",
    gen_research="Extra generators need research: Integrated power system (2003, Naval combat systems).",
    err_gen_research="Error: Extra generators need Integrated power system research.",
    power="Power: ", slash=" / ", mw=" MW",
    research="Railguns need research: Electromagnetic railgun (2020, Naval combat systems).",
    drive="Railguns need electric power: Nuclear or Gas turbine propulsion, or Diesel with Hybrid diesel-electric propulsion research.",
    short="Not enough power for railguns: see Power under the hull data (needed / spare MW).",
    err_research="Error: Railguns need Electromagnetic railgun research.",
    err_drive="Error: Railguns need Nuclear or Gas turbine propulsion, or Diesel with hybrid diesel-electric drive.",
    err_power="Error: Railguns and lasers need more power than the plant can spare (see Power).",
    lasers_caption="Lasers",
    lasers_hint="Lasers against missiles, weaker in bad weather. 20 t, 1 MW and 3 topside points each.",
    laser_research="Lasers need research: Shipboard high-energy lasers (2022, Naval combat systems).",
    err_laser_research="Error: Lasers need Shipboard high-energy lasers research.",
    laser_shot=" Incoming missile shot down by laser.",
    rail_shot=" Incoming missile shot down by railgun.",
    hyper_caption="Hypersonic SSMs",
    hyper_hint="Hypersonic SSMs: much harder to shoot down. VLS SSM cells are heavier and costlier.",
    hyper_research="Hypersonic SSMs need research: Hypersonic anti-ship missiles (2023, Naval combat systems).",
    err_hyper_research="Error: Hypersonic SSMs need Hypersonic anti-ship missiles research.",
    sec_rail_caption="Railgun secondaries",
    sec_rail_hint="Secondary guns become railguns: double range, better penetration. They need power.",
    sec_rail_research="Railgun secondaries and tertiaries need research: Railgun secondary batteries (2027, Naval combat systems).",
    ter_rail_caption="Railgun tertiaries",
    ter_rail_hint="Tertiary guns become railguns: double range, better penetration. They need power.",
    ter_rail_research="Railgun secondaries and tertiaries need research: Railgun secondary batteries (2027, Naval combat systems).",
    err_rail_research="Error: Railgun secondaries and tertiaries need Railgun secondary batteries research.",
    super_caption="Super heavy SSMs",
    super_hint="Super heavy SSMs (CA, BC, BB): heavy SSMs reach twice as far and hit harder. Heavier mounts.",
    super_research="Super heavy SSMs need research: Effective cruise missiles (1960, Missile technology).",
    super_hull="Super heavy SSMs need a CA, BC or BB hull.",
    err_super_research="Error: Super heavy SSMs need Effective cruise missiles research.",
    err_super_hull="Error: Super heavy SSMs need a CA, BC or BB hull.",
)


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def discover(blob, base, normalized):
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Railguns refuse changed native code at "+hex(address)+".")
    delta = base-BASE
    for name, address in (("GetMaxRange", 0x90AB88), ("FireGuns", 0x907FE4), ("HandleHit", 0x8F7068),
                          ("ComputeAmmoWeight", 0x9462F0), ("CountGuns", 0x94F564), ("HasResearchId", 0x729FA4),
                          ("LoadMeFromBigFile", 0x94D570), ("SaveMeToBigFile", 0x94C73C), ("RecomputeValues", 0x9395F8)):
        if rt.method_address(blob, base, name) != address+delta:
            raise ValueError("Unsupported native railgun method: "+name)
    for vmt, name in ((NATIVE["checkbox_vmt"], b"TCheckBox"), (NATIVE["label_vmt"], b"TLabel"), (NATIVE["spin_vmt"], b"TSpinEdit")):
        class_name = struct.unpack_from("<I", normalized, vmt-0x38-BASE)[0]-BASE
        if normalized[class_name:class_name+1+len(name)] != bytes([len(name)])+name:
            raise ValueError("Unsupported VCL class layout: "+name.decode())
    info = {k: v+delta for k, v in NATIVE.items()}
    # GetResults reads the designer nation as [[form variable]+0xC63]; the variable comes from that code.
    info["design_form"] = struct.unpack_from("<I", blob, 0x93BE1E-BASE)[0]
    info["sites"] = [dict(name=name, address=address+delta, original=blob[address-BASE:address-BASE+size].hex())
                     for name, address, size in SITES]
    info["laser_layer_original"] = blob[0x8C1584-BASE:0x8C158E-BASE].hex()   # imul eax, [esi+0xA55], 0xA7
    import modern_combat as combat   # battle research lookups: campaign pointer and nation by index
    info["main"] = struct.unpack_from("<I", blob, combat.MAIN_LOAD-BASE+1)[0]
    info["nation"] = combat.NATIVE["nation"]+delta
    info["ciws_hyper_original"] = blob[0x8C160D-BASE:0x8C1615-BASE].hex()    # lea eax,[ebp-4]; mov edx, CIWS text
    info["maa_hyper_original"] = blob[0x8C16F9-BASE:0x8C1701-BASE].hex()     # lea eax,[ebp-4]; mov edx, AA text
    info["air_record_original"] = blob[0x849D37-BASE:0x849D3E-BASE].hex()    # mov dword [ebx+14h],300: its speed
    return info


def build(page, info, ext, names_sync=None, nuclear_missile=None, cell_cost_at=None, asbm=None, carrier_sync=None,
          propulsion_sync=None, point_defence=None, side_nation=None, carrier_weight=None):
    """Six pages: code in page, page+0x2000, page+0x3000, page+0x4000 and page+0x5000, strings in page+0x1000 and
    the gaps after them; ext is modern_extension's lookup. point_defence: its addresses() (layer, channel, weight,
    sync); side_nation: modern_recon's (a missile holds its launcher's battle side). Returns blocks, patches."""
    from campaign_security import Code   # imported late: campaign_security imports modern_research
    at = dict(scale=page+SCALE, refresh=page, sync=page+0x40, find=page+FIND, create_box=page+0x300, create_label=page+0x3C0,
              power=page+POWER, click=page+0x4C0, turret_weight=page+0xB80, haa=page+0x940,
              turret_cost=page+0x700, gun_data=page+0x780, range_entry=page+0x7A0,
              range_exit=page+0x5700, fire_ie=page+0x5780, penetration=page+0x2800, magazine=page+0x880,
              diving=page+0x8C0, flash=page+0x900, battery=page+0xFF0,
              laser_sync=page+0x2000, create_spin=page+0x2100, create_laser_label=page+0x21C0,
              laser_change=page+0x2240, laser_layer=page+LASER_LAYER, hyper_sync=page+0x2440, create_hyper=page+0x2540,
              hyper_click=page+0x2600, sam1=page+0x2700, sam2=page+0x2740, layer3=page+0x2780, ciws_hyper=page+0x27C0,
              sam_stands=page+SAM_STANDS, gun_stands=page+GUN_STANDS, drive_kind=page+0x2A00,
              maa_hyper=page+0x2A40, is_hyper=page+IS_HYPER, gen_sync=page+0x4000, create_gen=page+0x4100,
              create_gen_label=page+0x41C0, gen_change=page+0x4240,
              hyper_tons=page+0x2AC0, hyper_pending=page+0x2AC4, hyper_cursor=page+0x2AC8,
              launch_ebx=page+0x2B80, launch_frame=page+0x2BC0, air_record=page+0x2AD0,
              missile_table=page+0x3000, legality=page+0x3200, super_sync=page+0x3400, create_super=page+0x3500,
              super_click=page+0x35C0, range_ebx=page+0x3700, range_edi=page+0x3740, range_frame8=page+0x3780,
              range_frameC=page+0x37C0, super_hit=page+0x3800, is_super=page+0x3840, missile_flag=page+0x3860,
              hyper_record=page+0x3900, ammo=page+0x3A00, sec_rail_sync=page+0x5000, create_sec_rail=page+0x5100,
              sec_rail_click=page+0x51C0, ter_rail_sync=page+0x5300, create_ter_rail=page+0x5400,
              ter_rail_click=page+0x54C0, rail_mw=page+0x5600, rail_layer=page+0x5800)
    texts, blocks = {}, []
    areas = [(page+0x1000, page+0x2000), (page+0x2C00, page+0x3000), (page+0x3B80, page+0x4000), (page+0x4400, page+0x5000),
             (page+0x5A00, page+0x6000)]   # after rail_layer
    offset, end = areas.pop(0)
    for key, text in TEXT.items():
        body = literal(text); size = (len(body)+15) & ~15
        while offset+size > end:
            if not areas: raise ValueError("Railgun texts exceed their pages.")
            offset, end = areas.pop(0)
        texts[key] = offset+12
        blocks.append(dict(name="Railgun text: "+key, address=offset, bytes=body.hex()))
        offset += size
    F, V, n = FORM, VCL, info
    code = {}

    def call_slot(c, slot): c.emit(b"\x8b\x08\xff\x91"); c.u32(slot)   # mov ecx,[eax]; call [ecx+slot]

    # Refresh epilogue: EBX is the designer form.
    c = Code(at["refresh"])
    c.emit(b"\x60\x8b\xc3"); c.branch(b"\xe8", at["sync"]); c.emit(b"\x61")
    c.emit(bytes.fromhex("5f5e5b8be55dc3"))
    code["refresh"] = c.finish()

    # sync(EAX form): find or create the controls, mirror the design, write the Power text.
    c = Code(at["sync"])
    c.emit(bytes.fromhex("558bec83ec10535657"))                  # push ebp; mov ebp,esp; sub esp,16; push ebx/esi/edi
    c.emit(bytes.fromhex("8bd833c08945fc8945f88945f48945f0"))    # ebx=form; locals := 0
    c.emit(b"\x8b\xc3\xba"); c.u32(n["checkbox_vmt"]); c.emit(b"\xb9"); c.u32(MAGIC_CHECKBOX); c.branch(b"\xe8", at["find"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_box")
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["create_box"])
    c.mark("have_box"); c.emit(b"\x8b\xf8")                       # edi = checkbox
    c.emit(b"\x8b\xc3\xba"); c.u32(n["label_vmt"]); c.emit(b"\xb9"); c.u32(MAGIC_LABEL); c.branch(b"\xe8", at["find"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_label")
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["create_label"])
    c.mark("have_label"); c.emit(b"\x89\x45\xf0")                 # [ebp-16] = label
    c.emit(b"\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "finish")
    # Checkbox state follows the design without firing OnClick.
    c.emit(b"\x80\xbe"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.emit(b"\x0f\x94\xc2\x52")   # sete dl; push edx
    c.emit(b"\x8b\xc7"); call_slot(c, V["get_checked"]); c.emit(b"\x5a\x3a\xc2"); c.branch(b"\x0f\x84", "state_ok")
    c.emit(b"\xff\xb7"); c.u32(V["on_click"]); c.emit(b"\xc7\x87"); c.u32(V["on_click"]); c.u32(0)
    c.emit(b"\x8b\xc7"); call_slot(c, V["set_checked"])
    c.emit(b"\x8f\x87"); c.u32(V["on_click"])
    c.mark("state_ok")
    # Enabled: editable design, and research owned or already a railgun.
    c.emit(b"\x33\xd2\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "set_enabled")
    c.emit(b"\xb2\x01\x80\xbe"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x84", "set_enabled")
    c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.RAILGUN); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x8b\xd0")
    c.mark("set_enabled"); c.emit(b"\x8b\xc7"); call_slot(c, V["set_enabled"])
    # A railgun keeps the Increased elevation box ticked.
    c.emit(b"\x80\xbe"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "power_text")
    c.emit(b"\x8b\x83"); c.u32(F["elevation"]); call_slot(c, V["get_checked"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", "power_text")
    c.emit(b"\x8b\x83"); c.u32(F["elevation"]); c.emit(b"\xff\xb0"); c.u32(V["on_click"]); c.emit(b"\xc7\x80"); c.u32(V["on_click"]); c.u32(0)
    c.emit(b"\xb2\x01"); call_slot(c, V["set_checked"])
    c.emit(b"\x8b\x83"); c.u32(F["elevation"]); c.emit(b"\x8f\x80"); c.u32(V["on_click"])
    c.mark("power_text")
    c.emit(b"\x8b\xc6\x33\xc9\x8b\x93"); c.u32(F["nation"]); c.branch(b"\xe8", at["power"])
    c.emit(b"\x52\x8d\x55\xfc"); c.branch(b"\xe8", n["int_to_str"])
    c.emit(b"\x58\x8d\x55\xf8"); c.branch(b"\xe8", n["int_to_str"])
    c.emit(b"\x68"); c.u32(texts["power"]); c.emit(b"\xff\x75\xfc\x68"); c.u32(texts["slash"])
    c.emit(b"\xff\x75\xf8\x68"); c.u32(texts["mw"]); c.emit(b"\x8d\x45\xf4\xba\x05\x00\x00\x00"); c.branch(b"\xe8", n["cat_n"])
    c.emit(b"\x8b\x45\xf0\x8b\x55\xf4"); c.branch(b"\xe8", n["set_text"])
    c.mark("finish"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["laser_sync"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["hyper_sync"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["super_sync"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["gen_sync"])
    for name in ("sec_rail", "ter_rail"):
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at[name+"_sync"])
    if names_sync:   # designer_names: captions of modules that research replaces
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", names_sync)
    if carrier_sync:   # modern_carrier: the Ski jump box in Flight installations
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", carrier_sync)
    if propulsion_sync:   # modern_propulsion: the Range box, greyed for a nuclear design
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", propulsion_sync)
    if point_defence:   # the point-defence strip under the armament tabs
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", point_defence["sync"])
    c.emit(b"\x8d\x45\xf4\xba\x03\x00\x00\x00"); c.branch(b"\xe8", n["clear_n"])
    c.emit(bytes.fromhex("5f5e5b8be55dc3"))
    code["sync"] = c.finish()

    # find(EAX form, EDX class, ECX tag) -> EAX component or 0; scans the form's components.
    c = Code(at["find"])
    c.emit(b"\x53\x56\x8b\x40"); c.emit(bytes([V["components"]])); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "none")
    c.emit(b"\x8b\x70\x08\x8b\x40\x04")
    c.mark("next"); c.emit(b"\x4e"); c.branch(b"\x0f\x88", "none")
    c.emit(b"\x8b\x1c\xb0\x39\x13"); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x39\x4b"); c.emit(bytes([V["tag"]])); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x8b\xc3\x5e\x5b\xc3")
    c.mark("none"); c.emit(b"\x33\xc0\x5e\x5b\xc3")
    code["find"] = c.finish()

    def create(c, vmt, magic, parent_field, bounds, hint):
        c.emit(b"\x53\x56\x8b\xd8\x8b\xcb\xb2\x01\xb8"); c.u32(vmt); c.emit(b"\xff\x50"); c.emit(bytes([V["create"]]))
        c.emit(b"\x8b\xf0\xc7\x46"); c.emit(bytes([V["tag"]])); c.u32(magic)
        c.emit(b"\x8b\x93" if parent_field else b"\x8b\xd3")
        if parent_field: c.u32(parent_field)
        c.emit(b"\x8b\xc6"); call_slot(c, V["set_parent"])
        for setter, value in zip(("set_left", "set_top", "set_width", "set_height"), bounds):
            c.emit(b"\xba"); c.u32(value); c.branch(b"\xe8", at["scale"]); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n[setter])
        c.emit(b"\x8d\x86"); c.u32(V["hint"]); c.emit(b"\xba"); c.u32(texts[hint]); c.branch(b"\xe8", n["assign"])
        c.emit(b"\xb2\x01\x8b\xc6"); c.branch(b"\xe8", n["set_show_hint"])

    c = Code(at["create_box"])   # EAX form -> EAX checkbox
    create(c, n["checkbox_vmt"], MAGIC_CHECKBOX, F["group_main"], CHECKBOX_BOUNDS, "hint")
    c.emit(b"\xba"); c.u32(texts["caption"]); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["set_text"])
    c.emit(b"\xc7\x86"); c.u32(V["on_click"]); c.u32(at["click"]); c.emit(b"\x89\x9e"); c.u32(V["on_click"]+4)
    c.emit(b"\x8b\xc6\x5e\x5b\xc3")
    code["create_box"] = c.finish()
    c = Code(at["create_label"])   # EAX form -> EAX label (parent: the form)
    create(c, n["label_vmt"], MAGIC_LABEL, 0, LABEL_BOUNDS, "power_hint")
    c.emit(b"\x8b\xc6\x5e\x5b\xc3")
    code["create_label"] = c.finish()

    # drive_kind(EAX design, EDX nation) -> EAX its propulsion as the electric rules see it: Diesel with tree.HYBRID
    # research reads as Gas turbine (diesel generators and electric motors). Keeps EBX/ESI/EDI.
    c = Code(at["drive_kind"]); c.emit(b"\x0f\xb6\x88"); c.u32(0x9D4)
    c.emit(b"\x80\xf9"+bytes([DIESEL])); c.branch(b"\x0f\x85", "plain")
    c.emit(b"\x51\x8b\xc2\xba"); c.u32(tree.HYBRID[0]); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x59\x84\xc0")
    c.branch(b"\x0f\x84", "plain"); c.emit(b"\xb9\x04\x00\x00\x00")
    c.mark("plain"); c.emit(b"\x8b\xc1\xc3")
    code["drive_kind"] = c.finish()

    code["scale"] = dpi_scale_routine(F["group_flight"], GROUP_WIDTH)   # EDX: a 96-DPI bound -> on screen

    # power(EAX design, EDX nation, ECX 1: count the main battery as railguns) -> EAX MW the railguns and lasers
    # need, EDX MW the plant can spare. The main battery counts when it is a railgun or ECX asks (ticking it).
    c = Code(at["power"])
    c.emit(b"\x53\x56\x57\x8b\xd8\x8b\xfa\x33\xf6\xf6\xc1\x01"); c.branch(b"\x0f\x85", "main")
    c.emit(b"\x80\xbb"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "secondaries")
    c.mark("main"); c.emit(b"\x83\x7b\x6d\x00"); c.branch(b"\x0f\x8e", "secondaries")
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["count_guns"])
    c.emit(b"\x8b\x4b\x6d\x0f\xaf\xc9\x0f\xaf\xc1\x6b\xc0"); c.emit(bytes([MW_PER_GUN_5IN]))
    c.emit(b"\x83\xc0\x0c\x33\xd2\xb9\x19\x00\x00\x00\xf7\xf1\x8b\xf0")   # (+12)/25: x16/25 = per (calibre/5)^2
    c.mark("secondaries"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["rail_mw"]); c.emit(b"\x03\xf0")
    for index, ident in enumerate(tree.RAILGUN_EFFICIENCY):   # pulsed-power research: x3/4 each
        c.emit(b"\x8b\xc7\xba"); c.u32(ident); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x84\xc0")
        c.branch(b"\x0f\x84", f"efficient{index}"); c.emit(b"\x8d\x34\x76\xc1\xee\x02")   # esi = esi*3/4
        c.mark(f"efficient{index}")
    multiplier = lambda percent: 746*percent//25
    c.mark("spare"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no_lasers")
    c.emit(b"\x0f\xb6\x00\x6b\xc0"); c.emit(bytes([LASER_MW])); c.emit(b"\x03\xf0")   # needed += lasers x MW
    c.mark("no_lasers"); c.emit(b"\x8b\xc3\x8b\xd7"); c.branch(b"\xe8", at["drive_kind"])
    c.emit(b"\x3c\x04"); c.branch(b"\x0f\x85", "not_gas")
    ident, percent = tree.INTEGRATED_POWER
    c.emit(b"\xb9"); c.u32(multiplier(GAS_TURBINE_SPARE))
    c.emit(b"\x51\x8b\xc7\xba"); c.u32(ident); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x59\x84\xc0")
    c.branch(b"\x0f\x84", "share"); c.emit(b"\xb9"); c.u32(multiplier(percent)); c.branch(b"\xe9", "share")
    c.mark("not_gas"); c.emit(b"\x33\xd2\x3c\x05"); c.branch(b"\x0f\x85", "done")
    c.emit(b"\xb9"); c.u32(multiplier(tree.NUCLEAR_SPARE))
    for index, (ident, percent) in enumerate(tree.REACTOR_GENERATIONS):   # newest first
        c.emit(b"\x51\x8b\xc7\xba"); c.u32(ident); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x59\x84\xc0")
        c.branch(b"\x0f\x84", f"older{index}"); c.emit(b"\xb9"); c.u32(multiplier(percent)); c.branch(b"\xe9", "share")
        c.mark(f"older{index}")
    c.mark("share"); c.emit(b"\x8b\x43\x3c\xf7\xe1\xb9"); c.u32(SPARE_DIVISOR); c.emit(b"\xf7\xf1\x8b\xd0")
    c.mark("done"); c.emit(b"\x52\x8b\xc3"); c.branch(b"\xe8", ext); c.emit(b"\x5a\x85\xc0"); c.branch(b"\x0f\x84", "spared")
    c.emit(b"\x0f\xb6\x40"+bytes([GEN_SHIFT//8])+b"\x6b\xc0"+bytes([GEN_STEP_MW])+b"\x03\xd0")   # spare += generators
    c.mark("spared"); c.emit(b"\x8b\xc6\x5f\x5e\x5b\xc3")
    code["power"] = c.finish()

    # OnClick(EAX form, EDX checkbox).
    c = Code(at["click"])
    c.emit(b"\x60\x8b\xd8\x8b\xfa\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x8b\xc7"); call_slot(c, V["get_checked"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "untick")
    c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.RAILGUN); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0\xb8"); c.u32(texts["research"]); c.branch(b"\x0f\x84", "refuse")
    c.emit(b"\x8b\xc6\x8b\x93"); c.u32(F["nation"]); c.branch(b"\xe8", at["drive_kind"])
    for kind in ELECTRIC:
        c.emit(b"\x3c"+bytes([kind])); c.branch(b"\x0f\x84", "drive_ok")
    c.emit(b"\xb8"); c.u32(texts["drive"]); c.branch(b"\xe9", "refuse")
    c.mark("drive_ok"); c.emit(b"\x8b\xc6\xb9\x01\x00\x00\x00\x8b\x93"); c.u32(F["nation"]); c.branch(b"\xe8", at["power"])
    c.emit(b"\x3b\xc2\xb8"); c.u32(texts["short"]); c.branch(b"\x0f\x87", "refuse")
    c.emit(b"\xb0"+bytes([RAILGUN])); c.branch(b"\xe9", "store")
    c.mark("untick"); c.emit(b"\x80\xbe"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "resync")
    c.emit(b"\xb0\x01")   # untick keeps increased elevation
    c.mark("store"); c.emit(b"\x88\x86"); c.u32(0x9A6)
    c.emit(b"\x8b\x8b"); c.u32(F["ship2"]); c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "stored")
    c.emit(b"\x88\x81"); c.u32(0x9A6)
    c.mark("stored"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["recompute"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["update"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["refresh"])
    c.emit(b"\x61\xc3")
    c.mark("refuse"); c.emit(b"\x83\xca\xff\x83\xc9\xff"); c.branch(b"\xe8", n["message"])
    c.mark("resync"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["sync"]); c.emit(b"\x61\xc3")
    code["click"] = c.finish()

    # Legality check, after its last native test and before the error lines are shown:
    # EBX design, ESI form, [ebp-0Ch] error lines, [ebp-6] legal flag, [ebp-5] show report.
    c = Code(at["legality"])
    c.emit(b"\x60\x8b\xc3"); c.branch(b"\xe8", ext); c.emit(b"\x33\xff\x85\xc0"); c.branch(b"\x0f\x84", "no_ext")
    c.emit(b"\x0f\xb6\x38")                                                   # edi = lasers
    c.emit(b"\x80\x78"+bytes([GEN_SHIFT//8])+b"\x00"); c.branch(b"\x0f\x84", "no_gen")   # extra generators
    c.emit(b"\x50"); c.branch(b"\xe8", "gen_research"); c.emit(b"\x58")
    c.mark("no_gen")
    c.emit(b"\xf7\x00"); c.u32(SECONDARY_RAIL_BIT | TERTIARY_RAIL_BIT); c.branch(b"\x0f\x84", "no_rail2")
    c.emit(b"\x50"); c.branch(b"\xe8", "rail2_research"); c.emit(b"\x58")
    c.mark("no_rail2")
    c.emit(b"\xf7\x00"); c.u32(HYPER_BIT); c.branch(b"\x0f\x84", "no_hyper"); c.emit(b"\x50"); c.branch(b"\xe8", "hyper_research")
    c.emit(b"\x58")
    c.mark("no_hyper"); c.emit(b"\xf7\x00"); c.u32(SUPER_BIT); c.branch(b"\x0f\x84", "no_ext"); c.branch(b"\xe8", "super_checks")
    c.mark("no_ext"); c.emit(b"\x80\xbb"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "lasers_only")
    c.emit(b"\x8b\x86"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.RAILGUN); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", "research_ok")
    c.emit(b"\xba"); c.u32(texts["err_research"]); c.branch(b"\xe8", "add")
    c.mark("research_ok"); c.emit(b"\x8b\xc3\x8b\x96"); c.u32(F["nation"]); c.branch(b"\xe8", at["drive_kind"])
    for kind in ELECTRIC:
        c.emit(b"\x3c"+bytes([kind])); c.branch(b"\x0f\x84", "with_power")
    c.emit(b"\xba"); c.u32(texts["err_drive"]); c.branch(b"\xe8", "add")
    c.branch(b"\xe8", "laser_research"); c.branch(b"\xe9", "checked")       # power is moot without electric drive
    c.mark("lasers_only"); c.emit(b"\x85\xff"); c.branch(b"\x0f\x85", "with_power")
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "checked")
    c.emit(b"\xf7\x00"); c.u32(SECONDARY_RAIL_BIT | TERTIARY_RAIL_BIT); c.branch(b"\x0f\x84", "checked")
    c.mark("with_power"); c.branch(b"\xe8", "laser_research")
    c.emit(b"\x8b\xc3\x33\xc9\x8b\x96"); c.u32(F["nation"]); c.branch(b"\xe8", at["power"])
    c.emit(b"\x3b\xc2"); c.branch(b"\x0f\x86", "checked")
    c.emit(b"\xba"); c.u32(texts["err_power"]); c.branch(b"\xe8", "add")
    c.mark("checked"); c.emit(b"\x61")
    c.mark("replay"); c.emit(b"\x80\x7d\xfb\x00"); c.branch(b"\x0f\x84", n["legality_skip"]); c.branch(b"\xe9", n["legality_show"])
    c.mark("add"); c.emit(b"\x8b\x45\xf4\x8b\x08\xff\x51"); c.emit(bytes([V["list_add"]])); c.emit(b"\xc6\x45\xfa\x00\xc3")
    c.mark("laser_research")   # EDI lasers: research needed for any
    c.emit(b"\x85\xff"); c.branch(b"\x0f\x84", "laser_ok")
    c.emit(b"\x8b\x86"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.LASERS); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", "laser_ok")
    c.emit(b"\xba"); c.u32(texts["err_laser_research"]); c.branch(b"\xe8", "add")
    c.mark("laser_ok"); c.emit(b"\xc3")
    c.mark("hyper_research"); c.emit(b"\xba"); c.u32(tree.HYPERSONIC); c.emit(b"\xb9"); c.u32(texts["err_hyper_research"])
    c.branch(b"\xe9", "need")
    c.mark("super_checks")
    c.emit(b"\x8b\x86"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.SUPER_HEAVY); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", "super_research_ok")
    c.emit(b"\xba"); c.u32(texts["err_super_research"]); c.branch(b"\xe8", "add")
    c.mark("super_research_ok"); c.emit(b"\x0f\xb6\x83"); c.u32(0x9D3)                   # ship type
    for kind in SUPER_TYPES:
        c.emit(b"\x3c"+bytes([kind])); c.branch(b"\x0f\x84", "super_hull_ok")
    c.emit(b"\xba"); c.u32(texts["err_super_hull"]); c.branch(b"\xe8", "add")
    c.mark("super_hull_ok"); c.emit(b"\xc3")
    c.mark("rail2_research"); c.emit(b"\xba"); c.u32(tree.RAILGUN_SECONDARIES); c.emit(b"\xb9"); c.u32(texts["err_rail_research"])
    c.branch(b"\xe9", "need")
    c.mark("gen_research"); c.emit(b"\xba"); c.u32(tree.INTEGRATED_POWER[0]); c.emit(b"\xb9"); c.u32(texts["err_gen_research"])
    c.mark("need")   # EDX research, ECX error line: added unless the nation has the research
    c.emit(b"\x51\x8b\x86"); c.u32(F["nation"]); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x5a\x84\xc0")
    c.branch(b"\x0f\x84", "add"); c.emit(b"\xc3")
    code["legality"] = c.finish()

    # GetResults main-turret loop: EBX -> design pointer, EDI turret, ESI turret cost.
    c = Code(at["turret_weight"])
    c.emit(b"\x8b\x13\x80\xba"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "native")
    c.emit(b"\x51\xb9"); c.u32(MOUNT_WEIGHT)
    for index, (ident, percent) in enumerate(tree.LIGHTER_MOUNTS):   # newest first
        c.emit(b"\x51\xa1"); c.u32(info["design_form"]); c.emit(b"\x8b\x00\x8b\x80"); c.u32(FORM["nation"])
        c.emit(b"\xba"); c.u32(ident); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x59\x84\xc0")
        c.branch(b"\x0f\x84", f"older{index}"); c.emit(b"\xb9"); c.u32(percent); c.branch(b"\xe9", "apply")
        c.mark(f"older{index}")
    c.mark("apply"); c.emit(b"\x8b\x47\x17\x0f\xaf\xc1\xb9\x64\x00\x00\x00\x99\xf7\xf9\x89\x47\x17\x59")   # weight x percent/100
    c.mark("native"); c.emit(b"\x8b\x47\x17\x8b\x13"); c.branch(b"\xe9", n["weight_back"])
    code["turret_weight"] = c.finish()
    c = Code(at["turret_cost"])
    c.emit(b"\x8b\x03\x80\xb8"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "native")
    c.emit(b"\x56\x8d\x34\xb6\xd1\xee\x01\xb0"); c.u32(0xA8C); c.emit(b"\x5e"); c.branch(b"\xe9", n["cost_back"])   # x2.5
    c.mark("native"); c.emit(b"\x01\xb0"); c.u32(0xA8C); c.branch(b"\xe9", n["cost_back"])
    code["turret_cost"] = c.finish()
    c = Code(at["ammo"])   # EAX main-battery ammunition weight
    c.emit(b"\x8b\x13\x80\xba"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "store")
    c.emit(b"\xd1\xe8")
    c.mark("store"); c.emit(b"\x89\x82"); c.u32(0xAAC)
    c.emit(b"\x60")                                                              # pushad; EDX design
    if cell_cost_at: c.branch(b"\xe8", cell_cost_at)                             # every VLS cell's missile
    if point_defence: c.branch(b"\xe8", point_defence["weight"])                 # SeaRAM, gun-missile, RAM
    if carrier_weight: c.branch(b"\xe8", carrier_weight)                         # modern_carrier: the ski jump
    c.emit(b"\x8b\xc2"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\xf0\x0f\xb6\x06\x6b\xc8"); c.emit(bytes([LASER_TONS])); c.emit(b"\x01\x8a"); c.u32(0xAA4)   # armament weight
    c.emit(b"\x6b\xc8"); c.emit(bytes([LASER_COST])); c.emit(b"\x01\x8a"); c.u32(0xA8C)                    # armament cost
    c.emit(b"\x0f\xb6\x46"+bytes([GEN_SHIFT//8])+b"\x6b\xc8"+bytes([GEN_TONS])); c.emit(b"\x01\x8a"); c.u32(0xAA4)   # generators
    c.emit(b"\x69\xc8"); c.u32(GEN_COST); c.emit(b"\x01\x8a"); c.u32(0xA8C)
    c.emit(b"\x8b\xc2"); c.branch(b"\xe8", at["rail_mw"])                    # railgun secondaries and tertiaries
    c.emit(b"\x6b\xc8"+bytes([RAIL_TONS_PER_MW])); c.emit(b"\x01\x8a"); c.u32(0xAA4)
    c.emit(b"\x6b\xc8"+bytes([RAIL_COST_PER_MW])); c.emit(b"\x01\x8a"); c.u32(0xA8C)
    # Hypersonic: extra weight and cost per SSM VLS cell (MountType 4-6 with 8/16/32/64 tubes, as vls_cells).
    # Super heavy: each heavy SSM mount (launcher or VLS bank) weighs its native weight again.
    c.emit(b"\xf7\x06"); c.u32(HYPER_BIT | SUPER_BIT); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xff\x36\x8b\x82"); c.u32(0x9E); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "flags")   # [esp] data; mounts
    c.emit(b"\x8b\x48\x08\x8b\x70\x04\x33\xff\x33\xed")                                   # ecx count, esi items
    c.mark("next"); c.emit(b"\x49"); c.branch(b"\x0f\x88", "sum")
    c.emit(b"\x8b\x04\x8e\x0f\xb6\x58\x0e\xf7\x04\x24"); c.u32(SUPER_BIT); c.branch(b"\x0f\x84", "hyper")
    c.emit(b"\x83\xfb"+bytes([HEAVY_SSM_MOUNT])); c.branch(b"\x0f\x85", "hyper")
    c.emit(b"\x8b\x58\x0a\x03\xfb\x6b\xdb"+bytes([SUPER_COST_PER_TON])+b"\x03\xeb\x0f\xb6\x58\x0e")
    c.mark("hyper"); c.emit(b"\xf7\x04\x24"); c.u32(HYPER_BIT); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x83\xeb"); c.emit(bytes([SSM_TYPES[0]]))                                       # ebx = SSM size index
    c.emit(b"\x83\xfb"); c.emit(bytes([len(SSM_TYPES)-1])); c.branch(b"\x0f\x87", "next")
    c.emit(b"\x8b\x40\x04")                                                                  # eax = Tubes
    for size in VLS_SIZES:
        c.emit(b"\x83\xf8"+bytes([size])); c.branch(b"\x0f\x84", "vls")
    c.branch(b"\xe9", "next")
    c.mark("vls"); c.emit(b"\x0f\xb6\x9b"); c.u32(at["hyper_tons"]); c.emit(b"\x0f\xaf\xd8\x03\xfb")
    c.emit(b"\x6b\xc0"); c.emit(bytes([HYPER_CELL_COST])); c.emit(b"\x03\xe8"); c.branch(b"\xe9", "next")
    c.mark("sum"); c.emit(b"\x01\xba"); c.u32(0xAA4); c.emit(b"\x01\xaa"); c.u32(0xA8C)
    c.mark("flags"); c.emit(b"\x58")
    c.mark("done"); c.emit(b"\x61"); c.branch(b"\xe9", n["ammo_back"])
    code["ammo"] = c.finish()
    cell_cost = None
    if cell_cost_at:   # EDX design: armament cost += CELL_COST for every cell of its VLS banks. Keeps EDX only.
        c = Code(cell_cost_at); c.emit(b"\xeb"+bytes([len(CELL_COST)])); costs = c.address+len(c.data); c.emit(bytes(CELL_COST))
        c.emit(b"\x8b\x82"); c.u32(0x9E); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "none")
        c.emit(b"\x8b\x48\x08\x8b\x70\x04\x33\xed")
        c.mark("cell"); c.emit(b"\x49"); c.branch(b"\x0f\x88", "sum")
        c.emit(b"\x8b\x04\x8e\x0f\xb6\x58\x0e\x4b\x83\xfb\x05"); c.branch(b"\x0f\x87", "cell")
        c.emit(b"\x8b\x40\x04\x83\xf8"+bytes([VLS_SIZES[0]])); c.branch(b"\x0f\x82", "cell")
        c.emit(b"\x0f\xb6\x9b"); c.u32(costs); c.emit(b"\x0f\xaf\xc3\x03\xe8"); c.branch(b"\xe9", "cell")
        c.mark("sum"); c.emit(b"\x01\xaa"); c.u32(0xA8C)
        c.mark("none"); c.emit(b"\xc3")
        cell_cost = c.finish()
        if len(cell_cost) > 0x80: raise ValueError("Railgun code exceeds its reservation: cell_cost")

    # laser_sync(EAX form): find or create the Lasers box and label, mirror the design silently.
    c = Code(at["laser_sync"])
    c.emit(b"\x53\x56\x57\x8b\xd8\x8b\xc3\xba"); c.u32(n["spin_vmt"]); c.emit(b"\xb9"); c.u32(MAGIC_LASERS); c.branch(b"\xe8", at["find"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_spin"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["create_spin"])
    c.mark("have_spin"); c.emit(b"\x8b\xf8\x8b\xc3\xba"); c.u32(n["label_vmt"]); c.emit(b"\xb9"); c.u32(MAGIC_LASER_LABEL)
    c.branch(b"\xe8", at["find"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_label")
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["create_laser_label"])
    c.mark("have_label"); c.emit(b"\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no_ext")
    c.emit(b"\x0f\xb6\x00"); c.branch(b"\xe9", "have_count")
    c.mark("no_ext"); c.emit(b"\x33\xc0")
    c.mark("have_count"); c.emit(b"\x50\x8b\xc7"); c.branch(b"\xe8", n["spin_get"]); c.emit(b"\x3b\x04\x24"); c.branch(b"\x0f\x84", "value_ok")
    c.emit(b"\xff\xb7"); c.u32(V["on_change"]); c.emit(b"\xc7\x87"); c.u32(V["on_change"]); c.u32(0)
    c.emit(b"\x8b\xc7\x8b\x54\x24\x04"); c.branch(b"\xe8", n["spin_set"]); c.emit(b"\x8f\x87"); c.u32(V["on_change"])
    c.mark("value_ok"); c.emit(b"\x33\xd2\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "set_enabled")
    c.emit(b"\xb2\x01\x83\x3c\x24\x00"); c.branch(b"\x0f\x85", "set_enabled")
    c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.LASERS); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x8b\xd0")
    c.mark("set_enabled"); c.emit(b"\x8b\xc7"); call_slot(c, V["set_enabled"]); c.emit(b"\x58")
    c.mark("done"); c.emit(b"\x5f\x5e\x5b\xc3")
    code["laser_sync"] = c.finish()

    c = Code(at["create_spin"])   # EAX form -> EAX Lasers box (0..MAX_LASERS, OnChange laser_change)
    create(c, n["spin_vmt"], MAGIC_LASERS, F["group_aa"], SPIN_BOUNDS, "lasers_hint")
    c.emit(b"\xc7\x86"); c.u32(V["spin_min"]); c.u32(0); c.emit(b"\xc7\x86"); c.u32(V["spin_max"]); c.u32(MAX_LASERS)
    c.emit(b"\xc7\x86"); c.u32(V["on_change"]); c.u32(at["laser_change"]); c.emit(b"\x89\x9e"); c.u32(V["on_change"]+4)
    c.emit(b"\x8b\xc6\x5e\x5b\xc3")
    code["create_spin"] = c.finish()
    c = Code(at["create_laser_label"])
    create(c, n["label_vmt"], MAGIC_LASER_LABEL, F["group_aa"], LASER_LABEL_BOUNDS, "lasers_hint")
    c.emit(b"\xba"); c.u32(texts["lasers_caption"]); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["set_text"])
    c.emit(b"\x8b\xc6\x5e\x5b\xc3")
    code["create_laser_label"] = c.finish()

    # OnChange(EAX form, EDX Lasers box).
    c = Code(at["laser_change"])
    c.emit(b"\x60\x8b\xd8\x8b\xfa\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x8b\xc7"); c.branch(b"\xe8", n["spin_get"]); c.emit(b"\x8b\xe8\x83\xfd"); c.emit(bytes([MAX_LASERS]))
    c.branch(b"\x0f\x86", "in_range"); c.emit(b"\xbd"); c.u32(MAX_LASERS)
    c.mark("in_range"); c.emit(b"\x85\xed"); c.branch(b"\x0f\x84", "store")
    c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.LASERS); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", "store")
    c.emit(b"\xb8"); c.u32(texts["laser_research"]); c.emit(b"\x83\xca\xff\x83\xc9\xff"); c.branch(b"\xe8", n["message"])
    c.branch(b"\xe9", "resync")
    c.mark("store"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x8b\x08\x81\xe1\x00\xff\xff\xff\x0b\xcd\x89\x08")                # keep other data bits
    c.emit(b"\x8b\x83"); c.u32(F["ship2"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "stored")
    c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "stored")
    c.emit(b"\x8b\x08\x81\xe1\x00\xff\xff\xff\x0b\xcd\x89\x08")
    c.mark("stored"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["recompute"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["update"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["refresh"])
    c.emit(b"\x61\xc3")
    c.mark("resync"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["laser_sync"]); c.emit(b"\x61\xc3")
    code["laser_change"] = c.finish()

    # ResolveMissileHit, before CIWS: ESI target ship, EBX incoming missile (speed +0x14), EBP frame.
    c = Code(at["laser_layer"])
    c.emit(b"\x60\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x0f\xb6\x38\x85\xff"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\xb8\x64\x00\x00\x00"); c.branch(b"\xe8", n["random"]); c.emit(b"\x50\x8b\xc6"); c.branch(b"\xe8", n["superstructure"])
    c.emit(b"\x5a\x3b\xd0"); c.branch(b"\x0f\x8e", "no")                         # knocked out with the superstructure
    if point_defence:   # a fire-control channel left after SeaRAM and gun-missile mounts
        c.emit(b"\x80\x3d"); c.u32(point_defence["channel"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "no")
        c.emit(b"\xfe\x0d"); c.u32(point_defence["channel"])
    c.emit(b"\x6b\xff"); c.emit(bytes([LASER_PERCENT])); c.emit(b"\x83\xff"); c.emit(bytes([LASER_CAP]))
    c.branch(b"\x0f\x8e", "capped"); c.emit(b"\xbf"); c.u32(LASER_CAP)
    c.mark("capped"); c.emit(b"\xa1"); c.u32(n["precipitation"]); c.emit(b"\x80\x38"); c.emit(bytes([CLEAR_WEATHER]))
    c.branch(b"\x0f\x84", "dry"); c.emit(b"\xd1\xef")
    c.mark("dry"); c.emit(b"\xa1"); c.u32(n["sea"]); c.emit(b"\x83\x38"); c.emit(bytes([SEA_ROUGH]))
    c.branch(b"\x0f\x8c", "calm"); c.emit(b"\xd1\xef")
    c.mark("calm"); c.branch(b"\xe8", at["is_hyper"]); c.branch(b"\x0f\x84", "slow")
    c.emit(b"\x8d\x3c\x7f\x8b\xc7\x33\xd2\xb9\x0a\x00\x00\x00\xf7\xf1\x8b\xf8")   # 30% against hypersonic missiles
    c.mark("slow"); c.emit(b"\xb8\x64\x00\x00\x00"); c.branch(b"\xe8", n["random"]); c.emit(b"\x3b\xc7"); c.branch(b"\x0f\x8d", "no")
    c.emit(b"\x61\x8d\x45\xfc\xba"); c.u32(texts["laser_shot"]); c.branch(b"\xe8", n["lstr_asg"]); c.branch(b"\xe9", n["ciws_shot"])
    c.mark("no"); c.emit(b"\x61"); c.branch(b"\xe9", at["rail_layer"])
    code["laser_layer"] = c.finish()
    # Then railgun point defence, ESI target ship, EBX missile: each DP railgun battery adds a chance, capped,
    # a third of it against hypersonic missiles; the defending nation needs the research.
    import modern_combat as combat
    ident, percent, cap = tree.RAILGUN_POINT_DEFENCE
    c = Code(at["rail_layer"])
    c.emit(b"\x60\x33\xff\x80\xbe"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "secondaries")
    c.emit(b"\x80\xbe"); c.u32(0x85); c.emit(b"\x00"); c.branch(b"\x0f\x84", "secondaries"); c.emit(b"\x83\xc7"+bytes([percent]))
    c.mark("secondaries"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "any")
    c.emit(b"\x8b\x08")
    for bit, _, _, number in RAIL_BATTERIES:   # GunsDP: one byte per battery from 0x85
        c.emit(b"\xf7\xc1"); c.u32(bit); c.branch(b"\x0f\x84", f"skip{number}")
        c.emit(b"\x80\xbe"); c.u32(0x84+number); c.emit(b"\x00"); c.branch(b"\x0f\x84", f"skip{number}")
        c.emit(b"\x83\xc7"+bytes([percent]))
        c.mark(f"skip{number}")
    c.mark("any"); c.emit(b"\x85\xff"); c.branch(b"\x0f\x84", "no")
    combat.researched(c, n, b"\x8b\x56\x14", ident, "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x83\xff"+bytes([cap])); c.branch(b"\x0f\x8e", "capped"); c.emit(b"\xbf"); c.u32(cap)
    c.mark("capped"); c.branch(b"\xe8", at["is_hyper"]); c.branch(b"\x0f\x84", "slow")
    c.emit(b"\x8b\xc7\x33\xd2\xb9\x03\x00\x00\x00\xf7\xf1\x8b\xf8")               # a third against hypersonic missiles
    c.mark("slow"); c.emit(b"\xb8\x64\x00\x00\x00"); c.branch(b"\xe8", n["random"]); c.emit(b"\x3b\xc7"); c.branch(b"\x0f\x8d", "no")
    c.emit(b"\x61\x8d\x45\xfc\xba"); c.u32(texts["rail_shot"]); c.branch(b"\xe8", n["lstr_asg"]); c.branch(b"\xe9", n["ciws_shot"])
    c.mark("no"); c.emit(b"\x61")
    if point_defence:   # the gun CIWS needs a channel left too (railgun point defence takes none)
        c.emit(b"\x80\x3d"); c.u32(point_defence["channel"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", n["ciws_fail"])
    c.emit(bytes.fromhex(info["laser_layer_original"])); c.branch(b"\xe9", n["ciws_step"])
    code["rail_layer"] = c.finish()

    def option(name, bit, magic, bounds, research, hulls=()):
        """Additional armament tick box mirroring an extension bit: name_sync(EAX form), create_name, name_click."""
        c = Code(at[name+"_sync"])   # find or create the box, mirror the design silently
        c.emit(b"\x53\x56\x57\x8b\xd8\x8b\xc3\xba"); c.u32(n["checkbox_vmt"]); c.emit(b"\xb9"); c.u32(magic); c.branch(b"\xe8", at["find"])
        c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_box"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["create_"+name])
        c.mark("have_box"); c.emit(b"\x8b\xf8\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "done")
        c.emit(b"\x33\xd2\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "have_flag")
        c.emit(b"\xf7\x00"); c.u32(bit); c.emit(b"\x0f\x95\xc2")                               # dl = flag
        c.mark("have_flag"); c.emit(b"\x52\x8b\xc7"); call_slot(c, V["get_checked"]); c.emit(b"\x5a\x52\x3a\xc2"); c.branch(b"\x0f\x84", "state_ok")
        c.emit(b"\xff\xb7"); c.u32(V["on_click"]); c.emit(b"\xc7\x87"); c.u32(V["on_click"]); c.u32(0)
        c.emit(b"\x8b\xc7"); call_slot(c, V["set_checked"]); c.emit(b"\x8f\x87"); c.u32(V["on_click"])
        c.mark("state_ok"); c.emit(b"\x5a\x84\xd2"); c.branch(b"\x0f\x85", "editable")   # ticked: editable designs may untick
        c.emit(b"\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "set_enabled")
        c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(research); c.branch(b"\xe8", n["has_research"])
        c.emit(b"\x8b\xd0"); c.branch(b"\xe9", "set_enabled")
        c.mark("editable"); c.emit(b"\x8a\x93"); c.u32(F["editable"])
        c.mark("set_enabled"); c.emit(b"\x8b\xc7"); call_slot(c, V["set_enabled"])
        c.mark("done"); c.emit(b"\x5f\x5e\x5b\xc3")
        code[name+"_sync"] = c.finish()

        c = Code(at["create_"+name])   # EAX form -> EAX box on the Additional armament panel
        create(c, n["checkbox_vmt"], magic, F["panel_additional"], bounds, name+"_hint")
        c.emit(b"\xba"); c.u32(texts[name+"_caption"]); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["set_text"])
        c.emit(b"\xc7\x86"); c.u32(V["on_click"]); c.u32(at[name+"_click"]); c.emit(b"\x89\x9e"); c.u32(V["on_click"]+4)
        c.emit(b"\x8b\xc6\x5e\x5b\xc3")
        code["create_"+name] = c.finish()

        c = Code(at[name+"_click"])   # OnClick(EAX form, EDX box): set or clear the bit on the design and its working copy
        c.emit(b"\x60\x8b\xd8\x8b\xfa\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "resync")
        c.emit(b"\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "resync")
        c.emit(b"\x33\xed\x8b\xc7"); call_slot(c, V["get_checked"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "apply")
        c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(research); c.branch(b"\xe8", n["has_research"])
        c.emit(b"\x84\xc0\xb8"); c.u32(texts[name+"_research"]); c.branch(b"\x0f\x84", "refuse")
        if hulls:   # the design's ship type byte
            c.emit(b"\x0f\xb6\x86"); c.u32(0x9D3)
            for kind in hulls:
                c.emit(b"\x3c"+bytes([kind])); c.branch(b"\x0f\x84", "tick")
            c.emit(b"\xb8"); c.u32(texts[name+"_hull"]); c.branch(b"\xe9", "refuse")
        c.mark("tick"); c.emit(b"\xbd"); c.u32(bit)
        c.mark("apply"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "resync")
        c.emit(b"\x8b\x10\x81\xe2"); c.u32(0xFFFFFFFF ^ bit); c.emit(b"\x0b\xd5\x89\x10")   # keep other data bits
        c.emit(b"\x8b\x83"); c.u32(F["ship2"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "stored")
        c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "stored")
        c.emit(b"\x8b\x10\x81\xe2"); c.u32(0xFFFFFFFF ^ bit); c.emit(b"\x0b\xd5\x89\x10")
        c.mark("stored"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["recompute"])
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["update"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["refresh"])
        c.emit(b"\x61\xc3")
        c.mark("refuse"); c.emit(b"\x83\xca\xff\x83\xc9\xff"); c.branch(b"\xe8", n["message"])
        c.mark("resync"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at[name+"_sync"]); c.emit(b"\x61\xc3")
        code[name+"_click"] = c.finish()

    option("hyper", HYPER_BIT, MAGIC_HYPER, HYPER_BOUNDS, tree.HYPERSONIC)
    option("super", SUPER_BIT, MAGIC_SUPER, SUPER_BOUNDS, tree.SUPER_HEAVY, SUPER_TYPES)
    option("sec_rail", SECONDARY_RAIL_BIT, MAGIC_SEC_RAIL, SEC_RAIL_BOUNDS, tree.RAILGUN_SECONDARIES)
    option("ter_rail", TERTIARY_RAIL_BIT, MAGIC_TER_RAIL, TER_RAIL_BOUNDS, tree.RAILGUN_SECONDARIES)

    # Launch wrappers at a ship's FireSSM calls: note that ship's hypersonic and super heavy flags.
    assert HYPER_SLOTS & (HYPER_SLOTS-1) == 0
    for name, ship in (("launch_ebx", b"\xc3"), ("launch_frame", b"\x45\xe8")):   # ship: EBX or [ebp-18h]
        c = Code(at[name])
        c.emit(b"\x50\x51\x52\x8b"+ship); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "store")
        c.emit(b"\x8b\x00\x25"); c.u32(HYPER_BIT | SUPER_BIT)
        c.mark("store")
        if asbm: c.emit(b"\x8b"+bytes([ship[0] | 8])+ship[1:]); c.branch(b"\xe8", asbm)   # ECX the launcher: a land battery?
        c.emit(b"\xa3"); c.u32(at["hyper_pending"]); c.emit(b"\x5a\x59\x58"); c.branch(b"\xe9", n["fire_ssm"])
        code[name] = c.finish()
    # FireSSM, EBX new missile, EDI its range (yards), [ebp+0Ch] its type: replay the speed store, forget the
    # address, then remember the launch flags (8-byte entries). Super heavy is heavy SSMs only: twice the range.
    c = Code(at["hyper_record"])
    c.emit(b"\x8b\x45\x14\x89\x43\x14\xb9"); c.u32(HYPER_SLOTS)
    c.mark("forget"); c.emit(b"\x39\x1c\xcd"); c.u32(at["missile_table"]-8); c.branch(b"\x0f\x85", "kept")
    c.emit(b"\xc7\x04\xcd"); c.u32(at["missile_table"]-8); c.u32(0)            # a freed missile's address came back
    c.mark("kept"); c.emit(b"\x49"); c.branch(b"\x0f\x85", "forget")
    c.emit(b"\x33\xc9\x87\x0d"); c.u32(at["hyper_pending"])
    c.emit(b"\xf7\xc1"); c.u32(SUPER_BIT); c.branch(b"\x0f\x84", "flags")
    c.emit(b"\x83\x7d\x0c"+bytes([HEAVY_SSM_MISSILE])); c.branch(b"\x0f\x84", "super")
    c.emit(b"\x81\xe1"); c.u32(0xFFFFFFFF ^ SUPER_BIT); c.branch(b"\xe9", "flags")
    c.mark("super"); c.emit(b"\x03\xff")
    c.mark("flags"); c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "back")
    c.emit(b"\xa1"); c.u32(at["hyper_cursor"]); c.emit(b"\x89\x1c\xc5"); c.u32(at["missile_table"])
    c.emit(b"\x89\x0c\xc5"); c.u32(at["missile_table"]+4)
    c.emit(b"\x40\x83\xe0"+bytes([HYPER_SLOTS-1])+b"\xa3"); c.u32(at["hyper_cursor"])
    c.mark("back"); c.branch(b"\xe9", n["record_back"])
    code["hyper_record"] = c.finish()
    # The air-launched missile routine (only AirdropASM calls it), EBX the new missile, [EBP-20h] the caller's EBX (the air
    # formation), [EBP-8] the nation: replay the speed store, forget the address, then remember a hypersonic launch when
    # the formation's aircraft model is from tree.HYPERSONIC_AIRCRAFT_YEAR and the nation has tree.HYPERSONIC.
    c = Code(at["air_record"]); c.emit(bytes.fromhex(info["air_record_original"])+b"\x60\xb9"); c.u32(HYPER_SLOTS)
    c.mark("forget"); c.emit(b"\x39\x1c\xcd"); c.u32(at["missile_table"]-8); c.branch(b"\x0f\x85", "kept")
    c.emit(b"\xc7\x04\xcd"); c.u32(at["missile_table"]-8); c.u32(0)
    c.mark("kept"); c.emit(b"\x49"); c.branch(b"\x0f\x85", "forget")
    c.emit(b"\x8b\x75\xe0\x8b\x46\x10\x85\xc0"); c.branch(b"\x0f\x84", "done")           # the aircraft model
    c.emit(b"\x81\x78\x0c"); c.u32(tree.HYPERSONIC_AIRCRAFT_YEAR); c.branch(b"\x0f\x8c", "done")
    combat.researched(c, n, b"\x8b\x55\xf8", tree.HYPERSONIC, "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xa1"); c.u32(at["hyper_cursor"]); c.emit(b"\x89\x1c\xc5"); c.u32(at["missile_table"])
    c.emit(b"\xc7\x04\xc5"); c.u32(at["missile_table"]+4); c.u32(HYPER_BIT)
    c.emit(b"\x40\x83\xe0"+bytes([HYPER_SLOTS-1])+b"\xa3"); c.u32(at["hyper_cursor"])
    c.mark("done"); c.emit(b"\x61"); c.branch(b"\xe9", n["air_back"])
    code["air_record"] = c.finish()
    # is_hyper / is_super(EBX missile) -> ZF clear when its launch had that flag; keep every register.
    for name, bit in (("is_hyper", HYPER_BIT), ("is_super", SUPER_BIT)):
        c = Code(at[name]); c.emit(b"\x51\xb9"); c.u32(bit); c.branch(b"\xe9", at["missile_flag"])
        code[name] = c.finish()
    c = Code(at["missile_flag"])   # ECX flag, caller's ECX on the stack
    c.emit(b"\x52\x85\xdb"); c.branch(b"\x0f\x84", "none"); c.emit(b"\xba"); c.u32(HYPER_SLOTS)
    c.mark("next"); c.emit(b"\x39\x1c\xd5"); c.u32(at["missile_table"]-8); c.branch(b"\x0f\x85", "skip")
    c.emit(b"\x85\x0c\xd5"); c.u32(at["missile_table"]-4); c.branch(b"\xe9", "done")
    c.mark("skip"); c.emit(b"\x4a"); c.branch(b"\x0f\x85", "next")
    c.mark("none"); c.emit(b"\x33\xd2")                                     # ZF set: not flagged
    c.mark("done"); c.emit(b"\x5a\x59\xc3")
    code["missile_flag"] = c.finish()
    # ResolveMissileHit, EBX missile: a super heavy missile reaches HandleHit as a SUPER_CALIBRE-inch hit.
    c = Code(at["super_hit"])
    if nuclear_missile:   # nuclear_subs: an SSBN's nuclear missile hits as a nuclear shell does
        c.branch(b"\xe8", nuclear_missile); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "ordinary")
        c.emit(b"\xb8"); c.u32(tree.NUCLEAR_SHELLS[2]); c.branch(b"\xe9", "plain")
        c.mark("ordinary")
    c.emit(b"\x8b\x43\x28"); c.branch(b"\xe8", at["is_super"]); c.branch(b"\x0f\x84", "plain")
    c.emit(b"\xb8"); c.u32(SUPER_CALIBRE)
    c.mark("plain"); c.emit(b"\x50\x68\x88\x13\x00\x00"); c.branch(b"\xe9", n["hit_back"])
    code["super_hit"] = c.finish()
    # Missile range(EAX nation, EDX mount type) at a ship's firing and AI decisions: a super heavy ship's heavy
    # SSMs reach twice as far.
    for name, ship in (("range_ebx", b"\x8b\xc3"), ("range_edi", b"\x8b\xc7"), ("range_frame8", b"\x8b\x45\xf8"),
                       ("range_frameC", b"\x8b\x45\xf4")):
        c = Code(at[name])
        c.emit(b"\x52"); c.branch(b"\xe8", n["range"]); c.emit(b"\x5a\x80\xfa"+bytes([HEAVY_SSM_MOUNT])); c.branch(b"\x0f\x85", "out")
        c.emit(b"\x50"+ship); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "plain")
        c.emit(b"\xf7\x00"); c.u32(SUPER_BIT); c.branch(b"\x0f\x84", "plain"); c.emit(b"\x58\x03\xc0\xc3")
        c.mark("plain"); c.emit(b"\x58")
        c.mark("out"); c.emit(b"\xc3")
        code[name] = c.finish()

    # stands(EBX missile, ESI defending ship) -> AL 1 when a layer's kill stands; clobbers EAX/ECX/EDX. A hypersonic
    # missile survives (100-HYPER_KEEP)% of kills (SAMs of a nation with HYPERSONIC_SAM: 100-its percent); then an SSM
    # of a nation with STEALTH_SSM (its nation at missile +3Eh) survives (100-its percent)% of the kills left.
    for name, sam in (("sam_stands", True), ("gun_stands", False)):
        c = Code(at[name]); c.branch(b"\xe8", at["is_hyper"]); c.branch(b"\x0f\x84", "stealth")
        if sam:
            combat.researched(c, n, b"\x8b\x56\x14", tree.HYPERSONIC_SAM[0], "interceptors")
            c.emit(b"\x84\xc0\xb9"); c.u32(HYPER_KEEP); c.branch(b"\x0f\x84", "roll"); c.emit(b"\xb9"); c.u32(tree.HYPERSONIC_SAM[1])
        else: c.emit(b"\xb9"); c.u32(HYPER_KEEP)
        c.mark("roll"); c.emit(b"\x51\xb8\x64\x00\x00\x00"); c.branch(b"\xe8", n["random"]); c.emit(b"\x59\x3b\xc1")
        c.branch(b"\x0f\x8d", "survives")
        c.mark("stealth"); c.emit(b"\x8b\x53\x3e")                       # the missile's side, then its nation
        if side_nation: c.branch(b"\xe8", side_nation)
        combat.researched(c, n, b"", tree.STEALTH_SSM[0], "asked")
        c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "stands")
        c.emit(b"\xb8\x64\x00\x00\x00"); c.branch(b"\xe8", n["random"]); c.emit(b"\x83\xf8"+bytes([tree.STEALTH_SSM[1]]))
        c.branch(b"\x0f\x8d", "survives")
        c.mark("stands"); c.emit(b"\xb0\x01\xc3")
        c.mark("survives"); c.emit(b"\x33\xc0\xc3")
        code[name] = c.finish()
    for name in ("sam1", "sam2", "layer3"):   # after an interception layer: AL hit
        c = Code(at[name]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", n[name+"_fail"])
        c.branch(b"\xe8", at["sam_stands"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", n[name+"_fail"])
        c.branch(b"\xe9", n[name+"_ok"])
        code[name] = c.finish()
    for name, layer in (("ciws_hyper", "ciws"), ("maa_hyper", "maa")):   # at a gun kill, before its message
        c = Code(at[name]); c.branch(b"\xe8", at["gun_stands"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", n[layer+"_fail"])
        c.emit(bytes.fromhex(info[name+"_original"])); c.branch(b"\xe9", n[layer+"_back"])
        code[name] = c.finish()
    c = Code(at["gun_data"])   # secondary/tertiary gun data: the railgun bonus is main-battery only
    c.emit(b"\x0f\xb6\x90"); c.u32(0x9A6); c.emit(b"\x80\xfa\x01\x76\x05\xba\x01\x00\x00\x00\xc3")
    code["gun_data"] = c.finish()

    # GetMaxRange(EAX ship, EDX battery): main-battery railguns reach twice as far.
    c = Code(at["range_entry"])
    c.emit(b"\x89\x15"); c.u32(at["battery"]); c.emit(b"\x8b\xc2\x48"); c.branch(b"\x0f\x84", n["range_one"])
    c.branch(b"\xe9", n["range_two"])
    code["range_entry"] = c.finish()
    def rail_battery(c, battery_operand, label):   # EAX ship, battery 2 or 3: ZF clear when that battery is railguns
        c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", label)
        for bit, _, _, number in RAIL_BATTERIES:
            c.emit(battery_operand+bytes([number])); c.branch(b"\x0f\x85", f"{label}{number}")
            c.emit(b"\xf7\x00"); c.u32(bit); c.branch(b"\xe9", label)
            c.mark(f"{label}{number}")
        c.emit(b"\x33\xc0")   # another battery: ZF set
        c.mark(label)

    c = Code(at["range_exit"])   # [ebp-8] range, [ebp-4] ship, at["battery"] its battery
    c.emit(b"\x8b\x45\xf8\x83\x3d"); c.u32(at["battery"]); c.emit(b"\x01"); c.branch(b"\x0f\x85", "other")
    c.emit(b"\x8b\x4d\xfc\x80\xb9"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "out")
    c.emit(b"\x03\xc0"); c.branch(b"\xe9", "out")
    c.mark("other"); c.emit(b"\x8b\x45\xfc")
    rail_battery(c, b"\x83\x3d"+struct.pack("<I", at["battery"]), "known")
    c.emit(b"\x8b\x45\xf8"); c.branch(b"\x0f\x84", "out"); c.emit(b"\x03\xc0")
    c.mark("out"); c.emit(b"\x5f\x5e"); c.branch(b"\xe9", n["range_out"])
    code["range_exit"] = c.finish()
    # FireGuns: the firer's railgun byte reaches HandleHit only for main-battery shots, and railgun secondaries
    # and tertiaries pass the railgun value for their own shots.
    c = Code(at["fire_ie"])
    c.emit(b"\x8b\x45\xdc\x0f\xb6\x80"); c.u32(0x9A6); c.emit(b"\x83\x7d\x18\x01"); c.branch(b"\x0f\x84", "back")
    c.emit(b"\x3c"+bytes([RAILGUN])); c.branch(b"\x0f\x85", "kept"); c.emit(b"\xb0\x01")
    c.mark("kept"); c.emit(b"\x50\x8b\x45\xdc"); rail_battery(c, b"\x83\x7d\x18", "known"); c.emit(b"\x58")
    c.branch(b"\x0f\x84", "back"); c.emit(b"\xb8"); c.u32(RAILGUN)
    c.mark("back"); c.branch(b"\xe9", n["fire_back"])
    code["fire_ie"] = c.finish()
    # rail_mw(EAX design) -> EAX MW of its railgun secondaries and tertiaries (before pulsed-power research);
    # every other register is kept.
    c = Code(at["rail_mw"])
    c.emit(b"\x53\x51\x52\x56\x57\x8b\xd8\x33\xff"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x30")
    for bit, calibre, count, number in RAIL_BATTERIES:
        c.emit(b"\xf7\xc6"); c.u32(bit); c.branch(b"\x0f\x84", f"skip{number}")
        c.emit(b"\x8b\x43"+bytes([calibre])+b"\x0f\xaf\xc0\x0f\xaf\x83"); c.u32(count)
        c.emit(b"\x6b\xc0"+bytes([MW_PER_GUN_5IN])+b"\x83\xc0\x0c\x33\xd2\xb9\x19\x00\x00\x00\xf7\xf1\x03\xf8")
        c.mark(f"skip{number}")
    c.mark("done"); c.emit(b"\x8b\xc7\x5f\x5e\x5a\x59\x5b\xc3")
    code["rail_mw"] = c.finish()
    # Penetration(EAX calibre, EDX range yards, ECX, five stack args with [esp+0Ch] the elevation byte; ret 14h):
    # a railgun shell penetrates like a gun 4 inches larger at half the range: hypervelocity rounds keep their
    # speed. The native tables stop at 20 inches; beyond that the 20-inch result is scaled by calibre/20 (depth
    # grows about linearly with calibre at one velocity, as the 16-20 inch rows do).
    c = Code(at["penetration"])
    c.emit(b"\x80\x7c\x24\x0c"+bytes([RAILGUN])); c.branch(b"\x0f\x85", "native"); c.emit(b"\x83\xc0\x04\xd1\xea")
    c.emit(b"\x83\xf8\x14"); c.branch(b"\x0f\x8e", "native")
    c.emit(b"\x50"+b"\xff\x74\x24\x18"*5+b"\xb8\x14\x00\x00\x00"); c.branch(b"\xe8", "native")   # 20 inches, same args
    c.emit(b"\x59\x0f\xaf\xc1\xb9\x14\x00\x00\x00\x99\xf7\xf9\xc2\x14\x00")                  # x calibre / 20
    c.mark("native"); c.emit(bytes.fromhex("558bec83c4ec")); c.branch(b"\xe9", n["pen_back"])
    code["penetration"] = c.finish()
    # HandleHit, target in [ebp-8]: inert railgun rounds neither explode nor flash.
    c = Code(at["magazine"])
    c.emit(b"\x8b\x45\xf8\x80\xb8"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x84", n["no_magazine"])
    c.emit(b"\x83\x78\x6d\x05"); c.branch(b"\x0f\x8f", n["magazine_calibre"]); c.branch(b"\xe9", n["magazine_small"])
    code["magazine"] = c.finish()
    # gen_sync(EAX form): find or create the Generators box and label, show the design's MW silently.
    c = Code(at["gen_sync"])
    c.emit(b"\x53\x56\x57\x8b\xd8\x8b\xc3\xba"); c.u32(n["spin_vmt"]); c.emit(b"\xb9"); c.u32(MAGIC_GEN); c.branch(b"\xe8", at["find"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_spin"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["create_gen"])
    c.mark("have_spin"); c.emit(b"\x8b\xf8\x8b\xc3\xba"); c.u32(n["label_vmt"]); c.emit(b"\xb9"); c.u32(MAGIC_GEN_LABEL)
    c.branch(b"\xe8", at["find"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_label")
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["create_gen_label"])
    c.mark("have_label"); c.emit(b"\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no_ext")
    c.emit(b"\x0f\xb6\x40"+bytes([GEN_SHIFT//8])+b"\x6b\xc0"+bytes([GEN_STEP_MW])); c.branch(b"\xe9", "have_mw")
    c.mark("no_ext"); c.emit(b"\x33\xc0")
    c.mark("have_mw"); c.emit(b"\x50\x8b\xc7"); c.branch(b"\xe8", n["spin_get"]); c.emit(b"\x3b\x04\x24"); c.branch(b"\x0f\x84", "value_ok")
    c.emit(b"\xff\xb7"); c.u32(V["on_change"]); c.emit(b"\xc7\x87"); c.u32(V["on_change"]); c.u32(0)
    c.emit(b"\x8b\xc7\x8b\x54\x24\x04"); c.branch(b"\xe8", n["spin_set"]); c.emit(b"\x8f\x87"); c.u32(V["on_change"])
    c.mark("value_ok"); c.emit(b"\x33\xd2\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "set_enabled")
    c.emit(b"\xb2\x01\x83\x3c\x24\x00"); c.branch(b"\x0f\x85", "set_enabled")
    c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.INTEGRATED_POWER[0]); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x8b\xd0")
    c.mark("set_enabled"); c.emit(b"\x8b\xc7"); call_slot(c, V["set_enabled"]); c.emit(b"\x58")
    c.mark("done"); c.emit(b"\x5f\x5e\x5b\xc3")
    code["gen_sync"] = c.finish()
    c = Code(at["create_gen"])   # EAX form -> EAX Generators box (0..2550 MW in 10 MW steps, OnChange gen_change)
    create(c, n["spin_vmt"], MAGIC_GEN, 0, GEN_SPIN_BOUNDS, "gen_hint")
    c.emit(b"\xc7\x86"); c.u32(V["spin_min"]); c.u32(0); c.emit(b"\xc7\x86"); c.u32(V["spin_max"]); c.u32(GEN_MAX_UNITS*GEN_STEP_MW)
    c.emit(b"\xc7\x86"); c.u32(V["spin_increment"]); c.u32(GEN_STEP_MW)
    c.emit(b"\xc7\x86"); c.u32(V["on_change"]); c.u32(at["gen_change"]); c.emit(b"\x89\x9e"); c.u32(V["on_change"]+4)
    c.emit(b"\x8b\xc6\x5e\x5b\xc3")
    code["create_gen"] = c.finish()
    c = Code(at["create_gen_label"])
    create(c, n["label_vmt"], MAGIC_GEN_LABEL, 0, GEN_LABEL_BOUNDS, "gen_hint")
    c.emit(b"\xba"); c.u32(texts["gen_caption"]); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["set_text"])
    c.emit(b"\x8b\xc6\x5e\x5b\xc3")
    code["create_gen_label"] = c.finish()
    # OnChange(EAX form, EDX Generators box): MW / step, 0..GEN_MAX_UNITS, research needed for any.
    c = Code(at["gen_change"])
    c.emit(b"\x60\x8b\xd8\x8b\xfa\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x8b\xc7"); c.branch(b"\xe8", n["spin_get"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x8d", "positive"); c.emit(b"\x33\xc0")
    c.mark("positive"); c.emit(b"\x33\xd2\xb9"); c.u32(GEN_STEP_MW); c.emit(b"\xf7\xf1\x8b\xe8\x81\xfd"); c.u32(GEN_MAX_UNITS)
    c.branch(b"\x0f\x86", "in_range"); c.emit(b"\xbd"); c.u32(GEN_MAX_UNITS)
    c.mark("in_range"); c.emit(b"\x85\xed"); c.branch(b"\x0f\x84", "store")
    c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.INTEGRATED_POWER[0]); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", "store")
    c.emit(b"\xb8"); c.u32(texts["gen_research"]); c.emit(b"\x83\xca\xff\x83\xc9\xff"); c.branch(b"\xe8", n["message"])
    c.branch(b"\xe9", "resync")
    c.mark("store"); c.emit(b"\xc1\xe5"+bytes([GEN_SHIFT])); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext)
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x8b\x08\x81\xe1\xff\xff\x00\xff\x0b\xcd\x89\x08")                # keep other data bits
    c.emit(b"\x8b\x83"); c.u32(F["ship2"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "stored")
    c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "stored")
    c.emit(b"\x8b\x08\x81\xe1\xff\xff\x00\xff\x0b\xcd\x89\x08")
    c.mark("stored"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["recompute"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["update"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["refresh"])
    c.emit(b"\x61\xc3")
    c.mark("resync"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["gen_sync"]); c.emit(b"\x61\xc3")
    code["gen_change"] = c.finish()

    c = Code(at["diving"])
    c.emit(b"\x8b\x55\xf8\x80\xba"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x84", n["no_diving"])
    c.emit(b"\x8b\x92\x9a\x00\x00\x00"); c.branch(b"\xe9", n["diving_back"])
    code["diving"] = c.finish()
    c = Code(at["flash"])
    c.emit(b"\x52\x8b\x55\xf8\x80\xba"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.emit(b"\x5a"); c.branch(b"\x0f\x84", n["no_flash"])
    c.emit(b"\x3b\xf0"); c.branch(b"\x0f\x8e", n["no_flash"]); c.branch(b"\xe9", n["flash"])
    code["flash"] = c.finish()
    # Heavy AA factor, DP main battery share in [ebp-20h] (ESI ship): hypervelocity railgun rounds count 1.5x;
    # three times shorter flight time outweighs about half the rate of fire.
    c = Code(at["haa"])
    c.emit(b"\x80\xbe"); c.u32(0x9A6); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "native")
    c.emit(b"\x8b\x45\xe0\x8d\x04\x40\xd1\xf8\x89\x45\xe0")
    c.mark("native"); c.emit(b"\x8b\x86\x9a\x00\x00\x00"); c.branch(b"\xe9", n["haa_back"])
    code["haa"] = c.finish()

    limits = dict(refresh=0x40, sync=0x280, find=0x40, create_box=0xC0, create_label=0x80, power=0x180, click=0x140,
                  legality=0x200, turret_weight=0xC0, turret_cost=0x40, ammo=0x180, gun_data=0x20, range_entry=0x20,
                  laser_sync=0x100, create_spin=0xC0, create_laser_label=0x80, laser_change=0x100, laser_layer=0x100,
                  gen_sync=0x100, create_gen=0xC0, create_gen_label=0x80, gen_change=0x140, scale=0x80,
                  hyper_sync=0x100, create_hyper=0xC0, hyper_click=0x100, sam1=0x40, sam2=0x40, layer3=0x40,
                  ciws_hyper=0x40, maa_hyper=0x40, sam_stands=0xC0, gun_stands=0xC0, drive_kind=0x40, air_record=0xB0, is_hyper=0x40, hyper_record=0x100, launch_ebx=0x40, launch_frame=0x40,
                  super_sync=0x100, create_super=0xC0, super_click=0x140, range_ebx=0x40, range_edi=0x40,
                  range_frame8=0x40, range_frameC=0x40, super_hit=0x40, is_super=0x20, missile_flag=0xA0,
                  range_exit=0x80, fire_ie=0x80, penetration=0x80, magazine=0x40, diving=0x40, flash=0x40, haa=0x40,
                  sec_rail_sync=0x100, create_sec_rail=0xC0, sec_rail_click=0x140, ter_rail_sync=0x100,
                  create_ter_rail=0xC0, ter_rail_click=0x140, rail_mw=0x80, rail_layer=0x200)
    for name, body in code.items():
        if len(body) > limits[name]: raise ValueError("Railgun code exceeds its reservation: "+name)
        blocks.append(dict(name="Railgun: "+name, address=at[name], bytes=body.hex()))
    if cell_cost: blocks.append(dict(name="Railgun: cell_cost", address=cell_cost_at, bytes=cell_cost.hex()))
    blocks.append(dict(name="Railgun: battery", address=at["battery"], bytes="00000000"))
    blocks.append(dict(name="Railgun: hyper_tons", address=at["hyper_tons"], bytes=bytes(HYPER_CELL_TONS).hex()))
    for name, size in (("hyper_pending", 4), ("hyper_cursor", 4), ("missile_table", 8*HYPER_SLOTS)):   # no launches yet
        blocks.append(dict(name="Railgun: "+name, address=at[name], bytes="00"*size))
    calls = dict(sec_data=at["gun_data"], ter_data=at["gun_data"], launch_auto=at["launch_ebx"], launch_auto2=at["launch_ebx"],
                 launch_salvo=at["launch_ebx"], launch_other=at["launch_frame"], range_auto=at["range_ebx"],
                 range_auto2=at["range_ebx"], range_salvo=at["range_ebx"], range_longest=at["range_edi"],
                 range_longest2=at["range_edi"], range_ai=at["range_frame8"], range_screen=at["range_frameC"],
                 range_screen2=at["range_frameC"])
    jumps = dict(at, laser_layer=point_defence["layer"]) if point_defence else at   # its layers come first
    plans = []
    for site in info["sites"]:
        old, name = bytes.fromhex(site["original"]), site["name"]
        if name in calls:
            new = b"\xe8"+struct.pack("<i", calls[name]-site["address"]-5)+b"\x90"*(len(old)-5)
        else:
            new = b"\xe9"+struct.pack("<i", jumps[name]-site["address"]-5)+b"\x90"*(len(old)-5)
        plans.append(patch("Railgun: "+name, site["address"], old, new))
    return blocks, plans

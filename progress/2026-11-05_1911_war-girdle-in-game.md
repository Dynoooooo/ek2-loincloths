# Step 3a done: war girdle and hip trophies show in game (men and women)

**Done** (commit: the one that adds this file)
- Launch 1 of 3 for this feature: Aldrydd and a new Reach woman in the barbershop with the war look: cord-belt loincloth, wide smoked-hide girdle (ochre zig-zag, painted bone beads, stitching) above the cord belt, five teeth/claws on sinew cords at each hip; women also the chest band. Screenshots: `source/preview/ingame_war_m.jpg`, `ingame_war_f.jpg`.
- The band clipping fix (previous note) was seen in game too: no band showing through the arms.
- Piece `ek2lc_{m,f}_reach_war_01`, built by `source/build_reach_hide.py` (same run as the loincloth), own texture set `ek2lc_reach_war_01_*` (512 px) in `gfx/models/portraits/ek2lc/reach_hide_01/`. No point inside the body on any shape or over the callous_1 idle.
- New gene `gene_ek2lc_war` (`ek2lc_no_war`, `ek2lc_reach_war`); every modifier now sets it.
- New `common/scripted_triggers/ek2lc_triggers.txt`: `ek2lc_war_role_trigger` = adult, capable, free, and (commanding an army, in an army, or a knight), while they or their liege are at war.
- Modifiers `ek2lc_reach_war_m/f` (Reach, war role) replace EK2's armour with this look; the commoner modifiers now exclude war roles.
- error.log: nothing about our files (only the test-hook flag).

**In progress**
- Nothing half-made.

**Next step**
- The user's verdict on the war look. Then step 3b, the armoured loincloth (hide-and-bone strip skirt, pteruges-like), on the same base, after their OK.

**Decisions the user made**
- War look for "Knights, commanders and anyone in an army, while their realm is at war" (adult Reach).

**Problems and workarounds**
- Not checked in game: the real war trigger (the test used the flag hook). EK2 headgear (helmets) is left as EK2 picks it.
- The console cuts lines at 255 characters. Woman for testing (239 chars): `effect create_character = { gender_female_chance = 100 age = 25 employer = root save_scope_as = w } scope:w = { get_title = root.capital_county add_character_flag = ek2lc_test_wear } set_player_character = scope:w`, then `effect open_view_data = barbershop`.
- io_pdx_mesh export fails on n-gons (no tangents): triangulate caps.

**How to test**
- `ck3_test.sh start/wait/stop`; temporary hook `modifier = { add = 100 is_female = no/yes has_character_flag = ek2lc_test_wear }` in the war modifiers' weight (never commit); `effect add_character_flag = ek2lc_test_wear`, `effect open_view_data = barbershop`.

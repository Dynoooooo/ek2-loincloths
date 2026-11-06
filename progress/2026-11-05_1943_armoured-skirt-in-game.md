# Step 3b done: armoured hide-and-bone strip skirt shows in game (men and women)

**Done** (commit: the one that adds this file; the flap fix before it is 59dabfc)
- Flap bump fixed (59dabfc): on men the pouch strip slid up to 2.3 cm out beside the front flap's edge in the idles. Its sides now blend into the flap's apron weights, and it's 0.5 cm narrower over the fig leaf. Now 0 cm in callous_1 and callous_2; fig leaf just as hidden. Women rebuilt too (same script; they were fine).
- Launch 1 of 3 for this feature: Aldrydd and a new Reach woman in the barbershop with the armoured look. Crops: `source/preview/ingame_armour_m.jpg`, `ingame_armour_f.jpg`. Flap edges clean.
- Piece `ek2lc_{m,f}_reach_armour_01` (built by `source/build_reach_hide.py`): the war girdle (same geometry and texture), plus 5 flat hide strips per hip (62-118 degrees from the front), each with 3 bone lames, lacing holes and studs (texture only). The strips are sewn onto the girdle's lower half and hang straight over the cord belt to mid-thigh, as far out as the hip needs. No trophies. Texture set `ek2lc_reach_armour_01` = the war set with the strip painted into its lower half.
- Checks: no point inside the body on any shape; over the callous_1/_2 idles the strips stay at least 0.3 cm off the skin and never go inside the loincloth.
- Gene `gene_ek2lc_war` has a new template `ek2lc_reach_armour` (index 2). New trigger `ek2lc_armour_role_trigger` = war role and (knight or prowess >= 12). Modifiers `ek2lc_reach_armour_m/f`; the war modifiers now need `ek2lc_armour_role_trigger = no`.
- error.log: nothing about our files. ck3-tiger: no reports on our new items (it doesn't load EK2, so EK2's triggers show as unknown).

**In progress**
- Nothing half-made.

**Next step**
- The user's verdict on the armoured look. Then step 4, the royal ladder for one culture: first show the user the tier table from the brief and ask which culture (Argonian or Pellitine Khajiit were suggested), then build.

**Decisions the user made**
- War and armour looks: "Both look pretty good. Except for the man" (the flap bump, now fixed). Then: "proceed to step 3b".
- Armour goes to "the best fighters": knights or prowess 12+ (my reading of the brief; the user can change it).

**Problems and workarounds**
- Rays from outside the body hit the hanging arms (rest pose): the strips' obstacles leave out arm triangles, and leg centres are found with rays cast from inside.
- The body mesh is sparse round the thighs: find leg centres with rays, not by averaging vertices.
- A fat belly overhangs the girdle: each strip also clears 2.6 cm above its top.
- The barbershop can open with a "No Social Profile" popup over the hips; Escape closes it. Escape with no popup closes the barbershop.

**How to test**
- `ck3_test.sh start/wait/stop`; temporary hook `modifier = { add = 100 is_female = no/yes has_character_flag = ek2lc_test_wear }` in the armour modifiers' weight (never commit); console as in the 1911 note; `ck3ctl` built from `source/tools/ck3ctl.swift` into a scratch folder.

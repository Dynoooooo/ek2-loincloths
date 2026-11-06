# Step 4a built: Reach royal ladder, four tiers (not yet seen in game)

**Done** (commit: the one that adds this file)
- User's choices: Reach first ("Reach (Recommended)"), and spouses get the same tier ("Yes, same tier").
- Tiers, by the higher of a character's own and their primary spouse's top title tier:
  - county and below: loincloth (and chest band) in fine dyed hide (set `ek2lc_reach_fine_01`); nothing added
  - duke: fine loincloth + `ek2lc_{m,f}_reach_duke_01`: royal girdle (war girdle's shape), short front apron with bone chevrons, 3 bead strings per hip
  - king: royal smoked-black hide with patterned squares (set `ek2lc_reach_royal_01`) + `ek2lc_{m,f}_reach_king_01`: girdle, long front apron (to the knee) and back apron with woven-look bands and fringe, 3 hagraven feathers per hip
  - emperor: royal hide + `ek2lc_{m,f}_reach_emperor_01` = the king mesh with Dwemer bronze and garnet (texture only)
- Fine/royal loincloths and bands, and the emperor piece, are .asset files reusing existing meshes (`write_asset` in the build script).
- Checks: no point inside the body on any shape; over the callous_1/_2 idles the king and duke pieces stay off the skin and never go inside the loincloth (woman's long apron touches the flap's fringe edge by 1 mm).
- Renders: `source/preview/preview_royal_{m,f}.png` (duke, king, emperor front, emperor back).
- Game files: gene templates (loincloth fine 2 / royal 3; top band_fine 2 / band_royal 3; war slot duke 3 / king 4 / emperor 5), accessories, triggers `ek2lc_royal_trigger` and `ek2lc_royal_tier_trigger = { LOW HIGH }`, 8 modifiers `ek2lc_reach_royal_<tier>_<m|f>`. Weight 2 against 1 for "no loincloth" (brief: tribal rulers "sometimes"). War roles keep the war/armour looks. Commoner modifiers now exclude royals.
- Fixed on the way: the leg-centre finder (near the crotch the middle can be outside the body); feathers placed with leg rays; aprons weighted like the flaps under them.

**In progress**
- Step 4b: the emperor's fur-and-feather mantle (collar + back cape). Not started. Neck note: `bn_sp_cervical` sits in front of the neck's centre; rays from it miss above the shoulders.

**Next step**
- One launch: Aldrydd (a duke) with test flags per tier, then a Reach woman; crops of all four tiers. Then 4b after the user's verdict.

**Problems and workarounds**
- Steam rewrites `dlc_load.json` from its Workshop list and can drop our local mod: check it before launches.
- /private/tmp scratch was deleted on 2026-11-05: the idle/clearance check scripts were scratch only; rewrite small ones if needed (`ck3ctl` builds from `source/tools/ck3ctl.swift`).

**How to test**
- As in the 1943 note; temporary hooks `has_character_flag = ek2lc_test_t1..t4` in the royal modifiers (never commit).

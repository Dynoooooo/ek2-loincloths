# Step 4b seen in game: the emperor's fur-and-feather mantle (men and women)

**Done** (commit: the one that adds this file)
- New piece `ek2lc_{m,f}_reach_mantle_01` (own texture set `ek2lc_reach_mantle_01`, 1024 px):
  - thick pale snow-bear fur collar round the base of the neck, tufted outer edge (alpha);
  - cape of overlapping hagraven feathers (garnet rows, garnet-tipped hem, feather-tip hem cut out), lined with garnet-dyed hide (bronze border, black-and-bone zig-zag band near the hem). Hangs from under the collar to mid-calf.
- How it's built (`mantle_piece()` in `source/build_reach_hide.py`): the collar and the cape's top ("yoke") follow the skin, by rays from inside the chest. Below that the cape hangs free where vanilla cloaks hang: taut over the shoulder blades and buttocks (and the king's back apron), flaring a little to the hem. Weights blend from the skin into the skeleton's own cloak bones (`bn_b_cloak1-5`, `bn_lb/rb_cloak1-5`), as vanilla cloaks do.
- Its own gene `gene_ek2lc_mantle` (0 none, 1 Reach mantle). Every modifier sets it; only the two emperor modifiers give the mantle.
- Checks: no point inside the body on any body shape. Women: collar 2.1+ cm from the chest band; the band's back stays inside the cape (1 point out on the dwarf shape only).
- Launch: Aldrydd and a new Reach woman, emperor look forced by a test flag, seen in the barbershop. Crops: `source/preview/ingame_mantle_m.jpg`, `ingame_mantle_f.jpg`. Blender render: `source/preview/preview_mantle_{m,f}.png`. error.log: nothing about our files.

**In progress**
- Nothing half-made. Step 4 (the Reach royal ladder) is complete.

**Next step**
- Ask the user: their verdict on the mantle, then step 5 (other cultures: mostly new textures on the same shapes) or the barbershop entries + localisation (not done anywhere yet).

**Decisions the user made**
- "No changes needed. Continue." on the four tiers; mantle OK'd to build.

**Problems and workarounds**
- The men's neck is cut lower in front than behind: the collar starts just under the cut there.
- The CK3 console cuts long lines (~240 characters): split commands; carry a scope between lines with `set_global_variable`.
- Escape in the barbershop briefly shows "Paused" but leaves it open; console commands still work.
- Not checked: the back of the cape in game (the barbershop shows the front; needs a mouse drag to turn). Long hair and veils lie over the collar.
- error.log lists old game-rule names (`ek2lc_frequency_lore` etc.) from `player/game_rules/presets.txt`, left from the deleted first version. Harmless.

**How to test**
- `source/tools/ck3_test.sh start/wait/stop`; `ck3ctl` built from `source/tools/ck3ctl.swift` into a scratch folder.
- Temporary hooks (never commit): `modifier = { add = 1000 is_female = no/yes has_character_flag = ek2lc_test_t4 }` in the emperor modifiers' weight. Console: `effect add_character_flag = ek2lc_test_t4`, `effect open_view_data = barbershop`.
- Woman, in three console lines: `effect create_character = { age = 26 gender_female_chance = 100 culture = root.culture faith = root.faith location = root.capital_province save_scope_as = w } set_global_variable = { name = w value = scope:w }`, then `effect global_var:w = { get_title = root.capital_county add_character_flag = ek2lc_test_t4 }`, then `effect set_player_character = global_var:w`.

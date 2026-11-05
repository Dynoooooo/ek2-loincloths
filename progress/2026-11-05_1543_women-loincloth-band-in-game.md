# Step 2 done: Reach loincloth + chest band for women; men's clipping fix confirmed in game

**Done** (commit: the one that adds this file)
- Launch 4 (the user said yes to it): men's tucked-under-belt version and the new women's set seen in the barbershop, thin and heavy, men and women. No errors for our files. Screenshots: `source/preview/ingame_men_thin_heavy.jpg`, `ingame_women_thin_heavy.jpg`.
- `source/build_reach_hide.py` (replaces build_reach_hide_m.py) builds either body: `... -- <game> <mod> male|female`. Women get 8 body shapes (fat, gaunt, muscular, old, dwarf, pregnant, breast size max/min) like vanilla women's clothes.
- Chest band: separate piece `ek2lc_f_reach_band_01` in its own gene `gene_ek2lc_top` (templates `ek2lc_no_top`, `ek2lc_reach_band`), so a culture can drop it for some women later. It bridges the cleavage (convex hull per slice), sits 1.0-1.2 cm off the skin, top kept below the armpits.
- All pieces share one texture set in `gfx/models/portraits/ek2lc/reach_hide_01/` (`ek2lc_reach_hide_01_*.dds`); the band uses the strip's plain-hide area. The old `m_reach_hide_01/` folder is gone.
- Rules: `ek2lc_reach_hide_f` = adult Reach commoner women: loincloth + band, always. Every modifier sets both genes.

**In progress**
- Nothing half-made.

**Next step**
- Ask the user what they think of the women's look. Then step 3 (war loincloth add-ons, then armoured), after their OK.

**Decisions the user made**
- "Should I start step 2?" ... "that is also a yes." 4th launch: "Yes."

**Problems and workarounds**
- Arms-crossed idle: the forearm and upper arms press into the band (up to ~2 cm inside the arms). Hidden by the arms, as with any top; not fixed.
- `change_current_weight` clamps at +-100, so -200 after +200 gives the thinnest body, not normal.
- Women in the barbershop: create a Reach woman, `get_title = root.capital_county`, then `set_player_character` (a landless one ends the game).

**How to test**
- `ck3_test.sh start/wait/stop`; temporary hooks `has_character_flag = ek2lc_test_wear` + `is_female = yes/no` in both modifiers (never commit). Console line for the woman is in this session's notes: create_character ... get_title ... set_player_character, then `effect open_view_data = barbershop`.
- Blender: `source/tools/make_check_blend.py` -> `source/reach_hide_{m,f}_check.blend` (callous idle; shape sliders on the body drive the pieces).

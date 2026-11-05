# Reach hide loincloth shows in game (adult men)

**Done** (commit: the one that adds this file)
- Seen in game on launch 2, in the barbershop: cord belt and fringed front flap; EK2's clothes, legwear and cloak are cleared ("No Clothes", "None"). Heavy body: belt and flap follow the body, no clipping seen. Screenshots: `source/preview/ingame_*.jpg`.
- Rule now: adult Reach men who are EK2 commoners (not in armour) always wear it. Group `ek2lc_loincloth`, priority 101.
- error.log: nothing about our files.

**In progress**
- Nothing half-made.

**Next step**
- Step 2, after the user's OK: women's Reach loincloth and chest band, made together on the vanilla female body (`gfx/models/portraits/female_body`), starting from a copy of `source/build_reach_hide_m.py`. Add the female accessory to template `ek2lc_reach_hide` and an `is_female = yes` modifier. Reach women always wear the chest band.

**Decisions the user made**
- "Yes. Start step 1." and "Take 2-3 screenshots."
- Men first, then women together with the chest band (proposed before step 1 was approved).

**Problems and workarounds**
- The character window shows only down to the chest. For a full-body look, temporarily add `modifier = { add = 100 has_character_flag = ek2lc_test_wear }` to the weight (never commit it), then console: `effect add_character_flag = ek2lc_test_wear`, `effect open_view_data = barbershop` (plain `open_view` opens it empty). `effect change_current_weight = 200` tests the heavy shape.
- `set_player_character` to a landless courtier ends the game (Game Over). Don't.
- CK3 can hang when quit; `ck3_test.sh stop` now force-quits before restoring.
- `presets.txt` still holds game-rule keys from the deleted old mod: harmless "Failed to read key reference: ek2lc_*" lines in error.log.
- A "No Social Profile found" pop-up shows on launch; Escape closes it.

**How to test**
- `source/tools/ck3_test.sh start`, then `wait` (~20 s); keys with `ck3ctl` (build: `swiftc -O -o <bin> source/tools/ck3ctl.swift`; 50 = console, 36 = Return, 53 = Escape); `screencapture -x -o -l <ck3ctl winid>`; then `ck3_test.sh stop`.

# Barbershop rows all have names; error-log check

**Done** (Claude Code; this commit)
- The user asked for names on the clothing "inside and outside the barbershop", then pointed at rows reading "None (Default)".
- Already worked (checked in game, launch 1): every dropdown entry, the "(Default)" row of a worn piece, and the DNA Modifiers list all use our names ("Reach Fine Hide Loincloth").
- Cause of "None": a "no X" template used the built-in `empty` piece, and the barbershop labels an empty current piece with the engine key `BARBERSHOP_ACCESSORY_NONE` ("None").
- Fix (`gen_script_files.py`, `none_acc()`): each "no X" template now uses its own piece that draws nothing (`ek2lc_no_loincloth_01`, `ek2lc_no_top_01`, `ek2lc_no_war_01`, `ek2lc_no_mantle_01`, `ek2lc_no_trophy_01`, `ek2lc_no_arena_01`, `ek2lc_no_camp_01`), named "No Loincloth", "No Mantle", etc.
- Side effect, found in launch 2: the barbershop leaves the worn choice out of the list and hides a row with only one other choice. Shoulder Guard and Camp Follower's Wrap had two choices, so they vanished.
- Fix: a third, barbershop-only choice for each, from models that already existed: "Lich's Burial Shoulder Guard" and "Lich's Burial Camp Wrap" (EXTRA kinds `lich_arena_guard`, `lich_camp_wrap`, game rule None = no game modifier). Templates added at the end (index 2), so saved characters keep their pieces.
- Launch 3 (`progress/screens/barbershop_names.jpg`): Loincloth, Girdle, "No Mantle (Default)", "No Trophy Belt (Default)", "No Shoulder Guard (Default)", "No Camp Wrap (Default)". The lich shoulder guard draws when picked. No new error.log lines from our files.
- Tried and dropped: names for the 324 game modifiers (`PORTRAIT_MODIFIER_ek2lc_loincloth_<modifier>`). The game never shows them; the barbershop and DNA list use the barbershop entries' names.

**Error-log check** (user's own game at 20:06: EK2 + this mod + Better Barbershop + Undead Expanded)
- Ours: only the 7 "Failed to read key reference: ek2lc_frequency_lore …" lines. They come from the user's saved lobby preset `player/game_rules/presets.txt`, which still lists 7 game-rule options the mod no longer has. They appear even with EK2 alone. Harmless; removing the 7 `ek2lc_*` words from that file would silence them (user's decision).
- Not ours: 14 "Failed to read key reference: : ," lines (also with EK2 alone, launch 4); "Portrait type '' has no portrait type group" (only with Undead Expanded); everything else names EK2, vanilla, Undead Expanded (`cof_ekue_*`) or Better Barbershop (`FSB_modifiers.txt`, its `.mod` supported_version) files.

**Still the vanilla name**
- The vanilla Clothes row says "No Clothes (Default)" for loincloth wearers. Changing it would mean editing vanilla's clothes group, which the brief forbids.

**Next step**
- Same as `2026-11-06_1745_undead.md` (grave wrap seen only in previews; presets.txt cleanup is the user's call).

**How to test**
- `bash source/tools/ck3_test.sh start ugc_2220326926`, `wait`, console `effect open_view_data = barbershop`, click Retry on "No Social Profile", drag the list's scrollbar to the bottom. `stop` afterwards.

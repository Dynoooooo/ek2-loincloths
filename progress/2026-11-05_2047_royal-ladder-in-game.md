# Step 4a seen in game: Reach royal ladder, all four tiers (men and women)

**Done** (commit: the one that adds this file; the build is a534a2b)
- Launch 1 for step 4: Aldrydd and a new Reach woman in the barbershop, each tier forced with a test flag. All four tiers show and differ: county (fine dyed hide), duke (royal girdle, short chevron apron, bead strings), king (royal hide, long patterned front apron, feathers), emperor (king pieces with bronze and garnet). Women wear the matching fine or royal chest band.
- Crops (brightened, the barbershop is dim): `source/preview/ingame_royal_m.jpg`, `ingame_royal_f.jpg`, tiers left to right.
- error.log: nothing about our files.
- `ck3_test.sh start` now loads exactly EK2 + this mod for the test (Steam rewrites the list from its subscriptions); `stop` restores the user's own list.
- Kios Mod Editor: the user dropped it (it is a set of HTML pages for CK3 1.19). Removed from `dlc_load.json`; its Workshop folders moved to the Trash. The user unsubscribes in Steam.

**In progress**
- Nothing half-made.

**Next step**
- The user's verdict on the four tiers. Then step 4b, the emperor's mantle (fur collar + feathered back cape), after their OK. Notes for it in the 2043 note.

**Decisions the user made**
- Reach first; spouses share the tier ("Yes, same tier").

**Problems and workarounds**
- Not checked in game: the real tier rules (the test used flags). Aldrydd is a duke, so in a normal game he should show the duke look two times in three.
- The "No Social Profile" popup shows on the first barbershop open only; Escape closes it.

**How to test**
- `ck3_test.sh start/wait/stop`; hooks `modifier = { add = 1000 is_female = no/yes has_character_flag = ek2lc_test_t1..t4 }` in the royal modifiers' weights (never commit); swap flags with `effect remove_character_flag` / `add_character_flag`, reopen the barbershop.

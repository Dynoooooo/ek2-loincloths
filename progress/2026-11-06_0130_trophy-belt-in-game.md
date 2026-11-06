# Extra: trophy belt that grows with prowess (seen in game)

**Done** (commit: the one that adds this file; Claude Code)
- New gene `gene_ek2lc_trophy`, three tiers, same pieces for every culture (bone, claw and sinew from the Reach war texture):
  - tier 1 (prowess 8-11): a tooth on a sinew cord at the front of each hip (53 degrees from the front);
  - tier 2 (prowess 12-15): plus a claw at the back of each hip (133 degrees);
  - tier 3 (prowess 16+): as tier 2, plus two bone beads on each front cord where it crosses the belt.
- Where they hang: below the belt there is room only between the front flap's edge (46 degrees) and the armoured strips (56), and between the strips (124) and the back flap (138). The hips belong to the war trophies, the strips and the royal ornaments. So the belt goes with every look. Longer trophies or more beads below the belt reached the flaps or strips on some body shapes, so tier 3 grows upwards instead.
- `build_reach_hide.py` builds the trophies last and pushes each one out from the body until it clears every other piece (loincloth, war, armour, duke, king) by `TROPHY_GAP` = 0.3 cm on every body shape (asserted). It reports `TROPHY tier N at ... gap ...` per trophy, plus a `TROPHYGAP` summary.
- `gen_script_files.py`: `EXTRA` holds culture-independent extras. The trophy accessories draw only while our loincloth tag is set, so the game group `ek2lc_trophy` needs no culture or look: anyone 14+ by prowess. Barbershop group "Trophy Belt" (interface position 13) with English names.
- In game: Aldrydd with `effect add_prowess_skill = 25` shows tier 3 beside the front flap's edges (`progress/screens/trophy_belt_tier3.jpg`). error.log: nothing new about our files.

**In progress**
- Nothing half-made.

**Next step**
- The other extras the user asked for: the arena fighter's shoulder guard and the camp follower's wrap. Then Better Barbershop support.

**Problems and workarounds**
- Prowess only; "battles won" isn't tracked.
- Tiers 1 and 2 not looked at in game (same pieces, fewer trophies).

**How to test**
- As in `2026-11-06_0100_kids-in-game.md`; raise prowess with `effect add_prowess_skill = 25`.

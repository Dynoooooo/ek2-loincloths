# Extras: arena shoulder guard and camp follower's wrap (seen in game)

**Done** (commit: the one that adds this file; Claude Code)
- `gene_ek2lc_arena`: one guard on the **left** shoulder, men and women, every body shape. Three overlapping hide lames faced with bone (Reach armour texture) and a strap round the upper arm. Each point is bound to the shoulder/upper-arm skin and copies its weights, so it follows the arm (seen in two different idle poses). Rule: `has_trait = tourney_participant` with foot-track XP > 0 (has fought on foot at a tournament), age 14+.
- `gene_ek2lc_camp`: patched undyed-wool sash where the war girdle sits (same shape), knot and two tails at the left hip, a cloth bundle on a cord at the right hip. Own texture set `ek2lc_camp_01`. Rule: new scripted trigger `ek2lc_camp_follower_trigger` = not a knight or in a war role, and either a courtier of a landless adventurer's camp or someone whose spouse is in an army.
- Camp followers of loincloth cultures also get the plain loincloth (+ band for women): new modifiers `ek2lc_<culture>_camp_m/f`. Needed because EK2 dresses an adventurer's camp as low nobility, so the commoner rule missed them.
- Tags: war-gene pieces now set `ek2lc_girdle` (hides the wrap: same place), the mantle sets `ek2lc_mantle` (hides the guard: its collar overlaps that shoulder).
- Barbershop groups "Shoulder Guard" (position 14) and "Camp Follower's Wrap" (15), English names.
- In game: Aldrydd with the tourney trait (`progress/screens/arena_guard_ingame.jpg`); a lowborn Reach woman in a new adventurer's camp shows loincloth, band, guard and wrap (`progress/screens/camp_wrap_and_guard_f_ingame.jpg`). error.log: nothing about our files.

**In progress**
- Nothing half-made.

**Next step**
- Better Barbershop support (brief section "Better Barbershop"). Ask the user first (budget). Better Barbershop is already installed: Workshop item 2220326926, in the user's normal mod list (ck3_test.sh loads only EK2 + this mod).

**Problems and workarounds**
- A courtier reports the camp's government, so `is_landless_adventurer` is true for everyone in a camp; the trigger uses `is_ruler = no` instead.
- The CK3 console cuts long commands (~200 characters): split `create_character` and `add_courtier`.
- Console `create_character` without `dynasty = none` makes a noble (EK2 gives them noble clothes).
- Arm strap touches the girls' chest band (0.04 cm, infant shape only, under the armpit). Accepted.
- Wrap sash touches the cord belt on the fat body, as the war girdle always has. Accepted.
- Build reports `XGAP` (closest point of the new pieces to every other piece, per shape) and asserts the guard never enters the body.

**How to test**
- `source/tools/ck3_test.sh start`, `wait`, Return (closes the social-profile notice), then console:
  - guard: `effect add_trait = tourney_participant`, `effect add_trait_xp = { trait = tourney_participant track = foot value = 20 }`, `effect open_view_data = barbershop`.
  - wrap: create a man saved as `global_var:adv`, `effect global_var:adv = { create_landless_adventurer_title_effect = { REASON = flag:voluntary FLAVOR_CHAR = this } }`, create a woman with `dynasty = none` saved as `global_var:c`, `effect global_var:adv = { add_courtier = global_var:c }`, `effect set_player_character = global_var:c`, barbershop.

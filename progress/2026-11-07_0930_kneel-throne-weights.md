# Kneeling, the throne and bowing: weights solved over the game's own poses; the hands answer

**Asked** (2026-11-07 morning): fix the throne-room kneel overlap "really well"; and do the hands pass through
the leggings and skirts?

**Found**
- Every piece that hangs below the hips clipped in the throne room's poses, not only kneeling: one-knee kneel
  (petitioners, `throneRoom_kneel1_1`; the messenger, `messenger1_1`), both knees (`kneel2_1`), the throne on a
  chair (`ruler2_1`, vanilla's `throne_room_ruler`) and cross-legged (`ruler3_1`), bows. Worst before: loincloth
  3.7 cm into the raised thigh kneeling (the front flap torn between two skirt bones, sticking out like a board),
  7.7 cm cross-legged (front flap buried in the crossed legs), women's loincloth 3.4 cm on a chair.
  Vanilla robes clip there too (the raised knee goes 15 cm through a vanilla robe in the one-knee kneel).
- EK2 + Khans of the Steppe (installed): Reach, orc, goblin, Bosmer and Argonian courts get the steppe court room,
  Khajiit (and Velothi etc.) the Indian one; both thrones seat ruler and spouse cross-legged
  (`throne_room_ruler_3`). So cross-legged is the main throne pose for most of our cultures (Yashnag's court).
- Many women's clips (kneels, emotions, bows, cheers, conversations) key only skirt bones 1-2 of the f/b/l/r
  chains and no cloak bones; in the game the others stay at rest, but Blender kept the previous clip's values,
  so women's kneel checks before today were wrong. `inspect_scan.py` now puts every bone at rest before a clip.
- How the game plays clips (decided from the files, 2026-11-07): every bone keeps its own length; only the
  clip's rotations are used (the pelvis's position too). io_pdx_mesh applies the clips' bone offsets literally,
  and those only fit the rig the clip was made on: literally, the women's kneel/emotion/bow/cheer clips drop the
  skirt bones 13-38 cm and shred a vanilla women's dress (looked at in Blender), two men's emotion clips put the
  toe 40 cm from the ankle, and children (shorter bones, via additive "infant proportions" clips) couldn't work.
  With bone lengths kept the vanilla dress hangs right; the vanilla men's robe then has the raised knee poking
  through when kneeling (ordinary vanilla clipping). The solver and the inspection tools use this
  (`weight_solver.game_pose`, `inspect_scan._game_pose`). Not verified in game: computer use can't send keys to
  CK3 here, so the debug window that plays any clip on a portrait (console: `animation.testwindow`) wasn't
  opened; worth a look by hand.
- Women's emotion clips now import (they don't key `ground_joint`, body_root's parent in the female skeleton:
  `weight_solver.import_anim` unparents body_root while importing).

**Done**
- `source/weight_solver.py`, run by the build (section "weights solved over the game's own poses", before the
  export): the build imports 27 of the game's clips (idles, emotions, the throne room's), 3 frames each, and
  re-solves the bone weights of everything below the hips so that over all 81 frames each point stays outside
  the body (no forearms/hands) by a margin (1.3 cm for flaps: outside the leggings too), keeps its shape (edges
  and second neighbours keep their rest lengths: hide doesn't crumple), keeps its standing look in the standing
  frames, never points up, and settles under gravity when kneeling or sitting (those frames count 3x).
  Projected gradient descent on the weights; two starts (old weights; half pelvis + half thigh), the one leaving
  the least inside the body when kneeling or sitting kept; then at most 4 bones. ~5.5 min per body in the build.
  Not mirrored: the game's poses aren't (the kneel always raises the right knee, cross-legged the left).
- Solved: loincloth (belt, strip, flaps; tucked rows tied to the belt; the strip may not leave the groin), war,
  armour, duke and king girdles with their hanging parts, camp wrap, trophy belts, the mantle's cape (also the fur
  cloak). The royal aprons below the cord belt copy the solved flap behind them, so apron and flap move as one.
- Not solved: leggings (skin weights; their points inside the body are in folds behind the knee and in the hip
  crease, hidden), children's skirt, tunic and charms (children stand in the throne room).
- Looked at in the Blender app: kneel1 (flap hangs in front of the kneeling leg, edge resting on the raised
  thigh), cross-legged (flap hangs into the lap behind the crossed shins), chair (flap lies over the lap),
  standing (an idle where the old flap swung 10 cm forward now hangs down).

**Hands** (the question): yes, in places. Men: hands stay outside skin and leggings in the idles (one point at
most); a bow brushes them, and kneeling the right hand rests on the knee and sinks ~1 cm into the leggings.
Women: the game's own women's idles push part of the hand into the hip itself (~15% of the hand inside the skin,
fingertips up to 3 cm), so the fingers disappear into the leggings, the armour strips at the hips and the girls'
wrap skirt in every idle frame; vanilla dresses swallow them the same way. The leggings can't avoid a hand that
is inside the skin; hanging pieces at the hips (armour strips, trophies, feathers) could be solved to swing out
over the hand (not done; the user decides).

**Numbers** (deepest point inside the body, cm / how many points, over 3 frames of each clip, after this commit):
- Men: loincloth kneeling 1.1/4 (was 3.7), cross-legged 1.9/7 (was 7.7: flap buried in the legs), chair 0,
  standing 0.6; armour, war, duke, camp wrap under 1; king 1.5 cross-legged; trophy belts 2.3-2.8 cross-legged
  (pinched in the deep hip fold, hidden); mantle 1.8 standing (was 4.4), 0.8 kneeling.
- Women: loincloth 2.7 in the deep curtsey (was 5.7; the flap now folds over the raised thigh), chair 1.4,
  standing 0.8; war, camp wrap, trophy belts under 1; armour 1.3; duke/king aprons 3.2-3.7 on 8 points in the
  curtsey/kneel (they copy the flap's weights; the apron reaches lower than the flap); mantle 3.3 on 5 points in
  one standing emotion (the cape's top at the shoulder blades), and 2 points of its hem corner at the feet in the
  two-knee kneel.
- Leggings unchanged: 6-18 skin points at the bent knees peek through in kneels and seats (both bodies); up close
  they don't show (the leggings' quill pattern is white).
- Looked at in the Blender app after the last build: men's kneel (all sides), cross-legged, women's kneel and
  curtsey, standing idles, the women's cape kneeling (spreads behind over the heels).

**Next step**
- The user looks in game: Hold Court (petitioners kneel), the throne room (steppe court: cross-legged), bows.

**Tools**
- `inspect_scan.hands(sex, pieces)`: hands/forearms into each piece over the clips.
- `inspect_setup.py` loads all 27 solver clips per body; `build_in_app.py` keeps the build's globals in
  `bpy.app.driver_namespace["ek2lc_build_<sex>"]` (to re-run `solve_piece` there).
- The build now takes ~13 min per body in the app (the solve ~5.5 min).

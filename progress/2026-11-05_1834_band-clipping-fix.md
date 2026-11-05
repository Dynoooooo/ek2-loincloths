# Chest band clipping fix (women)

**Done** (commit: the one that adds this file)
- The band's top row sat level with the armpits, where the torso's slice takes in the upper arms, so the band wrapped round the arms (out to x = 25.8 cm) and sank 2.6-3.6 cm into them when they moved.
- Now the top edge dips 5.5 cm under the armpits (full height over the bust), each column is built from its own slice, true arm skin (arm weight > 0.9) is left out of the outline, and a last pass keeps every point 0.25 cm off the skin.
- Static clearance: 0 points inside on every body shape (was 25 points, -2.35 cm on fat).
- Over the callous_1/_2 idles the worst overlap went from -3.6 to about -1.6 cm. What's left is the arms resting on the band (crossed forearms in front, upper arms at the sides): the arm sits in front and hides it. Thinner sides made no difference, so not kept.
- Loincloth itself: unchanged (worst -0.4 cm, dwarf only).
- Not yet seen in game; it will be checked in the step 3a launch.

**In progress**
- Step 3a: war belt add-on (thick hide belt with teeth, claws, bone beads) over the Reach loincloth, men and women.

**Next step**
- Build the war belt in a new script `source/build_reach_war.py`, a new gene `gene_ek2lc_war`, and modifiers for adult Reach war roles.

**Decisions the user made**
- Women's look: "Clean up the clipping".
- Step 3a: go. War look for knights, commanders and anyone in an army, while their realm is at war (adult Reach only).

**Problems and workarounds**
- `female_body_AI_callous.anim` fails to import with io_pdx_mesh; use `female_body_AI_callous_1.anim` (301 frames) for the check file.

**How to test**
- Blender: `source/tools/make_check_blend.py -- source/reach_hide_f_v01.blend <game>/gfx/models/portraits/female_body/female_body_AI_callous_1.anim source/reach_hide_f_check.blend`.
- In game: as before (`ck3_test.sh`, temporary flag hook, barbershop).

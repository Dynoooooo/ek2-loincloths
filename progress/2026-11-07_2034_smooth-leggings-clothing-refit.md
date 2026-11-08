# Smooth leggings and clothing refit — working milestone, not zero clipping

**Done — work commit `76493ab`**
- All modelling, posing, visual inspection, and exports ran in the live Blender app. No headless Blender or delegation.
- Rebuilt both leggings on a smooth axis through the hip, knee, and ankle. The old axis averaged uneven skin vertices and jumped sideways between rows, folding the neutral mesh into spikes. Kept the dark hide, quillwork, lining, cuffs, and all body morphs.
- Improved the royal apron weights/clearance; refitted the female hide panels with a narrower lower cut and their original pose-solved weights. Broader weight smoothing made clipping worse and was rejected.
- Both capes have more room behind the arms and smoother hanging weights. The six shoulder/yoke rows keep their original skin weights so bowing does not open a gap below the collar. The fur cloak shares these repairs.
- Exported seven female and six male pieces, including their 13 female / 10 male blendshape files. Culture and undead variants reuse them automatically. No gameplay, outfit-selection, or barbershop-script changes.
- Rejected the male armour geometry adjustment and an experimental male cape weight solve because they increased penetration. Kept the accepted male panels.

**Sources and repeatability**
- Edited sources: `source/reach_hide_f_v02.blend`, `source/reach_hide_m_v02.blend`. The original v01 sources remain the procedural baseline.
- `source/fitting_female.npz` / `fitting_male.npz` preserve the reviewed coordinates and weights. `source/fitting.py` applies them before export in the normal build, with a topology/baseline guard.
- `source/tools/refit_clothing.py`: `resume(sex)` resumes v02 without double-baking corrections. `prepare(sex)` is for an unmodified v01. The tapered flap function is female-only.
- Existing GUI build entry remains `source/tools/build_in_app.py`. Do not remove the fitting archives or change baseline geometry without refitting.

**Checked**
- Reimported the actual exported game meshes into Blender; looked at standing, single/both-knee poses, the male cross-legged throne, female curtsey, and the scheming pose from several angles.
- Checked combined adult sliders and the infant-shaped tunic/leggings in the source scene. This was not every child animation or beast-tail combination.
- Every edited base/shape export has matching vertex counts and a skin block. Final saved weights normalize to one and use at most four bones. Python syntax and `git diff --check` passed.
- Fixed `inspect_setup.py`: exported skeletons with extra unused sleeve bones could create a separate rig; imported garments now explicitly follow the body's inspection rig. This avoids misleading body/clothing pose mismatches.
- Blender remains open on the exported male royal outfit. The Female scene has the curtsey. Ignored inspection file: `source/inspect_current.blend`.

**Remaining / next step**
- Clipping is reduced, not eliminated: the female hide flap still reaches about 1.65 cm into the thigh at the deepest curtsey; the female royal apron about 0.96 cm at one knee. Male hide about 1.28 cm in the two-knee pose; leggings about 2.1–2.2 cm at folded knees. These are sampled vertex depths, not a guarantee about every face/frame.
- The game's female idle also puts fingers into the underlying hip; fitting the leggings alone cannot remove that body/hand intersection.
- No CK3 launch this session, and no saves/settings changed. Pose inspection still uses the previous session's rotations-plus-root-translation assumption; confirm against the game before claiming the throne problem fully solved.
- Next: inspect Hold Court petitioners, Yashnag's cross-legged throne, and a female commoner's base hide look in game, including cold leggings. Address the remaining visible overlaps before expanding the mod.
- Test from the mod root in Nushell: `with-env {PLAY: "k_falkreath"} {bash source/tools/ck3_test.sh start ugc_2220326926 ugc_2919125340}`. The existing helper protects/restores settings and saves; finish with `bash source/tools/ck3_test.sh stop`.

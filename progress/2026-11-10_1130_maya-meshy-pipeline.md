# Audit, part 2: Maya Meshy pipeline, pose fix, first remake

**Done** (this commit)
- In game (Aldrydd + a test Reach woman, barbershop Scene tab poses): newer pieces' hanging parts fly out in the
  throne pose and kneeling (giant everyday's side strips, Keptu chieftain's back panel flipped up). Shots in
  `source/build_logs/ingame/` (ignored).
- error.log: cowrie war belt's portrait trigger read a variable on dead characters (990 errors). Fixed with
  `is_alive = yes` (generator + file). Next launch: 0 mod errors.
- `ck3scene.pose()`: throne clips seat the legs through unkeyed clip values; Maya stood them up. Fixed; poses re-dumped.
- `source/maya/mbuild.py` + `glb.py`: Meshy GLB -> fit, chest wrap, weights, .mesh, all shapes, asset lines,
  textures, in ~30 s per piece (both bodies). Checked against the Blender-built festival wrap (same fit).
- Remade with Meshy: Keptu Chieftain's Loincloth (painted hide apron, ringed belt with red gem, bearskin, chest
  wrap for women). Seen in game on Aldrydd (renders right). Concepts for the other 15 peoples' looks made and
  approved by eye; their 3D models are being made (task ids in `source/meshy/tasks.json`).
- Meshy credits spent: 9 + 30 (Keptu ruler) + 15 x 9 (concepts) + 15 x 30 (models) = 624.

**Next step**: download the 15 models (`meshy_download_model` to `source/meshy/<key>/model.glb`), then in Maya
`mb.build(key, key)` for each (fit_kw thin 0.2/tight 0.9 for fur ones), `make_colour.py`, look in Maya (rest, kneel,
throne), then one launch to look at all 16 in the barbershop (Scene tab poses), Loincloth set to No Loincloth.

**Problems**: weights of the new pieces are plain skin/skirt weights (2-5 cm into the thighs kneeling); the proxy
solver isn't good enough yet (moves the standing look). Computer Use can't type into CK3 (use ck3ctl console).

**How to test**: `OPEN=1 bash source/tools/ck3_test.sh start`, `wait`; ck3ctl console `effect open_view_data = barbershop`;
Peoples' Loincloths dropdown at the bottom of the list; Scene tab for poses; `stop` restores everything.

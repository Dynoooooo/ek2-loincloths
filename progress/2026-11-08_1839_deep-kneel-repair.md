# Deep-kneel clothing repair

**Done**
- Corrected the visible thigh intersections in the male/female hide flaps and royal aprons in Blender's sampled deep-kneel and curtsey poses. Both hide flaps and both royal apron sets returned zero sampled outer-panel contacts after the final surface fitting pass.
- Rebuilt the leggings on the body's leg triangles with matching skin weights. Kept the hide/quillwork atlas, lining, slanted upper hems, and all body shapes. The front ankle openings now arch upward to accommodate the feet when they fold against the shins in a deep kneel.
- Separated royal panels from the base hide, fading the extra clearance into their ties. Matched each hide flap's lining weights to its outer surface.
- Exported four pieces per sex: `leggings`, `reach_hide`, `reach_king`, `reach_duke`, plus 40 male and 52 female morph meshes. Culture/undead variants reuse these files.
- Fixed an export issue found during verification: quads could triangulate differently for different morphs. The app exporter and normal builder now triangulate the basis once and reuse its topology.
- All geometry, posing, exports, and visual checks used live Blender.app/MCP. No headless Blender, subagents, body-shrink genes, gameplay changes, or changes to the other agent's project.

**Files / repeatability**
- Author sources: `source/reach_hide_m_v03.blend`, `source/reach_hide_f_v03.blend`. v01/v02 are unchanged.
- Fitting archives: `source/fitting_male.npz`, `source/fitting_female.npz`. Full replacement topology and per-loop UVs preserve the new leggings during normal builds; baseline guards still apply.
- Author helpers: `source/tools/retopo_leggings.py`, `source/tools/fix_deep_kneel.py`. Use `refit_clothing.resume(sex)` on a v03 source before further fitting. Do not reapply the edits to an already fitted source.
- Independent skin-anchor reassignment and adaptive subdivision trials were discarded: vertex-only clearance hid face intersections. The earlier in-progress note is superseded by this one.

**Verified**
- Reimported the actual game meshes; inspected front/side/rear views of single-knee, both-knee, female curtsey, and male seated/cross-legged poses. Final arched cuffs were inspected in the app and reimported into both inspection scenes.
- All eight edited bases have skin blocks. All 92 morph exports match their base vertex counts and triangle indices; final leggings archives have matching shapes, normalized weights, and at most four bone influences.
- Fitting archive replay against original v01 sources matched the reviewed source coordinates within 0.000001 cm. Looked at a combined female adult slider sample and the tunic/leggings infant shape; this was not every slider combination or child animation.
- Changed Python syntax and `git diff --check` passed.
- Blender is left in ignored `source/inspect_current.blend`: Male has the both-knee royal outfit; Female has the curtsey with the base hide and leggings.

**Still unverified / exact next step**
- CK3 was not launched; working desktop/game UI control was unavailable (System Events returned -10827). No saves or game settings changed.
- The inspector retains the earlier rotations-plus-root-translation retarget assumption. It is not yet verified against the engine; these are Blender visual results, not an in-game or every-frame zero-clipping guarantee.
- Next: verify Hold Court petitioners and Yashnag's cross-legged throne in CK3, including a female base-hide wearer with cold leggings. Keep the final cuff openings; do not resume the discarded vertex-binding/subdivision experiments.

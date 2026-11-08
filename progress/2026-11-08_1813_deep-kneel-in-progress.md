# Deep-kneel repair — in progress

- User explicitly requested fixing the remaining deep-kneel clipping from the last milestone (`f3bf8dd`). Work is not yet finalized or committed.
- Blender.app/MCP only. Another task temporarily shared Blender; the user confirmed it has finished. The dragon/raptor project was saved and left untouched on disk.
- Current live Blender scene: male clothing. A timer is refining knee surfaces; log `source/build_logs/deep_kneel_surface_m.log`. Wait for `SURFACE DONE` before changing the live scene.
- Female intermediate accepted vertex-fit source/export: `source/reach_hide_f_v03.blend`. Four edited pieces: leggings, hide, king, duke. All sampled vertices clear the body; final face checks/refinements still need completing.
- New leggings follow the body's leg triangles instead of sparse ring geometry. `source/tools/retopo_leggings.py` builds them in the app. Existing colours/UV atlas and all body morphs are retained.
- `source/tools/fix_deep_kneel.py` performs local clearance, stable skin-anchor binding, royal layer separation, and adaptive subdivision of intersecting cloth faces. It uses solid-angle containment to reject false positives from reversed nearest normals at folded skin.
- Royal panels have 2 cm of extra layer clearance, fading to zero at their ties, to avoid the base hide poking through.
- Male: leggings/base/king/duke vertex contacts were zero before final adaptive surface checks. Some face interiors still crossed the body; the running timer subdivides only those patches and binds the added support points.
- `source/fitting.py` and `source/tools/refit_clothing.py` now support full topology + per-loop UV archives, not only vertex deltas. `source/build_reach_hide.py` consumes those UVs and saves v03 sources.
- Not using the experimental cuff shortening, foot-weight transfer, or body-shrink previews. Those trials were rejected. No gameplay/portrait gene changes.
- Next: finish male surface refinement, inspect multiple kneel/throne poses, save fitting archive and v03 source, export. Then load female v03 with `refit_clothing.resume('female')`, apply the same final surface refinements, and export again.
- Before completion: reimport actual exports, check body morph vertex counts and rebuild archive application, check static slider/child fits, write final progress note and commit. Do not describe all clipping as fixed before these checks.
- No CK3 launch or save/settings changes this session.

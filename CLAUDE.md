# EK2 Loincloths — notes for Claude

Read first: `~/Documents/Paradox Interactive/EK2_LOINCLOTHS_SOLO_MODDER.md` (design, CK3 facts, in-game testing rules), then the newest file in `progress/`.
Its Blender sections are obsolete: Maya replaced Blender on 2026-11-10 (see below).
Add new facts here, one short bullet each, with the date.

## 3D app: Maya 2027 (Blender is gone)
- Blender was uninstalled on 2026-11-10 and the user will NOT reinstall it. Never suggest it.
- Maya 2027 at `/Applications/Autodesk/maya2027/Maya.app` (Python 3.13.9, PySide6 6.8, numpy 2.3.5 in `mayapy`).
- Work in the Maya GUI through the `maya` MCP, so results get checked by eye (same reason as the old "no headless Blender" rule).
- `mayapy` (`/Applications/Autodesk/maya2027/Maya.app/Contents/bin/mayapy`) is fine for pure-numpy tools: `source/tools/make_colour.py`, `check_colour.py`.

## Maya MCP
- Server `maya` = GG_MayaMCP (PyPI `maya-mcp`, v0.6.1), run as `uvx maya-mcp` from `claude_desktop_config.json`.
- Env: `MAYA_MCP_ENABLE_RAW_EXECUTION=true` (raw Python via `script_run`), `MAYA_MCP_CLAUDE_DESKTOP_COMPAT=1` (underscore tool names), `MAYA_MCP_SCRIPT_TIMEOUT=600`.
- It talks to Maya's commandPort `localhost:7001`. `~/Library/Preferences/Autodesk/maya/2027/scripts/userSetup.py` opens it when Maya starts. Check with `health_check`, `scene_info`; look with `viewport_capture`.

## PDX exporter in Maya
- io_pdx_mesh 0.91 (ross-g, the only Maya build) in `~/Library/Preferences/Autodesk/maya/scripts/io_pdx_mesh`.
- Patched for Maya 2027 (redo if you reinstall it; some files have CRLF line endings, so sed patterns must allow `\r`):
  - `from importlib import reload` in `__init__.py` and `pdx_maya/maya_ui.py` (Py 3.13 has no `imp`);
  - `maya_ui.py`: PySide6/shiboken6 import first, `dialog.screen()` instead of `QDesktopWidget`, `list(ENGINE_SETTINGS.keys())[0]` (2 places), and `closeEvent` skips `removeCallback` when `self.id` is unset.
- Checked 2026-11-10 in the Maya GUI: the tool window opens, and `ek2lc_art_amber_artifact.mesh` imported and re-exported at the same size (113,132 bytes).
- `import io_pdx_mesh` opens the tool window. Script API: `from io_pdx_mesh.pdx_maya import maya_import_export as ie`, then `ie.import_meshfile(path, imp_mesh=True, imp_skel=True, imp_locs=True)`, `ie.export_meshfile(path, exp_mesh=True, exp_skel=True, exp_locs=True, exp_selected=False)`, `ie.import_animfile`, `ie.export_animfile`.
- Needs PyMEL. PyPI's pymel 1.5.0 breaks on Py 3.13 (`logging._acquireLock`). Installed instead (2026-11-10, user's OK): the community fork iamsleepy/pymel 1.7.1rc1 (wheel from its GitHub releases, has Maya 2027 caches) in `~/Library/Preferences/Autodesk/maya/2027/scripts/site-packages`, which Maya puts on `sys.path`.
- The MCP's `health_check` says "offline" until the first real call; `scene_info` connects it.

## Old Blender pipeline
- The bpy scripts (`build_reach_hide.py`, `build_regalia.py`, `weight_solver.py`, `fitting.py`, `tools/build.sh`, `refit_clothing.py`, icon renderers, etc.) moved to `source/legacy_blender/`. They need `bpy`/`mathutils` and can't run any more. Use them as the recipe when porting to Maya (`maya.cmds`, `maya.api.OpenMaya`, numpy).
- Pure-numpy modules stay in `source/` (`colour.py`, `cultures.py`, `undead.py`, `fitting_*.npz`, `tools/make_colour.py`, `gen_script_files.py`, `install_art.py`).
- All `.blend` files went to the Trash; `*.blend*` is gitignored. The six tracked ones are still in git history: `git log --all -- source/reach_hide_m_v03.blend`, then `git show <hash>:<path> > file`.
- The shipped `.mesh` files are the real source now: import them into Maya with io_pdx_mesh.

## Meshy
- The user has Meshy Premium. Models: geometry `meshy-7.1`, texture `meshy-7`. Images: `gpt-image-2-5-sunburst`; MCP v0.6.10 (latest on 2026-11-10) refuses `gpt-image-2-6-sunburst`, so re-check with `npm view @meshy-ai/meshy-mcp-server version`.
- Sources go in `source/meshy/<key>/` (concept.png, model.glb, textures).

## Audit tools in Maya (2026-11-10)
- `source/maya/ck3scene.py`: body + every vanilla/EK2 body shape (blendShape targets named by game attribute), pieces with their shapes on the same skeleton, game poses (`pose(sex, clip, frame)`). `audit.py` measures clipping, poke-through, stretch, weights, shells, UVs; `run_audit.py` runs every piece x shape x pose, results in `source/build_logs/audit/<sex>.json` (ignored).
- 2026-11-10: the maya MCP's calls time out after about 60 s, but Maya keeps running the code to the end; split long jobs (2 poses per call) or check the state afterwards.
- 2026-11-10: io_pdx_mesh's `import_animfile` zeroes every joint's jointOrient and puts every bone in the clip at the clip's initial pose. `ck3scene.pose()` restores the rest pose (with jointOrient), puts bones the clip doesn't key back at rest, and gives every bone but the roots its rest length (the old Blender rule; still not checked against the game).
- 2026-11-10: women's clips key `bn_l_sleeve`/`bn_r_sleeve`, which the body lacks; `pose()` adds them under the elbows.
- 2026-11-10: io_pdx_mesh makes Maya vertex i from file vertex i (no welding), so weights can be written straight into a `.mesh` skin block (`skin_io.patch_mesh`; unused slots are ix -1, w 0.0) and the shape files stay valid.
- 2026-11-10: `MMeshIntersector.create` needs the shape node (`dagPath.extendToShape()`), not the transform.
- 2026-11-10: the game body is low-res (male 3,206 verts); our pieces carry the full 134-bone skeleton (skirt and cloak chains included).
- 2026-11-10: the `sitting` clip is played by no vanilla or EK2 event; kneels are (57 events), throne poses everywhere. EK2's steppe/Indian courts seat rulers cross-legged (`throneRoom_ruler3_1`).
- 2026-11-10: EK2 body shapes our pieces lack: `giantish_body_bs` (75 pieces), `imgan_body_bs` (all), `bs_briarheart_body` (men, all). EK2's own clothes lack them too (only one fur follows Briarheart).

## Validation (2026-11-10)
- ck3-tiger loads EK2 through `source/tools/ek2_for_tiger.mod` (EK2's own `ugc_2887120253.mod` makes tiger 1.19 stop with "Invalid config"). Remaining reports sit in EK2/vanilla files (tiger 1.19 doesn't know CK3 1.20); read only our files' lines.
- clausewitz `validate_mod` with EK2 indexed: the full run and `unknown_script` time out; run `syntax`/`encoding`/`localisation` alone. Its "missing loc" hits for `set_variable` names are false positives.

## Meshy pieces in Maya (2026-11-10)
- `source/maya/mbuild.py` + `glb.py`: Meshy GLB -> fitted piece. `mb.build(key, base, fit_kw=..)` does both bodies: fit round the hips (port of the Blender meshy_fit), women's chest wrap from the garment's top part (`fit_band`, hull over the bust), weights (skin at the belt, skirt chains below, as vanilla skirts), writes the `.mesh` straight with `pdx_data` (template: the festival wrap's file; Z negated, triangle corners reversed), every body shape (`shapes.py`) and the `.asset` lines, then textures. Then run `mayapy -I source/tools/make_colour.py` for the diffuse and colour mask.
- 2026-11-10: Meshy GLBs load as Maya space directly (glTF Y up, front +Z); their UVs are already the file's u0 (v down).
- 2026-11-10: Meshy's image_to_3d with `should_remesh` + `target_polycount 8000` gives ~7-8k tris and PBR maps in `model_textures/` (base_color, normal, roughness, metallic). Fur comes out as a thick volume: `fit_kw={"thin": 0.2, "tight": 0.9}`.
- 2026-11-10: `ck3scene.pose()` must keep the clip's own value on bones the clip lists without keys: the throne clips (`throneRoom_ruler2_1`) seat the legs that way (seen in game; the "unkeyed bones at rest" rule stood the throne pose up). Re-dump `pose_dump.dump_poses(sex)` after changing pose().
- 2026-11-10: plain skin-to-skirt weights clip 2-5 cm kneeling/cross-legged (vanilla robes ~15); the solved Reach pieces ~0. `wsolve.py` on a proxy (`mb.dump_proxy`, `tools/solve_bg.sh`) runs in 2-4 min but moves the standing look ~4 cm: not used yet.

## In-game checks (2026-11-10)
- Rebuild `ck3ctl` each session: `swiftc -O -o <scratchpad>/ck3ctl source/tools/ck3ctl.swift` (`~/.copilot/bin` is gone). Console keys through it work with CK3 in the background.
- Computer Use can click CK3 (app "ck3", full screen tools) but refuses to type into it (dev-path app, "focus anomaly"): type only through the console with ck3ctl.
- Barbershop Scene tab: pose dropdown (Kneeling, Sit on Throne Version One/Two, Curtsey, Bowing...), Zoom +/- buttons, Hide UI; the pose list scrolls ~1.5 entries per pixel of its scrollbar. Good for pose checks without events.
- Portrait-modifier triggers that read variables need `is_alive = yes` first (dead "weak" characters hold none; vanilla does the same): the cowrie belt logged 990 errors per launch before.
- 2026-11-10: Meshy cloth is a two-sided shell; any push that moves only the layer touching the skin pops it through the outer layer (holes showing the body). `shapes.spatial_spread` carries pushes by distance (2.5 cm) so both layers move; `mb.repair_poke` also samples the body's faces (the low-res body pokes between its vertices).
- 2026-11-10: Meshy's concept "strip between the legs" can't be fitted radially (it becomes a bar across both thighs): `mb.crotch_mask` drops it. A three-quarter concept can come out turned (the tabard's panels at the hips): `build(..., yaw=-90)`.
- 2026-11-10: the chest wrap's fit must ignore the upper arms: their skin is weighted to `bn_*_deltoid` (not "shoulder").
- 2026-11-10: properties maps: vanilla marks metal R ~1, B ~0.7, A ~0.35 (cloth R 0, B 0). `mb.textures` sets that where Meshy's metallic map > 0.5 and the colour looks like metal (Meshy grades silk as half metal); make_colour then leaves metal out of the colour mask.
- 2026-11-10: regalia (art_*) also have an artifact-window model (`ek2lc_<key>_artifact.mesh`, static, court shader) and an icon strip: `mb.write_display(key)`, `icons.render(key)` (viewport shot on black and white, alpha from the difference).
- 2026-11-10: `BG=1 OPEN=1 ck3_test.sh start` launches CK3 behind the user's windows (`open -g`). Console keys work then; event windows ignore posted keys (option hotkeys need CK3 in front, and Escape opens the pause menu): click events only when the user is idle.
- 2026-11-10: CK3 in debug mode reloads textures that change on disk; rewriting DDS (make_colour.py) while it runs logs 'Expected more data in the texture mipmaps' and VkResult -3. Stop the game before rebuilding textures.
- 2026-11-10: Meshy sources (`source/meshy/**/*.glb`, `*.png`) are in Git LFS (`.gitattributes`); history was rewritten with `git lfs migrate import --everything`, so commit hashes in progress notes from f183555 (festival wrap) on no longer match: find commits by message. After a migrate, run `git lfs checkout` (it leaves pointer files in the working tree).
- 2026-11-10: `*.mesh` and `*.dds` are in Git LFS too (history rewritten again). LFS keeps every version whole (no delta compression), so locally `.git` grew to 3.1 GB (2.7 GB LFS store); it pays off only with a remote. PNG sources (425 MB) and the old .blend files (72 MB) are still in the git pack.
- 2026-11-10: the game maps a piece's skin indices onto the body's bones BY INDEX: a piece's skeleton must be the body's (same bones, same ix order). The women's Reach pieces carried two unused sleeve bones (from the old Blender inspector) that shifted later indices, so seated thighs followed the ankles in game while Maya (by name) looked fine. Check any new mesh with `skel_fix.check(path, sex)`; fix with `skel_fix.fix`.

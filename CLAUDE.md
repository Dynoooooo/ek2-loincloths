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

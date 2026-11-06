# Fig-leaf side fix (investigated, blocked; not fixed)

**Done** (commit: the one that adds this file)
- Traced the attachment in both vanilla and EK2: `clothes` gene, `no_clothes` template (index 1), adult accessories `male_clothes_secular_western_nudity_01` / `female_clothes_secular_western_nudity_01`, with their corresponding nudity entities. This is not a separate fig-leaf gene.
- Our `source/tools/gen_script_files.py` explicitly selects `clothes = no_clothes` in every wearing modifier. Both upstream clothes genes have no empty-clothes template.
- Vanilla/EK2 portrait modifiers support explicitly selecting an accessory within a template. Whether that can select `empty` outside this template's accessory list was not verified; no speculative script change was made.
- Reviewed the geometry route in `build_reach_hide.py`: body-bound pouch points and separately hanging front/back flaps, with body-shape-specific obstacle projection. The flaps do not form a closed side cover. A wrap or front-position change would require rebuilding and checking every shape, especially dwarf and digitigrade.
- Started CK3 using `source/tools/ck3_test.sh`; the helper confirmed the map was running. Stopped it using the helper, which reported successful restoration of settings, presets and saves.
- No meshes, textures, genes or portrait modifiers were changed. Vanilla and EK2 files were only read.

**In progress**
- The fig-leaf sliver is unchanged. Neither additive suppression nor a geometry fix was validated.

**Next step**
- kids' set (step 6)
- The fig-leaf fix remains blocked and must not be treated as completed.

**Problems and workarounds**
- Non-interactive permissions denied the standalone brief, Clausewitz workspace access, Blender scene access and compilation of the native CK3 input controller. Without approved input access, the required barbershop side views and before/after screenshots could not be captured. No screenshots were added.
- `error.log` was inspected for the baseline launch: existing EK2/vanilla warnings and the seven stale saved-preset `ek2lc_*` game-rule references were present. This was not a validation of a fix.
- The previous failed pouch-rounding attempt remains reverted; existing dwarf clipping was not changed.

**How to test**
- Once tool permissions are available, finish the fig-leaf fix before claiming it is gone: nudity off, Reach man, Argonian woman and another culture, both side views and a full turn; preserve nudity-on behavior.
- Use `bash source/tools/ck3_test.sh start`, then `bash source/tools/ck3_test.sh wait`; always finish with `bash source/tools/ck3_test.sh stop`.
- For a geometry change, rebuild through `build_reach_hide.py` and check every blend shape and side-ray occlusion before the in-game checks.

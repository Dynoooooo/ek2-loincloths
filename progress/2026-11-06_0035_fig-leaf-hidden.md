# Fig leaf hidden under our loincloths (seen in game)

**Done** (commit: the one that adds this file; done by Claude Code, not Copilot)
- Cause: our wearing modifiers set `clothes = no_clothes`. That template's accessory (`male/female_clothes_secular_western_nudity_01`) is only a fig-leaf mesh (132 vertices, about 14 cm wide, in front of the hips). Nothing in the shaders depends on "Show nudity", so it was drawn under our loincloths with nudity on or off and peeked out from the side. Vanilla itself only uses `no_clothes` with nudity on.
- Fix: every loincloth accessory (hide, fine, royal; all cultures, men and women; 54 in all) now has `set_tags = "ek2lc_loincloth"`. New file `gfx/portraits/accessories/zz_ek2lc_figleaf.txt` redefines the two vanilla fig-leaf accessories with a first variant that draws nothing when that tag is set (vanilla's `required_tags` pattern, as on ccp4's khanty hood), then vanilla's own entity as the fallback. Anyone not wearing one of our loincloths still gets vanilla's fig leaf, including our wearers who pick "No loincloth" in the barbershop.
- Both written by `source/tools/gen_script_files.py` (`figleaf()`, `LOINCLOTH_TAG`).
- In game, launch 1: a test version drew our mantle instead of nothing. Aldrydd wore the mantle with Clothes = No Clothes and Cloak = None, which proves the redefinition wins over vanilla's (the `zz_` file is read after `clothes.txt`) and that the loincloth's tag reaches it. Launch 2: the real version, no mantle, loincloth unchanged. error.log: nothing about these files.

**In progress**
- Nothing half-made.

**Next step**
- Kids' set (step 6), by Claude Code. The user stopped Copilot for this mod.
- A Copilot run had started on the kids' set and was stopped. Its only edit (adds `is_adult = yes` to the war and royal modifiers in `gen_script_files.py`, so adult pieces never land on children) is in `git stash` ("copilot kids-set partial"). Decide on it when doing the kids' set.

**Problems and workarounds**
- Not yet looked at from the side in game (turning the model needs mouse clicks). The fix replaces the fig leaf's entity rather than covering it, so no angle can show it.
- This redefines two vanilla accessory keys (not a whole vanilla file). Any other mod that also redefines `*_clothes_secular_western_nudity_01` will clash with it, depending on load order.
- `effect open_view_data = barbershop` sent right after `ck3_test.sh wait` can be lost; send it again. A "No Social Profile found" pop-up can cover the barbershop; Return dismisses it.
- The seven `ek2lc_*` lines in error.log are saved game-rule presets left over from the deleted first version of the mod, not our files.
- `~/.copilot/bin/ck3ctl` is a prebuilt `ck3ctl` (copies in /private/tmp vanish on restart).

**How to test**
- `source/tools/ck3_test.sh start`, then `wait`; console via `ck3ctl key <pid> 50`, `ck3ctl type <pid> "effect open_view_data = barbershop"`, `ck3ctl key <pid> 36`; screenshot with `screencapture -x -o -l $(ck3ctl winid <pid>)`; `ck3_test.sh stop`.

# Better Barbershop support: body sliders done, recolouring works but painted lines look dull

**Done** (commits 9b0d583, 14dd04b, 6118f8f, c30c3de and the one adding this file; Claude Code + Copilot CLI)
- Body sliders: Better Barbershop only adds offsets to gene_bs_body_type / _body_shape / _bust / gene_height (`mode = modify`, never a template change). Our pieces already follow every shape those drive (fat, gaunt, muscular, bust size; body-shape morphs and height are bones). Seen in game at both ends, band and belt follow, no clipping (`progress/screens/bb_body_sliders.jpg`). No change needed.
- Recolouring: CK3 1.20 shows the colour swatch only beside the vanilla genes (Clothes, Headwear, Cloak, Legwear). Their colours are stored per "colour block", and any entity whose name starts with that block's prefix (common/defines/jomini/portraits.txt) reads them. Our entities are now `f_clothes_…` (loincloths, bands), `f_legwear_…` (girdles, war/royal aprons, camp wrap, trophies) and `f_cloak_…` (mantle, shoulder guard), with the pattern shader, a mask and a variation. Seen in game: the Clothes swatch, Primary Color 1, recolours loincloth, cord belt and chest band together (`progress/screens/bb_clothes_picker_red.jpg`).
- Made by `source/tools/make_colour.py` (Blender's Python; the Blender build runs it at the end). Only each texture's main hide/cloth (biggest colour group) is masked. Its diffuse is stored divided by its colour, per mip level, and the palette holds that colour. Paint, beads, bone and metal keep their own colours.
- Two test launches as the brief asks: with Better Barbershop (Claude Code), without it (Copilot, twice). error.log is clean for our files.

**In progress / open problem**
- Thin painted lines on masked hide (e.g. the zigzag band on the plain loincloths) render dull mauve-grey in game instead of red-orange (`progress/screens/colour_recheck2_f.jpg` vs `camp_wrap_and_guard_f_ingame.jpg`). The cause is texture filtering at the mask edge: neutral hide × colour next to an unmasked red line doesn't average back to the original.
- Mask channels G and B never took a colour on our pieces in game, neither from the palette nor from a picked colour. So USED_GROUPS = 1.

**Next step** (ask the user first; it needs one more check launch)
- Fix: mask the paint too. Put all soft pixels in channel R, divided by the hide colour, so no mask edge runs along the paint. For decorations brighter than the hide (bone-white motifs, beads), use a partial mask so nothing clips. Paint then shifts with the picked colour. Re-run make_colour.py, then do one look-only check (Copilot task `~/.copilot/tasks/ek2lc_task5_render_recheck.md`).
- Or revert recolouring (`git revert` of the four colour commits) if the user prefers the old look.

**Decisions the user made**
- "Do it" for Better Barbershop support. Use Copilot as a subagent on `claude-opus-5.5 --reasoning-effort xhigh`, and watch for refusals and hidden toning-down edits (none so far: both runs changed only screenshots).

**Problems and workarounds**
- A variation's pattern textures share a texture array with the character's other pieces, so they must match vanilla's layout: colour masks DXT5 512² with 2 mips; normal and properties maps DXT5 512² with full mips. Vanilla's no_*.dds are DXT3, so don't reference them.
- Vanilla's fixed layout form is `scale = { min = 1 max = 1 }` (ck3-tiger rejects scalars).
- Computer-use can't type into ck3 (the app has no bundle id, so it reports a "focus anomaly"). Clicks and drags work, but in the colour square only drags take.
- error.log "Failed to read key reference ek2lc_*" for 7 game rules: the presets file still remembers rules from the deleted first version of the mod. Harmless.

**How to test**
- `source/tools/ck3_test.sh start ugc_2220326926` (with Better Barbershop) or `start` alone, then `wait`, then Return. Console: create a Reach woman with `dynasty=none` saved to `global_var:c`, then `effect set_player_character = global_var:c` and `effect open_view_data = barbershop`. Use the swatch beside Clothes and drag in the colour square. Better Barbershop sliders: `effect set_variable = { name = bb_gene_bs_body_type value = 0.45 }` (also bb_gene_bs_body_shape, bb_gene_bs_bust, bb_gene_height).

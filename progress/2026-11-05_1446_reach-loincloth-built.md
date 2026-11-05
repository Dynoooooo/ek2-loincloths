# Reach hide loincloth (adult men) built, first game test next

**Done**
- `source/build_reach_hide_m.py` builds everything in ~2 s (headless Blender): cord belt, strip between the legs (a pouch over the fig leaf), fringed front and back flaps folded over the belt. Exports the .mesh, 5 body-shape meshes (fat, gaunt, muscular, old, dwarf), DDS textures and the .asset. Blender preview: `source/preview/preview.png`.
- Game files: gene `gene_ek2lc_loincloth` (template 0 = none, 1 = `ek2lc_reach_hide`), accessory `ek2lc_m_reach_hide_01`, portrait modifier group `ek2lc_loincloth` (priority 101).
- ck3-tiger (with EK2 loaded as base): nothing reported for our files.

**In progress**
- Not yet seen in game.

**Next step**
- `source/tools/ck3_test.sh start`, then `wait`. Open the console (key code 50) with `ck3ctl` and type:
  `effect create_character = { age = 30 gender = male culture = culture:reachman faith = root.faith employer = root save_scope_as = t } scope:t = { open_view_data = character }`
  Screenshot with `screencapture -x -o -l <ck3ctl winid>`, then `ck3_test.sh stop`.

**Decisions the user made**
- Step 1 approved; men first, women together with the chest band next. Screenshots wanted (2-3).

**Problems and workarounds**
- EK2 stacks outfit groups by priority (culture 1, armour 4, children 35, events 100). Ours is 101 and sets clothes/legwear/cloak to none, so no EK2 outfit can end up on top.
- Fig leaf (nudity off) sits up to 2.5 cm off the body; the strip is lifted into a pouch over it.
- History IDs (e.g. `sarkarain_101`) aren't console IDs, and Aldrydd has no adult brothers, so the test creates a man.

**How to test**
- See "Next step". Loincloth rule for now: adult Reach men who are commoners (always).

# Audit, part 4: lich looks remade, Meshy normals fixed, women's Reach skeleton fixed

**Done** (commits 864388a, e1f6180, 77c302a; none of it seen in game yet)
- Women's Reach pieces (hide, war, armour, duke, king, mantle, leggings): their skeleton had two extra sleeve bones,
  which shifted every later bone index. The game maps skin by index, so the leggings' thighs followed the ankles and
  stood up when seated. Now the body's own skeleton (`source/maya/skel_fix.py`); every mod mesh checked.
- Meshy pieces: 3-15% of each piece's triangles were shaded facing inward (dark blotches; the "white flecks"), from
  welding normals across the two cloth layers. Fixed in the writer and repaired in place on all 25 earlier pieces
  (`fix_meshy_normals.py`). Also flipped copies of triangles whose back can be seen (CK3 culls back faces).
- The 22 lich looks that reused a living mesh are their own Meshy pieces now (`lich_remake.py`, prompts in
  `source/meshy/lich_prompts.json`): loincloths x3, skirt, tunic, chest bands x3, war, armour, duke/king/emperor
  aprons, camp wrap, charm, trophy cords x3, leggings, mantle, fur robe, shoulder guard. Lich fauld and tassets
  refitted over them. Checked in Maya: front/side/back, kneel, throne (contact sheets).
- Meshy credits: 2,112 -> 1,242 (870 spent; resets Dec 10).

**Next step**: CK3 needs Steam running (it hung at 0% CPU without it, 2026-11-10 16:45). With the user's OK to start
Steam: `BG=1 OPEN=1 bash source/tools/ck3_test.sh start`, then (1) a Reach woman seated in the barbershop (Scene tab,
Sit on Throne): leggings must lie on the lap; (2) a lich (console: make Aldrydd a lich, or `hello` an EK2 lich) in the
barbershop: the new lich pieces; (3) any Meshy piece: no dark blotches; (4) when the user is away: the 37 events and
8 decisions (click the first option). Grep error.log for ek2lc.

**Decisions the user made**: "Remake the lich ones" (2026-11-10); culture colourways (~100 per sex, Reach meshes
with culture textures) stay texture variants for now (more credits than are left).

**Problems**: hanging parts of all Meshy pieces still clip 2-5 cm kneeling/cross-legged; aprons lie forward like
boards on the throne. Capes from a three-quarter concept need `yaw` (mantle 12.5, fur robe 5).

**How to test**: as above; the mod's CLAUDE.md has the in-game rules (no texture rewrites while CK3 runs).

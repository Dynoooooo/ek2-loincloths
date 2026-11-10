# Audit, part 1: Maya tools, script check, body shapes fixed

**Done** (commits f927414, e3e40f5 and this one)
- Setup: Maya 2027 + PyMEL + io_pdx_mesh work; clausewitz indexed; ck3-tiger now loads EK2 (`source/tools/ek2_for_tiger.mod`).
- Script: tiger and clausewitz clean for our files; every barbershop name resolves. error.log in game: only Go Native /
  Return decisions lacked `ai_check_interval` (fixed: 0, as vanilla's player-only decisions).
- Maya tools in `source/maya/` (see CLAUDE.md): `ck3scene` (body, all vanilla+EK2 shapes, poses), `audit`/`run_audit`
  (clipping per piece x shape x pose), `shapes` (new shapes from the body's own displacement; repair passes),
  `look` (contact sheets), `pose_dump` + `wsolve` (port of the pose weight solver; mayapy) + `skin_io` (weights into .mesh).
- Shapes: giantish added to the 75 pieces that lacked it, imgan to the leggings (feet); every piece's shapes pushed out
  where they clipped (fat+muscular belly ~1 cm on ~50 pieces, pregnant+fat ~3.5 cm, teens, hunter's pouch 1.8 cm, priest
  apron on draugr 1.2 cm, victor's sash knot 0.5-0.7 cm in the rest shape). Rest-pose audit now: worst 0.75 cm on two
  armpit vertices of the women's peoples chest pieces (child shape).
- Briarheart (chest cavity only) and imgan (feet only) need nothing on the other pieces.

**Found, not fixed yet**
- Poses: the Reach pieces (solved 2026-11-07) pass kneel and throne; the newer pieces (wraps, peoples, regalia, wrestler,
  priest...) clip 2-6 cm into the raised thigh kneeling, and women's 3-9 cm in bows, cheers, curtsey and the throne (their
  skin-to-skirt-chain weights act like vanilla dresses). The solver port works (malo 3.96 -> 1.93 cm) but is slow
  (143 s/piece) and not good enough yet. The pose model is still unchecked against the game: look in game first.
- Low detail (flat boards, thin procedural textures), remake candidates for Meshy: the 16 peoples' looks, wedding/mourning/
  elder wraps, priest apron, holy tabard, Champion's Apron (also a rayed sun); crude face decals on lich ash/fauld.
- Meshy: 3,048 credits (resets Dec 10). Spent today: 0.

**Next step**: in game (`OPEN=1 bash source/tools/ck3_test.sh start`; the bare binary isn't a registered app, so Computer
Use can't type into it): barbershop on Aldrydd, a newer piece kneeling/throne if reachable, error.log; then port meshy_fit
to Maya and remake the weak pieces; then events/decisions/icons in game.

**How to test**: as above, then `wait`; console `effect open_view_data = barbershop`; `stop` restores settings and saves.

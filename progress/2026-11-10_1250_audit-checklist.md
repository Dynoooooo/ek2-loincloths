# Audit checklist, part 3 (supersedes 2026-11-10_0704_audit-checklist.md)

Ticked = checked and fixed this audit. Per-piece shape list: see the 0704 file (giantish now on every piece).

## Pieces
- [x] 16 peoples' looks (Giants, Keptu, Old Nedes, Yokudans x everyday/ruler/warrior/festive): remade with Meshy,
      both bodies, women's chest wraps, every body shape. In game: 4 rulers (Aldrydd) + 4 commoner women.
- [x] Champion's Apron (+ artifact display model, icon), Sacred Aprons, Holy-Order Tabard, wedding, mourning,
      elder's wraps: remade with Meshy, fitted over the loincloth/leggings worn under them. Not yet seen in game.
- [x] Lich Barrow-Iron Fauld, Lich Bonemold Tassets: remade (the crude face decals). Not yet seen in game.
- [x] Festival wrap (Meshy, earlier): re-checked in Maya; same fit with the Maya port.
- [x] Reach set (hide/fine/royal, band, war, armour, duke, king, mantle, skirt, tunic, leggings) and its culture and
      grave variants: solved weights, ~0 cm in kneel/throne/cross-legged in Maya. Leggings: women's seated pose
      shows their tops standing up (in game, 2026-11-10 shot) - not fixed.
- [ ] Other procedural pieces (camp/ragged/werewolf/sailor wraps, 7 regalia, wrestler, hunter, victor sash,
      cowrie, arena guard, trophies, kid charm, lich twins): not remade; plain weights clip 2-6 cm kneeling.
- [ ] Lich twins that reuse a living piece's mesh with a lich texture (arena guard, camp wrap, kid charm, leggings,
      trophies, Reach-set lich looks): against the "no texture variants" rule; ask the user.

## Script
- [x] error.log: cowrie belt variable on dead characters (990 errors) fixed; 0 mod script errors after.
- [x] ck3-tiger: 0 reports in our files (164 in EK2/vanilla: tiger 1.19 vs CK3 1.20).
- [x] Every event picture (13), decision picture (8), trait (3), court position (1) and artifact icon (8): sizes and
      formats match vanilla; every DDS has its full mip data (451 checked).
- [ ] Events (37) and decisions (8) clicked through in game: only ek2lc_life.0001 seen (renders right). Keys can't
      answer event windows with CK3 behind; needs the screen while the user is away.

## Tools (source/maya)
- [x] mbuild.py (Meshy -> piece), glb.py, sheet.py (contact sheets), icons.py (artifact icons), pose() fix.
- [ ] Pose weights for hanging parts (wsolve proxy: fast, but moves the standing look); a bs_body_seated shape
      (vanilla's throne trick) not tried.

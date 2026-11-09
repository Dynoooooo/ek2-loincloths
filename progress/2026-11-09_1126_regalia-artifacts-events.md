# Commissioned regalia (wearable artifacts) and the events pack

**Done** (not yet seen in game)
- 8 new regalia pieces, each its own mesh and texture (user: "Absolute no asset reuse!!"), both bodies, every body shape:
  Champion's Apron, Malacath's Iron Fauld, Feather Girdle of the Ancestors, Briarheart Girdle, Hist-Amber Wrap,
  Green Pact Bone Apron, Ancestor-Ash Tassets, Mane's Moon Silk. Built and looked at in Blender (front, back, both sexes).
- They are artifacts (own type `ek2lc_loincloth_regalia`, regalia slot). Equipped → `var:ek2lc_regalia = flag:<style>` →
  gene `gene_ek2lc_regalia` draws the piece over our loincloth; it hides the war/royal girdle, trophies, camp wrap, charms
  (tag `ek2lc_regalia`). Barbershop row "Regalia". Recolourable (legwear block).
- Icons (4 rarity frames) and the artifact window's static models rendered/exported from Blender; decision picture rendered too.
- Decision "Commission Ceremonial Regalia" → style (own people's / champion / feather / foreign) → grade (rough/fine/
  masterwork, 40/120/300 gold, x1.5 for kings) → months later: finished (rarity by grade + stewardship), or the weaver flees,
  or a vassal bids for it. Yearly: patron's gift of a Champion's Apron to a knight, moths, inherited regalia at court.
- Events pack (events/ek2lc_life_events.txt): First Loincloth at 14 (own / child's), trophies after 3/6/10/15 battles won,
  the knot gives way at a feast, sumptuary petition, scandalised guest, Hist sap (Argonians), Hircine's night (lycan_character),
  cold snap. Hooks appended in common/on_action/ek2lc_on_actions.txt.

**Files**: source/build_regalia.py (pieces; reuses build_reach_hide.py's code, not its meshes), tools/render_regalia_icons.py,
tools/build_in_app.py now takes `script=`. Recolour pass (make_colour.py) also re-synced a few older culture sets (orc, goblin,
charm, lich war) to their current PNG sources; that is the pipeline's normal output.

**Next step**
1. In game: console `effect = { ek2lc_create_regalia_effect = { STYLE = art_champion RARITY = famed OWNER = root } }` as a Reach
   character (bookmark command below), check the portrait, the artifact window and the icon; then take the decision.
2. Then the new auto-worn meshes the user picked: wrestler's belt, hunter's pouches, priest's long aprons, victor's sash.

**Problems**: ck3-tiger 1.19 can't load EK2 (its "Invalid config" on EK2's descriptor), so run it on our mod alone with
`--config /dev/null`; EK2 trigger errors are noise. Loc data functions take `[name.X]`, not `[scope:name.X]`.

**How to test**: `./ck3.app/Contents/MacOS/ck3 -gdpr-compliant -debug_mode -skip -bookmark=bm_interregnum -play=d_druadach`

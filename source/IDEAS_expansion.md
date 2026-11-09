# EK2 Loincloths: expansion ideas (2026-11-09)

**Status (2026-11-09): everything below is built** (see progress/2026-11-09_* notes), each piece as its own mesh
(the user: no asset reuse). Extra, not on the list: the Loincloth Maker court position and trait (three ranks).

Research (exa): loincloth types worldwide, UESP lore (Reach, Argonian, Bosmer, Ashlander), CK3 artifact modding,
Hawaiian feather regalia, sumo keshō-mawashi, Aztec reward clothing. Notes on sources at the bottom.

Cost tags: **T** = texture variant on an existing mesh (cheap, no Blender geometry). **M** = new mesh (Blender app,
both sexes, all body shapes, eye-checked; the expensive kind). **S** = script only (events, decisions, artifacts).

## 1. Commissioned loincloth artifacts (wearable, shown on the portrait)
How: vanilla's own route (the Reichskrone does this). A regalia-slot artifact carries a variable; our portrait
modifier shows the matching piece while it is equipped: `any_equipped_character_artifact = { has_variable = ... }`.
It is inherited like any artifact, so it becomes a dynasty heirloom by itself. Icon rendered from Blender.

- **Decision: Commission a Ceremonial Loincloth** (S). Adults of loincloth cultures (and anyone who has "gone
  native", below). Pick a style and a grade (rough / fine / masterwork), pay gold by grade and tier.
  ~3–6 months later the weaver's event: quality from stewardship + luck; rare outcomes: masterpiece, botched
  dye, weaver flees with the gold, a rival tries to buy it first.
- Styles (each = one artifact, culture-themed textures):
  1. **Champion's Apron** (M) — Tamrielic keshō-mawashi: ankle-long embroidered front apron, gold fringe.
     Usually *gifted by patrons* (event: a vassal sponsors your champion/knight after a tournament win).
  2. **Feather Girdle of the Ancestors** (T on royal girdle, later M) — after Līloa's kāʻei: red-and-gold
     feather sash with rows of teeth; each heir who wears it at succession adds a row (variable → texture tier).
  3. **Briarheart Girdle** (T) — Reach: briar-wrapped belt, hagraven feathers, bear/elk/wolf/raven tooling.
  4. **Hist-Amber Wrap** (T) — Argonian: woven grass cloth, Hist-resin beads, tortoise-shell plaques.
  5. **Green Pact Bone Apron** (T) — Bosmer: bone and beetle-shell beads, no wood or plant fibre.
  6. **Ancestor-Ash Tassets** (T) — Ashlander: netch leather, enamelled chitin tassets, tribal colours.
  7. **Mane's Moon Silk** (T) — Khajiit: fine silk sash with the two moons, gold thread.
  8. **Malacath's Iron Fauld** (T on armoured skirt) — Orc: forged iron lames, stronghold sigil.
- Artifact upkeep events (S): moth damage / repair, theft at a feast, a thief caught wearing it.

## 2. New looks worn automatically (existing triggers decide who)
- **Wrestler's Belt** (M) — mawashi-style thick belt; tourney wrestlers, duellists (has_trait_xp tourney track).
- **Festival White Wrap** (T) — plain white wrap while at a feast or festival activity.
- **Wedding Wrap** (T) — fine decorated wrap at one's own wedding activity.
- **Mourning Wrap** (T) — dark, plain, for a while after a close relative dies (modifier from an event, S).
- **Hunter's Loincloth** (M) — belt pouches + knife sheath; on hunts, Master of the Hunt, hunter traits.
- **Ragged Loincloth** (T, alpha tears) — prisoners, beggars, hermits, the destitute.
- **Priest's Sacred Apron** (M, long aprons) — shamans, Hist-tenders, hagraven-touched, court chaplains.
- **Elder's Long Wrap** (T or small M) — age 60+.
- **Sailor's Malo** (T) — admirals, coastal courtiers at sea / on a fleet.
- **Werewolf's Tatters** (T) — EK2 lycanthropes in human form: claw-torn hide.
- **Victor's Sash** (M, one sash) — for a year after winning a tournament or duel.
- **Holy-Order Colours** (T) — war loincloth in the order's colours, for holy-order members.
- **Cowrie War Belt** (T on trophy belt) — Naga-style: shells grow with *battles won* (S counter), not prowess.

## 3. Events (S)
- **First Loincloth** — rite of passage at 14 for loincloth-culture children: a parent gives the first warrior
  wrap; choose the clan mark (trait xp / opinion); it stays as the plain coming-of-age piece.
- **A Gift of Cloth** — after a tournament win a patron sends a Champion's Apron (artifact).
- **Trophies for the Belt** — after a won battle a warrior asks to add trophies → counter → belt tier.
- **The Tie Snaps** — comic feast mishap; laugh it off (prestige), storm out (stress), blame the weaver.
- **Sumptuary Petition** — weavers ask to reserve fine cloth for nobles; enforce / relax / tax it.
- **Scandalised Envoy** — a foreign dignitary objects to court dress: dress foreign or proudly.
- **Hist Sap Blessing** (Argonian) — steep the loincloth in Hist sap; piety, chance the cloth is ruined.
- **Hircine's Night** (Reach/werewolf) — a transformation shreds the loincloth → tatters for a while.
- **Cold Snap** — a courtier is freezing; give them hide leggings (opinion).
- **Heirloom at Investiture** — the new ruler wears the dynasty girdle at succession → legitimacy, adds a row.

## 4. Decisions (S)
- **Commission a Ceremonial Loincloth** (above).
- **Go Native** — a non-loincloth-culture ruler adopts loincloth court dress (flag; toggle back any time).
- **Proclaim a Loincloth Festival** — court wears festival wraps for a season; opinion with loincloth courtiers.

## 5. Game rules (only if wanted)
Loincloth frequency, nobles wearing them, war looks on/off, artifacts/events on/off.

## Sources (short)
Wikipedia "Loincloth"; tastesofhistory.co.uk (shendyt, subligaculum, maxtlatl); earth-cloth (fundoshi kinds);
UESP Reachmen/Argonian/Bosmer/Ashlander motif pages; CK3 wiki "Artifact modding"; Bishop Museum "Kāʻei kapu o
Līloa"; Japan Times / the-sumo.com on keshō-mawashi; mexicolore.co.uk on Aztec reward capes; vanilla
`portrait_reichskrone_trigger` (00_clothing_triggers.txt) for the equipped-artifact portrait route.

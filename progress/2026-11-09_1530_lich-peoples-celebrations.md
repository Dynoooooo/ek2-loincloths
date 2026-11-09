# Lich pieces, four new loincloth peoples, their celebrations, Go Native background

**Done** (built and looked at in Blender.app, both bodies; ck3-tiger clean apart from EK2 noise; not yet seen in game)
- Research (Exa, 14 searches): see source/RESEARCH_lich_peoples.md.
- **Fix (important):** decisions, events, on_actions and the Loincloth Maker position tested culture with EK2's
  portrait_ek_*_clothing_trigger, which needs scope:culture (portraits only), so none could have fired in game. Now
  ek2lc_loincloth_people_trigger / ek2lc_native_culture_trigger test `culture = { has_clothing_gfx = ... }`.
- Go Native event background: the user's image (common/event_backgrounds/ek2lc_event_backgrounds.txt).
- **16 lich pieces**, all new meshes (bone bead nets, tumi backflaps with rattles, soul gems, the Revenant moon, bonemold,
  faience bead net, vertebra cords, teeth and knucklebones, defaced tabard). Liches get them through the lich tag
  (accessory draws lich_<kind>); barbershop rows added. Liches never get wraps (rule) and keep their burial loincloth.
- **Four new peoples**, each with everyday / ruler / warrior / celebration looks (16 new meshes per body; women's carry
  a chest piece): giants (ek_giant; EK2's giantish body shape added to the build), Keptu (ek_nedic_keptu), Old Nedes
  (ek_nedic_old), Yokudans (ek_yokudan; pleated kilt). Own gene gene_ek2lc_people, group ek2lc_peoples, tag
  ek2lc_people (hides the fig leaf; no older extras drawn on them). Frequency and nobles game rules apply.
- **Celebrations** (own decision and events each, no shared framework): Gathering at the Stones (giants), Bloodroot Hunt
  (Keptu), Watch of the Celestials (Nedes), Drigh R'Zimb (Yokudans). While the modifier lasts, the ruler and court wear
  the celebration look.

**Problems and fixes**: ray misses near the armpits made wide chest plates (now filled from neighbours; deltoid/sleeve
bones count as arm); new pieces use a 6x6 atlas; a script step once wiped the modifiers and decisions files (restored
from git and re-appended: 8 decisions, 38 modifiers).

**Next step**: in game: a giant, Keptu, Nede and Yokudan character (barbershop row "Peoples' Loincloths"); take each
celebration decision; a lich with regalia equipped. Regalia and the Loincloth Maker are not offered to the new peoples yet.

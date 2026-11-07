# Children's tunic and wrap skirt, cold-weather layers, children's charms (built, seen in game)

**Done** (Claude Code; this commit). The user asked for all four after the history of tribal children's dress.
- **Wrap skirt** (`SKIRT` in `build_reach_hide.py`): the cord belt plus four hide panels round the hips, tucked under the belt, hanging like the flaps to 4 cm above the knee. Each panel samples a flap's area of the plain hide texture (inset 0.012, else light seams), so every culture's colours, painted band and fringed hem come with it. Faces wound explicitly (no side rims: their smoothing drew light lines).
- **Tunic** (`TUNIC`): the same skirt and belt plus the torso's skin lifted 0.3 cm (no arms), plain hide from the flaps' upper area. Sets tag `ek2lc_tunic`; every chest band draws nothing under it.
- **Leggings** (`LEGG`, set `ek2lc_leggings_01`): each leg's skin lifted 0.3 cm, from 2 cm above the ankle to the thigh (high outside, low inside). Lacing on the outer seam, a quillwork band under the knee.
- **Fur cloak**: the emperor's mantle mesh with its own fur texture (`ek2lc_robe_01`), written with `write_asset` only. Sets `ek2lc_robe`; the mantle hides it, it hides the shoulder guard.
- **Charms** (`CHARM`, set `ek2lc_charm_01`): at 55° each side (where adults' trophy belt hangs), 1.6× trophy size. Right: quill wrap, two cowries, tassel. Left: quill wrap, tooth, tassel. Bound with `leg_bind`; pushed out to clear the loincloth, skirt, tunic and leggings by 0.3 cm on every shape.
- Lich versions of leggings, cloak and charms (blackened); lich and per-culture skirts and tunics come from `KINDS`.
- Scripts (`gen_script_files.py`): skirt and tunic are `LATE` kinds of `gene_ek2lc_loincloth`, appended after every old template, so saves are unchanged.
  - Dress rules: tunic for commoner children 4–6; wrap skirt plus band for commoner girls 7–13; the loincloth from 7 (boys) and 14 (women).
  - New extras (rules now carry their own age):
    - leggings (4+, `ek2lc_cold_trigger`: Skyrim/Reach regions, winter, tundra, taiga, mountains);
    - fur cloak (4+, `ek2lc_winter_trigger`: winter in Skyrim/Reach, harsh winter, tundra);
    - charms (4–13, hidden under a ruler's girdle).
- In game (one launch, Aldrydd, September):
  - 5-year-old courtier Maira in the tunic.
  - 9-year-old courtier Sinead: DNA Modifiers list "Reach Hide Wrap Skirt" plus "Reach Hide Chest Band".
  - Aldrydd: leggings by default (the Reach), fur cloak and Orcish wrap skirt picked in the barbershop (`progress/screens/cold_layers_skirt_ingame.jpg`).
  - New barbershop rows are named (Leggings, Fur Cloak, Charms). error.log: nothing from our files.
- Previews: `source/preview/preview_layers_m.png`, `preview_layers_f.png` (adult with leggings and cloak; child in tunic; child in skirt).

**Problems and notes**
- A ruler's own children are nobility to EK2 (`portrait_commoner_trigger` excludes high nobles), so they keep EK2 clothes, as before. Test children: lowborn courtiers (`create_character` with `employer = root`, no `location`, no `father`).
- The tunic's neckline follows the body's triangles, so it's a little ragged. Points inside the body on the fat, muscular and dwarf shapes are near the armpits; children (infant shape) are clear.
- Typing into CK3 via computer use was refused once (focus check); scroll dropdowns instead.

**Next step**
- The user looks in game; cold layers on a winter date not seen (the test date was September).

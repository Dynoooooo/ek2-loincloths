# Step 5: Ashlander, Bosmer, Argonian and Khajiit loincloths (seen in game)

**Done** (commit: the one that adds this file)
- Every Reach piece now has a culture version for Ashlanders, Bosmer, Argonians and Khajiit (Anequina and Pellitine): same meshes, own diffuse texture (normal and properties maps are the Reach ones), own barbershop names.
  - Palettes and names: `source/cultures.py`. Ashlander netch leather, rust and ochre, chitin lames, chitin-and-glass trim, stepped band. Bosmer hide, greens, horn and amber, leaf band. Argonian olive hide, turquoise, Hist amber and jade, scale-plated lames, diamond-scale band. Khajiit sand cotton, saffron and purple, gold and moonstone, crescent-moon band.
  - Textures: `build_reach_hide.py` now reads every colour through `K(r, g, b)` and `set_culture(palette)`; the Reach output is byte-identical. Culture diffuse PNGs go to the ignored `source/textures/cultures/`.
- Who wears them: EK2's clothing styles `ek_ashlander` (also used by EK2 for Chimer, Chimeri-Quey, Cantemiric, Shinathi), `ek_bosmeri`, `ek_argonian`, `ek_anequinan` + `ek_pellitinian`. Same rules as the Reach: commoners always, war roles, best fighters, rulers and spouses two in three, four tiers.
- Argonian women commoners: while "Show nudity" is on, one in three goes bare-chested (`should_show_nudity` works in portrait weights). Off: always the chest band.
- All pieces got blend shapes for EK2's beast bodies: `bs_khajiit_body`, `argonian_digitigrade_bs` (every Argonian), `khajiit_digitigrade_bs` (Lilmothiit). Read from EK2's files at build time, never copied.
- Game script files are written by `source/tools/gen_script_files.py` (genes, accessories, who-wears-what, barbershop, names). Edit `cultures.py`, rerun it; add cultures only at the end (template indices).
- In game: an Argonian woman, a Khajiit man, an Ashlander woman and a Bosmer man all showed their culture's pieces. Tails come out over the top of the back flap, which reads as a tail hole. error.log: nothing about our files.

**In progress**
- Nothing half-made.

**Next step**
- Ask the user: verdict on the four cultures. Then: other loincloth cultures from the brief (orcs, goblins, Kothringi, Lilmothiit), or step 6 (kids).

**Problems and workarounds**
- Turning the model in the barbershop: hover it, then click the arrows under its feet (a left-drag pans the camera instead).
- Known, not fixed: with "Show nudity" off, a sliver of the vanilla fig leaf shows from the side (between the pouch and the front flap), on every culture incl. the Reach; front views hide it. On Argonian women (the fig leaf doesn't follow EK2's digitigrade shape) more of it shows from the side. Tried a 9-column pouch that rounds over the fig leaf: no gain in a side-ray test, and new poke-through on the dwarf shape, so reverted. A real fix would keep the loincloth's front from moving back on EK2 shapes, or wrap the front flap's sides back.
- Lilmothiit digitigrade shape: 6 (men) / 11 (women) loincloth points up to 0.5 cm under the skin. Not fixed (Lilmothiit not done yet).
- ck3-tiger can't see EK2's triggers; its `portrait_ek_*_clothing_trigger` errors are noise.

**How to test**
- As before. New characters by culture: `effect create_character = { age = 26 gender_female_chance = 100 culture = culture:hleel faith = root.faith location = root.capital_province save_scope_as = a } set_global_variable = { name = a value = scope:a }`, then `effect set_player_character = global_var:a`. Culture keys used: hleel (Argonian), anequinan (Khajiit), ashlander, silvenari (Bosmer).

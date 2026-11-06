# Step 5: Orc, Goblin, Kothringi and Lilmothiit loincloths (seen in game)

**Done** (commit: the one that adds this file)
- Every piece now has Orc, Goblin, Kothringi and Lilmothiit versions: own diffuse textures and barbershop names, shared meshes and Reach normal/properties maps.
  - Orc: dark leather, iron plates and trim, ivory tusks, rust-red marks. Goblin: scavenged hide, rag colours, bone, muted feathers.
  - Kothringi: reed-cloth, swamp greens, silver and river pearls. Lilmothiit: woven fibre, cream shells, turquoise beads and orange accents.
- Palettes/names were appended to `source/cultures.py`; earlier gene indices are unchanged. Textures/assets come from `build_reach_hide.py`; all game scripts were regenerated with `source/tools/gen_script_files.py`, not hand-edited.
- EK2 clothing inputs: `ek_orc`, `ek_goblin`, `ek_nedic_south` (Kothringi and Horwalli share it), `ek_lilmothiit`. Same commoner, war-role, best-fighter, ruler/spouse and four-tier rules as the earlier cultures.
- Adult Kothringi and Lilmothiit women commoners use the Argonian nudity rule: one in three bare-chested only with `should_show_nudity = yes`; off always gives the chest band. Orc and Goblin women always get the band.
- EK2 has no separate Orc/Goblin body blendshape meshes. Their build/weight uses standard body genes; Goblin shortness uses `gene_height` scaling, which the skinned pieces already follow.
- Fixed all 6 male / 11 female Lilmothiit digitigrade strip points. Projected them outside the folded groin; the build now asserts no loincloth points remain inside on `khadigi`. Minimum clearance: men 0.07 cm, women 0.05 cm.
- Checksums: every existing Reach texture and every other mesh is byte-identical. Only the two loincloth `bs_khadigi.mesh` files changed; updated build `.blend` sources were saved.
- Seen in one test launch: Orc woman (also selected the iron-plated skirt), Goblin man, Kothringi woman with her chest band, Lilmothiit man on the fox/digitigrade body. Screens: `progress/screens/orc.png`, `goblin.png`, `kothringi.png`, `lilmothiit.png` (all 800 px wide).
- CK3 stopped and the user's settings, presets and saves restored. The test helper now signals specific process IDs on shutdown.

**In progress**
- Nothing half-made. The nudity-on distribution uses the existing Argonian generator logic; it was not separately sampled in game tonight.

**Next step**
- fig-leaf side fix, then kids

**Problems and workarounds**
- No game errors referring to the new assets/scripts. Seven old `ek2lc_*` game-rule references in the user's saved preset produce startup warnings; the preset was restored unchanged.
- ck3-tiger is older than this CK3 version and cannot resolve EK2 clothing triggers; its trigger errors and two vanilla camp-law errors are noise. Clausewitz workspace setup was unavailable in this non-interactive run.
- Existing dwarf diagnostic: two loincloth points inside on each body, up to 0.18 cm (unchanged). The fig-leaf side sliver is also unchanged and out of scope here.
- Real barbershop clicks need CK3 frontmost; keys can target its PID. Close an edited barbershop view with Confirm to discard, before sending console commands.

**How to test**
- `bash source/tools/ck3_test.sh start`, then `bash source/tools/ck3_test.sh wait`; always finish with `bash source/tools/ck3_test.sh stop`.
- Use the previous progress note's `create_character` / `set_player_character` effects. Culture keys: `main_orc`, `goblin`, `kothringi`, `lilmothiit`; female chance 100 for Orc/Kothringi, 0 for Goblin/Lilmothiit. Optional explicit fox ethnicity: `ethnicity = race_lilmothiit`.
- Open F1, hover the portrait, click its brush; scroll Appearance down to Loincloth, Chest Piece, Girdle and Mantle. Orc iron plates are the "Orcish Iron-Plated Strip Skirt" girdle choice.
- Rebuild male then female using the command in `source/build_reach_hide.py`'s header; run `python3 source/tools/gen_script_files.py` after palette/name changes.

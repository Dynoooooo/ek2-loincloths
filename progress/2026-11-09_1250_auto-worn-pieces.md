# Four new auto-worn pieces (new meshes, own textures)

**Done** (built and looked at in Blender, both sexes; not yet seen in game)
- Wrestler's Belt with Cords (gene_ek2lc_wrestler): thick indigo silk belt, back knot, 15 stiff cords in front.
  Who: 16+, a recent tournament wrestling win, or tourney_participant foot xp >= 50 with prowess 12+.
- Hunter's Pouch and Knife (gene_ek2lc_hunter): strap, pouch on the right hip, antler-handled knife on the left, two feathers.
  Who: 14+, lifestyle_hunter, Master of the Hunt, or on a hunt activity.
- Sacred Aprons with Amulet (gene_ek2lc_priest): rope belt, knee-long front apron with a sacred tree, back apron, amulet, tassels.
  Who: 16+, court chaplain, devoted, lifestyle_mystic or theologian.
- Victor's Sash (gene_ek2lc_victor): crimson-and-gold sash over the right shoulder, knotted at the left waist.
  Who: 14+, any tournament_<duel|melee|wrestling|joust|archery|horse_race>_winner_modifier.
- All only over our loincloths (culture rule, as the other extras). Hiding: girdles/regalia hide belt, hunter, priest;
  belt hides trophies and hunting gear; aprons hide trophies, camp wrap and hunting gear; mantle/fur cloak hide the sash.
  Barbershop rows for each. Recolourable (sash in the cloak block, the rest legwear). No lich versions.

**Built with**: source/build_regalia.py (keys wrestler_belt, hunter_gear, priest_apron, victor_sash; rebuild one with
`start("male", "female", script="build_regalia.py", args=["victor_sash"])`), then gen_script_files.py and make_colour.py.

**Problems and fixes**
- The body mesh is open at the neck out to ~12.5 cm (the head mesh covers it): the sash crosses the shoulder at x ~16.
- Rays skip arm vertices (hands hang by the hips), so on the shoulder the sash uses the full body, arms included.
- Remaining clearance: sash < 0.7 cm under the waist knot, belts < 0.2 cm at the lower back rim. Hidden.

**Next step**
- In game, as a Reach character: give the modifiers/traits (console `add_trait lifestyle_hunter`, etc.) and check each piece,
  then the regalia (see 2026-11-09_1126 note). At most 3 launches.
- Later ideas still open (source/IDEAS_expansion.md): festival/wedding/mourning wraps, werewolf tatters, cowrie war belt, Go Native.

**Validation**: ck3-tiger (our mod alone, `--config /dev/null`): nothing in the new files; the rest is the known EK2 noise.

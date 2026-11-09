# Loincloth Maker, the rest of the ideas list, game rules

**Done** (built and looked at in Blender, both sexes; ck3-tiger clean apart from EK2 noise; not yet seen in game)
- **Loincloth Maker** (user: "a custom role ... with specific skill levels"): trait in three ranks
  (`ek2lc_loincloth_maker_1/2/3`: Apprentice, Journeyman, Master; group `ek2lc_loincloth_maker`) and a court position
  `ek2lc_loincloth_maker_court_position` (aptitude: stewardship x2, learning, rank +15/+30/+45, patient, diligent, lazy).
  Own icons rendered in Blender (wedding wrap + bone needle on bronze/silver/gold badges; 70x70 position icon).
  A court Loincloth Maker: commissions 15% cheaper (Master 30%), quicker, finer, the weaver rarely flees; the maker gains
  XP per work (rank 2 at 3, rank 3 at 8). Appointment gives rank 1. Yearly event "A Gift for the Needle" finds one.
- **Wraps replacing the loincloth** (gene_ek2lc_wrap, own meshes inside the loincloth's room so girdles/regalia still fit;
  the loincloth draws nothing under tag ek2lc_wrap): ragged (prisoners, lunatics) > mourning (a year after a close
  relative's death, on_death) > wedding (own wedding) > festival white (feast/festival activity or Loincloth Festival) >
  werewolf tatters (lycan_character) > sailor's malo (at sea) > elder's long wrap (60+, not rulers).
- **Cowrie war belt** in 3 tiers by var:ek2lc_battles_won (3/6/10); hides the trophy belt; hidden under royal girdles.
- **Holy-order tabard** for holy-order governments and their courts.
- Decisions: Proclaim a Loincloth Festival (90 days), Go Native (pick a people; flag ek2lc_native_<culture> makes the
  generator's culture tests match), Return to Your Own Dress. Events: the dye ran, regalia stolen at a feast.
- Game rules: frequency (always/often/sometimes), nobles on/off, war looks on/off, events on/off.

**Files**: build_regalia.py (new keys), tools/render_maker_icons.py, common/traits, common/court_positions/types,
common/game_rules, common/scripted_triggers/ek2lc_wrap_triggers.txt; gen_script_files.py (genes, tags, rules, flags).

**Next step**: in game (user looks): appoint a Loincloth Maker, commission (console `event ek2lc_regalia.0010` to skip the
wait), check the trait icons; give `effect add_character_modifier = ek2lc_mourning_modifier` to see a wrap; check the
game rules screen.

**Problems**: court position hooks run with the holder in scope:employee (not root). Body mesh is open at the neck to ~12.5 cm.

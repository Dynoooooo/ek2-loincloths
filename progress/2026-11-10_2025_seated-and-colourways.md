# Throne drape for every hanging piece; 61 culture colourways remade (75 left)

**Done** (commits f15d6f4 and the one with this note; none seen in game yet: CK3 needs Steam running)
- Throne: vanilla's `throne_room_ruler` animation switches on `bs_body_seated`; every piece with hanging parts now
  has its own `_bs_seated` shape (`source/maya/seated.py`: proxy cloth drape in throneRoom_ruler2, legs widened as
  support, a seat, a per-vertex push out of the body). Vertices inside the seated body, all pieces: 21,594 -> 5,055;
  the aprons now lie on the lap and fall over the knees instead of standing out like boards.
- Colourways: 61 of the 136 culture pieces that reused a Reach mesh have their own Meshy T2.5 mesh and texture:
  hide, fine and royal loincloths, the three chest bands and the war belt for Argonian, Ashlander, Bosmer, Khajiit,
  Orc, goblin, Kothringi and Lilmothiit; Reach fine and royal loincloths and bands; the Reach fur robe.
  Designs: `source/meshy/culture_prompts.json`; build: `source/maya/colourway_remake.py`.
- Meshy: 1,242 -> ~65 credits (incl. ~440 permanent credits that appeared mid-session).

**Not closed**
- Kneeling clipping (2-5 cm, mostly the belt/apron top at the hip crease of the raised thigh): weight blends
  (`wfix.py`, many variants) halve it in kneel1 but make cross-legged worse and change little by eye; no vanilla
  pose-shape hook exists for kneels. Not applied.
- 75 colourways left: armour, duke, king, emperor, mantle, skirt, tunic, grave, grave band for the 8 cultures;
  Reach emperor, grave, grave band. ~1,800 credits at T2.5 (after the Dec 10 reset: add them to a `batch3` in
  culture_prompts.json, run the concept/3D calls, `cr.run(keys)`, `make_colour.py`).

**Next step**: with the user's OK to start Steam: `BG=1 OPEN=1 bash source/tools/ck3_test.sh start`; check a seated
ruler (barbershop Scene tab, Sit on Throne), the women's leggings seated, a lich, and a few colourway pieces; grep
error.log for ek2lc. When the user is away: the 37 events and 8 decisions.

**Problems**: GPT Image draws rayed suns into "patterned" cloth unless told the pattern and "no suns, no rays".

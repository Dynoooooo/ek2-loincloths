# WIP: pose clipping and culture colourways (stopped at the usage limit)

**Done**: nothing new in game files. Tools only (commit below).
- Colourways: 136 pieces need their own mesh (8 cultures x 16 kinds + 7 Reach tiers + fur robe). User OK'd Meshy T2.5
  (smart topology 15 + GPT concept 9 = 24 credits each; 3,264 total; ~51 now with 1,242 left, rest after Dec 10).
  Designs: `source/meshy/culture_prompts.json` (lore notes, per-culture materials, per-kind templates, `batch1` = 45
  pieces); prompts: `python3 -I source/tools/culture_prompt.py batch1`. Test piece argonian_hide: concept done
  (source/meshy/argonian_hide/concept.png), T2.5 3D task 01a1c7a6-7a47-7238-82db-5fd19efc0bc7 (download, build with
  mb.build band=False over=("leggings",) after mlike.retarget of both assets, compare with a meshy-7.1 piece).
- Clipping, findings: kneel1 clipping is the belt/apron top at the hip crease (rest y 88-95, no chain weight), not
  the hanging part; cross-legged is the hem at the knees. `wfix.py` (weight blend chain<->leg/skin, coarse grid)
  only halves it at best and moves the standing look 2-3 cm: not applied. Throne: vanilla's trick is the
  `bs_body_seated` shape (gene_seated, added by the throne_room_ruler animation); `seated.py` makes one by a proxy
  cloth drape, but the drape still drops the hanging part ~30 cm (median): tethers/edge solve need work. Not written.

**Next step**: fix seated.drape (limit the drop: e.g. stop free nodes at the lap by casting down to the body first,
or many more edge iterations), check visually with cs.set_shape("bs_body_seated", 1) in ruler2, then run it for
every hanging piece; then the colourway batch1.

**Problems**: Exa hit its free rate limit mid-research (Bosmer/Orc/goblin from known lore + UESP fetches).

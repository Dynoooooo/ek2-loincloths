# First Meshy piece: the festival wrap

**Done** (built and looked at in Blender.app, both bodies; not yet seen in game)
- Design picture with GPT Image 2.5 Sunburst on Meshy (the Meshy MCP doesn't list 2.6 yet; the API has it), then
  image to 3D with Smart Topology meshy-t2.5, 4,000 triangles, texture meshy-n1. 24 credits (76 left, reset Dec 1).
  Sources: source/meshy/festival_wrap/ (concept.png, model.glb, model_base_color.png).
- New fit step in build_regalia.py (`meshy_piece`): the garment's top ring goes on the belt line, scaled per angle to
  each body shape's outline; then a smooth push field (angle x height) moves it clear of the outermost body and
  leggings above, so cloth hangs from the widest part and layers keep their order. Weights from the skin, blending
  into the skirt chains as it hangs. Every body shape gets its own fit (blendshapes); no poke-through except the strip
  by under 1 mm on the dwarf and infant shapes.
- The wraps' strip between the legs is added under it (the apron alone left the groin bare from the side), in a
  painted cell under Meshy's texture (the set is 2048: Meshy's image on top, one row of our cells below).
- Removed the procedural festival wrap.

**Fix (make_colour.py)**: one random stream was shared by every texture set in name order, so changing one set (the
festival wrap's texture grew to 2048) shifted the colour groups of borderline sets after it (goblin, Kothringi, lich,
orc, Reach). Each set now seeds its own stream from its name; 13 sets were regrouped once (default-look error
0.3-4%), and a rerun changes nothing.

**Next step**: in game, proclaim the festival. Next Meshy pieces: same flow (`meshy_piece(pc, at, key)`).

# Festival wrap remade with Meshy (the first one looked like papier-mâché)

**Why the first one failed**: the concept's ghost-mannequin shot had a stiff grey "bucket" inside the belt, so Meshy
built a solid pot-shaped shell; 4,000 triangles made the folds lumpy; the meshy-n1 texture was hundreds of tiny
islands with baked shading; the hip streamers were paper.

**Done** (built for both bodies and looked at in Blender.app; not yet seen in game)
- New concept (GPT Image 2.5 Sunburst, 2:3, background removed): open rope ring knotted at the back, hollow inside,
  open sides, swaying linen front apron with a ring sun (hollow ring, eight separate rays), stripes and fringe, wider
  back flap, three cloth tassels per hip. A first try (9 credits) was dropped: flat banner apron and a rayed sun too
  close to the Rising Sun flag.
- Image to 3D: meshy-t2.5 smart topology, 6,000 target (5,595 faces after the fit), texture meshy-7 with a texture
  prompt asking for flat colours. Files replaced in source/meshy/festival_wrap/ (old ones are in git).
- Credits: 9 + 9 + 15 = 33 (52 left, reset Dec 1).
- Build unchanged (`meshy_piece(..., gap=1.0)` plus the linen strip): BUILD OK male and female.

**Seen in Blender**: clean cloth look, belt sits on the hip line, apron in front, flap at the back. Small grey smudge
right of the sun on the front apron (Meshy texture). Meshy also put a sun on the back flap.

**User's verdict**: "pretty damn good", except the rope was bulkier at the back and one hip had two tassels, the other
three. Fixed in build_regalia.py (BUILD OK male and female, looked at in Blender):
- `meshy_fit(parts=...)`: the fit stretched every vertex out by the body's width per angle, so the rope got thickest
  over the buttocks. Now the rope (and knot, tassel tops) keeps its inner edge on the body but its own thickness, scaled
  like its height; small parts hanging from it move with their top; panel tops ease from the rope into the plain fit.
- `meshy_symmetric` (`meshy_piece(..., symmetric=True)`): Meshy's three tassels (9 parts) mirrored over the other hip's
  two (6 parts). Meshy's own geometry and UVs, mirrored; nothing modelled by hand.

**Next step**: in game, proclaim the festival and look from the front and back.

# Clipping fix: flaps tucked under the belt; check file fixed

**Done** (commit: the one that adds this file)
- The clipping the user found in Blender (belly through the front flap's top, belt through the back flap's fold) came mostly from a bug in the .blend: in Blender 5.2 new shape keys start at 1.0, so all five body shapes were on at once on body and loincloth. Keys are now saved at 0, and in the check file the loincloth's shape keys follow the body's (drivers).
- Design change: the flaps now tuck under the belt (top at BELT_Z + 0.9, between belt and skin) instead of folding over it. The belt is thicker (outer 1.4 cm, middle 1.9 cm off the skin). The top rows of the flaps follow the skin behind them; the lower rows blend into stiff-apron weights. Weights are mirror-symmetric.
- Checked in Blender over the callous idle (every 10 frames) for normal, fat, gaunt, muscular, old, dwarf and fat+old: nothing sinks into the body except the hidden dwarf strip (0.37 cm). Where the front flap comes out from under the belt they overlap by up to 0.5 cm (reads as tucking). On fat and old bodies the flap's top shows a little above the belt.
- Not yet seen in game: this piece has used its 3 launches; ask the user before a 4th. `source/preview/ingame_*.jpg` still show the previous version (flap folded over the belt).

**In progress**
- Nothing half-made. The user is checking `source/reach_hide_m_check.blend` in Blender.

**Next step**
- The user's verdict. A game launch only if they ask. Then step 2 (women's loincloth + chest band) after their OK.

**Decisions the user made**
- "There are some of the sites of clipping I found. Please fix."

**Problems and workarounds**
- Blender 5.2: `shape_key_add` creates keys at value 1.0. Always set them to 0 before saving.
- To look at a body shape in the check file, set it on the body only; the loincloth follows.

**How to test**
- In game: as in the earlier progress files (`ck3_test.sh`, temporary flag hook, barbershop).
- In Blender: `source/tools/make_check_blend.py` makes the check file (callous idle on the rig).

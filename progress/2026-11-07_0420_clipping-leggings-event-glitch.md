# Clipping fixed in Blender, new leggings, loincloth-only rule, King Falk's event glitch

**Done** (Claude Code, in the Blender app as the user asked; this commit)
- Blender inspection (`source/tools/inspect_setup.py`, `inspect_scan.py`, scene `source/inspect_current.blend`): bodies + every exported piece on the real rigs, 13 portrait animations (idle, events, throne). Builds now run inside the app (`source/tools/build_in_app.py`; no headless).
- Hanging pieces ride the skeleton's skirt bones (`skirt_weights()`), as vanilla robes do: flaps, royal aprons, kids' wrap skirt/tunic; strip skirt and camp-wrap tails half thigh, half skirt bone. Thighs/leggings no longer cut through flaps in idles; seated, the flap and apron drape over the lap.
- Leggings rebuilt (built first; every piece hangs clear of them): a two-layer hide tube, snug thigh, loose shin, flared cuff, slanted top (low inside, rising to the outer thigh), rolled stitched hem; body corners that showed through as pale diamonds lifted clear. New texture: dark smoked hide, red/bone quilled strip down the outer side, knee band, notched cuff, folds in the normal map. In game they read clearly on Yashnag.
- Strip skirt no longer dips into the rope belt (each row checks down to the next); same for aprons, flaps, tails.
- Kids' wrap skirt: A-line like vanilla dresses (fitted at the sides), no slits between panels.
- Script: every person 4+ of a loincloth culture always gets one of our looks (no random "no loincloth"; rulers were 2 in 3). New: non-ruling nobles, and knights/court officers at peace, wear the fine loincloth; a ruler's children get the children's dress. Wearers get no EK2 outfit, legwear, cloak, headgear, veil, crown or hood.
- King Falk's glitch (Yashnag's start event): filmed at ~30 fps; with the mod he showed one frame in a placeholder look and pose. Bisected over 12 launches: caused by our "no X" pieces (an entity without a mesh on every character). They are empty now, and extras go only to the loincloth cultures. Two runs since: clean.

**Not changeable without editing EK2**: Yashnag keeps a crown and fur mantle: EK2's history gives him a scripted portrait override (works like a barbershop pick). The player can remove them in the barbershop.

**Known**: hands still touch the leggings/skirt sides in idles, as with vanilla clothes. Kneeling (throne room) still pushes thighs into some pieces. Women's emotion animations won't import in Blender (exporter bug), so women were checked in idle, callous and throne poses.

**Next step**
- The user looks in game (their own setup with Better Barbershop and Undead Expanded).

**How to test**
- `PLAY=k_falkreath bash source/tools/ck3_test.sh start` (Yashnag; `NOMOD=1` for EK2 alone), `wait`, `stop`. Frames: `source/tools/capture_window.sh <win id> <dir> 28` right after `start` (the event pops up ~9 s in).

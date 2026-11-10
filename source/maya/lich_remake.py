"""2026-11-10: the 22 lich looks that reused a living piece's mesh with a lich texture, remade as their own pieces
from Meshy (source/meshy/lich_*, prompts in source/meshy/lich_prompts.json). Run inside Maya:

    import lich_remake as lr; lr.run()            # or lr.run(["lich_mantle"]) for some
then: mayapy -I source/tools/make_colour.py

Order matters: the leggings first (the loincloths and the tunic are fitted over them), then the loincloths (the
pieces worn over a loincloth are fitted over all three), then the rest.
"""
import mbuild as mb
import mlike as ml

LOIN = ("lich_hide", "lich_fine", "lich_royal")
OVER = LOIN + ("lich_leggings",)
FUR = {"thin": 0.2, "tight": 0.9}

STEPS = [
    ("lich_leggings", lambda log: ml.build_like("lich_leggings", "lich_leggings", "leggings", "legs", log=log)),
    ("lich_hide", lambda log: mb.build("lich_hide", "lich_hide", band=False, over=("lich_leggings",), log=log)),
    ("lich_fine", lambda log: mb.build("lich_fine", "lich_fine", band=False, over=("lich_leggings",), log=log)),
    ("lich_royal", lambda log: mb.build("lich_royal", "lich_royal", band=False, over=("lich_leggings",), log=log)),
    ("lich_skirt", lambda log: mb.build("lich_skirt", "lich_skirt", band=False, over=("lich_leggings",), log=log)),
    ("lich_tunic", lambda log: ml.build_like("lich_tunic", "lich_tunic", "reach_tunic", "torso", over=("lich_leggings",), log=log)),
    ("lich_band", lambda log: ml.build_band("lich_band", "lich_band", top=5.0, bot=-8.5, log=log)),
    ("lich_band_fine", lambda log: ml.build_band("lich_band_fine", "lich_band_fine", top=5.0, bot=-8.5, log=log)),
    ("lich_band_royal", lambda log: ml.build_band("lich_band_royal", "lich_band_royal", top=5.0, bot=-8.5, log=log)),
] + [
    (k, (lambda k: lambda log: mb.build(k, k, band=False, over=OVER, log=log))(k))
    for k in ("lich_war", "lich_armour", "lich_duke", "lich_king", "lich_emperor", "lich_camp_wrap", "lich_kid_charm",
              "lich_trophy_1", "lich_trophy_2", "lich_trophy_3")
] + [
    # capes: Meshy took the three-quarter concept's view as the front; the front opening pointed -12.5 / -5 degrees
    ("lich_mantle", lambda log: ml.build_like("lich_mantle", "lich_mantle", "reach_mantle", "cape",
                                             over=("lich_tunic", "lich_royal"), yaw=12.5, log=log)),
    ("lich_fur_robe", lambda log: ml.build_like("lich_fur_robe", "lich_fur_robe", "reach_mantle", "cape",
                                               over=("lich_tunic", "lich_royal"), yaw=5.0, log=log)),
    ("lich_arena_guard", lambda log: ml.build_like("lich_arena_guard", "lich_arena_guard", "arena_guard", "shoulder",
                                                  over=("lich_tunic",), log=log)),
    # remade earlier (2026-11-10) over the Reach hide the lich loincloth used to share: refitted over the new ones
    ("lich_art_fauld", lambda log: mb.build("lich_art_fauld", "lich_art_fauld", band=False, over=OVER, log=log)),
    ("lich_art_ash", lambda log: mb.build("lich_art_ash", "lich_art_ash", band=False, over=OVER, log=log)),
]


def run(which=None, log=print):
    out = {}
    for k, f in STEPS:
        if which is None or k in which:
            out[k] = f(log)
    return out

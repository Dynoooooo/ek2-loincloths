"""2026-11-10: the culture colourways (Reach meshes with culture textures) remade as their own Meshy pieces
(meshy-t2.5 smart topology + meshy-7 PBR; designs in source/meshy/culture_prompts.json). Run inside Maya:

    import colourway_remake as cr; cr.run(cr.KEYS)       # then mayapy -I source/tools/make_colour.py

Each key is <culture>_<kind> (fur_robe: the Reach fur robe). The .asset files are pointed at their own mesh and
texture set first (mlike.retarget). Loincloths first: the war belts are fitted over the culture's loincloths.
"""
import json
import math
import os
import numpy as np
import ck3scene as cs
import mbuild as mb
import mlike as ml

D = json.load(open(cs.MOD + "/source/meshy/culture_prompts.json"))
KEYS = D["batch1"]
ORDER = ("hide", "fine", "royal", "grave", "skirt", "band", "band_fine", "band_royal", "grave_band", "war", "armour",
         "duke", "king", "emperor", "tunic", "mantle", "fur_robe")


def split(key):
    if key == "fur_robe":
        return "reach", "fur_robe"
    for c in sorted(D["cultures"], key=len, reverse=True):
        if key.startswith(c + "_"):
            return c, key[len(c) + 1:]
    raise KeyError(key)


def _have(base, sex="m"):
    return os.path.exists("%s/ek2lc_%s_%s_01.mesh" % (cs.OUT, sex, base))


def cape_yaw(key):
    """Turn that brings the cape's front opening to the front (largest empty angle at chest height)."""
    V = mb.load(key).V
    y0, y1 = V[:, 1].min(), V[:, 1].max()
    c = (V.min(0) + V.max(0)) / 2
    m = (V[:, 1] > y0 + 0.55 * (y1 - y0)) & (V[:, 1] < y0 + 0.8 * (y1 - y0))
    a = np.degrees(np.arctan2(V[m, 0] - c[0], V[m, 2] - c[2])) % 360
    h = np.histogram(a, bins=72, range=(0, 360))[0] > 0
    best, start = 0, 0
    for s in range(72):
        if h[s]:
            continue
        L = 0
        while L < 72 and not h[(s + L) % 72]:
            L += 1
        if L > best:
            best, start = L, s
    g = ((start + best / 2) * 5 + 180) % 360 - 180
    return -g if best >= 3 else 0.0


def build(key, log=print):
    c, kind = split(key)
    for s in "mf":
        a = "ek2lc_%s_%s_01" % (s, key)
        if os.path.exists("%s/%s.asset" % (cs.OUT, a)):
            ml.retarget(a)
    if kind in ("hide", "fine", "royal", "grave", "skirt"):
        return mb.build(key, key, band=False, over=("leggings",), log=log)
    if kind in ("band", "band_fine", "band_royal", "grave_band"):
        return ml.build_band(key, key, top=5.0, bot=-8.5, log=log)
    if kind in ("war", "armour", "duke", "king", "emperor"):
        over = tuple(b if _have(b) else "reach_hide" for b in ("%s_hide" % c, "%s_fine" % c, "%s_royal" % c))
        over = tuple(dict.fromkeys(over)) + ("leggings",)
        return mb.build(key, key, band=False, over=over, log=log)
    if kind == "tunic":
        return ml.build_like(key, key, "reach_tunic", "torso", over=("leggings",), log=log)
    if kind in ("mantle", "fur_robe"):
        yaw = cape_yaw(key)
        log("YAW %s %.1f" % (key, yaw))
        return ml.build_like(key, key, "reach_mantle", "cape", yaw=yaw, log=log)
    raise KeyError(kind)


def run(keys, log=print):
    import traceback
    keys = sorted(keys, key=lambda k: ORDER.index(split(k)[1]))
    for k in keys:
        if not os.path.exists(os.path.join(mb.MESHY, k, "model.glb")):
            log("SKIP %s (no model yet)" % k)
            continue
        try:
            build(k, log=log)
            log("STEP OK %s" % k)
        except Exception:
            log("STEP ERROR %s %s" % (k, traceback.format_exc()))
    log("DONE")


def run_all_then_seated(keys, log=print):
    """The colourway builds (each gets its seated shape in mbuild.finish), then the seated shape again for every
    other piece (seated.py improved after the first pass)."""
    import seated
    run(keys, log=log)
    built = {"ek2lc_%s_%s_01" % (s, k) for k in keys for s in "mf"}
    seated.run_all(log=log, skip=built)

"""Make every EK2 Loincloths piece recolourable in the barbershop (see source/colour.py).

For each texture set used by an .asset in the model folder:
  - groups the soft parts of its diffuse (hide, cloth, cord, fur, paint: the pixels whose
    properties are the set's plain value) into up to 3 colour groups; the biggest one (the main
    hide or cloth, usually with its cord) goes in mask channel R. Smaller groups (painted bands,
    beads) and shiny parts (bone, teeth, metal, gems) stay out of the mask and keep their colours.
    In CK3 1.20 only channel R took a colour on our pieces in game (G and B stayed white even with
    a picked colour), so USED_GROUPS is 1; raise it if a later patch fixes that;
  - writes the diffuse with the masked group divided by its colour (near-neutral), and a
    16x1 palette holding that colour, so the default look is unchanged and a picked colour
    (barbershop: the swatch beside Clothes, Legwear or Cloak, "Primary Color 1") replaces it;
  - writes the mask, full size like vanilla's (identical masks are shared).
Then writes the variation file and patches every .asset (prefixed entity name, pattern shader,
mask and variation). The patterns are solid (colour channel 1, flat normal, the set's own
properties), so they need no second UV set.

Reads the PNG sources (source/textures, source/textures/cultures), never its own output, so it
can be re-run; run it after build_reach_hide.py. Needs numpy: run it with Blender's Python:
  /Applications/Blender.app/Contents/Resources/5.2/python/bin/python3.13 -I source/tools/make_colour.py
"""
import glob
import hashlib
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
MOD = os.path.dirname(SRC)
sys.path.insert(0, SRC)
import colour  # noqa: E402

MAGICK = "/opt/homebrew/bin/magick"
OUT = os.path.join(MOD, colour.MODEL_DIR)
PAT = os.path.join(MOD, colour.PATTERN_DIR)
TEX = os.path.join(SRC, "textures")
BOM = "﻿"
MAX_GROUPS = 3
USED_GROUPS = 1     # groups that get a mask channel (see above)
MERGE_DIST = 0.035   # chroma distance under which two groups are one colour
MIN_SHARE = 0.01     # smaller groups join the nearest one
PAT_SIZE = 512       # vanilla's pattern texture size (they share texture arrays)


def read_png(path):
    w, h = map(int, subprocess.run([MAGICK, "identify", "-format", "%w %h", path], capture_output=True,
                                   check=True, text=True).stdout.split())
    raw = subprocess.run([MAGICK, path, "-depth", "8", "rgba:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 4).astype(np.float32) / 255.0


def write_dds(arr, path, compression, mips=True):
    """mips: True = full chain, False = none, or a number of extra levels."""
    h, w = arr.shape[:2]
    data = np.clip(np.round(arr * 255.0), 0, 255).astype(np.uint8).tobytes()
    nm = int(np.log2(min(h, w))) if mips is True else int(mips)
    subprocess.run([MAGICK, "-size", "%dx%d" % (w, h), "-depth", "8", "rgba:-", "-define", "dds:compression=" + compression,
                    "-define", "dds:mipmaps=%d" % nm, path], input=data, check=True)


def pyramid(a):
    """Mip levels of a square array, 2x2 box filter down to 1x1."""
    out = [a]
    while out[-1].shape[0] > 1:
        b = out[-1]
        out.append(b.reshape(b.shape[0] // 2, 2, b.shape[1] // 2, 2, -1).mean((1, 3)))
    return out


def write_dds_levels(levels, path, compression):
    """DDS with our own mip levels (ImageMagick's dds:mipmaps=fromlist)."""
    tmp = path + ".levels"
    os.makedirs(tmp, exist_ok=True)
    args = [MAGICK, "-depth", "8"]
    for i, lv in enumerate(levels):
        f = os.path.join(tmp, "%d.rgba" % i)
        open(f, "wb").write(np.clip(np.round(lv * 255.0), 0, 255).astype(np.uint8).tobytes())
        args += ["-size", "%dx%d" % (lv.shape[1], lv.shape[0]), "rgba:" + f]
    subprocess.run(args + ["-define", "dds:compression=" + compression, "-define", "dds:mipmaps=fromlist", path], check=True)
    for i in range(len(levels)):
        os.remove(os.path.join(tmp, "%d.rgba" % i))
    os.rmdir(tmp)


def features(px):
    s = px[:, 0] + px[:, 1] + px[:, 2] + 1e-3
    lum = 0.3 * px[:, 0] + 0.59 * px[:, 1] + 0.11 * px[:, 2]
    return np.stack([px[:, 0] / s, px[:, 1] / s, 0.05 * np.log(lum + 0.02)], 1)


def groups(feat, rng):
    """Up to MAX_GROUPS centroids: k-means (k=5), then merge close or tiny groups."""
    sub = feat[rng.choice(len(feat), min(len(feat), 40000), replace=False)]
    cent = [sub[rng.integers(len(sub))]]
    for _ in range(4):  # k-means++ seeding
        d = np.min(((sub[:, None] - np.array(cent)[None]) ** 2).sum(-1), 1)
        cent.append(sub[rng.choice(len(sub), p=d / d.sum())] if d.sum() > 0 else sub[0])
    cent = np.array(cent)
    for _ in range(30):
        lab = np.argmin(((sub[:, None] - cent[None]) ** 2).sum(-1), 1)
        cent = np.array([sub[lab == k].mean(0) if np.any(lab == k) else cent[k] for k in range(len(cent))])
    lab = np.argmin(((sub[:, None] - cent[None]) ** 2).sum(-1), 1)
    cl = [[cent[k], float(np.mean(lab == k))] for k in range(len(cent)) if np.any(lab == k)]
    while len(cl) > 1:
        pairs = [(np.linalg.norm(cl[i][0][:2] - cl[j][0][:2]), i, j) for i in range(len(cl)) for j in range(i + 1, len(cl))]
        d, i, j = min(pairs)
        small = min(range(len(cl)), key=lambda k: cl[k][1])
        if d < MERGE_DIST:
            pass
        elif cl[small][1] < MIN_SHARE or len(cl) > MAX_GROUPS:
            i = small
            j = min((k for k in range(len(cl)) if k != i), key=lambda k: np.linalg.norm(cl[k][0][:2] - cl[i][0][:2]))
        else:
            break
        wi, wj = cl[i][1], cl[j][1]
        cl[j] = [(cl[i][0] * wi + cl[j][0] * wj) / (wi + wj), wi + wj]
        del cl[i]
    cl.sort(key=lambda c: -c[1])  # biggest group = R ("Primary Color 1")
    return np.array([c[0] for c in cl])


def assets():
    """{asset name: (diffuse set, properties set)} from the .asset files."""
    out = {}
    for p in sorted(glob.glob(os.path.join(OUT, "*.asset"))):
        t = open(p).read()
        out[os.path.basename(p)[:-6]] = (re.search(r'texture_diffuse = "(.+?)_diffuse\.dds"', t).group(1),
                                         re.search(r'texture_specular = "(.+?)_properties\.dds"', t).group(1))
    return out


def main():
    os.makedirs(PAT, exist_ok=True)
    rng = np.random.default_rng(7)
    sets = {}
    for name, (tset, nset) in assets().items():
        sets.setdefault(tset, nset)
    masks, mask_of, props_of, info = {}, {}, {}, []
    for tset, nset in sorted(sets.items()):
        dpath = next(p for p in (os.path.join(TEX, tset + "_diffuse.png"), os.path.join(TEX, "cultures", tset + "_diffuse.png"))
                     if os.path.exists(p))
        dif = read_png(dpath)
        props = read_png(os.path.join(TEX, nset + "_properties.png"))
        base_g = props[..., 1].min()
        soft = props[..., 1] <= base_g + 0.01
        px = dif[soft][:, :3]
        cent = groups(features(px), rng)
        lab_soft = np.argmin(((features(px)[:, None] - cent[None]) ** 2).sum(-1), 1)
        lab = np.full(soft.shape, -1, np.int32)
        lab[soft] = lab_soft
        opaque = dif[..., 3] > 0.5
        refs = []
        for k in range(len(cent)):
            sel = lab == k
            pick = sel & opaque if np.any(sel & opaque) else sel
            refs.append(np.maximum(np.percentile(dif[pick][:, :3], 99.5, axis=0), 0.03))
        refs = refs[:USED_GROUPS]
        m = np.zeros(dif.shape, np.float32)
        for k in range(len(refs)):
            m[..., k] = lab == k
        m[..., 3] = 1.0  # DXT1 reads alpha as 1 anyway; channel A's pattern is the neutral ek2lc_none
        key = hashlib.sha1(np.round(m * 255).astype(np.uint8).tobytes()).hexdigest()
        if key not in masks:
            masks[key] = tset
            write_dds_levels(pyramid(m), os.path.join(OUT, tset + "_masks.dds"), "dxt1")
        mask_of[tset] = masks[key]
        # Divide by exactly what the shader multiplies by: the mask as the game reads it (compressed,
        # for the full-size level), lerping from white to each group's colour in channel order.
        # Done for every mip level separately (the original's mip / that mip's colour), because in
        # portraits the game samples small mips: there, dividing the full size and averaging after
        # left thin unmasked lines (painted zigzags) pale.
        mlev = pyramid(m)
        mlev[0] = read_png(os.path.join(OUT, masks[key] + "_masks.dds") + "[0]")
        levels = []
        for dl, ml in zip(pyramid(dif), mlev):
            col = np.ones(dl.shape[:2] + (3,), np.float32)
            for k, ref in enumerate(refs):
                col += (ref - col) * ml[..., k:k + 1]
            nl = dl.copy()
            nl[..., :3] = np.clip(dl[..., :3] / np.maximum(col, 1e-3), 0, 1)
            levels.append(nl)
        write_dds_levels(levels, os.path.join(OUT, tset + "_diffuse.dds"), "dxt5")
        pal = np.ones((1, 16, 4), np.float32)
        for k, ref in enumerate(refs):
            pal[0, k * 4, :3] = ref
        write_dds(pal, os.path.join(PAT, tset + "_palette.dds"), "none", mips=False)
        a = float(props[soft][:, 3].mean())
        props_of[tset] = (round(float(base_g) * 255), round(a * 255))
        info.append("%s: %d of %d groups coloured %s, soft %.0f%%" % (tset, len(refs), len(cent), " ".join("#%02x%02x%02x" % tuple(int(c * 255) for c in r)
                                                                                  for r in refs), 100 * soft.mean()))

    # solid patterns: colour channel 1 only, flat normal (.ga = 0.5), the set's plain properties with AO 1
    # Same layout as every vanilla pattern texture (they share texture arrays with the character's other
    # pieces): DXT5 512x512; colour masks with 2 mip levels, normal and properties maps with the full chain.
    def solid(rgba, path):
        write_dds(np.broadcast_to(np.array(rgba, np.float32) / 255.0, (PAT_SIZE, PAT_SIZE, 4)).copy(), path, "dxt5",
                  mips=1 if path.endswith("colormask.dds") else True)
    solid((255, 0, 0, 0), os.path.join(PAT, "ek2lc_pattern_colormask.dds"))
    solid((128, 128, 255, 128), os.path.join(PAT, "ek2lc_pattern_normal.dds"))
    out = [BOM + "# EK2 Loincloths: barbershop colours for our pieces (made by source/tools/make_colour.py).\n"
           "# Each texture set's mask channels R/G/B are its colour groups; the palette holds their default colours.\n"
           "# Patterns are solid, so they need no second UV set."]
    for g, a in sorted(set(props_of.values())):
        pt = "ek2lc_solid_g%d_a%d" % (g, a)
        solid((255, g, 0, a), os.path.join(PAT, pt + "_properties.dds"))
        out.append('pattern_textures = {\n\tname = "%s"\n\tcolormask = "%s/ek2lc_pattern_colormask.dds"\n'
                   '\tnormal = "%s/ek2lc_pattern_normal.dds"\n\tproperties = "%s/%s_properties.dds"\n}'
                   % (pt, colour.PATTERN_DIR, colour.PATTERN_DIR, colour.PATTERN_DIR, pt))
    # a neutral pattern for channel A (colour mask 0, so it changes nothing). Our own, not vanilla's no_*.dds:
    # those are DXT3, and every texture in a variation's pattern array must share size and format.
    solid((0, 0, 0, 0), os.path.join(PAT, "ek2lc_pattern_none_colormask.dds"))
    solid((255, 56, 0, 148), os.path.join(PAT, "ek2lc_pattern_none_properties.dds"))
    out.append('pattern_textures = {\n\tname = "ek2lc_none"\n\tcolormask = "%s/ek2lc_pattern_none_colormask.dds"\n'
               '\tnormal = "%s/ek2lc_pattern_normal.dds"\n\tproperties = "%s/ek2lc_pattern_none_properties.dds"\n}'
               % (colour.PATTERN_DIR, colour.PATTERN_DIR, colour.PATTERN_DIR))
    out.append('pattern_layout = {\n\tname = "ek2lc_flat"\n\tscale = { min = 1.0\tmax = 1.0 }\n\trotation = { min = 0\tmax = 0 }\n'
               '\toffset = { x = { min = 0\tmax = 0 }\ty = { min = 0\tmax = 0 } }\n}')  # vanilla's fixed-layout form
    for tset in sorted(sets):
        pt = "ek2lc_solid_g%d_a%d" % props_of[tset]
        ch = "\n".join('\t\t%s = { textures = "%s"\tlayout = "ek2lc_flat" }' % (c, pt if c != "a" else "ek2lc_none")
                       for c in "rgba")
        out.append('variation = {\n\tname = "%s"\n\tpattern = {\n\t\tweight = 1\n%s\n\t}\n'
                   '\tcolor_palette = { weight = 1\ttexture = "%s/%s_palette.dds" }\n}'
                   % (colour.variation_name(tset), ch, colour.PATTERN_DIR, tset))
    vpath = os.path.join(MOD, "gfx/portraits/accessory_variations/ek2lc_variations.txt")
    open(vpath, "w", encoding="utf-8").write("\n\n".join(out) + "\n")

    n = 0
    for name, (tset, _) in assets().items():
        p = os.path.join(OUT, name + ".asset")
        t = open(p).read()
        t2 = colour.patch_asset(t, name, mask_of[tset], tset)
        if t2 != t:
            open(p, "w").write(t2)
            n += 1
    print("\n".join(info))
    print("%d texture sets, %d masks, %d assets patched" % (len(sets), len(masks), n))


if __name__ == "__main__":
    main()

"""Make every EK2 Loincloths piece recolourable in the barbershop (see source/colour.py).

For each texture set used by an .asset in the model folder:
  - finds the main hide or cloth colour: the biggest colour group of the soft pixels (hide, cloth,
    cord, fur, paint, stitching: the pixels whose properties are the set's plain value);
  - puts ALL soft pixels in mask channel R, stored divided by that colour. Paint and stitching
    then have no mask edge along them (texture filtering at such an edge made thin painted lines
    dull mauve-grey in game) and become a darker or redder shade of a picked colour. Pixels
    brighter than the hide (bone-white motifs, beads) get a partial mask value, so nothing is
    stored above 1.0. Shiny parts (bone, teeth, metal, gems) stay unmasked and keep their colours.
    In CK3 1.20 only channel R took a colour on our pieces in game (G and B stayed white even with
    a picked colour), so USED_GROUPS is 1 (channels G and B are empty);
  - writes the diffuse divided per mip level by exactly what the shader multiplies by: the mask
    level as the game reads it (decoded from the written DXT1), lerping from white to the hide
    colour in linear light. A 16x1 palette holds that colour, so the default look is unchanged and
    a picked colour (barbershop: the swatch beside Clothes, Legwear or Cloak, "Primary Color 1")
    replaces it;
  - writes the mask at half size with its own mip levels (identical masks are shared, unused ones
    deleted);
  - prints the default look's error per mip level (decoded diffuse x mask x palette against the
    original) and source/tools/check_colour.py checks painted lines in detail.
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
import struct
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
NOISE = 6 / 255.0    # hide pixels up to this much brighter than the hide colour raise it instead of
                     # getting a partial mask (keeps masks of plain sets identical, so shared)
MASK_STEPS = 31      # partial mask values are multiples of 1/31: exact in DXT1's 5-bit red


def lin(s):
    return np.where(s <= 0.04045, s / 12.92, ((np.maximum(s, 0.04045) + 0.055) / 1.055) ** 2.4)


def srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.maximum(x, 0.0031308) ** (1 / 2.4) - 0.055)


def _bc1(blk, dxt1):
    """RGBA of BC1 colour blocks (bh, bw, 8 bytes) -> (bh*4, bw*4, 4)."""
    b = blk.astype(np.uint32)
    c0, c1 = b[..., 0] | b[..., 1] << 8, b[..., 2] | b[..., 3] << 8
    idx = b[..., 4] | b[..., 5] << 8 | b[..., 6] << 16 | b[..., 7] << 24

    def rgb(c):
        return np.stack([(c >> 11 & 31) / 31.0, (c >> 5 & 63) / 63.0, (c & 31) / 31.0], -1).astype(np.float32)
    p0, p1 = rgb(c0), rgb(c1)
    four = (c0 > c1) if dxt1 else np.ones(c0.shape, bool)
    pal = np.ones(blk.shape[:2] + (4, 4), np.float32)
    pal[..., 0, :3], pal[..., 1, :3] = p0, p1
    pal[..., 2, :3] = np.where(four[..., None], (2 * p0 + p1) / 3, (p0 + p1) / 2)
    pal[..., 3, :3] = np.where(four[..., None], (p0 + 2 * p1) / 3, 0)
    pal[..., 3, 3] = np.where(four, 1.0, 0.0)
    sel = (idx[..., None] >> (2 * np.arange(16, dtype=np.uint32))) & 3
    px = np.take_along_axis(pal, sel[..., None].astype(np.int64), axis=2)
    bh, bw = blk.shape[:2]
    return px.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)


def _bc3_alpha(blk):
    b = blk.astype(np.uint64)
    a0, a1 = b[..., 0].astype(np.float32), b[..., 1].astype(np.float32)
    bits = sum(b[..., 2 + k] << np.uint64(8 * k) for k in range(6))
    sel = ((bits[..., None] >> (3 * np.arange(16, dtype=np.uint64))) & np.uint64(7)).astype(np.int64)
    pal = np.zeros(blk.shape[:2] + (8,), np.float32)
    pal[..., 0], pal[..., 1] = a0, a1
    big = a0 > a1
    for i in range(2, 8):
        pal[..., i] = np.where(big, ((8 - i) * a0 + (i - 1) * a1) / 7, ((6 - i) * a0 + (i - 1) * a1) / 5 if i < 6 else 255.0 * (i == 7))
    px = np.take_along_axis(pal, sel, axis=2) / 255.0
    bh, bw = blk.shape[:2]
    return px.reshape(bh, bw, 4, 4).transpose(0, 2, 1, 3).reshape(bh * 4, bw * 4)


def read_dds(path):
    """Every mip level of a DXT1/DXT5 .dds as the GPU decodes it (ImageMagick reads level 0 only)."""
    b = open(path, "rb").read()
    h, w = struct.unpack_from("<II", b, 12)
    nmip, fourcc, off, out = max(1, struct.unpack_from("<I", b, 28)[0]), b[84:88], 128, []
    for i in range(nmip):
        lw, lh = max(1, w >> i), max(1, h >> i)
        bw, bh = (lw + 3) // 4, (lh + 3) // 4
        if fourcc == b"DXT1":
            blk = np.frombuffer(b, np.uint8, bw * bh * 8, off).reshape(bh, bw, 8)
            img = _bc1(blk, True)
        elif fourcc == b"DXT5":
            blk = np.frombuffer(b, np.uint8, bw * bh * 16, off).reshape(bh, bw, 16)
            img = _bc1(blk[..., 8:], False)
            img[..., 3] = _bc3_alpha(blk[..., :8])
        else:
            raise ValueError("%s: %r" % (path, fourcc))
        out.append(img[:lh, :lw])
        off += blk.size
    return out


def compose(d, m, ref):
    """What the shader shows by default: diffuse x lerp(1, palette colour, mask R), in linear light."""
    return lin(d[..., :3]) * (1 - m[..., :1] * (1 - lin(ref)))


def upsample(a):
    """A level magnified 2x as the GPU samples it at the finer level's texel centres (bilinear, clamped)."""
    p = np.pad(a, ((1, 1), (1, 1), (0, 0)), mode="edge")
    rows = np.empty((2 * a.shape[0],) + p.shape[1:], np.float32)
    rows[0::2], rows[1::2] = 0.75 * p[1:-1] + 0.25 * p[:-2], 0.75 * p[1:-1] + 0.25 * p[2:]
    out = np.empty((rows.shape[0], 2 * a.shape[1], a.shape[2]), np.float32)
    out[:, 0::2], out[:, 1::2] = 0.75 * rows[:, 1:-1] + 0.25 * rows[:, :-2], 0.75 * rows[:, 1:-1] + 0.25 * rows[:, 2:]
    return out


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
        if p.endswith("_artifact.asset"):  # an artifact window's model (court shader, own display diffuse): not recoloured
            continue
        t = open(p).read()
        out[os.path.basename(p)[:-6]] = (re.search(r'texture_diffuse = "(.+?)_diffuse\.dds"', t).group(1),
                                         re.search(r'texture_specular = "(.+?)_properties\.dds"', t).group(1))
    return out


def main():
    os.makedirs(PAT, exist_ok=True)
    sets = {}
    for name, (tset, nset) in assets().items():
        sets.setdefault(tset, nset)
    masks, mask_of, props_of, info, worst = {}, {}, {}, [], np.zeros(4)
    decoded = {}
    for tset, nset in sorted(sets.items()):
        dpath = next(p for p in (os.path.join(TEX, tset + "_diffuse.png"), os.path.join(TEX, "cultures", tset + "_diffuse.png"))
                     if os.path.exists(p))
        dif = read_png(dpath)
        props = read_png(os.path.join(TEX, nset + "_properties.png"))
        if props.shape != dif.shape:  # a smaller diffuse on a bigger set's maps (the grave wraps): soft only where all of it is
            f = props.shape[0] // dif.shape[0]
            props = props.reshape(dif.shape[0], f, dif.shape[1], f, 4).max((1, 3))
        base_g = props[..., 1].min()
        soft = props[..., 1] <= base_g + 0.01
        px = dif[soft][:, :3]
        # each set its own random stream, from its name: a change to one set never shifts another's colour groups
        rng = np.random.default_rng(int(hashlib.sha1(tset.encode()).hexdigest()[:8], 16))
        cent = groups(features(px), rng)
        lab_soft = np.argmin(((features(px)[:, None] - cent[None]) ** 2).sum(-1), 1)
        main_grp = np.zeros(soft.shape, bool)
        main_grp[soft] = lab_soft == 0
        opaque = dif[..., 3] > 0.5
        pick = main_grp & opaque if np.any(main_grp & opaque) else main_grp
        ref = np.percentile(dif[pick][:, :3], 99.5, axis=0)
        near = soft & np.all(dif[..., :3] <= ref + NOISE, -1)
        ref = np.maximum(ref, dif[near][:, :3].max(0))
        ref = np.clip(np.ceil(np.maximum(ref, 0.03) * 255 - 1e-3) / 255, 0, 1)  # as the palette stores it
        room = 1 - lin(ref)
        need = np.where(room > 1e-6, (1 - lin(dif[..., :3])) / np.maximum(room, 1e-6), np.inf).min(-1)
        mval = np.where(soft, np.floor(np.clip(need, 0, 1) * MASK_STEPS + 1e-4) / MASK_STEPS, 0.0).astype(np.float32)
        # The mask is half size (the diffuse's mip 1 and below match its levels exactly). Each texel is
        # the lowest value of its 2x2 block and the 8 blocks around it: a lower mask never makes the
        # diffuse clip, also where the game magnifies the mask for the diffuse's full-size level.
        h, w = mval.shape
        pad = np.pad(mval.reshape(h // 2, 2, w // 2, 2).min((1, 3)), 1, mode="edge")
        m = np.zeros((h // 2, w // 2, 4), np.float32)
        m[..., 0] = np.min([pad[y:y + h // 2, x:x + w // 2] for y in range(3) for x in range(3)], 0)
        m[..., 3] = 1.0  # DXT1 reads alpha as 1 anyway; channel A's pattern is the neutral ek2lc_none
        key = hashlib.sha1(np.round(m * 255).astype(np.uint8).tobytes()).hexdigest()
        if key not in masks:
            masks[key] = tset
            mp = os.path.join(OUT, tset + "_masks.dds")
            write_dds_levels(pyramid(m), mp, "dxt1")
            dec = read_dds(mp)
            decoded[key] = [upsample(dec[0])] + dec
        mask_of[tset] = masks[key]
        # Divide each mip level of the original by exactly what the shader multiplies it by there:
        # that level of the mask as the game reads it (decoded DXT1), lerping from white to the
        # palette colour. In portraits the game samples small mips, where thin lines are part-texels.
        levels = []
        for dl, ml in zip(pyramid(dif), decoded[key]):
            nl = dl.copy()
            nl[..., :3] = srgb(lin(dl[..., :3]) / (1 - ml[..., :1] * room))
            levels.append(nl)
        dds = os.path.join(OUT, tset + "_diffuse.dds")
        write_dds_levels(levels, dds, "dxt5")
        err = []
        for dl, rd, ml in list(zip(pyramid(dif), read_dds(dds), decoded[key]))[:4]:
            op = dl[..., 3] > 0.5
            err.append(100 * float(np.abs(srgb(compose(rd, ml, ref)) - dl[..., :3])[op].mean()))
        worst = np.maximum(worst, err)
        pal = np.ones((1, 16, 4), np.float32)
        pal[0, 0, :3] = ref
        write_dds(pal, os.path.join(PAT, tset + "_palette.dds"), "none", mips=False)
        a = float(props[soft][:, 3].mean())
        props_of[tset] = (round(float(base_g) * 255), round(a * 255))
        part = soft & (mval < 1)
        info.append("%s: hide #%02x%02x%02x, soft %.0f%%, partial mask %.2f%% (min %.2f), error mip 0-3 %s%%"
                    % ((tset,) + tuple(int(round(c * 255)) for c in ref) + (100 * soft.mean(), 100 * part.mean(),
                       float(mval[part].min()) if part.any() else 1.0, " ".join("%.2f" % e for e in err))))
    for p in glob.glob(os.path.join(OUT, "*_masks.dds")):
        if os.path.basename(p)[:-len("_masks.dds")] not in masks.values():
            os.remove(p)

    # solid patterns: colour channel 1 only, flat normal (.ga = 0.5), the set's plain properties with AO 1
    # Same layout as every vanilla pattern texture (they share texture arrays with the character's other
    # pieces): DXT5 512x512; colour masks with 2 mip levels, normal and properties maps with the full chain.
    def solid(rgba, path):
        write_dds(np.broadcast_to(np.array(rgba, np.float32) / 255.0, (PAT_SIZE, PAT_SIZE, 4)).copy(), path, "dxt5",
                  mips=1 if path.endswith("colormask.dds") else True)
    solid((255, 0, 0, 0), os.path.join(PAT, "ek2lc_pattern_colormask.dds"))
    solid((128, 128, 255, 128), os.path.join(PAT, "ek2lc_pattern_normal.dds"))
    out = [BOM + "# EK2 Loincloths: barbershop colours for our pieces (made by source/tools/make_colour.py).\n"
           "# Each texture set's mask channel R holds its hide, cloth and paint; the palette holds the hide colour.\n"
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
    print("%d texture sets, %d masks, %d assets patched; worst default-look error mip 0-3: %s%%"
          % (len(sets), len(masks), n, " ".join("%.2f" % e for e in worst)))


if __name__ == "__main__":
    main()

"""Offline check of the barbershop recolouring (made by make_colour.py) for some texture sets.

For each mip level it rebuilds what the shader shows by default (decoded diffuse x lerp(1, palette,
decoded mask)) and compares it with the original texture's mip level: at the texel centres, and
half a texel off (2x2 average of diffuse and mask apart, like bilinear filtering). "Paint" is the
soft paint on the hide: pixels whose red is over twice their green (the Reach zigzag). The
"DXT5 alone" line is the error the original texture had from compression alone.

  python3 source/tools/check_colour.py [--old <git rev>] [--preview <png>] [set ...]
With --old it also checks that revision's files (from git), and --preview writes a side-by-side of the
Reach zigzag: rows mip 0 and mip 2 (magnified like the GPU does); columns original, old, new, and new
with a blue colour picked. Needs numpy (Blender's Python, or any Python with numpy).
"""
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_colour as mc  # noqa: E402

PICKED = np.array([0.25, 0.42, 0.75], np.float32)


def blob(rev, path):
    """A file's bytes from the working tree (rev None) or from git, saved to a temp file."""
    if rev is None:
        return path
    rel = os.path.relpath(path, mc.MOD)
    data = subprocess.run(["git", "-C", mc.MOD, "show", "%s:%s" % (rev, rel)], capture_output=True, check=True).stdout
    f = tempfile.NamedTemporaryFile(suffix=os.path.splitext(path)[1], delete=False)
    f.write(data)
    f.close()
    return f.name


def files(tset, rev=None):
    """Decoded diffuse levels, mask levels aligned with them, and the palette colour."""
    asset = next(os.path.join(mc.OUT, n + ".asset") for n, (t, _) in mc.assets().items() if t == tset)
    text = open(blob(rev, asset)).read()
    mask = re.search(r'pattern_mask = "[^"]*?([^"/]+_masks\.dds)"', text).group(1)
    d = mc.read_dds(blob(rev, os.path.join(mc.OUT, tset + "_diffuse.dds")))
    m = mc.read_dds(blob(rev, os.path.join(mc.OUT, mask)))
    if m[0].shape[0] * 2 == d[0].shape[0]:
        m = [mc.upsample(m[0])] + m
    pal = mc.read_png(blob(rev, os.path.join(mc.PAT, tset + "_palette.dds")) + "[0]")[0, 0, :3]
    return d, m, pal


def half(a):
    """Every texel averaged with its right, lower and lower-right neighbours (half a texel off)."""
    return (a[:-1, :-1] + a[1:, :-1] + a[:-1, 1:] + a[1:, 1:]) / 4


def stats(orig, paint, d, m, pal, n=4):
    rows = []
    for i, (t, pt, dl, ml) in enumerate(list(zip(mc.pyramid(orig), mc.pyramid(paint[..., None]), d, m))[:n]):
        op = t[..., 3] > 0.5
        e = np.abs(mc.srgb(mc.compose(dl, ml, pal)) - t[..., :3])
        tl = mc.lin(t[..., :3])
        eh = np.abs(mc.srgb(mc.compose(half(dl), half(ml), pal)) - mc.srgb(half(tl)))
        oh, ph, pp = half(op.astype(np.float32)) > 0.99, half(pt[..., 0]) > 0.5, pt[..., 0] > 0.5
        rows.append((100 * e[op].mean(), 100 * eh[oh].mean(), 100 * e[pp & op].mean() if pp.any() else 0,
                     100 * eh[ph & oh].mean() if ph.any() else 0, 100 * np.percentile(eh[ph & oh].max(-1), 95) if ph.any() else 0))
    return rows


def view(orig, d, m, pal, level, box):
    """The crop box (x0, y0, x1, y1 at full size) as shown from a mip level, magnified like the GPU."""
    t, dl, ml = mc.pyramid(orig)[level], d[level], m[level]
    tl = mc.lin(t[..., :3])
    for _ in range(level):
        t, dl, ml, tl = mc.upsample(t), mc.upsample(dl), mc.upsample(ml), mc.upsample(tl)
    x0, y0, x1, y1 = box
    out = [mc.srgb(tl), mc.srgb(mc.compose(dl, ml, pal))]
    return [o[y0:y1, x0:x1] for o in out], (dl[y0:y1, x0:x1], ml[y0:y1, x0:x1])


def main():
    args, old, preview = sys.argv[1:], None, None
    if "--old" in args:
        i = args.index("--old")
        old = args[i + 1]
        del args[i:i + 2]
    if "--preview" in args:
        i = args.index("--preview")
        preview = args[i + 1]
        del args[i:i + 2]
    for tset in args or ["ek2lc_reach_hide_01"]:
        p = os.path.join(mc.TEX, tset + "_diffuse.png")
        orig = mc.read_png(p if os.path.exists(p) else os.path.join(mc.TEX, "cultures", tset + "_diffuse.png"))
        paint = ((orig[..., 0] > 2 * orig[..., 1]) & (orig[..., 3] > 0.5)).astype(np.float32)
        tmp = os.path.join(tempfile.mkdtemp(), "orig.dds")
        mc.write_dds_levels(mc.pyramid(orig), tmp, "dxt5")
        base = [100 * float(np.abs(b[..., :3] - t[..., :3])[t[..., 3] > 0.5].mean())
                for b, t in list(zip(mc.read_dds(tmp), mc.pyramid(orig)))[:4]]
        print("%s (paint %.2f%% of pixels); errors in %% of full scale, mip 0-3" % (tset, 100 * paint.mean()))
        print("  DXT5 alone:            mean %s" % " ".join("%5.2f" % b for b in base))
        for label, rev in (("new", None),) + ((("old " + old, old),) if old else ()):
            r = stats(orig, paint, *files(tset, rev))
            for k, name in enumerate(("mean at texels", "mean half-texel off", "paint at texels", "paint half-texel off",
                                      "paint 95th pct off")):
                print("  %-4s %-22s %s" % (label[:4], name + ":", " ".join("%5.2f" % row[k] for row in r)))
    if preview:
        tset = "ek2lc_reach_hide_01"
        orig = mc.read_png(os.path.join(mc.TEX, tset + "_diffuse.png"))
        box = (12, 760, 268, 840)
        rows = []
        for level in (0, 2):
            new, (dl, ml) = view(orig, *files(tset), level, box)
            cols = [new[0], view(orig, *files(tset, old), level, box)[0][1] if old else new[0] * 0, new[1],
                    mc.srgb(mc.compose(dl, ml, PICKED))]
            rows.append(np.concatenate(sum([[c, np.ones((c.shape[0], 4, 3))] for c in cols], [])[:-1], 1))
        img = np.concatenate([rows[0], np.ones((4, rows[0].shape[1], 3)), rows[1]], 0)
        img = np.repeat(np.repeat(img, 2, 0), 2, 1)
        rgba = np.concatenate([img, np.ones(img.shape[:2] + (1,))], -1)
        subprocess.run([mc.MAGICK, "-size", "%dx%d" % (rgba.shape[1], rgba.shape[0]), "-depth", "8", "rgba:-", preview],
                       input=np.clip(np.round(rgba * 255), 0, 255).astype(np.uint8).tobytes(), check=True)
        print("wrote", preview)


if __name__ == "__main__":
    main()

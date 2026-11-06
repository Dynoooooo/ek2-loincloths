"""Textures for EK2's undead (build_reach_hide.py makes them; pure numpy, so it also runs outside Blender).

  - Lich's burial regalia: one texture set per piece type, shared by all cultures. The texture code
    draws the Reach pieces in LICH's colours (cultures.py roles), then lich_finish() soots, cracks
    and greys them and puts green-black patina in the metal's recesses.
  - Grave wrap: each culture's plain loincloth texture (the chest band shares it), rotted by
    grave_rot(): faded, greyed and darkened, grave dirt and mould, frayed and torn flap edges and
    hems, a few small holes. Only the flaps' side edges and hems lose anything: the strip (pouch),
    the chest band, the belt and the middle of the flaps stay solid.
"""
import numpy as np

SOOT, BLOOM, PATINA = np.array([0.02, 0.019, 0.018]), np.array([0.30, 0.30, 0.31]), np.array([0.07, 0.11, 0.075])
DIRT, MOULD, BLACK = np.array([0.10, 0.085, 0.065]), np.array([0.33, 0.37, 0.28]), np.array([0.03, 0.03, 0.025])
FLAPS = ((0.01, 0.49, 0.01, 0.74), (0.51, 0.99, 0.01, 0.74))  # the plain loincloth's flaps (u0, u1, v0, v1)


def fbm(h, w, k, seed, octaves=4):
    """Smooth value noise in 0..1, k cells across at the first octave."""
    rng = np.random.default_rng(seed)
    acc, amp, tot = np.zeros((h, w), np.float32), 1.0, 0.0
    for o in range(octaves):
        n = k * 2 ** o
        g = rng.random((n + 2, n + 2)).astype(np.float32)
        ys, xs = np.linspace(0, n, h, endpoint=False), np.linspace(0, n, w, endpoint=False)
        y0, x0 = ys.astype(np.int32), xs.astype(np.int32)
        fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
        a, b, c, d = g[np.ix_(y0, x0)], g[np.ix_(y0, x0 + 1)], g[np.ix_(y0 + 1, x0)], g[np.ix_(y0 + 1, x0 + 1)]
        acc += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
        tot += amp
        amp *= 0.5
    return acc / tot


def lerp(rgb, col, t):
    return rgb + (np.asarray(col, np.float32) - rgb) * t[..., None]


def grow(m, r):
    """Mask m grown by r pixels (square)."""
    out = m.copy()
    for _ in range(r):
        g = out.copy()
        g[1:] |= out[:-1]
        g[:-1] |= out[1:]
        g[:, 1:] |= out[:, :-1]
        g[:, :-1] |= out[:, 1:]
        out = g
    return out


def blacken(img, level=0.085):
    """A texture whose colours aren't palette roles (the camp wrap) greyed and darkened to the lich's hide."""
    out = img.copy()
    rgb = out[..., :3]
    lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
    rgb[:] = (0.25 * rgb + 0.75 * lum[..., None]) * (level / max(float(np.median(lum)), 1e-3))
    return np.clip(out, 0, 1)


def lich_finish(img, metal, seed):
    """Soot, cracks and a grey bloom over a lich texture; patina in the recesses of `metal` (bool mask)."""
    h, w = img.shape[:2]
    out = np.nan_to_num(img)
    rgb = out[..., :3]
    s = h / 1024.0  # noise and lines scale with the texture's size
    rgb[:] = lerp(rgb, SOOT, 0.55 * np.clip((fbm(h, w, 5, seed) - 0.45) * 2.5, 0, 1))
    lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
    rgb[:] = lerp(rgb, BLOOM, (0.06 + 0.16 * fbm(h, w, 7, seed + 1, 3)) * np.clip(1 - lum / 0.45, 0, 1))
    for k, sd, amt in ((6, 2, 0.45), (15, 3, 0.3)):  # crack networks: a dark line with a pale flaking rim
        d = np.abs(fbm(h, w, k, seed + sd, 6) - 0.5) * s
        core, rim = np.clip(1 - d / 0.004, 0, 1), np.clip(1 - d / 0.011, 0, 1)
        rgb[:] = lerp(rgb, BLOOM * 1.15, amt * rim * (1 - core) * np.clip(1 - lum / 0.45, 0, 1))
        rgb[:] *= (1 - 0.8 * core)[..., None]
    if metal.any():
        edge = metal & grow(~metal, max(1, int(round(2 * s))))  # the metal's rims: its recesses
        pn = fbm(h, w, 16, seed + 4, 3)
        amt = np.clip(np.where(edge, 0.8, 0.0) + (pn - 0.62) * 2.2, 0, 1) * metal
        rgb[:] = lerp(rgb, PATINA, 0.85 * amt * (0.8 + 0.4 * pn))
    return np.clip(out, 0, 1)


def grave_rot(img, seed):
    """The rotted grave wrap from a culture's plain loincloth texture (1024 square), at half size."""
    H, W = img.shape[:2]
    out = np.nan_to_num(img)
    rgb, a = out[..., :3], out[..., 3]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
    rgb[:] = (0.35 * rgb + 0.65 * lum[..., None]) * 0.68 + np.array([0.010, 0.008, 0.004], np.float32)
    rgb[:] = lerp(rgb, DIRT, 0.6 * np.clip((fbm(H, W, 4, seed) - 0.42) * 2.2, 0, 1))
    m = np.clip((fbm(H, W, 12, seed + 1) - 0.58) * 6, 0, 1) * np.clip(fbm(H, W, 3, seed + 2, 2) * 2.4 - 0.7, 0, 1)
    rgb[:] = lerp(rgb, MOULD * (0.8 + 0.4 * fbm(H, W, 40, seed + 3, 2))[..., None], 0.7 * m)
    sp = np.clip((fbm(H, W, 90, seed + 4, 2) - 0.68) * 9, 0, 1) * np.clip(0.25 + 1.5 * m, 0, 1)  # mould's black specks
    rgb[:] = lerp(rgb, BLACK, 0.8 * sp)
    rng = np.random.default_rng(seed + 5)
    cut = np.zeros((H, W), bool)
    for u0, u1, v0, v1 in FLAPS:
        x0, x1, y0, y1 = int(round(u0 * W)), int(round(u1 * W)), int(round((1 - v1) * H)), int(round((1 - v0) * H))
        h, w = y1 - y0, x1 - x0
        sx, sy = xx[y0:y1, x0:x1] - x0, yy[y0:y1, x0:x1] - y0
        fy = sy / (h - 1)
        edge = np.minimum(sx, w - 1 - sx)
        sub = rgb[y0:y1, x0:x1]
        sub *= (1 - 0.3 * fy ** 2)[..., None]  # grave dirt soaked up from the hem
        # torn side edges: a ragged line 2-3 px in, with a few deeper notches
        n1 = fbm(h, 2, 18, int(rng.integers(1 << 30)), 3)
        depth = 2 + 2 * n1 + 16 * np.clip((fbm(h, 2, 7, int(rng.integers(1 << 30)), 2) - 0.6) * 3, 0, 1)
        c = (sx < depth[:, :1]) | (w - 1 - sx < depth[:, 1:])
        # torn hem: the fringe eaten further up in places, a few threads left hanging
        n2 = fbm(2, w, 14, int(rng.integers(1 << 30)), 3)[0]
        hem = 0.955 - 0.08 * np.clip((n2 - 0.5) * 3, 0, 1)
        thread = ((sx.astype(np.int32) % 9) == 4) & (fy < hem + 0.03)
        c |= (fy > hem) & ~thread
        # small holes, only near the side edges or low on the flap
        for _ in range(7):
            if rng.random() < 0.5:
                cx = rng.uniform(8, 40) if rng.random() < 0.5 else w - 1 - rng.uniform(8, 40)
                cy = rng.uniform(0.2, 0.85) * h
            else:
                cx, cy = rng.uniform(40, w - 40), rng.uniform(0.78, 0.88) * h
            r = rng.uniform(3, 7) * H / 1024
            ang = np.arctan2(sy - cy, sx - cx)
            wob = 1 + 0.35 * np.sin(3 * ang + rng.uniform(0, 6)) + 0.2 * np.sin(5 * ang + rng.uniform(0, 6))
            c |= (sx - cx) ** 2 + (sy - cy) ** 2 < (r * wob) ** 2
        cut[y0:y1, x0:x1] |= c
    a[cut] = 0.0
    rim = grow(cut, 3) & ~cut  # rotted, darker edges round every tear and hole
    rgb[rim] *= 0.6
    out = out.reshape(H // 2, 2, W // 2, 2, 4).mean((1, 3))
    return np.clip(out, 0, 1)

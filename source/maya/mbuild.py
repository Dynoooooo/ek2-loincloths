"""A Meshy garment made into a CK3 piece, in the Maya GUI: fitted to the body, bone weights, the .mesh file,
then (with shapes.py) one blendshape per body shape. Port of source/legacy_blender/build_regalia.py's
meshy_load / meshy_parts / meshy_fit / hang_w and build_reach_hide.py's skirt_weights (2026-11-10).

    import ck3scene as cs, mbuild as mb
    cs.new_scene(); body = cs.load_body("male")
    g = mb.load("keptu_ruler")                    # source/meshy/keptu_ruler/model.glb
    P = mb.fit(g, body)                           # positions fitted round the hips (Maya space, cm)
    bones, w = mb.weights(P, body)                # top 4 bones per vertex: the skin at the belt, the skirt chains below
    mb.write_mesh("ek2lc_m_people_keptu_ruler_01", "male", P, g, bones, w, "ek2lc_people_keptu_ruler_01")
    mb.make_shapes("ek2lc_m_people_keptu_ruler_01", body)   # every body shape, then clipping repair

Space: Maya's (Y up, the body faces +Z, the character's left is +X). Angles round the body are measured from the
front (+Z) towards +X. The .mesh file has Z negated and the triangles' corners reversed (see write_mesh).
"""
import math
import os
import numpy as np
import maya.cmds as mc
import ck3scene as cs
import audit as au
import glb
import wsolve

MESHY = cs.MOD + "/source/meshy"
MB, MZ = 48, 1.0          # angle bins round the body, height rows (cm), as the Blender fit
SKIRT_CH = ("f", "lf", "l", "lb", "b", "rb", "r", "rf")


# ---------------------------------------------------------------- Meshy model
class Garment:
    """A Meshy GLB: vertices as stored (split at UV seams), welded ids, triangles, UVs, connected parts."""

    def __init__(self, key, path=None):
        self.key = key
        V, N, UV, T, self.images = glb.load(path or os.path.join(MESHY, key, "model.glb"))
        self.V, self.UV, self.T = V, UV, T
        self.wid = weld_ids(V)
        self.part = parts(self.wid, T)


def load(key, path=None):
    return Garment(key, path)


class Sub:
    """The vertices `keep` of a garment (and the triangles among them), renumbered; same attributes as Garment."""

    def __init__(self, g, keep):
        idx = np.nonzero(keep)[0]
        new = -np.ones(len(g.V), np.int64)
        new[idx] = np.arange(len(idx))
        T = g.T[keep[g.T].all(1)]
        self.key, self.images = g.key, g.images
        self.V, self.UV, self.T = g.V[idx], g.UV[idx], new[T]
        self.wid = new[g.wid[idx]]
        self.part = g.part[idx]
        self.idx = idx


def join(subs, Ps):
    """One garment from fitted subs (positions Ps): concatenated vertices and triangles."""
    class J:
        pass
    j = J()
    off = 0
    V, UV, T, wid, part = [], [], [], [], []
    for s, P in zip(subs, Ps):
        V.append(P), UV.append(s.UV), T.append(s.T + off), wid.append(s.wid + off), part.append(s.part)
        off += len(P)
    j.key, j.images = subs[0].key, subs[0].images
    j.V, j.UV, j.T, j.wid, j.part = np.vstack(V), np.vstack(UV), np.vstack(T), np.concatenate(wid), np.concatenate(part)
    return j


def split_top(g, overlap=0.04):
    """Mask of the chest wrap: the parts lying above the main (largest) part, allowing them to dip `overlap` of the
    garment's height below its top (a wrap's hem can reach down past the belt's top edge)."""
    y = g.V[:, 1]
    h = y.max() - y.min()
    ids, cnt = np.unique(g.part, return_counts=True)
    main = ids[np.argmax(cnt)]
    top_main = y[g.part == main].max()
    mask = np.zeros(len(y), bool)
    for p in ids:
        if p == main:
            continue
        m = g.part == p
        if (y[m].min() > top_main - overlap * h and np.median(y[m]) > top_main) or (y[m] > top_main).mean() > 0.7:
            mask |= m   # (the second: a wrap whose tie hangs down past the belt)
    return mask


def auto_yaw(g, ring_h=0.05):
    """Turn (degrees) that puts the garment's two biggest hanging panels at the front and back: the axis through the
    angle pair (a, a + 180) holding the most hanging vertices."""
    co = g.V
    y = co[:, 1]
    gc = np.array([(co[:, 0].min() + co[:, 0].max()) / 2, 0.0, (co[:, 2].min() + co[:, 2].max()) / 2])
    hang = y < y.max() - 0.25 * (y.max() - y.min())
    a = _ang(co[hang], gc)
    h, _ = np.histogram(a, bins=72, range=(0, 2 * math.pi))
    w = np.convolve(np.r_[h, h, h], np.ones(7), "same")[72:144]
    pair = w + np.roll(w, 36)
    k = int(np.argmax(pair[:36]))
    return -math.degrees((k + 0.5) * 2 * math.pi / 72)


def crotch_mask(g, frac=0.4, ring_h=0.05):
    """Vertices of a strip passing between the legs (near the garment's axis, below its belt ring), in Meshy's
    coordinates. The radial fit can't pass between the legs (it lays them across both thighs as a bar), so they are
    dropped; the strip's front and back ends still hang as narrow aprons."""
    co = g.V
    y = co[:, 1]
    gc = np.array([(co[:, 0].min() + co[:, 0].max()) / 2, 0.0, (co[:, 2].min() + co[:, 2].max()) / 2])
    rad = np.hypot(co[:, 0] - gc[0], co[:, 2] - gc[2])
    a = _ang(co, gc)
    kb = (a / (2 * math.pi) * MB).astype(int) % MB
    far = rad > 0.3 * rad.max()
    top = np.array([y[far & (kb == k)].max() if (far & (kb == k)).any() else np.nan for k in range(MB)])
    zt = np.nanmedian(top)
    ring = (y >= zt - ring_h) & (y <= zt + 0.01)
    zr, r_med = y[ring].mean(), np.median(rad[ring])
    return (rad < frac * r_med) & (y < zr - 2 * ring_h)


def _hull_radii(R, angs):
    """Radii of the convex hull of a ring (radius per angle): a band stretched over the bust bridges the cleavage."""
    pts = np.c_[np.sin(angs) * R, np.cos(angs) * R]
    order = np.lexsort((pts[:, 1], pts[:, 0]))
    P = pts[order]

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and np.cross(h[-1] - h[-2], p - h[-2]) <= 0:
                h.pop()
            h.append(p)
        return h
    hull = np.array(half(P)[:-1] + half(P[::-1])[:-1])
    out = np.empty(len(angs))
    for k, a in enumerate(angs):
        d = np.array([np.sin(a), np.cos(a)])
        best = 0.0
        for i in range(len(hull)):
            p, q = hull[i], hull[(i + 1) % len(hull)]
            e = q - p
            den = d[0] * (-e[1]) - d[1] * (-e[0])
            if abs(den) < 1e-12:
                continue
            t = (p[0] * (-e[1]) - p[1] * (-e[0])) / den
            u = (d[0] * p[1] - d[1] * p[0]) / den
            if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                best = max(best, t)
        out[k] = best
    return out


def chest_y(B):
    """Height of the bust's most forward point (the legacy CHEST_Z)."""
    P = B.P
    m = (np.abs(P[:, 0]) < 14) & (P[:, 1] > B.belt + 18) & (P[:, 1] < B.belt + 55)
    return P[m][np.argmax(P[m][:, 2]), 1]


def fit_band(g, body, top=3.5, bot=-7.5, gap=0.35, max_thick=1.0, log=print):
    """A chest wrap laid on the body between chest_y + top and chest_y + bot: each vertex at its angle and its
    relative height in the band, gap outside the body's hull at that height, keeping its own thickness (lacing and
    knots stick out as they did)."""
    B = body if isinstance(body, Body) else Body(body)
    co = g.V
    y = co[:, 1]
    gc = np.array([(co[:, 0].min() + co[:, 0].max()) / 2, 0.0, (co[:, 2].min() + co[:, 2].max()) / 2])
    rad = np.hypot(co[:, 0] - gc[0], co[:, 2] - gc[2])
    a = _ang(co, gc)
    cy_ = chest_y(B)
    y0, y1 = y.min(), y.max()
    yt = cy_ + top + (y - y1) / (y1 - y0) * (top - bot)
    angs = 2 * math.pi * (np.arange(MB) + 0.5) / MB
    rows = np.arange(math.floor(yt.min()) - 1, math.ceil(yt.max()) + 2, MZ)
    R = np.zeros((MB, len(rows)))
    for j, yy in enumerate(rows):
        R[:, j] = _hull_radii(B.radii(yy, angs, chest=True), angs)
    kb = (a / (2 * math.pi) * MB).astype(int) % MB
    jb = np.clip(np.round((yt - rows[0]) / MZ).astype(int), 0, len(rows) - 1)
    inner_k = np.array([np.percentile(rad[kb == k], 20) if (kb == k).sum() > 3 else np.nan for k in range(MB)])
    inner_k = _fill(inner_k)
    scale = np.median((_lerp_bins(R.mean(1), angs) + gap) / inner_k)
    thick = np.clip((rad - _lerp_bins(inner_k, a)) * scale, 0.0, max_thick)
    yc = np.interp(yt, rows, np.arange(len(rows)))
    j0 = np.clip(yc.astype(int), 0, len(rows) - 2)
    u = yc - j0
    f = a / (2 * math.pi) * MB - 0.5
    k0 = np.floor(f).astype(int)
    t = f - k0
    k1, k0 = (k0 + 1) % MB, k0 % MB
    Ra = (R[k0, j0] * (1 - t) + R[k1, j0] * t) * (1 - u) + (R[k0, j0 + 1] * (1 - t) + R[k1, j0 + 1] * t) * u
    out = np.empty_like(co)
    for i in range(len(co)):
        c = np.array([0.0, yt[i], B.cz(round(yt[i]))])
        out[i] = c + np.array([math.sin(a[i]), 0.0, math.cos(a[i])]) * (Ra[i] + gap + thick[i])
    out[:, 1] = yt
    log("BAND %s: chest %.1f, rows %.1f..%.1f, thickness to %.2f cm" % (g.key, cy_, yt.min(), yt.max(), thick.max()))
    return out


def weld_ids(V, tol=1e-5):
    """Representative vertex per position (vertices split only by UVs get the same id)."""
    q = np.round(V / tol).astype(np.int64)
    _, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    return first[inv.ravel()]


def parts(wid, T):
    """Connected part id per vertex, over welded vertices (Meshy keeps rope, knot, each tassel apart)."""
    n = len(wid)
    par = np.arange(n)

    def root(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    W = wid[T]
    for a, b in ((0, 1), (1, 2), (0, 2)):
        for x, y in zip(W[:, a], W[:, b]):
            rx, ry = root(x), root(y)
            if rx != ry:
                par[rx] = ry
    return np.array([root(wid[i]) for i in range(n)])


# ---------------------------------------------------------------- the body, as numpy
def _ray_first(O, D, A, E1, E2, maxd):
    """First hit distance along each ray (Moller-Trumbore against every triangle), inf where none."""
    out = np.full(len(O), np.inf)
    for s in range(0, len(O), 64):
        o, d = O[s:s + 64, None, :], D[s:s + 64, None, :]
        p = np.cross(d, E2[None])
        det = (E1[None] * p).sum(-1)
        ok = np.abs(det) > 1e-9
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = o - A[None]
        u = (tv * p).sum(-1) * inv
        q = np.cross(tv, E1[None])
        v = (d * q).sum(-1) * inv
        t = (E2[None] * q).sum(-1) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6) & (t < maxd)
        out[s:s + 64] = np.where(hit, t, np.inf).min(1)
    return out


class Body:
    """The body without forearms and hands (they hang beside the hips), plus any worn pieces to fit over, in the
    rest pose and the current shape weights. Ray casts, the body's centre per height, skin weights."""

    def __init__(self, body, over=()):
        cs.rest_pose()
        self.name = body
        self.sex = "female" if body.endswith("_f") else "male"
        P = au.pts(body)
        T, _ = au.tris(body)
        info = au.body_info(body)
        arm = info["arm"]
        keep = ~(arm[T].any(1))
        self.P, self.T_all, self.T = P, T, T[keep]
        shoulder = np.array([any(k in j for k in ("shoulder", "clavicle", "deltoid", "upperarm", "bicep")) for j in info["dom"]]) | arm
        self.T_chest = T[~(shoulder[T].any(1))]   # a chest wrap follows the chest and spine, not the upper arms
        tc = P[self.T_chest]
        self.chest_tri = (tc[:, 0], tc[:, 1] - tc[:, 0], tc[:, 2] - tc[:, 0])
        Ts = [P[self.T]]
        for o in over:
            Po = au.pts(o)
            To, _ = au.tris(o)
            Ts.append(Po[To])
        tri = np.concatenate(Ts)
        self.A, self.E1, self.E2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        self.root_y = mc.xform("body_root", query=True, worldSpace=True, translation=True)[1]
        self.belt = self.root_y + 6.0
        mid = (np.abs(P[:, 0]) < 1.0) & (P[:, 1] > 40) & (P[:, 1] < self.root_y + 5)
        self.crotch = P[mid, 1].min()
        self.top = P[:, 1].max()
        self.W, self.infl = au.skin_weights(body)
        self._cz = {}

    def hits(self, O, D, maxd=400.0, chest=False):
        A, E1, E2 = self.chest_tri if chest else (self.A, self.E1, self.E2)
        return _ray_first(np.asarray(O, float), np.asarray(D, float), A, E1, E2, maxd)

    def cz(self, y):
        """Centre (z) at height y: half way between the front and back of the body; between the legs, the crotch's."""
        key = round(y, 2)
        if key not in self._cz:
            yy = max(y, self.crotch + 2.0)
            for _ in range(40):
                t = self.hits([(0, yy, 200), (0, yy, -200)], [(0, 0, -1), (0, 0, 1)])
                if np.isfinite(t).all():
                    break
                yy += 1.0
            self._cz[key] = ((200 - t[0]) + (-200 + t[1])) / 2
        return self._cz[key]

    def radii(self, y, angs, chest=False):
        """Outermost body radius at height y for each angle, from the centre at that height (chest: torso only)."""
        c = np.array([0.0, y, self.cz(y)])
        d = np.c_[np.sin(angs), np.zeros(len(angs)), np.cos(angs)]
        t = self.hits(c + d * 80.0, -d, 80.0, chest)
        r = 80.0 - t
        r[~np.isfinite(t)] = np.nan
        if np.isnan(r).all():
            return np.zeros(len(angs))
        idx = np.arange(len(r))
        good = ~np.isnan(r)
        r[~good] = np.interp(idx[~good], idx[good], r[good], period=len(r))
        return r


def _ang(X, c):
    return np.arctan2(X[:, 0] - c[0], X[:, 2] - c[2]) % (2 * math.pi)


def _dir(a):
    return np.c_[np.sin(a), np.zeros(len(a)), np.cos(a)]


def _fill(vals):
    out = vals.copy()
    idx = np.arange(len(vals))
    good = ~np.isnan(vals)
    out[~good] = np.interp(idx[~good], idx[good], vals[good], period=len(vals))
    return out


def _lerp_bins(vals, a):
    f = a / (2 * math.pi) * MB - 0.5
    k0 = np.floor(f).astype(int)
    t = f - k0
    return vals[k0 % MB] * (1 - t) + vals[(k0 + 1) % MB] * t


def _field(F, a, y, z_hi):
    nz = F.shape[1]
    f = a / (2 * math.pi) * MB - 0.5
    k0 = np.floor(f).astype(int)
    t = f - k0
    g = np.clip((z_hi - y) / MZ, 0.0, nz - 1.001)
    j0 = g.astype(int)
    u = g - j0
    k1 = (k0 + 1) % MB
    k0 = k0 % MB
    return ((F[k0, j0] * (1 - t) + F[k1, j0] * t) * (1 - u) + (F[k0, j0 + 1] * (1 - t) + F[k1, j0 + 1] * t) * u)


def fit(g, body, gap=0.6, z_scale=0.72, ring_h=0.05, tight=0.75, thin=1.0, over=(), log=print):
    """Positions of the garment's vertices on the body (rest pose, current shape weights): its top ring (the belt)
    scaled per angle onto the body at belt height plus gap, heights scaled by the ring's median factor x z_scale,
    the rope keeping its own thickness, small parts (tassels) moved as one with their top; then flaring parts
    pulled in towards the body by `tight` of their slack, then everything pushed out to gap outside the body."""
    B = body if isinstance(body, Body) else Body(body, over)
    co = g.V
    y = co[:, 1]
    gc = np.array([(co[:, 0].min() + co[:, 0].max()) / 2, 0.0, (co[:, 2].min() + co[:, 2].max()) / 2])
    rad = np.hypot(co[:, 0] - gc[0], co[:, 2] - gc[2])
    a = _ang(co, gc)
    r_ext = rad.max()
    kb = (a / (2 * math.pi) * MB).astype(int) % MB
    top = np.full(MB, np.nan)
    far = rad > 0.3 * r_ext
    for k in range(MB):
        m = far & (kb == k)
        if m.any():
            top[k] = y[m].max()
    zt = np.nanmedian(top)
    ring = (y >= zt - ring_h) & (y <= zt + 0.01)
    zr = y[ring].mean()
    r_med = np.median(rad[ring])
    rin = np.full(MB, np.nan)
    for k in range(MB):
        m = ring & (kb == k) & (rad >= 0.75 * r_med)
        if m.any():
            rin[k] = rad[m].min()
    rin = _fill(rin)
    angs = 2 * math.pi * (np.arange(MB) + 0.5) / MB
    rb = B.radii(B.belt, angs)
    q = (rb + gap) / rin
    sz = np.median(q) * z_scale
    cb = np.array([0.0, B.belt, B.cz(B.belt)])

    def belt_shift(i):
        ri, qa = _lerp_bins(rin, a[i]), _lerp_bins(q, a[i])
        return ri * qa + (rad[i] - ri) * sz - rad[i] * qa
    wt = np.zeros(len(co))
    anchor = np.arange(len(co))
    h = y.max() - y.min()
    for pid in np.unique(g.part):
        p = np.nonzero(g.part == pid)[0]
        z0, z1 = y[p].min(), y[p].max()
        if z1 >= zt - ring_h and z1 - z0 <= 3 * ring_h:       # the rope, its knot, a tassel's top
            wt[p] = 1.0
        elif z1 - z0 < 0.35 * h:                               # a small part: moved with its top, if that's at the rope
            t_ = p[np.argmax(y[p])]
            wt[p] = 1.0 if z1 >= zr - 3 * ring_h else 0.0
            anchor[p] = t_
        else:                                                   # a panel: its top follows the rope, eased below
            wt[p] = np.clip((y[p] - (zr - 3 * ring_h)) / (2 * ring_h), 0.0, 1.0)
    r = rad * _lerp_bins(q, a) + np.where(wt > 0, wt * belt_shift(anchor), 0.0)
    out = cb + _dir(a) * r[:, None] + np.c_[np.zeros(len(co)), (y - zr) * sz, np.zeros(len(co))]
    # the body's outermost radius per angle and height row; below the belt, the most of it above (no tucking in)
    z_hi = out[:, 1].max() + MZ
    nz = int((z_hi - out[:, 1].min()) / MZ) + 3
    R = np.zeros((MB, nz))
    for j in range(nz):
        yj = z_hi - j * MZ
        R[:, j] = B.radii(yj, angs) if yj > 2.0 else 0.0
    below = np.nonzero(z_hi - np.arange(nz) * MZ <= B.belt)[0]
    for j in below[1:]:
        R[:, j] = np.maximum(R[:, j], R[:, j - 1])
    cbz = lambda P: np.c_[P[:, 0] - cb[0], P[:, 2] - cb[2]]
    rh = lambda P: np.hypot(*cbz(P).T)

    def bins(P):
        k = (_ang(P, cb) / (2 * math.pi) * MB).astype(int) % MB
        j = np.clip(np.round((z_hi - P[:, 1]) / MZ).astype(int), 0, nz - 1)
        return k, j
    # tighten: Meshy's skirts flare off the body: pull each bin's innermost layer in by `tight` of its slack
    k, j = bins(out)
    e = rh(out) - (R[k, j] + gap)
    E = np.full((MB, nz), np.inf)
    np.minimum.at(E, (k, j), e)
    T = np.where(np.isfinite(E), -np.maximum(E, 0.0) * tight, np.nan)
    for _ in range(200):
        if not np.isnan(T).any():
            break
        nb = np.stack([np.roll(T, 1, 0), np.roll(T, -1, 0), np.pad(T, ((0, 0), (1, 0)), constant_values=np.nan)[:, :-1],
                       np.pad(T, ((0, 0), (0, 1)), constant_values=np.nan)[:, 1:]])
        cnt = (~np.isnan(nb)).sum(0)
        mean = np.where(cnt > 0, np.nansum(nb, 0) / np.maximum(cnt, 1), np.nan)
        T = np.where(np.isnan(T), mean, T)
    T = np.nan_to_num(T)
    for _ in range(10):
        T = (T * 2 + np.roll(T, 1, 0) + np.roll(T, -1, 0) + np.c_[T[:, :1], T[:, :-1]] + np.c_[T[:, 1:], T[:, -1:]]) / 6
    out = out + _dir(_ang(out, cb)) * _field(T, _ang(out, cb), out[:, 1], z_hi)[:, None]
    if thin < 1.0:  # bulky parts (Meshy models fur as a thick volume): layers outside a bin's innermost brought closer
        k, j = bins(out)
        r_ = rh(out)
        RM = np.full((MB, nz), np.inf)
        np.minimum.at(RM, (k, j), r_)
        RM = np.where(np.isfinite(RM), RM, np.nan)
        for _ in range(200):
            if not np.isnan(RM).any():
                break
            nb = np.stack([np.roll(RM, 1, 0), np.roll(RM, -1, 0), np.pad(RM, ((0, 0), (1, 0)), constant_values=np.nan)[:, :-1],
                           np.pad(RM, ((0, 0), (0, 1)), constant_values=np.nan)[:, 1:]])
            cnt = (~np.isnan(nb)).sum(0)
            RM = np.where(np.isnan(RM), np.where(cnt > 0, np.nansum(nb, 0) / np.maximum(cnt, 1), np.nan), RM)
        RM = np.nan_to_num(RM)
        for _ in range(6):
            RM = np.minimum(RM, (RM * 2 + np.roll(RM, 1, 0) + np.roll(RM, -1, 0) + np.c_[RM[:, :1], RM[:, :-1]]
                                 + np.c_[RM[:, 1:], RM[:, -1:]]) / 6)
        a_ = _ang(out, cb)
        rm = _field(RM, a_, out[:, 1], z_hi)
        r2 = np.where(r_ > rm, rm + (r_ - rm) * thin, r_)
        out = out + _dir(a_) * (r2 - r_)[:, None]
    # then how far out each vertex must still go; dilate, smooth (never below a bin's own need)
    k, j = bins(out)
    need = R[k, j] + gap - rh(out)
    D = np.zeros((MB, nz))
    np.maximum.at(D, (k, j), need)
    Dp = np.pad(D, ((0, 0), (1, 1)), mode="edge")
    D = np.max([np.roll(Dp, dk, 0)[:, 1 + dj: 1 + dj + nz] for dk in (-1, 0, 1) for dj in (-1, 0, 1)], 0)
    for _ in range(4):
        D = np.maximum(D, (np.roll(D, 1, 0) + np.roll(D, -1, 0) + np.c_[D[:, :1], D[:, :-1]] + np.c_[D[:, 1:], D[:, -1:]]) / 4)
    a2 = _ang(out, cb)
    out = out + _dir(a2) * np.maximum(0.0, _field(D, a2, out[:, 1], z_hi))[:, None]
    log("FIT %s: belt %.1f, ring r %.1f-%.1f, scale %.1f, height %.1f..%.1f, pushed max %.1f cm" % (
        g.key, B.belt, rb.min(), rb.max(), sz, out[:, 1].min(), out[:, 1].max(), D.max()))
    return out


# ---------------------------------------------------------------- weights
def _skirt_rig():
    chains = {}
    for c in SKIRT_CH:
        hs = [np.array(mc.xform("bn_%s_skirt%d" % (c, i), query=True, worldSpace=True, translation=True)) for i in range(1, 6)]
        tails = hs[1:] + [hs[4] + (hs[4] - hs[3])]
        chains[c] = (hs, tails)
    angs = sorted((math.atan2(chains[c][0][0][0], chains[c][0][0][2]) % (2 * math.pi), c) for c in SKIRT_CH)
    pivot = float(np.mean([chains[c][0][0][1] for c in SKIRT_CH]))
    return chains, angs, pivot


def skirt_weights(a, y, rig, fade=4.0):
    """{bone: w} of a point hanging at angle a and height y: the two nearest skirt chains by angle, along each its
    bones by height (each fully at its middle); above the chains' pivot the pelvis, blending in over `fade` cm."""
    chains, angs, pivot = rig
    a = a % (2 * math.pi)
    n = len(angs)
    for k in range(n):
        (a0, c0), (a1, c1) = angs[k], angs[(k + 1) % n]
        span, da = (a1 - a0) % (2 * math.pi), (a - a0) % (2 * math.pi)
        if da <= span:
            t = da / span
            break
    out = {}
    for c, wc in ((c0, 1.0 - t), (c1, t)):
        if wc <= 1e-4:
            continue
        hs, tl = chains[c]
        mids = [(h[1] + q[1]) / 2 for h, q in zip(hs, tl)]
        if y >= mids[0]:
            ws = {0: 1.0}
        elif y <= mids[4]:
            ws = {4: 1.0}
        else:
            i = max(jj for jj in range(4) if y <= mids[jj])
            u = (mids[i] - y) / (mids[i] - mids[i + 1])
            ws = {i: 1.0 - u, i + 1: u}
        for i, w in ws.items():
            b = "bn_%s_skirt%d" % (c, i + 1)
            out[b] = out.get(b, 0.0) + w * wc
    k = min(1.0, max(0.0, (pivot - y) / fade))
    k = k * k * (3 - 2 * k)
    d = {b: w * k for b, w in out.items()}
    d["body_root"] = d.get("body_root", 0.0) + (1.0 - k)
    return d


def torso_weights(P, B, tris=None):
    """Skin weights at the closest point of the body's torso (no forearms or hands) per point: (n, n_infl)."""
    TT = B.T if tris is None else tris
    A, Bv, C = B.P[TT[:, 0]], B.P[TT[:, 1]], B.P[TT[:, 2]]
    cen = (A + Bv + C) / 3
    out = np.zeros((len(P), B.W.shape[1]))
    for s in range(0, len(P), 256):
        p = P[s:s + 256]
        d2 = ((p[:, None, :] - cen[None]) ** 2).sum(-1)
        cand = np.argpartition(d2, 24, axis=1)[:, :24]
        R = wsolve.closest_on_tris(p[:, None, :], A[cand], Bv[cand], C[cand])
        dd = ((R - p[:, None, :]) ** 2).sum(-1)
        best = cand[np.arange(len(p)), dd.argmin(1)]
        q = R[np.arange(len(p)), dd.argmin(1)]
        a, b, c = A[best], Bv[best], C[best]
        v0, v1, v2 = b - a, c - a, q - a
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
        d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
        den = np.maximum(d00 * d11 - d01 * d01, 1e-12)
        bv = (d11 * d20 - d01 * d21) / den
        bw = (d00 * d21 - d01 * d20) / den
        bu = 1 - bv - bw
        tri = TT[best]
        out[s:s + 256] = (B.W[tri[:, 0]] * bu[:, None] + B.W[tri[:, 1]] * bv[:, None] + B.W[tri[:, 2]] * bw[:, None])
    return out


def weights(P, body, hang=26.0, top_only=None):
    """Top-4 (bones, weights) per vertex: the skin at its closest torso point, blending into the skirt chains as it
    hangs below the belt (0 at 2 cm under the belt line, fully the chains `hang` x 0.42 below), as the old flaps.
    top_only: vertices that follow the skin alone (a chest piece)."""
    B = body if isinstance(body, Body) else Body(body)
    TW = torso_weights(P, B)
    if top_only is not None and top_only.any():
        TW[top_only] = torso_weights(P[top_only], B, B.T_chest)
    rig = _skirt_rig()
    names = list(B.infl)
    cb = np.array([0.0, 0.0, B.cz(B.belt)])
    a = _ang(P, cb)
    rows = []
    for i, p in enumerate(P):
        t = min(1.0, max(0.0, (B.belt - 2.0 - p[1]) / hang))
        u = min(1.0, max(0.0, (t - 0.12) / 0.3))
        u = u * u * (3 - 2 * u)
        if top_only is not None and top_only[i]:
            u = 0.0
        d = {}
        for k in np.nonzero(TW[i] > 1e-4)[0]:
            d[names[k]] = d.get(names[k], 0.0) + TW[i, k] * (1 - u)
        if u > 0:
            for b, w in skirt_weights(a[i], p[1], rig).items():
                d[b] = d.get(b, 0.0) + w * u
        row = sorted(d.items(), key=lambda kv: -kv[1])[:4]
        row = [(b, w) for b, w in row if w > 0.01]
        s = sum(w for _, w in row)
        rows.append([(b, w / s) for b, w in row])
    bones = [[b for b, _ in r] + [""] * (4 - len(r)) for r in rows]
    w = np.array([[x for _, x in r] + [0.0] * (4 - len(r)) for r in rows])
    return bones, w


# ---------------------------------------------------------------- the .mesh file
def _vertex_normals(P, T, wid):
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    acc = np.zeros_like(P)
    for c in range(3):
        np.add.at(acc, wid[T[:, c]], fn)
    n = acc[wid]
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def _tangents(P, Nn, UV, T):
    """Per-vertex tangent (xyz) and handedness (w) from the UV gradients, in the file's space."""
    p0, p1, p2 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    w0, w1, w2 = UV[T[:, 0]], UV[T[:, 1]], UV[T[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    d1, d2 = w1 - w0, w2 - w0
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-12, 1e-12, r)
    sdir = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]
    tdir = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]
    tan, bit = np.zeros_like(P), np.zeros_like(P)
    for c in range(3):
        np.add.at(tan, T[:, c], sdir)
        np.add.at(bit, T[:, c], tdir)
    t = tan - Nn * (Nn * tan).sum(1, keepdims=True)
    bad = np.linalg.norm(t, axis=1) < 1e-9
    t[bad] = np.cross(Nn[bad], [0.0, 1.0, 0.0]) + 1e-6
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    w = np.where((np.cross(Nn, t) * bit).sum(1) < 0, -1.0, 1.0)
    return np.c_[t, w]


def template_mesh(sex):
    """A shipped Meshy piece of this sex: its skeleton block and layout are copied into new files."""
    return "%s/ek2lc_%s_festival_wrap_01.mesh" % (cs.OUT, sex[0])


def write_mesh(name, sex, P, g, bones, w, tset, folder=cs.OUT, shader="portrait_attachment_pattern_alpha_to_coverage"):
    """Writes <folder>/<name>.mesh from Maya-space positions P (vertex order = the garment's, so shapes and solved
    weights map 1:1 after io_pdx_mesh imports it), removing the old shape files of that name."""
    from io_pdx_mesh import pdx_data
    for f in os.listdir(folder):
        if f.startswith(name + "_bs_") and f.endswith(".mesh"):
            os.remove(os.path.join(folder, f))
    root = pdx_data.read_meshfile(template_mesh(sex))
    obj = root.find("object")
    shape = obj[0]
    shape.tag = name + "Shape"
    m = shape.find("mesh")
    skel = shape.find("skeleton")
    bi = {j.tag: int(j.attrib["ix"][0]) for j in list(skel)}
    flip = np.array([1.0, 1.0, -1.0])
    Pf = P * flip
    Tf = g.T[:, ::-1]                                   # Z negated: corners reversed keeps the faces outward
    Nf = _vertex_normals(Pf, Tf, g.wid)
    ta = _tangents(Pf, Nf, g.UV, Tf)
    m.attrib["p"] = [float(x) for x in Pf.ravel()]
    m.attrib["n"] = [float(x) for x in Nf.ravel()]
    m.attrib["ta"] = [float(x) for x in ta.ravel()]
    m.attrib["u0"] = [float(x) for x in g.UV.ravel()]
    m.attrib["tri"] = [int(x) for x in Tf.ravel()]
    lo, hi = Pf.min(0), Pf.max(0)
    m.find("aabb").attrib["min"] = [float(x) for x in lo]
    m.find("aabb").attrib["max"] = [float(x) for x in hi]
    c = (lo + hi) / 2
    m.attrib["boundingsphere"] = [float(x) for x in c] + [float(np.linalg.norm(Pf - c, axis=1).max())]
    mat = m.find("material")
    mat.attrib = {"shader": [shader], "diff": [tset + "_diffuse.dds"], "n": [tset + "_normal.dds"],
                  "spec": [tset + "_properties.dds"]}
    ix, ww = [], []
    for row, wr in zip(bones, w):
        for b, x in zip(row, wr):
            if b and x > 0:
                ix.append(bi[b])
                ww.append(float(x))
            else:
                ix.append(-1)
                ww.append(0.0)
    sk = m.find("skin")
    sk.attrib["bones"] = [4]
    sk.attrib["ix"] = ix
    sk.attrib["w"] = ww
    out = "%s/%s.mesh" % (folder, name)
    pdx_data.write_meshfile(out, root)
    return out


# ---------------------------------------------------------------- shapes
def make_shapes(name, body, folder=cs.OUT, repair=True, log=print):
    """One shape file per body shape the body has (shapes.shape_field), then shapes.repair over the shape states.
    The piece must be loaded (cs.load_piece) with no shapes yet; reloads it with them."""
    import shapes
    sex = "female" if name.startswith("ek2lc_f_") else "male"
    made = []
    for suf, attr, f in cs.body_shapes(sex):
        if not os.path.exists(f):
            continue
        G0, G1, npush = shapes.shape_field(name, body, attr)
        shapes.write_shape(name, suf, G0, G1, folder)
        made.append(suf)
    mc.delete(name)
    t = cs.load_piece(name, folder)
    log("SHAPES %s: %s" % (name, " ".join(made)))
    if repair:
        shapes.repair(name, body, shapes.repair_states(sex), folder=folder)
        mc.delete(name)
        t = cs.load_piece(name, folder)
    return t


# ---------------------------------------------------------------- textures
def textures(key, tset, size=2048, props=(0.0, 0.221, 0.0, 0.598), log=print):
    """source/meshy/<key>/ textures -> source/textures/<tset>_{diffuse,normal,properties}.png and the normal and
    properties .dds (DXT5, full mips) in the model folder. The diffuse .dds and the colour mask are written by
    tools/make_colour.py afterwards (it reads the PNG). Normal: Meshy's tangent-space map with X in alpha and Y in
    green, as the game's portrait normals (flat = 0.5, 0.5 in .ga); properties: the festival wrap's cloth values."""
    import sys
    sys.path.insert(0, cs.MOD + "/source/tools")
    import make_colour as mk
    src = os.path.join(MESHY, key)
    files = [os.path.join(r, f) for r, _, fs in os.walk(src) for f in fs if f.endswith(".png") and f != "concept.png"]
    pick = lambda *keys: next((f for k in keys for f in sorted(files) if k in os.path.basename(f).lower()), None)
    base = pick("base_color", "basecolor", "albedo")
    nrm = pick("normal")
    tex = cs.MOD + "/source/textures"

    def rd(p):
        a = mk.read_png(p)
        if a.shape[0] != size:
            tmp = os.path.join(src, "_tmp_%d.png" % size)
            import subprocess
            subprocess.run([mk.MAGICK, p, "-resize", "%dx%d!" % (size, size), tmp], check=True)
            a = mk.read_png(tmp)
            os.remove(tmp)
        return a
    d = rd(base)
    d[..., 3] = 1.0
    _png(d, "%s/%s_diffuse.png" % (tex, tset), mk)
    if nrm:
        n = rd(nrm)
        out = np.stack([np.full(n.shape[:2], 0.5), n[..., 1], np.zeros(n.shape[:2]), n[..., 0]], -1)
    else:
        out = np.broadcast_to(np.array([0.5, 0.5, 0.0, 0.5]), (size, size, 4)).copy()
    _png(out, "%s/%s_normal.png" % (tex, tset), mk)
    mk.write_dds(out.astype(np.float32), "%s/%s_normal.dds" % (cs.OUT, tset), "dxt5")
    pr = np.broadcast_to(np.array(props, float), (size, size, 4)).copy()
    _png(pr, "%s/%s_properties.png" % (tex, tset), mk)
    mk.write_dds(pr.astype(np.float32), "%s/%s_properties.dds" % (cs.OUT, tset), "dxt5")
    log("TEX %s -> %s (normal %s)" % (key, tset, "Meshy" if nrm else "flat"))


def _png(arr, path, mk):
    import subprocess
    h, w = arr.shape[:2]
    data = np.clip(np.round(arr * 255.0), 0, 255).astype(np.uint8).tobytes()
    subprocess.run([mk.MAGICK, "-size", "%dx%d" % (w, h), "-depth", "8", "rgba:-", path], input=data, check=True)


# ---------------------------------------------------------------- one piece, both bodies
SKIP_SHAPES = ("imgan", "briarheart")  # feet only / chest cavity only: nothing on a loincloth moves (2026-11-10)


def build(key, base, tset=None, sexes=("male", "female"), fit_kw=None, band_kw=None, band=True, shapes_=True,
          tex=True, strip=True, over=(), yaw=0.0, log=print):
    """source/meshy/<key> -> gfx/.../ek2lc_<m|f>_<base>_01.mesh (+ shapes, asset lines) and texture set `tset`
    (default ek2lc_<base>_01). Women get the garment's top part as a chest wrap (band=True), men never."""
    import shapes as shp
    tset = tset or "ek2lc_%s_01" % base
    rep = {}
    for sex in sexes:
        name = "ek2lc_%s_%s_01" % (sex[0], base)
        cs.new_scene()
        au._BODY.clear()
        body = cs.load_body(sex)
        obst = [cs.load_piece("ek2lc_%s_%s_01" % (sex[0], o)) for o in over]   # worn under it: fitted over them
        B = Body(body, obst)
        for o in obst:
            for x in (o, o + "_BS"):
                if mc.objExists(x):
                    mc.delete(x)
        g = load(key)
        if yaw == "auto":
            yaw = auto_yaw(g)
            log("YAW %s: %.0f deg" % (key, yaw))
        if yaw:  # Meshy took a three-quarter concept's view as the front: turn the garment round its axis
            c_, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            x, z = g.V[:, 0].copy(), g.V[:, 2].copy()
            g.V[:, 0], g.V[:, 2] = c_ * x + s_ * z, -s_ * x + c_ * z
        top = split_top(g)
        drop = crotch_mask(Sub(g, ~top)) if strip else None
        lo = Sub(g, ~top)
        if drop is not None and drop.any():
            lo = Sub(lo, ~drop)
            log("STRIP %s: %d vertices between the legs dropped" % (key, drop.sum()))
        subs, Ps = [lo], [fit(lo, B, log=log, **(fit_kw or {}))]
        if sex == "female" and band and top.any():
            hi = Sub(g, top)
            subs.append(hi)
            Ps.append(fit_band(hi, B, log=log, **(band_kw or {})))
        j = join(subs, Ps)
        top_only = np.r_[np.zeros(len(Ps[0]), bool), np.ones(len(j.V) - len(Ps[0]), bool)]
        bones, w = weights(j.V, B, top_only=top_only)
        write_mesh(name, sex, j.V, j, bones, w, tset)
        t = cs.load_piece(name)
        n_in, deep = shp.repair_base(t, body)
        repair_poke(name, body, log=log)
        mc.delete(t)
        t = cs.load_piece(name)
        made = []
        if shapes_:
            mc.delete(t)
            t = cs.load_piece(name)
            for suf, attr, f in cs.body_shapes(sex):
                if suf in SKIP_SHAPES or not os.path.exists(f):
                    continue
                G0, G1, _ = shp.shape_field(t, body, attr)
                shp.write_shape(t, suf, G0, G1)
                shp.link_assets(name, suf, attr)
                made.append(suf)
            for x in (t, t + "_BS"):
                if mc.objExists(x):
                    mc.delete(x)
            t = cs.load_piece(name)
            r = shp.repair(t, body, shp.repair_states(sex))
            rep[name] = dict(verts=len(j.V), tris=len(j.T), rest_fixed=(n_in, round(deep, 2)), shapes=made,
                             repair={k: v for k, v in r.items() if v[0] > 0})
        log("BUILT %s: %d verts, %d tris, rest pushed %d (deepest %.2f cm), %d shapes" % (
            name, len(j.V), len(j.T), n_in, deep, len(made)))
    if tex:
        textures(key, tset, log=log)
    return rep


# ---------------------------------------------------------------- weights copied from the solved Reach pieces
# The Reach pieces' hanging parts were solved over the game's poses (2026-11-07, legacy weight_solver): about 0 cm
# inside the body kneeling, on the throne and cross-legged, where plain skin-to-skirt-chain weights go 2-5 cm in.
SOLVED = ("reach_hide", "reach_king", "reach_armour", "reach_war", "reach_mantle")


def solved_reference(sex, names=SOLVED):
    """Rest positions and dense weights (over the body's bones) of the solved pieces' vertices below the belt."""
    import audit as au_
    bones = list(au_.skin_weights("BODY_%s" % sex[0])[1])
    loaded = []
    for n in names:
        nm = "ek2lc_%s_%s_01" % (sex[0], n)
        if not mc.objExists(nm):
            cs.load_piece(nm)
            loaded.append(nm)
    cs.rest_pose()
    cs.set_shape(None)
    Ps, Ws = [], []
    for n in names:
        nm = "ek2lc_%s_%s_01" % (sex[0], n)
        w, infl = au_.skin_weights(nm)
        W = np.zeros((len(w), len(bones) + 64))
        ext = list(bones)
        for k, j in enumerate(infl):
            if j not in ext:
                ext.append(j)
            W[:, ext.index(j)] += w[:, k]
        Ps.append(au_.pts(nm))
        Ws.append((W, ext))
    for nm in loaded:
        for x in (nm, nm + "_BS"):
            if mc.objExists(x):
                mc.delete(x)
    allb = sorted({b for _, e in Ws for b in e})
    bi = {b: i for i, b in enumerate(allb)}
    Wd = []
    for W, e in Ws:
        D = np.zeros((len(W), len(allb)))
        for k, b in enumerate(e):
            D[:, bi[b]] += W[:, k]
        Wd.append(D)
    return np.vstack(Ps), np.vstack(Wd), allb


def weights_from_solved(P, body, bones, w, ref=None, below=2.0, k=6, arc_r=15.0, log=print):
    """Replace the weights of vertices more than `below` cm under the belt by those of the nearest solved Reach
    vertices in (arc round the body, height) - the radius ignored, so a thick pelt gets the flap's motion - blending
    in over 4 cm. Above, the skin weights stay. Returns new (bones, w)."""
    B = body if isinstance(body, Body) else Body(body)
    RP, RW, RB = ref or solved_reference(B.sex)
    cb = np.array([0.0, 0.0, B.cz(B.belt)])
    lowr = RP[:, 1] < B.belt - below + 1.0
    RP, RW = RP[lowr], RW[lowr]
    ra = _ang(RP, cb)
    pa = _ang(P, cb)
    Rc = np.c_[np.cos(ra) * arc_r, np.sin(ra) * arc_r, RP[:, 1]]
    Pc = np.c_[np.cos(pa) * arc_r, np.sin(pa) * arc_r, P[:, 1]]
    out_b, out_w = [list(r) for r in bones], w.copy()
    t = np.clip((B.belt - below - P[:, 1]) / 4.0, 0.0, 1.0)
    idx = np.nonzero(t > 0)[0]
    for s in range(0, len(idx), 512):
        ii = idx[s:s + 512]
        d2 = ((Pc[ii, None, :] - Rc[None]) ** 2).sum(-1)
        nn = np.argpartition(d2, k, axis=1)[:, :k]
        dd = np.take_along_axis(d2, nn, 1)
        ww = 1.0 / np.maximum(dd, 0.25)
        Wn = (RW[nn] * ww[..., None]).sum(1) / ww.sum(1, keepdims=True)
        for r, v in enumerate(ii):
            d = {}
            for b, x in zip(bones[v], w[v]):
                if b and x > 0:
                    d[b] = d.get(b, 0.0) + x * (1 - t[v])
            for kk in np.nonzero(Wn[r] > 1e-3)[0]:
                d[RB[kk]] = d.get(RB[kk], 0.0) + Wn[r, kk] * t[v]
            row = sorted(d.items(), key=lambda kv: -kv[1])[:4]
            row = [(b, x) for b, x in row if x > 0.01]
            ssum = sum(x for _, x in row)
            out_b[v] = [b for b, _ in row] + [""] * (4 - len(row))
            out_w[v] = [x / ssum for _, x in row] + [0.0] * (4 - len(row))
    log("WEIGHTS from solved Reach pieces: %d of %d vertices" % (len(idx), len(P)))
    return out_b, np.array(out_w)


# ---------------------------------------------------------------- the pose solver (wsolve.py) on a proxy mesh
def proxy(P, T, cell=1.5):
    """Vertex-clustering decimation: cluster id per vertex (cells of `cell` cm), cluster centres, the triangles
    between three different clusters. The solver runs on this (a few hundred vertices instead of ~10,000)."""
    key = np.floor(P / cell).astype(np.int64)
    _, cid = np.unique(key, axis=0, return_inverse=True)
    cid = cid.ravel()
    m = cid.max() + 1
    C = np.zeros((m, 3))
    np.add.at(C, cid, P)
    C /= np.bincount(cid, minlength=m)[:, None]
    Tp = cid[T]
    ok = (Tp[:, 0] != Tp[:, 1]) & (Tp[:, 1] != Tp[:, 2]) & (Tp[:, 0] != Tp[:, 2])
    Tp = Tp[ok]
    _, u = np.unique(np.sort(Tp, 1), axis=0, return_index=True)
    return C, Tp[np.sort(u)], cid


def dump_proxy(name, sex, P, T, bones, w, cell=1.5):
    """source/build_logs/solve/piece_<name>.npz for wsolve.py: the proxy's rest points, triangles, weights."""
    d = np.load("%s/source/build_logs/solve/poses_%s.npz" % (cs.MOD, sex))
    pb = [str(b) for b in d["bones"]]
    bi = {b: k for k, b in enumerate(pb)}
    C, Tp, cid = proxy(P, T, cell)
    Wv = np.zeros((len(P), len(pb)))
    for v, (row, wr) in enumerate(zip(bones, w)):
        for b, x in zip(row, wr):
            if b and x > 0:
                Wv[v, bi[b]] += x
    W0 = np.zeros((len(C), len(pb)))
    np.add.at(W0, cid, Wv)
    W0 /= np.maximum(W0.sum(1, keepdims=True), 1e-9)
    np.savez_compressed("%s/source/build_logs/solve/piece_%s.npz" % (cs.MOD, name), rest=C, tris=Tp, W0=W0)
    np.savez_compressed("%s/source/build_logs/solve/proxy_%s.npz" % (cs.MOD, name), cid=cid, P=P, C=C)
    return len(C), len(Tp)


def run_solver(names, sex, iters=150, inits="half", ref=1.0, wait=True):
    """mayapy wsolve.py on dumped proxies, one process per piece (in parallel); returns the report lines."""
    import subprocess
    env = dict(os.environ, WS_ITERS=str(iters), WS_INITS=inits, WS_REF=str(ref))
    py = "/Applications/Autodesk/maya2027/Maya.app/Contents/bin/mayapy"
    logd = "%s/source/build_logs/solve" % cs.MOD
    procs = [(n, subprocess.Popen([py, "-I", "%s/source/maya/wsolve.py" % cs.MOD, sex, n], env=env,
                                  stdout=open("%s/log_%s.txt" % (logd, n), "w"), stderr=subprocess.STDOUT)) for n in names]
    if not wait:
        return procs
    for n, p in procs:
        p.wait()
    return [open("%s/log_%s.txt" % (logd, n)).read().strip().splitlines()[-1] for n, _ in procs]


def solved_weights(name, P, k=4):
    """The proxy's solved weights carried back to every vertex (inverse-distance over its k nearest proxy points)."""
    d = np.load("%s/source/build_logs/solve/w_%s.npz" % (cs.MOD, name))
    pr = np.load("%s/source/build_logs/solve/proxy_%s.npz" % (cs.MOD, name))
    C = pr["C"]
    nb, nw = [[str(b) for b in r] for r in d["bones"]], d["weights"]
    out_b, out_w = [], []
    for s in range(0, len(P), 1024):
        p = P[s:s + 1024]
        d2 = ((p[:, None, :] - C[None]) ** 2).sum(-1)
        nn = np.argpartition(d2, k, axis=1)[:, :k]
        dd = np.take_along_axis(d2, nn, 1)
        ww = 1.0 / np.maximum(dd, 0.04)
        ww /= ww.sum(1, keepdims=True)
        for r in range(len(p)):
            acc = {}
            for j, x in zip(nn[r], ww[r]):
                for b, y in zip(nb[j], nw[j]):
                    if y > 0:
                        acc[b] = acc.get(b, 0.0) + x * y
            row = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
            row = [(b, x) for b, x in row if x > 0.01]
            ssum = sum(x for _, x in row)
            out_b.append([b for b, _ in row] + [""] * (4 - len(row)))
            out_w.append([x / ssum for _, x in row] + [0.0] * (4 - len(row)))
    return out_b, np.array(out_w)


def repair_poke(name, body, want=0.6, passes=8, folder=cs.OUT, log=print):
    """Push the base mesh out where body vertices poke through it (Meshy's remesh leaves big flat triangles over the
    curved buttocks and belly): each poking body vertex pushes the three corners of the garment triangle in front of
    it out along its normal to `want` cm outside, spread to their neighbours. Rewrites <name>.mesh only (run it before
    the shapes are made). Returns (poking before, after, deepest before)."""
    import shapes as shp
    from io_pdx_mesh import pdx_data
    flip = np.array([1.0, 1.0, -1.0])
    f0 = "%s/%s.mesh" % (folder, name)
    root = pdx_data.read_meshfile(f0)
    m = root.find("object")[0].find("mesh")
    T = np.array(m.attrib["tri"]).reshape(-1, 3)
    P = np.array(m.attrib["p"]).reshape(-1, 3) * flip
    weld = shp._weld_ids(P * flip)
    nb = shp._neighbours(T, weld)
    cs.rest_pose()
    cs.set_shape(None)
    Bp0, Bn0 = au.pts(body), au.vnormals(body)
    arm0 = au.body_info(body)["arm"]
    BT, _ = au.tris(body)
    # the body's vertices and points on its faces (centres, edge middles): a low-res body pokes through between
    # its vertices too
    samp = [Bp0]
    nrm = [Bn0]
    armv = [arm0]
    for bc in ((1 / 3, 1 / 3, 1 / 3), (0.5, 0.5, 0.0), (0.0, 0.5, 0.5), (0.5, 0.0, 0.5)):
        samp.append(sum(Bp0[BT[:, i]] * bc[i] for i in range(3)))
        nn = sum(Bn0[BT[:, i]] * bc[i] for i in range(3))
        nrm.append(nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-12))
        armv.append(arm0[BT].any(1))
    Bp, Bn, arm = np.vstack(samp), np.vstack(nrm), np.concatenate(armv)
    first = None
    for it in range(passes):
        A, Bv, C = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
        fn = np.cross(Bv - A, C - A)
        fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
        cen = (A + Bv + C) / 3
        lo, hi = P.min(0) - 2, P.max(0) + 2
        near = np.nonzero(~arm & (Bp >= lo).all(1) & (Bp <= hi).all(1))[0]
        push = np.zeros(len(P))
        dirs = np.zeros_like(P)
        worst, n = 0.0, 0
        for s in range(0, len(near), 256):
            ii = near[s:s + 256]
            b = Bp[ii]
            d2 = ((b[:, None, :] - cen[None]) ** 2).sum(-1)
            cand = np.argpartition(d2, 12, axis=1)[:, :12]
            R = wsolve.closest_on_tris(b[:, None, :], A[cand], Bv[cand], C[cand])
            dd = ((R - b[:, None, :]) ** 2).sum(-1)
            k = dd.argmin(1)
            f = cand[np.arange(len(ii)), k]
            q = R[np.arange(len(ii)), k]
            dist = np.sqrt(dd[np.arange(len(ii)), k])
            # the body vertex is in front of the garment (outside it) if it lies on the side the body normal points to
            side = ((b - q) * Bn[ii]).sum(1)
            poke = (side > 0) & (dist < 3.0) & ((fn[f] * Bn[ii]).sum(1) > 0.2)
            for r in np.nonzero(poke)[0]:
                need = side[r] + want
                for v in T[f[r]]:
                    if need > push[v]:
                        push[v] = need
                        dirs[v] = Bn[ii[r]]
                worst = max(worst, side[r])
                n += 1
        if first is None:
            first = (n, worst)
        if n == 0:
            break
        c = shp._spread(shp.spatial_spread(P, push[:, None] * dirs), nb)
        P = P + c
    m.attrib["p"] = [float(x) for x in (P * flip).ravel()]
    n0 = np.array(m.attrib["n"]).reshape(-1, 3)
    Pf = P * flip
    m.attrib["n"] = [float(x) for x in _vertex_normals(Pf, T, weld).ravel()]
    lo_, hi_ = Pf.min(0), Pf.max(0)
    m.find("aabb").attrib["min"] = [float(x) for x in lo_]
    m.find("aabb").attrib["max"] = [float(x) for x in hi_]
    cc = (lo_ + hi_) / 2
    m.attrib["boundingsphere"] = [float(x) for x in cc] + [float(np.linalg.norm(Pf - cc, axis=1).max())]
    pdx_data.write_meshfile(f0, root)
    log("POKE %s: %d body vertices through (deepest %.2f cm), %d after %d passes" % (name, first[0], first[1], n, it + 1))
    return first[0], n, first[1]


def write_display(key, tset=None, sex="male", folder=cs.OUT, log=print):
    """The artifact window's model of a regalia piece (art_*): the worn mesh of `sex`, unskinned and centred on the
    origin, written into the existing ek2lc_<key>_artifact.mesh (vanilla's inventory artifacts are static meshes with
    the court shader); its diffuse is the original PNG (make_colour.py divides the worn piece's by its mask)."""
    import subprocess
    import sys
    from io_pdx_mesh import pdx_data
    sys.path.insert(0, cs.MOD + "/source/tools")
    import make_colour as mk
    tset = tset or "ek2lc_%s_01" % key
    src = pdx_data.read_meshfile("%s/ek2lc_%s_%s_01.mesh" % (folder, sex[0], key))
    sm = src.find("object")[0].find("mesh")
    out_p = "%s/ek2lc_%s_artifact.mesh" % (folder, key)
    root = pdx_data.read_meshfile(out_p)
    m = root.find("object")[0].find("mesh")
    P = np.array(sm.attrib["p"]).reshape(-1, 3)
    P = P - P.mean(0)
    m.attrib["p"] = [float(x) for x in P.ravel()]
    for k in ("n", "ta", "u0", "tri"):
        m.attrib[k] = list(sm.attrib[k])
    lo, hi = P.min(0), P.max(0)
    m.find("aabb").attrib["min"] = [float(x) for x in lo]
    m.find("aabb").attrib["max"] = [float(x) for x in hi]
    c = (lo + hi) / 2
    m.attrib["boundingsphere"] = [float(x) for x in c] + [float(np.linalg.norm(P - c, axis=1).max())]
    if m.find("skin") is not None:
        m.remove(m.find("skin"))
    pdx_data.write_meshfile(out_p, root)
    subprocess.run([mk.MAGICK, "%s/source/textures/%s_diffuse.png" % (cs.MOD, tset), "-define", "dds:compression=dxt5",
                    "-define", "dds:mipmaps=10", "%s/%s_display_diffuse.dds" % (folder, tset)], check=True)
    log("DISPLAY %s: %d verts" % (key, len(P)))

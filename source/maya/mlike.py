"""Meshy pieces that don't hang from the hips, fitted by the living piece they stand in for (2026-11-10, the lich
remakes): a tunic, leggings, capes, a shoulder guard. And chest bands alone (women's tops worn as their own gene).

    import mlike as ml
    ml.retarget("ek2lc_m_lich_mantle_01")                  # the .asset onto its own mesh and texture set first
    ml.build_like("lich_mantle", "lich_mantle", "reach_mantle", kind="cape")
    ml.build_band("lich_band", "lich_band")                 # women only

build_like: the Meshy garment's box scaled per axis onto the living piece's box (legs: each leg's half onto the
living piece's same half), pulled in where it stands off the body more than `slack` (both layers of a two-sided
shell by the same amount: the local minimum distance decides), pushed out to `gap` outside the body (spread so both
layers move), then the living piece's own weights at the closest point of it (the Reach set's were solved over the
game's poses). Shapes and repairs as mbuild.build.
"""
import math
import os
import re
import numpy as np
import maya.cmds as mc
import ck3scene as cs
import audit as au
import mbuild as mb
import shapes as shp
import wsolve

KINDS = {  # gap, tight, slack, halves, yaw
    "torso": dict(gap=0.5, tight=0.6, slack=1.2, halves=False),
    "legs": dict(gap=0.35, tight=0.8, slack=0.8, halves=True),
    "cape": dict(gap=0.8, tight=0.0, slack=99.0, halves=False),
    "shoulder": dict(gap=0.6, tight=0.5, slack=1.5, halves=False),
}


# ---------------------------------------------------------------- the .asset
def retarget(asset, folder=cs.OUT):
    """Point <asset>.asset at its own mesh (<asset>.mesh, shapes <asset>_bs_*.mesh) and texture set
    (ek2lc_<key>_01, key = the asset name without ek2lc_<m|f>_ and _01). Returns the texture set."""
    p = "%s/%s.asset" % (folder, asset)
    raw = open(p, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    t = raw.decode("utf-8-sig")
    tset = "ek2lc_%s_01" % re.match(r"ek2lc_[mf]_(.+)_01$", asset).group(1)
    t = re.sub(r'(\tfile = ")[^"]+(\.mesh")', r"\g<1>%s\2" % asset, t, count=1)
    t = re.sub(r'(type = ")[^"]+?(_bs_[a-z_0-9]+\.mesh")', r"\g<1>%s\2" % asset, t)
    t = re.sub(r'(meshsettings = \{\s*name = ")[^"]+(")', r"\g<1>%sShape\2" % asset, t, count=1)
    for k, s in (("diffuse", "diffuse"), ("normal", "normal"), ("specular", "properties")):
        t = re.sub(r'(texture_%s = ")[^"]+(")' % k, r"\g<1>%s_%s.dds\2" % (tset, s), t, count=1)
    open(p, "wb").write((b"\xef\xbb\xbf" if bom else b"") + t.encode("utf-8"))
    return tset


# ---------------------------------------------------------------- geometry
def _closest(P, A, B, C, k=24):
    """Closest point on the triangles (A, B, C) per point: (points, triangle index, barycentric u v w)."""
    cen = (A + B + C) / 3
    Q = np.zeros_like(P)
    ti = np.zeros(len(P), np.int64)
    for s in range(0, len(P), 256):
        p = P[s:s + 256]
        d2 = ((p[:, None, :] - cen[None]) ** 2).sum(-1)
        kk = min(k, len(cen) - 1)
        cand = np.argpartition(d2, kk, axis=1)[:, :kk]
        R = wsolve.closest_on_tris(p[:, None, :], A[cand], B[cand], C[cand])
        dd = ((R - p[:, None, :]) ** 2).sum(-1)
        j = dd.argmin(1)
        ti[s:s + 256] = cand[np.arange(len(p)), j]
        Q[s:s + 256] = R[np.arange(len(p)), j]
    a, b, c = A[ti], B[ti], C[ti]
    v0, v1, v2 = b - a, c - a, Q - a
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-12)
    bv = (d11 * d20 - d01 * d21) / den
    bw = (d00 * d21 - d01 * d20) / den
    return Q, ti, np.c_[1 - bv - bw, bv, bw]


class Skin:
    """The body's surface (rest pose, no shapes) without forearms and hands, plus pieces worn under: signed
    distance and outward normal at the closest point."""

    def __init__(self, body, over=()):
        cs.rest_pose()
        cs.set_shape(None)
        P, N = au.pts(body), au.vnormals(body)
        T, _ = au.tris(body)
        T = T[~au.body_info(body)["arm"][T].any(1)]
        Ps, Ns, Ts, off = [P], [N], [T], len(P)
        for o in over:
            Po, No = au.pts(o), au.vnormals(o)
            To, _ = au.tris(o)
            Ps.append(Po)
            Ns.append(No)
            Ts.append(To + off)
            off += len(Po)
        self.P, self.N, self.T = np.vstack(Ps), np.vstack(Ns), np.vstack(Ts)

    def dist(self, X):
        Q, ti, bc = _closest(X, self.P[self.T[:, 0]], self.P[self.T[:, 1]], self.P[self.T[:, 2]])
        n = sum(self.N[self.T[ti, i]] * bc[:, i:i + 1] for i in range(3))
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        return ((X - Q) * n).sum(1), n


def _local_min(P, d, r):
    out = d.copy()
    for s in range(0, len(P), 256):
        dd = ((P[s:s + 256, None, :] - P[None]) ** 2).sum(-1)
        out[s:s + 256] = np.where(dd <= r * r, d[None, :], np.inf).min(1)
    return out


def _box_map(V, lo, hi, rlo, rhi):
    return rlo + (V - lo) / np.maximum(hi - lo, 1e-6) * (rhi - rlo)


def align(V, R, halves=False):
    """V's box onto R's box, per axis; halves: the x < middle and x > middle halves each onto R's x < 0 / x > 0."""
    if not halves:
        return _box_map(V, V.min(0), V.max(0), R.min(0), R.max(0))
    out = V.copy()
    mid = (V[:, 0].min() + V[:, 0].max()) / 2
    for side in (-1, 1):
        m = (V[:, 0] - mid) * side > 0
        r = R[R[:, 0] * side > 0]
        out[m] = _box_map(V[m], V[m].min(0), V[m].max(0), r.min(0), r.max(0))
    return out


def fit_like(g, skin, R, gap=0.5, tight=0.5, slack=1.5, halves=False, yaw=0.0, passes=3, log=print):
    V = g.V.copy()
    if yaw:
        c_, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        x, z = V[:, 0].copy(), V[:, 2].copy()
        V[:, 0], V[:, 2] = c_ * x + s_ * z, -s_ * x + c_ * z
    P = align(V, R, halves)
    d, n = skin.dist(P)
    if tight > 0:
        dm = _local_min(P, d, 2.5)
        pull = np.maximum(dm - slack, 0.0) * tight
        P = P - n * pull[:, None]
        log("PULL %s: up to %.1f cm (median %.1f)" % (g.key, pull.max(), np.median(pull)))
    pushed = 0.0
    for _ in range(passes):
        d, n = skin.dist(P)
        need = np.maximum(gap - d, 0.0)
        if need.max() < 0.02:
            break
        P = P + shp.spatial_spread(P, n * need[:, None])
        pushed = max(pushed, need.max())
    d, _ = skin.dist(P)
    log("FIT %s: box %s, pushed to %.1f cm, inside after %d" % (g.key, np.round(P.max(0) - P.min(0), 1), pushed, (d < 0).sum()))
    return P


# ---------------------------------------------------------------- weights
def ref_piece(name):
    """Rest points, triangles and dense weights (n, bones) of a loaded or loadable piece."""
    made = not mc.objExists(name)
    if made:
        cs.load_piece(name)
    cs.rest_pose()
    cs.set_shape(None)
    P = au.pts(name)
    T, _ = au.tris(name)
    W, infl = au.skin_weights(name)
    if made:
        for x in (name, name + "_BS"):
            if mc.objExists(x):
                mc.delete(x)
    return P, T, W, list(infl)


def weights_like(P, ref):
    """Top-4 (bones, weights) per point: the reference piece's weights at its closest point."""
    RP, RT, RW, RB = ref
    _, ti, bc = _closest(P, RP[RT[:, 0]], RP[RT[:, 1]], RP[RT[:, 2]])
    W = sum(RW[RT[ti, i]] * bc[:, i:i + 1] for i in range(3))
    bones, w = [], []
    for row in W:
        k = np.argsort(-row)[:4]
        k = [i for i in k if row[i] > 0.01]
        s = sum(row[i] for i in k)
        bones.append([RB[i] for i in k] + [""] * (4 - len(k)))
        w.append([row[i] / s for i in k] + [0.0] * (4 - len(k)))
    return bones, np.array(w)


# ---------------------------------------------------------------- builds
def _scene(sex, over):
    cs.new_scene()
    au._BODY.clear()
    body = cs.load_body(sex)
    obst = [cs.load_piece("ek2lc_%s_%s_01" % (sex[0], o)) for o in over]
    return body, obst


def _drop(objs):
    for o in objs:
        for x in (o, o + "_BS"):
            if mc.objExists(x):
                mc.delete(x)


def build_like(key, base, ref_base, kind, sexes=("male", "female"), over=(), tset=None, yaw=0.0, tex=True, log=print,
               **kw):
    """source/meshy/<key> -> ek2lc_<m|f>_<base>_01.mesh fitted like ek2lc_<m|f>_<ref_base>_01, + shapes; textures."""
    opts = dict(KINDS[kind])
    opts.update(kw)
    tset = tset or "ek2lc_%s_01" % base
    rep = {}
    for sex in sexes:
        name = "ek2lc_%s_%s_01" % (sex[0], base)
        body, obst = _scene(sex, over)
        skin = Skin(body, obst)
        _drop(obst)
        ref = ref_piece("ek2lc_%s_%s_01" % (sex[0], ref_base))
        g = mb.load(key)
        P = fit_like(g, skin, ref[0], yaw=yaw, log=log, **opts)
        bones, w = weights_like(P, ref)
        mb.write_mesh(name, sex, P, g, bones, w, tset)
        skip = () if kind == "legs" else None   # leggings reach the feet: Imga's shape moves them
        rep[name] = mb.finish(name, sex, body, len(P), len(g.T), skip=skip, log=log)
    if tex:
        mb.textures(key, tset, log=log)
    return rep


def build_band(key, base, tset=None, tex=True, log=print, **band_kw):
    """source/meshy/<key> -> ek2lc_f_<base>_01.mesh: the whole garment as a chest wrap (mbuild.fit_band), on the
    chest and spine skin only."""
    tset = tset or "ek2lc_%s_01" % base
    name = "ek2lc_f_%s_01" % base
    body, _ = _scene("female", ())
    B = mb.Body(body)
    g = mb.load(key)
    P = mb.fit_band(g, B, log=log, **band_kw)
    bones, w = mb.weights(P, B, top_only=np.ones(len(P), bool))
    mb.write_mesh(name, "female", P, g, bones, w, tset)
    rep = {name: mb.finish(name, "female", body, len(P), len(g.T), log=log)}
    if tex:
        mb.textures(key, tset, log=log)
    return rep

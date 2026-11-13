"""Kneel shapes (2026-11-12): pose-space shapes for the two kneeling animations, switched on by the animation
entries themselves, as vanilla does for thrones (seated.py):

  gfx/portraits/portrait_animations/zz_ek2lc_kneel.txt   throne_room_kneel_1/_2 + `ek2lc_pose = kneel1/kneel2`
  gfx/portraits/portrait_modifiers/ek2lc_pose.txt        morph gene_ek2lc_kneel1/2 -> 1, the _fat ones by weight
  common/genes/ek2lc_pose_genes.txt                      attributes: EK2's unused whiskers_* (see POSES)
  <piece>_bs_kneel1.mesh / _bs_kneel2.mesh               made here, linked in the piece's .asset files

Why a shape and not weights: at the hip crease of a raised thigh the body runs through itself (the thigh's top
passes into the belly), and no blend of the pelvis' and the thigh's transforms puts a belt vertex into the free
corner above the crease (wfix.py / wsolve.py only halved the depth and moved the standing look).

What is different from the throne drape:
  - the body is treated as ONE solid (`Solid`): inside/outside by the winding number (signed crossings of rays
    through the closed body), then an exact distance transform on a 0.5 cm grid. The closest-triangle test
    (wfix._sd) calls a belt vertex "outside" when it sits just in front of belly skin that is itself buried in
    the thigh; here it is inside, and the gradient leads out of both;
  - the belt is not pinned: every node is pushed out of the solid; belt nodes are pulled back to where the skin
    weights put them, so they move only where they collide;
  - a vertex is asked for the clearance it has at rest (at most `gap`), so parts that sit in the skin at rest
    are left alone;
  - the body is taken from the rest pose into the kneel in STEPS small steps (`path`), the cloth solved at each:
    solved in the final pose alone, a flap that hangs through the raised thigh leaves it upwards on one side of
    the thigh's middle and downwards on the other, and tears. Carried along, it rides up on the thigh as one sheet.

    import kneel; kneel.make("ek2lc_m_lich_king_01", "male", "kneel1")     # mayapy or Maya; needs pose_dump's npz
    kneel.run_all()
"""
import os
import numpy as np
import ck3scene as cs
import mbuild as mb
import shapes as shp
import seated
import wfix
import wsolve

# The game only resolves a gene's attribute if the BODY or HEAD entity declares it (genedatabase: "could not find
# attribute", seen 2026-11-12; vanilla declares bs_body_seated on the body for this). We may not edit those files, so
# the kneel genes drive four attributes EK2's heads declare with a neutral shape and nothing else uses (no gene, no
# other model): its unused whiskers_* names. If EK2 ever gives them a gene, pick other free ones (kneel.free_attrs()).
POSES = {"kneel1": ("throneRoom_kneel1_1", "whiskers_thin_1"), "kneel2": ("throneRoom_kneel2_1", "whiskers_thin_2")}
VARIANT_ATTR = {("kneel1", "fat"): "whiskers_droop", ("kneel2", "fat"): "whiskers_wavy"}
SKIP = ("leggings",)     # skin-tight leg wear folds with the skin at the knee: pushing it out of the fold tears it
H = 0.5
STEPS = 16
_SOLID = {}
_PATH = {}


# ---------------------------------------------------------------- the body as one solid
def _closed(P, T, rest):
    """Points and triangles plus a fan over every open end (the neck, the cut forearms): a closed surface.
    Topology by rest position (the body's vertices are split along UV seams)."""
    _, wid = np.unique(np.round(rest, 3), axis=0, return_inverse=True)
    wid = wid.ravel()
    Ev = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    Ew = wid[Ev]
    have = set(map(tuple, Ew.tolist()))
    nxt = {}
    for (a, b), (va, vb) in zip(Ew.tolist(), Ev.tolist()):
        if a != b and (b, a) not in have:
            nxt[a] = (b, va, vb)
    Ps, Ts, n, seen = [P], [T], len(P), set()
    for a0 in list(nxt):
        loop, a = [], a0
        while a in nxt and a not in seen:
            seen.add(a)
            b, va, vb = nxt[a]
            loop.append((va, vb))
            a = b
        if len(loop) < 3:
            continue
        Ps.append(P[[va for va, _ in loop]].mean(0)[None])
        Ts.append(np.array([[vb, va, n] for va, vb in loop]))
        n += 1
    return np.vstack(Ps), np.vstack(Ts)


def _winding(P, T, lo, n, h):
    """Winding number at every cell centre: signed crossings of the +z ray through each (x, y) column, summed
    up the column. Also the total per column (0 for a closed surface)."""
    nx, ny, nz = n
    D = np.zeros((nx, ny, nz + 1), np.int16)
    tot = np.zeros((nx, ny), np.int16)
    A, B, C = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    a, b, c = [(V[:, :2] - lo[:2]) / h - 0.5 for V in (A, B, C)]
    area = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    mn = np.ceil(np.minimum(np.minimum(a, b), c)).astype(int)
    mx = np.floor(np.maximum(np.maximum(a, b), c)).astype(int)
    for t in np.nonzero((np.abs(area) > 1e-9) & (mx[:, 0] >= 0) & (mx[:, 1] >= 0) & (mn[:, 0] < nx) & (mn[:, 1] < ny))[0]:
        i0, i1 = max(mn[t, 0], 0), min(mx[t, 0], nx - 1)
        j0, j1 = max(mn[t, 1], 0), min(mx[t, 1], ny - 1)
        if i0 > i1 or j0 > j1:
            continue
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing="ij")
        px, py = ii - a[t, 0], jj - a[t, 1]
        w1 = (px * (c[t, 1] - a[t, 1]) - py * (c[t, 0] - a[t, 0])) / area[t]
        w2 = (py * (b[t, 0] - a[t, 0]) - px * (b[t, 1] - a[t, 1])) / area[t]
        w0 = 1 - w1 - w2
        m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not m.any():
            continue
        z = w0[m] * A[t, 2] + w1[m] * B[t, 2] + w2[m] * C[t, 2]
        k0 = np.clip(np.ceil((z - lo[2]) / h - 0.5).astype(int), 0, nz)
        s = -1 if area[t] > 0 else 1          # normal towards +z: the ray leaves the solid there
        np.add.at(D, (ii[m], jj[m], k0), s)
        np.add.at(tot, (ii[m], jj[m]), s)
    return np.cumsum(D[:, :, :nz], axis=2), tot


def _edt(src, R):
    """Exact Euclidean distance (in cells) to the nearest True cell, capped at R + 1: one pass per axis."""
    n = src.shape[2]
    idx = np.arange(n, dtype=np.float32)
    fwd = np.maximum.accumulate(np.where(src, idx, -np.inf), axis=2)
    bwd = np.minimum.accumulate(np.where(src, idx, np.inf)[..., ::-1], axis=2)[..., ::-1]
    g = np.minimum(np.minimum(idx - fwd, bwd - idx), R + 1.0).astype(np.float32)
    d2 = g * g
    for ax in (1, 0):
        out = d2.copy()
        for o in range(1, R + 1):
            sa, sb = [slice(None)] * 3, [slice(None)] * 3
            sa[ax], sb[ax] = slice(o, None), slice(None, -o)
            sa, sb = tuple(sa), tuple(sb)
            np.minimum(out[sa], d2[sb] + o * o, out=out[sa])
            np.minimum(out[sb], d2[sa] + o * o, out=out[sb])
        d2 = out
    return np.sqrt(d2)


class Solid:
    """Signed distance (cm, negative inside) to a posed body as one solid, sampled from a grid of h cm cells."""

    def __init__(self, P, T, rest, lo, hi, h=H, r_in=24, r_out=8):
        Pc, Tc = _closed(np.asarray(P, float), np.asarray(T, int), rest)
        self.h = h
        self.lo = np.asarray(lo, float) + 0.137 * h          # off the vertices' round numbers
        self.n = np.ceil((np.asarray(hi, float) - self.lo) / h).astype(int)
        W, tot = _winding(Pc, Tc, self.lo, self.n, h)
        if (W < 0).sum() > (W > 0).sum():
            W = -W
        self.open_cols = float((tot != 0).mean())
        inside = W >= 1
        self.sd = (np.where(inside, -(_edt(~inside, r_in) - 0.5), _edt(inside, r_out) - 0.5) * h).astype(np.float32)

    def sample(self, X):
        """Signed distance and the unit way out at X (points off the grid: far outside)."""
        n = self.n
        f = (X - self.lo) / self.h - 0.5
        ok = ((f >= 0) & (f <= n - 1.001)).all(1)
        fc = np.clip(f, 0, n - 1.001)
        i = np.floor(fc).astype(int)
        tx, ty, tz = (fc - i).T
        x, y, z = i.T
        c = [[[self.sd[x + a, y + b, z + d] for d in (0, 1)] for b in (0, 1)] for a in (0, 1)]
        ux, uy, uz = 1 - tx, 1 - ty, 1 - tz
        sd = (c[0][0][0] * ux * uy * uz + c[1][0][0] * tx * uy * uz + c[0][1][0] * ux * ty * uz + c[1][1][0] * tx * ty * uz +
              c[0][0][1] * ux * uy * tz + c[1][0][1] * tx * uy * tz + c[0][1][1] * ux * ty * tz + c[1][1][1] * tx * ty * tz)
        gx = ((c[1][0][0] - c[0][0][0]) * uy * uz + (c[1][1][0] - c[0][1][0]) * ty * uz +
              (c[1][0][1] - c[0][0][1]) * uy * tz + (c[1][1][1] - c[0][1][1]) * ty * tz)
        gy = ((c[0][1][0] - c[0][0][0]) * ux * uz + (c[1][1][0] - c[1][0][0]) * tx * uz +
              (c[0][1][1] - c[0][0][1]) * ux * tz + (c[1][1][1] - c[1][0][1]) * tx * tz)
        gz = ((c[0][0][1] - c[0][0][0]) * ux * uy + (c[1][0][1] - c[1][0][0]) * tx * uy +
              (c[0][1][1] - c[0][1][0]) * ux * ty + (c[1][1][1] - c[1][1][0]) * tx * ty)
        g = np.c_[gx, gy, gz]
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
        return np.where(ok, sd, 99.0), g


def _solid_of(sex, B):
    """The solid of body points B. The box holds the legs and the torso up to 45 cm over the hips (hands and
    forearms are no part of it, as in every other tool here)."""
    S = wfix.poses(sex)
    J = seated.S_joints(sex)
    hip_y = (J["bn_l_hip"][1] + J["bn_r_hip"][1]) / 2
    used = np.zeros(len(B), bool)
    used[np.unique(S["tris"])] = True
    low = used & (S["rest"][:, 1] < hip_y + 45)
    return Solid(B, S["tris"], S["rest"], B[low].min(0) - 10, B[low].max(0) + 10)


def _pts(path):
    """A .mesh file's points in Maya space."""
    from io_pdx_mesh import pdx_data
    m = pdx_data.read_meshfile(path).find("object")[0].find("mesh")
    return np.array(m.attrib["p"]).reshape(-1, 3) * np.array([1.0, 1.0, -1.0])


_REST = {}


def body_rest(sex, variant="base"):
    """The body's rest points: "base", or "fat" (vanilla's bs_body_fat_1 target at 1: the heaviest body, which the
    game blends in by weight_for_portrait for overweight characters)."""
    if (sex, variant) not in _REST:
        S = wfix.poses(sex)
        if variant == "base":
            B = S["rest"]
        else:
            B = _pts("%s/gfx/models/portraits/%s_body/blendshapes/%s_bs_body_%s_1.mesh" % (cs.GAME, sex, sex, variant))
            assert B.shape == S["rest"].shape and np.abs(B - S["rest"]).max() < 30, "body shape file does not match"
        _REST[(sex, variant)] = B
    return _REST[(sex, variant)]


def posed_body(sex, k, variant="base", M=None):
    S = wfix.poses(sex)
    if variant == "base" and M is None:
        return S["body"][k]
    return wfix.lbs(body_rest(sex, variant), S["W"], S["mats"][k] if M is None else M)


def solid(sex, k=None, log=print, variant="base"):
    """The solid of pose k of the pose dump (None: the rest pose) for a body variant, cached."""
    if (sex, k, variant) not in _SOLID:
        S = wfix.poses(sex)
        s = _solid_of(sex, body_rest(sex, variant) if k is None else posed_body(sex, k, variant))
        log("SOLID %s %s %s: grid %s, %.1f%% inside, open columns %.2f%%" % (sex, variant,
            "rest" if k is None else S["names"][k], "x".join(map(str, s.n)), 100 * (s.sd < 0).mean(), 100 * s.open_cols))
        _SOLID[(sex, k, variant)] = s
    return _SOLID[(sex, k, variant)]


def _axis_angle(R):
    U, _, Vt = np.linalg.svd(R)
    R = U @ Vt
    ang = np.arccos(np.clip((np.trace(R, axis1=1, axis2=2) - 1) / 2, -1.0, 1.0))
    ax = np.stack([R[:, 2, 1] - R[:, 1, 2], R[:, 0, 2] - R[:, 2, 0], R[:, 1, 0] - R[:, 0, 1]], 1)
    ln = np.linalg.norm(ax, axis=1, keepdims=True)
    return np.where(ln > 1e-8, ax / np.maximum(ln, 1e-12), np.array([1.0, 0.0, 0.0])), ang


def path(sex, k, log=print, variant="base"):
    """[(bone matrices, Solid)] from just off the rest pose to pose k: every bone's rotation grows about its own
    joint, the joint moves in a straight line (bones change length a little on the way; the last step is the
    dumped pose itself). Cached for one sex at a time (16 grids of ~28 MB per pose)."""
    if (sex, k, variant) not in _PATH:
        for key in [q for q in _PATH if q[0] != sex or q[2] != variant]:
            del _PATH[key]
        S = wfix.poses(sex)
        J = seated.S_joints(sex)
        c = np.array([J[b] for b in S["bones"]])
        M = S["mats"][k]
        ax, ang = _axis_angle(M[:, :3, :3])
        K = np.zeros((len(c), 3, 3))
        K[:, 0, 1], K[:, 0, 2], K[:, 1, 0] = -ax[:, 2], ax[:, 1], ax[:, 2]
        K[:, 1, 2], K[:, 2, 0], K[:, 2, 1] = -ax[:, 0], -ax[:, 1], ax[:, 0]
        c1 = np.einsum("jab,jb->ja", M[:, :3, :3], c) + M[:, :3, 3]
        out = []
        for i in range(1, STEPS + 1):
            f = i / STEPS
            if i == STEPS:
                out.append((M, solid(sex, k, log, variant)))
                break
            a = (ang * f)[:, None, None]
            Rt = np.eye(3)[None] + np.sin(a) * K + (1 - np.cos(a)) * (K @ K)
            Mt = np.tile(np.eye(4), (len(c), 1, 1))
            Mt[:, :3, :3] = Rt
            Mt[:, :3, 3] = c + f * (c1 - c) - np.einsum("jab,jb->ja", Rt, c)
            out.append((Mt, _solid_of(sex, posed_body(sex, k, variant, Mt))))
        log("PATH %s %s %s: %d steps" % (sex, variant, S["names"][k], STEPS))
        _PATH[(sex, k, variant)] = out
    return _PATH[(sex, k, variant)]


# ---------------------------------------------------------------- the shape
def relax(X0, Gp, edges, L, hang, want, sol, floor=-1e9, iters=12, g=0.0, sub=4, keep=0.5):
    """Position-based cloth on the proxy: every node leaves the solid by `want` cm; an edge may take any length
    between its posed and its rest length (skinning crumples and stretches cloth: it may smooth out, but nothing
    new is stretched or squeezed), so nodes that touch nothing do not move at all. Belt nodes (hang 0) are heavy and
    pulled back to their posed place. With g > 0 the hanging nodes also fall, tethered to the belt node they hang
    from by their cloth distance (a full re-drape; off by default: the clip's skirt bones already place the flaps)."""
    X = X0.copy()
    im = 0.1 + 0.9 * hang
    gd, root = seated._geodesic(len(X), edges, L, hang <= 0)
    teth = (hang > 0) & np.isfinite(gd) & (root >= 0) & (g > 0)
    e0, e1 = edges[:, 0], edges[:, 1]
    wsum = im[e0] + im[e1]
    Lp = np.linalg.norm(Gp[e1] - Gp[e0], axis=1)
    l_lo, l_hi = np.minimum(L, Lp), np.maximum(L, Lp)
    for _ in range(iters):
        X[:, 1] -= g * hang
        X += (keep * (1 - hang))[:, None] * (Gp - X)
        for _ in range(sub):
            d = X[e1] - X[e0]
            ln = np.maximum(np.linalg.norm(d, axis=1), 1e-6)
            c = ((ln - np.clip(ln, l_lo, l_hi)) / ln / wsum)[:, None] * d
            acc = np.zeros_like(X)
            cnt = np.zeros(len(X))
            np.add.at(acc, e0, c * im[e0, None])
            np.add.at(acc, e1, -c * im[e1, None])
            np.add.at(cnt, e0, 1)
            np.add.at(cnt, e1, 1)
            X += acc / np.maximum(cnt, 1)[:, None]
            r = X[teth] - X[root[teth]]
            rl = np.linalg.norm(r, axis=1)
            over = rl > gd[teth] * 1.02
            if over.any():
                idx = np.nonzero(teth)[0][over]
                X[idx] = X[root[idx]] + r[over] * (gd[idx] * 1.02 / rl[over])[:, None]
        sd, way = sol.sample(X)
        X += way * np.where(sd < want, _target(want) - sd, 0.0)[:, None]
        X[:, 1] = np.maximum(X[:, 1], np.where(hang > 0, floor, -1e9))
    return X


def _vnormals(X, T):
    n = np.cross(X[T[:, 1]] - X[T[:, 0]], X[T[:, 2]] - X[T[:, 0]])
    N = np.zeros_like(X)
    for c in range(3):
        np.add.at(N, T[:, c], n)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def unpoke(X, T, body, bnrm, used, margin=0.6, r=2.0, passes=3):
    """The other way round (audit.measure's poke test): body vertices standing in front of the cloth over them
    (a heel or knee between cloth vertices, where no cloth vertex is inside). The nearest cloth vertex and its
    neighbours within 2.5 cm are pushed out past the body vertex by `margin`. Returns the added move (V x 3)."""
    D = np.zeros_like(X)
    B, NB = body[used], bnrm[used]
    for _ in range(passes):
        Y = X + D
        lo, hi = Y.min(0) - r, Y.max(0) + r
        near = np.all((B > lo) & (B < hi), axis=1)
        if not near.any():
            break
        b, nb = B[near], NB[near]
        o = wsolve.Obstacle(Y, T)
        o.refresh(b)
        TT = o.T[o.cand]
        A_, B_, C_ = Y[TT[..., 0]], Y[TT[..., 1]], Y[TT[..., 2]]
        R = wsolve.closest_on_tris(np.broadcast_to(b[:, None, :], A_.shape), A_, B_, C_)
        dd = np.linalg.norm(b[:, None, :] - R, axis=-1)
        kk = dd.argmin(1)
        i_ = np.arange(len(b))
        tri, q, dist = o.cand[i_, kk], R[i_, kk], dd[i_, kk]
        nc = o.N[tri]
        cos = (nc * nb).sum(1)
        nc = nc * np.sign(cos)[:, None]
        along = ((b - q) * nc).sum(1)
        bad = (along > 0.15) & (dist < r) & (along > 0.7 * dist) & (np.abs(cos) > 0.5)
        push = np.zeros_like(Y)
        for i in np.nonzero(bad)[0]:
            v = nc[i] * (along[i] + margin)
            for c in o.T[tri[i]]:
                if np.linalg.norm(v) > np.linalg.norm(push[c]):
                    push[c] = v
        hit = int(bad.sum())
        if not hit:
            break
        D = D + shp.spatial_spread(Y, push)
    return D


def _smoother(P, T):
    """Laplacian smoothing of a per-vertex move over the mesh, welded by rest position (both layers of a two-sided
    panel are one node). Only moved nodes and their neighbours change; the rest stays at 0."""
    _, wid = np.unique(np.round(P, 3), axis=0, return_inverse=True)
    wid = wid.ravel()
    n = wid.max() + 1
    e = wid[wsolve.mesh_edges(T)]
    e = e[e[:, 0] != e[:, 1]]
    deg = np.bincount(e.ravel(), minlength=n).astype(float)
    cnt = np.bincount(wid, minlength=n).astype(float)

    def run(D, iters):
        Dw = np.stack([np.bincount(wid, weights=D[:, a], minlength=n) for a in range(3)], 1) / cnt[:, None]
        live = np.linalg.norm(Dw, axis=1) > 1e-4
        live[e[live[e[:, 0]], 1]] = True
        live[e[live[e[:, 1]], 0]] = True
        for _ in range(iters):
            acc = np.zeros_like(Dw)
            np.add.at(acc, e[:, 0], Dw[e[:, 1]])
            np.add.at(acc, e[:, 1], Dw[e[:, 0]])
            Dw = np.where(live[:, None], 0.5 * Dw + 0.5 * acc / np.maximum(deg, 1)[:, None], Dw)
        return Dw[wid]
    return run


def _target(want, margin=0.6):
    """Where a point that has come closer to the body than at rest is put: `margin` cm out (cloth that only just
    clears the low-res body shows it between its vertices); parts that sit in the skin at rest keep their depth."""
    return np.where(want >= 0.0, np.maximum(want, margin), want)


def _inside(sol, X, want):
    """How far each point is short of its wanted clearance (cm)."""
    sd, _ = sol.sample(X)
    return np.maximum(want - sd, 0.0)


def make(name, sex, key, variant="base", gap=0.6, cell=1.5, g=0.0, smooth_rounds=6, smooth_iters=6, log=print, write=True):
    """The kneel shape of one piece. variant "fat": the extra move a heavy body needs (`<key>_fat`, attribute
    `bs_ek2lc_<key>_fat`, set to weight_for_portrait for overweight characters), solved on top of the piece's own
    fat shape and its plain kneel shape, against the heaviest body."""
    clip, attr = POSES[key]
    suffix = key if variant == "base" else "%s_%s" % (key, variant)
    attr = attr if variant == "base" else VARIANT_ATTR[(key, variant)]
    S = wfix.poses(sex)
    fr = [i for i, n in enumerate(S["names"]) if n.split(":")[0] == clip]
    k = fr[len(fr) // 2]
    root, m, skel, P, ix, w = wfix._read(name)
    T = np.array(m.attrib["tri"]).reshape(-1, 3)
    Wc = wfix._dense(ix, w, skel, S["bones"])
    chain = np.array([("skirt" in b) or ("cloak" in b) for b in S["bones"]])
    cw = Wc[:, chain].sum(1)
    M = S["mats"][k]
    off_v = np.zeros_like(P)    # the piece's own shape for this body variant (rest space)
    off_k = np.zeros_like(P)    # and its plain kneel shape, under the variant's extra
    if variant != "base":
        for o, suf in ((off_v, variant), (off_k, key)):
            f = "%s/%s_bs_%s.mesh" % (cs.OUT, name, suf)
            if os.path.exists(f):
                o += _pts(f) - P
    G = wfix.lbs(P + off_v + off_k, Wc, M)
    sol = solid(sex, k, log, variant)
    # the clearance each vertex has at rest (at most gap; never asked to come out further than it is at rest)
    want = np.clip(solid(sex, None, log, variant).sample(P + off_v)[0], -1.0, gap)
    short0 = _inside(sol, G, want)
    if short0.max() < 0.15 and (cw.max() < 0.05 or variant != "base"):
        log("KNEEL %s %s: nothing inside%s" % (name, suffix, ", nothing hangs" if variant == "base" else ""))
        return None
    C, Tp, cid = mb.proxy(P, T, cell)
    n = len(C)
    cnt = np.bincount(cid, minlength=n)

    def per_node(v):
        return np.bincount(cid, weights=v, minlength=n) / cnt

    Wn = np.zeros((n, Wc.shape[1]))
    np.add.at(Wn, cid, Wc)
    Wn /= cnt[:, None]
    hang = np.clip((per_node(cw) - 0.15) / 0.5, 0.0, 1.0) ** 2
    wantp = per_node(want)
    Cs = C + np.stack([per_node((off_v + off_k)[:, a]) for a in range(3)], 1)
    edges = wsolve.mesh_edges(Tp)
    L = np.linalg.norm(C[edges[:, 1]] - C[edges[:, 0]], axis=1)
    d = np.zeros((n, 3))            # each node's move, kept in rest space between the steps
    for Mt, sol_t in path(sex, k, log, variant):
        A = np.einsum("vj,jab->vab", Wn, Mt[:, :3, :3])
        Gp = wfix.lbs(Cs, Wn, Mt)
        X = relax(Gp + np.einsum("vab,vb->va", A, d), Gp, edges, L, hang, wantp, sol_t, g=g)
        d = np.linalg.solve(A, (X - Gp)[..., None])[..., 0]
    Dp = X - Gp
    for _ in range(2):   # smooth the move along the cloth, then out of the body again
        acc = np.zeros_like(Dp)
        ec = np.zeros(n)
        np.add.at(acc, edges[:, 0], Dp[edges[:, 1]])
        np.add.at(acc, edges[:, 1], Dp[edges[:, 0]])
        np.add.at(ec, edges[:, 0], 1)
        np.add.at(ec, edges[:, 1], 1)
        Dp = (Dp + acc) / (1 + ec)[:, None]
    Dp = relax(Gp + Dp, Gp, edges, L, hang, wantp, sol, iters=6, g=0.0, keep=0.0) - Gp
    # per vertex: the 4 nearest proxy nodes in REST space (along the cloth), by inverse distance
    D = np.zeros_like(G)
    for s in range(0, len(G), 512):
        d2 = ((P[s:s + 512, None, :] - C[None]) ** 2).sum(-1)
        nn = np.argpartition(d2, 4, axis=1)[:, :4]
        wt = 1.0 / np.maximum(np.take_along_axis(d2, nn, 1), 0.05)
        D[s:s + 512] = (Dp[nn] * wt[..., None]).sum(1) / wt.sum(1, keepdims=True)
    D[np.linalg.norm(D, axis=1) < 0.05] = 0.0
    # last: every vertex out to its wanted clearance (the push carried to its neighbours, both cloth layers move),
    # the move smoothed over the welded mesh between pushes: pushed one by one, a thin belt went jagged at the
    # raised thigh's crease (neighbours 1-2 cm apart over 0.5 cm edges)
    Bk = posed_body(sex, k, variant)
    Nk = S["nrm"][k] if variant == "base" else _vnormals(Bk, S["tris"])
    used = np.unique(S["tris"])
    used = used[Bk[used, 1] > Bk[used, 1].min() + 15.0]   # not the feet and shins on the floor:
    sm = _smoother(P, T)                                                    # hems rest on them, out of the portrait
    for r in range(smooth_rounds + 1):
        for _ in range(4):
            sd, way = sol.sample(G + D)
            need = np.where(sd < want, _target(want) - sd, 0.0)
            if need.max() < 0.05:
                break
            D = D + shp.spatial_spread(G + D, way * need[:, None])
        D = D + unpoke(G + D, T, Bk, Nk, used)
        if r < smooth_rounds:
            D = sm(D, smooth_iters)
    A = np.einsum("vj,jab->vab", Wc, M[:, :3, :3])
    d_rest = np.linalg.solve(A, D[..., None])[..., 0]
    mv = np.linalg.norm(D, axis=1)
    # report: vertices short of their clearance by more than 0.15 cm, in every dumped frame of the clip
    rep = []
    for kk in fr:
        s_k = solid(sex, kk, log, variant)
        b = _inside(s_k, wfix.lbs(P + off_v + off_k, Wc, S["mats"][kk]), want)
        a = _inside(s_k, wfix.lbs(P + off_v + off_k + d_rest, Wc, S["mats"][kk]), want)
        rep.append((int((b > 0.15).sum()), float(b.max()), int((a > 0.15).sum()), float(a.max())))
    e = wsolve.mesh_edges(T)
    l0 = np.linalg.norm(G[e[:, 1]] - G[e[:, 0]], axis=1)
    l1 = np.linalg.norm((G + D)[e[:, 1]] - (G + D)[e[:, 0]], axis=1)
    ratio = l1[l0 > 0.05] / l0[l0 > 0.05]
    log("KNEEL %s %s: %d verts, moved %d (max %.1f cm); inside %s -> %s; deepest %.1f -> %.1f cm; edge stretch 1%%/99%% %.2f/%.2f" % (
        name, suffix, len(P), int((mv > 0).sum()), mv.max(), "/".join(str(r[0]) for r in rep), "/".join(str(r[2]) for r in rep),
        max(r[1] for r in rep), max(r[3] for r in rep), np.percentile(ratio, 1), np.percentile(ratio, 99)))
    if mv.max() < 0.1:
        return None
    if write:
        shp.write_shape(name, suffix, P, P + d_rest)
        shp.link_assets(name, suffix, attr)
    return dict(moved=float(mv.max()), frames=rep)


def pieces():
    return sorted(f[:-5] for f in os.listdir(cs.OUT) if f.endswith("_01.mesh") and "_bs_" not in f
                  and (f.startswith("ek2lc_m_") or f.startswith("ek2lc_f_")) and not any(s in f for s in SKIP))


def run_all(names=None, keys=("kneel1", "kneel2"), variants=("base", "fat"), log=print):
    import traceback
    for nm in names or pieces():
        sex = "female" if nm.startswith("ek2lc_f_") else "male"
        for key, variant in [(k_, v_) for v_ in variants for k_ in keys]:
            try:
                make(nm, sex, key, variant, log=log)
            except Exception:
                log("KNEEL ERROR %s %s %s %s" % (nm, key, variant, traceback.format_exc().splitlines()[-1]))
    log("KNEEL ALL DONE")


def look_at(name, sex, key, out, others=(), size=(420, 420), dist=1.0):
    """Maya GUI: front-side and side views in the kneel pose without and with the shape (back faces culled, as the
    game draws them), side by side in one picture."""
    import subprocess
    import maya.cmds as mc
    import look
    clip, attr = POSES[key]
    S = wfix.poses(sex)
    fr = [n for n in S["names"] if n.split(":")[0] == clip]
    cs.new_scene()
    body = cs.load_body(sex)
    sh = mc.shadingNode("lambert", asShader=True, name="kneel_look_mat")
    mc.setAttr(sh + ".color", 0.85, 0.42, 0.12, type="double3")
    for k in (name,) + tuple(others):
        p = cs.load_piece(k)
        mc.select(p)
        mc.hyperShade(assign=sh)     # flat colour: cloth against skin is what this view is for
    mc.select(clear=True)
    for m_ in mc.ls(type="mesh"):
        mc.setAttr(m_ + ".backfaceCulling", 3)
    look.setup_view()
    cs.pose(sex, clip, int(fr[len(fr) // 2].split(":")[1]))
    bb = mc.exactWorldBoundingBox(name)
    aim = ((bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2)
    shots = []
    for wgt in (0.0, 1.0):
        cs.set_shape(attr, wgt)
        for i, off in enumerate(((-90, 60, 110), (0, 30, 150), (-150, 40, 10))):
            mc.xform("persp", ws=True, t=(aim[0] + off[0] * dist, aim[1] + off[1] * dist, aim[2] + off[2] * dist))
            mc.viewLookAt("persp", pos=aim)
            shots.append(look.shot("%s_%d_%d.jpg" % (out[:-4], int(wgt), i), size[0], size[1]))
    subprocess.run([look.MAGICK, "(", shots[0], shots[1], shots[2], "+append", ")", "(", shots[3], shots[4], shots[5], "+append", ")",
                    "-append", "-quality", "82", out], check=True)
    for s in shots:
        os.remove(s)
    return out


def free_attrs():
    """Attributes the body or head entities (vanilla, EK2) declare with a neutral shape that no gene sets and no
    other model uses: the ones the kneel genes may drive."""
    import glob
    import re
    W = os.path.expanduser("~/Library/Application Support/Steam/steamapps/workshop/content/1158310/2887120253")
    att = re.compile(r'attribute\s*=\s*\{\s*name\s*=\s*"([^"]+)"\s*blend_shape\s*=\s*"([^"]+)"')
    base, other, genes = {}, set(), set()
    for root in (cs.GAME, W):
        for f in glob.glob(root + "/gfx/models/portraits/**/*.asset", recursive=True):
            t_ = open(f, encoding="utf-8-sig", errors="replace").read()
            isbase = re.search(r"/(male|female|boy|girl)_(body|head)\.asset$", f) is not None
            for a, bs in att.findall(t_):
                (base.setdefault(a, set()).add(bs) if isbase else other.add(a))
        for f in glob.glob(root + "/common/genes/*.txt"):
            genes |= set(re.findall(r'attribute\s*=\s*"([^"]+)"', open(f, encoding="utf-8-sig", errors="replace").read()))
    ours = set(a for a, _ in POSES.values()) | set(VARIANT_ATTR.values())
    return sorted(a for a, s in base.items() if all("neutral" in x for x in s) and (a not in genes or a in ours) and a not in other)

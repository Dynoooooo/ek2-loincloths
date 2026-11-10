"""Bone-weight solver for pieces that hang below the hips: numpy port of source/legacy_blender/weight_solver.py
and build_reach_hide.solve_piece (2026-11-07 design; ported to Maya space, Y up, 2026-11-10).

Why (from the original): the game moves a piece only through bone weights. Copying the skin's weights keeps it
right in the idles, but kneeling, sitting on the throne and bowing push thighs and hip creases through flaps,
aprons, belts and strips. So for every free vertex the weights (up to four bones) are solved such that over the
game's own animation frames it stays outside the body by a margin, the piece keeps its shape (edge lengths),
standing poses keep their look, neighbours have similar weights, and hanging parts never point up.

Pure numpy: run it with Maya's Python, outside the GUI (it changes no geometry; the result is looked at in Maya):
    mayapy -I source/maya/wsolve.py male ek2lc_m_festival_wrap_01 [more pieces]
Reads source/build_logs/solve/poses_<sex>.npz and piece_<name>.npz (pose_dump.py), writes
source/build_logs/solve/w_<name>.npz (top-4 bone names and weights per vertex) and prints a report line.
"""
import math
import os
import sys
import time
import numpy as np

UP = 1
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build_logs", "solve")
K_CAND = 40          # candidate triangles kept per query point between refreshes
REFRESH = 10         # iterations between candidate refreshes


# ---------------------------------------------------------------- geometry
def closest_on_tris(P, A, B, C):
    """Closest points on triangles (A, B, C: N x 3) to points P (N x 3). Ericson, Real-Time Collision Detection."""
    ab, ac, ap = B - A, C - A, P - A
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    bp = P - B
    d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    cp = P - C
    d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    den = np.where(np.abs(va + vb + vc) < 1e-12, 1e-12, va + vb + vc)
    v = vb / den
    w = vc / den
    R = A + ab * v[..., None] + ac * w[..., None]  # inside the face
    # regions (later ones take precedence where they apply)
    m = (vb <= 0) & (d2 >= 0) & (d6 <= 0)  # edge AC
    t = d2 / np.where(np.abs(d2 - d6) < 1e-12, 1e-12, d2 - d6)
    R = np.where(m[..., None], A + ac * t[..., None], R)
    m = (vc <= 0) & (d1 >= 0) & (d3 <= 0)  # edge AB
    t = d1 / np.where(np.abs(d1 - d3) < 1e-12, 1e-12, d1 - d3)
    R = np.where(m[..., None], A + ab * t[..., None], R)
    m = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)  # edge BC
    t = (d4 - d3) / np.where(np.abs((d4 - d3) + (d5 - d6)) < 1e-12, 1e-12, (d4 - d3) + (d5 - d6))
    R = np.where(m[..., None], B + (C - B) * t[..., None], R)
    R = np.where(((d1 <= 0) & (d2 <= 0))[..., None], A, R)
    R = np.where(((d3 >= 0) & (d4 <= d3))[..., None], B, R)
    R = np.where(((d6 >= 0) & (d5 <= d6))[..., None], C, R)
    return R


class Obstacle:
    """A posed body (triangles without forearms and hands) with a nearest-point query. Candidate triangles per
    query point are cached and refreshed every REFRESH iterations (the solve moves points slowly)."""

    def __init__(self, pts, tris):
        self.P = np.asarray(pts, float)
        self.T = np.asarray(tris, int)
        a, b, c = self.P[self.T[:, 0]], self.P[self.T[:, 1]], self.P[self.T[:, 2]]
        n = np.cross(b - a, c - a)
        self.N = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        self.C = (a + b + c) / 3
        self.cand = None

    def refresh(self, X):
        out = np.empty((len(X), K_CAND), int)
        cc = (self.C ** 2).sum(1)
        for s in range(0, len(X), 400):
            x = X[s:s + 400]
            d2 = (x ** 2).sum(1)[:, None] + cc[None, :] - 2 * x @ self.C.T
            k = min(K_CAND, d2.shape[1] - 1)
            out[s:s + 400, :k] = np.argpartition(d2, k, axis=1)[:, :k]
        self.cand = out

    def query(self, X):
        """loc, face normal, distance for each X (after refresh())."""
        T = self.T[self.cand]  # V x K x 3
        A, B, C = self.P[T[..., 0]], self.P[T[..., 1]], self.P[T[..., 2]]
        Xk = np.broadcast_to(X[:, None, :], A.shape)
        R = closest_on_tris(Xk, A, B, C)
        d = np.linalg.norm(Xk - R, axis=-1)
        k = d.argmin(1)
        i = np.arange(len(X))
        return R[i, k], self.N[self.cand[i, k]], d[i, k]


# ---------------------------------------------------------------- the solver (as weight_solver.Problem)
def simplex_proj(Y, allowed=None):
    if allowed is not None:
        Y = np.where(allowed, Y, -1e9)
    n, d = Y.shape
    U = -np.sort(-Y, axis=1)
    css = np.cumsum(U, axis=1) - 1
    ind = np.arange(1, d + 1)
    cond = U - css / ind > 0
    rho = d - 1 - np.argmax(cond[:, ::-1], axis=1)
    theta = css[np.arange(n), rho] / (rho + 1)
    return np.maximum(Y - theta[:, None], 0)


class Problem:
    def __init__(self, rest, edges, W0, free, allowed, poses, margin, stick=None, down=None):
        self.rest = np.asarray(rest, float)
        self.V = len(self.rest)
        self.E = np.asarray(edges, int).reshape(-1, 2)
        self.L = np.linalg.norm(self.rest[self.E[:, 0]] - self.rest[self.E[:, 1]], axis=1)
        self.W = np.array(W0, float)
        self.B = self.W.shape[1]
        self.free = np.asarray(free, bool)
        self.allowed = np.asarray(allowed, bool) | (self.W > 0)
        self.poses = poses
        self.margin = np.broadcast_to(np.asarray(margin, float), (self.V,)).copy()
        self.stick = stick
        self.down = np.asarray(down if down is not None else [], int).reshape(-1, 2)
        self.down_slack = 1.0
        self.grav = np.zeros(self.V)
        h = np.c_[self.rest, np.ones(self.V)]
        self.fidx = np.nonzero(self.free)[0]
        for p in poses:
            p["Q"] = np.einsum("bij,vj->vbi", p["mats"], h)[:, :, :3]
        self.it = 0

    def positions(self, p, W=None):
        return np.einsum("vb,vbi->vi", self.W if W is None else W, p["Q"])

    def _contact(self, p, X, gX, lam, E, refresh):
        ob = p["obst"]
        if ob is None or not len(self.fidx):
            return
        Xf = X[self.fidx]
        if refresh or ob.cand is None:
            ob.refresh(Xf)
        loc, nor, dist = ob.query(Xf)
        sd = ((Xf - loc) * nor).sum(1)
        m = self.margin[self.fidx]
        wpose = p.get("w", 1.0)
        pen = sd < m
        e = np.where(pen, m - sd, 0.0)
        E["pen"] += lam["pen"] * wpose * float((e * e).sum())
        gX[self.fidx] -= (lam["pen"] * wpose * 2 * e)[:, None] * nor
        if self.stick is not None:
            st = self.stick[self.fidx]
            s = (~pen) & (sd > st)
            e = np.where(s, sd - st, 0.0)
            E["stick"] += lam.get("stick", 0.0) * float((e * e).sum())
            gX[self.fidx] += (lam.get("stick", 0.0) * 2 * e)[:, None] * nor

    def energy_grad(self, lam, refresh=False):
        W = self.W
        G = np.zeros_like(W)
        E = {"pen": 0.0, "stick": 0.0, "ref": 0.0, "len": 0.0, "smooth": 0.0, "down": 0.0, "grav": 0.0}
        a, b = self.E[:, 0], self.E[:, 1]
        for p in self.poses:
            X = self.positions(p)
            gX = np.zeros_like(X)
            self._contact(p, X, gX, lam, E, refresh)
            if len(self.down) and lam.get("down", 0.0):
                u, l_ = self.down[:, 0], self.down[:, 1]
                r = np.maximum(X[l_, UP] - X[u, UP] - self.down_slack, 0.0)
                E["down"] += lam["down"] * float((r ** 2).sum())
                g = lam["down"] * 2 * r
                np.add.at(gX[:, UP], l_, g)
                np.add.at(gX[:, UP], u, -g)
            if p.get("ref") is not None:
                Dd = (X - p["ref"])[self.fidx]
                E["ref"] += lam["ref"] * float((Dd ** 2).sum())
                gX[self.fidx] += lam["ref"] * 2 * Dd
            elif lam.get("grav", 0.0) and self.grav.any():
                E["grav"] += lam["grav"] * float((self.grav * X[:, UP]).sum())
                gX[:, UP] += lam["grav"] * self.grav
            if len(self.E):
                dv = X[a] - X[b]
                ln = np.linalg.norm(dv, axis=1) + 1e-9
                r = ln - self.L
                E["len"] += lam["len"] * float((r ** 2).sum())
                g = (lam["len"] * 2 * r / ln)[:, None] * dv
                np.add.at(gX, a, g)
                np.add.at(gX, b, -g)
            G += np.einsum("vi,vbi->vb", gX, p["Q"])
        if len(self.E):
            dW = W[a] - W[b]
            E["smooth"] = lam["smooth"] * float((dW ** 2).sum())
            gs = lam["smooth"] * 2 * dW
            np.add.at(G, a, gs)
            np.add.at(G, b, -gs)
        G[~self.free] = 0
        return E, G

    def run(self, lam, iters=250, max_dw=0.03, decay=0.99, log=None):
        s = max_dw
        E = None
        for it in range(iters):
            E, G = self.energy_grad(lam, refresh=(it % REFRESH == 0))
            Gt = np.where(self.allowed, G, 0.0)
            Gt = Gt - (Gt.sum(axis=1, keepdims=True) / np.maximum(self.allowed.sum(axis=1, keepdims=True), 1)) * self.allowed
            m = np.abs(Gt[self.fidx]).max() if len(self.fidx) else 0.0
            if m < 1e-12:
                break
            Wn = self.W - (s / m) * Gt
            Wn[self.fidx] = simplex_proj(Wn[self.fidx], self.allowed[self.fidx])
            self.W[self.fidx] = Wn[self.fidx]
            s *= decay
            if log and (it % 50 == 0 or it == iters - 1):
                log("    it %3d  %s" % (it, {k: round(v, 1) for k, v in E.items()}))
        return E

    def prune(self, k=4, thr=0.015):
        for v in self.fidx:
            idx = np.argsort(-self.W[v])
            keep = [i for i in idx[:k] if self.W[v, i] > thr]
            row = np.zeros(self.B)
            row[keep] = self.W[v, keep]
            self.W[v] = row / row.sum()
        self.allowed = self.allowed & (self.W > 0) | ~self.free[:, None]

    def penetration(self, W=None, tol=0.0):
        out = []
        for p in self.poses:
            if p["obst"] is None:
                continue
            X = self.positions(p, W)[self.fidx]
            p["obst"].refresh(X)
            loc, nor, dist = p["obst"].query(X)
            sd = ((X - loc) * nor).sum(1)
            bad = sd < -tol
            if bad.any():
                out.append((round(float(-sd[bad].min()), 2), int(bad.sum()), p["name"]))
        return sorted(out, reverse=True)

    def stretch(self, W=None):
        out = []
        a, b = self.E[:, 0], self.E[:, 1]
        for p in self.poses:
            X = self.positions(p, W)
            r = np.abs(np.linalg.norm(X[a] - X[b], axis=1) - self.L)
            out.append((round(float(r.max()), 2), p["name"]))
        return sorted(out, reverse=True)


# ---------------------------------------------------------------- mesh helpers (as weight_solver)
def mesh_edges(tris):
    e = np.sort(np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), axis=1)
    return np.unique(e, axis=0)


def islands(n, edges):
    par = np.arange(n)

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
    return np.array([find(i) for i in range(n)])


def tie_pairs(rest, comp, maxd):
    out = set()
    for i in range(len(rest)):
        other = comp != comp[i]
        if not other.any():
            continue
        d = ((rest - rest[i]) ** 2).sum(1)
        d[~other] = 1e18
        k = int(np.argmin(d))
        if d[k] <= maxd * maxd:
            out.add((min(i, k), max(i, k)))
    return np.array(sorted(out), int).reshape(-1, 2)


def bend_pairs(rest, edges, min_angle=150.0):
    nb = {}
    for a, b in edges:
        nb.setdefault(a, set()).add(b)
        nb.setdefault(b, set()).add(a)
    cosmax = math.cos(math.radians(min_angle))
    out = set()
    for b, ns in nb.items():
        ns = list(ns)
        if len(ns) < 2:
            continue
        U = rest[ns] - rest[b]
        lu = np.linalg.norm(U, axis=1)
        ok = lu > 1e-6
        Un = U / np.maximum(lu[:, None], 1e-9)
        Cs = Un @ Un.T
        ii, jj = np.nonzero(np.triu(Cs < cosmax, 1) & ok[:, None] & ok[None, :])
        for i, j in zip(ii, jj):
            a, c = ns[i], ns[j]
            out.add((min(a, c), max(a, c)))
    return np.array(sorted(out), int).reshape(-1, 2)


def ang_of(p):
    """Angle round the body's vertical axis: 0 at the front (+Z), +90 deg towards +X."""
    return math.atan2(p[0], p[2])


# ---------------------------------------------------------------- solve one piece (as build_reach_hide.solve_piece)
def load_poses(sex, keep=None):
    d = np.load(os.path.join(D, "poses_%s.npz" % sex))
    bones = [str(b) for b in d["bones"]]
    names = [str(n) for n in d["names"]]
    kinds = [str(k) for k in d["kinds"]]
    tris = d["tris"]
    hand = d["hand_v"]
    tri_ok = ~hand[tris].any(1)
    P = dict(bones=bones, bi={b: k for k, b in enumerate(bones)}, tris=tris[tri_ok], poses=[],
             rest_pts=d["rest_pts"], joints_rest=d["joints_rest"])
    for k, n in enumerate(names):
        if keep and not any(n.startswith(x) for x in keep):
            continue
        P["poses"].append(dict(name=n, kind=kinds[k], mats=d["mats"][k], body=d["body_pts"][k].astype(float)))
    return P


def hang_allowed_fn(P):
    bi = P["bi"]
    base = [bi[b] for b in ("body_root", "bn_sp_lumbar", "bn_l_hip", "bn_r_hip")]
    chains = {}
    for b, k in bi.items():
        if "_skirt" in b:
            c = b.split("_skirt")[0][3:]  # bn_lf_skirt2 -> lf
            chains.setdefault(c, []).append(k)
    angs = {}
    for c in chains:
        j1 = bi.get("bn_%s_skirt1" % c)
        if j1 is not None:
            angs[c] = ang_of(P["joints_rest"][j1])
    win = math.radians(75)

    def fn(p):
        th = ang_of(p)
        out = set(base)
        for c, a in angs.items():
            if abs((th - a + math.pi) % (2 * math.pi) - math.pi) <= win:
                out |= {bi["bn_%s_skirt%d" % (c, i)] for i in (1, 2, 3) if "bn_%s_skirt%d" % (c, i) in bi}
        return out
    return fn


def cape_allowed_fn(P):
    bi = P["bi"]
    s = {k for b, k in bi.items() if "_cloak" in b} | {bi[b] for b in ("body_root", "bn_sp_lumbar", "bn_sp_thoracic",
                                                                       "bn_l_hip", "bn_r_hip") if b in bi}
    return lambda p: s


def solve(name, P, free=None, cap=1.0, allowed_fn=None, tie_d=1.0, iters=250, inits=("orig", "half"), pose_w=3.0,
          belt_y=None, log=print):
    t0 = time.time()
    pc = np.load(os.path.join(D, "piece_%s.npz" % name))
    rest, tris, W0full = pc["rest"].astype(float), pc["tris"], pc["W0"]
    n = len(rest)
    hip_y = P["joints_rest"][P["bi"]["bn_l_hip"]][UP]
    BELT = belt_y if belt_y is not None else hip_y + 6.0
    if free is None:
        free = rest[:, UP] < BELT
    free = np.asarray(free, bool)
    allowed_fn = allowed_fn or hang_allowed_fn(P)
    E = mesh_edges(tris)
    comp = islands(n, E)
    edges = np.concatenate([E, tie_pairs(rest, comp, tie_d), bend_pairs(rest, E)])
    cand = set()
    for v in np.nonzero(free)[0]:
        cand |= allowed_fn(rest[v])
    bones = sorted(set(np.nonzero(W0full.any(axis=0))[0]) | cand)
    bl = {b: k for k, b in enumerate(bones)}
    W0 = W0full[:, bones]
    allowed = np.zeros_like(W0, bool)
    for v in np.nonzero(free)[0]:
        for b in allowed_fn(rest[v]):
            allowed[v, bl[b]] = True
    rest_obst = Obstacle(P["rest_pts"], P["tris"])
    rest_obst.refresh(rest)
    loc, nor, _ = rest_obst.query(rest)
    rc = ((rest - loc) * nor).sum(1)
    margin = np.minimum(np.broadcast_to(cap, (n,)), 0.8 * np.maximum(rc, 0.0))
    H = np.c_[rest, np.ones(n)]
    poses = []
    for p in P["poses"]:
        m_ = p["mats"][bones]
        ref = None
        if p["kind"] == "ref":
            Q = np.einsum("bij,vj->vbi", m_, H)[:, :, :3]
            ref = np.einsum("vb,vbi->vi", W0, Q)
        poses.append(dict(name=p["name"], mats=m_, obst=Obstacle(p["body"], P["tris"]), ref=ref,
                          w=1.0 if p["kind"] == "ref" else pose_w))
    down = []
    for a, b in E:
        if free[a] and free[b]:
            dd = rest[a] - rest[b]
            if abs(dd[UP]) > 0.8 * np.linalg.norm(dd):
                down.append((a, b) if dd[UP] > 0 else (b, a))
    lam = dict(pen=20.0, ref=float(os.environ.get("WS_REF", "1.0")), len=2.0, smooth=30.0, stick=5.0, down=20.0, grav=0.5)
    lside = 1 if P["joints_rest"][P["bi"]["bn_l_hip"]][0] > 0 else -1
    best = None
    free_names = {p["name"] for p in poses if p["ref"] is None}
    before = Problem(rest, edges, W0, free, allowed, poses, margin, None, down)
    pen0 = [r for r in before.penetration() if r[2] in free_names]
    for init in inits:
        prob = Problem(rest, edges, W0, free, allowed, poses, margin, None, down)
        prob.down_slack = 0.0
        prob.grav = np.where(free & (rest[:, UP] < BELT - 2.0), 1.0, 0.0)
        if init == "half":
            Wh = prob.W.copy()
            for v in np.nonzero(free & (rest[:, UP] < BELT - 4.0))[0]:
                row = np.zeros(len(bones))
                x = rest[v][0]
                wl = min(1.0, max(0.0, 0.5 + x / 20.0)) if lside > 0 else min(1.0, max(0.0, 0.5 - x / 20.0))
                row[bl[P["bi"]["body_root"]]] = 0.5
                row[bl[P["bi"]["bn_l_hip"]]] = 0.5 * wl
                row[bl[P["bi"]["bn_r_hip"]]] = 0.5 * (1 - wl)
                k_ = min(1.0, (BELT - 4.0 - rest[v][UP]) / 6.0)
                Wh[v] = (1 - k_) * Wh[v] + k_ * row
            prob.W = Wh
        en = prob.run(lam, iters=iters, max_dw=0.03, decay=0.99)
        tot = sum(en.values())
        worst = max([r[0] for r in prob.penetration() if r[2] in free_names] or [0.0])
        if best is None or worst < best[0] - 0.3 or (abs(worst - best[0]) <= 0.3 and tot < best[1]):
            best = (worst, tot, init, prob, en)
    worst, tot, init, prob, en = best
    prob.prune(4, 0.015)
    prob.run(lam, iters=40, max_dw=0.01, decay=0.98)
    pen = prob.penetration()
    st = prob.stretch()
    dev = [float(np.linalg.norm(prob.positions(p) - p["ref"], axis=1)[free].max()) for p in poses if p["ref"] is not None]
    Wfull = np.zeros((n, len(P["bones"])))
    Wfull[:, bones] = prob.W
    # top 4 per vertex
    idx = np.argsort(-Wfull, axis=1)[:, :4]
    w4 = np.take_along_axis(Wfull, idx, 1)
    w4 = w4 / np.maximum(w4.sum(1, keepdims=True), 1e-9)
    names = np.array(P["bones"])[idx]
    np.savez_compressed(os.path.join(D, "w_%s.npz" % name), bones=names, weights=w4)
    rep = ("SOLVE %-34s %4d free, start %s, %.0fs; inside before: %s; after: %s; stretch %.1f cm (%s); standing moved "
           "max %.1f median %.1f" % (name, free.sum(), init, time.time() - t0,
                                     "; ".join("%.2f x%d %s" % r for r in pen0[:2]) or "none",
                                     "; ".join("%.2f x%d %s" % r for r in pen[:3]) or "none", st[0][0], st[0][1],
                                     max(dev or [0]), float(np.median(dev)) if dev else 0.0))
    log(rep)
    return rep


if __name__ == "__main__":
    sex = sys.argv[1]
    keep = None
    args = sys.argv[2:]
    P = load_poses(sex, keep)
    print("poses", len(P["poses"]), flush=True)
    for nm in args:
        try:
            solve(nm, P, iters=int(os.environ.get("WS_ITERS", "250")),
                  inits=tuple(os.environ.get("WS_INITS", "orig,half").split(",")), log=lambda s: print(s, flush=True))
        except Exception as e:  # noqa
            import traceback
            print("FAILED", nm, traceback.format_exc()[-600:], flush=True)

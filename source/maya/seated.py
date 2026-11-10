"""The throne shape, as vanilla does it (2026-11-10): the `throne_room_ruler` portrait animation (throneRoom_ruler2)
adds the morph gene_seated (attribute bs_body_seated = 1, 00_animation_expressions.txt `seated_skirt`), and vanilla
gowns carry a `_bs_seated` blend shape that drapes them for sitting. Our hanging parts followed the skirt chains and
stood out over the lap like boards; this makes their own seated shape:

  1. the piece in the throne pose (pose dump, frame 151), on a proxy (1.5 cm cells: both cloth layers are one node);
  2. a short cloth drape there: the belt pinned (by how little a node rides the skirt chains), gravity, the proxy's
     rest edge lengths kept, pushed out of the seated body;
  3. the drape's move per vertex (interpolated from the proxy) turned back into rest space through each vertex's
     own skinning transform, written as <piece>_bs_seated.mesh and linked to bs_body_seated in its .asset files.

    import seated; seated.make("ek2lc_m_lich_king_01", "male")
"""
import numpy as np
import maya.cmds as mc
import ck3scene as cs
import mbuild as mb
import shapes as shp
import wfix
import wsolve

POSE = "throneRoom_ruler2_1:151"
_J = {}


def S_joints(sex):
    """Rest joint positions by name (pose dump)."""
    if sex not in _J:
        d = np.load("%s/poses_%s.npz" % (wfix.D, sex))
        _J[sex] = {str(b): d["joints_rest"][k] for k, b in enumerate(d["bones"])}
    return _J[sex]


def _geodesic(n, edges, L, src):
    """Cloth distance from the pinned nodes (Dijkstra over the proxy's edges) and the pin each node hangs from."""
    import heapq
    adj = [[] for _ in range(n)]
    for (a, b), l in zip(edges, L):
        adj[a].append((b, l))
        adj[b].append((a, l))
    dist = np.full(n, np.inf)
    root = -np.ones(n, int)
    h = []
    for i in np.nonzero(src)[0]:
        dist[i] = 0.0
        root[i] = i
        h.append((0.0, i))
    heapq.heapify(h)
    while h:
        d, a = heapq.heappop(h)
        if d > dist[a]:
            continue
        for b, l in adj[a]:
            if d + l < dist[b]:
                dist[b] = d + l
                root[b] = root[a]
                heapq.heappush(h, (d + l, b))
    return dist, root


def drape(Xp, edges, L, inv_m, body, tris, nrm, gap=0.8, iters=140, g=0.35, sub=6, seat=None, support=None, log=print):
    """Position-based drape: gravity, edge lengths, tethers (no node farther from its pin than its cloth distance;
    long chains converge slowly otherwise), and the body pushed out (closest point with smooth normals)."""
    X = Xp.copy()
    o = wsolve.Obstacle(body, tris)
    free = inv_m > 0
    gd, root = _geodesic(len(X), edges, L, ~free)
    above0 = support(Xp) - 1.0 <= Xp[:, 1] if support is not None else None
    teth = free & np.isfinite(gd) & (root >= 0)
    for it in range(iters):
        X[:, 1] -= g * inv_m
        for _ in range(sub):
            d = X[edges[:, 1]] - X[edges[:, 0]]
            ln = np.linalg.norm(d, axis=1)
            wsum = inv_m[edges[:, 0]] + inv_m[edges[:, 1]]
            ok = (ln > 1e-6) & (wsum > 0)
            c = np.where(ok, (ln - L) / np.maximum(ln, 1e-6) / np.maximum(wsum, 1e-6), 0.0)[:, None] * d
            acc = np.zeros_like(X)
            cnt = np.zeros(len(X))
            np.add.at(acc, edges[:, 0], c * inv_m[edges[:, 0], None])
            np.add.at(acc, edges[:, 1], -c * inv_m[edges[:, 1], None])
            np.add.at(cnt, edges[:, 0], ok)
            np.add.at(cnt, edges[:, 1], ok)
            X += acc / np.maximum(cnt, 1)[:, None]
            r = X[teth] - Xp[root[teth]]
            rl = np.linalg.norm(r, axis=1)
            over = rl > gd[teth] * 1.02
            if over.any():
                idx = np.nonzero(teth)[0][over]
                X[idx] = Xp[root[idx]] + r[over] * (gd[idx] * 1.02 / rl[over])[:, None]
        if it % 2 == 0:
            o.refresh(X)
        sd = wfix._sd(o, X, nrm, maxd=1e9)
        loc, n_, _ = o.query(X)
        push = np.maximum(gap - sd, 0.0)
        X[free] += (n_ * push[:, None])[free]
        if support is not None:   # cloth that came down onto the lap bridges the gap between the thighs
            H = support(X)
            on = free & above0 & (X[:, 1] < H + gap)
            X[on, 1] = H[on] + gap
        if seat is not None:   # the throne's seat: nothing sinks below the bottom of the thighs inside its footprint
            ys, z0, z1, xm = seat
            on = free & (X[:, 2] > z0) & (X[:, 2] < z1) & (np.abs(X[:, 0]) < xm) & (X[:, 1] < ys + gap)
            X[on, 1] = ys + gap
        X[~free] = Xp[~free]
    return X


def support_of(body, tris, r=7.0, cell=1.0, keep=None):
    """A height map of the posed body (vertices and triangle centres), widened by r cm: what a cloth lying on the
    lap rests on (it bridges the gap between the thighs and runs a little past the knees before it falls)."""
    if keep is not None:   # the legs only (not the hands resting on the lap, nor the belly above it)
        tris = tris[keep[tris].all(1)]
    pts = np.vstack([body[np.unique(tris)], body[tris].mean(1)])
    lo = pts[:, [0, 2]].min(0) - r - 2
    idx = np.floor((pts[:, [0, 2]] - lo) / cell).astype(int)
    nx, nz = idx.max(0) + int(r / cell) + 4
    Hm = np.full((nx, nz), -1e9)
    np.maximum.at(Hm, (idx[:, 0], idx[:, 1]), pts[:, 1])
    k = int(r / cell)
    D = Hm.copy()
    for dx in range(-k, k + 1):
        for dz in range(-k, k + 1):
            if dx * dx + dz * dz > k * k:
                continue
            sh = np.full_like(Hm, -1e9)
            xs, xd = (slice(dx, None), slice(None, -dx or None)) if dx >= 0 else (slice(None, dx), slice(-dx, None))
            zs, zd = (slice(dz, None), slice(None, -dz or None)) if dz >= 0 else (slice(None, dz), slice(-dz, None))
            sh[xd, zd] = Hm[xs, zs]
            D = np.maximum(D, sh)

    def H(X):
        i = np.clip(np.floor((X[:, [0, 2]] - lo) / cell).astype(int), 0, [nx - 1, nz - 1])
        return D[i[:, 0], i[:, 1]]
    return H


def legs_of(S):
    """Body vertices whose strongest bone is a thigh or a shin."""
    dom = S["W"].argmax(1)
    legs = [S["bones"].index(b) for b in ("bn_l_hip", "bn_r_hip", "bn_l_knee", "bn_r_knee")]
    return np.isin(dom, legs)


def seat_of(body, joints_posed):
    """(seat height, z from, z to, half width) under the seated body: the lowest point of the thighs and buttocks
    (body points between the knees' height - 10 cm and the hips, behind the knees), from behind the buttocks to the front of the knees."""
    ky = (joints_posed["bn_l_knee"][1] + joints_posed["bn_r_knee"][1]) / 2
    kz = max(joints_posed["bn_l_knee"][2], joints_posed["bn_r_knee"][2])
    hy = (joints_posed["bn_l_hip"][1] + joints_posed["bn_r_hip"][1]) / 2
    m = (body[:, 1] > ky - 10) & (body[:, 1] < hy + 5) & (body[:, 2] < kz - 6) & (np.abs(body[:, 0]) < 25)
    B = body[m]
    return float(B[:, 1].min()), float(B[:, 2].min() - 8), float(kz + 2), float(np.abs(B[:, 0]).max() + 6)


def make(name, sex, gap=0.8, cell=1.5, log=print, write=True):
    S = wfix.poses(sex)
    k = S["names"].index(POSE)
    root, m, skel, P, ix, w = wfix._read(name)
    T = np.array(m.attrib["tri"]).reshape(-1, 3)
    Wc = wfix._dense(ix, w, skel, S["bones"])
    chain = np.array([("skirt" in b) or ("cloak" in b) for b in S["bones"]])
    cw = Wc[:, chain].sum(1)
    if cw.max() < 0.05:
        log("SEATED %s: nothing hangs" % name)
        return None
    M = S["mats"][k]
    G = wfix.lbs(P, Wc, M)                                           # posed (Maya space)
    C, Tp, cid = mb.proxy(P, T, cell)
    n = len(C)
    cnt = np.bincount(cid, minlength=n)
    Gp = np.zeros((n, 3))
    np.add.at(Gp, cid, G)
    Gp /= cnt[:, None]
    cwp = np.bincount(cid, weights=cw, minlength=n) / cnt
    inv_m = np.clip((cwp - 0.15) / 0.5, 0.0, 1.0) ** 2              # belt pinned, fully free well down the chains
    edges = wsolve.mesh_edges(Tp)
    L = np.linalg.norm(C[edges[:, 1]] - C[edges[:, 0]], axis=1)      # rest lengths
    jp = {b: (M[j] @ np.r_[S_joints(sex)[b], 1.0])[:3] for j, b in enumerate(S["bones"]) if b in ("bn_l_knee", "bn_r_knee", "bn_l_hip", "bn_r_hip")}
    seat = seat_of(S["body"][k], jp)
    X = drape(Gp, edges, L, inv_m, S["body"][k], S["tris"], S["nrm"][k], gap=gap, seat=seat,
              support=support_of(S["body"][k], S["tris"], keep=legs_of(S)), log=log)
    Dp = X - Gp
    for _ in range(4):   # smooth the move along the cloth (pinned nodes keep theirs: 0)
        acc = np.zeros_like(Dp)
        cnt = np.zeros(len(Dp))
        np.add.at(acc, edges[:, 0], Dp[edges[:, 1]])
        np.add.at(acc, edges[:, 1], Dp[edges[:, 0]])
        np.add.at(cnt, edges[:, 0], 1)
        np.add.at(cnt, edges[:, 1], 1)
        Dp = np.where((inv_m > 0)[:, None], (Dp + acc) / (1 + cnt)[:, None], Dp)
    # per vertex: inverse-distance blend of the 4 nearest proxy nodes in REST space (along the cloth: panels that
    # touch when seated must not mix their moves), so no steps between cells
    D = np.zeros_like(G)
    for s in range(0, len(G), 512):
        d2 = ((P[s:s + 512, None, :] - C[None]) ** 2).sum(-1)
        nn = np.argpartition(d2, 4, axis=1)[:, :4]
        dd = np.take_along_axis(d2, nn, 1)
        wt = 1.0 / np.maximum(dd, 0.05)
        D[s:s + 512] = (Dp[nn] * wt[..., None]).sum(1) / wt.sum(1, keepdims=True)
    D[cw < 0.02] = 0.0
    # last: every hanging vertex out of the seated body by a small gap, the push carried to its neighbours within
    # 2.5 cm (both layers of a two-sided panel move together)
    o = wsolve.Obstacle(S["body"][k], S["tris"])
    hang = cw >= 0.02
    for _ in range(3):
        X = G + D
        o.refresh(X)
        sd = wfix._sd(o, X, S["nrm"][k], maxd=1e9)
        loc, nrm_, _ = o.query(X)
        need = np.where(hang, np.maximum(0.4 - sd, 0.0), 0.0)
        if need.max() < 0.05:
            break
        D = D + np.where(hang[:, None], shp.spatial_spread(X, nrm_ * need[:, None]), 0.0)
    # back to rest space through each vertex's skinning transform
    A = np.einsum("vj,jab->vab", Wc, M[:, :3, :3])
    d_rest = np.linalg.solve(A, D[..., None])[..., 0]
    mv = np.linalg.norm(D, axis=1)
    o = wsolve.Obstacle(S["body"][k], S["tris"])
    o.refresh(G)
    before = -wfix._sd(o, G, S["nrm"][k])
    o.refresh(G + D)
    after = -wfix._sd(o, G + D, S["nrm"][k])
    log("SEATED %s: seat y %.1f z %.1f..%.1f; %d proxy nodes, moved max %.1f / median %.1f cm (of the hanging part); inside >0.5 cm %d -> %d, deepest %.1f -> %.1f" % (
        name, seat[0], seat[1], seat[2], n, mv.max(), np.median(mv[cw > 0.3]) if (cw > 0.3).any() else 0.0, (before > 0.5).sum(), (after > 0.5).sum(),
        before.max(), after.max()))
    if write:
        cs.new_scene()
        cs.load_body(sex)
        piece = cs.load_piece(name)
        cs.rest_pose()
        cs.set_shape(None)
        G0 = np.array(__import__("audit").pts(piece))
        shp.write_shape(piece, "seated", G0, G0 + d_rest)
        shp.link_assets(name, "seated", "bs_body_seated")
        for x in (piece, piece + "_BS"):
            if mc.objExists(x):
                mc.delete(x)
    return dict(moved=float(mv.max()), inside=(int((before > 0.5).sum()), int((after > 0.5).sum())))


def look_at(name, sex, out, others=()):
    """Side views in the throne pose without and with the seated shape (back faces culled), side by side."""
    import subprocess
    import look
    import sheet
    cs.new_scene()
    cs.load_body(sex)
    for k in (name,) + tuple(others):
        p = cs.load_piece(k)
        sheet._tex(p, k[8:-3])
    for m_ in mc.ls(type="mesh"):
        mc.setAttr(m_ + ".backfaceCulling", 3)
    look.setup_view()
    cs.pose(sex, POSE.split(":")[0], int(POSE.split(":")[1]))
    shots = []
    for wgt in (0.0, 1.0):
        cs.set_shape("bs_body_seated", wgt)
        for i, (cam, aim) in enumerate((((190, 60, 20), (0, 55, 10)), ((60, 90, 170), (0, 55, 10)))):
            mc.xform("persp", ws=True, t=cam)
            mc.viewLookAt("persp", pos=aim)
            shots.append(look.shot("%s_%d_%d.jpg" % (out[:-4], int(wgt), i), 360, 300))
    subprocess.run([look.MAGICK, "(", shots[0], shots[1], "+append", ")", "(", shots[2], shots[3], "+append", ")",
                    "-append", out], check=True)
    return out


def run_all(log=print, skip=()):
    """The seated shape for every piece with hanging parts (each base .mesh of the model folder; pieces with no
    skirt or cloak weight are skipped by make())."""
    import os
    import traceback
    names = sorted(f[:-5] for f in os.listdir(cs.OUT) if f.endswith("_01.mesh") and "_bs_" not in f
                   and (f.startswith("ek2lc_m_") or f.startswith("ek2lc_f_")))
    for n in names:
        if n in skip:
            continue
        sex = "female" if n.startswith("ek2lc_f_") else "male"
        try:
            make(n, sex, log=log)
        except Exception:
            log("SEATED ERROR %s %s" % (n, traceback.format_exc().splitlines()[-1]))
    log("SEATED ALL DONE")

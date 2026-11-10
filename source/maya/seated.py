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


def drape(Xp, edges, L, inv_m, body, tris, nrm, gap=0.8, iters=140, g=0.35, sub=6, log=print):
    """Position-based drape: gravity, edge lengths, tethers (no node farther from its pin than its cloth distance;
    long chains converge slowly otherwise), and the body pushed out (closest point with smooth normals)."""
    X = Xp.copy()
    o = wsolve.Obstacle(body, tris)
    free = inv_m > 0
    gd, root = _geodesic(len(X), edges, L, ~free)
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
        X[~free] = Xp[~free]
    return X


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
    X = drape(Gp, edges, L, inv_m, S["body"][k], S["tris"], S["nrm"][k], gap=gap, log=log)
    Dp = X - Gp
    # per vertex: inverse-distance blend of the 4 nearest proxy nodes (posed space), so no steps between cells
    D = np.zeros_like(G)
    for s in range(0, len(G), 512):
        d2 = ((G[s:s + 512, None, :] - Gp[None]) ** 2).sum(-1)
        nn = np.argpartition(d2, 4, axis=1)[:, :4]
        dd = np.take_along_axis(d2, nn, 1)
        wt = 1.0 / np.maximum(dd, 0.05)
        D[s:s + 512] = (Dp[nn] * wt[..., None]).sum(1) / wt.sum(1, keepdims=True)
    D[cw < 0.02] = 0.0
    # back to rest space through each vertex's skinning transform
    A = np.einsum("vj,jab->vab", Wc, M[:, :3, :3])
    d_rest = np.linalg.solve(A, D[..., None])[..., 0]
    mv = np.linalg.norm(D, axis=1)
    o = wsolve.Obstacle(S["body"][k], S["tris"])
    o.refresh(G)
    before = -wfix._sd(o, G, S["nrm"][k])
    o.refresh(G + D)
    after = -wfix._sd(o, G + D, S["nrm"][k])
    log("SEATED %s: %d proxy nodes, moved max %.1f / median %.1f cm (of the hanging part); inside >0.5 cm %d -> %d, deepest %.1f -> %.1f" % (
        name, n, mv.max(), np.median(mv[cw > 0.3]) if (cw > 0.3).any() else 0.0, (before > 0.5).sum(), (after > 0.5).sum(),
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

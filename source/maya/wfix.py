"""Pose-aware weights for the hanging parts of a piece (2026-11-10): each vertex that rides the skirt chains gets a
blend alpha between its own weights (skin at the belt, skirt chains below) and the skin weights of the body under it
(which follow the thighs and shins), chosen from 0, .25, .5, .75, 1 to keep it outside the body in the game's
kneeling, sitting and bowing poses ("free" samples of the pose dump), while the standing poses ("ref") must stay
where they were; then alpha is smoothed in space (both layers of a two-sided Meshy panel take one value), the
weights are cut to the 4 strongest and written into the .mesh (shape files need nothing: weights live in the base).

    import wfix; wfix.fix("ek2lc_m_lich_king_01", "male")     # inside Maya or mayapy; needs pose_dump's npz

Plain numpy on the pose dump (source/build_logs/solve/poses_<sex>.npz, bones as deform matrices in Maya space).
"""
import os
import numpy as np
import ck3scene as cs
import wsolve

D = cs.MOD + "/source/build_logs/solve"
ALPHAS = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
FREE = ("throneRoom_kneel1_1", "throneRoom_kneel2_1", "throneRoom_ruler1_1", "throneRoom_ruler2_1",
        "throneRoom_ruler3_1", "throneRoom_bow1_1", "throneRoom_bow2_1", "throneRoom_messenger1_1")
_POSES = {}


def poses(sex):
    if sex not in _POSES:
        d = np.load(os.path.join(D, "poses_%s.npz" % sex))
        hand = d["hand_v"]
        tris = d["tris"][~hand[d["tris"]].any(1)]
        names = [str(n) for n in d["names"]]
        kinds = [str(k) for k in d["kinds"]]
        _POSES[sex] = dict(bones=[str(b) for b in d["bones"]], names=names, kinds=kinds, mats=d["mats"],
                           body=d["body_pts"], nrm=d["body_nrm"], rest=d["rest_pts"], tris=tris, W=d["body_w"])
    return _POSES[sex]


def _read(name, folder=cs.OUT):
    from io_pdx_mesh import pdx_data
    root = pdx_data.read_meshfile("%s/%s.mesh" % (folder, name))
    sh = root.find("object")[0]
    m = sh.find("mesh")
    skel = {int(j.attrib["ix"][0]): j.tag for j in list(sh.find("skeleton"))}
    P = np.array(m.attrib["p"]).reshape(-1, 3) * np.array([1.0, 1.0, -1.0])     # Maya space
    sk = m.find("skin")
    nb = int(sk.attrib["bones"][0])
    ix = np.array(sk.attrib["ix"]).reshape(-1, nb)
    w = np.array(sk.attrib["w"]).reshape(-1, nb)
    return root, m, skel, P, ix, w


def _dense(ix, w, skel, bones):
    bi = {b: k for k, b in enumerate(bones)}
    W = np.zeros((len(ix), len(bones)))
    for c in range(ix.shape[1]):
        ok = (ix[:, c] >= 0) & (w[:, c] > 0)
        cols = np.array([bi[skel[i]] for i in ix[ok, c]], int)
        np.add.at(W, (np.nonzero(ok)[0], cols), w[ok, c])
    return W / np.maximum(W.sum(1, keepdims=True), 1e-9)


def skin_weights_at(P, S):
    """The body's weights at the closest rest-pose body point (no hands): dense (n, bones)."""
    R, T = S["rest"], S["tris"]
    A, B, C = R[T[:, 0]], R[T[:, 1]], R[T[:, 2]]
    cen = (A + B + C) / 3
    out = np.zeros((len(P), S["W"].shape[1]))
    for s in range(0, len(P), 256):
        p = P[s:s + 256]
        d2 = ((p[:, None, :] - cen[None]) ** 2).sum(-1)
        cand = np.argpartition(d2, 24, axis=1)[:, :24]
        Q = wsolve.closest_on_tris(p[:, None, :], A[cand], B[cand], C[cand])
        k = ((Q - p[:, None, :]) ** 2).sum(-1).argmin(1)
        t = T[cand[np.arange(len(p)), k]]
        q = Q[np.arange(len(p)), k]
        a, b, c = R[t[:, 0]], R[t[:, 1]], R[t[:, 2]]
        v0, v1, v2 = b - a, c - a, q - a
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
        d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
        den = np.maximum(d00 * d11 - d01 * d01, 1e-12)
        bv = (d11 * d20 - d01 * d21) / den
        bw = (d00 * d21 - d01 * d20) / den
        bu = 1 - bv - bw
        out[s:s + 256] = S["W"][t[:, 0]] * bu[:, None] + S["W"][t[:, 1]] * bv[:, None] + S["W"][t[:, 2]] * bw[:, None]
    return out


def leg_weights(P, S, joints):
    """Follow the nearest leg: the side's thigh bone (bn_<s>_hip) above its knee, the shin (bn_<s>_knee) below,
    eased over 6 cm at the knee and across the middle (x within 3 cm). joints: {name: rest position}."""
    bi = {b: k for k, b in enumerate(S["bones"])}
    W = np.zeros((len(P), len(S["bones"])))
    left = np.clip((P[:, 0] + 3.0) / 6.0, 0.0, 1.0)
    left = left * left * (3 - 2 * left)
    for side, f in (("l", left), ("r", 1 - left)):
        ky = joints["bn_%s_knee" % side][1]
        t = np.clip((ky + 3.0 - P[:, 1]) / 6.0, 0.0, 1.0)
        t = t * t * (3 - 2 * t)
        W[:, bi["bn_%s_hip" % side]] += f * (1 - t)
        W[:, bi["bn_%s_knee" % side]] += f * t
    return W


def lbs(P, W, M):
    """Posed points: sum_j w_j (M_j @ [p, 1]); M (bones, 4, 4)."""
    Ph = np.c_[P, np.ones(len(P))]
    out = np.zeros_like(P)
    for j in np.nonzero(W.any(0))[0]:
        m = W[:, j] > 0
        out[m] += W[m, j:j + 1] * (Ph[m] @ M[j].T)[:, :3]
    return out


def _sd(o, X, N, maxd=8.0):
    """Signed distance to the body by its smooth vertex normals at the closest point (face normals flip in the
    crotch and other hollows); deeper than maxd is not a real penetration (a leg is ~8 cm thick): counted as 0."""
    T = o.T[o.cand]
    A, B, C = o.P[T[..., 0]], o.P[T[..., 1]], o.P[T[..., 2]]
    Xk = np.broadcast_to(X[:, None, :], A.shape)
    R = wsolve.closest_on_tris(Xk, A, B, C)
    k = np.linalg.norm(Xk - R, axis=-1).argmin(1)
    i = np.arange(len(X))
    t, q = T[i, k], R[i, k]
    a, b, c = o.P[t[:, 0]], o.P[t[:, 1]], o.P[t[:, 2]]
    v0, v1, v2 = b - a, c - a, q - a
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-12)
    bv = (d11 * d20 - d01 * d21) / den
    bw = (d00 * d21 - d01 * d20) / den
    n = N[t[:, 0]] * (1 - bv - bw)[:, None] + N[t[:, 1]] * bv[:, None] + N[t[:, 2]] * bw[:, None]
    sd = ((X - q) * n).sum(1) / np.maximum(np.linalg.norm(n, axis=1), 1e-9)
    return np.where(sd < -maxd, 0.0, sd)


def signed(X, body, tris):
    o = wsolve.Obstacle(body, tris)
    o.refresh(X)
    loc, nrm, dist = o.query(X)
    return ((X - loc) * nrm).sum(1)


def fix(name, sex, gap=0.4, mu=4.0, nu=0.3, smooth_r=2.5, coarse=(24, 6.0), alt="leg", waist=3.0, above_knee=None,
        log=print, write=True):
    S = poses(sex)
    root, m, skel, P, ix, w = _read(name)
    Wc = _dense(ix, w, skel, S["bones"])
    chain = np.array(["skirt" in b for b in S["bones"]])
    if alt == "leg":   # everything below the waist may lean on the legs (the belt is pierced by a raised thigh)
        d = np.load(os.path.join(D, "poses_%s.npz" % sex))
        joints = {b: d["joints_rest"][k] for k, b in enumerate(S["bones"])}
        hip_y = (joints["bn_l_hip"][1] + joints["bn_r_hip"][1]) / 2
        hang = P[:, 1] < hip_y + waist
        if above_knee is not None:   # only the thigh-height part (below the knees the kneeling shin pulls it down)
            knee_y = (joints["bn_l_knee"][1] + joints["bn_r_knee"][1]) / 2
            hang &= P[:, 1] > knee_y + above_knee
        Ws = leg_weights(P, S, joints)
    else:
        hang = Wc[:, chain].sum(1) > 0.05
        Ws = skin_weights_at(P, S)
    if not hang.any():
        log("WFIX %s: nothing hangs" % name)
        return None
    H = np.nonzero(hang)[0]
    free = [k for k, n in enumerate(S["names"]) if S["kinds"][k] == "free" and n.split(":")[0] in FREE]
    ref = [k for k, n in enumerate(S["names"]) if S["kinds"][k] == "ref"]
    E = np.zeros((len(H), len(ALPHAS)))
    worst0 = np.zeros(len(H))
    for k in free:
        Pc, Ps = lbs(P[H], Wc[H], S["mats"][k]), lbs(P[H], Ws[H], S["mats"][k])
        o = wsolve.Obstacle(S["body"][k], S["tris"])
        o.refresh((Pc + Ps) / 2)
        for a_i, a in enumerate(ALPHAS):
            X = (1 - a) * Pc + a * Ps
            sd = _sd(o, X, S["nrm"][k])
            E[:, a_i] += np.maximum(gap - sd, 0.0) ** 2
            if a_i == 0:
                worst0 = np.maximum(worst0, -sd)
    for k in ref:
        Pc, Ps = lbs(P[H], Wc[H], S["mats"][k]), lbs(P[H], Ws[H], S["mats"][k])
        dd = ((Ps - Pc) ** 2).sum(1)
        E += mu / len(ref) * dd[:, None] * ALPHAS[None, :] ** 2
    E += nu * ALPHAS[None, :] ** 2
    alpha = np.zeros(len(P))
    if coarse:
        # one alpha per cell of (angle round the body, height), smoothed and interpolated: whole regions of a panel
        # move together (per-vertex choices tore the panels apart, 2026-11-10)
        na, dy = coarse
        Q = P[H]
        ang = np.arctan2(Q[:, 0], Q[:, 2]) % (2 * np.pi)
        y0 = Q[:, 1].min()
        ny = int((Q[:, 1].max() - y0) / dy) + 2
        fa, fy = ang / (2 * np.pi) * na, (Q[:, 1] - y0) / dy
        ia, iy = fa.astype(int) % na, np.clip(fy.astype(int), 0, ny - 1)
        C = np.zeros((na, ny, len(ALPHAS)))
        np.add.at(C, (ia, iy), E)
        cnt = np.zeros((na, ny))
        np.add.at(cnt, (ia, iy), 1)
        G = np.where(cnt > 0, ALPHAS[C.argmin(2)], np.nan)
        for _ in range(50):
            if not np.isnan(G).any():
                break
            nb = np.stack([np.roll(G, 1, 0), np.roll(G, -1, 0), np.pad(G, ((0, 0), (1, 0)), constant_values=np.nan)[:, :-1],
                           np.pad(G, ((0, 0), (0, 1)), constant_values=np.nan)[:, 1:]])
            m_ = np.nanmean(np.where(np.isnan(nb), np.nan, nb), 0) if np.isfinite(nb).any() else nb[0]
            G = np.where(np.isnan(G), m_, G)
        G = np.nan_to_num(G)
        for _ in range(2):
            G = (G * 2 + np.roll(G, 1, 0) + np.roll(G, -1, 0) + np.c_[G[:, :1], G[:, :-1]] + np.c_[G[:, 1:], G[:, -1:]]) / 6
        ta, ty = fa - 0.5, np.clip(fy - 0.5, 0, ny - 1.001)
        a0, b0 = np.floor(ta).astype(int), ty.astype(int)
        u, v = ta - a0, ty - b0
        a1, a0 = (a0 + 1) % na, a0 % na
        b1 = np.minimum(b0 + 1, ny - 1)
        alpha[H] = (G[a0, b0] * (1 - u) * (1 - v) + G[a1, b0] * u * (1 - v) + G[a0, b1] * (1 - u) * v + G[a1, b1] * u * v)
    else:
        alpha[H] = ALPHAS[E.argmin(1)]
        # smooth: each vertex takes the strongest alpha within smooth_r (both layers alike), eased by distance
        Q = P[H]
        sm = alpha[H].copy()
        for s in range(0, len(H), 256):
            d = np.sqrt(((Q[s:s + 256, None, :] - Q[None]) ** 2).sum(-1))
            f = np.clip(1.0 - d / smooth_r, 0.0, 1.0)
            sm[s:s + 256] = (f * alpha[H][None, :]).max(1)
        alpha[H] = sm
    Wn = (1 - alpha[:, None]) * Wc + alpha[:, None] * Ws
    # top 4, renormalised
    order = np.argsort(-Wn, axis=1)[:, :4]
    top = np.take_along_axis(Wn, order, 1)
    top[top < 0.01] = 0.0
    top /= np.maximum(top.sum(1, keepdims=True), 1e-9)
    # report: worst depth before / after over the free poses, standing drift
    worst1, drift = np.zeros(len(H)), np.zeros(len(H))
    Wt = np.zeros_like(Wn)
    np.put_along_axis(Wt, order, top, 1)
    for k in free:
        X = lbs(P[H], Wt[H], S["mats"][k])
        o = wsolve.Obstacle(S["body"][k], S["tris"])
        o.refresh(X)
        worst1 = np.maximum(worst1, -_sd(o, X, S["nrm"][k]))
    for k in ref:
        drift = np.maximum(drift, np.linalg.norm(lbs(P[H], Wt[H], S["mats"][k]) - lbs(P[H], Wc[H], S["mats"][k]), axis=1))
    log("WFIX %s: %d hanging, alpha>0 on %d; deepest %.1f -> %.1f cm (inside >0.5 cm: %d -> %d); standing drift max %.1f, 99%% %.1f cm" % (
        name, len(H), int((alpha > 0).sum()), worst0.max(), worst1.max(), int((worst0 > 0.5).sum()), int((worst1 > 0.5).sum()),
        drift.max(), np.percentile(drift, 99)))
    if write:
        from io_pdx_mesh import pdx_data
        inv = {b: i for i, b in skel.items()}
        nb = ix.shape[1]
        nix = np.full((len(P), nb), -1, int)
        nw = np.zeros((len(P), nb))
        for c in range(4):
            ok = top[:, c] > 0
            nix[ok, c] = [inv[S["bones"][j]] for j in order[ok, c]]
            nw[ok, c] = top[ok, c]
        sk = m.find("skin")
        sk.attrib["ix"] = [int(x) for x in nix.ravel()]
        sk.attrib["w"] = [float(x) for x in nw.ravel()]
        pdx_data.write_meshfile("%s/%s.mesh" % (cs.OUT, name), root)
    return dict(worst0=float(worst0.max()), worst1=float(worst1.max()), drift=float(drift.max()))


CHECK = ("throneRoom_kneel1_1", "throneRoom_kneel2_1", "throneRoom_ruler1_1", "throneRoom_ruler2_1", "throneRoom_ruler3_1",
         "throneRoom_bow1_1", "idle_1", "idle_2")


def audit_row(name, sex, clips=CHECK):
    """Maya audit (vertices > 0.15 cm inside the body / deepest cm) per clip: the check that counts."""
    import audit as au
    cs.new_scene()
    au._BODY.clear()
    b = cs.load_body(sex)
    p = cs.load_piece(name)
    out = {}
    for c in clips:
        cs.pose(sex, c)
        m = au.measure(p, b)
        out[c.replace("throneRoom_", "")] = (m["torso_n"], m["torso_max"])
    return out

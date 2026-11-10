"""Numeric mesh audit in the Maya GUI, on a scene made with ck3scene.py (body + pieces on one skeleton).

    import audit; audit.static(piece)            # once per piece, in the rest pose: weights, shells, normals, UVs
    audit.measure(piece, body)                   # in the current shape weights and pose: clipping and stretch

All lengths in cm (CK3 units). Thresholds: see the constants. Results are plain dicts so a driver can write JSON.
"""
import re
import maya.cmds as mc
import maya.api.OpenMaya as om
import numpy as np

DEPTH = 0.15      # a piece vertex deeper than this inside the body is clipping
POKE = 0.15       # a body vertex this far in front of the piece surface pokes through it
STRETCH = (0.5, 1.6)  # edge length ratio in a pose against the rest pose
ARM_KEYS = ("elbow", "forearm", "wrist", "hand", "finger", "thumb", "_fi_", "prop", "sleeve")


def _dag(mesh):
    sel = om.MSelectionList()
    sel.add(mesh)
    return sel.getDagPath(0)


def pts(mesh):
    fn = om.MFnMesh(_dag(mesh))
    return np.array(fn.getPoints(om.MSpace.kWorld))[:, :3]


def vnormals(mesh):
    fn = om.MFnMesh(_dag(mesh))
    return np.array(fn.getVertexNormals(False, om.MSpace.kWorld))[:, :3]


def tris(mesh):
    fn = om.MFnMesh(_dag(mesh))
    counts, ids = fn.getTriangles()
    return np.array(ids).reshape(-1, 3), np.repeat(np.arange(len(counts)), counts)


def edges(mesh):
    it = om.MItMeshEdge(_dag(mesh))
    e = []
    while not it.isDone():
        e.append((it.vertexId(0), it.vertexId(1)))
        it.next()
    return np.array(e)


def shells(mesh):
    """Connected component id per vertex."""
    n = mc.polyEvaluate(mesh, vertex=True)
    par = np.arange(n)

    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for a, b in edges(mesh):
        ra, rb = f(a), f(b)
        if ra != rb:
            par[ra] = rb
    return np.array([f(i) for i in range(n)])


def skin_weights(mesh):
    sc = mc.ls(mc.listHistory(mesh), type="skinCluster")
    if not sc:
        return None, []
    sc = sc[0]
    infl = mc.skinCluster(sc, query=True, influence=True)
    sel = om.MSelectionList()
    sel.add(sc)
    import maya.api.OpenMayaAnim as oma
    fn = oma.MFnSkinCluster(sel.getDependNode(0))
    comp = om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
    om.MFnSingleIndexedComponent(comp).setCompleteData(mc.polyEvaluate(mesh, vertex=True))
    w, ninf = fn.getWeights(_dag(mesh), comp)
    return np.array(w).reshape(-1, ninf), infl


_BODY = {}


def body_info(body):
    """Dominant joint and arm/torso region per body vertex (cached)."""
    if body not in _BODY:
        w, infl = skin_weights(body)
        dom = np.array(infl)[w.argmax(1)]
        arm = np.array([any(k in j for k in ARM_KEYS) for j in dom])
        _BODY[body] = {"dom": dom, "arm": arm}
    return _BODY[body]


def _closest(mesh, P):
    """Closest point, its interpolated normal and face per query point (world space; our meshes sit at the origin)."""
    dp = _dag(mesh)
    dp.extendToShape()
    mi = om.MMeshIntersector()
    mi.create(dp.node(), dp.inclusiveMatrix())
    Q = np.empty((len(P), 3))
    N = np.empty((len(P), 3))
    F = np.empty(len(P), int)
    for i, p in enumerate(P):
        r = mi.getClosestPoint(om.MPoint(*p), 1000.0)
        q, n = r.point, r.normal
        Q[i] = (q.x, q.y, q.z)
        N[i] = (n.x, n.y, n.z)
        F[i] = r.face
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    return Q, N, F


def _body_vertex_of_face(body, F):
    fn = om.MFnMesh(_dag(body))
    return np.array([fn.getPolygonVertices(int(f))[0] for f in F])


def measure(piece, body, rest_lengths=None, e=None):
    """Clipping and stretch in the current pose and shape weights."""
    P = pts(piece)
    B = pts(body)
    Q, N, F = _closest(body, P)
    sd = np.einsum("ij,ij->i", P - Q, N)  # signed distance of piece vertices to the body (negative: inside)
    bi = body_info(body)
    bv = _body_vertex_of_face(body, F)
    arm = bi["arm"][bv]
    inside = sd < -DEPTH
    res = {"verts": len(P)}
    for name, m in (("torso", inside & ~arm), ("arm", inside & arm)):
        res[name + "_n"] = int(m.sum())
        res[name + "_max"] = round(float(-sd[m].min()), 2) if m.any() else 0.0
        if m.any():
            k = np.where(m)[0][np.argmin(sd[m])]
            res[name + "_at"] = [round(float(x), 1) for x in P[k]] + [str(bi["dom"][bv[k]])]
    # body poking through the piece: body vertices near the piece, in front of its surface
    lo, hi = P.min(0) - 2, P.max(0) + 2
    near = np.where(np.all((B > lo) & (B < hi), axis=1))[0]
    if len(near):
        G, NG, _ = _closest(piece, B[near])
        NB = vnormals(body)[near]
        cosn = np.einsum("ij,ij->i", NG, NB)
        NG[cosn < 0] *= -1
        facing = np.abs(cosn) > 0.5  # the piece's surface lies over the skin there (not a tube's top or a panel's edge)
        d = B[near] - G
        dist = np.linalg.norm(d, axis=1)
        along = np.einsum("ij,ij->i", d, NG)
        pk = (along > POKE) & (dist < 2.0) & (along > 0.7 * dist) & facing & ~bi["arm"][near]
        res["poke_n"] = int(pk.sum())
        res["poke_max"] = round(float(along[pk].max()), 2) if pk.any() else 0.0
        if pk.any():
            k = near[pk][np.argmax(along[pk])]
            res["poke_at"] = [round(float(x), 1) for x in B[k]] + [str(bi["dom"][k])]
    if rest_lengths is not None:
        L = np.linalg.norm(P[e[:, 0]] - P[e[:, 1]], axis=1)
        r = L / np.maximum(rest_lengths, 1e-6)
        bad = (r < STRETCH[0]) | (r > STRETCH[1])
        bad &= rest_lengths > 0.05
        res["stretch_n"] = int(bad.sum())
        res["stretch_max"] = round(float(max(r.max(), 1 / max(r.min(), 1e-6))), 2)
    return res


def static(piece, body):
    """Rest pose, no shapes: influences, shells (floating, facing inwards), UV stretch."""
    out = {}
    w, infl = skin_weights(piece)
    if w is None:
        out["skin"] = "none"
    else:
        nz = (w > 1e-4).sum(1)
        out["max_infl"] = int(nz.max())
        out["infl_gt4"] = int((nz > 4).sum())
        s = w.sum(1)
        out["unnormalised"] = int((np.abs(s - 1) > 0.01).sum())
        # far influences: a vertex mostly driven by a joint far away
        P = pts(piece)
        jp = np.array([mc.xform(j, query=True, worldSpace=True, translation=True) for j in infl])
        dom = w.argmax(1)
        dfar = np.linalg.norm(P - jp[dom], axis=1)
        out["far_joint_n"] = int((dfar > 45).sum())
        out["far_joint_max"] = round(float(dfar.max()), 1)
        out["dom_joints"] = sorted(set(np.array(infl)[dom]))[:40]
    P = pts(piece)
    T, Tf = tris(piece)
    sh = shells(piece)
    ids, inv = np.unique(sh, return_inverse=True)
    # face normals (world) and the body normal nearest each face centre
    C = P[T].mean(1)
    FN = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    A = np.linalg.norm(FN, axis=1)
    FN /= np.maximum(A[:, None], 1e-9)
    Q, NB, _ = _closest(body, C)
    sdc = np.einsum("ij,ij->i", C - Q, NB)
    inward = np.einsum("ij,ij->i", FN, NB) < -0.2
    tshell = inv[T[:, 0]]
    sl = []
    for k in range(len(ids)):
        m = tshell == k
        vm = inv == k
        area = float(A[m].sum() / 2)
        if area <= 0:
            continue
        inw = float((A[m] * inward[m]).sum() / max(A[m].sum(), 1e-9))
        sl.append({"shell": k, "verts": int(vm.sum()), "area": round(area, 1), "inward": round(inw, 2),
                   "body_gap_min": round(float(np.abs(sdc[m]).min()), 2),
                   "centre": [round(float(x), 1) for x in P[vm].mean(0)]})
    # floating: a shell far from the body and from every other shell
    for s_ in sl:
        vm = inv == s_["shell"]
        others = P[~vm]
        if len(others):
            Pi = P[vm][:: max(1, vm.sum() // 200)]
            d = np.sqrt(((Pi[:, None, :] - others[None, :: max(1, len(others) // 2000), :]) ** 2).sum(-1)).min()
        else:
            d = 1e9
        s_["other_gap_min"] = round(float(d), 2)
        s_["floating"] = bool(s_["body_gap_min"] > 4.0 and d > 1.0)
    out["shells"] = len(sl)
    out["floating"] = [s_ for s_ in sl if s_["floating"]]
    # inward-facing shells: worth a look when most of a shell faces the body
    out["inward_shells"] = [s_ for s_ in sl if s_["inward"] > 0.6 and s_["area"] > 2]
    out["inward_area_frac"] = round(float((A * inward).sum() / A.sum()), 2)
    # UVs: area ratio per face against its shell's median
    fn = om.MFnMesh(_dag(piece))
    us, vs = fn.getUVs()
    us, vs = np.array(us), np.array(vs)
    if len(us):
        uvc, uvi = fn.getAssignedUVs()
        # per polygon-vertex UV ids, in the same order as getTriangles' local vertices: rebuild per triangle
        tri_uv = []
        it = om.MItMeshPolygon(_dag(piece))
        while not it.isDone():
            ntri = it.numTriangles()
            if ntri:
                vl = list(it.getVertices())
                for t_ in range(ntri):
                    _, tv = it.getTriangle(t_)
                    tri_uv.append([it.getUVIndex(vl.index(v)) for v in tv])
            it.next()
        tri_uv = np.array(tri_uv)
        UV = np.stack([us, vs], 1)
        ua = np.abs(np.cross(UV[tri_uv[:, 1]] - UV[tri_uv[:, 0]], UV[tri_uv[:, 2]] - UV[tri_uv[:, 0]])) / 2
        ratio = ua / np.maximum(A / 2, 1e-9)
        bad = np.zeros(len(T), bool)
        for k in range(len(ids)):
            m = (tshell == k) & (A > 1e-4)
            if m.sum() < 3:
                continue
            med = np.median(ratio[m])
            bad[m] = (ratio[m] > med * 4) | (ratio[m] < med / 4)
        out["uv_bad_frac"] = round(float((A * bad).sum() / A.sum()), 3)
        out["uv_out_of_range"] = int(((UV < -0.001) | (UV > 1.001)).any(1).sum())
        out["uv_zero_faces"] = int((ua < 1e-9).sum())
    else:
        out["uv"] = "none"
    out["degenerate_faces"] = int((A < 1e-6).sum())
    return out

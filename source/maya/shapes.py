"""New body-shape blendshapes for a piece that lacks one (giantish, imgan, ...), in the Maya GUI.

    import shapes; shapes.make_shape("ek2lc_m_reach_hide_01", "giantish")   # body + piece loaded (ck3scene)
    shapes.link_assets("ek2lc_m_reach_hide_01", "giantish")                 # .asset lines (every asset using it)

How: the body's own displacement for that shape, carried to each piece vertex as a smooth field (inverse-square
weights of the 8 nearest body vertices; forearms and hands left out, they hang beside the hips), then any vertex
that ends up closer to the skin than at rest (up to 0.3 cm) is pushed back out along the body normal. Layers worn
together get the same field, so they keep their spacing. Normals: the file's own normals turned by the change of
the computed ones; tangents and UVs from the base file. Written like the existing shape files (base mesh without
its skin block), Maya z negated back to the file's space.
"""
import os
import re
import numpy as np
import maya.cmds as mc
import ck3scene as cs
import audit as au

ARM = au.ARM_KEYS


def _arm_mask(body):
    return au.body_info(body)["arm"]


def _vertex_normals(P, T, weld=None):
    N = np.zeros_like(P)
    fn = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    for k in range(3):
        np.add.at(N, T[:, k], fn)
    if weld is not None:  # share across split (UV seam) copies of a vertex
        S = np.zeros((weld.max() + 1, 3))
        np.add.at(S, weld, N)
        N = S[weld]
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def _weld_ids(P, tol=1e-4):
    key = np.round(P / tol).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    return inv.ravel()


def shape_field(piece, body, attr, k=8, keep=0.3):
    """Piece points in the shape (Maya space), from the body's displacement."""
    cs.rest_pose()
    cs.set_shape(None)
    B0 = au.pts(body)
    G0 = au.pts(piece)
    cs.set_shape(attr, 1.0, only=[body])
    B1 = au.pts(body)
    cs.set_shape(None)
    D = B1 - B0
    ok = ~_arm_mask(body)
    Bk, Dk = B0[ok], D[ok]
    G1 = np.empty_like(G0)
    for s in range(0, len(G0), 500):
        g = G0[s:s + 500]
        d2 = (g ** 2).sum(1)[:, None] + (Bk ** 2).sum(1)[None, :] - 2 * g @ Bk.T
        d2 = np.maximum(d2, 0)
        nn = np.argpartition(d2, k, axis=1)[:, :k]
        dd = np.take_along_axis(d2, nn, 1)
        w = 1.0 / np.maximum(dd, 0.25)
        G1[s:s + 500] = g + (Dk[nn] * w[..., None]).sum(1) / w.sum(1, keepdims=True)
    # clearance: no closer to the skin than at rest (up to `keep`)
    Q0, N0, _ = au._closest(body, G0)
    rc = ((G0 - Q0) * N0).sum(1)
    cs.set_shape(attr, 1.0, only=[body])
    Q1, N1, _ = au._closest(body, G1)
    cs.set_shape(None)
    sd = ((G1 - Q1) * N1).sum(1)
    want = np.minimum(np.maximum(rc, 0.0), keep)
    push = np.where((rc > 0) & (sd < want), want - sd, 0.0)
    G1 += push[:, None] * N1
    return G0, G1, int((push > 0).sum())


def write_shape(piece, suffix, G0, G1, folder=cs.OUT):
    import sys
    from io_pdx_mesh import pdx_data
    base = pdx_data.read_meshfile("%s/%s.mesh" % (folder, piece))
    mb = base.find("object")[0].find("mesh")
    nv = len(mb.attrib["p"]) // 3
    assert nv == len(G1)
    Pf0 = np.array(mb.attrib["p"]).reshape(-1, 3)
    flip = np.array([1.0, 1.0, -1.0])
    # (the skinned rest pose drifts up to ~0.01 cm from the file on deep skirt bones: write the change onto the file)
    assert np.abs(Pf0 - G0 * flip).max() < 0.05, "file/Maya vertex order or space mismatch"
    T = np.array(mb.attrib["tri"]).reshape(-1, 3)
    P1 = Pf0 + (G1 - G0) * flip
    weld = _weld_ids(Pf0)
    n0 = np.array(mb.attrib["n"]).reshape(-1, 3)
    c0 = _vertex_normals(Pf0, T, weld)
    c1 = _vertex_normals(P1, T, weld)
    n1 = n0 + (c1 - c0)
    n1 /= np.maximum(np.linalg.norm(n1, axis=1, keepdims=True), 1e-12)
    # template: an existing shape file of this piece (same layout), else the base without its skin
    tmpl = None
    for f in sorted(os.listdir(folder)):
        if f.startswith(piece + "_bs_") and f.endswith(".mesh"):
            tmpl = "%s/%s" % (folder, f)
            break
    root = pdx_data.read_meshfile(tmpl) if tmpl else base
    m = root.find("object")[0].find("mesh")
    if m.find("skin") is not None:
        m.remove(m.find("skin"))
    m.attrib["p"] = [float(x) for x in P1.ravel()]
    m.attrib["n"] = [float(x) for x in n1.ravel()]
    for key in ("ta", "u0", "tri"):
        if key in mb.attrib:
            m.attrib[key] = list(mb.attrib[key])
    ab = m.find("aabb")
    lo, hi = P1.min(0), P1.max(0)
    ab.attrib["min"] = [float(x) for x in lo]
    ab.attrib["max"] = [float(x) for x in hi]
    c = (lo + hi) / 2
    m.attrib["boundingsphere"] = [float(x) for x in c] + [float(np.linalg.norm(P1 - c, axis=1).max())]
    out = "%s/%s_bs_%s.mesh" % (folder, piece, suffix)
    pdx_data.write_meshfile(out, root)
    return out


def _neighbours(T, weld):
    """Vertex adjacency (welded across UV seams) as an index list per vertex."""
    n = len(weld)
    nb = [set() for _ in range(n)]
    W = weld
    for a, b, c in T:
        for x, y in ((a, b), (b, c), (c, a)):
            nb[x].add(y)
            nb[y].add(x)
    # seam copies share their neighbours
    groups = {}
    for v, g in enumerate(W):
        groups.setdefault(g, []).append(v)
    out = []
    for v in range(n):
        s = set()
        for u in groups[W[v]]:
            s |= nb[u]
        out.append(np.array(sorted(s), int))
    return out


def _spread(c, nb, iters=4):
    """Spread a per-vertex push (V x 3) to neighbours, never lowering a vertex's own push (as smooth_max)."""
    m = np.linalg.norm(c, axis=1)
    for _ in range(iters):
        avg = np.array([c[k].mean(0) if len(k) else c[v] for v, k in enumerate(nb)])
        am = np.linalg.norm(avg, axis=1)
        take = am > m
        c = np.where(take[:, None], avg, c)
        m = np.maximum(m, am)
    return c


def repair(piece, body, states, keep=0.3, folder=cs.OUT, passes=1):
    """Push the piece's shapes out where it clips in the given shape states ({attr: weight} dicts, e.g.
    {"bs_body_fat_1": 1, "bs_body_muscular_1": 1}). A combination's push is shared between its shapes by how
    far each moves the body outwards there. Rewrites the piece's existing _bs_ files. Returns {state: (before,
    after)} deepest points inside the body."""
    from io_pdx_mesh import pdx_data
    flip = np.array([1.0, 1.0, -1.0])
    sex = "female" if piece.startswith("ek2lc_f_") else "male"
    sa = cs.suffix_attr(sex)
    attr_suffix = {a: k for k, a in sa.items()}
    have = {a: k for k, a, f in cs.piece_shapes(piece)}
    base = pdx_data.read_meshfile("%s/%s.mesh" % (folder, piece))
    mb = base.find("object")[0].find("mesh")
    T = np.array(mb.attrib["tri"]).reshape(-1, 3)
    Pf0 = np.array(mb.attrib["p"]).reshape(-1, 3)
    weld = _weld_ids(Pf0)
    nb = _neighbours(T, weld)
    cs.rest_pose()
    cs.set_shape(None)
    G0 = au.pts(piece)
    Q0, N0, _ = au._closest(body, G0)
    rc = ((G0 - Q0) * N0).sum(1)
    want = np.minimum(np.maximum(rc, 0.0), keep)
    B0 = au.pts(body)
    Nb0 = au.vnormals(body)
    extra = {a: np.zeros_like(G0) for a in have}  # Maya-space additions per shape
    report = {}
    for ws in [s for s in states for _ in range(passes)]:
        ws = {a: w for a, w in ws.items() if a in have}
        if not ws:
            continue
        name = "+".join(attr_suffix[a] for a in ws)

        def state_pts():
            cs.set_shape(None)
            for a, w in ws.items():
                cs.set_shape(a, w)
            G = au.pts(piece) + sum(extra[a] * w for a, w in ws.items())
            return G
        G = state_pts()
        Q, N, F = au._closest(body, G)
        sd = ((G - Q) * N).sum(1)
        need = np.maximum(want - sd, 0.0)
        before = float(max(0.0, -sd.min()))
        if not need.any():
            report[name] = (round(before, 2), round(before, 2))
            cs.set_shape(None)
            continue
        c = _spread(need[:, None] * N, nb)
        # share between the state's shapes by the body's outward move at each point (nearest body vertex)
        moves = {}
        for a in ws:
            cs.set_shape(None)
            cs.set_shape(a, 1.0, only=[body])
            moves[a] = au.pts(body) - B0
        cs.set_shape(None)
        bb = (B0 ** 2).sum(1)
        nn = np.concatenate([((G0[s:s + 500] ** 2).sum(1)[:, None] + bb[None, :] - 2 * G0[s:s + 500] @ B0.T).argmin(1)
                             for s in range(0, len(G0), 500)])
        out = {a: np.maximum((moves[a][nn] * Nb0[nn]).sum(1), 0.0) for a in ws}
        tot = sum(out.values()) + 1e-6
        for a, w in ws.items():
            share = out[a] / tot if len(ws) > 1 else np.ones(len(G0))
            extra[a] += c * (share / max(w, 1e-6))[:, None]
        G = state_pts()
        Q, N, F = au._closest(body, G)
        after = float(max(0.0, -((G - Q) * N).sum(1).min()))
        report[name] = (report.get(name, (round(before, 2),))[0], round(after, 2))
        cs.set_shape(None)
    # write the changed shapes
    for a, e in extra.items():
        if not np.abs(e).max() > 1e-4:
            continue
        f = "%s/%s_bs_%s.mesh" % (folder, piece, have[a])
        root = pdx_data.read_meshfile(f)
        m = root.find("object")[0].find("mesh")
        P = np.array(m.attrib["p"]).reshape(-1, 3) + e * flip
        n0 = np.array(m.attrib["n"]).reshape(-1, 3)
        Pold = np.array(m.attrib["p"]).reshape(-1, 3)
        n1 = n0 + (_vertex_normals(P, T, weld) - _vertex_normals(Pold, T, weld))
        n1 /= np.maximum(np.linalg.norm(n1, axis=1, keepdims=True), 1e-12)
        m.attrib["p"] = [float(x) for x in P.ravel()]
        m.attrib["n"] = [float(x) for x in n1.ravel()]
        lo, hi = P.min(0), P.max(0)
        m.find("aabb").attrib["min"] = [float(x) for x in lo]
        m.find("aabb").attrib["max"] = [float(x) for x in hi]
        cc = (lo + hi) / 2
        m.attrib["boundingsphere"] = [float(x) for x in cc] + [float(np.linalg.norm(P - cc, axis=1).max())]
        pdx_data.write_meshfile(f, root)
    return report


def repair_base(piece, body, want=0.15, folder=cs.OUT):
    """Push the rest mesh out where it is inside the skin or touching it (closer than 0.05 cm): to `want`,
    spread to neighbours; every shape file gets the same offset, so the shapes keep their change."""
    from io_pdx_mesh import pdx_data
    flip = np.array([1.0, 1.0, -1.0])
    cs.rest_pose()
    cs.set_shape(None)
    G0 = au.pts(piece)
    Q, N, _ = au._closest(body, G0)
    sd = ((G0 - Q) * N).sum(1)
    need = np.where(sd < 0.05, want - sd, 0.0)
    if not need.any():
        return 0, 0.0
    f0 = "%s/%s.mesh" % (folder, piece)
    base = pdx_data.read_meshfile(f0)
    mb = base.find("object")[0].find("mesh")
    T = np.array(mb.attrib["tri"]).reshape(-1, 3)
    Pf0 = np.array(mb.attrib["p"]).reshape(-1, 3)
    weld = _weld_ids(Pf0)
    c = _spread(need[:, None] * N, _neighbours(T, weld)) * flip
    files = [f0] + ["%s/%s" % (folder, f) for f in sorted(os.listdir(folder)) if f.startswith(piece + "_bs_") and f.endswith(".mesh")]
    for f in files:
        root = base if f == f0 else pdx_data.read_meshfile(f)
        m = root.find("object")[0].find("mesh")
        Pold = np.array(m.attrib["p"]).reshape(-1, 3)
        P = Pold + c
        n0 = np.array(m.attrib["n"]).reshape(-1, 3)
        n1 = n0 + (_vertex_normals(P, T, weld) - _vertex_normals(Pold, T, weld))
        n1 /= np.maximum(np.linalg.norm(n1, axis=1, keepdims=True), 1e-12)
        m.attrib["p"] = [float(x) for x in P.ravel()]
        m.attrib["n"] = [float(x) for x in n1.ravel()]
        lo, hi = P.min(0), P.max(0)
        m.find("aabb").attrib["min"] = [float(x) for x in lo]
        m.find("aabb").attrib["max"] = [float(x) for x in hi]
        cc = (lo + hi) / 2
        m.attrib["boundingsphere"] = [float(x) for x in cc] + [float(np.linalg.norm(P - cc, axis=1).max())]
        pdx_data.write_meshfile(f, root)
    return int((need > 0).sum()), float(-sd.min())


def repair_states(sex):
    st = [{a: 1.0} for k, a, f in cs.body_shapes(sex)]
    st += [{"bs_body_fat_1": 1.0, "bs_body_muscular_1": 1.0}, {"bs_khajiit_body": 1.0, "khajiit_digitigrade_bs": 1.0}]
    if sex == "female":
        st.append({"bs_body_pregnant_1": 1.0, "bs_body_fat_1": 1.0})
    return st


def repair_all(sex, pieces=None, log_path=None, states=None, passes=1):
    """repair() on every piece of one sex, in a fresh scene; one log line per piece (runs past the MCP timeout:
    watch the log)."""
    import glob
    import json
    import time
    log_path = log_path or cs.MOD + "/source/build_logs/repair_%s.log" % sex
    s1 = sex[0]
    if pieces is None:
        pieces = sorted(os.path.basename(p)[:-5] for p in glob.glob("%s/ek2lc_%s_*.mesh" % (cs.OUT, s1)) if "_bs_" not in p)
    cs.new_scene()
    au._BODY.clear()
    body = cs.load_body(sex)
    cs._store_rest()
    with open(log_path, "w") as fh:
        for n in pieces:
            t = time.time()
            try:
                p = cs.load_piece(n)
                r = repair(p, body, states or repair_states(sex), passes=passes)
                changed = {k: v for k, v in r.items() if v[0] > 0.0}
                fh.write("%s %.1fs %s\n" % (n, time.time() - t, json.dumps(changed)))
            except Exception as e:  # noqa
                fh.write("%s FAILED %s\n" % (n, str(e)[:200]))
            fh.flush()
            for x in (n, n + "_BS"):
                if mc.objExists(x):
                    mc.delete(x)
        fh.write("DONE\n")


def assets_using(piece, folder=cs.OUT):
    out = []
    for f in sorted(os.listdir(folder)):
        if f.endswith(".asset"):
            t = open("%s/%s" % (folder, f), encoding="utf-8-sig").read()
            if re.search(r'file\s*=\s*"%s\.mesh"' % re.escape(piece), t):
                out.append(f)
    return out


def link_assets(piece, suffix, attr, folder=cs.OUT):
    """Add the blend_shape and attribute lines to every .asset that uses the piece's mesh (after its last ones)."""
    done = []
    for f in assets_using(piece, folder):
        p = "%s/%s" % (folder, f)
        raw = open(p, "rb").read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        t = raw.decode("utf-8-sig")
        nl = "\r\n" if "\r\n" in t else "\n"
        if ("_bs_%s.mesh" % suffix) in t:
            continue
        # pdxmesh block: after the last blend_shape line
        bl = list(re.finditer(r'^\tblend_shape = \{ id = "([^"]+)_bs_[a-z_0-9]+"\ttype = "[^"]+" \}' + re.escape(nl), t, re.M))
        al = list(re.finditer(r'^\tattribute = \{ name = "[^"]+"\tblend_shape = "([^"]+)_bs_[a-z_0-9]+" \}' + re.escape(nl), t, re.M))
        if not bl or not al:
            print("no shape lines to follow in", f)
            continue
        idn = bl[-1].group(1)
        en = al[-1].group(1)
        t = t[:bl[-1].end()] + '\tblend_shape = { id = "%s_bs_%s"\ttype = "%s_bs_%s.mesh" }%s' % (idn, suffix, piece, suffix, nl) + t[bl[-1].end():]
        al = list(re.finditer(r'^\tattribute = \{ name = "[^"]+"\tblend_shape = "([^"]+)_bs_[a-z_0-9]+" \}' + re.escape(nl), t, re.M))
        t = t[:al[-1].end()] + '\tattribute = { name = "%s"\tblend_shape = "%s_bs_%s" }%s' % (attr, en, suffix, nl) + t[al[-1].end():]
        open(p, "wb").write((b"\xef\xbb\xbf" if bom else b"") + t.encode("utf-8"))
        done.append(f)
    return done

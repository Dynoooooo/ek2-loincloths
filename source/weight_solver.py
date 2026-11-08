"""Bone-weight solver for the pieces that hang below the hips (added 2026-11-07).

Why: the game moves a piece only through bone weights (linear blend skinning). Copying the skin's weights, or
the skirt chains' as vanilla robes do, keeps a piece right in the idles, but when kneeling, sitting on the throne
or bowing the thighs and the hip creases pass through flaps, aprons, belts and strips (vanilla robes clip there
too: in the throne room's one-knee kneel the raised knee goes 15 cm through a vanilla robe). No single rule works
for every part, so the weights are solved: for every free vertex, a mix of up to four nearby bones such that over
a set of the game's own animation frames

  - it stays outside the body (and so outside the leggings, which hug the skin) by a margin,
  - the piece keeps its shape (edge lengths stay as at rest: no stretching or crumpling),
  - in the reference poses (idles, emotions: the looks already checked in game) it stays where it was,
  - neighbouring vertices have similar weights (the piece moves as one), and the left and right halves mirror.

It is a projected-gradient descent on the weights (each vertex's weights stay >= 0 and sum to 1).
The caller supplies the poses: per pose, the deform matrix of every candidate bone and the posed obstacles.
"""
import math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def simplex_proj(Y, allowed=None):
    """Project each row of Y onto the probability simplex (only the allowed entries may be non-zero)."""
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


def lbs(rest, W, mats):
    """Positions of points `rest` (V x 3) with weights W (V x B) under bone deform matrices `mats` (B x 4 x 4)."""
    h = np.c_[rest, np.ones(len(rest))]
    Q = np.einsum("bij,vj->vbi", mats, h)[:, :, :3]
    return np.einsum("vb,vbi->vi", W, Q)


class Problem:
    """rest: V x 3; edges: E x 2 (mesh edges plus any ties between islands); W0: V x B start weights;
    free: V bools; allowed: V x B bools (candidate bones per vertex); poses: list of dicts with
      mats (B x 4 x 4), obst (BVHTree of the posed obstacles), ref (V x 3 positions to keep, or None),
      w (weight of this pose's penetration term, default 1);
    margin: V clearances wanted; mirror_v / mirror_b: vertex and bone index maps of the left-right mirror;
    near: V x 3 per pose is computed lazily to skip vertices far from every obstacle."""

    def __init__(self, rest, edges, W0, free, allowed, poses, margin, mirror_v=None, mirror_b=None, stick=None, down=None):
        self.rest = np.asarray(rest, float)
        self.V = len(self.rest)
        self.E = np.asarray(edges, int).reshape(-1, 2)
        self.L = np.linalg.norm(self.rest[self.E[:, 0]] - self.rest[self.E[:, 1]], axis=1)
        self.W = np.array(W0, float)
        self.B = self.W.shape[1]
        self.free = np.asarray(free, bool)
        self.allowed = np.asarray(allowed, bool) | (self.W > 0)  # the start weights are always allowed
        self.poses = poses
        self.margin = np.broadcast_to(np.asarray(margin, float), (self.V,)).copy()
        self.mv, self.mb = mirror_v, mirror_b
        self.stick = stick  # optional V array: the most a vertex may sit off the obstacles (strips that must cover)
        # gravity: (upper, lower) vertex pairs of hanging parts; in no pose may the lower one rise above the upper
        # one by more than `down_slack` cm (a flap lies flat on a lap at most; it never points up)
        self.down = np.asarray(down if down is not None else [], int).reshape(-1, 2)
        self.down_slack = 1.0
        # gravity: per-vertex weight of a pull downwards in the poses without a reference look (kneeling, sitting):
        # a hanging part settles onto the thighs or shins under it instead of sticking out stiffly
        self.grav = np.zeros(self.V)
        h = np.c_[self.rest, np.ones(self.V)]
        self.fidx = np.nonzero(self.free)[0]
        for p in poses:
            p["Q"] = np.einsum("bij,vj->vbi", p["mats"], h)[:, :, :3]
            p["skip"] = np.zeros(self.V, int)  # iterations to skip a vertex that is far from the obstacles

    def positions(self, p, W=None):
        return np.einsum("vb,vbi->vi", self.W if W is None else W, p["Q"])

    def _contact(self, p, X, gX, lam, E, full=False):
        """Penetration (and stick) term for one pose; adds to gX and E."""
        obst = p["obst"]
        if obst is None:
            return
        wpose = p.get("w", 1.0)
        for v in self.fidx:
            if not full and p["skip"][v] > 0:
                p["skip"][v] -= 1
                continue
            x = Vector(X[v])
            loc, nor, fi, d = obst.find_nearest(x, 15.0)
            if loc is None:
                p["skip"][v] = 8
                continue
            sd = (x - loc).dot(nor)
            m = self.margin[v]
            if sd < m:
                e = m - sd
                E["pen"] += lam["pen"] * wpose * e * e
                gX[v] -= lam["pen"] * wpose * 2 * e * np.array(nor)
            elif self.stick is not None and sd > self.stick[v]:
                e = sd - self.stick[v]
                E["stick"] += lam.get("stick", 0.0) * e * e
                gX[v] += lam.get("stick", 0.0) * 2 * e * np.array(nor)
            elif sd > m + 4.0 and (self.stick is None or sd < self.stick[v] - 4.0):
                p["skip"][v] = 6  # far from both limits: look again in a few iterations
        # Optional surface samples for direct fitting in Blender. Vertex-only contact
        # misses a thigh or knee passing through the middle of a broad cloth quad.
        for ids in getattr(self, 'surface_faces', ()):
            x = Vector(X[ids].mean(axis=0))
            loc, nor, fi, d = obst.find_nearest(x, 8.0)
            if loc is None:
                continue
            e = float(self.margin[ids].mean()) - (x - loc).dot(nor)
            if e > 0:
                E['pen'] += lam['pen'] * wpose * e * e
                g = -lam['pen'] * wpose * 2 * e * np.array(nor) / len(ids)
                gX[ids] += g

    def energy_grad(self, lam, full=False):
        W = self.W
        G = np.zeros_like(W)
        E = {"pen": 0.0, "stick": 0.0, "ref": 0.0, "len": 0.0, "smooth": 0.0, "down": 0.0}
        a, b = self.E[:, 0], self.E[:, 1]
        for p in self.poses:
            X = self.positions(p)
            gX = np.zeros_like(X)
            self._contact(p, X, gX, lam, E, full)
            if len(self.down) and lam.get("down", 0.0):
                u, l = self.down[:, 0], self.down[:, 1]
                r = X[l, 2] - X[u, 2] - self.down_slack
                r = np.maximum(r, 0.0)
                E["down"] += lam["down"] * float((r ** 2).sum())
                g = lam["down"] * 2 * r
                np.add.at(gX[:, 2], l, g)
                np.add.at(gX[:, 2], u, -g)
            if p.get("ref") is not None:
                D = (X - p["ref"])[self.fidx]
                E["ref"] += lam["ref"] * float((D ** 2).sum())
                gX[self.fidx] += lam["ref"] * 2 * D
            elif lam.get("grav", 0.0) and self.grav.any():
                E["grav"] = E.get("grav", 0.0) + lam["grav"] * float((self.grav * X[:, 2]).sum())
                gX[:, 2] += lam["grav"] * self.grav
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

    def symmetrize(self):
        if self.mv is None:
            return
        self.W = 0.5 * (self.W + self.W[self.mv][:, self.mb])

    def run(self, lam, iters=250, max_dw=0.03, decay=0.99, log=None):
        s = max_dw
        E = None
        for it in range(iters):
            E, G = self.energy_grad(lam, full=(it % 10 == 0))
            Gt = np.where(self.allowed, G, 0.0)
            Gt = Gt - (Gt.sum(axis=1, keepdims=True) / np.maximum(self.allowed.sum(axis=1, keepdims=True), 1)) * self.allowed
            m = np.abs(Gt[self.fidx]).max() if len(self.fidx) else 0.0
            if m < 1e-12:
                break
            Wn = self.W - (s / m) * Gt
            Wn[self.fidx] = simplex_proj(Wn[self.fidx], self.allowed[self.fidx])
            self.W[self.fidx] = Wn[self.fidx]
            self.symmetrize()
            s *= decay
            if log and (it % 50 == 0 or it == iters - 1):
                log("    it %3d  %s" % (it, {k: round(v, 1) for k, v in E.items()}))
        return E

    def prune(self, k=4, thr=0.015):
        """At most k bones per vertex (the game's limit), none under thr; then mirror again."""
        for v in self.fidx:
            idx = np.argsort(-self.W[v])
            keep = [i for i in idx[:k] if self.W[v, i] > thr]
            row = np.zeros(self.B)
            row[keep] = self.W[v, keep]
            self.W[v] = row / row.sum()
        self.allowed = self.allowed & (self.W > 0) | ~self.free[:, None]
        self.symmetrize()

    def penetration(self, W=None, tol=0.0):
        """[(worst depth below the margin - tol, count, pose name)] over all poses (full check)."""
        out = []
        for p in self.poses:
            if p["obst"] is None:
                continue
            X = self.positions(p, W)
            worst, n = 0.0, 0
            for v in self.fidx:
                loc, nor, fi, d = p["obst"].find_nearest(Vector(X[v]), 15.0)
                if loc is None:
                    continue
                sd = (Vector(X[v]) - loc).dot(nor)
                if sd < -tol:
                    n += 1
                    worst = max(worst, -sd)
            if n:
                out.append((round(worst, 2), n, p["name"]))
        return sorted(out, reverse=True)

    def stretch(self, W=None):
        """[(largest edge-length change, pose name)] for the poses, worst first."""
        out = []
        a, b = self.E[:, 0], self.E[:, 1]
        for p in self.poses:
            X = self.positions(p, W)
            r = np.abs(np.linalg.norm(X[a] - X[b], axis=1) - self.L)
            out.append((round(float(r.max()), 2), p["name"]))
        return sorted(out, reverse=True)


def mirror_maps(rest, bones, mirror_name):
    """Vertex index of each vertex's mirror (x -> -x) and bone index of each bone's mirror."""
    P = np.asarray(rest, float)
    Q = P * np.array([-1.0, 1.0, 1.0])
    mv = np.zeros(len(P), int)
    for k in range(len(P)):
        mv[k] = int(np.argmin(((P - Q[k]) ** 2).sum(1)))
    bi = {b: k for k, b in enumerate(bones)}
    mb = np.array([bi.get(mirror_name(b), k) for k, b in enumerate(bones)])
    return mv, mb


def default_mirror_name(n):
    for a, b in (("bn_lf_", "bn_rf_"), ("bn_lb_", "bn_rb_"), ("bn_l_", "bn_r_")):
        if n.startswith(a):
            return b + n[len(a):]
        if n.startswith(b):
            return a + n[len(b):]
    return n


def bvh_from(coords, tris):
    return BVHTree.FromPolygons([Vector(c) for c in coords], [list(t) for t in tris])


# ------------------------------------------------------------------ the game's poses, for the build
STANDING_TOL = 3.0  # cm: a pose whose pelvis is this close to the rest height (and not bowing) keeps its look


def anim_bones(path):
    """Bone names an .anim file keys (io_pdx_mesh's reader)."""
    import bl_ext.user_default.io_pdx_mesh.pdx_data as pdx_data
    el = pdx_data.read_meshfile(path)
    return [b.tag.split(":")[-1] for b in el.find("info")]


def _rest_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.location, pb.rotation_quaternion, pb.scale = (0, 0, 0), (1, 0, 0, 0), (1, 1, 1)


ROOT_BONES = ("ground_joint", "body_root")


def game_pose(rig):
    """After a clip is evaluated: every bone but the roots back to its own length (the clip's rotations kept).
    The game does this: children play the adults' clips with shorter bones, and many women's clips (kneels,
    emotions, bows, cheers, conversations) were made on a rig whose skirt bones sit 13-38 cm lower; applied as
    they are, every vanilla dress would drop that much (found 2026-11-07)."""
    import bpy
    for pb in rig.pose.bones:
        if pb.name not in ROOT_BONES:
            pb.location = (0, 0, 0)
    bpy.context.view_layer.update()


def import_anim(rig, path):
    """Import one .anim onto rig as a new action (returned). Women's emotion clips don't key ground_joint, the
    parent of body_root in the female skeleton, which the importer can't handle: body_root is unparented while
    it imports (ground_joint sits at the origin, so nothing moves)."""
    import bpy
    keyed = set(anim_bones(path))
    par = rig.data.bones["body_root"].parent
    unparent = par is not None and par.name not in keyed
    win = bpy.context.window or (bpy.context.window_manager.windows[0] if bpy.context.window_manager and
                                 bpy.context.window_manager.windows else None)  # a timer has no window of its own
    ctx = dict(window=win, scene=bpy.context.scene, view_layer=bpy.context.view_layer,
               active_object=rig, object=rig) if win else dict(active_object=rig, object=rig)
    vl = bpy.context.view_layer
    hv = rig.hide_viewport
    rig.hide_viewport = False
    rig.hide_set(False)

    def set_parent(name):
        with bpy.context.temp_override(**ctx):
            vl.objects.active = rig
            bpy.ops.object.mode_set(mode='EDIT')
            rig.data.edit_bones["body_root"].parent = rig.data.edit_bones[name] if name else None
            bpy.ops.object.mode_set(mode='OBJECT')

    missing = [n for n in keyed if n not in rig.data.bones]
    if missing:  # bones a clip keys that the body's skeleton lacks (the women's sleeves): add them, unweighted
        with bpy.context.temp_override(**ctx):
            vl.objects.active = rig
            bpy.ops.object.mode_set(mode='EDIT')
            eb = rig.data.edit_bones
            for n in missing:
                side = "l" if "_l_" in n else "r"
                p_ = eb.get("bn_%s_elbow" % side) if "sleeve" in n else None
                b = eb.new(n)
                b.head, b.tail = ((p_.head.copy(), p_.tail.copy()) if p_ else ((0, 0, 0), (0, 0, 5)))
                b.parent = p_
            bpy.ops.object.mode_set(mode='OBJECT')
    if unparent:
        set_parent(None)
    try:
        rig.animation_data_create()
        rig.animation_data.action = None
        for o in vl.objects:
            o.select_set(False)
        vl.objects.active = rig
        rig.select_set(True)
        with bpy.context.temp_override(**ctx):
            bpy.ops.io_pdx_mesh.import_anim(filepath=path, int_start=1)
            if bpy.context.object and bpy.context.object.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        act = rig.animation_data.action
    finally:
        if unparent:
            set_parent(par.name)
        rig.select_set(False)
        rig.hide_viewport = hv
    return act, keyed


def sample_poses(rig, scene, game, sex, anims, bones, log=print):
    """[(name, kind, mats)] for the given animations: mats are the deform matrices (len(bones) x 4 x 4) of
    `bones` (identity for a name the rig lacks). kind: "ref" (standing: keeps the look checked in game) or
    "free" (kneeling, sitting, bowing: only clearance, shape and gravity count). Bones a clip doesn't key stay
    at rest, as in the game."""
    import bpy
    M = rig.matrix_world
    Mi = M.inverted()
    rest_root = (M @ rig.data.bones["body_root"].head_local).z
    # the clips go on a throwaway copy of the skeleton (importing edits it: added bones, body_root unparented for a
    # moment), so the build's own rig, which the pieces are exported with, stays untouched; the real rig's
    # bones are hidden meanwhile, or the importer would pick it
    work = rig.copy()
    work.data = rig.data.copy()
    work.animation_data_clear()
    scene.collection.objects.link(work)
    saved = rig.data
    rig.data = bpy.data.armatures.new("EK2LC_HIDDEN")
    out = []
    try:
        for a in anims:
            path = "%s/gfx/models/portraits/%s_body/%s_body_%s.anim" % (game, sex, sex, a)
            try:
                act, keyed = import_anim(work, path)
            except Exception as e:  # noqa: BLE001
                log("  pose %s not imported: %s" % (a, str(e).splitlines()[0][:100]))
                continue
            if act is None:
                log("  pose %s: no action" % a)
                continue
            f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
            bow = "bow" in a
            frames = sorted({f0, (f0 + f1) // 2, f1})
            for f in frames:
                _rest_pose(work)
                work.animation_data.action = act
                scene.frame_set(f)
                game_pose(work)
                root = M @ work.pose.bones["body_root"].head
                standing = abs(root.z - rest_root) < STANDING_TOL and not bow
                mats = []
                for b in bones:
                    pb = work.pose.bones.get(b)
                    mats.append(np.array(M @ pb.matrix @ pb.bone.matrix_local.inverted() @ Mi) if pb else np.eye(4))
                out.append(("%s:%d" % (a, f), "ref" if standing else "free", np.stack(mats)))
            work.animation_data.action = None
            bpy.data.actions.remove(act)
    finally:
        hidden = rig.data
        rig.data = saved
        bpy.data.armatures.remove(hidden)
        wd = work.data
        bpy.data.objects.remove(work, do_unlink=True)
        bpy.data.armatures.remove(wd)
        scene.frame_set(1)
    return out


def skin_matrix(weights, n_bones):
    """Dense V x B matrix from per-vertex lists of (bone index, weight)."""
    W = np.zeros((len(weights), n_bones))
    for v, ws in enumerate(weights):
        for b, w in (ws.items() if isinstance(ws, dict) else ws):
            W[v, b] += w
    return W


def bend_pairs(rest, faces, idx_ok=None, min_angle=150.0):
    """Second-neighbour pairs (a, c) through b where a-b-c is nearly straight at rest: their distance stands for
    bending stiffness (hide doesn't fold up)."""
    nb = {}
    for f in faces:
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            if idx_ok is not None and not (idx_ok[a] and idx_ok[b]):
                continue
            nb.setdefault(a, set()).add(b)
            nb.setdefault(b, set()).add(a)
    cosmax = math.cos(math.radians(min_angle))
    out = set()
    R = np.asarray(rest, float)
    for b, ns in nb.items():
        ns = list(ns)
        for i in range(len(ns)):
            for j in range(i + 1, len(ns)):
                a, c = ns[i], ns[j]
                u, w = R[a] - R[b], R[c] - R[b]
                lu, lw = np.linalg.norm(u), np.linalg.norm(w)
                if lu > 1e-6 and lw > 1e-6 and u.dot(w) / (lu * lw) < cosmax:
                    out.add((min(a, c), max(a, c)))
    return sorted(out)


def mesh_edges(faces):
    out = set()
    for f in faces:
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            out.add((min(a, b), max(a, b)))
    return sorted(out)


def islands(n, edges):
    par = list(range(n))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
    return [find(i) for i in range(n)]


def tie_pairs(rest, comp, maxd):
    """For each vertex, a tie to the nearest vertex of another island within maxd (parts tucked under or tied
    to each other move together)."""
    R = np.asarray(rest, float)
    out = set()
    comp = np.asarray(comp)
    for i in range(len(R)):
        other = comp != comp[i]
        if not other.any():
            continue
        d = ((R - R[i]) ** 2).sum(1)
        d[~other] = 1e18
        k = int(np.argmin(d))
        if d[k] <= maxd * maxd:
            out.add((min(i, k), max(i, k)))
    return sorted(out)

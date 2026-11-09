"""Build the commissioned regalia (wearable artifacts) for EK2 Loincloths, one body at a time.

Every piece here is its own mesh with its own texture set (the user, 2026-11-09: "Absolute no asset
reuse!!"). They are worn over our loincloth and replace the war/royal girdle while the artifact is
equipped (gen_script_files.py). Pieces:
  art_champion  Champion's Apron: tall silk belt and an embroidered ankle-long apron with gold fringe
                (a Tamrielic kesho-mawashi, gifted by patrons)
  art_fauld     Malacath's Iron Fauld: riveted iron belt, three iron lames in front, a boss
  art_feather   Feather Girdle of the Ancestors: feather sash, feather fringe, a tail with teeth
                (after the kaei of Liloa)
  art_briar     Briarheart Girdle: tooled belt, two briar vines with thorns, bear plaque, hagraven feathers
  art_amber     Hist-Amber Wrap: woven grass hip wrap, amber bead swags, tortoise-shell plaques
  art_bone      Green Pact Bone Apron: rawhide belt, front and back aprons of bone hairpipes and beetle beads
  art_ash       Ancestor-Ash Tassets: two crossing guar belts, chitin buckle, enamelled chitin tassets
  art_moon      Mane's Moon Silk: silk sash with a knot, two tails, Masser and Secunda discs

Reuses the code (not the meshes) of build_reach_hide.py: its body and body-shape setup, skin-weight
helpers and exporter are executed from that file. Our shipped loincloth and leggings are imported as
obstacles, so every piece sits outside them on every body shape.

Run in the Blender app through MCP for Blender:
    exec(open("<mod>/source/tools/build_in_app.py").read()); start("male", "female", script="build_regalia.py")
"""
import os, sys, math
import numpy as np

_BR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_reach_hide.py")
_T = open(_BR).read()
_M = "# ------------------------------------------------------------------ "


def _cut(a, b):
    i = _T.index(a)
    return _T[i:_T.index(b, i)]


exec(compile(_T[:_T.index(_M + "hide leggings")] + "\n" + _cut(_M + "skin weights", "# Flap weights.") + "\n"
             + _cut(_M + "make, export and check every piece", _M + "trophy belt"), _BR, "exec"), globals())

STRICT, MATS = set(), {}
KNEE_Z = (rig.matrix_world @ rig.data.bones["bn_l_knee"].head_local).z
ANKLE_Z = (rig.matrix_world @ rig.data.bones["bn_l_ankle"].head_local).z
LSIDE = 1 if (rig.matrix_world @ rig.data.bones["bn_l_hip"].head_local).x > 0 else -1
ONLY = [a for a in argv[3:]]  # optional: build only these pieces


# ------------------------------------------------------------------ obstacles: the body without its arms, our worn pieces
_ARMK = ("shoulder", "arm", "elbow", "wrist", "hand", "finger", "thumb", "_fi_")
_ARMG = {gi for gi, n in enumerate(VG) if any(k in n for k in _ARMK)}
ARMV = {i for i, ws in enumerate(BW) if sum(w for g, w in ws.items() if g in _ARMG) > 0.5}
TORSO_T = {s: [t for t in TRIS[s] if not ARMV.intersection(t)] for s in ALL}
TB = {s: BVHTree.FromPolygons(COORDS[s], TORSO_T[s]) for s in ALL}


def _mesh_world(objs):
    vs, fs = [], []
    for o in objs:
        if o.type != "MESH":
            continue
        b = len(vs)
        vs += [o.matrix_world @ v.co for v in o.data.vertices]
        fs += [[b + i for i in p.vertices] for p in o.data.polygons]
    return vs, fs


def obstacle(mesh):
    out = {}
    for s in ALL:
        path = os.path.join(OUT, mesh + (".mesh" if s == "basis" else "_bs_%s.mesh" % s))
        if not os.path.exists(path):
            continue
        objs = pdx_import(path, False)
        vs, fs = _mesh_world(objs)
        drop(objs)
        out[s] = BVHTree.FromPolygons(vs, fs)
    return out


OBST = [obstacle("ek2lc_%s_reach_hide_01" % S1), obstacle("ek2lc_%s_leggings_01" % S1)]
if SEX == "female":
    OBST.append(obstacle("ek2lc_f_reach_band_01"))  # the sash crosses the chest band
ALLB = {s: [TB[s]] + [o[s] for o in OBST if s in o] for s in ALL}
print("REGALIA obstacles", [len(o) for o in OBST])


def first_hit(s, start, d, maxd, bvhs=None):
    best = None
    for b in (bvhs or ALLB[s]):
        h = b.ray_cast(start, d, maxd)
        if h[0] is not None and (best is None or h[3] < best[3]):
            best = h
    return best


def cy(z, s):
    """Body centre (y) at height z; between the legs, the crotch's."""
    key = (round(z, 3), s)
    if key in _CY:
        return _CY[key]
    zz = max(z, CROTCH_Z + 2.0)
    for _ in range(40):  # a smaller body shape (a child's) may have its crotch higher: go up until both rays hit
        o = Vector((0, 0, zz))
        f = TB[s].ray_cast(o + FRONT * 200, -FRONT, 400)[0]
        b = TB[s].ray_cast(o - FRONT * 200, FRONT, 400)[0]
        if f is not None and b is not None:
            _CY[key] = (f.y + b.y) / 2
            return _CY[key]
        zz += 1.0
    raise RuntimeError("no body centre at z=%.1f on %s" % (z, s))


_CY = {}


def clear_pt(s, p, gap, iters=6):
    """p pushed out along the body's surface normal until it is gap clear of the skin (arms left out)."""
    for _ in range(iters):
        loc, nor, fi, d = TB[s].find_nearest(p)
        if loc is None or (p - loc).dot(nor) >= gap:
            break
        p = loc + nor * gap
    return p


def dirv(a):
    return FRONT * math.cos(a) + RIGHT * math.sin(a)


def smooth_max(vals, iters=3, closed=True):
    need, cur = list(vals), list(vals)
    n = len(vals)
    for _ in range(iters):
        b = []
        for i in range(n):
            nb = [cur[(i + k) % n] if closed else cur[min(max(i + k, 0), n - 1)] for k in (-1, 0, 1)]
            b.append(sum(nb) / 3)
        cur = [max(x, y) for x, y in zip(need, b)]
    return cur


def radial(s, z, angs, gap, closed=True, floor=None, over=None):
    """Points at height z, angles angs (radians from the front towards +x): gap outside the outermost of
    the body and our worn pieces, smoothed round the ring; floor: per-angle minimum radius."""
    c = Vector((0, cy(z, s), z))
    rs = []
    for k, a in enumerate(angs):
        d = dirv(a)
        h = first_hit(s, c + d * 80, -d, 80, ALLB[s] + (over[s] if over else []))
        r = (h[0] - c).dot(d) if h else (rs[-1] if rs else 10.0)
        if floor:
            r = max(r, floor[k])
        rs.append(r)
    rs = smooth_max(rs, 3, closed)
    return [c + dirv(a) * (r + gap) for a, r in zip(angs, rs)], rs


# ------------------------------------------------------------------ weights
def norm_w(d):
    row = [(g, w) for g, w in sorted(d.items(), key=lambda kv: -kv[1])[:4] if w > 0.01]
    tot = sum(w for _, w in row)
    return [(g, w / tot) for g, w in row]


def torso_w(p):
    loc, nor, fi, dist = TB["basis"].find_nearest(p)
    tri = TORSO_T["basis"][fi]
    return dict(weights_at(tri, poly_3d_calc([C0[k] for k in tri], loc)))


def hang_w(p, t, top=None):
    """Weights of a point hanging t (0 at its tie, 1 at its tip) below where it is tied: the skin there,
    blending into the skirt chains (as the loincloth's flaps)."""
    u = min(1.0, max(0.0, (t - 0.12) / 0.3))
    u = u * u * (3 - 2 * u)
    d = {}
    for g, w in (top if top is not None else torso_w(p)).items():
        d[g] = d.get(g, 0.0) + w * (1 - u)
    if u > 0:
        for g, w in skirt_weights(ang_of(p), p.z).items():
            d[g] = d.get(g, 0.0) + w * u
    return norm_w(d)


# ------------------------------------------------------------------ texture atlas
class Atlas:
    """A texture set split into cells (CELLS x CELLS); each material paints its own cells."""

    def __init__(self, tset, size=1024, cells=4):
        self.tset, self.size, self.cells, self.used, self.mats = tset, size, cells, set(), []

    def cell(self, painter, w=1, h=1):
        for j in range(self.cells - h + 1):
            for i in range(self.cells - w + 1):
                spots = {(i + a, j + b) for a in range(w) for b in range(h)}
                if not spots & self.used:
                    self.used |= spots
                    self.mats.append((i, j, w, h, painter))
                    c, S, px = self.cells, self.size, 3.0 / self.size
                    return (i / c + px, 1 - (j + h) / c + px, (i + w) / c - px, 1 - j / c - px)
        raise RuntimeError("atlas full: " + self.tset)

    def paint(self):
        S, c = self.size, self.cells
        cs = S // c
        img = np.zeros((S, S, 4), np.float32)
        img[..., :3] = 0.5
        nrm = np.zeros((S, S, 4), np.float32)
        nrm[..., 0] = nrm[..., 1] = nrm[..., 3] = 0.5
        props = np.zeros((S, S, 4), np.float32)
        props[..., 1], props[..., 3] = 0.22, 0.6
        for k, (i, j, w, h, painter) in enumerate(self.mats):
            H, WD = h * cs, w * cs
            yy, xx = np.mgrid[0:H, 0:WD].astype(np.float32)
            U, V = xx / (WD - 1), 1 - yy / (H - 1)
            r = painter(U, V, np.random.default_rng(1000 + k), (H, WD))
            sl = (slice(j * cs, j * cs + H), slice(i * cs, i * cs + WD))
            img[sl + (slice(0, 3),)] = np.clip(r["rgb"], 0, 1)
            img[sl + (3,)] = r.get("a", 1.0)
            props[sl + (1,)] = r.get("spec", 0.22)
            props[sl + (3,)] = r.get("rough", 0.6)
        return {"diffuse": img, "normal": nrm, "properties": props}


def lerp_uv(rect, lu, lv):
    u0, v0, u1, v1 = rect
    return (u0 + (u1 - u0) * lu, v0 + (v1 - v0) * lv)


# ------------------------------------------------------------------ piece builder
class Piece:
    def __init__(self, name, tset):
        self.name, self.set = name, tset
        self.pos = {s: [] for s in ALL}
        self.faces, self.part, self.uvs, self.vw = [], [], [], []
        self.orient, self.wrap, self.wrap_u, self.np = [], set(), {}, 0

    def verts(self, P, uvs, ws):
        b = len(self.uvs)
        for s in ALL:
            self.pos[s].extend(P[s])
        self.uvs.extend(uvs)
        self.vw.extend(ws)
        return b

    def new_part(self, out_fn):
        p = "p%03d" % self.np
        self.np += 1
        self.orient.append((p, out_fn, p + "o"))
        return p

    def face(self, f, part, wrap=False):
        if wrap:
            self.wrap.add(len(self.faces))
        self.faces.append(f)
        self.part.append(part)

    def as_dict(self):
        return dict(name=self.name, set=self.set, pos=self.pos, faces=self.faces, part=self.part, wrap=self.wrap,
                    wrap_u=self.wrap_u, uvs=self.uvs, vw=self.vw, orient=self.orient)


def _grid_n(P, R, C):
    N = []
    for j in range(R):
        for i in range(C):
            du = P[j * C + min(i + 1, C - 1)] - P[j * C + max(i - 1, 0)]
            dv = P[min(j + 1, R - 1) * C + i] - P[max(j - 1, 0) * C + i]
            n = du.cross(dv)
            N.append(n.normalized() if n.length > 1e-9 else Vector((0, 0, 1)))
    return N


def slab(pc, P, R, C, rect, ws, thick, out_fn, closed=False):
    """A sheet R rows x C columns (P[s]: row-major outer points, row 0 at the top), thickened inwards by
    thick. closed: the columns wrap round (a ring band; column C-1 joins column 0)."""
    sign = 1.0
    nb = _grid_n(P["basis"], R, C)
    if sum(n.dot(out_fn(p)) for n, p in zip(nb, P["basis"])) < 0:
        sign = -1.0
    Q = {}
    for s in ALL:
        N = _grid_n(P[s], R, C)
        Q[s] = list(P[s]) + [p - n * (sign * thick) for p, n in zip(P[s], N)]
    uvs = []
    for layer in range(2):
        for j in range(R):
            for i in range(C):
                uvs.append(lerp_uv(rect, i / (C - (0 if closed else 1)), 1 - j / (R - 1)))
    b = pc.verts(Q, uvs, list(ws) + list(ws))
    part = pc.new_part(out_fn)
    o = lambda j, i: b + j * C + (i % C)
    n = lambda j, i: b + R * C + j * C + (i % C)
    cols = C if closed else C - 1
    for j in range(R - 1):
        for i in range(cols):
            w = closed and i == C - 1
            pc.face([o(j, i), o(j, i + 1), o(j + 1, i + 1), o(j + 1, i)], part + "o", w)
            pc.face([n(j, i), n(j + 1, i), n(j + 1, i + 1), n(j, i + 1)], part + "i", w)
    if closed:
        pc.wrap_u.update({o(j, 0): rect[2] for j in range(R)})
        pc.wrap_u.update({n(j, 0): rect[2] for j in range(R)})
    else:
        for j in range(R - 1):
            pc.face([o(j, 0), o(j + 1, 0), n(j + 1, 0), n(j, 0)], part + "r")
            pc.face([o(j, C - 1), n(j, C - 1), n(j + 1, C - 1), o(j + 1, C - 1)], part + "r")
    for i in range(cols):
        w = closed and i == C - 1
        pc.face([o(0, i), n(0, i), n(0, i + 1), o(0, i + 1)], part + "r", w)
        pc.face([o(R - 1, i), o(R - 1, i + 1), n(R - 1, i + 1), n(R - 1, i)], part + "r", w)


def _frames(path):
    T = [(path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)]).normalized() for k in range(len(path))]
    ref = UP if abs(T[0].dot(UP)) < 0.9 else FRONT
    Nn = [T[0].cross(ref).normalized()]
    for k in range(1, len(path)):
        n = Nn[-1] - T[k] * Nn[-1].dot(T[k])
        Nn.append(n.normalized() if n.length > 1e-9 else Nn[-1])
    return T, Nn


def tube(pc, paths, radius, rect, ws, sides=6, caps=True, rad_fn=None):
    """A tube along paths[s] (points per body shape); ws: weights per path point; rad_fn(t) scales radius."""
    L = len(paths["basis"])
    Q = {s: [] for s in ALL}
    for s in ALL:
        T, Nn = _frames(paths[s])
        for k, p in enumerate(paths[s]):
            B = T[k].cross(Nn[k])
            r = radius * (rad_fn(k / (L - 1)) if rad_fn else 1.0)
            for q in range(sides):
                th = 2 * math.pi * q / sides
                Q[s].append(p + (Nn[k] * math.cos(th) + B * math.sin(th)) * r)
        if caps:
            Q[s] += [paths[s][0], paths[s][-1]]
    uvs = [lerp_uv(rect, q / sides, 1 - k / (L - 1)) for k in range(L) for q in range(sides)]
    W = [ws[k] for k in range(L) for q in range(sides)]
    if caps:
        uvs += [lerp_uv(rect, 0.5, 1.0), lerp_uv(rect, 0.5, 0.0)]
        W += [ws[0], ws[-1]]
    b = pc.verts(Q, uvs, W)
    pb = paths["basis"]

    def out(c):
        k = min(range(L), key=lambda i: (pb[i] - c).length)
        return c - pb[k]

    part = pc.new_part(out)
    for k in range(L - 1):
        for q in range(sides):
            q2 = (q + 1) % sides
            pc.face([b + k * sides + q, b + k * sides + q2, b + (k + 1) * sides + q2, b + (k + 1) * sides + q], part + "o")
    if caps:
        c0, c1 = b + L * sides, b + L * sides + 1
        for q in range(sides):
            q2 = (q + 1) % sides
            pc.face([c0, b + q2, b + q], part + "o")
            pc.face([c1, b + (L - 1) * sides + q, b + (L - 1) * sides + q2], part + "o")


def blob(pc, centers, radii, rect, w, seg=8, rings=5, axes=None):
    """A sphere (or ellipsoid: axes[s] = (X, Y, Z) scaled vectors) at centers[s]."""
    Q = {s: [] for s in ALL}
    for s in ALL:
        c = centers[s]
        X, Y, Z = axes[s] if axes else (RIGHT * radii, FRONT * radii, UP * radii)
        Q[s].append(c + Z)
        for r in range(1, rings):
            ph = math.pi * r / rings
            for q in range(seg):
                th = 2 * math.pi * q / seg
                Q[s].append(c + (X * math.cos(th) + Y * math.sin(th)) * math.sin(ph) + Z * math.cos(ph))
        Q[s].append(c - Z)
    n = 2 + (rings - 1) * seg
    uvs = [lerp_uv(rect, 0.5, 1.0)] + [lerp_uv(rect, q / seg, 1 - r / rings) for r in range(1, rings) for q in range(seg)] \
        + [lerp_uv(rect, 0.5, 0.0)]
    b = pc.verts(Q, uvs, [w] * n)
    cb = centers["basis"]
    part = pc.new_part(lambda c: c - cb)
    top, bot = b, b + n - 1
    ring = lambda r, q: b + 1 + (r - 1) * seg + (q % seg)
    for q in range(seg):
        pc.face([top, ring(1, q + 1), ring(1, q)], part + "o")
        pc.face([bot, ring(rings - 1, q), ring(rings - 1, q + 1)], part + "o")
        for r in range(1, rings - 1):
            pc.face([ring(r, q), ring(r, q + 1), ring(r + 1, q + 1), ring(r + 1, q)], part + "o")


def disc(pc, centers, normals, ups, radius, thick, rect, w, seg=12):
    """A coin: centre, facing normals[s], 'up' in its plane ups[s]."""
    Q = {s: [] for s in ALL}
    for s in ALL:
        n, u = normals[s].normalized(), ups[s].normalized()
        r_ = n.cross(u).normalized()
        u = r_.cross(n).normalized()
        for side in (0.5, -0.5):
            c = centers[s] + n * thick * side
            Q[s].append(c)
            for q in range(seg):
                th = 2 * math.pi * q / seg
                Q[s].append(c + (r_ * math.cos(th) + u * math.sin(th)) * radius)
    uv1 = [lerp_uv(rect, 0.5, 0.5)] + [lerp_uv(rect, 0.5 + 0.5 * math.cos(2 * math.pi * q / seg),
                                                0.5 + 0.5 * math.sin(2 * math.pi * q / seg)) for q in range(seg)]
    b = pc.verts(Q, uv1 + uv1, [w] * (2 * seg + 2))
    cb = centers["basis"]
    part = pc.new_part(lambda c: c - cb)
    f0, f1 = b, b + seg + 1
    for q in range(seg):
        q2 = (q + 1) % seg
        pc.face([f0, f0 + 1 + q, f0 + 1 + q2], part + "o")
        pc.face([f1, f1 + 1 + q2, f1 + 1 + q], part + "o")
        pc.face([f0 + 1 + q, f1 + 1 + q, f1 + 1 + q2, f0 + 1 + q2], part + "o")


def cone(pc, bases, tips, radius, rect, w, sides=4):
    Q = {s: [] for s in ALL}
    for s in ALL:
        d = (tips[s] - bases[s]).normalized()
        a = d.cross(UP if abs(d.dot(UP)) < 0.9 else FRONT).normalized()
        bb = d.cross(a)
        Q[s] = [bases[s] + (a * math.cos(2 * math.pi * q / sides) + bb * math.sin(2 * math.pi * q / sides)) * radius
                for q in range(sides)] + [tips[s], bases[s]]
    uvs = [lerp_uv(rect, q / sides, 0.0) for q in range(sides)] + [lerp_uv(rect, 0.5, 1.0), lerp_uv(rect, 0.5, 0.0)]
    b = pc.verts(Q, uvs, [w] * (sides + 2))
    cb = bases["basis"]
    part = pc.new_part(lambda c: c - cb)
    for q in range(sides):
        q2 = (q + 1) % sides
        pc.face([b + q, b + q2, b + sides], part + "o")
        pc.face([b + q2, b + q, b + sides + 1], part + "o")


# ------------------------------------------------------------------ shapes worn at the hips
def band(pc, z_top, z_bot, rows, nb, gap, thick, rect, extra_fn=None, tilt_fn=None, over=None, bvhs=None, clamp=False):
    """A belt or sash round the hips from z_top to z_bot: each ring gap outside everything worn under it.
    extra_fn(a): extra offset by angle; tilt_fn(a): height shift by angle; over: more obstacles (per shape)."""
    angs = [2 * math.pi * k / nb for k in range(nb)]
    gap = gap if clamp else max(gap, thick + 0.1)  # its inner face stays outside the skin
    P = {}
    for s in ALL:
        P[s] = []
        for j in range(rows):
            z = z_top + (z_bot - z_top) * j / (rows - 1)
            pts = []
            for a in angs:
                zz = z + (tilt_fn(a) if tilt_fn else 0.0)
                c = Vector((0, cy(zz, s), zz))
                d = dirv(a)
                h = first_hit(s, c + d * 80, -d, 80, (bvhs[s] if bvhs else ALLB[s]) + (over[s] if over else []))
                pts.append((c, d, (h[0] - c).dot(d) if h else 12.0))
            rs = smooth_max([r for _, _, r in pts], 4)
            ro = [r + gap + (extra_fn(a) if extra_fn else 0.0) for r, a in zip(rs, angs)]
            if clamp:  # a wrap that replaces the loincloth: inside the loincloth's room, so what goes over it still fits
                ro = [under_base(s, c, d, r_, r) for (c, d, _), r_, r in zip(pts, ro, rs)]
            P[s] += [c + d * r_ for (c, d, _), r_ in zip(pts, ro)]
    ws = [norm_w(torso_w(p)) for p in P["basis"]]
    slab(pc, P, rows, nb, rect, ws, thick, lambda c: Vector((c.x, c.y - cy(BELT_Z, "basis"), 0)), closed=True)
    return P


def ring_pts(P, rows, nb, row, s):
    return P[s][row * nb:(row + 1) * nb]


def bvh_of(P, R, C, closed=False):
    """Per-shape BVH of a grid (to keep later parts outside it)."""
    out = {}
    cols = C if closed else C - 1
    fs = [[j * C + i, j * C + (i + 1) % C, (j + 1) * C + (i + 1) % C, (j + 1) * C + i] for j in range(R - 1) for i in range(cols)]
    for s in ALL:
        out[s] = [BVHTree.FromPolygons(P[s], fs)]
    return out


def drape(pc, side, xs, z_top, z_bot, rows, gap, thick, rect, widen=0.0, over=None, tie_t=0.0, bvhs=None, clamp=False):
    """A flat apron hanging in front (side +1) or behind (-1): each column falls straight from the most
    prominent point above it, gap clear of everything under it. xs: column x positions at the top
    (widen: extra half-width at the bottom). Returns its points."""
    D = FRONT * side
    P = {}
    for s in ALL:
        E, HERE = [], {}
        for j in range(rows):
            t = j / (rows - 1)
            z = z_top + (z_bot - z_top) * t
            row = []
            for x in xs:
                xx = x * (1 + widen * t)
                h = first_hit(s, Vector((xx, 0, z)) + D * 80, -D, 160, (bvhs[s] if bvhs else ALLB[s]) + (over[s] if over else []))
                e = h[0].dot(D) if h else (-1e9 if j else 0.0)
                HERE[(j, len(row))] = e
                if j:
                    e = max(e, E[-1][len(row)])
                row.append(e)
            row = smooth_max(row, 2, closed=False)
            E.append(row)
        P[s] = []
        for j in range(rows):
            t = j / (rows - 1)
            z = z_top + (z_bot - z_top) * t
            for i, x in enumerate(xs):
                e_ = E[j][i] + gap
                if clamp and s in BASEB:
                    q = Vector((x * (1 + widen * t), 0, z))
                    hb = BASEB[s].ray_cast(q + D * 80, -D, 160)[0]
                    if hb is not None and e_ > hb.dot(D) - 0.12:
                        e_ = max(hb.dot(D) - 0.12, HERE[(j, i)] + 0.15)
                P[s].append(Vector((x * (1 + widen * t), 0, z)) + D * e_)
    ws = []
    top = {i: torso_w(P["basis"][i]) for i in range(len(xs))}
    for j in range(rows):
        t = tie_t + (1 - tie_t) * j / (rows - 1)
        for i in range(len(xs)):
            ws.append(hang_w(P["basis"][j * len(xs) + i], t, top[i]))
    slab(pc, P, rows, len(xs), rect, ws, thick, lambda c: D)
    return P


def radial_drape(pc, a0, a1, cols, z_top, z_bot, rows, gap, thick, rect, extra=0.0, over=None, tie_t=0.0):
    """A plate or strip hanging at the side between angles a0 and a1: rows fall straight from above,
    gap clear of everything under it (extra: added offset, for overlapping lames)."""
    angs = [a0 + (a1 - a0) * i / (cols - 1) for i in range(cols)]
    P = {}
    for s in ALL:
        R_ = []
        cs = []
        for j in range(rows):
            z = z_top + (z_bot - z_top) * j / (rows - 1)
            c = Vector((0, cy(z, s), z))
            cs.append(c)
            row = []
            for i, a in enumerate(angs):
                d = dirv(a)
                h = first_hit(s, c + d * 80, -d, 80, ALLB[s] + (over[s] if over else []))
                r = (h[0] - c).dot(d) if h else (-1e9 if j else 10.0)
                if j:
                    # straight down from the row above: the radius that keeps the same point in plan
                    r = max(r, (cs[-2] + dirv(a) * R_[-1][i] - c).dot(d))
                row.append(r)
            R_.append(smooth_max(row, 2, closed=False))
        P[s] = [cs[j] + dirv(a) * (R_[j][i] + gap + extra) for j in range(rows) for i, a in enumerate(angs)]
    top = {i: torso_w(P["basis"][i]) for i in range(cols)}
    ws = [hang_w(P["basis"][j * cols + i], tie_t + (1 - tie_t) * j / (rows - 1), top[i]) for j in range(rows) for i in range(cols)]
    am = (a0 + a1) / 2
    slab(pc, P, rows, cols, rect, ws, thick, lambda c: dirv(am))
    return P


def band_pt(P, rows, nb, row, a, s, out=0.0, dz=0.0):
    """Point on a band at fractional ring `row` (0 = top) and angle a, pushed out by `out`, raised dz."""
    k = (a % (2 * math.pi)) / (2 * math.pi) * nb
    k0, f = int(k) % nb, k - int(k)
    r0 = min(max(int(row), 0), rows - 2)
    g = min(max(row - r0, 0.0), 1.0)
    pts = []
    for rr in (r0, r0 + 1):
        r = ring_pts(P, rows, nb, rr, s)
        pts.append(r[k0].lerp(r[(k0 + 1) % nb], f))
    p = pts[0].lerp(pts[1], g)
    return p + outward(p, s) * out + UP * dz


def on_band(P, rows, nb, row, a, out=0.0, dz=0.0):
    """{s: point} on a band (band_pt) for every body shape."""
    return {s: band_pt(P, rows, nb, row, a, s, out, dz) for s in ALL}


def outward(p, s):
    c = Vector((0, cy(p.z, s), p.z))
    return Vector((p.x - c.x, p.y - c.y, 0)).normalized()


def card(pc, tops, length, width, rect, rows=3, tilt=0.25, thick=0.06, twist=0.0):
    """A feather or tassel card hanging from tops[s] (outward-facing), length cm, tilted out by `tilt`."""
    P = {}
    for s in ALL:
        o = outward(tops[s], s)
        tg = UP.cross(o).normalized()
        tg = (tg * math.cos(twist) + o * math.sin(twist)).normalized()
        down = (-UP + o * tilt).normalized()
        P[s] = [tops[s] + down * (length * j / (rows - 1)) + tg * (width * (i - 0.5)) + o * (0.15 * (j / (rows - 1)) ** 2)
                for j in range(rows) for i in range(2)]
    top = torso_w(tops["basis"])
    ws = [hang_w(P["basis"][j * 2 + i], 0.3 + 0.7 * j / (rows - 1), top) for j in range(rows) for i in range(2)]
    ob = tops["basis"]
    slab(pc, P, rows, 2, rect, ws, thick, lambda c: outward(ob, "basis"))


def path_on(fn, n):
    """{s: [points]} from fn(s, t) for t in 0..1."""
    return {s: [fn(s, k / (n - 1)) for k in range(n)] for s in ALL}


# ------------------------------------------------------------------ painters (numpy, per atlas cell)
def C(r, g, b):
    return np.array((r, g, b), np.float32)


def noise(shape, k, seed, oct_=3):
    return undead.fbm(shape[0], shape[1], k, seed, oct_)


def mix(a, b, t):
    t = np.asarray(t, np.float32)[..., None] if np.ndim(t) else t
    return a * (1 - t) + b * t


def P_silk(base, thread, motif=None, emb=None, fringe=0.0, fringe_col=None, stripes=None):
    def f(U, V, rng, sh):
        n = noise(sh, 16, int(rng.integers(1000000)))
        weave = 0.5 + 0.5 * np.sin(U * sh[1] * 1.6) * np.sin(V * sh[0] * 1.6)
        rgb = base[None, None, :] * (0.82 + 0.12 * weave + 0.12 * n)[..., None]
        if stripes:
            for v0, v1, col in stripes:
                m = (V >= v0) & (V <= v1)
                rgb[m] = col * (0.85 + 0.2 * n[m])[:, None]
        if emb is not None:
            m, col = emb(U, V)
            rgb = np.where(m[..., None], col * (0.85 + 0.25 * weave)[..., None], rgb)
        a = np.ones(sh, np.float32)
        spec = np.full(sh, 0.3, np.float32)
        rough = np.full(sh, 0.45, np.float32)
        if fringe > 0:
            fz = V < fringe
            rgb[fz] = (fringe_col if fringe_col is not None else thread) * (0.8 + 0.3 * n[fz])[:, None]
            strands = (np.sin(U * sh[1] * 0.9) > -0.2)
            a = np.where(fz & ~strands, 0.0, a)
            a = np.where(fz & (V < fringe * (0.2 + 0.6 * np.abs(np.sin(U * 37.0)))), 0.0, a)
            spec = np.where(fz, 0.55, spec)
        return {"rgb": rgb, "a": a, "spec": spec, "rough": rough}
    return f


def P_metal(base, rivets=0, edge=0.08, rust=0.0, boss=False):
    def f(U, V, rng, sh):
        n = noise(sh, 10, int(rng.integers(1000000)))
        n2 = noise(sh, 40, int(rng.integers(1000000)))
        rgb = base[None, None, :] * (0.75 + 0.25 * n + 0.1 * n2)[..., None]
        e = (U < edge) | (U > 1 - edge) | (V < edge) | (V > 1 - edge)
        rgb[e] *= 1.35
        if rust:
            r = n2 > 1 - rust
            rgb[r] = C(0.28, 0.12, 0.05) * (0.8 + 0.4 * n[r])[:, None]
        if rivets:
            for k in range(rivets):
                for vv in (0.25, 0.75):
                    d = np.hypot((U - (k + 0.5) / rivets) * sh[1], (V - vv) * sh[0])
                    rgb[d < 6] = base * 1.7
                    rgb[(d >= 6) & (d < 8)] = base * 0.5
        if boss:
            d = np.hypot(U - 0.5, V - 0.5)
            rgb[(d > 0.3) & (d < 0.36)] *= 0.5
            rgb[d < 0.12] *= 1.6
            ang = np.arctan2(V - 0.5, U - 0.5)
            spokes = (np.abs(np.sin(ang * 4)) < 0.15) & (d > 0.12) & (d < 0.3)
            rgb[spokes] *= 0.55
        return {"rgb": rgb, "spec": np.full(sh, 0.75, np.float32), "rough": 0.3 + 0.3 * n}
    return f


def P_leather(base, tool=None, border=True):
    def f(U, V, rng, sh):
        n = noise(sh, 14, int(rng.integers(1000000)))
        g = noise(sh, 60, int(rng.integers(1000000)), 2)
        rgb = base[None, None, :] * (0.7 + 0.35 * n + 0.1 * g)[..., None]
        if border:
            b = ((np.abs(V - 0.12) < 0.025) | (np.abs(V - 0.88) < 0.025))
            rgb[b] *= 0.55
        if tool is not None:
            m = tool(U, V)
            rgb[m] *= 0.6
        return {"rgb": rgb, "spec": np.full(sh, 0.2, np.float32), "rough": np.full(sh, 0.65, np.float32)}
    return f


def P_feather(col_a, col_b, tip=None, alpha=True):
    def f(U, V, rng, sh):
        n = noise(sh, 20, int(rng.integers(1000000)))
        x = (U - 0.5) * 2
        prof = 0.15 + 0.85 * np.sin(np.clip(V, 0, 1) * np.pi) ** 0.6  # widest in the middle
        inside = np.abs(x) < prof * (0.9 + 0.1 * np.sin(V * 60 + np.sign(x) * 3))
        barbs = 0.6 + 0.4 * np.sin((V * 40 - np.abs(x) * 12) * np.pi)
        rgb = mix(col_b, col_a, np.clip(V * 1.4 - 0.2, 0, 1)) * (0.75 + 0.25 * barbs + 0.1 * n)[..., None]
        if tip is not None:
            rgb[V < 0.15] = tip * (0.8 + 0.3 * n[V < 0.15])[:, None]
        rgb[np.abs(x) < 0.04] = C(0.85, 0.82, 0.7)  # the quill
        a = inside.astype(np.float32) if alpha else np.ones(sh, np.float32)
        return {"rgb": rgb, "a": a, "spec": np.full(sh, 0.35, np.float32), "rough": np.full(sh, 0.5, np.float32)}
    return f


def P_scales(col_a, col_b, every=3):
    """Overlapping feathers in rows (a feather sash seen from outside); every `every`-th row in col_b."""
    def f(U, V, rng, sh):
        n = noise(sh, 20, int(rng.integers(1000000)))
        kv = V * 7
        row = np.floor(kv).astype(int)
        fv = kv % 1
        ku = U * 18 + 0.5 * (row % 2)
        fu = ku % 1
        d = np.hypot((fu - 0.5) * 1.4, fv * 1.1)
        shade = np.clip(1.1 - d, 0.3, 1.0) * (0.8 + 0.25 * np.sin(fu * 30))
        col = np.where((row % every == 0)[..., None], col_b, col_a)
        rgb = col * (shade * (0.85 + 0.25 * n))[..., None]
        return {"rgb": rgb, "spec": np.full(sh, 0.35, np.float32), "rough": np.full(sh, 0.5, np.float32)}
    return f


def P_solid(col, spec=0.4, rough=0.4, var=0.2, rings=0, mottled=None):
    def f(U, V, rng, sh):
        n = noise(sh, 8, int(rng.integers(1000000)))
        rgb = col[None, None, :] * (1 - var + 2 * var * n)[..., None]
        if rings:
            rgb *= (0.85 + 0.15 * np.sin(V * rings * 2 * np.pi))[..., None]
        if mottled is not None:
            m = noise(sh, 6, int(rng.integers(1000000))) > 0.55
            rgb[m] = mottled * (0.8 + 0.4 * n[m])[:, None]
        return {"rgb": rgb, "spec": np.full(sh, spec, np.float32), "rough": np.full(sh, rough, np.float32)}
    return f


def P_weave(a_col, b_col, k=24):
    def f(U, V, rng, sh):
        n = noise(sh, 12, int(rng.integers(1000000)))
        cu, cv = (U * k).astype(int), (V * k).astype(int)
        over = ((cu + cv) % 2 == 0)
        fu, fv = U * k % 1, V * k % 1
        shade = np.where(over, 0.75 + 0.35 * np.sin(fu * np.pi), 0.75 + 0.35 * np.sin(fv * np.pi))
        rgb = np.where(over[..., None], a_col, b_col) * (shade * (0.85 + 0.25 * n))[..., None]
        return {"rgb": rgb, "spec": np.full(sh, 0.18, np.float32), "rough": np.full(sh, 0.7, np.float32)}
    return f


def P_bark(col, thorn_col=None):
    def f(U, V, rng, sh):
        n = noise(sh, 18, int(rng.integers(1000000)))
        streak = 0.7 + 0.3 * np.sin(U * 50 + n * 6)
        rgb = col[None, None, :] * (streak * (0.8 + 0.3 * n))[..., None]
        if thorn_col is not None:
            rgb = mix(rgb, thorn_col, np.clip((V - 0.55) * 2.2, 0, 1))
        return {"rgb": rgb, "spec": np.full(sh, 0.25, np.float32), "rough": np.full(sh, 0.6, np.float32)}
    return f


# emblem helpers (masks in a cell's U, V)
def emb_kesho(col_main, col_gold):
    def e(U, V):
        x, y = (U - 0.5) * 2, (V - 0.55) * 2.2
        r = np.hypot(x, y)
        sun = r < 0.32
        rays = (np.abs(np.sin(np.arctan2(y, x) * 8)) > 0.75) & (r > 0.38) & (r < 0.55)
        mtn = (V < 0.42) & (V > 0.18) & (np.abs(U - 0.5) < (0.42 - V) * 1.6)
        border = (U < 0.05) | (U > 0.95) | ((V > 0.93) & (V < 0.97)) | ((V > 0.12) & (V < 0.15))
        waves = (V > 0.15) & (V < 0.2) & (np.sin(U * 40) > 0.2)
        m = sun | rays | mtn | border | waves
        return m, np.where((sun | rays | border)[..., None], col_gold, col_main)
    return e


def tool_animals(U, V):
    # tooled bear, elk, wolf, raven silhouettes as simple stamped diamonds and chevrons round the belt
    k = (U * 12) % 1
    chev = (np.abs(k - 0.5) * 2 < (V - 0.25) * 1.6) & (V > 0.25) & (V < 0.75) & ((np.abs(k - 0.5) * 2) > (V - 0.45) * 1.6)
    dots = (np.hypot(k - 0.5, (V - 0.5) * 0.6) < 0.08)
    return chev | dots


# ------------------------------------------------------------------ the pieces
def ang_l(deg):  # degrees towards the character's own left (bn_l_ side) from the front
    return math.radians(deg) * LSIDE


PIECES_R = {}


def piece(key):
    def deco(fn):
        PIECES_R[key] = fn
        return fn
    return deco


@piece("art_champion")
def build_champion(pc, at):
    navy, gold, crimson = C(0.05, 0.07, 0.22), C(0.78, 0.58, 0.18), C(0.55, 0.05, 0.06)
    r_band = at.cell(P_silk(navy, gold, stripes=[(0.08, 0.14, gold), (0.86, 0.92, gold), (0.47, 0.53, crimson)]), 2, 1)
    r_apron = at.cell(P_silk(crimson, gold, emb=emb_kesho(navy, gold), fringe=0.1, fringe_col=gold), 2, 3)
    r_cord = at.cell(P_solid(gold, 0.6, 0.35, 0.15, rings=12))
    r_tassel = at.cell(P_silk(gold, gold, fringe=0.7, fringe_col=gold))
    BP = band(pc, BELT_Z + 4.0, BELT_Z - 3.5, 5, 48, 0.3, 0.7, r_band)
    bo = bvh_of(BP, 5, 48, True)
    z_bot = ANKLE_Z + (KNEE_Z - ANKLE_Z) * 0.3
    xs = [-13 + 26 * i / 8 for i in range(9)]
    drape(pc, +1, xs, BELT_Z - 2.0, z_bot, 20, 0.4, 0.25, r_apron, widen=0.08)
    # a twisted gold cord round the band's middle and two tassels at the front corners
    nb = 48
    cord = {s: [on_band(BP, 5, nb, 2, 2 * math.pi * k / 40, 0.45)[s] for k in range(41)] for s in ALL}
    tube(pc, cord, 0.35, r_cord, [norm_w(torso_w(p)) for p in cord["basis"]], sides=6, caps=False)
    for sgn in (-1, 1):
        top = on_band(BP, 5, nb, 4, math.radians(22) * sgn, 0.5)
        card(pc, top, 9.0, 2.2, r_tassel, rows=4, tilt=0.12, thick=0.1)


@piece("art_fauld")
def build_fauld(pc, at):
    iron, dark = C(0.32, 0.32, 0.33), C(0.12, 0.11, 0.1)
    r_belt = at.cell(P_metal(iron * 0.8, rivets=10), 2, 1)
    r_lame = [at.cell(P_metal(iron, rivets=6, rust=0.12), 2, 1) for _ in range(4)]
    r_boss = at.cell(P_metal(iron * 1.1, boss=True))
    r_strap = at.cell(P_leather(dark))
    BP = band(pc, BELT_Z + 3.0, BELT_Z - 3.0, 4, 48, 0.3, 0.6, r_belt)
    over = bvh_of(BP, 4, 48, True)
    spans = (54, 50, 46, 42)
    for k in range(4):
        zt = BELT_Z - 2.0 - k * 4.3
        a = math.radians(spans[k])
        radial_drape(pc, -a, a, 11, zt, zt - 5.6, 4, 0.35 + 0.4 * k, 0.3, r_lame[k], over=over, tie_t=0.1 + 0.25 * k)
    # leather straps tying the lames (vertical, at +-30 degrees)
    for sgn in (-1, 1):
        a = math.radians(30) * sgn
        pth = path_on(lambda s, t: radial(s, BELT_Z - 1.5 - 14.0 * t, [a], 1.6, False)[0][0], 8)
        tube(pc, pth, 0.3, r_strap, [hang_w(p, 0.1 + 0.6 * k / 7) for k, p in enumerate(pth["basis"])], sides=4)
    c = on_band(BP, 4, 48, 1, 0.0, 0.35, -1.0)
    disc(pc, c, {s: outward(c[s], s) for s in ALL}, {s: UP for s in ALL}, 3.0, 0.7, r_boss, norm_w(torso_w(c["basis"])), seg=14)


@piece("art_feather")
def build_feather(pc, at):
    red, yellow, black = C(0.62, 0.06, 0.04), C(0.92, 0.72, 0.12), C(0.05, 0.04, 0.03)
    r_band = at.cell(P_scales(red, yellow), 2, 1)
    r_fr = [at.cell(P_feather(red, yellow, tip=black)), at.cell(P_feather(yellow, red, tip=red * 0.5))]
    r_tail = at.cell(P_silk(red, yellow, stripes=[(0.15, 0.22, yellow), (0.45, 0.52, yellow), (0.75, 0.82, yellow)]), 1, 3)
    r_tooth = at.cell(P_solid(C(0.88, 0.84, 0.72), 0.45, 0.35, 0.1, rings=3))
    BP = band(pc, BELT_Z + 2.5, BELT_Z - 2.5, 4, 48, 0.3, 0.8, r_band)
    for row, n, ln, off in ((3, 22, 7.5, 0.4), (2, 22, 6.0, 1.0)):
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * (row == 2)) / n
            if abs(((a - ang_l(80)) + math.pi) % (2 * math.pi) - math.pi) < math.radians(12):
                continue  # the tail hangs there
            top = on_band(BP, 4, 48, row, a, off)
            card(pc, top, ln, 3.0, r_fr[k % 2], rows=4, tilt=0.3 + 0.1 * (row == 2), thick=0.06)
    a0, a1 = ang_l(70), ang_l(90)
    TP = radial_drape(pc, min(a0, a1), max(a0, a1), 4, BELT_Z - 1.5, KNEE_Z + 2.0, 12, 0.9, 0.25, r_tail)
    for j in (8, 10):
        for i in range(4):
            p = {s: TP[s][j * 4 + i] + outward(TP[s][j * 4 + i], s) * 0.25 for s in ALL}
            tip = {s: p[s] - UP * 1.8 + outward(p[s], s) * 0.2 for s in ALL}
            cone(pc, p, tip, 0.35, r_tooth, hang_w(p["basis"], 0.8), sides=5)


@piece("art_briar")
def build_briar(pc, at):
    hide, bark, thornc = C(0.36, 0.22, 0.12), C(0.30, 0.27, 0.12), C(0.55, 0.08, 0.06)
    r_belt = at.cell(P_leather(hide, tool=tool_animals), 2, 1)
    r_vine = at.cell(P_bark(bark), 2, 1)
    r_thorn = at.cell(P_bark(bark, thornc))
    r_plaque = at.cell(P_metal(C(0.55, 0.33, 0.16), rivets=0, boss=True))
    r_hag = [at.cell(P_feather(C(0.08, 0.07, 0.07), C(0.25, 0.22, 0.2))), at.cell(P_feather(C(0.2, 0.18, 0.17), C(0.06, 0.05, 0.05)))]
    BP = band(pc, BELT_Z + 2.0, BELT_Z - 2.0, 4, 48, 0.3, 0.6, r_belt)
    for ph in (0.0, math.pi):
        n = 72
        def vp(s, t, ph=ph):
            a = 2 * math.pi * t
            row = 1.5 - 1.05 * math.sin(3 * a + ph)  # rows 0..3 span BELT_Z+2..-2: z = BELT_Z + 1.4 sin
            return band_pt(BP, 4, 48, row, a, s, 0.5)
        pth = path_on(vp, n)
        tube(pc, pth, 0.55, r_vine, [norm_w(torso_w(p)) for p in pth["basis"]], sides=6, caps=False)
        for k in range(2, n - 1, 6):
            b = {s: pth[s][k] + outward(pth[s][k], s) * 0.4 for s in ALL}
            tip = {s: b[s] + (outward(b[s], s) * 1.3 + UP * (0.5 if k % 12 else -0.5)) for s in ALL}
            cone(pc, b, tip, 0.3, r_thorn, norm_w(torso_w(b["basis"])))
    c = on_band(BP, 4, 48, 1, 0.0, 0.9, -0.8)
    disc(pc, c, {s: outward(c[s], s) for s in ALL}, {s: UP for s in ALL}, 3.2, 0.6, r_plaque, norm_w(torso_w(c["basis"])), seg=6)
    for sgn in (-1, 1):
        for k in range(5):
            top = on_band(BP, 4, 48, 3, math.radians(84 + 7 * (k - 2)) * sgn, 0.6 + 0.12 * k)
            card(pc, top, 12.0 + 2.0 * (k % 2), 3.2, r_hag[k % 2], rows=4, tilt=0.2, thick=0.06, twist=0.15 * (k - 2))


@piece("art_amber")
def build_amber(pc, at):
    straw, green, amber, shell = C(0.62, 0.52, 0.28), C(0.28, 0.36, 0.14), C(0.85, 0.42, 0.05), C(0.35, 0.22, 0.08)
    r_wrap = at.cell(P_weave(straw, green), 2, 2)
    r_amber = at.cell(P_solid(amber, 0.7, 0.2, 0.25))
    r_cord = at.cell(P_solid(C(0.3, 0.25, 0.15), 0.2, 0.7, 0.1, rings=20))
    r_shell = at.cell(P_solid(shell, 0.65, 0.25, 0.2, mottled=C(0.7, 0.5, 0.15)))
    nb, rows = 48, 6
    BP = band(pc, BELT_Z + 3.0, BELT_Z - 7.0, rows, nb, 0.35, 0.5, r_wrap)
    over = bvh_of(BP, rows, nb, True)
    for a0, a1 in ((-62, -22), (-20, 20), (22, 62)):
        A = on_band(BP, rows, nb, rows - 1, math.radians(a0), 0.2)
        B = on_band(BP, rows, nb, rows - 1, math.radians(a1), 0.2)
        def sw(s, t, A=A, B=B):
            p = A[s].lerp(B[s], t) - UP * (5.5 * 4 * t * (1 - t))
            c = Vector((0, cy(p.z, s), p.z))
            a = math.atan2((p - c).dot(RIGHT), (p - c).dot(FRONT))
            return clear_pt(s, radial(s, p.z, [a], 1.0, False, over=over)[0][0], 1.15)
        pth = path_on(sw, 15)
        tube(pc, pth, 0.12, r_cord, [hang_w(p, 0.25) for p in pth["basis"]], sides=4)
        for k in range(1, 14, 2):
            cs = {s: pth[s][k] for s in ALL}
            blob(pc, cs, 0.85 + 0.25 * (k == 7), r_amber, hang_w(cs["basis"], 0.25), seg=8, rings=5)
    for sgn in (-1, 1):  # tortoise-shell plates over the wrap at the hips
        a0, a1 = math.radians(78) * sgn, math.radians(102) * sgn
        radial_drape(pc, min(a0, a1), max(a0, a1), 5, BELT_Z + 1.0, BELT_Z - 6.0, 5, 0.3, 0.3, r_shell, over=over, tie_t=0.0)


@piece("art_bone")
def build_bone(pc, at):
    raw, bone, beetle = C(0.62, 0.5, 0.34), C(0.88, 0.84, 0.7), C(0.08, 0.38, 0.32)
    r_belt = at.cell(P_leather(raw, border=True), 2, 1)
    r_bone = at.cell(P_solid(bone, 0.4, 0.4, 0.12, rings=3))
    r_bead = at.cell(P_solid(beetle, 0.8, 0.15, 0.3, mottled=C(0.25, 0.1, 0.4)))
    r_cord = at.cell(P_solid(raw * 0.7, 0.2, 0.7, 0.1, rings=16))
    nb = 48
    BP = band(pc, BELT_Z + 2.0, BELT_Z - 2.0, 4, nb, 0.3, 0.5, r_belt)
    for side, nrow in ((+1, 8), (-1, 6)):
        D = FRONT * side
        # the rows' places: a drape (not drawn) over everything worn under them
        xs = [-9 + 18 * i / 10 for i in range(11)]
        ghost = Piece("ghost", "x")
        G = drape(ghost, side, xs, BELT_Z - 2.5, BELT_Z - 2.5 - 2.6 * (nrow - 1), nrow, 0.55, 0.1, (0, 0, 1, 1))
        for j in range(nrow):
            t = 0.1 + 0.8 * j / max(nrow - 1, 1)
            for half in (range(0, 5), range(6, 11)):
                pth = {s: [G[s][j * 11 + i] for i in half] for s in ALL}
                tube(pc, pth, 0.45, r_bone, [hang_w(p, t) for p in pth["basis"]], sides=6)
            cs = {s: G[s][j * 11 + 5] for s in ALL}
            blob(pc, cs, 0.55, r_bead, hang_w(cs["basis"], t), seg=6, rings=4)
        for i in (0, 10):  # side cords
            pth = {s: [G[s][j * 11 + i] + D * 0.1 for j in range(nrow)] for s in ALL}
            tube(pc, pth, 0.14, r_cord, [hang_w(p, 0.1 + 0.8 * j / (nrow - 1)) for j, p in enumerate(pth["basis"])], sides=4)
        for i in (0, 10):  # hanging ends with a bead
            top = {s: G[s][(nrow - 1) * 11 + i] for s in ALL}
            pth = {s: [top[s] - UP * 2.2 * k for k in range(3)] for s in ALL}
            tube(pc, pth, 0.12, r_cord, [hang_w(p, 0.95) for p in pth["basis"]], sides=4)
            cs = {s: pth[s][-1] for s in ALL}
            blob(pc, cs, 0.5, r_bead, hang_w(cs["basis"], 1.0), seg=6, rings=4)


@piece("art_ash")
def build_ash(pc, at):
    guar, chitin, blue, ochre = C(0.42, 0.3, 0.18), C(0.36, 0.24, 0.1), C(0.1, 0.25, 0.42), C(0.7, 0.45, 0.12)
    r_belt = [at.cell(P_leather(guar), 2, 1), at.cell(P_leather(guar * 0.8), 2, 1)]
    r_tas = [at.cell(P_silk(chitin, ochre, stripes=[(0.1, 0.18, blue), (0.82, 0.9, ochre)]), 1, 1) for _ in range(3)]
    r_buckle = at.cell(P_metal(chitin * 1.3, boss=True))
    nb = 48
    B1 = band(pc, BELT_Z + 1.8, BELT_Z - 1.8, 3, nb, 0.3, 0.5, r_belt[0], tilt_fn=lambda a: 2.6 * math.sin(a))
    over = bvh_of(B1, 3, nb, True)
    B2 = band(pc, BELT_Z + 1.8, BELT_Z - 1.8, 3, nb, 0.3, 0.5, r_belt[1], tilt_fn=lambda a: -2.6 * math.sin(a), over=over)
    for b_ in bvh_of(B2, 3, nb, True).items():
        over[b_[0]] = over[b_[0]] + b_[1]
    c = on_band(B2, 3, nb, 1, 0.0, 0.5)
    disc(pc, c, {s: outward(c[s], s) for s in ALL}, {s: UP for s in ALL}, 2.4, 0.6, r_buckle, norm_w(torso_w(c["basis"])), seg=8)
    for sgn in (-1, 1):
        a0, a1 = math.radians(28) * sgn, math.radians(60) * sgn
        for k in range(3):
            zt = BELT_Z - 3.0 - k * 4.8
            radial_drape(pc, min(a0, a1), max(a0, a1), 5, zt, zt - 6.2, 4, 0.4 + 0.4 * k, 0.3, r_tas[k], over=over,
                         tie_t=0.15 + 0.25 * k)


@piece("art_moon")
def build_moon(pc, at):
    purple, silver, red = C(0.2, 0.06, 0.26), C(0.82, 0.84, 0.88), C(0.6, 0.18, 0.12)
    def moons(U, V):
        k = (U * 6) % 1
        d1 = np.hypot(k - 0.5, (V - 0.5) * 0.5)
        d2 = np.hypot(k - 0.42, (V - 0.5) * 0.5)
        m = (d1 < 0.22) & ~(d2 < 0.2)
        return m, np.broadcast_to(silver, m.shape + (3,))
    r_sash = at.cell(P_silk(purple, silver, emb=moons), 2, 1)
    r_tail = at.cell(P_silk(purple, silver, emb=moons, fringe=0.12, fringe_col=silver), 1, 2)
    r_mas = at.cell(P_metal(red))
    r_sec = at.cell(P_metal(silver))
    r_cord = at.cell(P_solid(silver * 0.8, 0.6, 0.3, 0.1, rings=14))
    ak = ang_l(-70)  # the knot on the right hip
    tilt = lambda a: -1.6 * (1 + math.cos(a - ak)) / 2
    nb = 48
    SP = band(pc, BELT_Z + 1.5, BELT_Z - 4.0, 4, nb, 0.35, 0.5, r_sash, tilt_fn=tilt)
    over = bvh_of(SP, 4, nb, True)
    kn = on_band(SP, 4, nb, 2, ak, 1.4)
    o = {s: outward(kn[s], s) for s in ALL}
    blob(pc, kn, 1.0, r_sash, norm_w(torso_w(kn["basis"])), seg=8, rings=5,
         axes={s: (UP.cross(o[s]).normalized() * 2.4, o[s] * 1.3, UP * 1.9) for s in ALL})
    for da, ln in ((-7, 30.0), (6, 24.0)):
        a = ak + math.radians(da)
        zt = kn["basis"].z - 1.0
        radial_drape(pc, a - math.radians(4.5), a + math.radians(4.5), 3, zt, zt - ln, 10, 0.7 + 0.3 * (da > 0), 0.2, r_tail,
                     over=over, tie_t=0.1)
    for da, r, rect, ln in ((-14, 2.0, r_mas, 7.0), (14, 1.3, r_sec, 5.0)):
        top = {s: kn[s] + o[s] * 0.6 for s in ALL}
        bot = {s: top[s] - UP * ln + o[s] * 1.4 + UP.cross(o[s]).normalized() * (da * 0.12) for s in ALL}
        pth = {s: [top[s].lerp(bot[s], k / 4) for k in range(5)] for s in ALL}
        tube(pc, pth, 0.1, r_cord, [hang_w(p, 0.2 + 0.15 * k) for k, p in enumerate(pth["basis"])], sides=4)
        cen = {s: clear_pt(s, bot[s] - UP * r, r * 0.4 + 0.5) for s in ALL}
        disc(pc, cen, {s: outward(cen[s], s) for s in ALL}, {s: UP for s in ALL}, r, 0.4, rect, hang_w(cen["basis"], 0.8))


# ------------------------------------------------------------------ auto-worn pieces (2026-11-09): new meshes, own textures
def hang_line(s, a, z0, length, n, gap, over=None):
    """Points of a stiff cord hanging from height z0 at angle a: straight down, never inside anything under it."""
    pts, prev = [], None
    for j in range(n):
        z = z0 - length * j / (n - 1)
        c = Vector((0, cy(z, s), z))
        d = dirv(a)
        h = first_hit(s, c + d * 80, -d, 80, ALLB[s] + (over[s] if over else []))
        r = (h[0] - c).dot(d) if h else -1e9
        if prev is not None:
            r = max(r, (prev - c).dot(d) - gap)
        p = c + d * (r + gap)
        pts.append(p)
        prev = p
    return pts


def P_rope(col):
    def f(U, V, rng, sh):
        n = noise(sh, 10, int(rng.integers(1000000)))
        tw = 0.65 + 0.35 * np.sin((U * 6 + V * 40) * np.pi)
        return {"rgb": col[None, None, :] * (tw * (0.85 + 0.25 * n))[..., None], "spec": np.full(sh, 0.18, np.float32),
                "rough": np.full(sh, 0.75, np.float32)}
    return f


def emb_tree(col):
    """A sacred tree: trunk, branches, roots and a sun disc above, in a border."""
    def e(U, V):
        x, y = U - 0.5, V
        trunk = (np.abs(x) < 0.04) & (y > 0.22) & (y < 0.62)
        crown = np.zeros(np.shape(U), bool)  # a cluster of leafy lobes
        for cx, cy_, r in ((-0.15, 0.64, 0.085), (0.15, 0.64, 0.085), (-0.09, 0.75, 0.09), (0.09, 0.75, 0.09), (0.0, 0.83, 0.08),
                           (-0.22, 0.72, 0.06), (0.22, 0.72, 0.06)):
            crown |= np.hypot((x - cx) * 1.0, (y - cy_) * 1.5) < r
        holes = np.zeros(np.shape(U), bool)
        branches = (np.abs(np.abs(x) - (y - 0.5) * 0.9) < 0.025) & (y > 0.5) & (y < 0.8)
        roots = (np.abs(np.abs(x) - (0.3 - y) * 1.4) < 0.025) & (y > 0.12) & (y < 0.3)
        sun = (np.hypot(x, (y - 0.9) * 1.5) < 0.06)
        border = (U < 0.06) | (U > 0.94) | ((V > 0.95)) | ((V > 0.14) & (V < 0.17))
        zig = (V > 0.17) & (V < 0.2) & (np.abs(((U * 14) % 1) - 0.5) * 0.06 > np.abs(V - 0.185))
        m = trunk | (crown & ~holes) | branches | roots | sun | border | zig
        return m, np.broadcast_to(col, m.shape + (3,))
    return e


@piece("wrestler_belt")
def build_wrestler(pc, at):
    indigo, sheen = C(0.08, 0.1, 0.3), C(0.18, 0.22, 0.5)
    r_belt = at.cell(P_silk(indigo, sheen, stripes=[(0.18, 0.2, indigo * 0.6), (0.38, 0.4, indigo * 0.6), (0.58, 0.6, indigo * 0.6),
                                                    (0.78, 0.8, indigo * 0.6)]), 2, 2)
    r_cord = at.cell(P_solid(indigo * 1.2, 0.5, 0.35, 0.12, rings=8))
    r_knot = at.cell(P_silk(indigo, sheen))
    nb, rows = 48, 6
    BP = band(pc, BELT_Z + 5.0, BELT_Z - 3.0, rows, nb, 1.35, 0.9, r_belt)
    over = bvh_of(BP, rows, nb, True)
    # the back knot
    kn = on_band(BP, rows, nb, 2.0, math.pi, 1.2)
    o = {s: outward(kn[s], s) for s in ALL}
    blob(pc, kn, 1.0, r_knot, norm_w(torso_w(kn["basis"])), seg=10, rings=6,
         axes={s: (UP.cross(o[s]).normalized() * 4.0, o[s] * 1.6, UP * 3.0) for s in ALL})
    # sagari: stiff cords hanging in front
    for k in range(15):
        a = math.radians(-36 + 72 * k / 14)
        z0 = band_pt(BP, rows, nb, rows - 1, a, "basis").z + 0.5
        ln = 19.0 + 2.0 * math.cos(a * 3)
        pth = {s: hang_line(s, a, z0, ln, 7, 0.75, over) for s in ALL}
        tube(pc, pth, 0.32, r_cord, [hang_w(p, 0.1 + 0.8 * j / 6) for j, p in enumerate(pth["basis"])], sides=5)


@piece("hunter_gear")
def build_hunter(pc, at):
    hide, dark, antler = C(0.42, 0.28, 0.15), C(0.2, 0.13, 0.07), C(0.82, 0.76, 0.62)
    r_strap = at.cell(P_leather(dark, border=False))
    r_pouch = at.cell(P_leather(hide, tool=lambda U, V: (np.abs(V - 0.7) < 0.02) | (np.hypot(U - 0.5, V - 0.45) < 0.06)), 2, 1)
    r_sheath = at.cell(P_leather(dark, tool=lambda U, V: np.abs(((U * 3 + V * 8) % 1) - 0.5) < 0.05), 1, 2)
    r_antler = at.cell(P_solid(antler, 0.35, 0.45, 0.15, rings=6))
    r_bead = at.cell(P_solid(C(0.6, 0.2, 0.08), 0.6, 0.25, 0.1))
    r_feather = at.cell(P_feather(C(0.35, 0.25, 0.15), C(0.85, 0.82, 0.75), tip=C(0.1, 0.08, 0.06)))
    # a strap round the hips, just under the cord belt
    strap = {s: radial(s, BELT_Z - 1.2, [2 * math.pi * k / 48 for k in range(48)], 0.9)[0] for s in ALL}
    for s in ALL:
        strap[s] = strap[s] + [strap[s][0]]
    tube(pc, strap, 0.3, r_strap, [norm_w(torso_w(p)) for p in strap["basis"]], sides=5, caps=False)
    # the pouch on the right hip
    ar = ang_l(-82)
    def pouch_c(s):
        p = radial(s, BELT_Z - 6.5, [ar], 2.9, False)[0][0]
        return clear_pt(s, p, 2.8)
    pc_ = {s: pouch_c(s) for s in ALL}
    o = {s: outward(pc_[s], s) for s in ALL}
    blob(pc, pc_, 1.0, r_pouch, hang_w(pc_["basis"], 0.35), seg=10, rings=6,
         axes={s: (UP.cross(o[s]).normalized() * 5.6, o[s] * 2.4, UP * 6.2) for s in ALL})
    tb = {s: pc_[s] + o[s] * 2.4 + UP * 3.0 for s in ALL}
    blob(pc, tb, 0.55, r_bead, hang_w(tb["basis"], 0.3), seg=6, rings=4)
    # the knife on the left hip: sheath angled forward, antler handle above
    al = ang_l(68)
    top = {s: radial(s, BELT_Z - 1.0, [al], 1.6, False)[0][0] for s in ALL}
    def sheath(s, t):
        p = top[s] - UP * (17.0 * t) + dirv(al - LSIDE * 0.35) * (3.0 * t)
        return clear_pt(s, radial(s, p.z, [math.atan2((p - Vector((0, cy(p.z, s), p.z))).dot(RIGHT),
                                                      (p - Vector((0, cy(p.z, s), p.z))).dot(FRONT))], 1.3, False)[0][0], 1.3)
    sp = path_on(sheath, 8)
    tube(pc, sp, 1.1, r_sheath, [hang_w(p, 0.2 + 0.5 * k / 7) for k, p in enumerate(sp["basis"])], sides=6,
         rad_fn=lambda t: 1.0 - 0.6 * t)
    hp = {s: [sp[s][0] + (sp[s][0] - sp[s][1]).normalized() * (5.5 * k / 4) for k in range(5)] for s in ALL}
    tube(pc, hp, 0.7, r_antler, [hang_w(p, 0.15) for p in hp["basis"]], sides=6)
    pm = {s: hp[s][-1] for s in ALL}
    blob(pc, pm, 0.9, r_antler, hang_w(pm["basis"], 0.15), seg=6, rings=4)
    # two fletching feathers tied at the pouch
    for k in (-1, 1):
        t0 = {s: pc_[s] + UP.cross(o[s]).normalized() * (3.2 * k) + UP * 3.0 + o[s] * 0.8 for s in ALL}
        card(pc, t0, 8.0, 2.0, r_feather, rows=3, tilt=0.15, thick=0.05, twist=0.2 * k)


@piece("priest_apron")
def build_priest(pc, at):
    linen, ochre, bone = C(0.86, 0.8, 0.66), C(0.55, 0.16, 0.06), C(0.85, 0.8, 0.68)
    r_rope = at.cell(P_rope(C(0.62, 0.52, 0.34)))
    r_front = at.cell(P_silk(linen, ochre, emb=emb_tree(ochre), fringe=0.08, fringe_col=linen * 0.9), 2, 3)
    r_back = at.cell(P_silk(linen, ochre, stripes=[(0.86, 0.9, ochre), (0.2, 0.24, ochre)], fringe=0.08, fringe_col=linen * 0.9), 1, 3)
    r_disc = at.cell(P_metal(bone, boss=True))
    r_tassel = at.cell(P_silk(ochre, ochre, fringe=0.75, fringe_col=ochre))
    rope = {s: radial(s, BELT_Z + 1.6, [2 * math.pi * k / 48 for k in range(48)], 0.8)[0] for s in ALL}
    for s in ALL:
        rope[s] = rope[s] + [rope[s][0]]
    tube(pc, rope, 0.45, r_rope, [norm_w(torso_w(p)) for p in rope["basis"]], sides=6, caps=False)
    zb = KNEE_Z + 3.0
    drape(pc, +1, [-11 + 22 * i / 8 for i in range(9)], BELT_Z + 0.5, zb, 16, 0.45, 0.25, r_front, widen=0.05)
    drape(pc, -1, [-10 + 20 * i / 4 for i in range(5)], BELT_Z + 0.5, zb + 3.0, 14, 0.45, 0.25, r_back, widen=0.05)
    # the amulet over the apron's top, and tassels at the sides
    c = {s: Vector((0, 0, BELT_Z - 3.5)) + FRONT * (first_hit(s, Vector((0, 0, BELT_Z - 3.5)) + FRONT * 80, -FRONT, 160)[0].dot(FRONT) + 1.3)
         for s in ALL}
    disc(pc, c, {s: FRONT for s in ALL}, {s: UP for s in ALL}, 2.2, 0.45, r_disc, hang_w(c["basis"], 0.2), seg=12)
    cord = {s: [Vector((0, 0, BELT_Z + 1.6)) + FRONT * (first_hit(s, Vector((0, 0, BELT_Z + 1.6)) + FRONT * 80, -FRONT, 160)[0].dot(FRONT) + 1.1),
                c[s] + UP * 2.2] for s in ALL}
    tube(pc, cord, 0.12, r_rope, [norm_w(torso_w(cord["basis"][0])), hang_w(cord["basis"][1], 0.2)], sides=4)
    for sgn in (-1, 1):
        top = {s: rope[s][int(round((math.radians(95) * sgn % (2 * math.pi)) / (2 * math.pi) * 48)) % 48] for s in ALL}
        card(pc, top, 11.0, 2.4, r_tassel, rows=4, tilt=0.1, thick=0.08)


@piece("victor_sash")
def build_victor(pc, at):
    crimson, gold = C(0.62, 0.05, 0.07), C(0.86, 0.66, 0.2)
    def lozenges(U, V):
        k = (U * 10) % 1
        m = (np.abs(k - 0.5) + np.abs(V - 0.5) * 0.5 < 0.18) & (V > 0.2) & (V < 0.8)
        return m, np.broadcast_to(gold, m.shape + (3,))
    r_sash = at.cell(P_silk(crimson, gold, emb=lozenges, stripes=[(0.03, 0.12, gold), (0.88, 0.97, gold)]), 4, 1)
    r_knot = at.cell(P_silk(crimson, gold))
    r_tail = at.cell(P_silk(crimson, gold, stripes=[(0.2, 0.25, gold)], fringe=0.2, fringe_col=gold), 1, 2)
    neck = rig.matrix_world @ rig.data.bones["bn_sp_cervical"].head_local
    # over the right shoulder, on the trapezius: the body mesh is open at the neck out to about 12.5 cm (the head mesh
    # covers the neck), so the sash crosses further out
    for _x in (16.0, 16.5, 17.0, 17.5, 18.0):
        sh_x = -LSIDE * _x
        _h = BVH["basis"].ray_cast(Vector((sh_x, neck.y, neck.z + 40)), -UP, 80)[0]
        if _h is not None:
            break
    top = Vector((sh_x, neck.y, _h.z - 4.0))
    low = Vector((LSIDE * 13.0, cy(BELT_Z + 8.0, "basis"), BELT_Z + 8.0))
    u = (top - low).normalized()
    nrm = u.cross(FRONT).normalized()
    cen = (top + low) / 2
    NL = 56
    phis = [2 * math.pi * k / NL for k in range(NL)]
    WD = [-2.5, 0.0, 2.5]
    P = {}
    for s in ALL:
        P[s] = []
        for w_ in WD:
            c0 = cen + nrm * w_
            rs, dirs = [], []
            for ph in phis:
                d = (u * math.cos(ph) + FRONT * math.sin(ph)).normalized()
                # the upper half crosses the shoulder: the whole body, arms too (the lower half: arms left out, the hands
                # hang beside the hips)
                full = [BVH[s]] + [o[s] for o in OBST if s in o]
                h = first_hit(s, c0 + d * 90, -d, 90, full if d.dot(UP) > 0.2 else None)
                ok = h is not None and h[1].dot(d) > 0.05  # an outer surface, facing the ray
                rs.append((h[0] - c0).dot(d) if ok else None)
                dirs.append(d)
            for k in range(NL):  # a missed or inward-facing hit: the larger of its nearest good neighbours
                if rs[k] is None:
                    a_ = next(rs[(k - j) % NL] for j in range(1, NL) if rs[(k - j) % NL] is not None)
                    b_ = next(rs[(k + j) % NL] for j in range(1, NL) if rs[(k + j) % NL] is not None)
                    rs[k] = max(a_, b_)
            rs = smooth_max(rs, 4)
            P[s] += [c0 + d * (r + 0.55) for d, r in zip(dirs, rs)]
    ws = [norm_w(torso_w(p)) for p in P["basis"]]
    slab(pc, P, len(WD), NL, r_sash, ws, 0.3, lambda c: c - cen, closed=True)
    # the knot at the left waist and two short fringed ends
    kn = {s: P[s][NL + NL // 2] + (P[s][NL + NL // 2] - cen).normalized() * 1.0 for s in ALL}
    o = {s: outward(kn[s], s) for s in ALL}
    blob(pc, kn, 1.0, r_knot, norm_w(torso_w(kn["basis"])), seg=8, rings=5,
         axes={s: (UP.cross(o[s]).normalized() * 2.6, o[s] * 1.4, UP * 2.2) for s in ALL})
    ka = math.atan2((kn["basis"] - Vector((0, cy(kn["basis"].z, "basis"), 0))).dot(RIGHT),
                    (kn["basis"] - Vector((0, cy(kn["basis"].z, "basis"), 0))).dot(FRONT))
    for da, ln in ((-6, 6.5), (5, 5.0)):
        a = ka + math.radians(da)
        zt = kn["basis"].z - 1.5
        radial_drape(pc, a - math.radians(5), a + math.radians(5), 3, zt, zt - ln, 6, 1.1 + 0.3 * (da > 0), 0.2, r_tail, tie_t=0.1)


# ------------------------------------------------------------------ wraps that replace the loincloth (2026-11-09)
# Worn instead of our loincloth (it draws nothing under them, tag ek2lc_wrap), so they sit inside the room the loincloth
# takes (under_base): every girdle, apron and regalia built over the loincloth still fits over them.
BASEB = OBST[0]
WRAPB = {s: [TB[s]] + ([OBST[1][s]] if s in OBST[1] else []) for s in ALL}  # the body and the leggings


def under_base(s, c, d, r_want, r_skin, inset=0.12):
    """Radius r_want along c + d*r, kept inset under the loincloth where it is there (never nearer the skin than 0.15)."""
    if s not in BASEB:
        return r_want
    h = BASEB[s].ray_cast(c + d * 80, -d, 80)[0]
    if h is None:
        return r_want
    rb = (h - c).dot(d)
    return max(rb - inset, r_skin + 0.15) if r_want > rb - inset else r_want


def wrap_strip(pc, rect):
    """The part between the legs, over the fig leaf (the loincloth's own algorithm, its own mesh and texture)."""
    P = {s: surface_parts(s)[NB * 5:] for s in ALL}
    ws = [weights_at(b[0], b[1]) for b in strip_bind]
    slab(pc, P, NS, SC, rect, ws, 0.1, lambda c: c - P0)


def wrap_common(pc, at, band_painter, strip_painter, z_top=1.6, z_bot=-1.6, gap=0.45):
    rb = at.cell(band_painter, 2, 1)
    rs = at.cell(strip_painter, 1, 2)
    BP = band(pc, BELT_Z + z_top, BELT_Z + z_bot, 4, 48, gap, 0.12, rb, bvhs=WRAPB, clamp=True)
    wrap_strip(pc, rs)
    return BP


def P_torn(base_painter, holes=0.08, jag=0.12, claws=False, seed=0):
    """A painter's cloth or hide, torn: holes, a jagged lower edge (low V), and optionally three claw slashes."""
    def f(U, V, rng, sh):
        r = base_painter(U, V, rng, sh)
        n = noise(sh, 9, int(rng.integers(1000000)))
        n2 = noise(sh, 30, int(rng.integers(1000000)))
        a = np.ones(sh, np.float32) * (r.get("a", 1.0) if np.ndim(r.get("a", 1.0)) else 1.0)
        a = np.where(n2 > 1 - holes, 0.0, a)
        a = np.where(V < jag * (0.35 + 0.65 * n), 0.0, a)
        rgb = r["rgb"] * (0.75 + 0.3 * n)[..., None]
        rgb = np.where((n2 > 1 - holes * 1.6)[..., None], rgb * 0.55, rgb)  # frayed, darker round the holes
        if claws:
            for k in range(3):
                line = np.abs((U - 0.3 - 0.12 * k) - (V - 0.5) * 0.35)
                cut = (line < 0.018) & (V > 0.25) & (V < 0.8)
                a = np.where(cut, 0.0, a)
                rgb = np.where(((line < 0.04) & (V > 0.22) & (V < 0.83))[..., None], rgb * 0.5, rgb)
        r = dict(r)
        r["rgb"], r["a"] = rgb, a
        return r
    return f


@piece("festival_wrap")
def build_festival(pc, at):
    white, shade = C(0.93, 0.92, 0.88), C(0.8, 0.79, 0.75)
    BP = wrap_common(pc, at, P_rope(white), P_silk(white, shade), z_top=1.4, z_bot=-1.4, gap=0.5)
    kn = on_band(BP, 4, 48, 1.5, math.pi, 0.5)
    o = {s: outward(kn[s], s) for s in ALL}
    blob(pc, kn, 1.0, at.cell(P_rope(white)), norm_w(torso_w(kn["basis"])), seg=8, rings=5,
         axes={s: (UP.cross(o[s]).normalized() * 2.6, o[s] * 1.2, UP * 2.0) for s in ALL})


@piece("wedding_wrap")
def build_wedding(pc, at):
    ivory, gold, red = C(0.92, 0.88, 0.78), C(0.85, 0.65, 0.2), C(0.6, 0.08, 0.08)
    def emb(U, V):
        k = (V * 8) % 1
        m = ((np.abs(U - 0.5) < 0.03) & (V > 0.2)) | ((np.abs(np.abs(U - 0.5) - k * 0.3) < 0.02) & (V > 0.2) & (V < 0.95)) \
            | (U < 0.05) | (U > 0.95)
        return m, np.where(((U < 0.05) | (U > 0.95))[..., None], gold, red)
    BP = wrap_common(pc, at, P_silk(ivory, gold, stripes=[(0.1, 0.25, gold), (0.75, 0.9, gold)]), P_silk(ivory, gold))
    zb = KNEE_Z + 4.0
    FP = drape(pc, +1, [-9 + 18 * i / 6 for i in range(7)], BELT_Z - 0.5, zb, 14, 0.45, 0.12,
               at.cell(P_silk(ivory, gold, emb=emb, fringe=0.06, fringe_col=gold), 2, 2), widen=0.05, bvhs=WRAPB, clamp=True)
    drape(pc, -1, [-8 + 16 * i / 4 for i in range(5)], BELT_Z - 0.5, BELT_Z - 28.0, 11, 0.45, 0.12,
          at.cell(P_silk(ivory, gold, stripes=[(0.1, 0.16, gold), (0.84, 0.9, gold)])), bvhs=WRAPB, clamp=True)
    r_bead = at.cell(P_solid(red, 0.7, 0.2, 0.15))
    for i in range(7):  # red beads along the hem
        cs = {s: FP[s][13 * 7 + i] - UP * 0.9 + FRONT * 0.15 for s in ALL}
        blob(pc, cs, 0.55, r_bead, hang_w(cs["basis"], 1.0), seg=6, rings=4)


@piece("mourning_wrap")
def build_mourning(pc, at):
    soot, ash = C(0.09, 0.085, 0.08), C(0.45, 0.44, 0.42)
    def smudge(U, V):
        x = (U - 0.5) * 2
        m = np.zeros(np.shape(U), bool)  # three fingers' smears of ash, top left to lower right
        for k in (-0.22, 0.0, 0.22):
            m |= (np.abs((x - k) + (V - 0.7) * 0.5) < 0.045) & (V > 0.5) & (V < 0.9)
        return m, np.broadcast_to(ash, m.shape + (3,))
    plain = P_leather(soot, border=False)
    BP = wrap_common(pc, at, P_leather(soot * 1.2), P_leather(soot))
    zb = KNEE_Z + 2.0
    drape(pc, +1, [-10 + 20 * i / 6 for i in range(7)], BELT_Z - 0.5, zb, 14, 0.45, 0.12,
          at.cell(P_silk(soot, ash, emb=smudge), 2, 2), widen=0.04, bvhs=WRAPB, clamp=True)
    drape(pc, -1, [-10 + 20 * i / 6 for i in range(7)], BELT_Z - 0.5, zb + 2.0, 14, 0.45, 0.12, at.cell(plain, 2, 1),
          widen=0.04, bvhs=WRAPB, clamp=True)


@piece("ragged_loincloth")
def build_ragged(pc, at):
    dirt = C(0.36, 0.3, 0.22)
    BP = wrap_common(pc, at, P_torn(P_leather(dirt * 0.8, border=False), 0.05, 0.0), P_torn(P_leather(dirt, border=False), 0.04, 0.0))
    drape(pc, +1, [-8 + 16 * i / 5 for i in range(6)], BELT_Z - 0.5, BELT_Z - 27.0, 11, 0.45, 0.12,
          at.cell(P_torn(P_leather(dirt, border=False), 0.07, 0.22), 2, 2), bvhs=WRAPB, clamp=True)
    drape(pc, -1, [-7 + 14 * i / 4 for i in range(5)], BELT_Z - 0.5, BELT_Z - 22.0, 9, 0.45, 0.12,
          at.cell(P_torn(P_leather(dirt * 0.9, border=False), 0.07, 0.25)), bvhs=WRAPB, clamp=True)


@piece("elder_wrap")
def build_elder(pc, at):
    flax, umber = C(0.72, 0.66, 0.52), C(0.38, 0.26, 0.15)
    BP = wrap_common(pc, at, P_silk(flax, umber, stripes=[(0.15, 0.3, umber)]), P_silk(flax, umber), z_top=2.4, z_bot=-2.0)
    zb = KNEE_Z - 1.0
    for side in (1, -1):
        drape(pc, side, [-13 + 26 * i / 8 for i in range(9)], BELT_Z - 0.5, zb, 16, 0.45, 0.12,
              at.cell(P_silk(flax, umber, stripes=[(0.04, 0.09, umber), (0.12, 0.14, umber)]), 2, 2), widen=0.03,
              bvhs=WRAPB, clamp=True)


@piece("sailor_malo")
def build_sailor(pc, at):
    indigo, tapa = C(0.12, 0.2, 0.36), C(0.74, 0.6, 0.42)
    def tapa_pat(U, V):
        k = (U * 10) % 1
        m = (np.abs(k - 0.5) < 0.07) | ((np.abs(((V * 6) % 1) - 0.5) < 0.06) & (k < 0.5))
        return m, np.broadcast_to(tapa, m.shape + (3,))
    BP = wrap_common(pc, at, P_silk(indigo, tapa, emb=tapa_pat), P_silk(indigo, tapa, emb=tapa_pat), z_top=2.2, z_bot=-2.6, gap=0.5)
    ak = ang_l(-75)  # knotted on the right hip
    kn = on_band(BP, 4, 48, 1.5, ak, 0.6)
    o = {s: outward(kn[s], s) for s in ALL}
    blob(pc, kn, 1.0, at.cell(P_silk(indigo, tapa)), norm_w(torso_w(kn["basis"])), seg=8, rings=5,
         axes={s: (UP.cross(o[s]).normalized() * 2.4, o[s] * 1.2, UP * 2.0) for s in ALL})
    radial_drape(pc, ak - math.radians(5), ak + math.radians(5), 3, kn["basis"].z - 1.2, kn["basis"].z - 13.0, 7, 1.0, 0.15,
                 at.cell(P_silk(indigo, tapa, emb=tapa_pat, fringe=0.15, fringe_col=indigo * 1.3), 1, 2), tie_t=0.1)


@piece("werewolf_tatters")
def build_werewolf(pc, at):
    hide, fur = C(0.3, 0.22, 0.15), C(0.24, 0.2, 0.17)
    BP = wrap_common(pc, at, P_torn(P_leather(hide * 0.8, border=False), 0.05, 0.0), P_torn(P_leather(hide, border=False), 0.03, 0.0))
    drape(pc, +1, [-9 + 18 * i / 5 for i in range(6)], BELT_Z - 0.5, BELT_Z - 25.0, 10, 0.45, 0.12,
          at.cell(P_torn(P_leather(hide, border=False), 0.04, 0.25, claws=True), 2, 2), bvhs=WRAPB, clamp=True)
    drape(pc, -1, [-8 + 16 * i / 4 for i in range(5)], BELT_Z - 0.5, BELT_Z - 21.0, 9, 0.45, 0.12,
          at.cell(P_torn(P_leather(hide * 0.9, border=False), 0.05, 0.3, claws=True)), bvhs=WRAPB, clamp=True)
    r_fur = at.cell(P_feather(fur, fur * 0.6, tip=C(0.1, 0.08, 0.07)))
    for k in range(16):  # tufts of fur at the belt
        a = 2 * math.pi * (k + 0.5) / 16
        top = on_band(BP, 4, 48, 3, a, 0.15)
        card(pc, top, 4.5, 2.4, r_fur, rows=3, tilt=0.4, thick=0.05, twist=0.3 * ((k % 3) - 1))


# ------------------------------------------------------------------ cowrie war belt and holy-order tabard
GIRDLES = [obstacle("ek2lc_%s_reach_%s_01" % (S1, k)) for k in ("war", "armour")]
ROYAL = [obstacle("ek2lc_%s_reach_%s_01" % (S1, k)) for k in ("duke", "king", "emperor")]
WITH_WAR = {s: [g[s] for g in GIRDLES if s in g] for s in ALL}
WITH_ALL = {s: [g[s] for g in GIRDLES + ROYAL if s in g] for s in ALL}


def P_cowrie():
    def f(U, V, rng, sh):
        n = noise(sh, 10, int(rng.integers(1000000)))
        rgb = C(0.92, 0.88, 0.76)[None, None, :] * (0.88 + 0.18 * n)[..., None]
        slit = (np.abs(U - 0.25) < 0.025) & (V > 0.25) & (V < 0.75)
        teeth = slit & ((V * 30) % 1 < 0.5)
        rgb[slit] = C(0.45, 0.35, 0.25)
        rgb[teeth] = C(0.8, 0.74, 0.6)
        return {"rgb": rgb, "spec": np.full(sh, 0.6, np.float32), "rough": np.full(sh, 0.25, np.float32)}
    return f


def build_cowrie(pc, at, tier):
    raw = C(0.5, 0.36, 0.22)
    r_band = at.cell(P_leather(raw, border=True), 2, 1)
    r_shell = at.cell(P_cowrie())
    r_cord = at.cell(P_solid(raw * 0.8, 0.2, 0.7, 0.1, rings=16))
    BP = band(pc, BELT_Z + 1.3, BELT_Z - 1.3, 3, 48, 0.35, 0.3, r_band, over=WITH_WAR)
    over = bvh_of(BP, 3, 48, True)
    span = 72 if tier == 1 else 180
    n = 20 if tier == 1 else 48

    def shell(c, w):
        o = {s: outward(c[s], s) for s in ALL}
        blob(pc, c, 1.0, r_shell, w, seg=8, rings=4,
             axes={s: (UP.cross(o[s]).normalized() * 0.55, o[s] * 0.4, UP * 0.85) for s in ALL})

    for k in range(n):
        a = math.radians(-span + 2 * span * (k + 0.5) / n) if tier == 1 else 2 * math.pi * k / n
        for row in ((1.0,) if tier < 3 else (0.4, 1.6)):
            c = on_band(BP, 3, 48, row, a + (math.pi / n if row > 1 else 0), 0.35)
            shell(c, norm_w(torso_w(c["basis"])))
    strings = [] if tier == 1 else [53, -53] + ([133, -133] if tier == 3 else [])
    for deg in strings:
        a = math.radians(deg)
        z0 = band_pt(BP, 3, 48, 2, a, "basis").z
        pth = {s: hang_line(s, a, z0, 9.0, 6, 0.6, {x: over[x] + WITH_WAR[x] for x in ALL}) for s in ALL}
        tube(pc, pth, 0.1, r_cord, [hang_w(p, 0.15 + 0.15 * j) for j, p in enumerate(pth["basis"])], sides=4)
        for j in range(1, 6):
            c = {s: pth[s][j] + outward(pth[s][j], s) * 0.35 for s in ALL}
            shell(c, hang_w(c["basis"], 0.2 + 0.15 * j))


for _t in (1, 2, 3):
    PIECES_R["cowrie_%d" % _t] = (lambda t_: (lambda pc, at: build_cowrie(pc, at, t_)))(_t)


@piece("holy_tabard")
def build_tabard(pc, at):
    white, red, gold = C(0.9, 0.88, 0.82), C(0.55, 0.06, 0.06), C(0.85, 0.66, 0.2)
    def star(U, V):
        x, y = (U - 0.5) * 2, (V - 0.68) * 2.6
        ang, r = np.arctan2(y, x), np.hypot(x, y)
        st = r < 0.25 + 0.25 * np.abs(np.cos(ang * 4)) ** 6
        border = (U < 0.08) | (U > 0.92) | (V > 0.95) | (V < 0.05)
        m = st | border
        return m, np.where(st[..., None], gold, red)
    rope = {s: radial(s, BELT_Z + 3.2, [2 * math.pi * k / 48 for k in range(48)], 0.7, over=WITH_ALL)[0] for s in ALL}
    for s in ALL:
        rope[s] = rope[s] + [rope[s][0]]
    tube(pc, rope, 0.3, at.cell(P_rope(red)), [norm_w(torso_w(p)) for p in rope["basis"]], sides=5, caps=False)
    for side, ln in ((1, 32.0), (-1, 30.0)):
        drape(pc, side, [-6.5 + 13 * i / 4 for i in range(5)], BELT_Z + 2.6, BELT_Z + 2.6 - ln, 13, 0.6, 0.2,
              at.cell(P_silk(white, gold, emb=star, fringe=0.05, fringe_col=red), 1, 3), over=WITH_ALL)


# ------------------------------------------------------------------ build, export
def save_set(set_name, arrays):
    images = {}
    for kind, arr in arrays.items():
        png = os.path.join(TEXSRC, "%s_%s.png" % (set_name, kind))
        im = bpy.data.images.new("%s_%s" % (set_name, kind), arr.shape[1], arr.shape[0], alpha=True)
        im.pixels.foreach_set(np.ascontiguousarray(np.flipud(arr), dtype=np.float32).ravel())
        im.filepath_raw, im.file_format = png, "PNG"
        im.save()
        images[kind] = im
        subprocess.run([MAGICK, png, "-define", "dds:compression=dxt5", "-define", "dds:mipmaps=%d" % int(math.log2(arr.shape[0])),
                        os.path.join(OUT, "%s_%s.dds" % (set_name, kind))], check=True)
    return images


def make_material(name, images):
    m = bpy.data.materials.new(name)
    m["shader"] = "portrait_attachment_alpha_to_coverage"
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = images["diffuse"]
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    nt.nodes.active = tex
    return m


def export_display(obj, key, tset):
    """The artifact window's model: the piece unskinned, centred on the origin (vanilla's inventory artifacts are
    static meshes with the court shader)."""
    me = obj.data.copy()
    c = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)
    for v in me.vertices:
        v.co -= c
    me.name = "ek2lc_%s_artifactShape" % key
    o = bpy.data.objects.new("ek2lc_%s_artifact" % key, me)
    scene.collection.objects.link(o)
    for x in bpy.context.view_layer.objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.io_pdx_mesh.export_mesh(filepath=os.path.join(OUT, "ek2lc_%s_artifact.mesh" % key), chk_mesh=True, chk_skel=False,
                                     chk_locs=False, chk_selected=True, chk_mesh_blendshape=False)
    with open(os.path.join(OUT, "ek2lc_%s_artifact.asset" % key), "w") as f:
        f.write("""pdxmesh = {
	name = "ek2lc_%(k)s_artifact_mesh"
	file = "ek2lc_%(k)s_artifact.mesh"
	meshsettings = {
		name = "ek2lc_%(k)s_artifactShape"
		index = 0
		texture_diffuse = "%(t)s_display_diffuse.dds"
		texture_normal = "%(t)s_normal.dds"
		texture_specular = "%(t)s_properties.dds"
		shader = "court_alpha_to_coverage"
		shader_file = "gfx/FX/court_scene.shader"
	}
}

entity = {
	name = "ek2lc_%(k)s_artifact_entity"
	pdxmesh = "ek2lc_%(k)s_artifact_mesh"
}
""" % {"k": key, "t": tset})
    bpy.data.objects.remove(o, do_unlink=True)
    # tools/make_colour.py divides the worn piece's diffuse by its colour mask; the window's model keeps the original
    subprocess.run([MAGICK, os.path.join(TEXSRC, tset + "_diffuse.png"), "-define", "dds:compression=dxt5", "-define",
                    "dds:mipmaps=10", os.path.join(OUT, tset + "_display_diffuse.dds")], check=True)


BUILT = []
for key, fn in PIECES_R.items():
    if ONLY and key not in ONLY:
        continue
    t0 = time.time()
    tset = "ek2lc_%s_01" % key
    at = Atlas(tset)
    pc = Piece("ek2lc_%s_%s_01" % (S1, key), tset)
    fn(pc, at)
    if SEX == "male" or not os.path.exists(os.path.join(OUT, tset + "_diffuse.dds")):
        MATS[tset] = make_material(tset, save_set(tset, at.paint()))
    else:  # the female body shares the male build's textures
        imgs = {"diffuse": bpy.data.images.load(os.path.join(TEXSRC, tset + "_diffuse.png"))}
        MATS[tset] = make_material(tset, imgs)
    obj = finish_piece(pc.as_dict())
    BUILT.append(obj)
    if SEX == "male" and key.startswith("art_"):
        export_display(obj, key, tset)
    print("REGALIA %s: %d verts, %d faces in %.1fs" % (pc.name, len(pc.uvs), len(pc.faces), time.time() - t0))

body.hide_set(False)
for o in BUILT:
    o.hide_set(False)
print("DONE regalia %s in %.1fs" % (SEX, time.time() - T0))

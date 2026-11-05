"""Build the Reach hide loincloth for adult men (EK2 Loincloths).

Makes the mesh on CK3's vanilla male body (EK2 uses the same body mesh), its five
body-shape meshes (fat, gaunt, muscular, old, dwarf), the textures (PNG sources in
source/textures, DDS in the mod), the .asset file, a .blend and a small preview.

Pieces: a rawhide cord belt, a strip passing between the legs, and fringed hide
flaps hanging in front and behind.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python build_reach_hide_m.py -- "<CK3 game dir>" "<mod dir>"
"""
import bpy, bmesh, addon_utils, sys, os, math, subprocess, time
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

T0 = time.time()
argv = sys.argv[sys.argv.index("--") + 1:]
GAME, MOD = argv[0], argv[1]
MAGICK = "/opt/homebrew/bin/magick"

NAME = "ek2lc_m_reach_hide_01"
NODE = NAME + "Shape"  # mesh node name in the .mesh; the .asset meshsettings name must match
OUT = os.path.join(MOD, "gfx/models/portraits/ek2lc/m_reach_hide_01")
SRC = os.path.join(MOD, "source")
TEXSRC = os.path.join(SRC, "textures")
PREV = os.path.join(SRC, "preview")
for d in (OUT, TEXSRC, PREV):
    os.makedirs(d, exist_ok=True)

BODY_DIR = os.path.join(GAME, "gfx/models/portraits/male_body")
FIG_MESH = os.path.join(GAME, "gfx/models/portraits/m_clothes/western/nudity_01/m_clothes_secular_western_nudity_01.mesh")
SHAPES = ["fat", "gaunt", "muscular", "old", "dwarf"]
ALL = ["basis"] + SHAPES

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("bl_ext.user_default.io_pdx_mesh", default_set=True)
import bl_ext.user_default.io_pdx_mesh.pdx_blender.blender_import_export as pdx_io

scene = bpy.context.scene


def pdx_import(path, skel):
    before = set(bpy.data.objects)
    bpy.ops.io_pdx_mesh.import_mesh(filepath=path, chk_mesh=True, chk_skel=skel, chk_locs=False, chk_joinmats=True)
    return [o for o in bpy.data.objects if o not in before]


def world_coords(obj):
    M = obj.matrix_world
    return [M @ v.co for v in obj.data.vertices]


def drop(objs):
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)


# ------------------------------------------------------------------ body and its shapes
objs = pdx_import(os.path.join(BODY_DIR, "male_body.mesh"), True)
rig = next(o for o in objs if o.type == "ARMATURE")
body = next(o for o in objs if o.type == "MESH")
W = body.matrix_world.copy()
assert W == Matrix.Identity(4), "body has a transform; this script assumes it doesn't"
WI = W.inverted()

COORDS = {"basis": world_coords(body)}
for s in SHAPES:
    tmp = pdx_import(os.path.join(BODY_DIR, "blendshapes", "male_bs_body_%s_1.mesh" % s), False)
    m = next(o for o in tmp if o.type == "MESH")
    assert len(m.data.vertices) == len(body.data.vertices), s
    COORDS[s] = world_coords(m)
    drop(tmp)

# the body is split along UV seams: weld normals of vertices that share a position
_groups = {}
for i, c in enumerate(COORDS["basis"]):
    _groups.setdefault((round(c.x, 2), round(c.y, 2), round(c.z, 2)), []).append(i)
WELD = [g for g in _groups.values() if len(g) > 1]


def shape_data(cs):
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.verts.ensure_lookup_table()
    for v, c in zip(bm.verts, cs):
        v.co = c
    bm.normal_update()
    ns = [v.normal.copy() for v in bm.verts]
    for g in WELD:
        a = Vector()
        for i in g:
            a += ns[i]
        a.normalize()
        for i in g:
            ns[i] = a
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="FIXED", ngon_method="EAR_CLIP")
    bm.verts.index_update()
    bm.faces.index_update()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    tris = [[v.index for v in f.verts] for f in bm.faces]
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return ns, tris, bvh


NRM, TRIS, BVH = {}, {}, {}
for s in ALL:
    NRM[s], TRIS[s], BVH[s] = shape_data(COORDS[s])

C0 = COORDS["basis"]
feet = [c for c in C0 if c.z < 6]
FRONT = Vector((0, -1.0 if sum(c.y for c in feet) / len(feet) < 0 else 1.0, 0))
UP = Vector((0, 0, 1))
RIGHT = Vector((1, 0, 0))
HIP_Z = (rig.matrix_world @ rig.data.bones["body_root"].head_local).z
CROTCH_Z = min(c.z for c in C0 if abs(c.x) < 1.0 and 40 < c.z < HIP_Z + 5)
BELT_Z = HIP_Z + 6.0


def center_y(z, s="basis"):
    o = Vector((0, 0, z))
    f = BVH[s].ray_cast(o + FRONT * 200, -FRONT, 400)[0]
    b = BVH[s].ray_cast(o - FRONT * 200, FRONT, 400)[0]
    return (f.y + b.y) / 2


# fig leaf (drawn under "no clothes" when nudity is off): the loincloth must cover it
tmp = pdx_import(FIG_MESH, False)
_fo = next(o for o in tmp if o.type == "MESH")
FIG = world_coords(_fo)
_fb = bmesh.new()
_fb.from_mesh(_fo.data)
_fb.transform(_fo.matrix_world)
FIG_BVH = BVHTree.FromBMesh(_fb)
_fb.free()
drop(tmp)
FIG_D = max(BVH["basis"].find_nearest(p)[3] for p in FIG)
FIG_X = max(abs(p.x) for p in FIG)
FIG_Z = (min(p.z for p in FIG), max(p.z for p in FIG))
print("BODY front=%s hip_z=%.1f crotch_z=%.1f belt_z=%.1f | fig: dist=%.2f half_w=%.1f z=%.1f..%.1f"
      % (tuple(FRONT), HIP_Z, CROTCH_Z, BELT_Z, FIG_D, FIG_X, FIG_Z[0], FIG_Z[1]))


# ------------------------------------------------------------------ binding to the body surface
def bind(loc, fidx, off):
    tri = TRIS["basis"][fidx]
    return (tri, poly_3d_calc([C0[i] for i in tri], loc), off)


def recon(b, s):
    tri, w, off = b
    p, n = Vector(), Vector()
    for i, k in zip(tri, w):
        p += COORDS[s][i] * k
        n += NRM[s][i] * k
    return p + n.normalized() * off


# belt: a rounded rawhide cord around the hips (5 points per section)
NB = 40
BELT_ROWS = [(-1.7, 0.25), (-1.7, 1.1), (0.0, 1.5), (1.7, 1.1), (1.7, 0.25)]  # (height, offset from skin)
YC = {dz: center_y(BELT_Z + dz) for dz in (-1.7, 0.0, 1.7)}
belt_bind = []
for k in range(NB):
    th = 2 * math.pi * k / NB
    d = (-FRONT) * math.cos(th) + RIGHT * math.sin(th)  # k = 0 at the back
    for dz, off in BELT_ROWS:
        loc, nor, fi, dist = BVH["basis"].ray_cast(Vector((0, YC[dz], BELT_Z + dz)), d, 100)
        belt_bind.append(bind(loc, fi, off))

# strip between the legs, from under the belt in front, round the crotch, up to the belt behind
NS = 25
STRIP_COLS = [-1.0, -0.5, 0.0, 0.5, 1.0]
SC = len(STRIP_COLS)
STRIP_OFF = 0.5
W_FRONT, W_BACK, W_CROTCH = 8.0, 6.5, 4.5
P0 = Vector((0, center_y(HIP_Z), BELT_Z - 1.0))
strip_bind, strip_mid = [], []
for a_i in range(NS):
    al = math.radians(90 - 180 * a_i / (NS - 1))
    mid = BVH["basis"].ray_cast(P0, (-UP) * math.cos(al) + FRONT * math.sin(al), 100)[0]
    strip_mid.append(mid)
    out = (mid - P0).normalized()
    t = abs(math.degrees(al)) / 90.0
    w = W_CROTCH + ((W_FRONT if al > 0 else W_BACK) - W_CROTCH) * t ** 1.2
    if al >= 0:  # at least as wide as the fig leaf at this height, plus 1 cm
        fw = [abs(p.x) for p in FIG if abs(p.z - mid.z) < 1.5]
        w = max(w, max(fw) + 1.0) if fw else w
    for c in STRIP_COLS:
        loc, nor, fi, dist = BVH["basis"].find_nearest(mid + RIGHT * (c * w) + out * 0.5)
        strip_bind.append(bind(loc, fi, STRIP_OFF))

# over the fig leaf the strip becomes a pouch: lifted clear of the fig leaf, then smoothed
need = []
for tri, bary, off in strip_bind:
    s_ = recon((tri, bary, 0.0), "basis")
    n_ = recon((tri, bary, 1.0), "basis") - s_
    hit = FIG_BVH.ray_cast(s_ + n_ * 0.01, n_, 10)
    hit_ok = hit[0] is not None and hit[3] <= FIG_D + 0.3  # ignore glancing hits on the fig leaf's sides
    need.append(max(STRIP_OFF, hit[3] + 0.36) if hit_ok else STRIP_OFF)
# the fig leaf is slightly lopsided; lift both sides the same so the pouch stays symmetric
need = [max(need[a * SC + c], need[a * SC + SC - 1 - c]) for a in range(NS) for c in range(SC)]
offs = list(need)
for _ in range(3):
    blur = []
    for a in range(NS):
        for ci in range(SC):
            nb = [offs[aa * SC + cc] for aa in range(max(a - 1, 0), min(a + 2, NS))
                  for cc in range(max(ci - 1, 0), min(ci + 2, SC))]
            blur.append(sum(nb) / len(nb))
    offs = [max(n, b) for n, b in zip(need, blur)]
strip_bind = [(tri, bary, o) for (tri, bary, _), o in zip(strip_bind, offs)]
print("STRIP pouch max offset %.2f" % max(offs))

# belt and strip quads (indices into the belt+strip vertex list)
SURF_QUADS = [[k * 5 + r, (k + 1) % NB * 5 + r, (k + 1) % NB * 5 + r + 1, k * 5 + r + 1]
              for k in range(NB) for r in range(4)]
SURF_QUADS += [[NB * 5 + a * SC + c, NB * 5 + a * SC + c + 1, NB * 5 + (a + 1) * SC + c + 1, NB * 5 + (a + 1) * SC + c]
               for a in range(NS - 1) for c in range(SC - 1)]


def surface_parts(s):
    return [recon(b, s) for b in belt_bind] + [recon(b, s) for b in strip_bind]


# what the flaps must hang clear of: the body, the belt and the strip, per body shape
OBST = {}
for s in ALL:
    nb_ = len(COORDS[s])
    OBST[s] = BVHTree.FromPolygons(list(COORDS[s]) + surface_parts(s),
                                   [list(t) for t in TRIS[s]] + [[i + nb_ for i in q] for q in SURF_QUADS])

# flaps: stiff hide folded over the belt and hanging straight down, clear of everything behind
# the back flap is no wider and a bit shorter than the front one, so from the front it
# doesn't peek out between the legs below or beside the front flap
FLAPS = {+1: dict(w_top=20.0, w_bot=17.0, length=34.0), -1: dict(w_top=20.0, w_bot=17.0, length=31.0)}
FR, FC, THICK = 14, 7, 0.35
Z_ATTACH = BELT_Z + 1.9  # just above the belt
REF = {}
for side in (+1, -1):
    loc, nor, fi, dist = BVH["basis"].ray_cast(Vector((0, center_y(BELT_Z), BELT_Z)), FRONT * side, 100)
    REF[side] = bind(loc, fi, 0.0)


def flap_positions(s, side):
    sp, D = FLAPS[side], FRONT * side
    dz = (recon(REF[side], s) - recon(REF[side], "basis")).z
    za = Z_ATTACH + dz
    bvh = OBST[s]

    def most_out(x, z):
        hit = bvh.ray_cast(Vector((x, 0, z)) + D * 200, -D, 400)[0]
        return hit.dot(D) if hit is not None else -1e9

    outer = []
    for j in range(FR):
        t = j / (FR - 1)
        z = za - t * sp["length"]
        w = sp["w_top"] + (sp["w_bot"] - sp["w_top"]) * t
        clear = 0.55 + 0.95 * t
        hw = 0.6 + 1.4 * min(1.0, t * 3)  # narrow look-around at the top, wider lower down
        zs = np.arange(z, za + 0.51, 0.75)
        fs = []
        for i in range(FC):
            x = (i / (FC - 1) - 0.5) * w
            fs.append(max(most_out(x + dx, zz) for dx in (-hw, -hw / 2, 0, hw / 2, hw) for zz in zs) + clear)
        if t > 0.25:
            fs = [max(fs[i], (fs[max(i - 1, 0)] + 2 * fs[i] + fs[min(i + 1, FC - 1)]) / 4) for i in range(FC)]
        for i in range(FC):
            outer.append(Vector(((i / (FC - 1) - 0.5) * w, fs[i] * D.y, z)))
    return outer + [p - D * THICK for p in outer]


def positions(s):
    return surface_parts(s) + flap_positions(s, +1) + flap_positions(s, -1)


POS = {s: positions(s) for s in ALL}

# ------------------------------------------------------------------ topology and UVs
UVS, FACES, PART, WRAP = [], [], [], set()


def add_face(f, part, wrap=False):
    if wrap:
        WRAP.add(len(FACES))
    FACES.append(f)
    PART.append(part)


# texture atlas: belt v .88-.99, strip v .755-.87, front flap u .01-.49 / back flap u .51-.99 at v .01-.74
for k in range(NB):
    for r in range(5):
        UVS.append((k / NB, 0.88 + 0.11 * r / 4))
for k in range(NB):
    k2 = (k + 1) % NB
    for r in range(4):
        add_face([k * 5 + r, k2 * 5 + r, k2 * 5 + r + 1, k * 5 + r + 1], "belt", wrap=(k2 == 0))

base = len(UVS)
arc = [0.0]
for a in range(1, NS):
    arc.append(arc[-1] + (strip_mid[a] - strip_mid[a - 1]).length)
for a in range(NS):
    for ci in range(SC):
        UVS.append((0.01 + 0.98 * arc[a] / arc[-1], 0.755 + 0.115 * ci / (SC - 1)))
for a in range(NS - 1):
    for ci in range(SC - 1):
        i0 = base + a * SC + ci
        add_face([i0, i0 + 1, i0 + SC + 1, i0 + SC], "strip")


def add_flap(side, u0, u1):
    b0 = len(UVS)
    for layer in range(2):
        for j in range(FR):
            for i in range(FC):
                UVS.append((u0 + (u1 - u0) * i / (FC - 1), 0.74 - 0.73 * j / (FR - 1)))
    o = lambda j, i: b0 + j * FC + i
    n = lambda j, i: b0 + FR * FC + j * FC + i
    p = "flap%+d" % side
    for j in range(FR - 1):
        for i in range(FC - 1):
            add_face([o(j, i), o(j, i + 1), o(j + 1, i + 1), o(j + 1, i)], p + "o")
            add_face([n(j, i), n(j + 1, i), n(j + 1, i + 1), n(j, i + 1)], p + "i")
    for j in range(FR - 1):
        add_face([o(j, 0), o(j + 1, 0), n(j + 1, 0), n(j, 0)], p + "r")
        add_face([o(j, FC - 1), n(j, FC - 1), n(j + 1, FC - 1), o(j + 1, FC - 1)], p + "r")
    for i in range(FC - 1):
        add_face([o(0, i), n(0, i), n(0, i + 1), o(0, i + 1)], p + "r")
        add_face([o(FR - 1, i), o(FR - 1, i + 1), n(FR - 1, i + 1), n(FR - 1, i)], p + "r")


add_flap(+1, 0.01, 0.49)
add_flap(-1, 0.51, 0.99)
assert len(POS["basis"]) == len(UVS)

me = bpy.data.meshes.new(NODE)
me.from_pydata([WI @ p for p in POS["basis"]], [], FACES)
me.update()
bm = bmesh.new()
bm.from_mesh(me)
bm.faces.ensure_lookup_table()


def orient(prefix, expected, vote_prefix=None):
    fs = [f for f in bm.faces if PART[f.index].startswith(prefix)]
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    voters = [f for f in fs if PART[f.index].startswith(vote_prefix or prefix)]
    score = sum(f.normal.dot(expected(f.calc_center_median())) for f in voters)
    if score < 0:
        bmesh.ops.reverse_faces(bm, faces=fs)


orient("belt", lambda c: Vector((c.x, c.y - YC[0.0], 0)))
orient("strip", lambda c: c - P0)
orient("flap+1", lambda c: FRONT, "flap+1o")
orient("flap-1", lambda c: -FRONT, "flap-1o")
uvl = bm.loops.layers.uv.new("map1")
for f in bm.faces:
    for l in f.loops:
        u, v = UVS[l.vert.index]
        if f.index in WRAP and l.vert.index < 5:
            u = 1.0
        l[uvl].uv = (u, v)
    f.smooth = True
bm.to_mesh(me)
bm.free()
me.update()
FACES_FINAL = [list(p.vertices) for p in me.polygons]

# ------------------------------------------------------------------ skin weights (copied from the body)
VG = [g.name for g in body.vertex_groups]
BW = [{} for _ in body.data.vertices]
for v in body.data.vertices:
    for g in v.groups:
        if g.weight > 1e-4:
            BW[v.index][g.group] = g.weight


def weights_at(tri, bary):
    acc = {}
    for i, k in zip(tri, bary):
        for gi, w in BW[i].items():
            acc[gi] = acc.get(gi, 0.0) + w * k
    top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
    s = sum(w for _, w in top)
    top = [(gi, w / s) for gi, w in top if w / s > 0.02]
    s = sum(w for _, w in top)
    return [(gi, w / s) for gi, w in top]


VW = [weights_at(b[0], b[1]) for b in belt_bind + strip_bind]

# Flaps hang like stiff aprons: at the top they move with the belt, lower down they also follow
# the average of both thighs. Every column gets the same weights, so a pose with one leg forward
# can't twist or split the flap (copying each side's nearest thigh did exactly that).
GI = {n: i for i, n in enumerate(VG)}


def flap_weights(side):
    top = dict(weights_at(*REF[side][:2]))
    m = (top.get(GI["bn_l_hip"], 0.0) + top.get(GI["bn_r_hip"], 0.0)) / 2  # mirror-symmetric
    if m:
        top[GI["bn_l_hip"]] = top[GI["bn_r_hip"]] = m
    bottom = {GI["body_root"]: 0.4, GI["bn_l_hip"]: 0.3, GI["bn_r_hip"]: 0.3}
    rows = []
    for j in range(FR):
        s = (j / (FR - 1)) ** 1.5
        d = {}
        for k, w in top.items():
            d[k] = d.get(k, 0.0) + w * (1 - s)
        for k, w in bottom.items():
            d[k] = d.get(k, 0.0) + w * s
        row = [(k, w) for k, w in sorted(d.items(), key=lambda kv: -kv[1])[:4] if w > 0.01]
        tot = sum(w for _, w in row)
        rows.append([(k, w / tot) for k, w in row])
    return [rows[j] for layer in range(2) for j in range(FR) for i in range(FC)]


VW += flap_weights(+1) + flap_weights(-1)


# ------------------------------------------------------------------ textures
def make_textures():
    H = WD = 1024
    rng = np.random.default_rng(11)

    def vnoise(h, w, k):
        g = rng.random((k + 2, k + 2)).astype(np.float32)
        ys = np.linspace(0, k, h, endpoint=False)
        xs = np.linspace(0, k, w, endpoint=False)
        y0, x0 = ys.astype(np.int32), xs.astype(np.int32)
        fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
        a, b = g[np.ix_(y0, x0)], g[np.ix_(y0, x0 + 1)]
        c, d = g[np.ix_(y0 + 1, x0)], g[np.ix_(y0 + 1, x0 + 1)]
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

    def fbm(h, w, k, octaves=5):
        acc, amp, tot = np.zeros((h, w), np.float32), 1.0, 0.0
        for o in range(octaves):
            acc += amp * vnoise(h, w, k * 2 ** o)
            tot += amp
            amp *= 0.5
        return acc / tot

    img = np.ones((H, WD, 4), np.float32)
    hide = np.array([0.52, 0.37, 0.24], np.float32)
    n1, n2, n3, n4 = fbm(H, WD, 4), fbm(H, WD, 24, 3), fbm(H, WD, 6, 4), fbm(H, WD, 10, 3)
    img[..., :3] = hide * (0.78 + 0.34 * n1 + 0.12 * (n2 - 0.5))[..., None]
    img[..., :3] *= (1 - 0.2 * np.clip((n3 - 0.58) * 5, 0, 1))[..., None]  # darker patches
    img[..., :3] *= (1 - 0.25 * np.clip(1 - np.abs(n4 - 0.5) / 0.01, 0, 1))[..., None]  # creases

    def px(u, v):
        return int(round(u * WD)), int(round((1 - v) * H))

    def flap(u0, u1, v0, v1):
        x0, y0 = px(u0, v1)
        x1, y1 = px(u1, v0)
        sub = img[y0:y1, x0:x1]
        h, w = sub.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        fy = yy / (h - 1)
        edge = np.minimum(xx, w - 1 - xx)
        sub[..., :3] *= np.clip(0.70 + edge / 36.0, 0.70, 1.0)[..., None]  # darker cut edges
        hy = 0.095 * (h - 1)
        for cx in np.arange(14, w - 10, 28):  # lacing holes just below the belt
            sub[(xx - cx) ** 2 + (yy - hy) ** 2 < 3.5 ** 2, :3] *= 0.35
        wear = fbm(h, w, 14, 3)
        tri = np.abs((xx / (w / 7.0)) % 1.0 - 0.5) * 2.0
        for yc in (0.69, 0.735):  # worn ochre-red zig-zag band
            m = (np.abs(fy - (yc + (tri - 0.5) * 0.035)) * h < 3.2) & (wear > 0.32)
            sub[m, :3] = sub[m, :3] * 0.3 + np.array([0.50, 0.13, 0.08], np.float32) * 0.7
        slit_p = 22  # fringe: slits at the bottom, ragged ends
        sid = (xx // slit_p).astype(np.int32)
        rnd = np.random.default_rng(5).random(int(sid.max()) + 2).astype(np.float32)
        slit = ((xx % slit_p) < 4) & (fy > 0.86 + 0.03 * rnd[sid])
        end = fy > 0.975 + 0.02 * rnd[sid + 1]
        sub[..., 3] = np.where(slit | end, 0.0, 1.0)
        sub[..., :3] *= np.where(fy[..., None] > 0.9, 0.85, 1.0)

    flap(0.01, 0.49, 0.01, 0.74)
    flap(0.51, 0.99, 0.01, 0.74)
    x0, y0 = px(0.0, 0.875)
    x1, y1 = px(1.0, 0.75)
    sub = img[y0:y1, x0:x1]  # strip: a little darker, lengthwise folds
    yy = np.mgrid[0:sub.shape[0], 0:sub.shape[1]][0].astype(np.float32)
    sub[..., :3] *= (0.82 + 0.08 * np.sin(yy / sub.shape[0] * np.pi * 6))[..., None]
    x0, y0 = px(0.0, 1.0)
    x1, y1 = px(1.0, 0.875)
    sub = img[y0:y1, x0:x1]  # belt: twisted rawhide cord
    h, w = sub.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    fy = yy / (h - 1)
    twist = 0.5 + 0.5 * np.sin(2 * np.pi * (xx / w * 38 + fy * 1.2))
    sub[..., :3] = np.array([0.33, 0.22, 0.14], np.float32) * (0.55 + 0.5 * twist * (0.6 + 0.4 * np.sin(np.pi * fy) ** 0.6))[..., None]
    sub[..., 3] = 1.0
    normal = np.zeros((H, WD, 4), np.float32)
    normal[..., 0] = normal[..., 1] = normal[..., 3] = 0.5  # flat, in CK3's packed layout
    props = np.zeros((H, WD, 4), np.float32)
    props[..., 1], props[..., 3] = 0.22, 0.58  # same channels as vanilla's plain clothes
    return {"diffuse": np.clip(img, 0, 1), "normal": normal, "properties": props}


IMAGES = {}
for kind, arr in make_textures().items():
    png = os.path.join(TEXSRC, "%s_%s.png" % (NAME, kind))
    im = bpy.data.images.new("%s_%s" % (NAME, kind), arr.shape[1], arr.shape[0], alpha=True)
    im.pixels.foreach_set(np.ascontiguousarray(np.flipud(arr), dtype=np.float32).ravel())
    im.filepath_raw = png
    im.file_format = "PNG"
    im.save()
    IMAGES[kind] = im
    subprocess.run([MAGICK, png, "-define", "dds:compression=dxt5", "-define", "dds:mipmaps=10",
                    os.path.join(OUT, "%s_%s.dds" % (NAME, kind))], check=True)

# ------------------------------------------------------------------ material, object, export
mat = bpy.data.materials.new("ek2lc_reach_hide")
mat["shader"] = "portrait_attachment_alpha_to_coverage"
try:
    mat.use_nodes = True
except Exception:
    pass
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = IMAGES["diffuse"]
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
nt.nodes.active = tex

lo = bpy.data.objects.new(NAME, me)
scene.collection.objects.link(lo)
lo.matrix_world = W
me.materials.append(mat)
vgroups = {}
for vi, ws in enumerate(VW):
    for gi, w in ws:
        if VG[gi] not in vgroups:
            vgroups[VG[gi]] = lo.vertex_groups.new(name=VG[gi])
        vgroups[VG[gi]].add([vi], w, "REPLACE")
lo.modifiers.new("Armature", "ARMATURE").object = rig


def export(obj, path, as_bs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.io_pdx_mesh.export_mesh(filepath=path, chk_mesh=True, chk_skel=not as_bs, chk_locs=False,
                                     chk_selected=True, chk_mesh_blendshape=as_bs)


export(lo, os.path.join(OUT, NAME + ".mesh"), False)
uv_flat = np.empty(len(me.loops) * 2, np.float32)
me.uv_layers[0].data.foreach_get("uv", uv_flat)
counts = {}
for s in SHAPES:
    ms = bpy.data.meshes.new("bs_" + s)
    ms.from_pydata([WI @ p for p in POS[s]], [], FACES_FINAL)
    ms.update()
    ms.uv_layers.new(name="map1").data.foreach_set("uv", uv_flat)
    for p in ms.polygons:
        p.use_smooth = True
    ms.materials.append(mat)
    o = bpy.data.objects.new("bs_" + s, ms)
    scene.collection.objects.link(o)
    o.matrix_world = W
    me.name = "base_tmp"
    ms.name = NODE
    export(o, os.path.join(OUT, "%s_bs_%s.mesh" % (NAME, s)), True)
    try:
        nb = len(pdx_io.get_mesh_info(lo, 0, split_criteria=None, split_all=False, sort_vertices=True)[0]["p"]) // 3
        ns_ = len(pdx_io.get_mesh_info(o, 0, split_criteria=["id", "p", "uv"], split_all=False, sort_vertices=True)[0]["p"]) // 3
        counts[s] = (nb, ns_)
    except Exception as e:
        counts[s] = repr(e)[:120]
    ms.name = "bs_" + s
    me.name = NODE
    drop([o])
print("EXPORT vertex counts (base, shape):", counts)

bs_lines = "\n".join('\tblend_shape = { id = "%s_bs_%s"\ttype = "%s_bs_%s.mesh" }' % (NAME, s, NAME, s) for s in SHAPES)
attr_lines = "\n".join('\tattribute = { name = "bs_body_%s_1"\tblend_shape = "%s_bs_%s" }' % (s, NAME, s) for s in SHAPES)
with open(os.path.join(OUT, NAME + ".asset"), "w") as f:
    f.write(f"""pdxmesh = {{
	name = "{NAME}_mesh"
	file = "{NAME}.mesh"
{bs_lines}

	meshsettings = {{
		name = "{NODE}"
		index = 0
		texture_diffuse = "{NAME}_diffuse.dds"
		texture_normal = "{NAME}_normal.dds"
		texture_specular = "{NAME}_properties.dds"
		shader = "portrait_attachment_alpha_to_coverage"
		shader_file = "gfx/FX/jomini/portrait.shader"
	}}
}}

entity = {{
	name = "{NAME}_entity"
	pdxmesh = "{NAME}_mesh"
{attr_lines}
}}
""")

# poke-through check: loincloth points inside the body, per body shape
PARTS = [("belt", 0, NB * 5), ("strip", NB * 5, NB * 5 + NS * SC),
         ("front", NB * 5 + NS * SC, NB * 5 + NS * SC + 2 * FR * FC), ("back", NB * 5 + NS * SC + 2 * FR * FC, len(UVS))]
for s in ALL:
    row = []
    for pname, a, b in PARTS:
        inside, worst, wp = 0, 1e9, None
        for p in POS[s][a:b]:
            loc, nor, fi, d = BVH[s].find_nearest(p)
            sd = (p - loc).dot(nor)
            if sd < worst:
                worst, wp = sd, p
            inside += sd < 0
        row.append("%s %d/%.2f%s" % (pname, inside, worst, " @(%.0f,%.0f,%.0f)" % tuple(wp) if inside else ""))
    print("CLEARANCE %-8s" % s, " | ".join(row))
print("MESH verts=%d faces=%d groups=%d" % (len(me.vertices), len(me.polygons), len(lo.vertex_groups)))

# body shapes as shape keys on both, so the .blend shows the loincloth following them (export is done)
for obj, data in ((body, COORDS), (lo, POS)):
    obj.shape_key_add(name="Basis")
    for s in SHAPES:
        kb = obj.shape_key_add(name=s, from_mix=False)
        for i, c in enumerate(data[s]):
            kb.data[i].co = WI @ c
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SRC, "reach_hide_m_v01.blend"))


# ------------------------------------------------------------------ preview render (Blender, not the game)
def preview():
    try:
        scene.render.engine = "BLENDER_WORKBENCH"
    except TypeError as e:
        print("engine:", e)
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    world = bpy.data.worlds.new("bg")
    world.color = (0.16, 0.16, 0.18)
    scene.world = world
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 300, 420, 100
    skin = bpy.data.materials.new("preview_skin")
    skin.diffuse_color = (0.78, 0.6, 0.5, 1.0)
    body.data.materials.clear()
    body.data.materials.append(skin)
    green = bpy.data.materials.new("preview_fig")  # the fig leaf in bright green: it must not show
    green.diffuse_color = (0.1, 0.9, 0.1, 1.0)
    for o in pdx_import(FIG_MESH, False):
        if o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(green)
    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    cam.ortho_scale = 66
    co = bpy.data.objects.new("cam", cam)
    scene.collection.objects.link(co)
    scene.camera = co
    target = Vector((0, center_y(HIP_Z), 79))
    kb = body.data.shape_keys.key_blocks["fat"]
    kl = lo.data.shape_keys.key_blocks["fat"]
    shots = []
    for tag, ang, fat in (("front", 0, 0), ("side", 90, 0), ("back", 180, 0), ("fat", 25, 1)):
        kb.value = kl.value = fat
        a = math.radians(ang)
        co.location = target + (FRONT * math.cos(a) + RIGHT * math.sin(a)) * 300
        co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(PREV, "v_%s.png" % tag)
        bpy.ops.render.render(write_still=True)
        shots.append(scene.render.filepath)
    subprocess.run([MAGICK] + shots + ["+append", "-resize", "1000x", os.path.join(PREV, "preview.png")], check=True)


preview()
print("DONE in %.1fs" % (time.time() - T0))

"""Build the Reach hide loincloth for EK2 Loincloths, and for women the hide chest band.

Fits everything on CK3's vanilla bodies (EK2 uses the same body meshes) and rebuilds each
piece on every body shape, so the shapes match the body vertex for vertex. Exports the .mesh
files, the body-shape .mesh files, the .asset files, the shared textures (PNG sources in
source/textures, DDS in the mod), a .blend and a small preview.

Pieces: a rawhide cord belt, a strip passing between the legs (a pouch over the fig leaf),
fringed hide flaps tucked under the belt in front and behind, and for women a chest band
that bridges the cleavage like real cloth. A separate war piece (own texture set) adds a wide
hide girdle above the cord belt and teeth/claws on sinew cords at the hips.

Run once per body:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python build_reach_hide.py -- "<CK3 game dir>" "<mod dir>" male|female
"""
import bpy, bmesh, addon_utils, sys, os, math, subprocess, time
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
from mathutils.geometry import intersect_line_line_2d

T0 = time.time()
argv = sys.argv[sys.argv.index("--") + 1:]
GAME, MOD = argv[0], argv[1]
SEX = argv[2] if len(argv) > 2 else "male"
assert SEX in ("male", "female")
S1 = SEX[0]
MAGICK = "/opt/homebrew/bin/magick"

SET = "ek2lc_reach_hide_01"  # texture set shared by both bodies and the chest band
NAME = "ek2lc_%s_reach_hide_01" % S1
BAND = "ek2lc_f_reach_band_01"
OUT = os.path.join(MOD, "gfx/models/portraits/ek2lc/reach_hide_01")
SRC = os.path.join(MOD, "source")
TEXSRC = os.path.join(SRC, "textures")
PREV = os.path.join(SRC, "preview")
for d in (OUT, TEXSRC, PREV):
    os.makedirs(d, exist_ok=True)

BODY_DIR = os.path.join(GAME, "gfx/models/portraits/%s_body" % SEX)
FIG_MESH = os.path.join(GAME, "gfx/models/portraits/%s_clothes/western/nudity_01/%s_clothes_secular_western_nudity_01.mesh" % (S1, S1))
SHAPE_DEFS = [(s, "%s_bs_body_%s_1.mesh" % (SEX, s), "bs_body_%s_1" % s) for s in ("fat", "gaunt", "muscular", "old", "dwarf")]
if SEX == "female":
    SHAPE_DEFS += [("pregnant", "female_bs_body_pregnant_1.mesh", "bs_body_pregnant_1"),
                   ("breast_max", "female_bs_body_breast_size_max.mesh", "bs_body_breast_size_max"),
                   ("breast_min", "female_bs_body_breast_size_min.mesh", "bs_body_breast_size_min")]
SHAPES = [s for s, f, a in SHAPE_DEFS]
SHAPE_FILE = {s: f for s, f, a in SHAPE_DEFS}
SHAPE_ATTR = {s: a for s, f, a in SHAPE_DEFS}
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
objs = pdx_import(os.path.join(BODY_DIR, "%s_body.mesh" % SEX), True)
rig = next(o for o in objs if o.type == "ARMATURE")
body = next(o for o in objs if o.type == "MESH")
W = body.matrix_world.copy()
assert W == Matrix.Identity(4), "body has a transform; this script assumes it doesn't"
WI = W.inverted()

COORDS = {"basis": world_coords(body)}
for s in SHAPES:
    tmp = pdx_import(os.path.join(BODY_DIR, "blendshapes", SHAPE_FILE[s]), False)
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
FIG_ALL = world_coords(_fo)
_fb = bmesh.new()
_fb.from_mesh(_fo.data)
_fb.transform(_fo.matrix_world)
FIG_BVH = BVHTree.FromBMesh(_fb)
_fb.free()
drop(tmp)
FIG = [p for p in FIG_ALL if p.z < HIP_Z + 8]  # the part at the groin
FIG_CHEST = [p for p in FIG_ALL if p.z >= HIP_Z + 8]  # any part over the chest (women)
FIG_D = max(BVH["basis"].find_nearest(p)[3] for p in FIG)
FIG_X = max(abs(p.x) for p in FIG)
FIG_Z = (min(p.z for p in FIG), max(p.z for p in FIG))
print("BODY %s front=%s hip_z=%.1f crotch_z=%.1f belt_z=%.1f | fig: dist=%.2f half_w=%.1f z=%.1f..%.1f | chest part: %d pts%s"
      % (SEX, tuple(FRONT), HIP_Z, CROTCH_Z, BELT_Z, FIG_D, FIG_X, FIG_Z[0], FIG_Z[1], len(FIG_CHEST),
         " dist=%.2f z=%.1f..%.1f" % (max(BVH["basis"].find_nearest(p)[3] for p in FIG_CHEST),
                                      min(p.z for p in FIG_CHEST), max(p.z for p in FIG_CHEST)) if FIG_CHEST else ""))


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
BELT_ROWS = [(-1.7, 0.3), (-1.7, 1.4), (0.0, 1.9), (1.7, 1.4), (1.7, 0.3)]  # (height, offset from skin)
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
STRIP_OFF = 0.5  # more pushes it into the far side of the groin crease
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
    if al >= 0:  # at least as wide as the fig leaf at this height, plus 0.5 cm (more peeks out beside the front flap)
        fw = [abs(p.x) for p in FIG if abs(p.z - mid.z) < 1.5]
        w = max(w, max(fw) + 0.5) if fw else w
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


# what the flaps must hang clear of: the body and the strip, per body shape. Not the belt:
# the flaps tuck under it.
OBST = {}
for s in ALL:
    nb_ = len(COORDS[s])
    OBST[s] = BVHTree.FromPolygons(list(COORDS[s]) + surface_parts(s),
                                   [list(t) for t in TRIS[s]] + [[i + nb_ for i in q] for q in SURF_QUADS[NB * 4:]])

# flaps: stiff hide tucked under the belt (between belt and skin) and hanging straight down.
# Draped over the belt, their top edge got swallowed when the belly folds down in some poses.
# The back flap is no wider and a bit shorter than the front one, so from the front it
# doesn't peek out between the legs below or beside the front flap.
FLAPS = {+1: dict(w_top=20.0, w_bot=17.0, length=34.0), -1: dict(w_top=20.0, w_bot=17.0, length=31.0)}
FR, FC, THICK = 14, 7, 0.35
Z_ATTACH = BELT_Z + 0.9  # inside the belt band (belt spans BELT_Z +-1.7)
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
        clear = 0.45 + 1.05 * t  # top stays under the belt's outer surface (1.4 cm)
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

# ------------------------------------------------------------------ loincloth topology and UVs
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

# ------------------------------------------------------------------ skin weights (copied from the body)
VG = [g.name for g in body.vertex_groups]
GI = {n: i for i, n in enumerate(VG)}
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


def nearest_weights(p):
    loc, nor, fi, dist = BVH["basis"].find_nearest(p)
    tri = TRIS["basis"][fi]
    return weights_at(tri, poly_3d_calc([C0[k] for k in tri], loc))


def mirror_bone(gi):
    n = VG[gi].replace("bn_l_", "bn_X_").replace("bn_r_", "bn_l_").replace("bn_X_", "bn_r_")
    return GI.get(n, gi)


def skin_weights_at(x, z, side):
    D = FRONT * side
    loc, nor, fi, dist = BVH["basis"].ray_cast(Vector((x, 0, z)) + D * 200, -D, 400)
    tri = TRIS["basis"][fi]
    return dict(weights_at(tri, poly_3d_calc([C0[i] for i in tri], loc)))


# Flap weights. The top rows (under the belt) copy the skin behind them, as the belt does.
# Lower down they blend into one stiff-apron set (pelvis plus both thighs evenly), the same
# across the width, so a pose with one leg forward can't twist or split the flap. Below the
# belt the skin is sampled at belt height, so no thigh leaks in from one side. The right half
# mirrors the left, so both sides match exactly.
APRON = {GI["body_root"]: 0.4, GI["bn_l_hip"]: 0.3, GI["bn_r_hip"]: 0.3}


def apron_blend(t):
    u = min(1.0, max(0.0, (t - 0.15) / 0.3))
    return u * u * (3 - 2 * u)  # 0 = skin weights, 1 = apron weights


def flap_weights(side):
    sp = FLAPS[side]
    apron = APRON
    mid = (FC - 1) // 2
    b0 = NB * 5 + NS * SC + (0 if side == 1 else 2 * FR * FC)
    outer = POS["basis"][b0:b0 + FR * FC]
    grid = {}
    for j in range(FR):
        t = j / (FR - 1)
        z = Z_ATTACH - t * sp["length"]
        w = sp["w_top"] + (sp["w_bot"] - sp["w_top"]) * t
        s = apron_blend(t)
        for i in range(mid + 1):
            if j <= 1:  # under the belt: move with the skin right behind, as the belt does
                skin = dict(nearest_weights(outer[j * FC + i]))
            else:
                skin = skin_weights_at((i / (FC - 1) - 0.5) * w, max(z, BELT_Z - 1.7), side) if s < 1 else {}
            if i == mid:  # centre column: make it exactly symmetric
                sym = {}
                for k, v in skin.items():
                    sym[k] = sym.get(k, 0.0) + v / 2
                    sym[mirror_bone(k)] = sym.get(mirror_bone(k), 0.0) + v / 2
                skin = sym
            d = {}
            for k, v in skin.items():
                d[k] = d.get(k, 0.0) + v * (1 - s)
            for k, v in apron.items():
                d[k] = d.get(k, 0.0) + v * s
            row = [(k, v) for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:4] if v > 0.01]
            tot = sum(v for _, v in row)
            grid[(j, i)] = [(k, v / tot) for k, v in row]
        for i in range(mid + 1, FC):
            grid[(j, i)] = [(mirror_bone(k), v) for k, v in grid[(j, FC - 1 - i)]]
    return [grid[(j, i)] for layer in range(2) for j in range(FR) for i in range(FC)]


VW = [weights_at(b[0], b[1]) for b in belt_bind + strip_bind]

# The front of the strip hides behind the stiff front flap, but its sides sit on the groin
# crease and followed the thigh, so in the idles they slid up to 2.3 cm out beside the flap's
# edge (a dark bump on men). Its sides now blend into the flap's apron weights as the flap does
# at the same height, fading out towards the crotch, where the strip must follow the skin.
for a in range(NS // 2):
    fade = min(1.0, (NS // 2 - a) / 4.0)
    for ci, c in enumerate(STRIP_COLS):
        t = (Z_ATTACH - POS["basis"][NB * 5 + a * SC + ci].z) / FLAPS[1]["length"]
        k = abs(c) * fade * min(1.0, 2.5 * apron_blend(t))  # faster than the flap: its sides sample the skin at belt height
        if k <= 0:
            continue
        d = {}
        for g, w in VW[NB * 5 + a * SC + ci]:
            d[g] = d.get(g, 0.0) + w * (1 - k)
        for g, w in APRON.items():
            d[g] = d.get(g, 0.0) + w * k
        row = [(g, w) for g, w in sorted(d.items(), key=lambda kv: -kv[1])[:4] if w > 0.01]
        tot = sum(w for _, w in row)
        VW[NB * 5 + a * SC + ci] = [(g, w / tot) for g, w in row]
VW += flap_weights(+1) + flap_weights(-1)

PIECES = [dict(name=NAME, pos=POS, faces=FACES, part=PART, wrap=WRAP, wrap_u={i: 1.0 for i in range(5)}, uvs=UVS, vw=VW,
               orient=[("belt", lambda c: Vector((c.x, c.y - YC[0.0], 0)), None), ("strip", lambda c: c - P0, None),
                       ("flap+1", lambda c: FRONT, "flap+1o"), ("flap-1", lambda c: -FRONT, "flap-1o")])]


# ------------------------------------------------------------------ chest band (women)
def convex_hull_2d(pts):
    pts = sorted(set((round(p.x, 4), round(p.y, 4)) for p in pts))
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [Vector(p) for p in lower[:-1] + upper[:-1]]


def ray_to_hull(c, d, hull):
    far = c + d * 200
    for i in range(len(hull)):
        p = intersect_line_line_2d(c, far, hull[i], hull[(i + 1) % len(hull)])
        if p is not None:
            return (p - c).length
    return 0.0


if SEX == "female":
    best = None  # bust apex: the most forward point of the chest
    for zz in np.arange(HIP_Z + 15, HIP_Z + 60, 0.5):
        for xx in (6.0, 9.0, 12.0):
            hit = BVH["basis"].ray_cast(Vector((xx, 0, zz)) + FRONT * 200, -FRONT, 400)[0]
            if hit is not None and (best is None or hit.dot(FRONT) > best[0]):
                best = (hit.dot(FRONT), zz)
    APEX_Z = best[1]
    B_LO, B_HI = APEX_Z - 7.0, APEX_Z + 4.5  # top kept below the armpits: upper arms swing over it
    if FIG_CHEST:  # the nudity cover's chest part must end up under the band
        B_LO = min(B_LO, min(p.z for p in FIG_CHEST) - 1.0)
        B_HI = max(B_HI, max(p.z for p in FIG_CHEST) + 1.0)
    NBB, NRB = 48, 7
    loc, nor, fi, dist = BVH["basis"].ray_cast(Vector((0, 0, APEX_Z)) + FRONT * 200, -FRONT, 400)
    BREF = bind(loc, fi, 0.0)  # sternum at the apex height: the band moves up and down with it
    FIGC_BVH = FIG_BVH if FIG_CHEST else None
    print("BAND apex_z=%.1f rows %.1f..%.1f" % (APEX_Z, B_LO, B_HI))

    # The top edge dips under the armpits: level with the bust at the armpit, the torso's
    # slice takes in the upper arms, and the band wrapped round them and cut into the arms.
    BAND_DIP = 5.5
    BDIRS = [(-FRONT) * math.cos(2 * math.pi * k / NBB) + RIGHT * math.sin(2 * math.pi * k / NBB) for k in range(NBB)]  # k = 0 at the back
    BTOP = [B_HI - BAND_DIP * abs(math.sin(2 * math.pi * k / NBB)) ** 4 for k in range(NBB)]
    ARM_BONES = [GI[n] for n in VG if any(t in n for t in ("deltoid", "shoulder", "elbow", "forearm", "wrist", "fi_", "sleeve"))]
    # the arm itself; skin under the armpit is about half deltoid and still counts as torso
    ARM_V = {i for i, ws in enumerate(BW) if sum(ws.get(g, 0.0) for g in ARM_BONES) > 0.9}

    def band_slice(s, z):
        fy = BVH[s].ray_cast(Vector((0, 0, z)) + FRONT * 200, -FRONT, 400)[0]
        by = BVH[s].ray_cast(Vector((0, 0, z)) - FRONT * 200, FRONT, 400)[0]
        c = Vector((0, (fy.y + by.y) / 2, z))
        pts, arm = [], set()
        for k, d in enumerate(BDIRS):
            hit, nor, fi, dist = BVH[s].ray_cast(c, d, 100)
            if any(i in ARM_V for i in TRIS[s][fi]):
                arm.add(k)  # a slice shared with taller columns reaches the arms: keep them out
                continue
            pts.append(hit)
            if FIGC_BVH is not None and s == "basis":  # cover the nudity cover too
                fh = FIGC_BVH.ray_cast(c + d * (hit - c).length * 0.5, d, 30)[0]
                if fh is not None and abs(fh.z - z) < 1.0:
                    pts.append(fh)
        hull = convex_hull_2d(pts)  # bridges the cleavage like real cloth
        return c, [ray_to_hull(c.to_2d(), d.to_2d(), hull) for d in BDIRS], arm

    def band_positions(s):
        dz = (recon(BREF, s) - recon(BREF, "basis")).z
        cache, out, arm_hits = {}, [], 0
        for k in range(NBB):
            col = []
            for r in range(NRB):
                z = round(B_LO + (BTOP[k] - B_LO) * r / (NRB - 1) + dz, 3)
                if z not in cache:
                    cache[z] = band_slice(s, z)
                c, rad, arm = cache[z]
                arm_hits += k in arm
                col.append((c, rad[k]))
            d = BDIRS[k]
            out.append(col[0][0] + d * (col[0][1] + 0.35))  # inner edge, bottom
            for r, (c, rad) in enumerate(col):
                out.append(c + d * (rad + 1.0 + 0.2 * math.sin(math.pi * r / (NRB - 1))))  # thick hide
            out.append(col[-1][0] + d * (col[-1][1] + 0.35))  # inner edge, top
        if arm_hits:
            print("BAND WARNING %s: %d band points sit over arm skin" % (s, arm_hits))
        for i, p in enumerate(out):  # folds (fat bodies under the arms) can still dent the hull
            loc, nor, fi, dist = BVH[s].find_nearest(p)
            if (p - loc).dot(nor) < 0.25:
                out[i] = loc + nor * 0.25
        return out

    BPOS = {s: band_positions(s) for s in ALL}
    CPB = NRB + 2  # vertices per band column
    BUVS, BFACES, BPART, BWRAP = [], [], [], set()
    for k in range(NBB):
        for r in range(CPB):
            BUVS.append((0.01 + 0.98 * k / NBB, 0.755 + 0.115 * r / (CPB - 1)))  # plain hide (the strip's area)
    for k in range(NBB):
        k2 = (k + 1) % NBB
        for r in range(CPB - 1):
            if k2 == 0:
                BWRAP.add(len(BFACES))
            BFACES.append([k * CPB + r, k2 * CPB + r, k2 * CPB + r + 1, k * CPB + r + 1])
            BPART.append("band")
    BVW = [nearest_weights(p) for p in BPOS["basis"]]
    BAND_YC = sum(p.y for p in BPOS["basis"]) / len(BPOS["basis"])
    PIECES.append(dict(name=BAND, pos=BPOS, faces=BFACES, part=BPART, wrap=BWRAP, wrap_u={i: 0.99 for i in range(CPB)},
                       uvs=BUVS, vw=BVW, orient=[("band", lambda c: Vector((c.x, c.y - BAND_YC, 0)), None)]))


# ------------------------------------------------------------------ war girdle and trophies (both bodies)
# A wide, thick hide girdle at the waist just above the cord belt, and at each hip five
# trophies on sinew cords (bone bead + tooth or claw). The trophies hang at the sides only,
# clear of the flaps; their cords pass over the cord belt.
WAR = "ek2lc_%s_reach_war_01" % S1
WSET = "ek2lc_reach_war_01"
NW = 48
G_ROWS = [(2.1, 0.3), (2.1, 0.9), (4.5, 1.15), (7.0, 0.9), (7.0, 0.3)]  # (height above BELT_Z, offset from skin)


def skin_bind(th, z, off):
    """Bind a point to the skin at height z, angle th from the front (+ towards +x)."""
    d = FRONT * math.cos(th) + RIGHT * math.sin(th)
    loc, nor, fi, dist = BVH["basis"].ray_cast(Vector((0, center_y(z), z)), d, 100)
    return bind(loc, fi, off)


war_bind, WUVS, WFACES, WPART, WWRAP = [], [], [], [], set()
for k in range(NW):
    th = math.pi - 2 * math.pi * k / NW  # k = 0 at the back, like the cord belt
    for r, (dz, off) in enumerate(G_ROWS):
        war_bind.append(skin_bind(th, BELT_Z + dz, off))
        WUVS.append((k / NW, 0.52 + 0.46 * r / (len(G_ROWS) - 1)))
for k in range(NW):
    k2 = (k + 1) % NW
    for r in range(len(G_ROWS) - 1):
        if k2 == 0:
            WWRAP.add(len(WFACES))
        WFACES.append([k * 5 + r, k2 * 5 + r, k2 * 5 + r + 1, k * 5 + r + 1])
        WPART.append("girdle")


def add_tube(th0, path, radii, flat, uv_box, part, cap_tip=False):
    """A closed tube along path (local (c, z, o): sideways cm, height, offset from skin)."""
    R0 = (recon(skin_bind(th0, path[0][1], 0.0), "basis") - Vector((0, center_y(path[0][1]), path[0][1]))).length
    NSEG = 6
    b0 = len(war_bind)
    pts = [Vector(p) for p in path]
    n = len(pts) - (1 if cap_tip else 0)
    for i in range(n):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        u = t.cross(Vector((1, 0, 0))).normalized()  # towards the offset axis
        v = t.cross(u)
        for j in range(NSEG):
            a = 2 * math.pi * j / NSEG
            q = pts[i] + u * (math.cos(a) * radii[i] * flat) + v * (math.sin(a) * radii[i])
            war_bind.append(skin_bind(th0 + q.x / R0, q.y, q.z))  # local (c, z, o) in x, y, z
            WUVS.append((uv_box[0] + (uv_box[2] - uv_box[0]) * j / NSEG, uv_box[1] + (uv_box[3] - uv_box[1]) * i / (len(pts) - 1)))
    for i in range(n - 1):
        for j in range(NSEG):
            j2 = (j + 1) % NSEG
            WFACES.append([b0 + i * NSEG + j, b0 + i * NSEG + j2, b0 + (i + 1) * NSEG + j2, b0 + (i + 1) * NSEG + j])
            WPART.append(part)
    for j in range(1, NSEG - 1):  # cap at the start (triangles: the exporter needs no n-gons)
        WFACES.append([b0, b0 + j, b0 + j + 1])
        WPART.append(part)
    if cap_tip:  # a point at the end
        tip = len(war_bind)
        war_bind.append(skin_bind(th0 + pts[-1].x / R0, pts[-1].y, pts[-1].z))
        WUVS.append(((uv_box[0] + uv_box[2]) / 2, uv_box[3]))
        for j in range(NSEG):
            WFACES.append([b0 + (n - 1) * NSEG + j, b0 + (n - 1) * NSEG + (j + 1) % NSEG, tip])
            WPART.append(part)
    else:
        e0 = b0 + (n - 1) * NSEG
        for j in range(1, NSEG - 1):
            WFACES.append([e0, e0 + j, e0 + j + 1])
            WPART.append(part)


BONE_UV, CLAW_UV, CORD_UV = (0.03, 0.03, 0.47, 0.47), (0.53, 0.03, 0.97, 0.22), (0.53, 0.28, 0.97, 0.47)
TROPHIES = [(62, "tooth", 3.4), (76, "claw", 3.6), (90, "tooth", 4.4), (104, "claw", 3.6), (118, "tooth", 3.4)]
ti = 0
for side in (1, -1):
    for ang, kind, length in TROPHIES:
        th0 = side * math.radians(ang)
        bt, bb = BELT_Z - 2.3, BELT_Z - 3.3  # bone bead
        add_tube(th0, [(0, BELT_Z + 3.0, 0.6), (0, BELT_Z + 1.9, 2.4), (0, BELT_Z - 1.9, 2.4), (0, bt, 1.6)],
                 [0.14] * 4, 1.0, CORD_UV, "t%02dc" % ti)
        add_tube(th0, [(0, bt, 1.6), (0, (bt + bb) / 2, 1.6), (0, bb, 1.6)], [0.42, 0.55, 0.42], 1.0, BONE_UV, "t%02db" % ti)
        if kind == "tooth":
            path = [(0, bb, 1.4), (0, bb - length * 0.35, 1.35), (0, bb - length * 0.7, 1.2), (0, bb - length, 1.0)]
            add_tube(th0, path, [0.45, 0.42, 0.26, 0], 0.6, BONE_UV, "t%02dt" % ti, cap_tip=True)
        else:  # claw: curls outwards at the tip
            path = [(0, bb, 1.4), (0, bb - length * 0.4, 1.55), (0, bb - length * 0.75, 1.95), (0, bb - length, 2.6)]
            add_tube(th0, path, [0.4, 0.34, 0.2, 0], 0.55, CLAW_UV, "t%02dt" % ti, cap_tip=True)
        ti += 1

WPOS = {s: [recon(b, s) for b in war_bind] for s in ALL}
WVW = [weights_at(b[0], b[1]) for b in war_bind]
W_YC = center_y(BELT_Z + 4.5)
_wctr = {}
for f, p in zip(WFACES, WPART):
    _wctr.setdefault(p, []).extend(WPOS["basis"][i] for i in f)
W_ORIENT = [("girdle", lambda c: Vector((c.x, c.y - W_YC, 0)), None)]
for p, ps in _wctr.items():
    if p != "girdle":
        W_ORIENT.append((p, (lambda ctr: (lambda c: c - ctr))(sum(ps, Vector()) / len(ps)), None))
PIECES.append(dict(name=WAR, set=WSET, pos=WPOS, faces=WFACES, part=WPART, wrap=WWRAP, wrap_u={i: 1.0 for i in range(5)},
                   uvs=WUVS, vw=WVW, orient=W_ORIENT))
print("WAR %d vertices, %d trophies" % (len(war_bind), ti))


# ------------------------------------------------------------------ textures (shared by every piece)
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
    sub = img[y0:y1, x0:x1]  # strip and chest band: a little darker, lengthwise folds
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


def make_war_textures():
    """Smoked hide girdle with ochre war marks and painted bone beads; bone, claw, sinew."""
    H = WD = 512
    rng = np.random.default_rng(23)

    def noise(k):
        g = rng.random((k + 2, k + 2)).astype(np.float32)
        ys = np.linspace(0, k, H, endpoint=False)
        y0 = ys.astype(np.int32)
        f = (ys - y0) * (ys - y0) * (3 - 2 * (ys - y0))
        a, b, c, d = g[np.ix_(y0, y0)], g[np.ix_(y0, y0 + 1)], g[np.ix_(y0 + 1, y0)], g[np.ix_(y0 + 1, y0 + 1)]
        fx, fy = f[None, :], f[:, None]
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

    n = (noise(6) + 0.5 * noise(24) + 0.25 * noise(64)) / 1.75
    img = np.ones((H, WD, 4), np.float32)
    yy, xx = np.mgrid[0:H, 0:WD].astype(np.float32)
    v = 1 - yy / (H - 1)
    u = xx / (WD - 1)
    # girdle (v .5-1): smoked hide
    g = v >= 0.5
    img[g, :3] = np.array([0.27, 0.18, 0.11], np.float32) * (0.75 + 0.5 * n[g])[:, None]
    gv = (v - 0.52) / 0.46  # 0 inner bottom .. 1 inner top
    for lv in (0.2, 0.8):  # stitching just inside the edges
        m = g & (np.abs(gv - lv) < 0.012) & ((xx % 10) < 5)
        img[m, :3] = np.array([0.62, 0.52, 0.38], np.float32)
    tri = np.abs((u * 24) % 1.0 - 0.5) * 2.0  # ochre zig-zag across the middle
    m = g & (np.abs(gv - (0.5 + (tri - 0.5) * 0.22)) < 0.035) & (n > 0.3)
    img[m, :3] = img[m, :3] * 0.25 + np.array([0.55, 0.12, 0.07], np.float32) * 0.75
    for lv in (0.31, 0.69):  # rows of painted bone beads
        cx = (np.floor(u * 48) + 0.5) / 48
        m = g & (((u - cx) * WD) ** 2 + ((gv - lv) * 0.46 * H) ** 2 < 4.2 ** 2)
        img[m, :3] = np.array([0.82, 0.77, 0.64], np.float32) * (0.85 + 0.15 * n[m])[:, None]
    # bone (u < .5, v < .5): ivory, darker towards the tips
    b = (u < 0.5) & (v < 0.5)
    img[b, :3] = np.array([0.84, 0.79, 0.66], np.float32) * (0.8 + 0.25 * n[b] - 0.25 * (v[b] / 0.5) ** 3)[:, None]
    # claw (u > .5, v < .25): dark horn
    c = (u >= 0.5) & (v < 0.25)
    img[c, :3] = np.array([0.16, 0.13, 0.10], np.float32) * (0.8 + 0.4 * n[c])[:, None]
    # sinew cord (u > .5, .25 < v < .5)
    s = (u >= 0.5) & (v >= 0.25) & (v < 0.5)
    img[s, :3] = np.array([0.55, 0.44, 0.30], np.float32) * (0.7 + 0.3 * np.sin(xx[s] * 0.9 + yy[s] * 0.6))[:, None]
    normal = np.zeros((H, WD, 4), np.float32)
    normal[..., 0] = normal[..., 1] = normal[..., 3] = 0.5
    props = np.zeros((H, WD, 4), np.float32)
    props[..., 1], props[..., 3] = 0.22, 0.58
    props[(v < 0.5), 1] = 0.35  # bone and horn a little shinier
    return {"diffuse": np.clip(img, 0, 1), "normal": normal, "properties": props}


def save_set(set_name, arrays):
    images = {}
    for kind, arr in arrays.items():
        png = os.path.join(TEXSRC, "%s_%s.png" % (set_name, kind))
        im = bpy.data.images.new("%s_%s" % (set_name, kind), arr.shape[1], arr.shape[0], alpha=True)
        im.pixels.foreach_set(np.ascontiguousarray(np.flipud(arr), dtype=np.float32).ravel())
        im.filepath_raw = png
        im.file_format = "PNG"
        im.save()
        images[kind] = im
        mips = int(math.log2(arr.shape[0]))  # 10 for 1024, as before
        subprocess.run([MAGICK, png, "-define", "dds:compression=dxt5", "-define", "dds:mipmaps=%d" % mips,
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
    nt.nodes.active = tex
    return m


MATS = {SET: make_material("ek2lc_reach_hide", save_set(SET, make_textures())),
        WSET: make_material("ek2lc_reach_war", save_set(WSET, make_war_textures()))}


# ------------------------------------------------------------------ make, export and check every piece
def export(obj, path, as_bs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.io_pdx_mesh.export_mesh(filepath=path, chk_mesh=True, chk_skel=not as_bs, chk_locs=False,
                                     chk_selected=True, chk_mesh_blendshape=as_bs)


def finish_piece(pc):
    name, node = pc["name"], pc["name"] + "Shape"  # mesh node name in the .mesh = meshsettings name
    tset = pc.get("set", SET)
    mat = MATS[tset]
    me = bpy.data.meshes.new(node)
    me.from_pydata([WI @ p for p in pc["pos"]["basis"]], [], pc["faces"])
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    for prefix, expected, vote in pc["orient"]:
        fs = [f for f in bm.faces if pc["part"][f.index].startswith(prefix)]
        bmesh.ops.recalc_face_normals(bm, faces=fs)
        voters = [f for f in fs if pc["part"][f.index].startswith(vote or prefix)]
        if sum(f.normal.dot(expected(f.calc_center_median())) for f in voters) < 0:
            bmesh.ops.reverse_faces(bm, faces=fs)
    uvl = bm.loops.layers.uv.new("map1")
    for f in bm.faces:
        for l in f.loops:
            u, v = pc["uvs"][l.vert.index]
            if f.index in pc["wrap"] and l.vert.index in pc["wrap_u"]:
                u = pc["wrap_u"][l.vert.index]
            l[uvl].uv = (u, v)
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    me.update()
    faces_final = [list(p.vertices) for p in me.polygons]
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.matrix_world = W
    me.materials.append(mat)
    vgroups = {}
    for vi, ws in enumerate(pc["vw"]):
        for gi, w in ws:
            if VG[gi] not in vgroups:
                vgroups[VG[gi]] = obj.vertex_groups.new(name=VG[gi])
            vgroups[VG[gi]].add([vi], w, "REPLACE")
    obj.modifiers.new("Armature", "ARMATURE").object = rig
    export(obj, os.path.join(OUT, name + ".mesh"), False)
    uv_flat = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[0].data.foreach_get("uv", uv_flat)
    counts = {}
    for s in SHAPES:
        ms = bpy.data.meshes.new("bs_" + s)
        ms.from_pydata([WI @ p for p in pc["pos"][s]], [], faces_final)
        ms.update()
        ms.uv_layers.new(name="map1").data.foreach_set("uv", uv_flat)
        for p in ms.polygons:
            p.use_smooth = True
        ms.materials.append(mat)
        o = bpy.data.objects.new("bs_" + s, ms)
        scene.collection.objects.link(o)
        o.matrix_world = W
        me.name = "base_tmp"
        ms.name = node
        export(o, os.path.join(OUT, "%s_bs_%s.mesh" % (name, s)), True)
        try:
            nb = len(pdx_io.get_mesh_info(obj, 0, split_criteria=None, split_all=False, sort_vertices=True)[0]["p"]) // 3
            ns_ = len(pdx_io.get_mesh_info(o, 0, split_criteria=["id", "p", "uv"], split_all=False, sort_vertices=True)[0]["p"]) // 3
            counts[s] = (nb, ns_)
        except Exception as e:
            counts[s] = repr(e)[:120]
        ms.name = "bs_" + s
        me.name = node
        drop([o])
    print("EXPORT %s vertex counts (base, shape): %s" % (name, counts))
    bs_lines = "\n".join('\tblend_shape = { id = "%s_bs_%s"\ttype = "%s_bs_%s.mesh" }' % (name, s, name, s) for s in SHAPES)
    attr_lines = "\n".join('\tattribute = { name = "%s"\tblend_shape = "%s_bs_%s" }' % (SHAPE_ATTR[s], name, s) for s in SHAPES)
    with open(os.path.join(OUT, name + ".asset"), "w") as f:
        f.write(f"""pdxmesh = {{
	name = "{name}_mesh"
	file = "{name}.mesh"
{bs_lines}

	meshsettings = {{
		name = "{node}"
		index = 0
		texture_diffuse = "{tset}_diffuse.dds"
		texture_normal = "{tset}_normal.dds"
		texture_specular = "{tset}_properties.dds"
		shader = "portrait_attachment_alpha_to_coverage"
		shader_file = "gfx/FX/jomini/portrait.shader"
	}}
}}

entity = {{
	name = "{name}_entity"
	pdxmesh = "{name}_mesh"
{attr_lines}
}}
""")
    for s in ALL:  # poke-through check: points inside the body, per body shape
        inside, worst = 0, 1e9
        for p in pc["pos"][s]:
            loc, nor, fi, d = BVH[s].find_nearest(p)
            sd = (p - loc).dot(nor)
            worst = min(worst, sd)
            inside += sd < 0
        print("CLEARANCE %s %-10s inside=%d min=%.2f" % (name, s, inside, worst))
    return obj


OBJS = [finish_piece(pc) for pc in PIECES]

# body shapes as shape keys, so the .blend shows the pieces following them (export is done)
for obj, data in [(body, COORDS)] + [(o, pc["pos"]) for o, pc in zip(OBJS, PIECES)]:
    obj.shape_key_add(name="Basis")
    for s in SHAPES:
        kb = obj.shape_key_add(name=s, from_mix=False)
        for i, c in enumerate(data[s]):
            kb.data[i].co = WI @ c
        kb.value = 0.0  # new keys start at 1.0 in this Blender; all on at once is a body the game never makes
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SRC, "reach_hide_%s_v01.blend" % S1))


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
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 300, 520, 100
    skin = bpy.data.materials.new("preview_skin")
    skin.diffuse_color = (0.78, 0.6, 0.5, 1.0)
    body.data.materials.clear()
    body.data.materials.append(skin)
    green = bpy.data.materials.new("preview_fig")  # the nudity cover in bright green: it must not show
    green.diffuse_color = (0.1, 0.9, 0.1, 1.0)
    for o in pdx_import(FIG_MESH, False):
        if o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(green)
    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    cam.ortho_scale = 80 if SEX == "female" else 66
    co = bpy.data.objects.new("cam", cam)
    scene.collection.objects.link(co)
    scene.camera = co
    target = Vector((0, center_y(HIP_Z), 90 if SEX == "female" else 79))
    extra = "pregnant" if SEX == "female" else "fat"
    keys = [o.data.shape_keys.key_blocks[extra] for o in [body] + OBJS]
    shots = []
    for tag, ang, on in (("front", 0, 0), ("side", 90, 0), ("back", 180, 0), (extra, 25, 1)):
        for kb in keys:
            kb.value = on
        a = math.radians(ang)
        co.location = target + (FRONT * math.cos(a) + RIGHT * math.sin(a)) * 300
        co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(PREV, "v_%s_%s.png" % (S1, tag))
        bpy.ops.render.render(write_still=True)
        shots.append(scene.render.filepath)
    subprocess.run([MAGICK] + shots + ["+append", "-resize", "1000x", os.path.join(PREV, "preview_%s.png" % S1)], check=True)


preview()
print("DONE %s in %.1fs" % (SEX, time.time() - T0))

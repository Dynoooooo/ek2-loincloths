"""Build the Reach hide loincloth for EK2 Loincloths, and for women the hide chest band.

Fits everything on CK3's vanilla bodies (EK2 uses the same body meshes) and rebuilds each
piece on every body shape, so the shapes match the body vertex for vertex. Exports the .mesh
files, the body-shape .mesh files, the .asset files, the shared textures (PNG sources in
source/textures, DDS in the mod), a .blend and a small preview.

Pieces: a rawhide cord belt, a strip passing between the legs (a pouch over the fig leaf),
fringed hide flaps tucked under the belt in front and behind, and for women a chest band
that bridges the cleavage like real cloth. A separate war piece (own texture set) adds a wide
hide girdle above the cord belt and teeth/claws on sinew cords at the hips. Culture variants
(cultures.py) and EK2's undead (undead.py: lich's burial regalia, rotted grave wraps) reuse the
meshes with their own diffuse textures.

Run once per body, in the Blender app (the user's rule: the app, not headless), through MCP for Blender:
  source/tools/build_in_app.py starts it there (it sets sys.argv as below and runs this file).
Headless, only when the brief's conditions for it hold:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python build_reach_hide.py -- "<CK3 game dir>" "<mod dir>" male|female
In the app the build clears the open file's data (not a factory reset, which would unload the MCP
add-on), skips the preview renders (look at the pieces in the viewport instead) and leaves the
finished pieces in the scene.
"""
import bpy, bmesh, addon_utils, sys, os, math, subprocess, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cultures import ROLES, CULTURES, KINDS, TEX_OF, LICH
import colour
import undead
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
# Children: CK3's boy and girl bodies are these same meshes with the infant shape (plus shorter bones),
# so this one shape makes every piece child-sized.
SHAPE_DEFS += [("infant", "%s_bs_body_infant%s.mesh" % (SEX, "_1" if SEX == "female" else ""), "bs_body_infant_1")]
# EK2's beast-race body shapes (read from EK2, never copied): the Khajiit body, and the digitigrade
# legs of Argonians (all of them) and of Lilmothiit. A full path wins over BODY_DIR in os.path.join.
# Also EK2's draugr body (its undead, driven by var:ek_undead_decay). EK2's draugr gene also drives
# bs_gaunt_body and bs_old, but those are head shapes only, and bs_body_gaunt_1 is "gaunt" above.
EK2 = os.path.normpath(os.path.join(GAME, "../../../workshop/content/1158310/2887120253"))
EK2_BS = os.path.join(EK2, "gfx/models/portraits/%s_body/blendshapes" % SEX)
SHAPE_DEFS += [("khajiit", os.path.join(EK2_BS, "%s_khajiit_body.mesh" % SEX), "bs_khajiit_body"),
               ("argdigi", os.path.join(EK2_BS, "%s_argonian_digitigrade_bs.mesh" % SEX), "argonian_digitigrade_bs"),
               ("khadigi", os.path.join(EK2_BS, "%s_khajiit_digitigrade_bs.mesh" % SEX), "khajiit_digitigrade_bs"),
               ("draugr", os.path.join(EK2_BS, "%s_draugr_body.mesh" % SEX), "bs_draugr_body")]
SHAPES =[s for s, f, a in SHAPE_DEFS]
SHAPE_FILE = {s: f for s, f, a in SHAPE_DEFS}
SHAPE_ATTR = {s: a for s, f, a in SHAPE_DEFS}
ALL = ["basis"] + SHAPES

GUI = not bpy.app.background
if GUI:  # the live app: empty this file but keep the add-ons (MCP for Blender's server is one)
    if bpy.context.window:
        bpy.context.window.scene = bpy.data.scenes[0]
    for _sc in list(bpy.data.scenes)[1:]:
        bpy.data.scenes.remove(_sc)
    for _coll in (bpy.data.objects, bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.actions,
                  bpy.data.cameras, bpy.data.lights, bpy.data.collections):
        bpy.data.batch_remove(list(_coll))
    bpy.data.batch_remove([_im for _im in bpy.data.images if _im.type == "IMAGE"])
else:
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
    strip = [recon(b, s) for b in strip_bind]
    if s in ("khadigi", "infant", "dwarf"):
        # The Lilmothiit groin (and, slightly, a child's and a dwarf's) folds past a few barycentrically reconstructed strip points.
        for i, p in enumerate(strip):
            loc, nor, fi, d = BVH[s].find_nearest(p)
            if (p - loc).dot(nor) < 0:
                q = loc + nor * 0.15
                loc, nor, fi, d = BVH[s].find_nearest(q)
                if (q - loc).dot(nor) < 0:
                    # A folded crease's normal can point into its opposite wall; clear it from below.
                    hit = BVH[s].ray_cast(p - UP * 5, UP, 10)[0]
                    assert hit is not None, "Cannot clear the groin fold on shape " + s
                    q = hit - UP * 0.15
                strip[i] = q
    return [recon(b, s) for b in belt_bind] + strip


# ------------------------------------------------------------------ hide leggings (the cold layer; built first)
# Rebuilt 2026-11-07: the old ones were the leg's own skin lifted 0.3 cm, so in game they read as brown skin, and
# their top edge followed the body's triangles in steps. Now each leg is a tube of smoked hide built on its own
# rings round the leg: snug on the thigh, easing below the knee, loose round the shin and flaring a little over
# the ankle; cut high at the outer hip and low on the inner thigh (real leggings tie to the belt at the hip and
# pass under the breechcloth), with a thick rolled top hem and a bottom cuff. Two layers, so the hems show their
# thickness. The rings are bound to the skin, so they follow every body shape as the belt does.
# Every other piece is built after them and hangs clear of them, worn or not (flaps, aprons, strips, skirts,
# tails, trophies, charms), so nothing cuts through them.
LEGG, LEGSET = "ek2lc_%s_leggings_01" % S1, "ek2lc_leggings_01"
_KNEE = rig.matrix_world @ rig.data.bones["bn_l_knee"].head_local
_ANKLE = rig.matrix_world @ rig.data.bones["bn_l_ankle"].head_local
_LSIDE = 1 if (rig.matrix_world @ rig.data.bones["bn_l_hip"].head_local).x > 0 else -1  # bn_l_* is on this side of x
_ARMG0 = {g.index for g in body.vertex_groups if any(k in g.name for k in ("clavicle", "shoulder", "elbow", "forearm", "wrist",
                                                                           "_fi_", "prop", "sleeve", "deltoid"))}
_ARMV0 = {v.index for v in body.data.vertices if sum(g.weight for g in v.groups if g.group in _ARMG0) > 0.5}
_LEG_T = [list(t) for t in TRIS["basis"] if not _ARMV0.intersection(t)]
_LEG_BVH = BVHTree.FromPolygons(C0, _LEG_T)
_LBIN = {}
for i, c in enumerate(C0):
    if i not in _ARMV0 and c.z <= CROTCH_Z and abs(c.x) > 0.3:
        _LBIN.setdefault((1 if c.x > 0 else -1, int(round(c.z))), []).append(c)


def leg_axis(z, side):
    """Centre of one leg's cross-section at height z (frozen 3 cm under the crotch, for the hip above it)."""
    zb = int(round(min(z, CROTCH_Z - 3.0)))
    for r in range(1, 8):  # the legs are low-poly: widen the window until it holds a ring of vertices
        ps = [c for dz in range(-r, r + 1) for c in _LBIN.get((side, zb + dz), [])]
        if len(ps) >= 6:
            break
    return Vector((sum(c.x for c in ps) / len(ps), sum(c.y for c in ps) / len(ps), 0))


L_NC, L_NR = 24, 27  # columns round each leg, rows up it
L_BOT = _ANKLE.z + 1.0  # the cuff's lower edge, just over the ankle bone
L_HI = HIP_Z - 2.0  # the top at the outer side, on the thigh below the hip's curve (higher, its hem folded over
#                     the curve of a woman's hip in Blender, 2026-11-07)
L_LO = CROTCH_Z - 4.5  # the top on the inner thigh, under the loincloth's strip
L_V = [0.0, 0.012, 0.035] + [0.035 + (0.955 - 0.035) * k / (L_NR - 7) for k in range(1, L_NR - 6)] + [0.97, 0.985, 0.995, 1.0]
assert len(L_V) == L_NR


def l_dir(phi, side):  # phi: from the leg's front towards its outer side
    return FRONT * math.cos(phi) + RIGHT * (side * math.sin(phi))


def l_top(phi):  # high outside, low inside: low until well round the front and back (the strip's edges), then rising
    return L_LO + (L_HI - L_LO) * ((1 + math.sin(phi)) / 2) ** 2


def l_off(z, v):
    """Offset from the skin: snug on the thigh, easing at the knee, loose round the shin, flaring at the ankle;
    the top hem rolled thicker, the bottom cuff a little thicker."""
    kz = _KNEE.z
    if z >= kz + 4.0:
        o = 0.6
    elif z >= kz - 6.0:
        o = 0.6 + 0.25 * (kz + 4.0 - z) / 10.0
    else:
        o = 0.85 + 0.75 * ((kz - 6.0 - z) / (kz - 6.0 - L_BOT)) ** 1.6
    if v >= 0.97:
        o += 0.22 * math.sin(math.pi * min(1.0, (v - 0.955) / 0.045))  # the rolled top hem
    if v <= 0.035:
        o += 0.18
    return o


def l_uv_v(z):  # texture v of height z (the outer hip's top edge at 0.9)
    return 0.01 + 0.89 * (z - L_BOT) / (L_HI - L_BOT)


def _leg_hit(phi, side, z):
    """The skin under a ring point: (triangle, barycentric weights)."""
    ax = leg_axis(z, side)
    o, d = Vector((ax.x, ax.y, z)), l_dir(phi, side)
    loc, nor, fi, dist = _LEG_BVH.ray_cast(o, d, 60)
    if loc is None:
        loc, nor, fi, dist = _LEG_BVH.find_nearest(o + d * 8.0)
    tri = _LEG_T[fi]
    return tri, poly_3d_calc([C0[i] for i in tri], loc)


LEG_BIND, LEG_UV, LEG_F, LEG_P = [], [], [], []
for side in (_LSIDE, -_LSIDE):
    u0 = 0.01 if side == _LSIDE else 0.51
    b0 = len(LEG_BIND)
    grid = {}
    for j, v in enumerate(L_V):
        for c in range(L_NC):
            phi = 1.5 * math.pi + 2 * math.pi * c / L_NC
            z = L_BOT + (l_top(phi) - L_BOT) * v
            grid[j, c] = [phi, z, v] + list(_leg_hit(phi, side, z))
    # The body is low-poly: a ring point on a flat facet sits lower than the facet's corners near it, and in
    # Blender those corners showed through as pale diamonds (2026-11-07). So test every body vertex of the leg
    # against the hide's real surface, along the leg's outward direction, and lift the four ring points of the
    # quad it reaches by what it lacks of 0.35 cm; repeat until none comes that close. Then ease the lifts into
    # their neighbours (never lowering one) so the hide stays smooth.
    ndot = {}
    for (j, c), (phi, z, v, tri, bary) in grid.items():
        # an offset along the skin's normal moves the point out from the leg's axis by only this much per cm
        ndot[j, c] = max(0.4, (recon((tri, bary, 1.0), "basis") - recon((tri, bary, 0.0), "basis")).dot(l_dir(phi, side)))
    lift = {k: 0.0 for k in grid}
    legv = [bp for i, bp in enumerate(C0) if i not in _ARMV0 and bp.x * side > 0.3 and L_BOT < bp.z < L_HI + 1.0]
    for it in range(8):
        pts = {(j, c): recon((g[3], g[4], l_off(g[1], g[2]) + lift[j, c] / ndot[j, c]), "basis") for (j, c), g in grid.items()}
        keys = list(pts)
        kidx = {k: i for i, k in enumerate(keys)}
        tris, quad = [], []
        for j in range(L_NR - 1):
            for c in range(L_NC):
                q = [(j, c), (j, (c + 1) % L_NC), (j + 1, (c + 1) % L_NC), (j + 1, c)]
                tris += [[kidx[q[0]], kidx[q[1]], kidx[q[2]]], [kidx[q[0]], kidx[q[2]], kidx[q[3]]]]
                quad += [q, q]
        sbvh = BVHTree.FromPolygons([pts[k] for k in keys], tris)
        add = {}
        for bp in legv:
            ax = leg_axis(bp.z, side)
            d = Vector((bp.x - ax.x, bp.y - ax.y, 0))
            if d.length < 1e-3:
                continue
            d.normalize()
            hit = sbvh.ray_cast(bp - d * 0.5, d, 4.0)
            if hit[0] is None:
                continue
            lack = 0.35 - (hit[3] - 0.5)
            if lack > 0.0:
                for k in quad[hit[2]]:
                    add[k] = max(add.get(k, 0.0), lack + 0.02)
        if not add:
            break
        for k, x in add.items():
            lift[k] += x
    for _ in range(2):
        lift = {(j, c): max(lift[j, c], 0.5 * lift[j, c] + 0.5 * sum(lift[jj, cc % L_NC] for jj, cc in
                ((j, c - 1), (j, c + 1), (max(j - 1, 0), c), (min(j + 1, L_NR - 1), c))) / 4) for (j, c) in lift}
    print("LEGGINGS side %+d: %d passes, lifted %d of %d ring points, most %.2f cm" % (
        side, it + 1, sum(1 for x in lift.values() if x > 0), len(lift), max(lift.values())))
    for layer in (0, 1):  # outer, inner (0.3 cm in)
        for j in range(L_NR):
            for c in range(L_NC + 1):  # the seam on the inner side: its column twice (u 0 and 1)
                phi, z, v, tri, bary = grid[j, c % L_NC]
                off = l_off(z, v) + lift[j, c % L_NC] / ndot[j, c % L_NC]
                LEG_BIND.append((tri, bary, off if layer == 0 else max(0.18, off - 0.3)))
                LEG_UV.append((u0 + 0.48 * c / L_NC, l_uv_v(z)))  # v by height, so bands run level round the leg
    L_ = lambda layer, j, c: b0 + (layer * L_NR + j) * (L_NC + 1) + c  # noqa: E731
    tag = "leg%+d" % side
    for j in range(L_NR - 1):
        for c in range(L_NC):
            LEG_F.append([L_(0, j, c), L_(0, j, c + 1), L_(0, j + 1, c + 1), L_(0, j + 1, c)])
            LEG_P.append(tag + "o")
            LEG_F.append([L_(1, j, c), L_(1, j + 1, c), L_(1, j + 1, c + 1), L_(1, j, c + 1)])
            LEG_P.append(tag + "i")
    for j in (0, L_NR - 1):  # the hems: outer and inner layer joined
        for c in range(L_NC):
            LEG_F.append([L_(0, j, c), L_(1, j, c), L_(1, j, c + 1), L_(0, j, c + 1)])
            LEG_P.append(tag + "r")


def _leg_clear(s, pts):
    """On shapes whose thighs meet (a dwarf's, a child's), ring points by the groin end up inside the other thigh
    or the crotch: lift them clear. They sit between the legs, under the loincloth, tunic or skirt."""
    if s == "basis":
        return pts
    out = []
    for p in pts:
        loc, nor, fi, d = BVH[s].find_nearest(p)
        out.append(loc + nor * 0.2 if (p - loc).dot(nor) < 0.1 else p)
    return out


LPOS = {s: _leg_clear(s, [recon(b, s) for b in LEG_BIND]) for s in ALL}
_LEG_OUTER = [f for f, p in zip(LEG_F, LEG_P) if p.endswith("o") or p.endswith("r")]
LEG_KNEE_V = l_uv_v(_KNEE.z)  # the knee's texture v (for the texture's bands)
print("LEGGINGS %d vertices, %d faces, z %.1f..%.1f (inner top %.1f)" % (len(LEG_BIND), len(LEG_F), L_BOT, L_HI, L_LO))


def with_leggings(s, coords, tris):
    """(coords, tris) plus the leggings' outer surface on shape s: an obstacle for the pieces built after them."""
    n0 = len(coords)
    return list(coords) + LPOS[s], [list(t) for t in tris] + [[i + n0 for i in f] for f in _LEG_OUTER]


# what the flaps must hang clear of: the body, the strip and the leggings, per body shape. Not the belt:
# the flaps tuck under it.
OBST = {}
for s in ALL:
    nb_ = len(COORDS[s])
    _co, _tr = with_leggings(s, list(COORDS[s]) + surface_parts(s),
                             [list(t) for t in TRIS[s]] + [[i + nb_ for i in q] for q in SURF_QUADS[NB * 4:]])
    OBST[s] = BVHTree.FromPolygons(_co, _tr)

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
        clear = 0.6 + 1.5 * t  # top stays under the belt's outer surface (1.4 cm); room for the legs lower down
        hw = 0.6 + 1.4 * min(1.0, t * 3)  # narrow look-around at the top, wider lower down
        z_lo = z - (sp["length"] / (FR - 1) if j < FR - 1 else 0.0)  # down to the next row too (see strip_positions)
        zs = np.arange(z_lo, za + 0.51, 0.5)
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
    n = VG[gi]
    for a, b in (("bn_lf_", "bn_rf_"), ("bn_lb_", "bn_rb_"), ("bn_l_", "bn_r_")):
        if n.startswith(a):
            n = b + n[len(a):]
            break
        if n.startswith(b):
            n = a + n[len(b):]
            break
    return GI.get(n, gi)


# Vanilla skirts and robes hang from the skeleton's eight skirt chains (bn_f_skirt1-5, bn_lf_, bn_l_, bn_lb_,
# bn_b_, bn_rb_, bn_r_, bn_rf_), which the game's animations swing with the legs: a striding thigh tilts the
# front chain forward, a seated pose lays it over the lap. So the cloth moves round the legs instead of the
# legs passing through it. Everything of ours that hangs below the hips (flaps, aprons, strips, skirts, tails)
# uses them the same way; above the chains' pivot at the hips it follows the pelvis.
SKIRT_CH = ("f", "lf", "l", "lb", "b", "rb", "r", "rf")
for _c in SKIRT_CH:
    for _i in range(1, 6):
        _n = "bn_%s_skirt%d" % (_c, _i)
        if _n not in GI:  # the body isn't skinned to them; the skeleton has them
            GI[_n] = len(VG)
            VG.append(_n)
_SKB = {c: [(rig.matrix_world @ rig.data.bones["bn_%s_skirt%d" % (c, i)].head_local,
             rig.matrix_world @ rig.data.bones["bn_%s_skirt%d" % (c, i)].tail_local) for i in range(1, 6)] for c in SKIRT_CH}
_SK_ANGS = sorted((math.atan2(_SKB[c][0][0].dot(RIGHT), _SKB[c][0][0].dot(FRONT)) % (2 * math.pi), c) for c in SKIRT_CH)
SK_PIVOT = sum(_SKB[c][0][0].z for c in SKIRT_CH) / len(SKIRT_CH)


def skirt_weights(th, z, fade=4.0):
    """Weights of a point hanging at angle th (from the front, towards +x) and height z: the two nearest skirt
    chains by angle; along each, its bones by height (each bone fully at its middle); above the chains' pivot
    the pelvis (body_root), blending into the chains over `fade` cm below it."""
    a, n = th % (2 * math.pi), len(_SK_ANGS)
    for k in range(n):
        (a0, c0), (a1, c1) = _SK_ANGS[k], _SK_ANGS[(k + 1) % n]
        span, da = (a1 - a0) % (2 * math.pi), (a - a0) % (2 * math.pi)
        if da <= span:
            t = da / span
            break
    out = {}
    for c, wc in ((c0, 1.0 - t), (c1, t)):
        if wc <= 1e-4:
            continue
        mids = [(h.z + tl.z) / 2 for h, tl in _SKB[c]]
        if z >= mids[0]:
            ws = {0: 1.0}
        elif z <= mids[4]:
            ws = {4: 1.0}
        else:
            i = max(j for j in range(4) if z <= mids[j])
            u = (mids[i] - z) / (mids[i] - mids[i + 1])
            ws = {i: 1.0 - u, i + 1: u}
        for i, w in ws.items():
            g = GI["bn_%s_skirt%d" % (c, i + 1)]
            out[g] = out.get(g, 0.0) + w * wc
    k = min(1.0, max(0.0, (SK_PIVOT - z) / fade))
    k = k * k * (3 - 2 * k)  # 0 at and above the pivot (the pelvis), 1 from `fade` cm below it
    d = {g: w * k for g, w in out.items()}
    d[GI["body_root"]] = d.get(GI["body_root"], 0.0) + (1.0 - k)
    return d


def ang_of(p):
    """Angle of point p round the body (from the front, towards +x), from the body's axis at its height."""
    c = Vector((0, center_y(min(max(p.z, CROTCH_Z + 2.0), TOP_Z0 - 3.0)), p.z))
    return math.atan2((p - c).dot(RIGHT), (p - c).dot(FRONT))


TOP_Z0 = max(c.z for c in C0)


def skin_weights_at(x, z, side):
    D = FRONT * side
    loc, nor, fi, dist = BVH["basis"].ray_cast(Vector((x, 0, z)) + D * 200, -D, 400)
    tri = TRIS["basis"][fi]
    return dict(weights_at(tri, poly_3d_calc([C0[i] for i in tri], loc)))


# Flap weights. The top rows (under the belt) copy the skin behind them, as the belt does.
# Lower down they blend into the skirt chains in front of (or behind) them, as a vanilla tunic's
# skirt does, so a striding or seated leg carries the flap with it instead of passing through it
# (until 2026-11-07 they blended into a stiff pelvis-and-thighs mix, and the thighs and leggings
# poked through). Below the belt the skin is sampled at belt height, so no thigh leaks in from one
# side. The right half mirrors the left, so both sides match exactly.
APRON = {GI["body_root"]: 0.4, GI["bn_l_hip"]: 0.3, GI["bn_r_hip"]: 0.3}  # the old stiff mix (kept for reference)


def apron_blend(t):
    u = min(1.0, max(0.0, (t - 0.15) / 0.3))
    return u * u * (3 - 2 * u)  # 0 = skin weights, 1 = apron weights


def flap_weights(side):
    sp = FLAPS[side]
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
            p_ = outer[j * FC + i]
            for k, v in skirt_weights(ang_of(p_), p_.z).items():
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
        p_ = POS["basis"][NB * 5 + a * SC + ci]
        for g, w in skirt_weights(ang_of(p_), p_.z).items():  # as the flap in front of it (2026-11-07)
            d[g] = d.get(g, 0.0) + w * k
        row = [(g, w) for g, w in sorted(d.items(), key=lambda kv: -kv[1])[:4] if w > 0.01]
        tot = sum(w for _, w in row)
        VW[NB * 5 + a * SC + ci] = [(g, w / tot) for g, w in row]
VW += flap_weights(+1) + flap_weights(-1)

PIECES = [dict(name=NAME, pos=POS, faces=FACES, part=PART, wrap=WRAP, wrap_u={i: 1.0 for i in range(5)}, uvs=UVS, vw=VW,
               orient=[("belt", lambda c: Vector((c.x, c.y - YC[0.0], 0)), None), ("strip", lambda c: c - P0, None),
                       ("flap+1", lambda c: FRONT, "flap+1o"), ("flap-1", lambda c: -FRONT, "flap-1o")])]


def _leg_out(side):  # outwards from the leg's axis
    return lambda c: Vector((c.x - leg_axis(c.z, side).x, c.y - leg_axis(c.z, side).y, 0))


# the leggings (geometry above, built first): the skin's weights where each ring point is bound
PIECES.append(dict(name=LEGG, set=LEGSET, pos=LPOS, faces=LEG_F, part=LEG_P, wrap=set(), wrap_u={}, uvs=LEG_UV,
                   vw=[weights_at(b[0], b[1]) for b in LEG_BIND],
                   orient=[("leg%+d" % sd, _leg_out(sd), "leg%+do" % sd) for sd in (1, -1)]))


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


def add_tube(th0, path, radii, flat, uv_box, part, cap_tip=False, tgt=None, binder=None):
    """A closed tube along path (local (c, z, o): sideways cm, height, offset from skin).
    tgt: (bind, uvs, faces, parts) lists of the piece to build into; the war piece by default.
    binder: how points find the skin (skin_bind: rays from the body's axis)."""
    B, U, F, P = tgt or (war_bind, WUVS, WFACES, WPART)
    sb = binder or (lambda th, z, off: skin_bind(th, z, off))
    R0 = (recon(skin_bind(th0, path[0][1], 0.0), "basis") - Vector((0, center_y(path[0][1]), path[0][1]))).length
    NSEG = 6
    b0 = len(B)
    pts = [Vector(p) for p in path]
    n = len(pts) - (1 if cap_tip else 0)
    for i in range(n):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        u = t.cross(Vector((1, 0, 0))).normalized()  # towards the offset axis
        v = t.cross(u)
        for j in range(NSEG):
            a = 2 * math.pi * j / NSEG
            q = pts[i] + u * (math.cos(a) * radii[i] * flat) + v * (math.sin(a) * radii[i])
            B.append(sb(th0 + q.x / R0, q.y, q.z))  # local (c, z, o) in x, y, z
            U.append((uv_box[0] + (uv_box[2] - uv_box[0]) * j / NSEG, uv_box[1] + (uv_box[3] - uv_box[1]) * i / (len(pts) - 1)))
    for i in range(n - 1):
        for j in range(NSEG):
            j2 = (j + 1) % NSEG
            F.append([b0 + i * NSEG + j, b0 + i * NSEG + j2, b0 + (i + 1) * NSEG + j2, b0 + (i + 1) * NSEG + j])
            P.append(part)
    for j in range(1, NSEG - 1):  # cap at the start (triangles: the exporter needs no n-gons)
        F.append([b0, b0 + j, b0 + j + 1])
        P.append(part)
    if cap_tip:  # a point at the end
        tip = len(B)
        B.append(sb(th0 + pts[-1].x / R0, pts[-1].y, pts[-1].z))
        U.append(((uv_box[0] + uv_box[2]) / 2, uv_box[3]))
        for j in range(NSEG):
            F.append([b0 + (n - 1) * NSEG + j, b0 + (n - 1) * NSEG + (j + 1) % NSEG, tip])
            P.append(part)
    else:
        e0 = b0 + (n - 1) * NSEG
        for j in range(1, NSEG - 1):
            F.append([e0, e0 + j, e0 + j + 1])
            P.append(part)


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



# ------------------------------------------------------------------ armoured skirt (both bodies)
# The war girdle again (same geometry and texture), and instead of the trophies a skirt of
# hide strips faced with bone lames over each hip (like pteruges). Each strip is a flat plank
# sewn onto the girdle's lower half; over the cord belt and down the thigh it hangs straight,
# as far out as anything above it needs (as the flaps do). The strips stay at the sides, clear
# of the front and back flaps. Rows on the girdle follow the skin under them; lower rows move
# as one stiff piece with the thigh (weights from the thigh, found from the leg's centre).
_legc = {}
_BODY_NA = None


def ray_origin(z, side):
    """Body axis at the belt, the leg's own centre from 10 cm below it (so the strips stay on the
    outer thigh, out of the groin crease), blended in between."""
    t = min(1.0, max(0.0, (BELT_Z - 2.0 - z) / 8.0))
    axis = Vector((0, center_y(max(z, CROTCH_Z + 1.0)), z))  # no body at x = 0 below the crotch
    if t == 0:
        return axis
    key = (round(z, 1), side)
    if key not in _legc:
        # the body mesh is sparse round the thighs, so find the leg's centre with rays
        y0 = center_y(CROTCH_Z + 1.0)
        # outer side: from outside, on the body without its arms (they hang beside the hips)
        global _BODY_NA
        if _BODY_NA is None:
            _BODY_NA = BVHTree.FromPolygons(C0, [list(t) for t in TRIS["basis"] if not _ARMV.intersection(t)])
        outer = _BODY_NA.ray_cast(Vector((side * 60, y0, z)), Vector((-side, 0, 0)), 120)[0].x
        # inner side: from the middle, unless the middle is still inside the body (then the hit is the outer side)
        hit = _BODY_NA.ray_cast(Vector((0, y0, z)), Vector((side, 0, 0)), 60)[0]
        inner = hit.x if hit is not None and abs(hit.x) < abs(outer) - 1.0 else 0.0
        cx = (outer + inner) / 2
        f = BVH["basis"].ray_cast(Vector((cx, y0, z)) + FRONT * 60, -FRONT, 120)[0]
        b = BVH["basis"].ray_cast(Vector((cx, y0, z)) - FRONT * 60, FRONT, 120)[0]
        _legc[key] = Vector((cx, (f.y + b.y) / 2, z))
    return axis.lerp(_legc[key], t)


def leg_bind(th, z, off):
    side = 1 if th > 0 else -1
    d = FRONT * math.cos(th) + RIGHT * math.sin(th)
    loc, nor, fi, dist = BVH["basis"].ray_cast(ray_origin(z, side), d, 100)
    return bind(loc, fi, off)


ARM = "ek2lc_%s_reach_armour_01" % S1
ASET = "ek2lc_reach_armour_01"
NGV = NW * len(G_ROWS)
arm_bind, AUVS = list(war_bind[:NGV]), list(WUVS[:NGV])
AFACES = [f for f, p in zip(WFACES, WPART) if p == "girdle"]
APART = ["girdle"] * len(AFACES)
AWRAP = {i for i in WWRAP if i < len(AFACES)}
STRIP_ANG = [62, 76, 90, 104, 118]  # strip centres, degrees from the front, on each side
S_STEP = math.radians(14)
S_ROWS = [(4.2, 0.25), (2.1, 0.45), (0.0, 0.65), (-1.9, 0.65), (-5.0, 0.9), (-9.0, 1.1), (-13.0, 1.2), (-17.0, 1.3),
          (-20.5, 1.4)]  # (height above BELT_Z, clearance): on the girdle, over the cord belt, then hanging free
S_COLS, S_THICK = 3, 0.3
S_UV = (0.03, 0.02, 0.97, 0.48)
S_BASE = Vector((0, center_y(BELT_Z), 0))
GFACES = list(AFACES)


def s_frame(th):
    d = FRONT * math.cos(th) + RIGHT * math.sin(th)  # outwards
    t = RIGHT * math.cos(th) - FRONT * math.sin(th)  # across the strip
    return d, t


# what the strips hang clear of, per body shape: body (not the arms, which hang beside the hips
# in the rest pose), loincloth, girdle
_ARMB = {i for i, n in enumerate(VG) if any(k in n for k in ("clavicle", "shoulder", "elbow", "forearm", "wrist", "_fi_",
                                                              "prop", "sleeve", "deltoid"))}
_ARMV = {i for i, ws in enumerate(BW) if sum(w for g, w in ws.items() if g in _ARMB) > 0.5}
A_OBST = {}
for s in ALL:  # (and the leggings, 2026-11-07: the strips, aprons and camp-wrap tails hang clear of them too)
    nb_, nl_ = len(COORDS[s]), len(POS[s])
    girdle = [recon(b, s) for b in war_bind[:NGV]]
    A_OBST[s] = BVHTree.FromPolygons(*with_leggings(s, list(COORDS[s]) + POS[s] + girdle,
                                                    [list(t) for t in TRIS[s] if not _ARMV.intersection(t)] +
                                                    [[i + nb_ for i in f] for f in FACES] +
                                                    [[i + nb_ + nl_ for i in f] for f in GFACES]))


def s_out(s, th, x, z):
    d, t = s_frame(th)
    hit = A_OBST[s].ray_cast(S_BASE + t * x + UP * z + d * 200, -d, 400)[0]
    return (hit - S_BASE).dot(d) if hit is not None else -1e9


STRIPS = []  # (th, half width)
for side in (1, -1):
    for ang in STRIP_ANG:
        th = side * math.radians(ang)
        STRIPS.append((th, 0.44 * S_STEP * (s_out("basis", th, 0, BELT_Z) + 0.35)))


def strip_positions(s):
    """Flat strips hanging straight down: each row as far out as anything above it, or between it and the
    next row down, needs (only above, the straight piece to the next row dipped into the cord belt's rounded
    top: seen in Blender 2026-11-07)."""
    out = []
    z_top = BELT_Z + S_ROWS[0][0]
    for th, hw in STRIPS:
        d, t = s_frame(th)
        xs = [(c / (S_COLS - 1) - 0.5) * 2 * hw for c in range(S_COLS)]
        rows = []
        for r_, (dz, clear) in enumerate(S_ROWS):
            z = BELT_Z + dz
            z_lo = BELT_Z + S_ROWS[r_ + 1][0] if r_ + 1 < len(S_ROWS) else z
            zs = list(np.arange(z_lo, z_top + 2.6, 0.5))  # a little above the top too: a fat belly overhangs the girdle
            h = max(s_out(s, th, x + dx, zz) for x in xs for dx in (-0.6, 0.0, 0.6) for zz in zs) + clear
            rows.append([S_BASE + t * x + d * h + UP * z for x in xs])
        if rows:
            out += [p for row in rows for p in row]
            out += [p - d * S_THICK for row in rows for p in row]
    return out


SPOS = {s: strip_positions(s) for s in ALL}
NR = len(S_ROWS)
_ctr = [SPOS["basis"][r * S_COLS + 1] for r in range(NR)]
_slen = [0.0]
for a_, b_ in zip(_ctr, _ctr[1:]):
    _slen.append(_slen[-1] + (b_ - a_).length)
AVW = [weights_at(b[0], b[1]) for b in arm_bind]
for k, (th, hw) in enumerate(STRIPS):
    b0 = NGV + k * 2 * NR * S_COLS
    side = 1 if th > 0 else -1
    # rows on the girdle move with the skin under it; lower rows half with the thigh, half with the skirt chain
    _lb_thigh = leg_bind(th, BELT_Z - 10.0, 0.0)
    for layer in range(2):
        for r in range(NR):
            for c in range(S_COLS):
                uc = c / (S_COLS - 1) if side == 1 else 1 - c / (S_COLS - 1)
                AUVS.append((S_UV[0] + (S_UV[2] - S_UV[0]) * uc, S_UV[3] - (S_UV[3] - S_UV[1]) * _slen[r] / _slen[-1]))
                k_ = (0.0, 0.0, 0.0, 0.25, 0.6)[r] if r < 5 else 1.0  # over the cord belt: with the hip, as the belt
                p_ = SPOS["basis"][(b0 - NGV) + layer * NR * S_COLS + r * S_COLS + c]
                skin = dict(nearest_weights(p_))
                # half with the thigh under it (it carries the strip in a stride), half with the skirt chain (it
                # swings it clear when the legs spread or bend): the scan in Blender found either alone let the
                # leggings or the hands through (2026-11-07)
                stiff = {}
                for g, w in list(weights_at(*_lb_thigh[:2])) + [(g, w) for g, w in skirt_weights(ang_of(p_), p_.z).items()]:
                    stiff[g] = stiff.get(g, 0.0) + 0.5 * w
                dd = {}
                for g, w in skin.items():
                    dd[g] = dd.get(g, 0.0) + w * (1 - k_)
                for g, w in stiff.items():
                    dd[g] = dd.get(g, 0.0) + w * k_
                row = [(g, w) for g, w in sorted(dd.items(), key=lambda kv: -kv[1])[:4] if w > 0.01]
                tot = sum(w for _, w in row)
                AVW.append([(g, w / tot) for g, w in row])
    L = lambda layer, r, c: b0 + layer * NR * S_COLS + r * S_COLS + c
    tag = "s%02d" % k
    for r in range(NR - 1):
        for c in range(S_COLS - 1):
            AFACES.append([L(0, r, c), L(0, r, c + 1), L(0, r + 1, c + 1), L(0, r + 1, c)])
            APART.append(tag + "o")
            AFACES.append([L(1, r, c), L(1, r + 1, c), L(1, r + 1, c + 1), L(1, r, c + 1)])
            APART.append(tag + "i")
        for c in (0, S_COLS - 1):  # the long edges
            AFACES.append([L(0, r, c), L(0, r + 1, c), L(1, r + 1, c), L(1, r, c)])
            APART.append(tag + "e")
    for r in (0, NR - 1):  # top and bottom edges
        for c in range(S_COLS - 1):
            AFACES.append([L(0, r, c), L(1, r, c), L(1, r, c + 1), L(0, r, c + 1)])
            APART.append(tag + "e")

APOS = {s: [recon(b, s) for b in arm_bind] + SPOS[s] for s in ALL}
A_ORIENT = [("girdle", lambda c: Vector((c.x, c.y - W_YC, 0)), None)]
for k in range(len(STRIPS)):
    A_ORIENT.append(("s%02d" % k, lambda c: Vector((c.x, c.y - W_YC, 0)), "s%02do" % k))
PIECES.append(dict(name=ARM, set=ASET, pos=APOS, faces=AFACES, part=APART, wrap=AWRAP, wrap_u={i: 1.0 for i in range(5)},
                   uvs=AUVS, vw=AVW, orient=A_ORIENT))
print("ARMOUR %d vertices, %d strips" % (len(APOS["basis"]), len(STRIPS)))




# ------------------------------------------------------------------ royal ladder (both bodies)
# A ruler's look by the higher of their own and their spouse's top title tier:
#   county and below: the loincloth (and chest band) in finer, dyed hide; nothing added
#   duke:    the fine loincloth, and a royal girdle with a short decorated front apron and
#            strings of bone beads at the hips
#   king:    the loincloth in royal smoked-black hide with patterned squares, and the girdle with
#            long front and back aprons (woven-look bands, fringe) and hagraven feathers at the hips
#   emperor: the king's pieces trimmed with Dwemer bronze and garnets (same mesh, own texture)
# The fine and royal loincloths and bands are the same meshes with other textures (only new
# .asset files). The girdle is the war girdle's shape. The aprons hang like the armour strips;
# below the cord belt they turn into one stiff piece with the hips, as the flaps under them do.
FSET, RSET = "ek2lc_reach_fine_01", "ek2lc_reach_royal_01"
ROYAL_SETS = {"duke": "ek2lc_reach_duke_01", "king": "ek2lc_reach_king_01", "emperor": "ek2lc_reach_emperor_01"}
APRON_UV, FEATHER_UV, RCORD_UV, RBEAD_UV = (0.03, 0.02, 0.47, 0.48), (0.53, 0.26, 0.97, 0.48), (0.53, 0.03, 0.75, 0.22), (0.77, 0.03, 0.97, 0.22)


def hang_panel(s, out_fn, th, rows, ncols, flat, top_extra=2.6):
    """Rows (dz above BELT_Z, clearance, half width) of a panel hanging straight from its top row:
    each row as far out as anything above it needs. flat: one plank; else curved across, smoothed."""
    d, t = s_frame(th)
    z_top = BELT_Z + rows[0][0]
    res = []
    for r_, (dz, clear, hw) in enumerate(rows):
        z = BELT_Z + dz
        xs = [(c / (ncols - 1) - 0.5) * 2 * hw for c in range(ncols)]
        z_lo = BELT_Z + rows[r_ + 1][0] if r_ + 1 < len(rows) else z  # down to the next row too (see strip_positions)
        zs = list(np.arange(z_lo, z_top + top_extra, 0.5))
        hs = [max(out_fn(s, th, x + dx, zz) for dx in (-0.6, 0.0, 0.6) for zz in zs) + clear for x in xs]
        if flat:
            hs = [max(hs)] * ncols
        else:
            for _ in range(2):
                hs = [max(hs[i], (hs[max(i - 1, 0)] + 2 * hs[i] + hs[min(i + 1, ncols - 1)]) / 4) for i in range(ncols)]
        res.append([S_BASE + t * x + d * h + UP * z for x, h in zip(xs, hs)])
    return res


def apron_rows(bottom, hw):
    rows = [(4.2, 0.25, hw), (2.1, 0.45, hw), (0.0, 0.65, hw), (-1.9, 0.65, hw)]  # on the girdle, over the cord belt
    z = -5.0
    while z > bottom + 1.0:
        rows.append((z, 0.8, hw))
        z -= 4.0
    return rows + [(bottom, 0.8, hw)]


def apron_k(z):  # 0 = skin weights, 1 = the flaps' stiff apron weights; as the flap at the same height
    return 0.0 if z >= BELT_Z - 1.9 else apron_blend((Z_ATTACH - z) / FLAPS[1]["length"])


def blend_weights(a, b, k):
    d = {}
    for g, w in a.items():
        d[g] = d.get(g, 0.0) + w * (1 - k)
    for g, w in b.items():
        d[g] = d.get(g, 0.0) + w * k
    row = [(g, w) for g, w in sorted(d.items(), key=lambda kv: -kv[1])[:4] if w > 0.01]
    tot = sum(w for _, w in row)
    return [(g, w / tot) for g, w in row]


def royal_piece(tier):
    name = "ek2lc_%s_reach_%s_01" % (S1, tier)
    bind, uvs = list(war_bind[:NGV]), list(WUVS[:NGV])
    faces, part = list(GFACES), ["girdle"] * len(GFACES)
    tgt = (bind, uvs, faces, part)
    if tier == "duke":
        panels = [("pf", 0.0, apron_rows(-20.0, 6.5))]
    else:
        panels = [("pf", 0.0, apron_rows(-42.0, 7.5)), ("pb", math.pi, apron_rows(-38.0, 7.5))]
    k = 0
    for side in (1, -1):
        for ang in (72, 86, 100):
            th0 = side * math.radians(ang)
            if tier == "duke":  # a cord with three bone beads
                add_tube(th0, [(0, BELT_Z + 3.0, 0.6), (0, BELT_Z + 1.9, 2.4), (0, BELT_Z - 1.9, 2.4), (0, BELT_Z - 2.6, 1.6),
                               (0, BELT_Z - 9.0, 1.6)], [0.14] * 5, 1.0, RCORD_UV, "r%02dc" % k, tgt=tgt)
                for j, zb in enumerate((BELT_Z - 3.2, BELT_Z - 5.4, BELT_Z - 7.6)):
                    add_tube(th0, [(0, zb, 1.6), (0, zb - 0.6, 1.6), (0, zb - 1.2, 1.6)], [0.4, 0.55, 0.4], 1.0, RBEAD_UV,
                             "r%02db%d" % (k, j), tgt=tgt)
            else:  # a cord, a bead, and a hagraven feather hanging flat against the hip
                bt, bb = BELT_Z - 2.3, BELT_Z - 3.3
                add_tube(th0, [(0, BELT_Z + 3.0, 0.6), (0, BELT_Z + 1.9, 2.4), (0, BELT_Z - 1.9, 2.4), (0, bt, 1.6)],
                         [0.14] * 4, 1.0, RCORD_UV, "r%02dc" % k, tgt=tgt)
                add_tube(th0, [(0, bt, 1.6), (0, (bt + bb) / 2, 1.6), (0, bb, 1.6)], [0.42, 0.55, 0.42], 1.0, RBEAD_UV,
                         "r%02db" % k, tgt=tgt)
                add_tube(th0, [(0, bb, 1.5), (0, bb - 4.0, 1.7), (0, bb - 8.0, 1.9), (0, bb - 12.5, 2.1)],
                         [0.35, 1.0, 0.85, 0.0], 0.22, FEATHER_UV, "r%02df" % k, cap_tip=True, tgt=tgt,
                         binder=leg_bind)  # down near the crotch: rays from the leg's centre
            k += 1
    pos = {s: [recon(b, s) for b in bind] for s in ALL}
    vw = [weights_at(b[0], b[1]) for b in bind]
    orient = [("girdle", lambda c: Vector((c.x, c.y - W_YC, 0)), None)]
    ctr = {}
    for f, p in zip(faces, part):
        if p != "girdle":
            ctr.setdefault(p, []).extend(pos["basis"][i] for i in f)
    for p, ps in ctr.items():
        orient.append((p, (lambda c0: (lambda c: c - c0))(sum(ps, Vector()) / len(ps)), None))
    for tag, th, rows in panels:
        NR, NC, d_ = len(rows), 5, s_frame(th)[0]
        b0 = len(pos["basis"])
        for s in ALL:
            grid = hang_panel(s, s_out, th, rows, NC, False)
            pos[s] += [q for row in grid for q in row] + [q - d_ * 0.3 for row in grid for q in row]
        cl = [pos["basis"][b0 + r * NC + NC // 2] for r in range(NR)]
        sl = [0.0]
        for a_, b_ in zip(cl, cl[1:]):
            sl.append(sl[-1] + (b_ - a_).length)
        u0, v0, u1, v1 = APRON_UV
        for layer in range(2):
            for r in range(NR):
                for c in range(NC):
                    q = pos["basis"][b0 + layer * NR * NC + r * NC + c]
                    uvs.append((u0 + (u1 - u0) * c / (NC - 1), v1 - (v1 - v0) * sl[r] / sl[-1]))
                    # skin part sampled as the flap under it does: behind it, at belt height at most; lower down
                    # the skirt chains, as the flap under it (so the two move together)
                    skin = skin_weights_at(q.x, max(q.z, BELT_Z - 1.7), 1 if abs(th) < 1 else -1)
                    vw.append(blend_weights(skin, skirt_weights(ang_of(q), q.z), apron_k(q.z)))
        L = lambda layer, r, c: b0 + layer * NR * NC + r * NC + c
        for r in range(NR - 1):
            for c in range(NC - 1):
                faces.append([L(0, r, c), L(0, r, c + 1), L(0, r + 1, c + 1), L(0, r + 1, c)])
                part.append(tag + "o")
                faces.append([L(1, r, c), L(1, r + 1, c), L(1, r + 1, c + 1), L(1, r, c + 1)])
                part.append(tag + "i")
            for c in (0, NC - 1):
                faces.append([L(0, r, c), L(0, r + 1, c), L(1, r + 1, c), L(1, r, c)])
                part.append(tag + "e")
        for r in (0, NR - 1):
            for c in range(NC - 1):
                faces.append([L(0, r, c), L(1, r, c), L(1, r, c + 1), L(0, r, c + 1)])
                part.append(tag + "e")
        orient.append((tag, (lambda dd: (lambda c: dd))(d_), tag + "o"))
    print("ROYAL %s %d vertices" % (tier, len(pos["basis"])))
    return dict(name=name, set=ROYAL_SETS[tier], pos=pos, faces=faces, part=part, wrap=set(AWRAP),
                wrap_u={i: 1.0 for i in range(5)}, uvs=uvs, vw=vw, orient=orient)


DUKE, KING = "ek2lc_%s_reach_duke_01" % S1, "ek2lc_%s_reach_king_01" % S1
PIECES.append(royal_piece("duke"))
PIECES.append(royal_piece("king"))


# ------------------------------------------------------------------ emperor's mantle (both bodies)
# A thick fur collar round the base of the neck, and a cape of hagraven feathers lined with
# garnet-dyed hide, from under the collar to the calves. Its own gene, worn with the emperor's
# pieces. The collar and the cape's top (the yoke, under and just below the collar) follow the
# skin. Below that the cape hangs free where vanilla cloaks hang (a few cm off the back, taut
# over the shoulder blades and buttocks, flaring a little to the hem), weighted to the
# skeleton's cloak bones as vanilla cloaks are, so it sways as they do.
MANTLE, MSET = "ek2lc_%s_reach_mantle_01" % S1, "ek2lc_reach_mantle_01"
COLLAR_UV, CAPE_UV, LINING_UV = (0.0, 0.86, 1.0, 0.99), (0.02, 0.02, 0.66, 0.84), (0.70, 0.02, 0.98, 0.84)
for _n in ["bn_%s_cloak%d" % (c, i) for c in ("b", "lb", "rb") for i in range(1, 6)]:
    if _n not in GI:  # the body isn't skinned to the cloak bones; the skeleton has them
        GI[_n] = len(VG)
        VG.append(_n)
TOP_Z = max(c.z for c in C0)  # the body ends at the neck (the head is its own mesh)
NECK_Z = TOP_Z - 3.5  # the collar's inner edge
COL_C = Vector((0, center_y(TOP_Z - 13.0), TOP_Z - 13.0))  # rays for the collar start here, inside the chest
NPHI, C_PROFILE = 48, [0.5, 1.9, 2.9, 3.3, 3.0, 2.2, 1.4]  # fur thickness across the collar, neck to edge
C_ROWS = len(C_PROFILE)
C_WIDTH = 9.0 if SEX == "male" else 8.0  # along the skin, from the neck outwards
NCC = 9  # cape columns
CAPE_ANG = math.radians(55)  # the yoke spans the back this far each side of the spine (from the neck)
if SEX == "male":
    YOKE_S = [0.35 * C_WIDTH, 0.55 * C_WIDTH, 0.75 * C_WIDTH, 0.95 * C_WIDTH, C_WIDTH + 2.5, C_WIDTH + 5.0]
    YOKE_OFF = [0.6, 0.65, 0.7, 0.8, 0.9, 1.0]  # under the collar's fur, then out past its edge
else:  # the chest band's back reaches up to just under the collar: the yoke ends at the collar's edge
    YOKE_S = [0.35 * C_WIDTH, 0.5 * C_WIDTH, 0.65 * C_WIDTH, 0.8 * C_WIDTH, 0.92 * C_WIDTH, C_WIDTH + 0.6]
    YOKE_OFF = [0.6, 0.65, 0.7, 0.75, 0.8, 0.9]
CAPE_THICK, HW_HEM, FLARE = 0.35, (21.0 if SEX == "male" else 20.0), 0.06
HANG_GAP = 5.0 if SEX == "male" else 2.0  # first free row below the yoke (women: close, over the band's top edge)
BACK = -FRONT


def collar_walk(phi, s_list):
    """Skin points at arc lengths s_list from the neck base outwards, at azimuth phi (0 = front)."""
    h = FRONT * math.cos(phi) + RIGHT * math.sin(phi)
    es, pts = [], []
    for i in range(241):  # elevation 85 .. -35 degrees
        e = math.radians(85 - 0.5 * i)
        loc = BVH["basis"].ray_cast(COL_C, h * math.cos(e) + UP * math.sin(e), 100)[0]
        if loc is not None:
            es.append(e)
            pts.append(loc)
    z0 = min(NECK_Z, pts[0].z - 0.5)  # men's neck is cut lower in front: start just under the cut there
    i0 = next(i for i in range(1, len(pts)) if pts[i].z <= z0)
    a, b = pts[i0 - 1], pts[i0]
    t = min(1.0, max(0.0, (a.z - z0) / (a.z - b.z))) if a.z != b.z else 0.0
    arc, prev, acc = [(0.0, es[i0 - 1] + (es[i0] - es[i0 - 1]) * t)], a.lerp(b, t), 0.0
    for i in range(i0, len(pts)):
        acc += (pts[i] - prev).length
        prev = pts[i]
        arc.append((acc, es[i]))
    out = []
    for s_ in s_list:
        j = next(j for j in range(1, len(arc)) if arc[j][0] >= s_)
        (s0, e0), (s1, e1) = arc[j - 1], arc[j]
        e = e0 + (e1 - e0) * ((s_ - s0) / (s1 - s0) if s1 > s0 else 0.0)
        for de in (0.0, 1e-3, -1e-3, 3e-3, -3e-3):  # the body is split along UV seams: a ray can slip through
            loc, nor, fi, dist = BVH["basis"].ray_cast(COL_C, h * math.cos(e + de) + UP * math.sin(e + de), 100)
            if loc is not None:
                break
        out.append((loc, fi))
    return out


_CHAIN = {c: [GI["bn_%s_cloak%d" % (c, i)] for i in range(1, 6)] for c in ("b", "lb", "rb")}
_CHAIN_Z = {c: [(rig.matrix_world @ rig.data.bones["bn_%s_cloak%d" % (c, i)].head_local).z for i in range(1, 6)]
            for c in ("b", "lb", "rb")}
_SIDE_X = abs((rig.matrix_world @ rig.data.bones["bn_lb_cloak2"].head_local).x)


def cloak_weights(x, z):
    """Vanilla-cloak weights: the back chain in the middle, the side chain towards the edges;
    along each chain, between the bones by height."""
    side = "lb" if x > 0 else "rb"  # bn_l_* bones are on +x
    wc = max(0.0, 1.0 - abs(x) / _SIDE_X)
    out = {}
    for col, wcol in (("b", wc), (side, 1.0 - wc)):
        if wcol <= 0:
            continue
        zs = _CHAIN_Z[col]
        mids = [(zs[i] + (zs[i + 1] if i < 4 else zs[4] - 20.0)) / 2 for i in range(5)]
        if z >= mids[0]:
            ws = {0: 1.0}
        elif z <= mids[4]:
            ws = {4: 1.0}
        else:
            i = max(j for j in range(4) if z <= mids[j])
            t = (mids[i] - z) / (mids[i] - mids[i + 1])
            ws = {i: 1.0 - t, i + 1: t}
        for i, w in ws.items():
            out[_CHAIN[col][i]] = out.get(_CHAIN[col][i], 0.0) + w * wcol
    return out


def _nearest_vert(p):
    return min(range(len(C0)), key=lambda i: (C0[i] - p).length_squared)


# landmarks that follow each body shape: the hem (back of the calf) and the buttocks' apex
Z_HEM = 0.55 * CROTCH_Z
HEM_V = _nearest_vert(Vector((9.0, 0, Z_HEM)) + BACK * 25)  # the back of the calf
_cands = [i for i, c in enumerate(C0) if abs(c.x) < 12 and CROTCH_Z < c.z < HIP_Z + 10]
BUTT_V = max(_cands, key=lambda i: C0[i].dot(BACK))


def mantle_piece():
    bind_, uvs, faces, part, wrap = [], [], [], [], set()
    # collar: a ring of NPHI columns from the back (k = 0, the UV seam, under the cape) round
    for k in range(NPHI):
        phi = math.pi - 2 * math.pi * k / NPHI
        for r, (loc, fi) in enumerate(collar_walk(phi, [C_WIDTH * r / (C_ROWS - 1) for r in range(C_ROWS)])):
            bind_.append(bind(loc, fi, C_PROFILE[r]))
            uvs.append((k / NPHI, COLLAR_UV[3] - (COLLAR_UV[3] - COLLAR_UV[1]) * r / (C_ROWS - 1)))
    for k in range(NPHI):
        k2 = (k + 1) % NPHI
        for r in range(C_ROWS - 1):
            if k2 == 0:
                wrap.add(len(faces))
            faces.append([k * C_ROWS + r, k2 * C_ROWS + r, k2 * C_ROWS + r + 1, k * C_ROWS + r + 1])
            part.append("collar")
    nco = len(bind_)
    pos = {s: [recon(b, s) for b in bind_] for s in ALL}
    vw = [weights_at(b[0], b[1]) for b in bind_]
    # cape yoke: columns walk down the back from under the collar, as the collar's own rows do
    yoke = []  # [column][row] skin points
    for c in range(NCC):
        phi = math.pi + CAPE_ANG * (1 - 2 * c / (NCC - 1))  # c = 0 on -x
        yoke.append(collar_walk(phi, YOKE_S))
    NY = len(YOKE_S)
    yb_out = [[bind(loc, fi, off) for (loc, fi), off in zip(col, YOKE_OFF)] for col in yoke]
    yb_in = [[(t, w, off - CAPE_THICK) for t, w, off in col] for col in yb_out]
    # hanging rows: same parameters on every body shape, placed by that shape's own landmarks
    zyb = recon(yb_out[NCC // 2][-1], "basis").z
    nh = max(4, int(round((zyb - HANG_GAP - Z_HEM) / 6.0)))
    T_ROWS = [r / (nh - 1) for r in range(nh)]
    x_hem = [(2 * c / (NCC - 1) - 1) * HW_HEM for c in range(NCC)]
    nb_, nl_ = len(C0), len(POS["basis"])
    king = next(pc for pc in PIECES if pc["name"] == KING)
    hang = {}
    for s in ALL:
        nk_ = len(king["pos"][s])
        band = (BPOS[s], BFACES) if SEX == "female" else ([], [])
        obst = BVHTree.FromPolygons(list(COORDS[s]) + POS[s] + king["pos"][s] + band[0],
                                    [list(t) for t in TRIS[s] if not _ARMV.intersection(t)] +
                                    [[i + nb_ for i in f] for f in FACES] +
                                    [[i + nb_ + nl_ for i in f] for f in king["faces"]] +
                                    [[i + nb_ + nl_ + nk_ for i in f] for f in band[1]])

        def out_at(x, z):
            hit = obst.ray_cast(Vector((x, 0, z)) + BACK * 100, FRONT, 200)[0]
            return hit.dot(BACK) if hit is not None else -1e9

        ybs = [recon(col[-1], s) for col in yb_out]
        z_top = min(p.z for p in ybs) - HANG_GAP
        z_hem, z_flare = COORDS[s][HEM_V].z, COORDS[s][BUTT_V].z
        zr = [z_top + (z_hem - z_top) * t for t in T_ROWS]
        grid = []  # [column][row] (x, z, out)
        for c in range(NCC):
            p0 = ybs[c]
            b0 = p0.dot(BACK)
            prof, run, z_prev = [], b0, p0.z
            for r, z in enumerate(zr):
                x = p0.x + (x_hem[c] - p0.x) * T_ROWS[r]
                clear = 0.6 + 3.4 * min(1.0, max(0.0, (p0.z - z) / 25.0))
                for zz in np.arange(z_prev, z - 0.01, -1.0):  # hang straight from anything above
                    run = max(run, max(out_at(x + dx, zz) for dx in (-0.8, 0.0, 0.8)) + clear)
                run = max(run, max(out_at(x + dx, z) for dx in (-0.8, 0.0, 0.8)) + clear)
                prof.append([x, z, run])
                z_prev = z
            pts = [(p0.z, b0)] + [(z, b) for x, z, b in prof]
            for r in range(len(prof)):  # taut: the upper hull of the profile (straight over bumps)
                z = prof[r][1]
                for i in range(len(pts)):
                    for j in range(i + 1, len(pts)):
                        (za, ba), (zb, bb) = pts[i], pts[j]
                        if za > z > zb:
                            prof[r][2] = max(prof[r][2], ba + (bb - ba) * (za - z) / (za - zb))
            for q in prof:
                q[2] += FLARE * max(0.0, z_flare - q[1])
            grid.append(prof)
        for r in range(nh):  # across: a gentle curve, edges a little forward; never in
            hw = max(abs(grid[c][r][0]) for c in range(NCC))
            top = max(grid[c][r][2] for c in range(NCC))
            bs = [max(grid[c][r][2], top - 3.5 * (grid[c][r][0] / hw) ** 2) for c in range(NCC)]
            for _ in range(2):
                bs = [max(bs[i], (bs[max(i - 1, 0)] + 2 * bs[i] + bs[min(i + 1, NCC - 1)]) / 4) for i in range(NCC)]
            for c in range(NCC):
                grid[c][r][2] = bs[c]
        hang[s] = grid
    NR_ = NY + nh
    for s in ALL:
        outer = [[recon(yb_out[c][r], s) for r in range(NY)] +
                 [Vector((x, 0, z)) + BACK * b for x, z, b in hang[s][c]] for c in range(NCC)]
        inner = [[recon(yb_in[c][r], s) for r in range(NY)] +
                 [Vector((x, 0, z)) + BACK * (b - CAPE_THICK) for x, z, b in hang[s][c]] for c in range(NCC)]
        for layer in (outer, inner):
            pos[s] += [layer[c][r] for r in range(NR_) for c in range(NCC)]
    b0 = nco
    cl = [pos["basis"][b0 + r * NCC + NCC // 2] for r in range(NR_)]
    sl = [0.0]
    for a_, b_ in zip(cl, cl[1:]):
        sl.append(sl[-1] + (b_ - a_).length)
    for layer, box in ((0, CAPE_UV), (1, LINING_UV)):
        for r in range(NR_):
            for c in range(NCC):
                uvs.append((box[0] + (box[2] - box[0]) * c / (NCC - 1), box[3] - (box[3] - box[1]) * sl[r] / sl[-1]))
                yb = (yb_out if layer == 0 else yb_in)[c]
                if r < NY:
                    vw.append(weights_at(yb[r][0], yb[r][1]))
                else:
                    x, z, _ = hang["basis"][c][r - NY]
                    skin = dict(weights_at(yb[-1][0], yb[-1][1]))
                    k_ = min(1.0, max(0.0, (recon(yb[-1], "basis").z - z) / 12.0))
                    vw.append(blend_weights(skin, cloak_weights(x, z), k_))
    L = lambda layer, r, c: b0 + layer * NR_ * NCC + r * NCC + c
    for r in range(NR_ - 1):
        for c in range(NCC - 1):
            faces.append([L(0, r, c), L(0, r, c + 1), L(0, r + 1, c + 1), L(0, r + 1, c)])
            part.append("capeo")
            faces.append([L(1, r, c), L(1, r + 1, c), L(1, r + 1, c + 1), L(1, r, c + 1)])
            part.append("capei")
        for c in (0, NCC - 1):
            faces.append([L(0, r, c), L(0, r + 1, c), L(1, r + 1, c), L(1, r, c)])
            part.append("capee")
    for r in (0, NR_ - 1):
        for c in range(NCC - 1):
            faces.append([L(0, r, c), L(1, r, c), L(1, r, c + 1), L(0, r, c + 1)])
            part.append("capee")
    ctr = Vector((0, COL_C.y, COL_C.z))
    orient = [("collar", lambda c: c - ctr, None), ("cape", lambda c: BACK, "capeo")]
    hb = hang["basis"]
    print("MANTLE %d vertices; collar rows z front %.1f..%.1f back %.1f..%.1f; cape yoke z %.1f, hem z %.1f, "
          "out from the spine: top %.1f, buttocks %.1f, hem %.1f; hem half width %.1f"
          % (len(pos["basis"]), pos["basis"][NPHI // 2 * C_ROWS].z, pos["basis"][NPHI // 2 * C_ROWS + C_ROWS - 1].z,
             pos["basis"][0].z, pos["basis"][C_ROWS - 1].z, zyb, hb[NCC // 2][-1][1], hb[NCC // 2][0][2],
             max(q[2] for q in hb[NCC // 2] if abs(q[1] - C0[BUTT_V].z) < 4) if any(abs(q[1] - C0[BUTT_V].z) < 4 for q in hb[NCC // 2]) else -1,
             hb[NCC // 2][-1][2], HW_HEM))
    if SEX == "female":  # the collar must stay clear of the chest band
        bk = [q for q in BPOS["basis"] if q.dot(BACK) > 0]
        print("MANTLE band back z %.1f..%.1f" % (min(q.z for q in bk), max(q.z for q in bk)))
        for s in ALL:  # band points with the cape between them and the body poke through it
            co = BVHTree.FromPolygons(pos[s], [f for f, pt in zip(faces, part) if pt == "capeo"])
            n = sum(1 for q in BPOS[s] if co.ray_cast(q, FRONT, 20)[0] is not None)
            print("MANTLE cape-band %-9s band points outside the cape: %d" % (s, n))
        for s in ALL:
            bt = BVHTree.FromPolygons(BPOS[s], BFACES)
            print("MANTLE collar-band gap %-9s %.2f" % (s, min(bt.find_nearest(p)[3] for p in pos[s][:nco])))
    return dict(name=MANTLE, set=MSET, pos=pos, faces=faces, part=part, wrap=wrap,
                wrap_u={i: 1.0 for i in range(C_ROWS)}, uvs=uvs, vw=vw, orient=orient)


PIECES.append(mantle_piece())


# ------------------------------------------------------------------ textures (shared by every piece)
HIDE_STYLES = {  # base loincloth and chest band: plain (commoners), fine (county, duke), royal (king, emperor)
    "plain": dict(hide=(0.52, 0.37, 0.24), cord=(0.33, 0.22, 0.14)),
    "fine": dict(hide=(0.50, 0.30, 0.18), cord=(0.40, 0.12, 0.07)),
    "royal": dict(hide=(0.21, 0.15, 0.11), cord=(0.36, 0.09, 0.06)),
}
# Colours: K(r, g, b) is the Reach colour, or the current culture's colour for that role
# (cultures.py). set_culture({}) is the Reach.
REMAP, MOTIF = {}, "zigzag"


def K(r, g, b):
    return np.array(REMAP.get((r, g, b), (r, g, b)), np.float32)


def set_culture(pal):
    global REMAP, MOTIF, C_RED, C_OCHRE, C_BLACK, C_BONE
    REMAP = {ROLES[k]: v for k, v in pal.items() if k in ROLES}
    MOTIF = pal.get("motif", "zigzag")
    C_RED, C_OCHRE, C_BLACK, C_BONE = K(0.42, 0.07, 0.05), K(0.62, 0.38, 0.12), K(0.06, 0.045, 0.035), K(0.84, 0.78, 0.64)


set_culture({})


def band_motif(sub, xx, fy, h, w, wear):
    """The worn painted band across a plain flap, in the culture's motif."""
    col = K(0.50, 0.13, 0.08)
    ok = wear > 0.32
    if MOTIF == "zigzag":  # the Reach: two zig-zag lines
        tri = np.abs((xx / (w / 7.0)) % 1.0 - 0.5) * 2.0
        m = np.zeros(xx.shape, bool)
        for yc in (0.69, 0.735):
            m |= np.abs(fy - (yc + (tri - 0.5) * 0.035)) * h < 3.2
    elif MOTIF == "steps":  # Ashlanders: a stepped meander between two lines
        P = w / 8.0
        ph = (xx % P) / P
        lvl = np.where(ph < 0.5, 0.70, 0.725)
        m = (np.abs(fy - lvl) * h < 2.6) | ((np.minimum(ph, np.abs(ph - 0.5)) * P < 2.6) & (fy > 0.70) & (fy < 0.725))
        m |= (np.abs(fy - 0.675) * h < 2.0) | (np.abs(fy - 0.75) * h < 2.0)
    elif MOTIF == "leaves":  # Bosmer: a vine with leaves turned up and down in turn
        P = w / 7.0
        k = np.floor(xx / P)
        lx = (xx % P) - P / 2
        ly = (fy - 0.71) * h + np.where(k % 2 == 0, 1, -1) * P * 0.16
        c, s_ = 0.7071, np.where(k % 2 == 0, 0.7071, -0.7071)
        a_, b_ = lx * c + ly * s_, -lx * s_ + ly * c
        m = (a_ / (P * 0.30)) ** 2 + (b_ / (P * 0.12)) ** 2 < 1
        m |= np.abs(fy - 0.71 - 0.012 * np.sin(xx / P * 2 * np.pi)) * h < 1.6
    elif MOTIF == "scales":  # Argonians: a band of diamond scales
        P = w / 10.0
        dx = np.abs((xx / P) % 1.0 - 0.5)
        dy = np.abs(((fy - 0.665) * h / (P * 0.75)) % 1.0 - 0.5)
        m = (np.abs(dx + dy - 0.5) < 0.07) & (fy > 0.665) & (fy < 0.665 + 2 * P * 0.75 / h)
    else:  # Khajiit ("moons"): crescent moons with a dot between
        P = w / 6.0
        lx = (xx % P) - P / 2
        ly = (fy - 0.71) * h
        R = P * 0.22
        m = (lx ** 2 + ly ** 2 < R ** 2) & ((lx - R * 0.45) ** 2 + (ly + R * 0.1) ** 2 > (R * 0.85) ** 2)
        m |= ((np.abs(xx % P) - 0) ** 2 + ly ** 2 < (R * 0.25) ** 2)
        m |= ((np.abs((xx % P) - P)) ** 2 + ly ** 2 < (R * 0.25) ** 2)
    m &= ok
    sub[m, :3] = sub[m, :3] * 0.3 + col * 0.7


def hide_deco(style, sub, xx, yy, fy, h, w, wear):
    """Painted and stitched decoration on a flap of the fine or royal hide."""
    edge = np.minimum(xx, w - 1 - xx)
    if style == "fine":  # red edge line, bone stitching, black and red zig-zags low down
        sub[(np.abs(edge - 20) < 2.5) & (fy < 0.84), :3] = C_RED
        sub[(np.abs(edge - 30) < 2.0) & ((yy % 14) < 7) & (fy > 0.13) & (fy < 0.84), :3] = C_BONE
        tri = np.abs((xx / (w / 9.0)) % 1.0 - 0.5) * 2.0
        for yc, col in ((0.64, C_BLACK), (0.70, C_RED), (0.76, C_BLACK)):
            sub[(np.abs(fy - (yc + (tri - 0.5) * 0.03)) * h < 3.0) & (edge > 34), :3] = col
        return
    # royal: a stitched bone-white border, a grid of small patterned squares, a red band low down
    m = (edge > 10) & (edge < 22) & (fy < 0.85)
    sub[m, :3] = C_BONE * (0.85 + 0.15 * wear[m])[:, None]
    sub[(np.abs(edge - 16) < 1.2) & ((yy % 10) < 5) & (fy < 0.85), :3] = C_BLACK
    x0, x1, y0, y1, nc, nr, gap = 0.2 * w, 0.8 * w, 0.16 * h, 0.60 * h, 4, 5, 4
    cw, ch = (x1 - x0) / nc, (y1 - y0) / nr
    inside = (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)
    ci = np.clip((xx - x0) // cw, 0, nc - 1)
    ri = np.clip((yy - y0) // ch, 0, nr - 1)
    lx, ly = (xx - x0) - ci * cw, (yy - y0) - ri * ch
    cell = inside & (lx > gap) & (ly > gap) & (lx < cw - gap) & (ly < ch - gap)
    kind = ((ci + 2 * ri) % 4).astype(np.int32)
    u_, v_ = (lx - gap) / (cw - 2 * gap), (ly - gap) / (ch - 2 * gap)
    for k, col in enumerate((C_RED, C_OCHRE, C_BLACK, C_BONE)):
        m = cell & (kind == k)
        sub[m, :3] = col * (0.85 + 0.2 * wear[m])[:, None]
    sub[cell & (kind == 0) & (np.maximum(np.abs(u_ - 0.5), np.abs(v_ - 0.5)) < 0.22), :3] = C_BONE
    sub[cell & (kind == 1) & ((np.abs(u_ - v_) < 0.09) | (np.abs(u_ + v_ - 1) < 0.09)), :3] = C_BLACK
    sub[cell & (kind == 2) & (np.floor(v_ * 4) >= 3 - np.floor(u_ * 4)), :3] = C_RED
    sub[cell & (kind == 3) & ((u_ - 0.5) ** 2 + (v_ - 0.5) ** 2 < 0.04), :3] = C_RED
    m = (np.abs(fy - 0.70) * h < 9) & (edge > 22)
    sub[m, :3] = C_RED * (0.85 + 0.2 * wear[m])[:, None]
    tri = np.abs((xx / (w / 9.0)) % 1.0 - 0.5) * 2.0
    sub[(np.abs(fy - (0.70 + (tri - 0.5) * 0.02)) * h < 2.2) & (edge > 22), :3] = C_BONE


def make_textures(style="plain"):
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
    hide = K(*HIDE_STYLES[style]["hide"])
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
        if style == "plain":
            band_motif(sub, xx, fy, h, w, wear)
        else:
            hide_deco(style, sub, xx, yy, fy, h, w, wear)
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
    sub[..., :3] = K(*HIDE_STYLES[style]["cord"]) * (0.55 + 0.5 * twist * (0.6 + 0.4 * np.sin(np.pi * fy) ** 0.6))[..., None]
    if style == "royal":  # bone-white wraps round the red cord
        sub[((xx / w * 40) % 1.0) < 0.22, :3] = C_BONE * 0.9
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
    img[g, :3] = K(0.27, 0.18, 0.11) * (0.75 + 0.5 * n[g])[:, None]
    gv = (v - 0.52) / 0.46  # 0 inner bottom .. 1 inner top
    for lv in (0.2, 0.8):  # stitching just inside the edges
        m = g & (np.abs(gv - lv) < 0.012) & ((xx % 10) < 5)
        img[m, :3] = K(0.62, 0.52, 0.38)
    tri = np.abs((u * 24) % 1.0 - 0.5) * 2.0  # ochre zig-zag across the middle
    m = g & (np.abs(gv - (0.5 + (tri - 0.5) * 0.22)) < 0.035) & (n > 0.3)
    img[m, :3] = img[m, :3] * 0.25 + K(0.55, 0.12, 0.07) * 0.75
    for lv in (0.31, 0.69):  # rows of painted bone beads
        cx = (np.floor(u * 48) + 0.5) / 48
        m = g & (((u - cx) * WD) ** 2 + ((gv - lv) * 0.46 * H) ** 2 < 4.2 ** 2)
        img[m, :3] = K(0.82, 0.77, 0.64) * (0.85 + 0.15 * n[m])[:, None]
    # bone (u < .5, v < .5): ivory, darker towards the tips
    b = (u < 0.5) & (v < 0.5)
    img[b, :3] = K(0.84, 0.79, 0.66) * (0.8 + 0.25 * n[b] - 0.25 * (v[b] / 0.5) ** 3)[:, None]
    # claw (u > .5, v < .25): dark horn
    c = (u >= 0.5) & (v < 0.25)
    img[c, :3] = K(0.16, 0.13, 0.10) * (0.8 + 0.4 * n[c])[:, None]
    # sinew cord (u > .5, .25 < v < .5)
    s = (u >= 0.5) & (v >= 0.25) & (v < 0.5)
    img[s, :3] = K(0.55, 0.44, 0.30) * (0.7 + 0.3 * np.sin(xx[s] * 0.9 + yy[s] * 0.6))[:, None]
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


def make_armour_textures():
    """The war set's girdle half unchanged; the other half is a hide strip with three bone lames."""
    t = make_war_textures()
    img, props = t["diffuse"], t["properties"]
    H, WD = img.shape[:2]
    rng = np.random.default_rng(31)
    yy, xx = np.mgrid[0:H, 0:WD].astype(np.float32)
    v = 1 - yy / (H - 1)
    u = xx / (WD - 1)
    n = rng.random((H // 8 + 2, WD // 8 + 2)).astype(np.float32)
    n = n[(yy // 8).astype(int), (xx // 8).astype(int)] * 0.5 + rng.random((H, WD)).astype(np.float32) * 0.15
    s = v < 0.5
    su = np.clip((u - S_UV[0]) / (S_UV[2] - S_UV[0]), 0, 1)
    sl = np.clip((S_UV[3] - v) / (S_UV[3] - S_UV[1]), 0, 1)  # 0 at the top of the strip .. 1 at the bottom
    hide = K(0.31, 0.21, 0.13)
    img[s, :3] = hide * (0.7 + 0.5 * n[s])[:, None] * (1.0 - 0.25 * sl[s] ** 4)[:, None]  # worn, darker bottom
    m = s & (np.abs(np.abs(su - 0.5) - 0.42) < 0.012) & ((yy % 9) < 5)  # stitching along both long edges
    img[m, :3] = K(0.6, 0.5, 0.36)
    props[s, 1] = 0.22
    for l0, l1 in ((0.30, 0.46), (0.53, 0.69), (0.76, 0.92)):  # bone lames, lashed on
        lame = s & (sl > l0) & (sl < l1) & (np.abs(su - 0.5) < 0.36)
        rim = lame & ((sl - l0 < 0.012) | (l1 - sl < 0.012) | (0.36 - np.abs(su - 0.5) < 0.03))
        shade = 0.82 + 0.25 * n - 0.18 * ((sl - l0) / (l1 - l0))
        img[lame, :3] = K(0.83, 0.78, 0.64) * shade[lame][:, None]
        img[rim, :3] *= 0.6
        props[lame, 1] = 0.35
        for hu in (0.2, 0.8):  # lacing holes
            hole = s & (((su - hu) * WD * 0.94) ** 2 + ((sl - (l0 + l1) / 2) * H * 0.46) ** 2 < 2.6 ** 2)
            img[hole, :3] = K(0.12, 0.08, 0.05)
    for hu in (0.3, 0.7):  # bone studs where the strip is sewn to the girdle
        stud = s & (((su - hu) * WD * 0.94) ** 2 + ((sl - 0.05) * H * 0.46) ** 2 < 4.0 ** 2)
        img[stud, :3] = K(0.82, 0.77, 0.64) * (0.85 + 0.2 * n[stud])[:, None]
        props[stud, 1] = 0.35
    return {"diffuse": np.clip(img, 0, 1), "normal": t["normal"], "properties": props}


def make_royal_textures(tier):
    """Royal add-ons: girdle (top half, as the war girdle), apron, hagraven feather, sinew cord, beads."""
    H = WD = 512
    rng = np.random.default_rng({"duke": 41, "king": 43, "emperor": 43}[tier])
    n = rng.random((H // 8 + 2, WD // 8 + 2)).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:WD].astype(np.float32)
    n = n[(yy // 8).astype(int), (xx // 8).astype(int)] * 0.5 + rng.random((H, WD)).astype(np.float32) * 0.15
    v, u = 1 - yy / (H - 1), xx / (WD - 1)
    img = np.ones((H, WD, 4), np.float32)
    props = np.zeros((H, WD, 4), np.float32)
    props[..., 1], props[..., 3] = 0.22, 0.58
    BRONZE, GARNET = K(0.70, 0.50, 0.22), K(0.45, 0.03, 0.07)
    metal = tier == "emperor"
    trim, accent = (BRONZE, GARNET) if metal else (C_BONE, C_RED)
    base = K(0.46, 0.25, 0.15) if tier == "duke" else K(0.17, 0.12, 0.09)

    def shiny(m):
        props[m, 1] = 0.5 if metal else 0.35

    # girdle
    g = v >= 0.5
    img[g, :3] = base * (0.75 + 0.5 * n[g])[:, None]
    gv = (v - 0.52) / 0.46
    for lv in (0.16, 0.84):  # trim lines along both edges
        m = g & (np.abs(gv - lv) < 0.035)
        img[m, :3] = trim * (0.85 + 0.2 * n[m])[:, None]
        shiny(m)
    if tier == "duke":
        tri = np.abs((u * 24) % 1.0 - 0.5) * 2.0
        img[g & (np.abs(gv - (0.5 + (tri - 0.5) * 0.3)) < 0.04), :3] = C_BLACK
    else:  # a row of patterned squares round the middle
        cell = np.floor(u * 40)
        lu, lv_ = (u * 40) % 1.0, (gv - 0.28) / 0.44
        sq = g & (lv_ > 0) & (lv_ < 1) & (lu > 0.1) & (lu < 0.9)
        k = (cell % 3).astype(np.int32)
        for i, col in enumerate((accent, trim, C_OCHRE)):
            m = sq & (k == i)
            img[m, :3] = col * (0.85 + 0.2 * n[m])[:, None]
            if i < 2:
                shiny(m)
        img[sq & (k == 0) & (np.abs(lu - 0.5) < 0.15) & (np.abs(lv_ - 0.5) < 0.15), :3] = C_BLACK
    for lv in (0.06, 0.94):  # bead rows on the edges
        cx = (np.floor(u * 48) + 0.5) / 48
        m = g & (((u - cx) * WD) ** 2 + ((gv - lv) * 0.46 * H) ** 2 < 3.6 ** 2)
        img[m, :3] = trim * (0.85 + 0.15 * n[m])[:, None]
        shiny(m)
    # apron
    a = (u < 0.5) & (v < 0.5)
    au = np.clip((u - APRON_UV[0]) / (APRON_UV[2] - APRON_UV[0]), 0, 1)
    al = np.clip((APRON_UV[3] - v) / (APRON_UV[3] - APRON_UV[1]), 0, 1)  # 0 top .. 1 bottom
    img[a, :3] = base * (0.75 + 0.45 * n[a])[:, None]
    edge = np.minimum(au, 1 - au)
    m = a & (edge < 0.07) & (edge > 0.03)
    img[m, :3] = trim
    shiny(m)
    if tier == "duke":  # stacked bone chevrons
        chev = (al * 9 + np.abs(au - 0.5) * 3) % 1.0
        m = a & (chev < 0.18) & (al > 0.2) & (al < 0.8) & (edge > 0.12)
        img[m, :3] = C_BONE
    else:  # woven-look bands of small squares, steps and lines
        for b0 in (0.22, 0.44, 0.66):
            band = a & (al > b0) & (al < b0 + 0.12) & (edge > 0.1)
            img[band, :3] = accent * (0.85 + 0.2 * n[band])[:, None]
            shiny(band)
            lu = (au * 10) % 1.0
            lb = (al - b0) / 0.12
            m = band & (np.abs(lu - 0.5) < 0.22) & (np.abs(lb - 0.5) < 0.25)
            img[m, :3] = trim
            shiny(m)
            img[a & (np.abs(al - b0 - 0.135) < 0.008) & (edge > 0.1), :3] = trim * 0.9
    fr = (xx % 9) < 3  # fringe: slits over the bottom 12 %
    img[a & ((al > 0.88) & fr | (al > 0.985)), 3] = 0.0
    # hagraven feather: dark vane, pale shaft; red tip for the emperor
    f = (u >= 0.5) & (v >= 0.25) & (v < 0.5)
    fu = (u - FEATHER_UV[0]) / (FEATHER_UV[2] - FEATHER_UV[0])
    fv = np.clip((v - FEATHER_UV[1]) / (FEATHER_UV[3] - FEATHER_UV[1]), 0, 1)  # 0 quill .. 1 tip
    shaft = np.minimum(np.abs(fu - 0.0), np.minimum(np.abs(fu - 0.5), np.abs(fu - 1.0))) < 0.04
    barbs = 0.75 + 0.25 * np.sin((fv * 60 + np.abs(fu - 0.5) * 30))
    img[f, :3] = K(0.12, 0.12, 0.13) * barbs[f][:, None] * (1 + 0.6 * fv[f] ** 3)[:, None]
    img[f & shaft, :3] = K(0.75, 0.72, 0.66)
    if metal:
        img[f & (fv > 0.8) & ~shaft, :3] = GARNET * 1.3
    # sinew cord and beads
    c = (u >= 0.5) & (v < 0.25) & (u < 0.76)
    img[c, :3] = K(0.55, 0.44, 0.30) * (0.7 + 0.3 * np.sin(xx[c] * 0.9 + yy[c] * 0.6))[:, None]
    b = (u >= 0.76) & (v < 0.25)
    img[b, :3] = trim * (0.8 + 0.3 * n[b])[:, None]
    shiny(b)
    normal = np.zeros((H, WD, 4), np.float32)
    normal[..., 0] = normal[..., 1] = normal[..., 3] = 0.5
    return {"diffuse": np.clip(img, 0, 1), "normal": normal, "properties": props}


def make_mantle_textures():
    """Emperor's mantle: pale snow-bear fur collar (strands from the neck outwards, tufted edge);
    cape of overlapping hagraven feathers (rows of garnet ones, a garnet-tipped hem), feather-tip
    hem cut out of both sides; lining of garnet-dyed hide with a bronze border and a bone zig-zag."""
    H = WD = 1024
    rng = np.random.default_rng(47)
    yy, xx = np.mgrid[0:H, 0:WD].astype(np.float32)
    v, u = 1 - yy / (H - 1), xx / (WD - 1)
    img = np.zeros((H, WD, 4), np.float32)
    img[..., :3], img[..., 3] = 0.05, 1.0
    props = np.zeros((H, WD, 4), np.float32)
    props[..., 1], props[..., 3] = 0.22, 0.58
    BRONZE, GARNET = K(0.70, 0.50, 0.22), K(0.45, 0.03, 0.07)
    # collar
    m = v >= 0.855
    fv = np.clip((COLLAR_UV[3] - v) / (COLLAR_UV[3] - COLLAR_UV[1]), 0, 1)  # 0 at the neck .. 1 at the edge
    s1 = np.convolve(rng.random(WD + 8), np.ones(3) / 3, "same")[4:WD + 4].astype(np.float32)
    s2 = rng.random(WD).astype(np.float32)
    xi = xx.astype(np.int32)
    wav = (xi + (3 * np.sin(yy * 0.07 + xx * 0.013)).astype(np.int32)) % WD
    fur = K(0.80, 0.77, 0.70)[None, None, :] * (0.72 + 0.32 * s1[wav])[..., None]
    fur *= (0.62 + 0.38 * np.clip(fv * 1.4, 0, 1))[..., None]  # darker at the roots
    fur = np.where((s2[wav] < 0.12)[..., None], fur * 0.55, fur)  # dark guard hairs
    img[m, :3] = fur[m]
    tuft_p = 13
    tid = xi // tuft_p
    trnd = rng.random(int(tid.max()) + 2).astype(np.float32)
    tri = np.abs(((xx + trnd[tid] * 5) % tuft_p) / tuft_p - 0.5) * 2  # 0 at a tuft's tip .. 1 between tufts
    img[m & (fv > 0.80 + 0.17 * (1 - tri) * (0.6 + 0.4 * trnd[tid])), 3] = 0.0
    img[m & (fv > 0.985), 3] = 0.0
    # feathers (cape outside) and the same hem silhouette on the lining
    NFR, NFC = 20, 12
    p = 0.99 / (NFR + 0.6)
    frnd = rng.random((NFR + 2, NFC + 2)).astype(np.float32)

    def field(au, al):
        """Visible feather at (au, al): covered, row, fx (-1..1 across), fy (0 base .. 1 tip), shade."""
        r0 = np.floor(al / p).astype(np.int32)
        best = [np.zeros(au.shape, bool), np.zeros(au.shape, np.int32), np.zeros(au.shape, np.float32),
                np.zeros(au.shape, np.float32), np.zeros(au.shape, np.float32)]
        for r in (r0, r0 - 1):  # the upper row lies over the lower: written last
            ok = (r >= 0) & (r < NFR)
            cu = au * NFC + 0.5 * (r % 2)
            ci = np.clip(np.floor(cu).astype(np.int32), 0, NFC + 1)
            fx = (cu % 1.0) * 2 - 1
            fy = (al - r * p) / (1.6 * p)
            wdt = 1.15 * np.sin(np.pi * np.clip(fy, 0, 1) ** 0.8)
            inside = ok & (fy >= 0) & (fy <= 1) & (np.abs(fx) < wdt)
            sh = frnd[np.clip(r, 0, NFR + 1), ci]
            for k, val in enumerate((True, r, fx, fy, sh)):
                best[k] = np.where(inside, val, best[k])
        return best

    for box, is_cape in ((CAPE_UV, True), (LINING_UV, False)):
        reg = (u >= box[0]) & (u <= box[2]) & (v >= box[1]) & (v <= box[3])
        au = np.clip((u - box[0]) / (box[2] - box[0]), 0, 1)
        al = np.clip((box[3] - v) / (box[3] - box[1]), 0, 1)  # 0 top .. 1 hem
        cov, row, fx, fy, sh = field(au, al)
        dark = K(0.085, 0.085, 0.095)
        col = dark[None, None, :] * (0.75 + 0.5 * sh)[..., None]
        col = np.where(((row % 5) == 3)[..., None], GARNET[None, None, :] * (0.8 + 0.4 * sh)[..., None], col)
        col = np.where(((row == NFR - 1) & (fy > 0.65))[..., None], GARNET[None, None, :] * 1.2, col)
        barbs = 0.72 + 0.28 * np.sin(fy * 55 - np.abs(fx) * 16)
        rim = 0.55 + 0.45 * (1 - np.clip(np.abs(fx), 0, 1) ** 4)
        col = col * (barbs * rim)[..., None]
        shaft = np.abs(fx) < 0.06
        col = np.where(shaft[..., None], K(0.52, 0.50, 0.46)[None, None, :] * (1 - 0.5 * fy)[..., None], col)
        hem = al > (NFR - 1) * p  # below the last row's quills: only feathers, nothing between them
        if is_cape:
            m = reg & cov
            img[m, :3] = col[m]
            props[m, 1] = 0.3
        else:  # lining: garnet-dyed hide; the hem's feather tips show their dark undersides
            n = rng.random((H, WD)).astype(np.float32)
            m = reg
            img[m, :3] = K(0.30, 0.055, 0.055) * (0.8 + 0.3 * n[m])[:, None]
            edge = np.minimum(au, 1 - au)
            b = reg & (edge > 0.015) & (edge < 0.045)
            img[b, :3] = BRONZE
            props[b, 1] = 0.5
            zz = 0.81 + 0.02 * (np.abs((au * 14) % 1.0 - 0.5) * 2 - 0.5)
            img[reg & (np.abs(al - 0.81) < 0.025) & (edge > 0.05), :3] = C_BLACK
            img[reg & (np.abs(al - zz) < 0.006) & (edge > 0.05), :3] = C_BONE
            m = reg & hem & cov
            img[m, :3] = col[m] * 0.8
        img[reg & hem & ~cov, 3] = 0.0
    img[v < 0.025, 3] = 0.0  # the hem's edge faces sample here: keep them invisible
    normal = np.zeros((H, WD, 4), np.float32)
    normal[..., 0] = normal[..., 1] = normal[..., 3] = 0.5
    return {"diffuse": np.clip(img, 0, 1), "normal": normal, "properties": props}


MATS = {SET: make_material("ek2lc_reach_hide", save_set(SET, make_textures())),
        WSET: make_material("ek2lc_reach_war", save_set(WSET, make_war_textures())),
        ASET: make_material("ek2lc_reach_armour", save_set(ASET, make_armour_textures())),
        FSET: make_material("ek2lc_reach_fine", save_set(FSET, make_textures("fine"))),
        RSET: make_material("ek2lc_reach_royal", save_set(RSET, make_textures("royal")))}
for _t, _set in ROYAL_SETS.items():
    MATS[_set] = make_material("ek2lc_reach_" + _t, save_set(_set, make_royal_textures(_t)))
MATS[MSET] = make_material("ek2lc_reach_mantle", save_set(MSET, make_mantle_textures()))

# Culture variants: only the diffuse differs (normal and properties maps are the Reach ones),
# so only it is made, once (in the male run). PNGs go to an ignored folder; they're rebuilt here.
REACH_SET = {"hide": SET, "fine": FSET, "royal": RSET, "war": WSET, "armour": ASET, "mantle": MSET, **ROYAL_SETS}
CULT_PNG = os.path.join(TEXSRC, "cultures")
TEX_FNS = [("hide", make_textures), ("fine", lambda: make_textures("fine")), ("royal", lambda: make_textures("royal")),
           ("war", make_war_textures), ("armour", make_armour_textures), ("mantle", make_mantle_textures),
           ("duke", lambda: make_royal_textures("duke")), ("king", lambda: make_royal_textures("king")),
           ("emperor", lambda: make_royal_textures("emperor"))]


def save_diffuse(set_name, arr):
    """A diffuse-only set: PNG in CULT_PNG, DXT5 .dds with every mip level."""
    png = os.path.join(CULT_PNG, set_name + "_diffuse.png")
    im = bpy.data.images.new("tmp_" + set_name, arr.shape[1], arr.shape[0], alpha=True)
    im.pixels.foreach_set(np.ascontiguousarray(np.flipud(arr), dtype=np.float32).ravel())
    im.filepath_raw, im.file_format = png, "PNG"
    im.save()
    bpy.data.images.remove(im)
    subprocess.run([MAGICK, png, "-define", "dds:compression=dxt5", "-define", "dds:mipmaps=%d" % int(math.log2(arr.shape[0])),
                    os.path.join(OUT, set_name + "_diffuse.dds")], check=True)


if SEX == "male":
    os.makedirs(CULT_PNG, exist_ok=True)
    for _c, _cd in CULTURES.items():
        set_culture(_cd["pal"])
        for _k, _fn in TEX_FNS:
            save_diffuse("ek2lc_%s_%s_01" % (_c, _k), _fn()["diffuse"])
        print("CULTURE textures", _c)
    set_culture({})


# ------------------------------------------------------------------ make, export and check every piece
def export(obj, path, as_bs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.io_pdx_mesh.export_mesh(filepath=path, chk_mesh=True, chk_skel=not as_bs, chk_locs=False,
                                     chk_selected=True, chk_mesh_blendshape=as_bs)


def write_asset(name, mesh, tset, nset=None):
    """Entity `name` showing `mesh` (and its body-shape meshes) with texture set `tset`
    (its normal and properties maps from set `nset`, if given)."""
    nset = nset or tset
    node = mesh + "Shape"
    bs_lines = "\n".join('\tblend_shape = { id = "%s_bs_%s"\ttype = "%s_bs_%s.mesh" }' % (name, s, mesh, s) for s in SHAPES)
    attr_lines = "\n".join('\tattribute = { name = "%s"\tblend_shape = "%s_bs_%s" }' % (SHAPE_ATTR[s], name, s) for s in SHAPES)
    text = f"""pdxmesh = {{
	name = "{name}_mesh"
	file = "{mesh}.mesh"
{bs_lines}

	meshsettings = {{
		name = "{node}"
		index = 0
		texture_diffuse = "{tset}_diffuse.dds"
		texture_normal = "{nset}_normal.dds"
		texture_specular = "{nset}_properties.dds"
		shader = "portrait_attachment_alpha_to_coverage"
		shader_file = "gfx/FX/jomini/portrait.shader"
	}}
}}

entity = {{
	name = "{name}_entity"
	pdxmesh = "{name}_mesh"
{attr_lines}
}}
"""
    with open(os.path.join(OUT, name + ".asset"), "w") as f:
        f.write(colour.patch_asset(text, name, tset, tset))  # recolouring; tools/make_colour.py shares masks


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
        for corner, l in enumerate(f.loops):
            u, v = pc["loop_uvs"][f.index][corner] if "loop_uvs" in pc else pc["uvs"][l.vert.index]
            if f.index in pc["wrap"] and l.vert.index in pc["wrap_u"]:
                u = pc["wrap_u"][l.vert.index]
            l[uvl].uv = (u, v)
        f.smooth = True
    # All morphs must use the basis mesh's diagonals and vertex order.
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
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
    write_asset(name, name, tset)
    for s in ALL:  # poke-through check: points inside the body, per body shape
        inside, worst = 0, 1e9
        for p in pc["pos"][s]:
            loc, nor, fi, d = BVH[s].find_nearest(p)
            sd = (p - loc).dot(nor)
            worst = min(worst, sd)
            inside += sd < 0
        print("CLEARANCE %s %-10s inside=%d min=%.2f" % (name, s, inside, worst))
        if (name == NAME and s in ("khadigi", "infant", "dwarf")) or name in STRICT:
            assert inside == 0, "%s still penetrates the body on shape %s" % (name, s)
    return obj


# ------------------------------------------------------------------ trophy belt (extra, both bodies)
# Trophies on sinew cords tied over the cord belt; the better the fighter, the more of them
# (tiers 1-3 by prowess, chosen in the game scripts). They hang in the gaps between the
# front/back flaps and the hips (the hips belong to the war trophies, the armoured strips and
# the royal ornaments), so they go with every look. Drawn only while one of our loincloths is
# worn (its tag; gen_script_files.py). Bone, claw and sinew from the war texture.
# (angle from the front, kind, length, bone beads under the belt, extra offset from the skin,
# beads on the cord where it crosses the belt).
# Room below the belt: 46-56 degrees (front flap edge to the armoured strips) and 125-136 (strips
# to the back flap; 133 clears the women's strips too), one trophy each per side; the hips belong to the war trophies, the
# armoured strips and the royal ornaments. So the belt grows 2 -> 4 trophies, then beads on the
# cords over the belt (longer trophies would reach the flaps and strips). Built last: each trophy is pushed out until it clears every other piece by
# TROPHY_GAP on every body shape.
TROPHY_TIERS = {1: [(53, "tooth", 3.0, 1, 0.0, 0)],
                2: [(53, "tooth", 3.2, 1, 0.0, 0), (133, "claw", 3.2, 1, 0.0, 0)],
                3: [(53, "tooth", 3.2, 1, 0.0, 2), (133, "claw", 3.2, 1, 0.0, 0)]}  # back: the women's strips leave no room over the belt
TROPHY_GAP = 0.3
# EK2's draugr body (its undead; EK2's Reach briarhearts get it at 0.5) is so thin at the hips that the
# flaps, which keep their width in cm, reach into the trophies' gaps, and pushing the trophies out
# barely helps there. So in their draugr blend shape only, the trophies get a place of their own:
# turned round the body and pushed out, the least that clears every piece and the body by TROPHY_GAP
# on the draugr shape at 1.0 and 0.5 (REFIT_PURE, a must) and on each mix of it with another body
# shape at 1.0 (the rest of REFIT_MIXES) by as much as any place can (_MIXGAPS). The pieces themselves
# are only fitted shape by shape: on some mixes the flaps and armoured strips close in on the front
# trophies with belt beads so far that no place clears them by TROPHY_GAP. Every other shape keeps
# the trophies where they were.
REFIT = "draugr"
OWN = [s for s in ALL if s != REFIT]
REFIT_MIXES = [{REFIT: w} for w in (1.0, 0.5)] + [{REFIT: w, x: 1.0} for w in (1.0, 0.5) for x in SHAPES if x != REFIT]
REFIT_PURE = [i for i, ws in enumerate(REFIT_MIXES) if len(ws) == 1]


def mix(pos, ws):
    """Positions (n x 3 array) on a mix of body shapes, as the game blends them: the basis plus each
    shape's weighted offset from it."""
    b = np.array([tuple(p) for p in pos["basis"]])
    res = b.copy()
    for s, w in ws.items():
        res += w * (np.array([tuple(p) for p in pos[s]]) - b)
    return res


def mix_bvhs(obst):
    """obst: [(name, positions per shape, faces)] -> per REFIT mix, [(name, BVH)]."""
    return [[(n, BVHTree.FromPolygons(mix(pos, ws).tolist(), faces)) for n, pos, faces in obst] for ws in REFIT_MIXES]


def refit_gap(pos, vi, bvhs, stop=None, only=None):
    """Closest of points vi of a piece (positions per shape) to the obstacles over the REFIT mixes (or
    those indexed by only), as (gap, obstacle, mix); returns at the first gap under stop."""
    best = (1e9, None, None)
    for k, (ws, row) in enumerate(zip(REFIT_MIXES, bvhs)):
        if only is not None and k not in only:
            continue
        pts = mix(pos, ws)[vi]
        for n, bvh in row:
            d = min(bvh.find_nearest(Vector(p))[3] for p in pts)
            if d < best[0]:
                best = (d, n, ws)
                if stop is not None and d < stop:
                    return best
    return best


_TOBST = [o for o in PIECES if "band" not in o["name"] and "mantle" not in o["name"]]
_OBVH = [BVHTree.FromPolygons(o["pos"][s], [list(f) for f in o["faces"]]) for o in _TOBST for s in OWN]
_OBVH_S = [(o["name"], s) for o in _TOBST for s in OWN]
_TMIX = mix_bvhs([(o["name"], o["pos"], [list(f) for f in o["faces"]]) for o in _TOBST] +
                 [("body", COORDS, [list(t) for t in TRIS["basis"]])])
_R0 = (recon(skin_bind(math.radians(53), BELT_Z - 3.0, 0.0), "basis") - Vector((0, center_y(BELT_Z - 3.0), BELT_Z - 3.0))).length
# (cost in cm, turn in degrees (+: towards the back), push out in cm), least first
_RCANDS = sorted((math.hypot(_R0 * math.radians(da), do), da, float(do)) for da in np.arange(-20.0, 20.01, 0.5) for do in np.arange(0.0, 4.01, 0.125))
_MIXGAPS = (TROPHY_GAP, 0.2, 0.1, 0.05, 0.02, 0.0)  # the gap wanted on the mixes, most first (0: the pure shapes only)
_MIXPUSH = 3.0  # the most push out for a gap on the mixes (further, the trophy hangs off the belt)
# the mixes with shapes anyone may have (age, weight, health, prowess, breasts), then the rest
_COMMON = {"fat", "gaunt", "muscular", "old", "breast_max", "breast_min"}
_MIXGROUPS = [[k for k, ws in enumerate(REFIT_MIXES) if len(ws) > 1 and bool(set(ws) & _COMMON) == c] for c in (True, False)]
_SHRINK = ((1.0, 1.0), (1.0, 0.6), (1.0, 0.3), (0.8, 0.6), (0.8, 0.3), (0.8, 0.1))  # (tooth length, belt bead size)


def trophy_item(side, ang, kind, length, beads, out, belt_beads=0, ubead=1.0):
    """One trophy (cord, bone beads, tooth or claw) as (bind, uvs, faces, parts); faces index this item only.
    ubead scales the beads over the belt (the same vertices at any scale)."""
    tb, tu, tf, tp = [], [], [], []
    tgt = (tb, tu, tf, tp)
    th0 = side * math.radians(ang)
    bt = BELT_Z - 2.3
    add_tube(th0, [(0, BELT_Z + 3.0, 0.6), (0, BELT_Z + 1.9, 2.4 + out), (0, BELT_Z - 1.9, 2.4 + out), (0, bt, 1.6 + out)],
             [0.14] * 4, 1.0, CORD_UV, "c", tgt=tgt)
    for j in range(belt_beads):  # over the cord belt (it spans BELT_Z +-1.7, outer surface ~1.4 cm out)
        z0 = BELT_Z + 1.3 - 1.4 * j
        add_tube(th0, [(0, z0, 2.4 + out), (0, z0 - 0.5, 2.4 + out), (0, z0 - 1.0, 2.4 + out)], [r * ubead for r in (0.45, 0.6, 0.45)], 1.0,
                 BONE_UV, "u%d" % j, tgt=tgt)
    for j in range(beads):
        z0 = bt - 1.2 * j
        add_tube(th0, [(0, z0, 1.6 + out), (0, z0 - 0.5, 1.6 + out), (0, z0 - 1.0, 1.6 + out)], [0.42, 0.55, 0.42], 1.0,
                 BONE_UV, "b%d" % j, tgt=tgt)
    bb = bt - 1.2 * beads + 0.2
    if kind == "tooth":
        path = [(0, bb, 1.4 + out), (0, bb - length * 0.35, 1.35 + out), (0, bb - length * 0.7, 1.2 + out), (0, bb - length, 1.0 + out)]
        add_tube(th0, path, [0.45, 0.42, 0.26, 0], 0.6, BONE_UV, "t", cap_tip=True, tgt=tgt)
    else:  # claw: curls outwards at the tip
        path = [(0, bb, 1.4 + out), (0, bb - length * 0.4, 1.55 + out), (0, bb - length * 0.75, 1.95 + out), (0, bb - length, 2.6 + out)]
        add_tube(th0, path, [0.4, 0.34, 0.2, 0], 0.55, CLAW_UV, "t", cap_tip=True, tgt=tgt)
    return tgt


def trophy_gap(item):
    """Closest bead/tooth/claw point to any other piece on any body shape but REFIT (cords pass over the belt on purpose)."""
    tb, tu, tf, tp = item
    vi = sorted({i for f, prt in zip(tf, tp) if prt != "c" for i in f})
    return min((bvh.find_nearest(recon(tb[i], ns[1]))[3], ns) for bvh, ns in zip(_OBVH, _OBVH_S) for i in vi)


TROPHY = {}
for _tier, _items in TROPHY_TIERS.items():
    _fit = {}  # (side, item index) -> (item, out, gap, positions per shape)
    for _j, (ang, kind, length, beads, out0, belt_beads) in enumerate(_items):
        for side in (1, -1):
            out = out0
            for _try in range(8):
                item = trophy_item(side, ang, kind, length, beads, out, belt_beads)
                gap, near = trophy_gap(item)
                if gap >= TROPHY_GAP:
                    break
                out += TROPHY_GAP - gap + 0.05
            assert gap >= TROPHY_GAP, "tier %d trophy at %d deg can't clear: gap %.2f to %s on %s (out %.2f)" % (
                _tier, ang, gap, near[0], near[1], out)
            _fit[side, _j] = (item, out, gap, {s: [recon(b, s) for b in item[0]] for s in OWN})
        # the draugr blend shape, each side on its own (the pieces round it aren't mirror images)
        for sd in (1, -1):
            _vi = sorted({i for f, prt in zip(_fit[sd, _j][0][2], _fit[sd, _j][0][3]) if prt != "c" for i in f})
            # the least move that clears the pure shapes by TROPHY_GAP, then the mixes with the shapes anyone
            # may have by as much as any place within _MIXPUSH can (_MIXGAPS, most first), then the rest
            # likewise; smaller beads over the belt, then a shorter tooth, only where they buy more
            def _search(want):
                maxdo = _MIXPUSH if any(g > 0 for idx, g in want) else 1e9
                for lf, ub in _SHRINK if belt_beads else ((1.0, 1.0),):
                    for cost, da, do in _RCANDS:
                        if do > maxdo:
                            continue
                        _rp = [recon(b, REFIT) for b in trophy_item(sd, ang + da, kind, length * lf, beads, _fit[sd, _j][1] + do, belt_beads, ub)[0]]
                        _rpos = dict(_fit[sd, _j][3], **{REFIT: _rp})
                        if (refit_gap(_rpos, _vi, _TMIX, TROPHY_GAP, REFIT_PURE)[0] >= TROPHY_GAP
                                and all(g == 0 or refit_gap(_rpos, _vi, _TMIX, g, idx)[0] >= g for idx, g in want)):
                            return (da, do, lf, ub, _rp, _rpos)
                return None
            _want, _pick = [], None
            for idx in _MIXGROUPS:
                for g in _MIXGAPS:
                    _p = _search(_want + [(idx, g)])
                    if _p is not None:
                        _want.append((idx, g))
                        _pick = _p
                        break
            assert _pick is not None, "tier %d trophy at %+d deg can't clear on %s" % (_tier, sd * ang, REFIT)
            da, do, lf, ub, _rp, _rpos = _pick
            _fit[sd, _j][3][REFIT] = _rp
            _gp, _ga = refit_gap(_rpos, _vi, _TMIX, None, REFIT_PURE), refit_gap(_rpos, _vi, _TMIX)
            _gc, _gr = (refit_gap(_rpos, _vi, _TMIX, None, idx)[0] for idx in _MIXGROUPS)
            print("TROPHY tier %d at %+4d deg on %s: turn %+.1f deg, out %+.2f, length x%.1f, belt beads x%.1f, gap %.2f alone (to %s on %s), "
                  "%.2f on mixes with fat/gaunt/muscular/old/breasts, %.2f on the rest (to %s on %s)" % (
                      _tier, sd * ang, REFIT, da, do, lf, ub, _gp[0], _gp[1], _gp[2], _gc, _gr, _ga[1], _ga[2]))
    tb, tu, tf, tp = [], [], [], []
    _pos = {s: [] for s in ALL}
    k = 0
    for side in (1, -1):
        for _j, (ang, kind, length, beads, out0, belt_beads) in enumerate(_items):
            item, out, gap, ipos = _fit[side, _j]
            b0 = len(tb)
            tb += item[0]
            tu += item[1]
            tf += [[i + b0 for i in f] for f in item[2]]
            tp += ["%s%02d" % (prt, k) for prt in item[3]]
            for s in ALL:
                _pos[s] += ipos[s]
            print("TROPHY tier %d at %+4d deg: %s, out %.2f, gap %.2f" % (_tier, side * ang, kind, out, gap))
            k += 1
    _ctr = {}
    for f, p in zip(tf, tp):
        _ctr.setdefault(p, []).extend(_pos["basis"][i] for i in f)
    _orient = [(p, (lambda c0: (lambda c: c - c0))(sum(ps, Vector()) / len(ps)), None) for p, ps in _ctr.items()]
    TROPHY[_tier] = "ek2lc_%s_trophy_%d_01" % (S1, _tier)
    PIECES.append(dict(name=TROPHY[_tier], set=WSET, pos=_pos, faces=tf, part=tp, wrap=set(), wrap_u={}, uvs=tu,
                       vw=[weights_at(b[0], b[1]) for b in tb], orient=_orient))
    print("TROPHY tier %d: %d vertices, %d trophies" % (_tier, len(tb), k))


# ------------------------------------------------------------------ arena shoulder guard (extra, both bodies)
# One guard on the left shoulder for tournament fighters, like a gladiator's galerus: three
# overlapping hide lames faced with bone (the armoured skirt's texture), the top one capping the
# shoulder, and a strap round the upper arm below them. No chest strap: it would fight the
# women's chest band. Every point is bound to the skin of the shoulder and upper arm and takes
# that skin's weights, so the guard follows the arm in every pose and on every body shape.
GUARD = "ek2lc_%s_arena_guard_01" % S1
_SJ = rig.matrix_world @ rig.data.bones["bn_l_shoulder"].head_local
_SE = rig.matrix_world @ rig.data.bones["bn_l_elbow"].head_local
ARM_AX = (_SE - _SJ).normalized()  # down the upper arm (the rest pose is an A-pose)
ARM_O = (UP - ARM_AX * UP.dot(ARM_AX)).normalized()  # the arm's upper outer side
ARM_F = (FRONT - ARM_AX * FRONT.dot(ARM_AX) - ARM_O * FRONT.dot(ARM_O)).normalized()


def arm_hit(sa, phi):
    """Skin of the shoulder and upper arm: sa cm down the arm from the shoulder joint (negative: over
    the shoulder top, a dome round the joint, 8 degrees per cm), phi degrees round the arm from its
    upper outer side (positive: to the front). Rays start inside, on the arm's axis."""
    rad = ARM_O * math.cos(math.radians(phi)) + ARM_F * math.sin(math.radians(phi))
    if sa < 0:
        t = math.radians(-sa * 8.0)
        org, d = _SJ, rad * math.cos(t) - ARM_AX * math.sin(t)
    else:
        org, d = _SJ + ARM_AX * sa, rad
    loc, nor, fi, dist = BVH["basis"].ray_cast(org, d, 40)
    assert loc is not None, "no shoulder skin at %.1f cm, %d deg" % (sa, phi)
    return loc, fi


def slab(B, U, F, P, wrap, wrap_u, hits, offs, uv, tag, closed=False, u_end=None):
    """A plate or strap: two skin-bound grids (outer and inner offset; hits[row][col] = (loc, face))
    and its edges. uv(layer, row, col) -> (u, v). closed: round the arm (the seam faces get u_end)."""
    b0 = len(B)
    R, C = len(hits), len(hits[0])
    for layer, o_ in enumerate(offs):
        for i, row in enumerate(hits):
            for j, (loc, fi) in enumerate(row):
                B.append(bind(loc, fi, o_))
                U.append(uv(layer, i, j))
    V = lambda layer, i, j: b0 + layer * R * C + i * C + j % C  # noqa: E731
    jn = C if closed else C - 1
    for j in range(jn):
        seam = closed and j == C - 1
        for i in range(R - 1):
            for q in ([V(0, i, j), V(0, i, j + 1), V(0, i + 1, j + 1), V(0, i + 1, j)], [V(1, i, j), V(1, i + 1, j), V(1, i + 1, j + 1), V(1, i, j + 1)]):
                if seam:
                    wrap.add(len(F))
                F.append(q)
                P.append(tag + ("o" if q[0] < b0 + R * C else "i"))
        for i in (0, R - 1):  # top and bottom edges
            if seam:
                wrap.add(len(F))
            F.append([V(0, i, j), V(1, i, j), V(1, i, j + 1), V(0, i, j + 1)])
            P.append(tag + "e")
    if closed:
        for layer in range(2):
            for i in range(R):
                wrap_u[V(layer, i, 0)] = u_end
    else:
        for j in (0, C - 1):  # the side edges
            for i in range(R - 1):
                F.append([V(0, i, j), V(0, i + 1, j), V(1, i + 1, j), V(1, i, j)])
                P.append(tag + "e")


# (first and last row, cm down the arm; half span round the arm, degrees; outer offset from the skin;
# texture v of the bone bar it shows). Each lame overlaps the next by a centimetre, outside it.
LAMES = [(-5.5, 3.5, 100, 1.6, 0.31), (2.5, 7.0, 92, 1.1, 0.20), (6.0, 11.5, 84, 0.6, 0.093)]
L_THICK = 0.25
G_STRAP = (12.2, 14.2, 0.55, 0.3)  # rows, outer offset, thickness (higher, it touched the girls' chest band)
gb, guv, gf, gp, gwrap, gwu = [], [], [], [], set(), {}
for k, (s0, s1, span, off, vb) in enumerate(LAMES):
    rows = list(np.linspace(s0, s1, max(3, round(s1 - s0) + 1)))
    cols = list(np.linspace(-span, span, round(2 * span / 10) + 1))
    R_, C_ = len(rows), len(cols)
    slab(gb, guv, gf, gp, gwrap, gwu, [[arm_hit(sa, phi) for phi in cols] for sa in rows], (off, off - L_THICK),
         (lambda vb_, R_, C_: lambda layer, i, j: (0.085 + 0.83 * j / (C_ - 1), vb_ + 0.065 - 0.13 * i / (R_ - 1)) if layer == 0
          else (0.15 + 0.7 * j / (C_ - 1), 0.42 - 0.06 * i / (R_ - 1)))(vb, R_, C_), "l%d" % k)
_srows = list(np.linspace(G_STRAP[0], G_STRAP[1], 3))
_scols = [360.0 * j / 36 for j in range(36)]
slab(gb, guv, gf, gp, gwrap, gwu, [[arm_hit(sa, phi) for phi in _scols] for sa in _srows], (G_STRAP[2], G_STRAP[2] - G_STRAP[3]),
     lambda layer, i, j: (0.4 * j / 36, 0.895 - 0.045 * i), "st", closed=True, u_end=0.4)
GPOS = {s: [recon(b, s) for b in gb] for s in ALL}
_away = lambda c: c - (_SJ + ARM_AX * max(0.0, (c - _SJ).dot(ARM_AX)))  # noqa: E731
G_ORIENT = [(t, _away, t + "o") for t in ["l%d" % k for k in range(len(LAMES))] + ["st"]]
PIECES.append(dict(name=GUARD, set=ASET, pos=GPOS, faces=gf, part=gp, wrap=gwrap, wrap_u=gwu, uvs=guv,
                   vw=[weights_at(b[0], b[1]) for b in gb], orient=G_ORIENT))
print("GUARD %d vertices, %d faces, arm axis %s" % (len(gb), len(gf), tuple(round(c, 2) for c in ARM_AX)))


# ------------------------------------------------------------------ camp follower's wrap (extra, both bodies)
# Plain, patched cloth for the people who travel with armies: a sash wound round the waist where the
# war girdle sits (the girdle's shape; the game hides the wrap under any girdle by tag), knotted at
# the left hip with two short tails hanging down the thigh, and a small cloth bundle on a cord at the
# right hip. Own texture: undyed wool with patches.
WRAP = "ek2lc_%s_camp_wrap_01" % S1
CSET = "ek2lc_camp_01"
cb, cuv = list(war_bind[:NGV]), list(WUVS[:NGV])
cf, cp, cwrap = [list(f) for f in GFACES], ["sash"] * len(GFACES), set(AWRAP)
KNOT_UV, POUCH_UV, TAIL_UV = (0.53, 0.27, 0.97, 0.48), (0.53, 0.02, 0.97, 0.23), (0.03, 0.02, 0.47, 0.48)
_ct = (cb, cuv, cf, cp)
_kz = BELT_Z + 4.5  # the knot, over the sash's middle at the left hip
add_tube(math.pi / 2, [(0, _kz + 2.0, 1.4), (0, _kz + 1.0, 2.1), (0, _kz, 2.4), (0, _kz - 1.0, 2.1), (0, _kz - 2.0, 1.4)],
         [0.5, 1.4, 1.65, 1.4, 0.5], 0.7, KNOT_UV, "knot", tgt=_ct)
# the bundle: a cord from the sash over the cord belt, then a flat cloth bag pushed clear of the body and loincloth
# (on the draugr, pushed further in its own blend shape if it must be, as the trophies)
_PB = [BVHTree.FromPolygons(*with_leggings(s, COORDS[s] + POS[s], [list(t) for t in TRIS[s]] +
                                           [[i + len(COORDS[s]) for i in f] for f in FACES])) for s in OWN]
_pz, _pout = BELT_Z - 2.4, 1.85


def bundle(out):
    pt, ct = ([], [], [], []), ([], [], [], [])
    add_tube(-math.pi / 2, [(0, BELT_Z + 3.0, 0.6), (0, BELT_Z + 1.9, 2.4), (0, BELT_Z - 1.9, 2.4), (0, _pz + 0.3, out)],
             [0.2] * 4, 1.0, KNOT_UV, "cord", tgt=ct)
    add_tube(-math.pi / 2, [(0, _pz, out), (0, _pz - 1.0, out), (0, _pz - 3.0, out), (0, _pz - 5.5, out), (0, _pz - 6.8, out)],
             [0.55, 1.8, 2.6, 2.3, 0], 0.55, POUCH_UV, "pouch", cap_tip=True, tgt=pt)
    return ct, pt


for _try in range(8):
    _bct, _pt = bundle(_pout)
    _pgap = min(bvh.find_nearest(recon(b, s))[3] for bvh, s in zip(_PB, OWN) for b in _pt[0])
    if _pgap >= 0.3:
        break
    _pout += 0.3 - _pgap + 0.05
assert _pgap >= 0.3, "bundle can't clear the body: gap %.2f" % _pgap
_PMIX = mix_bvhs([("body and loincloth", {s: COORDS[s] + POS[s] for s in ALL},
                   [list(t) for t in TRIS["basis"]] + [[i + len(C0) for i in f] for f in FACES])])
_bown = {s: [recon(b, s) for b in _bct[0] + _pt[0]] for s in OWN}
_nbc = len(_bct[0])
_bpick = None  # as the trophies: the pure shapes must clear, every mix if some push can
for _pdo in np.arange(0.0, 3.01, 0.1):
    _bct2, _pt2 = bundle(_pout + _pdo)
    _brefit = [recon(b, REFIT) for b in _bct2[0] + _pt2[0]]
    _bpos = dict(_bown, **{REFIT: _brefit})
    _bvi = list(range(_nbc, len(_brefit)))
    if refit_gap(_bpos, _bvi, _PMIX, 0.3, REFIT_PURE)[0] < 0.3:
        continue
    if _bpick is None:
        _bpick = (_pdo, _brefit, _bpos)
    if refit_gap(_bpos, _bvi, _PMIX, 0.3)[0] >= 0.3:
        _bpick = (_pdo, _brefit, _bpos)
        break
assert _bpick is not None, "bundle can't clear the body on %s" % REFIT
_pdo, _brefit, _bpos = _bpick
_pg, _pgp = refit_gap(_bpos, _bvi, _PMIX), refit_gap(_bpos, _bvi, _PMIX, None, REFIT_PURE)
_BUNDLE0 = len(cb)  # its cord and bag, in that order; the draugr shape's positions are _brefit
for _t in (_bct, _pt):
    _o = len(cb)
    cb += _t[0]
    cuv += _t[1]
    cf += [[i + _o for i in f] for f in _t[2]]
    cp += _t[3]
print("WRAP bundle out %.2f, gap %.2f; on %s out %+.2f, gap %.2f alone, %.2f on mixes (%s)" % (
    _pout, _pgap, REFIT, _pdo, _pgp[0], _pg[0], _pg[2]))
NGC = len(cb)  # skin-bound vertices; the tails follow
# tails: flat cloth hanging straight from under the knot, as far out as anything above them needs
TAILS = [(84, 1.7, [4.0, 2.1, 0.0, -1.9, -5.0, -9.0, -12.5]), (97, 1.5, [4.0, 2.1, 0.0, -1.9, -5.0, -8.5, -10.0])]
T_CLEAR = [0.35, 0.55, 0.7, 0.7, 0.8, 0.8, 0.8]
T_COLS, T_THICK = 3, 0.2


def tail_positions(s):
    out = []
    for ang, hw, zs_ in TAILS:
        th = math.radians(ang)
        d, t = s_frame(th)
        xs = [(c / (T_COLS - 1) - 0.5) * 2 * hw for c in range(T_COLS)]
        z_top = BELT_Z + zs_[0]
        rows = []
        for r_, (dz, clear) in enumerate(zip(zs_, T_CLEAR)):
            z = BELT_Z + dz
            z_lo = BELT_Z + zs_[r_ + 1] if r_ + 1 < len(zs_) else z - 0.6  # down to the next row too (see strip_positions)
            zz_ = list(np.arange(z_lo, z_top + 2.6, 0.5))
            h = max(s_out(s, th, x + dx, zz) for x in xs for dx in (-0.6, 0.0, 0.6) for zz in zz_) + clear
            rows.append([S_BASE + t * x + d * h + UP * z for x in xs])
        out += [p for row in rows for p in row]
        out += [p - d * T_THICK for row in rows for p in row]
    return out


TPOS = {s: tail_positions(s) for s in ALL}
CPOS = {s: [recon(b, s) for b in cb] + TPOS[s] for s in ALL}
CPOS[REFIT][_BUNDLE0:_BUNDLE0 + len(_brefit)] = _brefit
cvw = [weights_at(b[0], b[1]) for b in cb]
NTR = len(T_CLEAR)
for k, (ang, hw, zs_) in enumerate(TAILS):
    b0 = NGC + k * 2 * NTR * T_COLS
    _lb_thigh = leg_bind(math.radians(ang), BELT_Z - 10.0, 0.0)
    for layer in range(2):
        for r in range(NTR):
            for c in range(T_COLS):
                cuv.append((TAIL_UV[0] + (TAIL_UV[2] - TAIL_UV[0]) * (0.5 * k + 0.5 * c / (T_COLS - 1)),
                            TAIL_UV[3] - (TAIL_UV[3] - TAIL_UV[1]) * r / (NTR - 1)))
                k_ = (0.0, 0.0, 0.0, 0.25, 0.6)[r] if r < 5 else 1.0  # on the sash: with the skin; lower: the skirt chains
                p_ = CPOS["basis"][b0 + layer * NTR * T_COLS + r * T_COLS + c]
                skin = dict(nearest_weights(p_))
                # half with the thigh under it (it carries the strip in a stride), half with the skirt chain (it
                # swings it clear when the legs spread or bend): the scan in Blender found either alone let the
                # leggings or the hands through (2026-11-07)
                stiff = {}
                for g, w in list(weights_at(*_lb_thigh[:2])) + [(g, w) for g, w in skirt_weights(ang_of(p_), p_.z).items()]:
                    stiff[g] = stiff.get(g, 0.0) + 0.5 * w
                dd = {}
                for g, w in skin.items():
                    dd[g] = dd.get(g, 0.0) + w * (1 - k_)
                for g, w in stiff.items():
                    dd[g] = dd.get(g, 0.0) + w * k_
                row = [(g, w) for g, w in sorted(dd.items(), key=lambda kv: -kv[1])[:4] if w > 0.01]
                tot = sum(w for _, w in row)
                cvw.append([(g, w / tot) for g, w in row])
    L = lambda layer, r, c: b0 + layer * NTR * T_COLS + r * T_COLS + c  # noqa: E731
    tag = "tail%d" % k
    for r in range(NTR - 1):
        for c in range(T_COLS - 1):
            cf.append([L(0, r, c), L(0, r, c + 1), L(0, r + 1, c + 1), L(0, r + 1, c)])
            cp.append(tag + "o")
            cf.append([L(1, r, c), L(1, r + 1, c), L(1, r + 1, c + 1), L(1, r, c + 1)])
            cp.append(tag + "i")
        for c in (0, T_COLS - 1):
            cf.append([L(0, r, c), L(0, r + 1, c), L(1, r + 1, c), L(1, r, c)])
            cp.append(tag + "e")
    for r in (0, NTR - 1):
        for c in range(T_COLS - 1):
            cf.append([L(0, r, c), L(1, r, c), L(1, r, c + 1), L(0, r, c + 1)])
            cp.append(tag + "e")
C_ORIENT = [("sash", lambda c: Vector((c.x, c.y - W_YC, 0)), None)]
for k in range(len(TAILS)):
    C_ORIENT.append(("tail%d" % k, lambda c: Vector((c.x, c.y - W_YC, 0)), "tail%do" % k))
_cc = {}
for f, p in zip(cf, cp):
    if p in ("knot", "pouch", "cord"):
        _cc.setdefault(p, []).extend(CPOS["basis"][i] for i in f)
for p, ps in _cc.items():
    C_ORIENT.append((p, (lambda c0: (lambda c: c - c0))(sum(ps, Vector()) / len(ps)), None))


def make_camp_textures():
    """Undyed wool, worn and patched: sash (v > .5), tails (u < .5), knot and bundle (u > .5)."""
    H = WD = 512
    rng = np.random.default_rng(31)

    def noise(k):
        g = rng.random((k + 2, k + 2)).astype(np.float32)
        ys = np.linspace(0, k, H, endpoint=False)
        y0 = ys.astype(np.int32)
        f = (ys - y0) * (ys - y0) * (3 - 2 * (ys - y0))
        a, b, c, d = g[np.ix_(y0, y0)], g[np.ix_(y0, y0 + 1)], g[np.ix_(y0 + 1, y0)], g[np.ix_(y0 + 1, y0 + 1)]
        fx, fy = f[None, :], f[:, None]
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

    n = (noise(5) + 0.5 * noise(20) + 0.25 * noise(60)) / 1.75
    n2 = noise(40)
    yy, xx = np.mgrid[0:H, 0:WD].astype(np.float32)
    v = 1 - yy / (H - 1)
    u = xx / (WD - 1)
    weave = 0.93 + 0.07 * np.sin(xx * 2.4) * np.sin(yy * 2.4)
    img = np.ones((H, WD, 4), np.float32)
    img[..., :3] = K(0.58, 0.53, 0.43) * ((0.8 + 0.35 * n) * weave)[..., None]
    # patches: other cloth sewn on with coarse dark thread (u0, v0, u1, v1, colour)
    patches = [(0.06, 0.60, 0.15, 0.86, (0.34, 0.36, 0.40)), (0.33, 0.56, 0.41, 0.80, (0.45, 0.34, 0.22)),
               (0.57, 0.66, 0.68, 0.93, (0.52, 0.44, 0.26)), (0.80, 0.58, 0.88, 0.84, (0.34, 0.36, 0.40)),
               (0.10, 0.18, 0.20, 0.33, (0.45, 0.34, 0.22)), (0.31, 0.06, 0.40, 0.22, (0.52, 0.44, 0.26)),
               (0.62, 0.05, 0.78, 0.14, (0.34, 0.36, 0.40))]
    j = (n2 - 0.5) * 0.012  # wobbly edges
    for u0, v0, u1, v1, col in patches:
        m = (u > u0 + j) & (u < u1 - j) & (v > v0 + j) & (v < v1 - j)
        img[m, :3] = K(*col) * ((0.8 + 0.35 * n[m]) * weave[m])[:, None]
        e = 4.0 / WD
        edge = m & ~((u > u0 + j + e) & (u < u1 - j - e) & (v > v0 + j + e) & (v < v1 - j - e))
        img[edge & (((xx + yy) % 7) < 3), :3] = K(0.20, 0.16, 0.12)
    # sash: soft fold lines along its length
    s = v >= 0.5
    gv = (v - 0.52) / 0.46
    fold = 1 - 0.18 * np.exp(-((((gv * 3.0) % 1.0) - 0.5) / 0.08) ** 2)
    img[s, :3] *= fold[s][:, None]
    # tails: frayed ends at the bottom
    t = (u < 0.5) & (v < 0.06)
    img[t & ((xx % 4) < 2), :3] *= 0.55
    # knot: deep folds
    kn = (u >= 0.5) & (v >= 0.25) & (v < 0.5)
    img[kn, :3] *= (0.75 + 0.25 * np.sin((xx[kn] + yy[kn] * 0.6) * 0.15))[:, None]
    # bundle: the tie near its neck
    b = (u >= 0.5) & (v >= 0.19) & (v < 0.23)
    img[b, :3] = K(0.40, 0.31, 0.21) * (0.75 + 0.3 * np.sin(xx[b] * 0.9 + yy[b] * 0.6))[:, None]
    img[..., :3] *= (0.85 + 0.15 * n2)[..., None]  # dirt
    normal = np.zeros((H, WD, 4), np.float32)
    normal[..., 0] = normal[..., 1] = normal[..., 3] = 0.5
    props = np.zeros((H, WD, 4), np.float32)
    props[..., 1], props[..., 3] = 0.15, 0.65  # dull cloth
    return {"diffuse": np.clip(img, 0, 1), "normal": normal, "properties": props}


MATS[CSET] = make_material("ek2lc_camp", save_set(CSET, make_camp_textures()))
# Undead (undead.py), diffuse only, made once (in the male run): the lich's burial regalia, one set per
# piece type shared by every culture, and each culture's plain loincloth rotted for the other undead.
if SEX == "male":
    for _i, (_k, _fn) in enumerate(TEX_FNS + [("camp", make_camp_textures)]):
        set_culture(LICH["pal"])
        _arr = _fn()["diffuse"]
        set_culture(dict(LICH["pal"], metal=(0.0, 1.0, 0.0)))  # where the metal is: it alone changes
        _metal = np.abs(_fn()["diffuse"][..., :3] - _arr[..., :3]).max(-1) > 0.15
        if _k == "camp":  # undyed wool: no colour roles
            _arr = undead.blacken(_arr)
        save_diffuse("ek2lc_lich_%s_01" % _k, undead.lich_finish(_arr, _metal, 101 + _i))
    for _c, _pal in [("reach", {})] + [(_c, _cd["pal"]) for _c, _cd in CULTURES.items()]:
        set_culture(_pal)
        save_diffuse("ek2lc_%s_grave_01" % _c, undead.grave_rot(make_textures()["diffuse"], 7))
    set_culture({})
    print("UNDEAD textures")
PIECES.append(dict(name=WRAP, set=CSET, pos=CPOS, faces=cf, part=cp, wrap=cwrap, wrap_u={i: 1.0 for i in range(5)}, uvs=cuv,
                   vw=cvw, orient=C_ORIENT))
print("WRAP %d vertices, %d faces" % (len(CPOS["basis"]), len(cf)))
# ------------------------------------------------------------------ wrap skirt, tunic, cold-weather layers, charms
# The user's picks of 2026-11-06, from the history of tribal children's dress:
#  - a hide wrap skirt (girls 7-13, in place of the loincloth, with the chest band): four panels round the hips,
#    tucked under the cord belt and hanging as the flaps do to just above the knee. Each panel uses a flap's
#    area of the hide texture, so every culture's colours, painted band and fringed hem come with it;
#  - a sleeveless tunic (children 4-6, in place of the loincloth): the torso's skin lifted off it (plain hide from
#    the flaps' upper area), over the same skirt and belt;
#  - hide leggings for the cold: each leg's skin from above the ankle to the thigh, lifted off it;
#  - a fur cloak for the winter: the emperor's mantle mesh with a fur texture of its own (no new mesh);
#  - children's charm cords: at each hip a sinew cord over the belt, a quill-wrapped length, shells (right) or
#    a tooth (left), and a fringe tassel.
# Shells keep the body's own triangles and winding (no orient entry), so they need no normal fixing.
_KNEE = rig.matrix_world @ rig.data.bones["bn_l_knee"].head_local
_ANKLE = rig.matrix_world @ rig.data.bones["bn_l_ankle"].head_local
_LSIDE = 1 if (rig.matrix_world @ rig.data.bones["bn_l_hip"].head_local).x > 0 else -1  # bn_l_* is on this side of x
KNEE_V = _nearest_vert(Vector((_KNEE.x, 0, _KNEE.z)) + FRONT * 25)  # the front of the knee, on every shape
_NOARM_T = [list(t) for t in TRIS["basis"] if not _ARMV.intersection(t)]
_NOARM = {s: BVHTree.FromPolygons(COORDS[s], _NOARM_T) for s in ALL}  # the arms hang beside the hips
SK_PANELS, SK_NC, SK_NR, SK_THICK = 4, 9, 15, 0.35
# column angles from the front, towards +x: panel 0 front, 1 the +x side, 2 back, 3 the -x side
SK_ANG = [math.radians(-45 + 90 * p + 90 * i / (SK_NC - 1)) for p in range(SK_PANELS) for i in range(SK_NC)]
SK_UV = [(0.022, 0.478), (0.022, 0.478), (0.522, 0.978), (0.522, 0.978)]  # the flaps' areas, inset: their edges bled light seams
SK_KNEE_GAP = 4.0  # the hem, above the front of the knee


def _dirv(th):
    return FRONT * math.cos(th) + RIGHT * math.sin(th)


_SK_OBST = {s: BVHTree.FromPolygons(*with_leggings(s, COORDS[s], _NOARM_T)) for s in ALL}  # body (no arms) and leggings


def skirt_ring(s):
    """Outer and inner points [row][column] of the skirt on shape s. Each row wraps the outline of the hips and
    legs (leggings included) at its height and down to the next row: their convex hull, so it bridges between
    the legs. Fitted at the sides, where the hands hang (until 2026-11-07 the panels hung straight from the hips'
    widest point there, and in the idles the hands sank into them), and hanging straight from anything above at
    the front and back, as stiff hide does; in between, a blend of the two."""
    dz = (recon(REF[+1], s) - recon(REF[+1], "basis")).z
    za = Z_ATTACH + dz
    zh = COORDS[s][KNEE_V].z + SK_KNEE_GAP
    yc = center_y(BELT_Z + dz, s)
    bvh = _SK_OBST[s]
    zs = [za - (za - zh) * j / (SK_NR - 1) for j in range(SK_NR)]
    step = (za - zh) / (SK_NR - 1)
    o2, n = Vector((0, 0)), len(SK_ANG)
    hull_r = []
    for j, z in enumerate(zs):
        pts = []
        for zz in np.arange(z - (step if j < SK_NR - 1 else 0.0), z + 0.51, 0.5):
            o = Vector((0, yc, zz))
            for k in range(96):
                D = _dirv(2 * math.pi * k / 96)
                hit = bvh.ray_cast(o + D * 200, -D, 400)[0]
                if hit is not None:
                    q = hit - o
                    pts.append(Vector((q.dot(RIGHT), q.dot(FRONT))))
        hull = convex_hull_2d(pts)
        hull_r.append([ray_to_hull(o2, Vector((math.sin(th), math.cos(th))), hull) for th in SK_ANG])
    outer, inner, run = [], [], [-1e9] * n
    for j, z in enumerate(zs):
        t = j / (SK_NR - 1)
        fs = []
        for i, th in enumerate(SK_ANG):
            run[i] = max(run[i], hull_r[j][i])  # hanging straight from anything above
            w = math.cos(th) ** 2  # 1 at the front and back, 0 at the sides
            fs.append(hull_r[j][i] + w * (run[i] - hull_r[j][i]) + 0.6 + 2.4 * t ** 1.2)  # an A-line, as vanilla dresses
        if t > 0.2:  # smooth round the ring, never inwards
            for _ in range(2):
                fs = [max(fs[i], (fs[i - 1] + 2 * fs[i] + fs[(i + 1) % n]) / 4) for i in range(n)]
        # each panel's last column and the next panel's first are at the same angle; the smoothing moved them apart
        # (different neighbours) and left a step between the panels you could see through (Blender, 2026-11-07)
        for p_ in range(SK_PANELS):
            a_, b_ = p_ * SK_NC + SK_NC - 1, ((p_ + 1) % SK_PANELS) * SK_NC
            fs[a_] = fs[b_] = max(fs[a_], fs[b_])
        outer.append([Vector((0, yc, z)) + _dirv(th) * f for th, f in zip(SK_ANG, fs)])
        inner.append([Vector((0, yc, z)) + _dirv(th) * (f - SK_THICK) for th, f in zip(SK_ANG, fs)])
    return outer, inner


_SK_RING = {s: skirt_ring(s) for s in ALL}


def skirt_piece(name, torso=False):
    """The cord belt (as the loincloth's) and the four-panel skirt; with torso, also the tunic's body."""
    pos = {s: [recon(b, s) for b in belt_bind] for s in ALL}
    uvs = [(k / NB, 0.88 + 0.11 * r / 4) for k in range(NB) for r in range(5)]
    faces, part, wrap = [], [], set()
    for k in range(NB):
        k2 = (k + 1) % NB
        for r in range(4):
            if k2 == 0:
                wrap.add(len(faces))
            faces.append([k * 5 + r, k2 * 5 + r, k2 * 5 + r + 1, k * 5 + r + 1])
            part.append("belt")
    vw = [weights_at(b[0], b[1]) for b in belt_bind]
    b0, n = len(uvs), len(SK_ANG)
    for layer in (0, 1):
        for j in range(SK_NR):
            for i in range(n):
                u0, u1 = SK_UV[i // SK_NC]
                uvs.append((u0 + (u1 - u0) * (i % SK_NC) / (SK_NC - 1), 0.74 - 0.73 * j / (SK_NR - 1)))
    for s in ALL:
        outer, inner = _SK_RING[s]
        pos[s] += [p for row in outer for p in row] + [p for row in inner for p in row]
    O = lambda j, i: b0 + j * n + i  # noqa: E731
    I = lambda j, i: b0 + SK_NR * n + j * n + i  # noqa: E731
    yc = center_y(BELT_Z)
    P0_ = pos["basis"]

    def wound(f, want):  # the face turned to face `want` (open panels: recalc_face_normals can't tell)
        a, b, c = P0_[f[0]], P0_[f[1]], P0_[f[2]]
        return f if (b - a).cross(c - a).dot(want) > 0 else f[::-1]

    def outw(f):
        c = sum((P0_[i] for i in f), Vector()) / len(f)
        return Vector((c.x, c.y - yc, 0))

    for p_ in range(SK_PANELS):  # open at their sides: a rim there smoothed light lines into the joins
        for i in range(p_ * SK_NC, p_ * SK_NC + SK_NC - 1):
            for j in range(SK_NR - 1):
                f = [O(j, i), O(j, i + 1), O(j + 1, i + 1), O(j + 1, i)]
                faces.append(wound(f, outw(f)))
                part.append("skirto")
                f = [I(j, i), I(j + 1, i), I(j + 1, i + 1), I(j, i + 1)]
                faces.append(wound(f, -outw(f)))
                part.append("skirti")
            for j, want in ((0, UP), (SK_NR - 1, -UP)):
                faces.append(wound([O(j, i), I(j, i), I(j, i + 1), O(j, i + 1)], want))
                part.append("skirtr")
    # weights: under the belt with the skin, lower down the skirt chains (2026-11-07; was a stiff apron)
    for layer in (0, 1):
        for j in range(SK_NR):
            for i, th in enumerate(SK_ANG):
                p = pos["basis"][O(j, i)]
                if j <= 1:
                    vw.append(nearest_weights(p))
                    continue
                sb = skin_bind(th, max(p.z, BELT_Z - 1.7), 0.0)  # lower down: the skirt chains, as a vanilla skirt
                vw.append(blend_weights(dict(weights_at(sb[0], sb[1])), skirt_weights(th, p.z),
                                        apron_blend((Z_ATTACH - p.z) / FLAPS[1]["length"])))
    orient = [("belt", lambda c: Vector((c.x, c.y - YC[0.0], 0)), None)]
    if torso:
        # the torso's skin from under the belt to the base of the neck, without the arms; front triangles on
        # the front flap's plain upper area, back ones on the back flap's
        z0, z1 = BELT_Z - 1.8, TOP_Z - 2.0
        tv = {i for i, c in enumerate(C0) if z0 <= c.z <= z1 and i not in _ARMV}
        xw = max(abs(C0[i].x) for i in tv)
        key = {}
        for t in TRIS["basis"]:
            if not all(i in tv for i in t):
                continue
            cc = sum((C0[i] for i in t), Vector()) / 3
            reg = 0 if (cc.y - center_y(min(max(cc.z, CROTCH_Z + 2), TOP_Z - 3))) * FRONT.y > 0 else 1
            f = []
            for i in t:
                if (i, reg) not in key:
                    key[i, reg] = len(uvs)
                    u0, u1 = SK_UV[0 if reg == 0 else 2]
                    fy = 0.12 + 0.5 * (z1 - C0[i].z) / (z1 - z0)
                    uvs.append((u0 + (u1 - u0) * (0.5 + 0.5 * C0[i].x / xw), 0.74 - 0.73 * fy))
                    vw.append(weights_at([i], [1.0]))
                    for s in ALL:
                        pos[s].append(COORDS[s][i] + NRM[s][i] * 0.3)
                f.append(key[i, reg])
            faces.append(f)
            part.append("torso")
    print("%s %d vertices, %d faces; skirt hem z %.1f (knee %.1f)" % (name, len(uvs), len(faces), _SK_RING["basis"][0][-1][0].z,
                                                                      C0[KNEE_V].z))
    return dict(name=name, set=SET, pos=pos, faces=faces, part=part, wrap=wrap, wrap_u={i: 1.0 for i in range(5)}, uvs=uvs,
                vw=vw, orient=orient)


SKIRT, TUNIC = "ek2lc_%s_reach_skirt_01" % S1, "ek2lc_%s_reach_tunic_01" % S1
PIECES.append(skirt_piece(SKIRT))
PIECES.append(skirt_piece(TUNIC, torso=True))

# leggings: built first (see "hide leggings" near the top), so every piece above clears them

# children's charm cords at each hip (55 degrees from the front, where the adults' trophy belt hangs: children
# never wear it), 1.6 times an adult trophy's size so they read on a child, pushed out until they clear the
# loincloth, skirt, tunic and leggings on every shape
CHARM, CHSET = "ek2lc_%s_kid_charm_01" % S1, "ek2lc_charm_01"
CH_CORD, CH_QUILL, CH_SHELL, CH_TOOTH, CH_FRINGE = ((0.03, 0.53, 0.47, 0.97), (0.53, 0.53, 0.97, 0.97), (0.03, 0.03, 0.47, 0.47),
                                                    (0.53, 0.03, 0.97, 0.22), (0.53, 0.28, 0.97, 0.47))


CH_S = 1.6


def charm_item(side, out):
    tgt = ([], [], [], [])
    th0 = side * math.radians(55)
    o = 1.7 + out
    z1 = BELT_Z - 2.6
    S_ = CH_S
    add_tube(th0, [(0, BELT_Z + 3.0, 0.6), (0, BELT_Z + 1.9, 2.4 + out), (0, BELT_Z - 1.9, 2.4 + out), (0, z1, o)],
             [0.12] * 4, 1.0, CH_CORD, "c", tgt=tgt, binder=leg_bind)
    zq = z1 - 3.0 * S_
    add_tube(th0, [(0, z1, o), (0, z1 - 1.0 * S_, o), (0, z1 - 2.0 * S_, o), (0, zq, o)], [r * S_ for r in (0.28, 0.3, 0.3, 0.28)],
             1.0, CH_QUILL, "q", tgt=tgt, binder=leg_bind)
    z = zq - 0.1
    if side > 0:  # two cowrie shells, then the tassel below them
        for k in range(2):
            add_tube(th0, [(0, z, o), (0, z - 0.7 * S_, o + 0.05), (0, z - 1.4 * S_, o)], [r * S_ for r in (0.3, 0.55, 0.3)], 0.5,
                     CH_SHELL, "s%d" % k, tgt=tgt, binder=leg_bind)
            z -= 1.45 * S_
        fringe = [(c * S_, z) for c in (-0.3, 0.0, 0.3)]
    else:  # a tooth, the tassel either side of it
        L = 2.6 * S_
        add_tube(th0, [(0, z, o - 0.1), (0, z - L * 0.35, o - 0.15), (0, z - L * 0.7, o - 0.3), (0, z - L, o - 0.5)],
                 [r * S_ for r in (0.38, 0.35, 0.22, 0)], 0.6, CH_TOOTH, "t", cap_tip=True, tgt=tgt, binder=leg_bind)
        fringe = [(c * S_, zq - 0.1) for c in (-0.6, 0.6)]
    for k, (c, zt) in enumerate(fringe):
        add_tube(th0, [(c, zt, o), (c * 1.2, zt - 1.5 * S_, o), (c * 1.4, zt - 3.0 * S_, o)], [0.1, 0.1, 0], 1.0, CH_FRINGE,
                 "f%d" % k, cap_tip=True, tgt=tgt, binder=leg_bind)
    return tgt


_CHOBST = [(pc["name"], s, BVHTree.FromPolygons(pc["pos"][s], [list(f) for f in pc["faces"]]))
           for pc in PIECES if pc["name"] in (NAME, SKIRT, TUNIC, LEGG) for s in OWN]
cb_, cuv_, cf_, cp_ = [], [], [], []
for side in (1, -1):
    out = 0.0
    for _try in range(10):
        item = charm_item(side, out)
        vi = sorted({i for f, prt in zip(item[2], item[3]) if prt != "c" for i in f})
        gap, near = min((bvh.find_nearest(recon(item[0][i], s))[3], (nm, s)) for nm, s, bvh in _CHOBST for i in vi)
        if gap >= 0.3:
            break
        out += 0.3 - gap + 0.05
    print("CHARM side %+d: out %.2f, gap %.2f (to %s on %s)" % (side, out, gap, near[0], near[1]))
    _o = len(cb_)
    cb_ += item[0]
    cuv_ += item[1]
    cf_ += [[i + _o for i in f] for f in item[2]]
    cp_ += ["%s%+d" % (p, side) for p in item[3]]
_chpos = {s: [recon(b, s) for b in cb_] for s in ALL}
_chc = {}
for f, p in zip(cf_, cp_):
    _chc.setdefault(p, []).extend(_chpos["basis"][i] for i in f)
PIECES.append(dict(name=CHARM, set=CHSET, pos=_chpos, faces=cf_, part=cp_, wrap=set(), wrap_u={}, uvs=cuv_,
                   vw=[weights_at(b[0], b[1]) for b in cb_],
                   orient=[(p, (lambda c0: (lambda c: c - c0))(sum(ps, Vector()) / len(ps)), None) for p, ps in _chc.items()]))


def _flat_maps(H, WD, rough=0.58, spec=0.22):
    normal = np.zeros((H, WD, 4), np.float32)
    normal[..., 0] = normal[..., 1] = normal[..., 3] = 0.5
    props = np.zeros((H, WD, 4), np.float32)
    props[..., 1], props[..., 3] = spec, rough
    return normal, props


def _fbm(H, WD, k, seed, octaves=4):
    return undead.fbm(H, WD, k, seed, octaves)


def make_leggings_textures():
    """Smoked hide leggings, rebuilt 2026-11-07 to read as a garment, not skin: dark smoked hide with grain and
    folds (bunched over the ankle, creased at the front of the knee); a quilled strip down the outer side (red
    with bone-white steps and borders); a rolled, stitched top hem that follows the slanted cut; a band of
    quillwork under the knee; a sootier cuff with a painted zig-zag and a notched edge; stitching up the inner
    seam. Normal map in CK3's packing (x in G, -y in A)."""
    H = WD = 1024
    yy, xx = np.mgrid[0:H, 0:WD].astype(np.float32)
    v, u = 1 - yy / (H - 1), xx / (WD - 1)
    n1, n2, n3 = _fbm(H, WD, 6, 61), _fbm(H, WD, 30, 62, 3), _fbm(H, WD, 90, 63, 2)
    lu = np.clip(np.where(u < 0.5, (u - 0.01) / 0.48, (u - 0.51) / 0.48), 0, 1)  # 0 inner seam, .25 front, .5 outer, .75 back
    cm = (v - 0.01) / 0.89 * (L_HI - L_BOT)  # height above the cuff's lower edge
    top_cm = L_LO + (L_HI - L_LO) * ((1 - np.cos(2 * np.pi * lu)) / 2) ** 2 - L_BOT  # the top edge, per column (l_top)
    dtop = top_cm - cm  # cm below the top edge
    knee_cm = _KNEE.z - L_BOT
    base = K(0.25, 0.165, 0.105)
    img = np.ones((H, WD, 4), np.float32)
    smoke = 1.0 - 0.25 * np.clip(1 - cm / 16.0, 0, 1)  # sootier towards the ankle
    img[..., :3] = base * ((0.84 + 0.26 * n1 + 0.12 * (n2 - 0.5) + 0.06 * (n3 - 0.5)) * smoke)[..., None]
    height = 0.12 * (n2 - 0.5) + 0.07 * (n3 - 0.5)  # grain
    ank = np.clip(1 - (cm - 2.5) / 12.0, 0, 1) * (cm > 2.5)
    height += 0.75 * ank * np.sin(2 * np.pi * (cm / 2.3 + 0.35 * n1))  # bunched over the ankle
    kn = np.exp(-((cm - knee_cm - 1.0) / 3.5) ** 2) * np.clip(1 - np.abs(lu - 0.25) / 0.2, 0, 1)
    height += 0.45 * kn * np.sin(2 * np.pi * (cm / 1.5 + 0.3 * n1))  # creases at the front of the knee
    height += 0.25 * np.exp(-((cm - knee_cm + 1.0) / 3.0) ** 2) * np.clip(1 - np.abs(lu - 0.75) / 0.15, 0, 1) * \
        np.sin(2 * np.pi * cm / 1.2)  # and behind it
    img[..., :3] *= (1.0 - 0.18 * np.clip(-height, 0, 1))[..., None]  # darker in the hollows
    props = np.zeros((H, WD, 4), np.float32)
    props[..., 1], props[..., 3] = 0.2, 0.62
    # the quilled strip down the outer side, from the cuff to the hem
    st = np.abs(lu - 0.5)
    strip = (st < 0.036) & (dtop > 1.6) & (cm > 2.8)
    sx = (lu - 0.5) / 0.036  # -1..1 across the strip
    img[strip, :3] = K(0.50, 0.13, 0.08) * (0.85 + 0.25 * n2[strip])[:, None]
    step = ((cm * 1.1) % 3.0) / 3.0  # stepped diamonds up the strip
    dia = strip & (np.abs(sx) < 0.62 - np.abs(step - 0.5) * 1.1)
    img[dia, :3] = K(0.84, 0.78, 0.64) * (0.9 + 0.15 * n2[dia])[:, None]
    core = dia & (np.abs(sx) < 0.3 - np.abs(step - 0.5) * 0.55)
    img[core, :3] = K(0.06, 0.045, 0.035)
    border = strip & (np.abs(sx) > 0.8)
    img[border, :3] = K(0.84, 0.78, 0.64) * 0.92
    height[strip] += 0.35 + 0.12 * np.sin(np.pi * 9 * sx[strip]) ** 2  # raised quill rows
    props[strip, 1], props[strip, 3] = 0.3, 0.42
    # the rolled top hem, with a running stitch under it
    hem = dtop < 1.9
    img[hem, :3] *= 0.72
    height += np.where(hem, 0.6 * np.sin(np.pi * np.clip(dtop / 1.9, 0, 1)), 0.0)
    stitch = (np.abs(dtop - 2.3) < 0.13) & (((xx + 3 * (yy // 7)) % 12) < 6)
    img[stitch, :3] = K(0.78, 0.70, 0.55)
    # quillwork band just under the knee
    kb = cm - (knee_cm - 5.0)
    band = np.abs(kb) < 1.3
    stripe = ((kb + 1.3) / 2.6 * 3).astype(np.int32).clip(0, 2)
    for k_, col in enumerate((K(0.55, 0.12, 0.07), K(0.80, 0.62, 0.20), K(0.88, 0.84, 0.74))):
        m_ = band & (stripe == k_)
        img[m_, :3] = col * (0.85 + 0.25 * n2[m_])[:, None]
    wraps = band & (((lu * 0.48 * WD) % 10) < 1.4)
    img[wraps, :3] *= 0.55
    height[band] += 0.3
    props[band, 1], props[band, 3] = 0.3, 0.45
    # the cuff: sootier, a painted zig-zag, a notched lower edge
    cuff = cm < 2.6
    img[cuff, :3] *= 0.7
    zig = np.abs(cm - (1.5 + 0.45 * np.abs(((lu * 0.48 * WD / 16.0) % 2.0) - 1.0))) < 0.14
    img[cuff & zig, :3] = K(0.50, 0.13, 0.08)
    img[(cm < 0.75) & (((xx + 2) % 11) < 4), 3] = 0.0  # notches (alpha to coverage cuts them)
    height += np.where(cuff, 0.35 * np.sin(np.pi * np.clip(cm / 2.6, 0, 1)), 0.0)
    # stitching up the inner seam
    seam = np.minimum(lu, 1 - lu) * 0.48 * WD  # pixels from the seam
    img[seam < 1.6, :3] *= 0.5
    sts = (seam < 7) & ((((cm * 11.0) % 9) < 3.5)) & (seam > 2.5)
    img[sts, :3] = K(0.62, 0.52, 0.38)
    # normal map from the height field
    gy, gx = np.gradient(height)
    k = 2.2
    nx, ny = -gx * k, gy * k  # gy: rows run down the image (v falls), so -dh/dv = +dh/drow
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny = nx / ln, ny / ln
    normal = np.zeros((H, WD, 4), np.float32)
    normal[..., 0] = 0.5
    normal[..., 1] = 0.5 + 0.5 * nx
    normal[..., 3] = 0.5 - 0.5 * ny
    return {"diffuse": np.clip(img, 0, 1), "normal": normal, "properties": props}


def make_robe_textures():
    """Fur cloak on the mantle's mesh: a dark brown bear-fur collar and cape (long hair running down, a tufted
    hem cut out of both sides), lined with smoked hide."""
    H = WD = 1024
    rng = np.random.default_rng(71)
    yy, xx = np.mgrid[0:H, 0:WD].astype(np.float32)
    v, u = 1 - yy / (H - 1), xx / (WD - 1)
    img = np.zeros((H, WD, 4), np.float32)
    img[..., :3], img[..., 3] = 0.05, 1.0
    normal, props = _flat_maps(H, WD, 0.7, 0.12)
    FUR = K(0.30, 0.22, 0.15)
    xi = xx.astype(np.int32)
    s1 = np.convolve(rng.random(WD + 8), np.ones(3) / 3, "same")[4:WD + 4].astype(np.float32)
    s2 = rng.random(WD).astype(np.float32)
    wav = (xi + (3 * np.sin(yy * 0.05 + xx * 0.017)).astype(np.int32)) % WD
    clump = 0.85 + 0.15 * np.sin(xx * 0.09 + 2 * np.sin(yy * 0.02))
    fur = FUR[None, None, :] * ((0.7 + 0.4 * s1[wav]) * clump)[..., None]
    fur = np.where((s2[wav] < 0.14)[..., None], fur * 0.55, fur)  # dark guard hairs
    fur = np.where((s2[wav] > 0.93)[..., None], fur * 1.45, fur)  # pale tips
    m = v >= 0.855  # collar: darker at the roots, tufted edge
    fv = np.clip((COLLAR_UV[3] - v) / (COLLAR_UV[3] - COLLAR_UV[1]), 0, 1)
    img[m, :3] = (fur * (0.62 + 0.38 * np.clip(fv * 1.4, 0, 1))[..., None])[m]
    tp = 13
    tid = xi // tp
    trnd = rng.random(int(tid.max()) + 2).astype(np.float32)
    tri = np.abs(((xx + trnd[tid] * 5) % tp) / tp - 0.5) * 2
    img[m & (fv > 0.80 + 0.17 * (1 - tri) * (0.6 + 0.4 * trnd[tid])), 3] = 0.0
    img[m & (fv > 0.985), 3] = 0.0
    tp2 = 17
    tid2 = xi // tp2
    trnd2 = rng.random(int(tid2.max()) + 2).astype(np.float32)
    tri2 = np.abs(((xx + trnd2[tid2] * 7) % tp2) / tp2 - 0.5) * 2
    for box, is_cape in ((CAPE_UV, True), (LINING_UV, False)):
        reg = (u >= box[0]) & (u <= box[2]) & (v >= box[1]) & (v <= box[3])
        al = np.clip((box[3] - v) / (box[3] - box[1]), 0, 1)  # 0 top .. 1 hem
        if is_cape:
            img[reg, :3] = (fur * (0.8 + 0.2 * np.clip(1.2 - al, 0, 1))[..., None])[reg]
        else:
            n = _fbm(H, WD, 8, 72)
            img[reg, :3] = K(0.33, 0.24, 0.16) * (0.8 + 0.3 * n[reg])[:, None]
        img[reg & (al > 0.93 + 0.06 * (1 - tri2) * (0.5 + 0.5 * trnd2[tid2])), 3] = 0.0  # tufted hem
    img[v < 0.025, 3] = 0.0
    return {"diffuse": np.clip(img, 0, 1), "normal": normal, "properties": props}


def make_charm_textures():
    """Children's charms: sinew cord, quills dyed red, yellow and white, cowrie shell, tooth, hide fringe."""
    H = WD = 512
    yy, xx = np.mgrid[0:H, 0:WD].astype(np.float32)
    v, u = 1 - yy / (H - 1), xx / (WD - 1)
    n = _fbm(H, WD, 12, 81, 3)
    img = np.ones((H, WD, 4), np.float32)
    img[..., :3] = K(0.55, 0.44, 0.30) * (0.8 + 0.3 * n)[..., None]  # sinew and fringe hide
    q = (u >= 0.5) & (v >= 0.5)  # quills: bands along the cord
    bands = ((v * H) // 9).astype(np.int32) % 4
    for k_, col in enumerate((K(0.62, 0.10, 0.06), K(0.86, 0.66, 0.18), K(0.90, 0.87, 0.78), K(0.10, 0.08, 0.07))):
        img[q & (bands == k_), :3] = col * (0.85 + 0.25 * n[q & (bands == k_)])[:, None]
    img[q & ((xx % 6) < 1), :3] *= 0.7
    sh = (u < 0.5) & (v < 0.5)  # cowrie: cream, a darker slit down the middle
    img[sh, :3] = K(0.90, 0.85, 0.72) * (0.9 + 0.15 * n[sh])[:, None]
    img[sh & (np.abs(u - 0.25) < 0.012), :3] = K(0.35, 0.26, 0.18)
    th_ = (u >= 0.5) & (v < 0.25)  # tooth
    img[th_, :3] = K(0.86, 0.81, 0.68) * (0.88 + 0.15 * n[th_])[:, None]
    normal, props = _flat_maps(H, WD, 0.55, 0.2)
    props[sh | th_, 1] = 0.45  # shell and tooth a little shiny (left unmasked by make_colour.py)
    props[sh | th_, 3] = 0.35
    return {"diffuse": np.clip(img, 0, 1), "normal": normal, "properties": props}


MATS[LEGSET] = make_material("ek2lc_leggings", save_set(LEGSET, make_leggings_textures()))
MATS[CHSET] = make_material("ek2lc_charm", save_set(CHSET, make_charm_textures()))
ROBESET = "ek2lc_robe_01"
MATS[ROBESET] = make_material("ek2lc_robe", save_set(ROBESET, make_robe_textures()))
if SEX == "male":  # their lich versions: no colour roles, so greyed and darkened (as the camp wrap)
    for _i, (_k, _fn) in enumerate((("leggings", make_leggings_textures), ("robe", make_robe_textures), ("charm", make_charm_textures))):
        save_diffuse("ek2lc_lich_%s_01" % _k, undead.lich_finish(undead.blacken(_fn()["diffuse"]), np.zeros((1, 1), bool), 131 + _i))

STRICT = {GUARD}
  # finish_piece: no point of these inside the body on any shape

# closest point of the new pieces to each piece they may be worn with, per body shape
for _xn in (GUARD, WRAP):
    _xp = next(pc for pc in PIECES if pc["name"] == _xn)
    for _o in PIECES:
        if _o["name"] == _xn:
            continue
        _vpart = {}
        for f, prt in zip(_xp["faces"], _xp["part"]):
            for i in f:
                _vpart[i] = prt
        _worst, _low = (1e9, None, None), []
        for s in ALL:
            _bvh = BVHTree.FromPolygons(_o["pos"][s], [list(f) for f in _o["faces"]])
            _ws = min((_bvh.find_nearest(p)[3], s, _vpart.get(i)) for i, p in enumerate(_xp["pos"][s]))
            _worst = min(_worst, _ws)
            if _ws[0] < 0.3:
                _low.append("%s %.2f %s" % (s, _ws[0], _ws[2]))
        print("XGAP %s vs %-26s min=%.2f (%s, %s)%s" % (_xn, _o["name"], *_worst, "  low: " + ", ".join(_low) if _low else ""))


# ------------------------------------------------------------------ weights solved over the game's own poses
# (2026-11-07) The weights above keep every piece right in the idles, but kneeling (the throne room's petitioners
# and messengers), sitting on a throne (cross-legged on the steppe and Indian thrones, which EK2 gives the Reach,
# orc, goblin, Bosmer, Argonian and Khajiit courts; on a chair elsewhere) and bowing pushed the thighs and the hip
# creases through flaps, aprons, belts, strips and capes. weight_solver.py re-solves the weights of everything that
# hangs below the hips over frames of the game's own animations (see its docstring): outside the body by a margin
# (the leggings hug the skin, so outside them too), keeping its shape, keeping the standing look, never pointing up.
# The game's poses aren't mirrored (the one-knee kneel always raises the right knee, cross-legged sitting the left
# one), so the two halves may differ.
import weight_solver as wsol
SOLVE_ANIMS = (["idle_1", "idle_2", "idle_3", "AI_callous_1", "emotion_angry", "emotion_grief", "emotion_happy",
                "emotion_sadness", "emotion_scheme"] + (["emotion_angry_start", "shocked_idle"] if SEX == "male" else []) +
               ["throneRoom_" + a for a in ("kneel1_1", "kneel2_1", "messenger1_1", "ruler1_1", "ruler2_1", "ruler3_1",
                                             "bow1_1", "bow2_1", "bow3_1", "cheer1_1", "applaud1_1", "conversation1_1",
                                             "conversation2_1", "chancellor_1", "oneHandedPassive1_1", "twoHandedPassive1_1")] +
               (["throneRoom_curtsey1_1"] if SEX == "female" else []))
_SB = list(VG)  # every group name: the body's, then the skirt and cloak bones added above
_SBI = {n: i for i, n in enumerate(_SB)}
_t = time.time()
POSES = wsol.sample_poses(rig, scene, GAME, SEX, SOLVE_ANIMS, _SB, log=print)
print("SOLVE %d poses (%d standing, which keep their look) in %.0fs" % (len(POSES), sum(k == "ref" for _, k, _ in POSES),
                                                                       time.time() - _t))
assert len(POSES) >= 3 * len(SOLVE_ANIMS) - 6, "too few poses imported for the weight solver (%d)" % len(POSES)
_BWM = wsol.skin_matrix(BW, len(_SB))
_BUSED = np.nonzero(_BWM.any(axis=0))[0]
_BH = np.c_[np.array([c[:] for c in C0]), np.ones(len(C0))]
_HANDK = ("elbow", "forearm", "wrist", "_fi_", "finger", "thumb", "hand", "prop", "sleeve")
_HANDB = [i for i, n in enumerate(VG) if any(k in n for k in _HANDK)]
_HANDV = {i for i, ws in enumerate(BW) if sum(w for g, w in ws.items() if g in _HANDB) > 0.5}
_NOHAND_T = [list(t) for t in TRIS["basis"] if not _HANDV.intersection(t)]  # body without forearms and hands


def _posed(W, mats, H):
    """LBS: positions of homogeneous points H (V x 4) with dense weights W (V x B) under mats (B x 4 x 4)."""
    used = np.nonzero(W.any(axis=0))[0]
    Y = np.einsum("bij,vj->vbi", mats[used, :3, :], H)
    return np.einsum("vb,vbi->vi", W[:, used], Y)


_BODY_POSED = [_posed(_BWM, m, _BH) for _, _, m in POSES]
SOLVED = {}  # piece name -> dense weights (V x len(_SB)), the obstacles for pieces worn over it
_CH_ANG = {c: a for a, c in _SK_ANGS}
_BASE = [GI["body_root"], GI["bn_sp_lumbar"], GI["bn_l_hip"], GI["bn_r_hip"]]


def _hang_allowed(p, window=math.radians(75)):
    """Bones a hanging point may follow: the pelvis, the lower spine, both thighs, and the first three bones of the
    skirt chains within 75 degrees of it round the body."""
    th = ang_of(p) % (2 * math.pi)
    out = set(_BASE)
    for c, a in _CH_ANG.items():
        if abs((th - a + math.pi) % (2 * math.pi) - math.pi) <= window:
            out |= {GI["bn_%s_skirt%d" % (c, i)] for i in (1, 2, 3)}
    return out


_CLOAKB = [GI[n] for n in VG if "_cloak" in n]
_SPINE = [GI[n] for n in ("body_root", "bn_sp_lumbar", "bn_sp_thoracic", "bn_l_hip", "bn_r_hip") if n in GI]


def _cape_allowed(p):
    return set(_CLOAKB) | set(_SPINE)


def solve_piece(pc, free, cap, allowed_fn=_hang_allowed, stick=None, extra=(), tie_d=1.0, ties=None, iters=250,
                inits=("orig", "half"), pose_w=3.0):
    """Solve the weights of pc's free vertices (see the section comment). cap: the margin wanted (per vertex, at
    most 0.8 of its clearance at rest); stick: per-vertex most distance off the obstacles (strips that must stay on);
    extra: names of solved pieces it is worn over (obstacles too)."""
    t0 = time.time()
    n = len(pc["pos"]["basis"])
    rest = np.array([p[:] for p in pc["pos"]["basis"]])
    H = np.c_[rest, np.ones(n)]
    faces = pc["faces"]
    E = wsol.mesh_edges(faces)
    comp = wsol.islands(n, E)
    edges = E + (wsol.tie_pairs(rest, comp, tie_d) if ties is None else list(ties)) + wsol.bend_pairs(rest, faces)
    pc.setdefault("vw0", list(pc["vw"]))  # the weights before solving (kept for re-solving in the app)
    W0full = wsol.skin_matrix(pc["vw0"], len(_SB))
    free = np.asarray(free, bool)
    cand = set()
    for v in np.nonzero(free)[0]:
        cand |= allowed_fn(Vector(rest[v]))
    bones = sorted(set(np.nonzero(W0full.any(axis=0))[0]) | cand)
    bl = {b: k for k, b in enumerate(bones)}
    W0 = W0full[:, bones]
    allowed = np.zeros_like(W0, bool)
    for v in np.nonzero(free)[0]:
        for b in allowed_fn(Vector(rest[v])):
            allowed[v, bl[b]] = True
    # obstacles: the body (without forearms and hands) and the solved pieces it is worn over, at rest and per pose
    ex = [(SOLVED[e], next(q for q in PIECES if q["name"] == e)) for e in extra]
    ex_h = [np.c_[np.array([p[:] for p in q["pos"]["basis"]]), np.ones(len(q["pos"]["basis"]))] for _, q in ex]

    def obstacle(body_pts, ex_pts):
        co, tr = [Vector(c) for c in body_pts], list(_NOHAND_T)
        for (_, q), pts in zip(ex, ex_pts):
            o_ = len(co)
            co += [Vector(c) for c in pts]
            tr += [[i + o_ for i in f] for f in q["faces"]]
        return BVHTree.FromPolygons(co, tr)
    rest_obst = obstacle(C0, [h[:, :3] for h in ex_h])
    rc = np.array([((Vector(p) - rest_obst.find_nearest(Vector(p))[0]).dot(rest_obst.find_nearest(Vector(p))[1])) for p in rest])
    margin = np.minimum(np.broadcast_to(cap, (n,)), 0.8 * np.maximum(rc, 0.0))
    poses = []
    for k, (nm, kind, mats) in enumerate(POSES):
        exp = [_posed(Wd, mats, h) for (Wd, _), h in zip(ex, ex_h)]
        m_ = mats[bones]
        poses.append(dict(name=nm, mats=m_, obst=obstacle(_BODY_POSED[k], exp),
                          ref=_posed(W0, m_, H) if kind == "ref" else None,
                          w=1.0 if kind == "ref" else pose_w))  # kneeling, sitting, bowing: clearance counts more
    down = []
    for a, b in E:
        if free[a] and free[b]:
            d = rest[a] - rest[b]
            if abs(d[2]) > 0.8 * np.linalg.norm(d):
                down.append((a, b) if d[2] > 0 else (b, a))
    lam = dict(pen=20.0, ref=1.0, len=2.0, smooth=30.0, stick=5.0, down=20.0, grav=0.5)
    best = None
    for init in inits:
        prob = wsol.Problem(rest, edges, W0, free, allowed, poses, margin, None, None,
                            None if stick is None else np.where(np.isfinite(stick), rc + stick, 1e9), down)
        prob.down_slack = 0.0
        prob.grav = np.where(free & (rest[:, 2] < BELT_Z - 2.0), 1.0, 0.0)
        if init == "half":  # start from half pelvis, half the thigh on that side (found the better drapes)
            Wh = prob.W.copy()
            for v in np.nonzero(free & (rest[:, 2] < BELT_Z - 4.0))[0]:
                row = np.zeros(len(bones))
                wl = min(1.0, max(0.0, 0.5 + rest[v][0] / 20.0)) if _LSIDE > 0 else min(1.0, max(0.0, 0.5 - rest[v][0] / 20.0))
                row[bl[GI["body_root"]]] = 0.5
                row[bl[GI["bn_l_hip"]]] = 0.5 * wl
                row[bl[GI["bn_r_hip"]]] = 0.5 * (1 - wl)
                k_ = min(1.0, (BELT_Z - 4.0 - rest[v][2]) / 6.0)
                Wh[v] = (1 - k_) * Wh[v] + k_ * row
            prob.W = Wh
        en = prob.run(lam, iters=iters, max_dw=0.03, decay=0.99)
        tot = sum(en.values())
        free_names = {p["name"] for p in poses if p["ref"] is None}
        worst = max([r[0] for r in prob.penetration() if r[2] in free_names] or [0.0])
        # the start that leaves the least inside the body when kneeling or sitting wins (the lower energy if close)
        if best is None or worst < best[0] - 0.3 or (abs(worst - best[0]) <= 0.3 and tot < best[1]):
            best = (worst, tot, init, prob, en)
    worst, tot, init, prob, en = best
    prob.prune(4, 0.015)
    prob.run(lam, iters=40, max_dw=0.01, decay=0.98)  # settle on the pruned bones
    pen = prob.penetration()
    st = prob.stretch()
    dev = [float(np.linalg.norm(prob.positions(p) - p["ref"], axis=1)[free].max()) for p in poses if p["ref"] is not None]
    print("SOLVE %-28s %4d free, start %s, %.0fs; worst left inside: %s; most stretch %.1f cm (%s); standing looks moved "
          "max %.1f cm, median %.1f" % (pc["name"], free.sum(), init, time.time() - t0,
                                        "; ".join("%.2f cm x%d %s" % r for r in pen[:3]) or "none", st[0][0], st[0][1],
                                        max(dev) if dev else 0.0, float(np.median(dev)) if dev else 0.0))
    Wf = np.zeros((n, len(_SB)))
    Wf[:, bones] = prob.W
    Wf[~free] = W0full[~free]
    SOLVED[pc["name"]] = Wf
    pc["vw"] = [[(int(b), float(Wf[v, b])) for b in np.nonzero(Wf[v] > 1e-4)[0]] for v in range(n)]


_PC = {pc["name"]: pc for pc in PIECES}
# the loincloth: everything (belt and strip may lift over a raised thigh's crease); the flaps' tucked rows tie to the belt
_nl = len(POS["basis"])
_kind = ["belt"] * (NB * 5) + ["strip"] * (NS * SC) + ["flap"] * (_nl - NB * 5 - NS * SC)
_cap = np.array([{"belt": 0.6, "strip": 0.6, "flap": 1.3}[k] for k in _kind])
_stick = np.array([1.2 if k == "strip" else np.inf for k in _kind])
_lp = np.array([p[:] for p in POS["basis"]])
_belt_i = np.arange(NB * 5)


def _to_belt(idx):  # each of these vertices tied to the nearest belt vertex
    out = []
    for i in idx:
        d = ((_lp[_belt_i] - _lp[i]) ** 2).sum(1)
        out.append((int(i), int(_belt_i[np.argmin(d)])))
    return out


_tucked = [i for i in range(NB * 5, _nl) if _lp[i][2] > BELT_Z - 2.6]  # flap rows and strip ends under the belt
solve_piece(_PC[NAME], np.ones(_nl, bool), _cap, stick=_stick, ties=_to_belt(_tucked))
# the royal aprons hang in front of the flaps: below the cord belt they take the solved weights of the flap
# behind them (its bottom row's further down), so apron and flap move as one (the solver can't treat the
# loincloth as an obstacle: its strip and belt are open sheets, and signed distances to them are unreliable)
_FL0 = NB * 5 + NS * SC  # the front flap's outer layer starts here; the back flap's at _FL0 + 2 * FR * FC
_SW = SOLVED[NAME]


def _apron_weights(pc):
    pos = pc["pos"]["basis"]
    hang = np.zeros(len(pos), bool)
    for f, pt in zip(pc["faces"], pc["part"]):
        if pt[:2] in ("pf", "pb"):
            for i in f:
                hang[i] = pos[i].z < BELT_Z - 1.9
    for i in np.nonzero(hang)[0]:
        q = pos[i]
        side = +1 if q.dot(FRONT) > 0 else -1
        b0 = _FL0 if side == +1 else _FL0 + 2 * FR * FC
        zc = max(q.z, POS["basis"][b0 + (FR - 1) * FC].z)  # below the flap: its bottom row
        k = min(range(b0, b0 + FR * FC), key=lambda j: (POS["basis"][j].x - q.x) ** 2 + (POS["basis"][j].z - zc) ** 2)
        pc["vw"][i] = [(int(b), float(_SW[k, b])) for b in np.nonzero(_SW[k] > 1e-4)[0]]
    return hang


# pieces worn over it: the girdles and everything hanging from them (the body as the obstacle)
for _nm in (WAR, ARM, DUKE, KING, WRAP) + tuple(TROPHY.values()):
    _pc = _PC[_nm]
    _hang = _apron_weights(_pc) if _nm in (DUKE, KING) else np.zeros(len(_pc["pos"]["basis"]), bool)
    _fr = np.array([p.z < BELT_Z + 8.0 for p in _pc["pos"]["basis"]]) & ~_hang
    solve_piece(_pc, _fr, 1.0)
# (the children's skirt, tunic and charms keep their weights: children stand in the throne room; they don't kneel
# as petitioners and a child ruler has their own throne pose)
# the mantle (and the fur cloak, the same mesh): the cape below the yoke, with the cloak bones and the spine
_pc = _PC[MANTLE]
_fr = np.array([any(g in _CLOAKB for g, w in ws) for ws in _pc["vw"]])
solve_piece(_pc, _fr, 1.3, allowed_fn=_cape_allowed)
print("SOLVE done in %.0fs" % (time.time() - _t))

import fitting
fitting.apply(PIECES, SEX, SRC, VG)
OBJS = [finish_piece(pc) for pc in PIECES]

# the trophies must not cut through the pieces they're worn with: closest trophy point to each
# other piece's surface, per body shape (beads are 0.55 cm thick, so under ~0.2 means touching)
for _t, _tn in TROPHY.items():
    _tpc = next(pc for pc in PIECES if pc["name"] == _tn)
    # beads, teeth and claws (the cords are meant to pass over the cord belt and under a girdle)
    _tvi = sorted({i for f, prt in zip(_tpc["faces"], _tpc["part"]) if not prt.startswith("c") for i in f})
    for _o in PIECES:
        if _o["name"] in TROPHY.values() or "band" in _o["name"]:
            continue
        _worst = (1e9, None)
        for s in ALL:
            _bvh = BVHTree.FromPolygons(_o["pos"][s], [list(f) for f in _o["faces"]])
            _d = min(_bvh.find_nearest(_tpc["pos"][s][i])[3] for i in _tvi)
            _worst = min(_worst, (_d, s))
        print("TROPHYGAP %s vs %-26s min=%.2f (%s)" % (_tn, _o["name"], _worst[0], _worst[1]))
# EK2's undead (draugr 1.0; its Reach briarhearts 0.5) with each other body shape: points of each piece inside
# the body, and the trophies' closest approach to every other piece, on each mix the game makes
_BMIX = [BVHTree.FromPolygons(mix(COORDS, ws).tolist(), [list(t) for t in TRIS["basis"]]) for ws in REFIT_MIXES]
for _pc in PIECES:
    _ins = []
    for ws, _bvh in zip(REFIT_MIXES, _BMIX):
        _n, _m = 0, 1e9
        for p in mix(_pc["pos"], ws):
            loc, nor, fi, d = _bvh.find_nearest(Vector(p))
            sd = (Vector(p) - loc).dot(nor)
            _n += sd < 0
            _m = min(_m, sd)
        _ins.append((_n, _m, "+".join("%s %.1f" % kv for kv in ws.items())))
    _w = max(_ins, key=lambda t: (t[0], -t[1]))
    print("DRAUGRMIX %-28s inside max=%d min=%.2f (%s); mixes with points inside: %d of %d" % (
        _pc["name"], _w[0], _w[1], _w[2], sum(1 for t in _ins if t[0]), len(_ins)))
for _t, _tn in TROPHY.items():
    _tpc = next(pc for pc in PIECES if pc["name"] == _tn)
    _tvi = sorted({i for f, prt in zip(_tpc["faces"], _tpc["part"]) if not prt.startswith("c") for i in f})
    _tmb = mix_bvhs([(o["name"], o["pos"], [list(f) for f in o["faces"]]) for o in PIECES
                     if o["name"] not in TROPHY.values() and "band" not in o["name"]])
    _g = refit_gap(_tpc["pos"], _tvi, _tmb)
    _gp = refit_gap(_tpc["pos"], _tvi, _tmb, None, REFIT_PURE)
    _bad = [ws for k, ws in enumerate(REFIT_MIXES) if refit_gap(_tpc["pos"], _tvi, _tmb, None, [k])[0] < TROPHY_GAP]
    print("TROPHYMIX %s alone min=%.2f (to %s on %s); all mixes min=%.2f to %s on %s; under %.1f: %s" % (
        _tn, _gp[0], _gp[1], _gp[2], _g[0], _g[1], _g[2], TROPHY_GAP, ", ".join("+".join("%s %.1f" % kv for kv in ws.items()) for ws in _bad) or "none"))
for _ent, _mesh, _set in [("ek2lc_%s_reach_fine_01" % S1, NAME, FSET), ("ek2lc_%s_reach_royal_01" % S1, NAME, RSET),
                          ("ek2lc_%s_reach_emperor_01" % S1, KING, ROYAL_SETS["emperor"])] + (
        [("ek2lc_f_reach_band_fine_01", BAND, FSET), ("ek2lc_f_reach_band_royal_01", BAND, RSET)] if SEX == "female" else []):
    write_asset(_ent, _mesh, _set)  # same mesh, other texture
for _c in CULTURES:  # culture variants: same meshes, the culture's diffuse
    for _k, (_piece, _rset) in KINDS.items():
        if _piece == "band" and SEX != "female":
            continue
        _mesh = BAND if _piece == "band" else "ek2lc_%s_reach_%s_01" % (S1, _piece)
        write_asset("ek2lc_%s_%s_%s_01" % (S1, _c, _k), _mesh, "ek2lc_%s_%s_01" % (_c, TEX_OF[_k]), REACH_SET[_rset])
for _k, (_piece, _rset) in KINDS.items():  # the lich's burial regalia: every piece, lich textures
    if _piece == "band" and SEX != "female":
        continue
    _mesh = BAND if _piece == "band" else "ek2lc_%s_reach_%s_01" % (S1, _piece)
    write_asset("ek2lc_%s_lich_%s_01" % (S1, _k), _mesh, "ek2lc_lich_%s_01" % TEX_OF[_k], REACH_SET[_rset])
for _t, _tn in TROPHY.items():
    write_asset("ek2lc_%s_lich_trophy_%d_01" % (S1, _t), _tn, "ek2lc_lich_war_01", WSET)
write_asset("ek2lc_%s_lich_arena_guard_01" % S1, GUARD, "ek2lc_lich_armour_01", ASET)
write_asset("ek2lc_%s_lich_camp_wrap_01" % S1, WRAP, "ek2lc_lich_camp_01", CSET)
write_asset("ek2lc_%s_fur_robe_01" % S1, MANTLE, ROBESET)  # the fur cloak: the mantle's mesh, its own texture
write_asset("ek2lc_%s_lich_fur_robe_01" % S1, MANTLE, "ek2lc_lich_robe_01", ROBESET)
write_asset("ek2lc_%s_lich_leggings_01" % S1, LEGG, "ek2lc_lich_leggings_01", LEGSET)
write_asset("ek2lc_%s_lich_kid_charm_01" % S1, CHARM, "ek2lc_lich_charm_01", CHSET)
for _c in ["reach"] + list(CULTURES):  # the other undead: the culture's plain loincloth (and band), rotted
    write_asset("ek2lc_%s_%s_grave_01" % (S1, _c), NAME, "ek2lc_%s_grave_01" % _c, SET)
    if SEX == "female":
        write_asset("ek2lc_f_%s_grave_band_01" % _c, BAND, "ek2lc_%s_grave_01" % _c, SET)

# body shapes as shape keys, so the .blend shows the pieces following them (export is done)
for obj, data in [(body, COORDS)] + [(o, pc["pos"]) for o, pc in zip(OBJS, PIECES)]:
    obj.shape_key_add(name="Basis")
    for s in SHAPES:
        kb = obj.shape_key_add(name=s, from_mix=False)
        for i, c in enumerate(data[s]):
            kb.data[i].co = WI @ c
        kb.value = 0.0  # new keys start at 1.0 in this Blender; all on at once is a body the game never makes
_version = 'v03' if os.path.exists(os.path.join(SRC, 'fitting_' + SEX + '.npz')) else 'v01'
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SRC, "reach_hide_%s_%s.blend" % (S1, _version)))


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
    for o in OBJS:  # the armour has its own girdle: show it (not the war or royal pieces) in the preview
        o.hide_render = o.name not in (NAME, BAND, ARM)
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



def preview_royal():
    """Duke, king and emperor (front), emperor (back): the royal pieces on the fine or royal loincloth."""
    objs = {o.name: o for o in OBJS}
    co = scene.camera
    target = Vector((0, center_y(HIP_Z), 90 if SEX == "female" else 79))
    for kb in [o.data.shape_keys.key_blocks[k] for o in [body] + OBJS for k in ("fat", "pregnant") if k in o.data.shape_keys.key_blocks]:
        kb.value = 0
    shots = []
    for tag, ang, base_set, piece, pset in (("duke", 0, FSET, DUKE, ROYAL_SETS["duke"]), ("king", 0, RSET, KING, ROYAL_SETS["king"]),
                                             ("emperor", 0, RSET, KING, ROYAL_SETS["emperor"]), ("emperor_back", 180, RSET, KING, ROYAL_SETS["emperor"])):
        for o in OBJS:
            o.hide_render = o.name not in (NAME, BAND, piece)
            if o.name in (NAME, BAND):
                o.data.materials[0] = MATS[base_set]
        objs[piece].data.materials[0] = MATS[pset]
        a = math.radians(ang)
        co.location = target + (FRONT * math.cos(a) + RIGHT * math.sin(a)) * 300
        co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(PREV, "r_%s_%s.png" % (S1, tag))
        bpy.ops.render.render(write_still=True)
        shots.append(scene.render.filepath)
    subprocess.run([MAGICK] + shots + ["+append", "-resize", "1000x", os.path.join(PREV, "preview_royal_%s.png" % S1)], check=True)


def preview_mantle():
    """The emperor with the mantle, whole figure: front, three-quarter, side, back."""
    objs = {o.name: o for o in OBJS}
    co = scene.camera
    co.data.ortho_scale = TOP_Z + 14
    target = Vector((0, center_y(HIP_Z), TOP_Z / 2))
    for o in OBJS:
        o.hide_render = o.name not in (NAME, BAND, KING, MANTLE)
        if o.name in (NAME, BAND):
            o.data.materials[0] = MATS[RSET]
    objs[KING].data.materials[0] = MATS[ROYAL_SETS["emperor"]]
    shots = []
    for tag, ang in (("front", 0), ("three", 35), ("side", 90), ("back", 180)):
        a = math.radians(ang)
        co.location = target + (FRONT * math.cos(a) + RIGHT * math.sin(a)) * 300
        co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(PREV, "mt_%s_%s.png" % (S1, tag))
        bpy.ops.render.render(write_still=True)
        shots.append(scene.render.filepath)
    subprocess.run([MAGICK] + shots + ["+append", "-resize", "800x", os.path.join(PREV, "preview_mantle_%s.png" % S1)], check=True)


def preview_extras():
    """The arena shoulder guard and the camp follower's wrap on the plain loincloth: front, three-quarter
    and side (the left, where the guard and the knot are), back."""
    co = scene.camera
    lo = BELT_Z - 24
    co.data.ortho_scale = TOP_Z - lo + 6
    target = Vector((0, center_y(HIP_Z), (TOP_Z + lo) / 2))
    for o in OBJS:
        o.hide_render = o.name not in (NAME, BAND, GUARD, WRAP)
        if o.name in (NAME, BAND):
            o.data.materials[0] = MATS[SET]
    shots = []
    for tag, ang in (("front", 0), ("three", 40), ("side", 90), ("back", 180)):
        a = math.radians(ang)
        co.location = target + (FRONT * math.cos(a) + RIGHT * math.sin(a)) * 300
        co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(PREV, "x_%s_%s.png" % (S1, tag))
        bpy.ops.render.render(write_still=True)
        shots.append(scene.render.filepath)
    subprocess.run([MAGICK] + shots + ["+append", "-resize", "1000x", os.path.join(PREV, "preview_extras_%s.png" % S1)], check=True)


def preview_draugr():
    """EK2's undead: the most trophies over the plain loincloth on the draugr body alone and with gaunt,
    fat and old, then over the war girdle and over the armoured skirt (draugr alone); front,
    three-quarter from the left, back three-quarter."""
    co = scene.camera
    co.data.ortho_scale = 80 if SEX == "female" else 66
    target = Vector((0, center_y(HIP_Z), 90 if SEX == "female" else 79))
    rows = []
    for tag, extra, look in (("draugr", None, NAME), ("gaunt", "gaunt", NAME), ("fat", "fat", NAME), ("old", "old", NAME),
                             ("war", None, WAR), ("armour", None, ARM)):
        for o in [body] + OBJS:
            for kb in o.data.shape_keys.key_blocks[1:]:
                kb.value = 1.0 if kb.name in (REFIT, extra) else 0.0
        for o in OBJS:
            o.hide_render = o.name not in (NAME, BAND, look, TROPHY[3])
            if o.name in (NAME, BAND):
                o.data.materials[0] = MATS[SET]
        shots = []
        for ang in (0, 60, 125):
            a = math.radians(ang)
            co.location = target + (FRONT * math.cos(a) + RIGHT * math.sin(a)) * 300
            co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
            scene.render.filepath = os.path.join(PREV, "d_%s_%s_%d.png" % (S1, tag, ang))
            bpy.ops.render.render(write_still=True)
            shots.append(scene.render.filepath)
        rows += ["("] + shots + ["+append", ")"]
    for o in [body] + OBJS:
        for kb in o.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
    subprocess.run([MAGICK] + rows + ["-append", "-resize", "900x", os.path.join(PREV, "preview_draugr_%s.png" % S1)], check=True)


def preview_layers():
    """The new pieces. Top row (adult): leggings with the plain loincloth and the fur cloak, front, side, back.
    Middle row (child): the tunic with the charms. Bottom row (child): the wrap skirt with the charms (and, on
    girls, the chest band). Front, side (the +x side), back."""
    co = scene.camera
    mant = next(o for o in OBJS if o.name == MANTLE)
    rows = []
    for tag, child, show in (("adult", False, (NAME, BAND, LEGG, MANTLE)), ("tunic", True, (TUNIC, CHARM, LEGG)),
                             ("skirt", True, (SKIRT, BAND, CHARM))):
        for o in [body] + OBJS:
            for kb in o.data.shape_keys.key_blocks[1:]:
                kb.value = 1.0 if (child and kb.name == "infant") else 0.0
        for o in OBJS:
            o.hide_render = o.name not in show
            if o.name in (NAME, BAND):
                o.data.materials[0] = MATS[SET]
        mant.data.materials[0] = MATS[ROBESET]
        zt = max(p.z for p in COORDS["infant" if child else "basis"])
        co.data.ortho_scale = zt + 6
        target = Vector((0, center_y(HIP_Z), zt / 2))
        shots = []
        for ang in (0, 90, 180):
            a = math.radians(ang)
            co.location = target + (FRONT * math.cos(a) + RIGHT * math.sin(a)) * 300
            co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
            scene.render.filepath = os.path.join(PREV, "n_%s_%s_%d.png" % (S1, tag, ang))
            bpy.ops.render.render(write_still=True)
            shots.append(scene.render.filepath)
        rows += ["("] + shots + ["+append", ")"]
    for o in [body] + OBJS:
        for kb in o.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
    mant.data.materials[0] = MATS[MSET]
    subprocess.run([MAGICK] + rows + ["-append", "-resize", "900x", os.path.join(PREV, "preview_layers_%s.png" % S1)], check=True)


if not GUI:  # in the app, look at the pieces in the viewport instead
    preview()
    preview_layers()
    preview_royal()
    preview_mantle()
    preview_extras()
    preview_draugr()
# Barbershop recolouring: masks, neutral diffuse, palettes, variations (rewrites the diffuse DDS from the PNGs)
subprocess.run([sys.executable, "-I", os.path.join(SRC, "tools", "make_colour.py")], check=True)
print("DONE %s in %.1fs" % (SEX, time.time() - T0))

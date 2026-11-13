"""CK3 portrait scene in the Maya GUI: the game's body on its skeleton, every body shape the game (vanilla + EK2)
uses, our pieces with their shapes, and the game's portrait poses. Run inside Maya (through the maya MCP):

    import sys; sys.path.insert(0, "<mod>/source/maya"); import ck3scene as cs
    cs.new_scene(); body = cs.load_body("male"); piece = cs.load_piece("ek2lc_m_reach_hide_01")
    cs.set_shape("bs_body_fat_1", 1.0); cs.pose("male", "throneRoom_kneel1_1", 10)

Port of the Blender inspector (source/legacy_blender/tools/inspect_setup.py). Everything is named so later tools
(audit.py, build.py) can find it: the body is BODY_<m|f>, a piece keeps its file name, blendShape nodes are
<mesh>_BS with one target per game attribute (bs_body_fat_1, giantish_body_bs, ...).
"""
import os
import maya.cmds as mc
import maya.api.OpenMaya as om
import numpy as np

GAME = os.path.expanduser("~/Library/Application Support/Steam/steamapps/common/Crusader Kings III/game")
EK2 = os.path.expanduser("~/Library/Application Support/Steam/steamapps/workshop/content/1158310/2887120253")
MOD = os.path.expanduser("~/Documents/Paradox Interactive/Crusader Kings III/mod/ek2_loincloths")
OUT = MOD + "/gfx/models/portraits/ek2lc/reach_hide_01"


def _ie():
    from io_pdx_mesh.pdx_maya import maya_import_export as ie
    return ie


# (our file suffix, game attribute, body blendshape file) per sex. Our pieces name their shape meshes
# <piece>_bs_<suffix>.mesh and link them to the attribute in the .asset.
def body_shapes(sex):
    V = "%s/gfx/models/portraits/%s_body/blendshapes" % (GAME, sex)
    E = "%s/gfx/models/portraits/%s_body/blendshapes" % (EK2, sex)
    s = [(k, "bs_body_%s_1" % k, "%s/%s_bs_body_%s_1.mesh" % (V, sex, k)) for k in ("fat", "gaunt", "muscular", "old", "dwarf")]
    s.append(("infant", "bs_body_infant_1", "%s/%s_bs_body_infant%s.mesh" % (V, sex, "_1" if sex == "female" else "")))
    if sex == "female":
        s += [("pregnant", "bs_body_pregnant_1", V + "/female_bs_body_pregnant_1.mesh"),
              ("breast_max", "bs_body_breast_size_max", V + "/female_bs_body_breast_size_max.mesh"),
              ("breast_min", "bs_body_breast_size_min", V + "/female_bs_body_breast_size_min.mesh")]
    s += [("khajiit", "bs_khajiit_body", "%s/%s_khajiit_body.mesh" % (E, sex)),
          ("argdigi", "argonian_digitigrade_bs", "%s/%s_argonian_digitigrade_bs.mesh" % (E, sex)),
          ("khadigi", "khajiit_digitigrade_bs", "%s/%s_khajiit_digitigrade_bs.mesh" % (E, sex)),
          ("draugr", "bs_draugr_body", "%s/%s_draugr_body.mesh" % (E, sex)),
          ("giantish", "giantish_body_bs", "%s/%s_giantish_body.mesh" % (E, sex)),
          ("imgan", "imgan_body_bs", "%s/%s_imgan_body.mesh" % (E, sex))]
    if sex == "male":
        s.append(("briarheart", "bs_briarheart_body", E + "/male_briarheart_body.mesh"))
    return s


def suffix_attr(sex):
    d = {k: a for k, a, f in body_shapes(sex)}
    d["seated"] = "bs_body_seated"   # pieces only: vanilla's throne drape (gene_seated), no body file
    d["kneel1"] = "whiskers_thin_1"   # pieces only: our kneel shapes (kneel.py) on EK2's unused whiskers attributes
    d["kneel2"] = "whiskers_thin_2"
    d["kneel1_fat"] = "whiskers_droop"   # the extra a heavy body needs (weight_for_portrait)
    d["kneel2_fat"] = "whiskers_wavy"
    return d


def new_scene():
    mc.file(new=True, force=True)
    _REST.clear()
    mc.currentUnit(time="film")  # 24 fps, as io_pdx_mesh expects for .anim files
    # io_pdx_mesh creates joints only when no joint of that name exists; nothing else to set up.


def _import(path, skel=True):
    before = set(mc.ls(type="transform", long=True))
    _ie().import_meshfile(path, imp_mesh=True, imp_skel=skel, imp_locs=False)
    new = [t for t in mc.ls(type="transform", long=True) if t not in before]
    meshes = [t for t in new if mc.listRelatives(t, shapes=True, type="mesh", fullPath=True)]
    return meshes


def _shape_targets(base, items, node_name):
    """items: [(alias, mesh file)]. Imports each file without a skeleton, makes it a target of a blendShape on
    base (in front of the skin cluster), then deletes the imported meshes."""
    tgts, names = [], []
    nv = mc.polyEvaluate(base, vertex=True)
    for alias, f in items:
        if not os.path.exists(f):
            continue
        m = _import(f, skel=False)
        if not m:
            continue
        t = m[0]
        if mc.polyEvaluate(t, vertex=True) != nv:
            print("SHAPE VERTEX COUNT MISMATCH", base, alias, mc.polyEvaluate(t, vertex=True), nv)
            mc.delete(m)
            continue
        t = mc.rename(t, alias + "_TGT")
        tgts.append(t)
        names.append(alias)
    if not tgts:
        return None
    bs = mc.blendShape(tgts, base, frontOfChain=True, name=node_name)[0]
    mc.delete(tgts)
    for i, a in enumerate(names):
        mc.aliasAttr(a, "%s.w[%d]" % (bs, i))
    return bs


def load_body(sex):
    path = "%s/gfx/models/portraits/%s_body/%s_body.mesh" % (GAME, sex, sex)
    m = _import(path, skel=True)
    body = mc.rename(m[0], "BODY_" + sex[0])
    _shape_targets(body, [(a, f) for k, a, f in body_shapes(sex)], "BODY_%s_BS" % sex[0])
    _store_rest()
    return body


def piece_shapes(name):
    """[(suffix, attribute, file)] for the shape meshes that exist for this piece."""
    sex = "female" if name.startswith("ek2lc_f_") else "male"
    sa = suffix_attr(sex)
    out = []
    for k, a in sa.items():
        f = "%s/%s_bs_%s.mesh" % (OUT, name, k)
        if os.path.exists(f):
            out.append((k, a, f))
    return out


def load_piece(name, folder=OUT):
    m = _import("%s/%s.mesh" % (folder, name), skel=True)
    if len(m) > 1:
        m = [mc.polyUniteSkinned(m, ch=False)[0]] if mc.ls(mc.listHistory(m[0]), type="skinCluster") else [mc.polyUnite(m, ch=False)[0]]
    t = mc.rename(m[0], name)
    if folder == OUT:
        _shape_targets(t, [(a, f) for k, a, f in piece_shapes(name)], name + "_BS")
    return t


def asset_textures(asset, folder=OUT):
    """{diffuse, normal, specular} file names from an .asset's first meshsettings."""
    import re
    t = open("%s/%s.asset" % (folder, asset), encoding="utf-8-sig").read()
    return {k: v for k, v in re.findall(r'texture_(diffuse|normal|specular)\s*=\s*"([^"]+)"', t)}


def texture_piece(mesh, asset=None, folder=OUT, alpha=True):
    """A lambert with the asset's diffuse (alpha as transparency, as the game's alpha-to-coverage shader)."""
    tx = asset_textures(asset or mesh, folder)
    f = "%s/%s" % (folder, tx["diffuse"])
    # the shipped diffuse is divided by its colour mask (source/tools/make_colour.py); the PNG source has the look
    for src in ("%s/source/textures/%s" % (MOD, tx["diffuse"]), "%s/source/textures/cultures/%s" % (MOD, tx["diffuse"])):
        if os.path.exists(src[:-4] + ".png"):
            f = src[:-4] + ".png"
            break
    sh = mc.shadingNode("lambert", asShader=True, name=mesh + "_MAT")
    fn = mc.shadingNode("file", asTexture=True, name=mesh + "_DIFF")
    mc.setAttr(fn + ".fileTextureName", f, type="string")
    mc.connectAttr(fn + ".outColor", sh + ".color")
    if alpha:
        mc.connectAttr(fn + ".outTransparency", sh + ".transparency")
    sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True, name=mesh + "_SG")
    mc.connectAttr(sh + ".outColor", sg + ".surfaceShader")
    mc.sets(mesh, edit=True, forceElement=sg)
    return sh


def bs_nodes():
    return mc.ls(type="blendShape")


def set_shape(attr, w=1.0, only=None):
    """Weight of one game attribute on the body and every piece (as the game does). attr=None zeroes all."""
    for bs in bs_nodes():
        if only and not any(bs.startswith(o) for o in only):
            continue
        for a in (mc.aliasAttr(bs, query=True) or [])[::2]:
            if attr is None or a == attr:
                mc.setAttr("%s.%s" % (bs, a), w if a == attr else 0.0)


# ---------------------------------------------------------------- poses
_REST = {}


def _store_rest():
    """Bind values of every joint. Call before the first pose(): io_pdx_mesh's anim import zeroes jointOrient
    (it bakes orientation into the rotation keys), so the rest pose needs the orient back as well."""
    for j in mc.ls(type="joint"):
        if j in _REST:
            continue
        _REST[j] = (mc.getAttr(j + ".translate")[0], mc.getAttr(j + ".rotate")[0], mc.getAttr(j + ".scale")[0],
                    mc.getAttr(j + ".jointOrient")[0])


def rest_pose():
    for j in mc.ls(type="joint"):
        for at in ("translate", "rotate", "scale"):
            for ax in "XYZ":
                p = "%s.%s%s" % (j, at, ax)
                for c in mc.listConnections(p, source=True, destination=False, type="animCurve") or []:
                    mc.delete(c)
        if j in _REST:
            t, r, s, jo = _REST[j]
            mc.setAttr(j + ".translate", *t)
            mc.setAttr(j + ".rotate", *r)
            mc.setAttr(j + ".scale", *s)
            mc.setAttr(j + ".jointOrient", *jo)


def anim_path(sex, anim):
    for root in (EK2, GAME):
        p = "%s/gfx/models/portraits/%s_body/%s_body_%s.anim" % (root, sex, sex, anim)
        if os.path.exists(p):
            return p
    return None


ROOTS = ("ground_joint", "body_root")


def pose(sex, anim, frame=None, static="clip"):
    """Play a portrait clip and hold one frame. As the game plays clips (see legacy weight_solver.game_pose),
    only the roots keep their translation keys; every other bone keeps its own length."""
    rest_pose()
    p = anim_path(sex, anim)
    if not p:
        raise RuntimeError("no anim %s %s" % (sex, anim))
    try:
        _ie().import_animfile(p, frame_start=1)
    except RuntimeError as e:  # clips that key bones the body lacks (sleeves): add them under the elbows, as Blender did
        import re
        missing = re.findall(r"'([^']+)'", str(e))
        if not missing:
            raise
        for n in missing:
            side = "l" if "_l_" in n else "r"
            par = "bn_%s_elbow" % side if "sleeve" in n else None
            mc.select(clear=True)
            j = mc.joint(name=n)
            if par and mc.objExists(par):
                mc.parent(j, par, relative=True)
        _store_rest()
        _ie().import_animfile(p, frame_start=1)
    for j in mc.ls(type="joint"):
        keyed = any(mc.listConnections("%s.%s%s" % (j, at, ax), source=True, destination=False, type="animCurve")
                    for at in ("translate", "rotate", "scale") for ax in "XYZ")
        if not keyed and j in _REST:
            t, r, s, jo = _REST[j]
            if static == "rest":  # the old rule (2026-11-07): bones a clip doesn't key stay at rest
                mc.setAttr(j + ".rotate", *r)
                mc.setAttr(j + ".jointOrient", *jo)
            # static == "clip" (2026-11-10, seen in game): a bone the clip lists without keys holds the clip's own
            # value (the throne clips seat the legs that way); only its length (and a root's position) as below
            if j not in ROOTS or static == "rest":
                mc.setAttr(j + ".translate", *t)
            mc.setAttr(j + ".scale", *s)
            continue
        if j in ROOTS:
            continue
        for ax in "XYZ":
            for c in mc.listConnections("%s.translate%s" % (j, ax), source=True, destination=False, type="animCurve") or []:
                mc.delete(c)
        if j in _REST:
            mc.setAttr(j + ".translate", *_REST[j][0])
    end = int(mc.playbackOptions(query=True, maxTime=True))
    f = end // 2 if frame is None else min(frame, end)
    mc.currentTime(f)
    return f


# ---------------------------------------------------------------- data
def points(mesh, world=True):
    sel = om.MSelectionList()
    sel.add(mesh)
    fn = om.MFnMesh(sel.getDagPath(0))
    pts = fn.getPoints(om.MSpace.kWorld if world else om.MSpace.kObject)
    return np.array([(p.x, p.y, p.z) for p in pts])


def mfn(mesh):
    sel = om.MSelectionList()
    sel.add(mesh)
    return om.MFnMesh(sel.getDagPath(0))


# ---------------------------------------------------------------- looking
def frame_view(objs, view="front", dist=None):
    """Point the active viewport camera at objs from front/back/left/right/three (three-quarter)."""
    bb = mc.exactWorldBoundingBox(objs)
    c = [(bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2]
    size = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
    d = dist or size * 2.2
    dirs = {"front": (0, 0, 1), "back": (0, 0, -1), "left": (1, 0, 0), "right": (-1, 0, 0),
            "three": (0.7, 0, 0.7), "below": (0, -0.6, 0.8)}
    v = dirs[view]
    cam = "persp"
    mc.xform(cam, worldSpace=True, translation=(c[0] + v[0] * d, c[1] + v[1] * d, c[2] + v[2] * d))
    mc.viewLookAt(cam, position=c)
    return cam

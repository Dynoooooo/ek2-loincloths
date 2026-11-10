"""Contact sheet of built Meshy pieces, one row per key: woman front / side / back, man front, woman kneeling
(side), woman on the throne (side). Textured with Meshy's base colour (what the diffuse .dds is made from).

    import sheet; sheet.rows(["people_keptu_ruler", ...], out="/tmp/x.jpg")
"""
import subprocess
import maya.cmds as mc
import ck3scene as cs
import look

VIEWS_F = [((0, 105, 190), (0, 85, 0)), ((190, 105, 0), (0, 85, 0)), ((0, 105, -190), (0, 85, 0))]


def _tex(mesh, key):
    sh = mc.shadingNode("lambert", asShader=True)
    sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True)
    mc.connectAttr(sh + ".outColor", sg + ".surfaceShader")
    f = mc.shadingNode("file", asTexture=True)
    mc.setAttr(f + ".fileTextureName", "%s/source/meshy/%s/model_textures/base_color.png" % (cs.MOD, key), type="string")
    mc.connectAttr(f + ".outColor", sh + ".color")
    mc.sets(mesh, e=True, forceElement=sg)


def _load(sex, keys):
    cs.new_scene()
    cs.load_body(sex)
    ps = {}
    for k in keys:
        n = "ek2lc_%s_%s_01" % (sex[0], k)
        if not mc.objExists(n) and not __import__("os").path.exists("%s/%s.mesh" % (cs.OUT, n)):
            continue                      # women-only pieces (chest bands)
        ps[k] = cs.load_piece(n)
        _tex(ps[k], k)
    for m in mc.ls(type="mesh"):          # as the game draws attachments (2026-11-10)
        mc.setAttr(m + ".backfaceCulling", 3)
    look.setup_view()
    return ps


def _shot(ps, k, cam, aim, path, w=200, h=260):
    for q in ps.values():
        mc.setAttr(q + ".visibility", q == ps[k])
    mc.xform("persp", ws=True, t=cam)
    mc.viewLookAt("persp", pos=aim)
    return look.shot(path, w, h)


def rows(keys, out, tmp="/tmp"):
    shots = {k: [] for k in keys}
    ps = _load("female", keys)
    for k in keys:
        for i, (c, a) in enumerate(VIEWS_F):
            shots[k].append(_shot(ps, k, c, a, "%s/sh_%s_f%d.jpg" % (tmp, k, i)))
    for clip, tag in (("throneRoom_kneel1_1", "kn"), ("throneRoom_ruler2_1", "th")):
        cs.pose("female", clip, 10)
        for k in keys:
            shots[k].append(_shot(ps, k, (150, 75, 60), (0, 55, 0), "%s/sh_%s_%s.jpg" % (tmp, k, tag)))
    cs.rest_pose()
    ps = _load("male", keys)
    for k in keys:
        if k in ps:
            shots[k].insert(3, _shot(ps, k, (0, 110, 190), (0, 90, 0), "%s/sh_%s_m.jpg" % (tmp, k)))
    rws = []
    for k in keys:
        r = "%s/shrow_%s.jpg" % (tmp, k)
        subprocess.run([look.MAGICK] + shots[k] + ["+append", r], check=True)
        subprocess.run([look.MAGICK, r, "-font", look.FONT, "-fill", "white", "-pointsize", "15", "-annotate", "+4+16",
                        k.replace("people_", ""), r], check=True)
        rws.append(r)
    subprocess.run([look.MAGICK] + rws + ["-append", "-resize", "1000x", out], check=True)
    return out

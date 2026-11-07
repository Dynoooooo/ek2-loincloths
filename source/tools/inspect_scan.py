"""Clipping scan in the live Blender app, over the animations inspect_setup.py loaded:

    exec(open("<mod>/source/tools/inspect_scan.py").read()); scan("male", pairs=..., step=5)

For each animation frame (every `step` frames) it measures, on the deformed meshes:
  - body: how deep each piece's vertices sink into the torso and legs (arms left out);
  - arm: how many of a piece's triangles cross the arms and hands;
  - a^b: how many triangles of two pieces worn together cross each other.
It prints the worst frame of each, with where it is, so `look` can show it.
"""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ARM_KEYS = ("elbow", "forearm", "wrist", "_fi_", "finger", "thumb", "hand", "prop", "sleeve")  # forearms and hands; the shoulders count as torso


def _ev(o, dg):
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    co = [v.co.copy() for v in me.vertices]
    tris = [tuple(p.vertices) for p in me.polygons]
    oe.to_mesh_clear()
    return co, tris


def _split(body):
    gi = {g.index for g in body.vertex_groups if any(k in g.name for k in ARM_KEYS)}
    armv = {v.index for v in body.data.vertices if sum(g.weight for g in v.groups if g.group in gi) > 0.5}
    polys = [tuple(p.vertices) for p in body.data.polygons]
    return [p for p in polys if not armv.intersection(p)], [p for p in polys if armv.intersection(p)]


def scan(sex, pieces=None, pairs=(), actions=None, step=5, depth_min=0.15, quiet_rest=False, shape=None):
    s1 = sex[0]
    sc = bpy.data.scenes[sex.capitalize()]
    bpy.context.window.scene = sc
    rig, body = bpy.data.objects["RIG_" + s1], bpy.data.objects["BODY_" + s1]
    for lc in bpy.context.view_layer.layer_collection.children:
        lc.exclude = False
    names = [o.name for o in sc.objects if o.name.startswith("ek2lc_")]
    if pieces:
        names = ["ek2lc_%s_%s_01" % (s1, p) for p in pieces]
    lab = {n: n[8:-3] for n in names}
    prs = [("ek2lc_%s_%s_01" % (s1, a), "ek2lc_%s_%s_01" % (s1, b)) for a, b in pairs]
    noarm, arm = _split(body)
    acts = [None] + sorted([a for a in bpy.data.actions if a.name.startswith(s1.upper() + "_")
                            and (actions is None or a.name[2:] in actions)], key=lambda a: a.name)
    report = {}
    for a in acts:
        if a is None:
            rig.animation_data.action = None
            for pb in rig.pose.bones:
                pb.location, pb.rotation_quaternion, pb.scale = (0, 0, 0), (1, 0, 0, 0), (1, 1, 1)
            frames, an = [1], "REST"
        else:
            rig.animation_data.action = a
            frames, an = range(int(a.frame_range[0]), int(a.frame_range[1]) + 1, step), a.name[2:]
        row = {}
        for f in frames:
            sc.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            bco, _ = _ev(body, dg)
            bt, ba = BVHTree.FromPolygons(bco, noarm), BVHTree.FromPolygons(bco, arm)
            data = {n: _ev(bpy.data.objects[n], dg) for n in names}
            bvh = {n: BVHTree.FromPolygons(c, t) for n, (c, t) in data.items()}
            for n in names:
                dmax, wp = 0.0, None
                for p in data[n][0]:
                    loc, nor, idx, d = bt.find_nearest(p)
                    if loc is not None and (p - loc).dot(nor) < -0.05 and d > dmax:
                        dmax, wp = d, p
                k = lab[n] + " /body"
                if dmax >= depth_min and dmax > row.get(k, (0,))[0]:
                    row[k] = (round(dmax, 2), f, tuple(round(x) for x in wp))
                ov = ba.overlap(bvh[n])
                k = lab[n] + " /arm"
                if len(ov) > row.get(k, (0,))[0]:
                    c_, t_ = data[n]
                    row[k] = (len(ov), f, tuple(round(x) for x in sum((c_[i] for i in t_[ov[0][1]]), Vector()) / len(t_[ov[0][1]])))
            for x, y in prs:
                ov = bvh[x].overlap(bvh[y])
                k = lab[x] + " ^ " + lab[y]
                if len(ov) > row.get(k, (0,))[0]:
                    c_, t_ = data[x]
                    row[k] = (len(ov), f, tuple(round(v) for v in sum((c_[i] for i in t_[ov[0][0]]), Vector()) / len(t_[ov[0][0]])))
        report[an] = row
        if row and not (quiet_rest and an == "REST"):
            print(an)
            for k, v in sorted(row.items()):
                print("    %-34s %s" % (k, v))
    rig.animation_data.action = None
    return report


def pose(sex, action, frame):
    """Put the rig in an animation frame for `look`."""
    s1 = sex[0]
    sc = bpy.data.scenes[sex.capitalize()]
    bpy.context.window.scene = sc
    bpy.data.objects["RIG_" + s1].animation_data.action = bpy.data.actions["%s_%s" % (s1.upper(), action)] if action else None
    sc.frame_set(frame)


def show(sex, *pieces):
    """Show only these pieces' collections (and the body)."""
    s1 = sex[0].upper()
    for lc in bpy.context.view_layer.layer_collection.children:
        lc.exclude = not any(lc.name == "%s_%s" % (s1, p) for p in pieces)

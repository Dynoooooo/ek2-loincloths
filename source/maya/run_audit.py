"""Audit driver, run inside Maya through the MCP in steps (each MCP call has a 600 s limit):

    import run_audit as ra
    ra.setup("male")              # new scene: body + every male piece (ek2lc_m_*), rest lengths per shape state
    ra.run_static()               # weights, shells, normals, UVs per piece
    for p in ra.POSES: ra.run_pose(p)   # clipping, poke-through, stretch per piece x shape state
    ra.save()                     # source/build_logs/audit/<sex>.json

A piece that lacks a body shape keeps its rest shape while the body changes, as in the game.
"""
import glob
import json
import os
import time
import numpy as np
import maya.cmds as mc
import ck3scene as cs
import audit as au

POSES = [("idle_1", None), ("throneRoom_ruler1_1", None), ("throneRoom_kneel1_1", None), ("throneRoom_kneel2_1", None),
         ("throneRoom_bow1_1", None), ("throneRoom_cheer1_1", None), ("sitting", None), ("throneRoom_curtsey1_1", None),
         ("throneRoom_rulerChild1_1", None)]
CHILD_POSES = ("throneRoom_rulerChild1_1",)
S = {}


def states(sex):
    st = [("base", {})]
    for k, a, f in cs.body_shapes(sex):
        st.append((k, {a: 1.0}))
    st += [("khajiit_full", {"bs_khajiit_body": 1.0, "khajiit_digitigrade_bs": 1.0}),
           ("child_half", {"bs_body_infant_1": 0.5}),
           ("fat_muscular", {"bs_body_fat_1": 1.0, "bs_body_muscular_1": 1.0})]
    return st


def apply(ws):
    cs.set_shape(None)
    for a, w in ws.items():
        cs.set_shape(a, w)


def setup(sex, pieces=None):
    t = time.time()
    cs.new_scene()
    au._BODY.clear()
    body = cs.load_body(sex)
    s1 = sex[0]
    if pieces is None:
        pieces = sorted(os.path.basename(p)[:-5] for p in glob.glob("%s/ek2lc_%s_*.mesh" % (cs.OUT, s1)) if "_bs_" not in p)
    loaded = []
    for p in pieces:
        try:
            loaded.append(cs.load_piece(p))
        except Exception as e:  # noqa
            print("LOAD FAILED", p, e)
    cs._store_rest()
    S.clear()
    S.update(sex=sex, body=body, pieces=loaded, static={}, res={}, edges={}, L0={})
    for p in loaded:
        S["edges"][p] = au.edges(p)
    cs.rest_pose()
    for name, ws in states(sex):
        apply(ws)
        for p in loaded:
            P = au.pts(p)
            e = S["edges"][p]
            S["L0"][(p, name)] = np.linalg.norm(P[e[:, 0]] - P[e[:, 1]], axis=1)
    apply({})
    print("setup", sex, len(loaded), "pieces", round(time.time() - t, 1), "s")


def run_static():
    t = time.time()
    cs.rest_pose()
    apply({})
    for p in S["pieces"]:
        try:
            S["static"][p] = au.static(p, S["body"])
        except Exception as e:  # noqa
            S["static"][p] = {"error": str(e)}
    print("static", round(time.time() - t, 1), "s")


def run_pose(anim, frame=None, names=None):
    t = time.time()
    if anim == "rest":
        cs.rest_pose()
        f = 0
    else:
        if not cs.anim_path(S["sex"], anim):
            print("no anim", anim)
            return
        f = cs.pose(S["sex"], anim, frame)
    for name, ws in states(S["sex"]):
        if names and name not in names:
            continue
        if anim in CHILD_POSES and name not in ("infant", "child_half"):
            continue
        apply(ws)
        for p in S["pieces"]:
            try:
                r = au.measure(p, S["body"], S["L0"][(p, name)], S["edges"][p])
            except Exception as e:  # noqa
                r = {"error": str(e)}
            S["res"].setdefault(p, {})["%s|%s" % (anim, name)] = r
    apply({})
    print("pose", anim, "frame", f, round(time.time() - t, 1), "s")


def save():
    d = cs.MOD + "/source/build_logs/audit"
    os.makedirs(d, exist_ok=True)
    out = {"sex": S["sex"], "static": S["static"], "res": S["res"]}
    with open("%s/%s.json" % (d, S["sex"]), "w") as fh:
        json.dump(out, fh, indent=0, default=str)
    print("saved", d)

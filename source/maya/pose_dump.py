"""Maya side of the weight solve: sample the game's poses and dump what the numpy solver (wsolve.py) needs.

    import pose_dump as pd
    pd.dump_poses("male")                       # source/build_logs/solve/poses_male.npz (once per sex)
    pd.dump_pieces("male", ["ek2lc_m_..."])     # source/build_logs/solve/piece_<name>.npz

Everything is in Maya world space (Y up, cm). Bone deform matrices are column-convention 4x4 (x' = M @ [x, 1]),
from the body skinCluster's bindPreMatrix and the posed joints. Port of the pose sampling in
source/legacy_blender/weight_solver.py (sample_poses): three frames per clip (first, middle, last); a frame whose
pelvis is within 3 cm of its rest height (and not a bow) is "ref" (standing: keeps the look checked in game),
the rest "free" (kneeling, sitting, bowing: clearance, shape and gravity count).
"""
import os
import numpy as np
import maya.cmds as mc
import ck3scene as cs
import audit as au

OUTD = cs.MOD + "/source/build_logs/solve"
STANDING_TOL = 3.0
HAND_KEYS = ("elbow", "forearm", "wrist", "_fi_", "finger", "thumb", "hand", "prop", "sleeve")


def solve_anims(sex):
    a = ["idle_1", "idle_2", "idle_3", "AI_callous_1", "emotion_angry", "emotion_grief", "emotion_happy",
         "emotion_sadness", "emotion_scheme"] + (["emotion_angry_start", "shocked_idle"] if sex == "male" else [])
    a += ["throneRoom_" + x for x in ("kneel1_1", "kneel2_1", "messenger1_1", "ruler1_1", "ruler2_1", "ruler3_1",
                                      "bow1_1", "bow2_1", "bow3_1", "cheer1_1", "applaud1_1", "conversation1_1",
                                      "conversation2_1", "chancellor_1", "oneHandedPassive1_1", "twoHandedPassive1_1")]
    if sex == "female":
        a.append("throneRoom_curtsey1_1")
    return a


def _body_bind(body):
    sc = mc.ls(mc.listHistory(body), type="skinCluster")[0]
    infl = mc.skinCluster(sc, query=True, influence=True)
    bpm = {}
    # bindPreMatrix is indexed like the influences' logical matrix connections
    for i in mc.getAttr("%s.matrix" % sc, multiIndices=True):
        j = mc.listConnections("%s.matrix[%d]" % (sc, i), source=True)[0]
        bpm[j] = np.array(mc.getAttr("%s.bindPreMatrix[%d]" % (sc, i))).reshape(4, 4)
    return infl, bpm


def _mats(bones, bpm):
    M = np.empty((len(bones), 4, 4))
    for k, j in enumerate(bones):
        if j in bpm and mc.objExists(j):
            wm = np.array(mc.getAttr(j + ".worldMatrix[0]")).reshape(4, 4)
            M[k] = (bpm[j] @ wm).T
        else:
            M[k] = np.eye(4)
    return M


def dump_poses(sex, anims=None):
    os.makedirs(OUTD, exist_ok=True)
    cs.new_scene()
    body = cs.load_body(sex)
    cs._store_rest()
    infl, bpm = _body_bind(body)
    bones = list(infl)
    W, _ = au.skin_weights(body)
    T, _ = au.tris(body)
    hand_b = np.array([any(k in b for k in HAND_KEYS) for b in bones])
    hand_v = W[:, hand_b].sum(1) > 0.5
    cs.rest_pose()
    rest_pts, rest_nrm = au.pts(body), au.vnormals(body)
    rest_root = mc.xform("body_root", query=True, worldSpace=True, translation=True)[1]
    joints_rest = np.array([mc.xform(b, query=True, worldSpace=True, translation=True) for b in bones])
    names, kinds, mats, bp, bn = [], [], [], [], []
    for a in anims or solve_anims(sex):
        p = cs.anim_path(sex, a)
        if not p:
            print("no anim", a)
            continue
        try:
            cs.pose(sex, a, 1)
        except Exception as e:  # noqa
            print("pose failed", a, str(e)[:100])
            continue
        f1 = int(mc.playbackOptions(query=True, maxTime=True))
        for f in sorted({1, (1 + f1) // 2, f1}):
            mc.currentTime(f)
            root = mc.xform("body_root", query=True, worldSpace=True, translation=True)[1]
            standing = abs(root - rest_root) < STANDING_TOL and "bow" not in a
            names.append("%s:%d" % (a, f))
            kinds.append("ref" if standing else "free")
            mats.append(_mats(bones, bpm))
            bp.append(au.pts(body).astype(np.float32))
            bn.append(au.vnormals(body).astype(np.float32))
    cs.rest_pose()
    np.savez_compressed("%s/poses_%s.npz" % (OUTD, sex), bones=np.array(bones), names=np.array(names),
                        kinds=np.array(kinds), mats=np.array(mats), body_pts=np.array(bp), body_nrm=np.array(bn),
                        rest_pts=rest_pts, rest_nrm=rest_nrm, tris=T, body_w=W, hand_v=hand_v,
                        joints_rest=joints_rest, rest_root=rest_root)
    print("poses", sex, len(names), "frames,", sum(k == "ref" for k in kinds), "standing")


def dump_pieces(sex, pieces):
    """Rest positions, triangles and current weights (dense over the body's bones) of loaded pieces."""
    d = np.load("%s/poses_%s.npz" % (OUTD, sex))
    bones = list(d["bones"])
    bi = {b: k for k, b in enumerate(bones)}
    cs.rest_pose()
    cs.set_shape(None)
    for p in pieces:
        w, infl = au.skin_weights(p)
        W = np.zeros((w.shape[0], len(bones)))
        for k, j in enumerate(infl):
            if j in bi:
                W[:, bi[j]] += w[:, k]
            elif w[:, k].any():
                print("piece bone not in body skeleton:", p, j, float(w[:, k].sum()))
        T, _ = au.tris(p)
        np.savez_compressed("%s/piece_%s.npz" % (OUTD, p), rest=au.pts(p), tris=T, W0=W)
    print("pieces dumped", len(pieces))

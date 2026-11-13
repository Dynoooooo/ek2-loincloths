"""Solved weights in and out: into a piece's skinCluster in the Maya scene (to look), and into the shipped .mesh
file's skin block (vertex order, shapes and everything else untouched).

    import skin_io; skin_io.apply_maya(piece)          # source/build_logs/solve/w_<piece>.npz -> skinCluster
    skin_io.patch_mesh(piece)                          # same weights -> gfx/.../<piece>.mesh (pure python, no Maya
                                                       # needed: io_pdx_mesh's pdx_data reader/writer)
io_pdx_mesh creates Maya vertex i from file vertex i (no welding), so the weights map 1:1.
"""
import os
import numpy as np

MOD = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = MOD + "/gfx/models/portraits/ek2lc/reach_hide_01"
D = MOD + "/source/build_logs/solve"


def load(piece):
    d = np.load("%s/w_%s.npz" % (D, piece))
    return [[str(b) for b in row] for row in d["bones"]], d["weights"]


def apply_maya(piece, bones=None, weights=None):
    import maya.cmds as mc
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    if bones is None:
        bones, weights = load(piece)
    sc = mc.ls(mc.listHistory(piece), type="skinCluster")[0]
    infl = mc.skinCluster(sc, query=True, influence=True)
    need = sorted({b for row, wr in zip(bones, weights) for b, w in zip(row, wr) if w > 0} - set(infl))
    for b in need:
        mc.skinCluster(sc, edit=True, addInfluence=b, weight=0.0, lockWeights=False)
    infl = mc.skinCluster(sc, query=True, influence=True)
    ii = {b: k for k, b in enumerate(infl)}
    n = len(bones)
    W = np.zeros((n, len(infl)))
    for v in range(n):
        for b, w in zip(bones[v], weights[v]):
            if w > 0:
                W[v, ii[b]] += w
    sel = om.MSelectionList()
    sel.add(sc)
    fn = oma.MFnSkinCluster(sel.getDependNode(0))
    sel2 = om.MSelectionList()
    sel2.add(piece)
    dp = sel2.getDagPath(0)
    comp = om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
    om.MFnSingleIndexedComponent(comp).setCompleteData(n)
    mc.setAttr(sc + ".normalizeWeights", 0)
    fn.setWeights(dp, comp, om.MIntArray(list(range(len(infl)))), om.MDoubleArray(W.ravel().tolist()), False)
    mc.setAttr(sc + ".normalizeWeights", 1)
    return len(need)


def patch_mesh(piece, bones=None, weights=None, path=None, out=None):
    """Write the weights into the .mesh skin block (bone indices into the file's own skeleton)."""
    import sys
    sys.path.insert(0, os.path.expanduser("~/Library/Preferences/Autodesk/maya/scripts"))
    from io_pdx_mesh import pdx_data
    if bones is None:
        bones, weights = load(piece)
    path = path or "%s/%s.mesh" % (OUT, piece)
    root = pdx_data.read_meshfile(path)
    obj = root.find("object")
    shapes = list(obj)
    assert len(shapes) == 1, "one shape per piece expected"
    shp = shapes[0]
    meshes = shp.findall("mesh")
    assert len(meshes) == 1, "one mesh per piece expected"
    skel = shp.find("skeleton")
    names = [b.tag for b in skel]
    six = {b.tag: int(b.attrib["ix"][0]) for b in skel}
    mesh = meshes[0]
    skin = mesh.find("skin")
    nv = len(mesh.attrib["p"]) // 3
    assert nv == len(bones), "vertex count %d != %d" % (nv, len(bones))
    missing = sorted({b for row, wr in zip(bones, weights) for b, w in zip(row, wr) if w > 0} - set(names))
    assert not missing, "bones not in the file's skeleton: %s" % missing
    ix, ww = [], []
    for v in range(nv):
        row = [(six[b], float(w)) for b, w in zip(bones[v], weights[v]) if w > 0]
        row.sort(key=lambda t: -t[1])
        row = row[:4]
        tot = sum(w for _, w in row)
        row = [(i, w / tot) for i, w in row]
        while len(row) < 4:
            row.append((-1, 0.0))
        ix += [i for i, _ in row]
        ww += [w for _, w in row]
    skin.attrib["bones"] = [4]
    skin.attrib["ix"] = ix
    skin.attrib["w"] = ww
    pdx_data.write_meshfile(out or path, root)
    return nv

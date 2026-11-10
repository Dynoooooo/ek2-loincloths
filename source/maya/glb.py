"""Minimal glTF binary (.glb) reader: positions, normals, UVs and triangles of every mesh primitive, with the node
transforms applied, plus the embedded images. Pure numpy (no Maya), so mayapy can use it too.

    import glb; V, N, UV, T, images = glb.load(path)

glTF is Y up with the model's front at +Z, which is Maya's (and our CK3 scene's) space, so nothing is turned.
UVs stay as glTF stores them (origin at the top left, v down), which is how .mesh files store u0.
"""
import json
import struct
import numpy as np

_CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _chunks(data):
    magic, version, length = struct.unpack_from("<III", data, 0)
    assert magic == 0x46546C67, "not a glb file"
    off, js, bin_ = 12, None, None
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off)
        body = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(body.decode("utf-8"))
        elif ctype == 0x004E4942:
            bin_ = body
        off += 8 + clen
    return js, bin_


def _accessor(js, bin_, i):
    a = js["accessors"][i]
    bv = js["bufferViews"][a["bufferView"]]
    dt = np.dtype(_CT[a["componentType"]])
    nc = _NC[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0) or dt.itemsize * nc
    cnt = a["count"]
    raw = np.frombuffer(bin_, np.uint8, count=stride * (cnt - 1) + dt.itemsize * nc, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, shape=(cnt, dt.itemsize * nc), strides=(stride, 1))
    out = np.frombuffer(rows.copy().tobytes(), dt).reshape(cnt, nc).astype(np.float64)
    if a.get("normalized") and dt != np.float32:
        out /= np.iinfo(dt).max
    return out


def _node_matrix(n):
    if "matrix" in n:
        return np.array(n["matrix"], float).reshape(4, 4).T
    M = np.eye(4)
    if "scale" in n:
        M = np.diag(list(n["scale"]) + [1.0]) @ M
    if "rotation" in n:
        x, y, z, w = n["rotation"]
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        Rm = np.eye(4)
        Rm[:3, :3] = R
        M = Rm @ M
    if "translation" in n:
        Tm = np.eye(4)
        Tm[:3, 3] = n["translation"]
        M = Tm @ M
    return M


def load(path):
    data = open(path, "rb").read()
    js, bin_ = _chunks(data)
    Vs, Ns, UVs, Ts = [], [], [], []
    base = 0

    def visit(ni, parent):
        nonlocal base
        n = js["nodes"][ni]
        M = parent @ _node_matrix(n)
        if "mesh" in n:
            for prim in js["meshes"][n["mesh"]]["primitives"]:
                at = prim["attributes"]
                V = _accessor(js, bin_, at["POSITION"])
                V = (np.c_[V, np.ones(len(V))] @ M.T)[:, :3]
                if "NORMAL" in at:
                    Nn = _accessor(js, bin_, at["NORMAL"]) @ np.linalg.inv(M[:3, :3])
                    Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-12)
                else:
                    Nn = np.zeros_like(V)
                UV = _accessor(js, bin_, at["TEXCOORD_0"]) if "TEXCOORD_0" in at else np.zeros((len(V), 2))
                T = _accessor(js, bin_, prim["indices"]).astype(np.int64).reshape(-1, 3) if "indices" in prim \
                    else np.arange(len(V)).reshape(-1, 3)
                if np.linalg.det(M[:3, :3]) < 0:
                    T = T[:, ::-1]
                Vs.append(V), Ns.append(Nn), UVs.append(UV), Ts.append(T + base)
                base += len(V)
        for c in n.get("children", []):
            visit(c, M)

    scene = js["scenes"][js.get("scene", 0)]
    for ni in scene["nodes"]:
        visit(ni, np.eye(4))
    images = []
    for im in js.get("images", []):
        if "bufferView" in im:
            bv = js["bufferViews"][im["bufferView"]]
            o = bv.get("byteOffset", 0)
            images.append((im.get("mimeType", ""), bin_[o:o + bv["byteLength"]]))
    return np.vstack(Vs), np.vstack(Ns), np.vstack(UVs), np.vstack(Ts), images

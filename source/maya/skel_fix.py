"""Give a piece's .mesh the game body's own skeleton (same bones, same ix order) and remap its skin by bone name.

The game maps a piece's skin indices onto the body's bones by index, not by name (seen 2026-11-10: the women's
Reach pieces carried two extra bones, bn_l_sleeve/bn_r_sleeve, inserted at ix 30/40, so every later index slid by
1-2 and the leggings' hip weights drove the ankles: seated, the thighs stood upright). Run inside Maya (or mayapy):

    import skel_fix; skel_fix.check(path, "female"); skel_fix.fix(path, "female")
"""
import copy
import os
from io_pdx_mesh import pdx_data

GAME = os.path.expanduser("~/Library/Application Support/Steam/steamapps/common/Crusader Kings III/game")


def body_skeleton(sex):
    r = pdx_data.read_meshfile("%s/gfx/models/portraits/%s_body/%s_body.mesh" % (GAME, sex, sex))
    return r.find("object")[0].find("skeleton")


def _ix(skel):
    return {j.tag: int(j.attrib["ix"][0]) for j in list(skel)}


def check(path, sex):
    """[(bone, body ix, piece ix)] for every bone whose index differs, plus bones the body lacks."""
    body = _ix(body_skeleton(sex))
    out = []
    for sh in pdx_data.read_meshfile(path).find("object"):
        sk = sh.find("skeleton")
        if sk is None:
            continue
        for k, i in _ix(sk).items():
            if body.get(k) != i:
                out.append((k, body.get(k), i))
    return out


def fix(path, sex):
    """Rewrites path in place. Raises if a weighted bone is missing from the body. Returns the bones dropped."""
    bsk = body_skeleton(sex)
    body = _ix(bsk)
    root = pdx_data.read_meshfile(path)
    dropped = set()
    for sh in root.find("object"):
        sk = sh.find("skeleton")
        if sk is None:
            continue
        name = {int(j.attrib["ix"][0]): j.tag for j in list(sk)}
        for m in sh.findall("mesh"):
            s = m.find("skin")
            if s is None:
                continue
            ix = []
            for i, w in zip(s.attrib["ix"], s.attrib["w"]):
                if i < 0:
                    ix.append(-1)
                    continue
                b = name[i]
                if b not in body:
                    if w > 0:
                        raise RuntimeError("%s: weighted bone %s is not on the %s body" % (path, b, sex))
                    ix.append(-1)
                    continue
                ix.append(body[b])
            s.attrib["ix"] = ix
        dropped |= {b for b in name.values() if b not in body}
        pos = list(sh).index(sk)
        sh.remove(sk)
        sh.insert(pos, copy.deepcopy(bsk))
    pdx_data.write_meshfile(path, root)
    return sorted(dropped)

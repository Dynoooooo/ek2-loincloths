"""2026-11-10: repair the Meshy pieces written before mbuild.normal_ids (3-15% of their triangles were shaded facing
inward: dark patches in game) and give them the flipped copies of triangles seen from behind (mbuild.double_exposed).
Run inside Maya: import fix_meshy_normals as fx; fx.run()
"""
import os
import ck3scene as cs
import mbuild as mb
import audit as au

SKIP = ("lich_hide", "lich_fine", "lich_royal", "lich_skirt", "lich_tunic", "lich_band", "lich_band_fine",
        "lich_band_royal", "lich_war", "lich_armour", "lich_duke", "lich_king", "lich_emperor", "lich_camp_wrap",
        "lich_kid_charm", "lich_trophy_1", "lich_trophy_2", "lich_trophy_3", "lich_leggings", "lich_mantle",
        "lich_fur_robe", "lich_arena_guard")   # remade with the fixed writer (lich_remake.py)


def keys():
    return sorted(d for d in os.listdir(mb.MESHY) if os.path.isdir(os.path.join(mb.MESHY, d)) and d not in SKIP)


def run(double=True, log=print):
    for sex in ("male", "female"):
        cs.new_scene()
        au._BODY.clear()
        body = cs.load_body(sex)
        for k in keys():
            name = "ek2lc_%s_%s_01" % (sex[0], k)
            if not os.path.exists("%s/%s.mesh" % (cs.OUT, name)):
                continue
            mb.fix_normals(name, log=log)
            if double:
                mb.double_exposed(name, body, log=log)
    for k in keys():   # artifact-window models (static, no shapes)
        name = "ek2lc_%s_artifact" % k
        if os.path.exists("%s/%s.mesh" % (cs.OUT, name)):
            mb.fix_normals(name, log=log)

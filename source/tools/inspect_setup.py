"""Inspection scene for the live Blender app (run through MCP for Blender, never headless):

    exec(open("<mod>/source/tools/inspect_setup.py").read())

Builds two scenes, "Male" and "Female", each with the vanilla body on its own rig, every exported piece
of the mod (the game's .mesh files, Reach textures from source/textures) in its own collection, and the
portrait animations the game plays most (idle, events, throne room) as actions on the rig.
Then inspect_scan.py measures clipping over those animations, and `look` shows it.
"""
import bpy, os

MOD = os.path.expanduser("~/Documents/Paradox Interactive/Crusader Kings III/mod/ek2_loincloths")
GAME = os.path.expanduser("~/Library/Application Support/Steam/steamapps/common/Crusader Kings III/game")
OUT = MOD + "/gfx/models/portraits/ek2lc/reach_hide_01"
TEX = MOD + "/source/textures"
PIECES = {  # piece -> texture set (Reach colours)
    "reach_hide": "ek2lc_reach_hide_01", "reach_band": "ek2lc_reach_hide_01", "leggings": "ek2lc_leggings_01",
    "reach_war": "ek2lc_reach_war_01", "reach_armour": "ek2lc_reach_armour_01", "reach_duke": "ek2lc_reach_duke_01",
    "reach_king": "ek2lc_reach_king_01", "reach_mantle": "ek2lc_reach_mantle_01", "trophy_1": "ek2lc_reach_war_01",
    "trophy_3": "ek2lc_reach_war_01", "reach_skirt": "ek2lc_reach_hide_01", "reach_tunic": "ek2lc_reach_hide_01",
    "kid_charm": "ek2lc_charm_01", "camp_wrap": "ek2lc_camp_01", "arena_guard": "ek2lc_reach_armour_01",
}
ANIMS = ["idle_1", "idle_2", "idle_3", "emotion_angry", "emotion_angry_start", "AI_callous_1", "emotion_grief",
         "emotion_happy", "emotion_sadness", "emotion_scheme", "shocked_idle", "throneRoom_ruler1_1", "throneRoom_kneel1_1"]


def _import(path):
    before = set(bpy.data.objects)
    bpy.ops.io_pdx_mesh.import_mesh(filepath=path, chk_mesh=True, chk_skel=True, chk_locs=False, chk_joinmats=True)
    return [o for o in bpy.data.objects if o not in before]


class _HideRigs:
    """io_pdx_mesh reuses any armature in the file with the same bones; hide the other sex's rig."""
    def __init__(self, keep=None):
        self.keep, self.saved = keep, []

    def __enter__(self):
        dummy = bpy.data.armatures.get("EK_DUMMY") or bpy.data.armatures.new("EK_DUMMY")
        for o in bpy.data.objects:
            if o.type == 'ARMATURE' and o is not self.keep and o.data is not dummy:
                o.data.use_fake_user = True
                self.saved.append((o, o.data))
                o.data = dummy
        return self

    def __exit__(self, *a):
        for o, d in self.saved:
            o.data = d


def _texture(o, tset):
    m = o.data.materials[0]
    nt = m.node_tree
    tex = next(n for n in nt.nodes if n.type == 'TEX_IMAGE')
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    p = os.path.join(TEX, tset + "_diffuse.png")
    if os.path.exists(p):
        tex.image = bpy.data.images.load(p, check_existing=True)
        if not tex.outputs['Color'].links:
            nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        if 'Alpha' in tex.outputs and not tex.outputs['Alpha'].links:
            nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    bsdf.inputs['Roughness'].default_value = 0.75


def _add_bones(rig, names):
    """Bones some animations key but the body mesh's skeleton lacks (sleeves, ground_joint)."""
    missing = [n for n in names if n not in rig.data.bones]
    if not missing:
        return
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    for n in missing:
        side = "l" if "_l_" in n else "r"
        par = eb.get("bn_%s_elbow" % side) if "sleeve" in n else None
        b = eb.new(n)
        b.head, b.tail = ((par.head.copy(), par.tail.copy()) if par else ((0, 0, 0), (0, 0, 5)))
        b.parent = par
    bpy.ops.object.mode_set(mode='OBJECT')


def build_scene(sex):
    s1 = sex[0]
    sc = bpy.data.scenes.get(sex.capitalize()) or bpy.data.scenes.new(sex.capitalize())
    bpy.context.window.scene = sc
    for o in list(sc.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    with _HideRigs():
        new = _import("%s/gfx/models/portraits/%s_body/%s_body.mesh" % (GAME, sex, sex))
    rig = next(o for o in new if o.type == 'ARMATURE')
    rig.name = "RIG_" + s1
    body = next(o for o in new if o.type == 'MESH')
    body.name = "BODY_" + s1
    with _HideRigs(keep=rig):
        for p, tset in PIECES.items():
            path = "%s/ek2lc_%s_%s_01.mesh" % (OUT, s1, p)
            if not os.path.exists(path):
                continue
            for o in _import(path):
                if o.type != 'MESH':
                    continue
                o.name = "ek2lc_%s_%s_01" % (s1, p)
                _texture(o, tset)
                cn = "%s_%s" % (s1.upper(), p)
                c = bpy.data.collections.get(cn) or bpy.data.collections.new(cn)
                if c.name not in sc.collection.children:
                    sc.collection.children.link(c)
                for uc in list(o.users_collection):
                    uc.objects.unlink(o)
                c.objects.link(o)
        _add_bones(rig, ["bn_l_sleeve", "bn_r_sleeve"])
        rig.animation_data_create()
        for a in ANIMS:
            path = "%s/gfx/models/portraits/%s_body/%s_body_%s.anim" % (GAME, sex, sex, a)
            if not os.path.exists(path):
                continue
            rig.animation_data.action = None
            bpy.context.view_layer.objects.active = rig
            try:
                bpy.ops.io_pdx_mesh.import_anim(filepath=path, int_start=1)
            except RuntimeError as e:
                print("anim not imported:", a, str(e).splitlines()[0][:120])
                continue
            act = rig.animation_data.action
            act.name = "%s_%s" % (s1.upper(), a)
            act.use_fake_user = True
        rig.animation_data.action = None
    print(sex, "pieces:", sorted(c.name for c in sc.collection.children),
          "anims:", sorted(a.name for a in bpy.data.actions if a.name.startswith(s1.upper() + "_")))
    return sc


if __name__ in ("__main__", "<run_path>") or True:
    for _o in list(bpy.data.objects):
        bpy.data.objects.remove(_o, do_unlink=True)
    for _c in list(bpy.data.collections):
        bpy.data.collections.remove(_c)
    for _a in list(bpy.data.actions):
        bpy.data.actions.remove(_a)
    build_scene("male")
    build_scene("female")

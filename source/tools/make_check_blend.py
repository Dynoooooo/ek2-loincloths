"""Make a .blend for checking the loincloth by eye: the build's .blend plus a CK3 idle
animation on the rig, the timeline set to it, and a front view in Material Preview.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python make_check_blend.py -- \
      <build .blend> <CK3 .anim> <output .blend>
"""
import bpy, addon_utils, sys, math
from mathutils import Euler

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, ANIM, OUT = argv[0], argv[1], argv[2]
bpy.ops.wm.open_mainfile(filepath=SRC)
addon_utils.enable("bl_ext.user_default.io_pdx_mesh", default_set=True)
sc = bpy.context.scene
rig = next(o for o in sc.objects if o.type == "ARMATURE")
for o in sc.objects:
    o.select_set(False)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.io_pdx_mesh.import_anim(filepath=ANIM)
act = rig.animation_data.action
sc.frame_start, sc.frame_end = int(act.frame_range[0]), int(act.frame_range[1])
sc.frame_set(int(sum(act.frame_range) / 2))
rig.hide_set(True)  # still drives the meshes; just keeps the bones out of the way
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == "VIEW_3D":
            sp = area.spaces.active
            sp.shading.type = "MATERIAL"
            r = sp.region_3d
            r.view_perspective = "PERSP"
            r.view_location = (0.0, 0.0, 82.0)
            r.view_distance = 120.0
            r.view_rotation = Euler((math.radians(88), 0, 0)).to_quaternion()  # front
lo = sc.objects.get("ek2lc_m_reach_hide_01")
if lo:
    for o in sc.objects:
        o.select_set(False)
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("CHECK saved", OUT, "frames", sc.frame_start, sc.frame_end)

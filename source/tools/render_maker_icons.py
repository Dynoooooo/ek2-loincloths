"""Render the Loincloth Maker icons in the Blender app, after build_regalia.py (male) built the wedding wrap:

    exec(open("<mod>/source/tools/render_maker_icons.py").read()); start_maker_icons()

The wedding wrap alone (unposed) with a bone needle and sinew thread through it. Trait icons (120x120, three ranks:
bronze, silver, gold rim) and the court position's (70x70), uncompressed DDS as vanilla's. Log: build_logs/maker_icons.log.
"""
import bpy
import math
import os
import subprocess
from mathutils import Vector

MOD = os.path.expanduser("~/Documents/Paradox Interactive/Crusader Kings III/mod/ek2_loincloths")
SRC = os.path.join(MOD, "source/textures/icons")
MAGICK = "/opt/homebrew/bin/magick"


def _mat(name, rgb, rough=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def render(log):
    sc = bpy.context.scene
    o = sc.objects["ek2lc_m_wedding_wrap_01"]
    for m in o.modifiers:
        m.show_render = m.show_viewport = False
    o.location = (0, 0, 0)
    bb = [o.matrix_world @ v.co for v in o.data.vertices]
    lo, hi = Vector([min(p[i] for p in bb) for i in range(3)]), Vector([max(p[i] for p in bb) for i in range(3)])
    c = (lo + hi) / 2
    extra = []
    # the needle: a bone shaft with an eye, crossing the apron
    bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=1.1, radius2=0.15, depth=36, location=Vector((c.x, lo.y - 2.0, c.z + 2)))
    nd = bpy.context.active_object
    nd.rotation_euler = (0, math.radians(55), 0)
    nd.data.materials.append(_mat("icon_bone", (0.85, 0.8, 0.66), 0.4))
    extra.append(nd)
    # the thread: a curve from the needle's eye looping over the apron
    cu = bpy.data.curves.new("icon_thread", "CURVE")
    cu.dimensions, cu.bevel_depth = "3D", 0.45
    sp = cu.splines.new("BEZIER")
    f = lo.y - 2.5
    pts = [Vector((c.x - 13, f, c.z + 14)), Vector((c.x - 4, f - 0.5, c.z + 8)), Vector((c.x + 6, f - 0.8, c.z + 16)),
           Vector((c.x + 12, f, c.z + 2))]
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    th = bpy.data.objects.new("icon_thread", cu)
    th.data.materials.append(_mat("icon_sinew", (0.6, 0.12, 0.08), 0.6))
    sc.collection.objects.link(th)
    extra.append(th)
    for x in sc.objects:
        x.hide_render = not (x is o or x in extra)
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = e
            break
        except TypeError:
            pass
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = 480
    cam_d = bpy.data.cameras.new("icon_cam")
    cam_d.type, cam_d.clip_end = "ORTHO", 1000
    cam_d.ortho_scale = max(hi.x - lo.x, hi.z - lo.z) * 1.25
    cam = bpy.data.objects.new("icon_cam", cam_d)
    sc.collection.objects.link(cam)
    d = Vector((0.35, -1.0, 0.25)).normalized()
    cam.location = c + d * 300
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    ld = bpy.data.lights.new("icon_sun", "SUN")
    ld.energy = 4.0
    lo_ = bpy.data.objects.new("icon_sun", ld)
    lo_.rotation_euler = (math.radians(50), 0, math.radians(-30))
    sc.collection.objects.link(lo_)
    sc.camera = cam
    os.makedirs(SRC, exist_ok=True)
    png = os.path.join(SRC, "maker_raw.png")
    sc.render.filepath = png
    bpy.ops.render.render(write_still=True)
    for x in extra + [cam, lo_]:
        bpy.data.objects.remove(x, do_unlink=True)
    T = os.path.join(MOD, "gfx/interface/icons/traits")
    P = os.path.join(MOD, "gfx/interface/icons/court_position_types")
    os.makedirs(T, exist_ok=True)
    os.makedirs(P, exist_ok=True)
    for lv, rim in ((1, "#9a6a3a"), (2, "#c8ccd2"), (3, "#e8bf4a")):
        out = os.path.join(SRC, "maker_%d.png" % lv)
        subprocess.run([MAGICK, "-size", "120x120", "xc:none", "-fill", "#2a1d14", "-stroke", rim, "-strokewidth", str(4 + lv),
                        "-draw", "circle 60,60 60,6", "(", png, "-resize", "96x96", ")", "-gravity", "center", "-compose", "over",
                        "-composite", out], check=True)
        subprocess.run([MAGICK, out, "-define", "dds:compression=none", "-define", "dds:mipmaps=0",
                        os.path.join(T, "ek2lc_loincloth_maker_%d.dds" % lv)], check=True)
    out = os.path.join(SRC, "maker_position.png")
    subprocess.run([MAGICK, "-size", "70x70", "xc:none", "-fill", "#d9c9a3", "-draw", "circle 35,35 35,2", "(", png, "-resize", "62x62",
                    ")", "-gravity", "center", "-compose", "over", "-composite", out], check=True)
    subprocess.run([MAGICK, out, "-define", "dds:compression=none", "-define", "dds:mipmaps=6",
                    os.path.join(P, "ek2lc_loincloth_maker_court_position.dds")], check=True)
    log.write("maker icons written\n")


def start_maker_icons():
    def run():
        with open(os.path.join(MOD, "source/build_logs/maker_icons.log"), "w", buffering=1) as log:
            try:
                render(log)
                log.write("ICONS OK\n")
            except Exception:
                import traceback
                log.write(traceback.format_exc() + "\nICONS FAILED\n")
        return None
    bpy.app.timers.register(run, first_interval=0.2)
    return "maker icon render started"

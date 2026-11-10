"""Render the regalia artifacts' inventory icons in the Blender app, after build_regalia.py (male) left its pieces
in the scene:

    exec(open("<mod>/source/tools/render_regalia_icons.py").read()); start_icons()

Each piece alone, unposed, from the front and a little to its left, on a transparent background. Vanilla's
artifact icons are 960x240 strips, one 240x240 frame per rarity (common, masterwork, famed, illustrious), so
the strip is the render four times: dulled, as is, brighter with a gold glow, brightest with a stronger glow.
Uncompressed DDS without mip levels, as vanilla's. Log: source/build_logs/icons.log.
"""
import bpy
import math
import os
import subprocess
from mathutils import Vector

MOD = os.path.expanduser("~/Documents/Paradox Interactive/Crusader Kings III/mod/ek2_loincloths")
ICONS = os.path.join(MOD, "gfx/interface/icons/artifact")
SRC = os.path.join(MOD, "source/textures/icons")
MAGICK = "/opt/homebrew/bin/magick"
KEYS = ["art_champion", "art_fauld", "art_feather", "art_briar", "art_amber", "art_bone", "art_ash", "art_moon"]


def _engine(sc):
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        try:
            sc.render.engine = e
            return e
        except TypeError:
            continue


def _frames(png, out_dds):
    t = png[:-4]
    glow = lambda col, sig, op: ["(", png, "-alpha", "extract", "-blur", "0x%d" % sig, "-level", "0,60%%",
                                 "-background", col, "-alpha", "shape", "-channel", "A", "-evaluate", "multiply", op, "+channel", ")"]
    cmds = [
        [MAGICK, png, "-modulate", "80,45", t + "_1.png"],
        [MAGICK, png, t + "_2.png"],
        [MAGICK] + glow("#e8b84a", 6, "0.6") + ["(", png, "-modulate", "108,115", ")", "-compose", "over", "-composite", t + "_3.png"],
        [MAGICK] + glow("#ffd76a", 9, "1.0") + ["(", png, "-modulate", "115,125", ")", "-compose", "over", "-composite", t + "_4.png"],
        [MAGICK, t + "_1.png", t + "_2.png", t + "_3.png", t + "_4.png", "+append", "-define", "dds:compression=none",
         "-define", "dds:mipmaps=0", out_dds],
    ]
    for c in cmds:
        subprocess.run(c, check=True)


def render_icons(log):
    os.makedirs(ICONS, exist_ok=True)
    os.makedirs(SRC, exist_ok=True)
    sc = bpy.context.scene
    keep = {o.name: o.hide_render for o in sc.objects}
    eng = _engine(sc)
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = 480
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    cam_d = bpy.data.cameras.new("icon_cam")
    cam_d.type = "ORTHO"
    cam = bpy.data.objects.new("icon_cam", cam_d)
    sc.collection.objects.link(cam)
    lights = []
    for nm, rot, en in (("icon_key", (math.radians(50), 0, math.radians(-30)), 4.0), ("icon_fill", (math.radians(70), 0, math.radians(140)), 1.5)):
        ld = bpy.data.lights.new(nm, "SUN")
        ld.energy = en
        lo = bpy.data.objects.new(nm, ld)
        lo.rotation_euler = rot
        sc.collection.objects.link(lo)
        lights.append(lo)
    old_cam = sc.camera
    sc.camera = cam
    for key in KEYS:
        o = sc.objects.get("ek2lc_m_%s_01" % key)
        if o is None:
            log.write("missing %s\n" % key)
            continue
        for x in sc.objects:
            if x.type == "MESH":
                x.hide_render = x is not o
        for m in o.modifiers:
            m.show_render = m.show_viewport = False
        o.location = (0, 0, 0)
        bb = [o.matrix_world @ v.co for v in o.data.vertices]
        lo_, hi = Vector([min(p[i] for p in bb) for i in range(3)]), Vector([max(p[i] for p in bb) for i in range(3)])
        c = (lo_ + hi) / 2
        front = -1.0 if sum(p.y for p in bb) / len(bb) < c.y + 50 else 1.0  # our bodies face -y
        d = Vector((0.45, -1.0, 0.3)).normalized()
        cam.location = c + d * 300
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        ext = max(hi.x - lo_.x, hi.z - lo_.z, hi.y - lo_.y)
        cam_d.ortho_scale = ext * 1.12
        cam_d.clip_end = 1000
        png = os.path.join(SRC, "ek2lc_%s.png" % key)
        sc.render.filepath = png
        bpy.ops.render.render(write_still=True)
        subprocess.run([MAGICK, png, "-resize", "240x240", png], check=True)
        _frames(png, os.path.join(ICONS, "ek2lc_%s.dds" % key))
        log.write("icon %s (%s)\n" % (key, eng))
    sc.camera = old_cam
    for x in [cam] + lights:
        bpy.data.objects.remove(x, do_unlink=True)
    for n, h in keep.items():
        if n in sc.objects:
            sc.objects[n].hide_render = h


def start_icons():
    def run():
        with open(os.path.join(MOD, "source/build_logs/icons.log"), "w", buffering=1) as log:
            try:
                render_icons(log)
                log.write("ICONS OK\n")
            except Exception:
                import traceback
                log.write(traceback.format_exc() + "\nICONS FAILED\n")
        return None
    bpy.app.timers.register(run, first_interval=0.2)
    return "icon render started"

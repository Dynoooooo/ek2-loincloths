"""Artifact inventory icons for the regalia (art_*) in the Maya GUI: port of
source/legacy_blender/tools/render_regalia_icons.py (2026-11-10).

    import icons; icons.render("art_champion")

The worn male piece alone, unposed, from the front and a little to its left, orthographic. The viewport can't
write alpha, so it is shot twice, on black and on white, and the alpha recovered from the difference. Vanilla's
artifact icons are 960x240 strips, one 240x240 frame per rarity (common, masterwork, famed, illustrious): the
render dulled, as is, brighter with a gold glow, brightest with a stronger glow. Uncompressed DDS, no mips.
"""
import os
import subprocess
import numpy as np
import maya.cmds as mc
import ck3scene as cs
import look

ICONS = cs.MOD + "/gfx/interface/icons/artifact"
SRC = cs.MOD + "/source/textures/icons"
MAGICK = look.MAGICK


def _frames(png, out_dds):
    t = png[:-4]
    glow = lambda col, sig, op: ["(", png, "-alpha", "extract", "-blur", "0x%d" % sig, "-level", "0,60%",
                                 "-background", col, "-alpha", "shape", "-channel", "A", "-evaluate", "multiply", op,
                                 "+channel", ")"]
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


def _read(path):
    w, h = map(int, subprocess.run([MAGICK, "identify", "-format", "%w %h", path], capture_output=True, check=True,
                                   text=True).stdout.split())
    raw = subprocess.run([MAGICK, path, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32) / 255.0


def render(key, size=720, tex_key=None):
    import sheet
    os.makedirs(SRC, exist_ok=True)
    cs.new_scene()
    p = cs.load_piece("ek2lc_m_%s_01" % key)
    sheet._tex(p, tex_key or key)
    look.setup_view()
    bb = mc.exactWorldBoundingBox(p)
    c = np.array([(bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2])
    ext = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
    d = np.array([-0.45, 0.3, 1.0])  # front (+Z), a little to the piece's right as we look, from slightly above
    d /= np.linalg.norm(d)
    cam = mc.camera(orthographic=True, orthographicWidth=ext * 1.12, nearClipPlane=1, farClipPlane=2000)[0]
    mc.xform(cam, ws=True, t=[float(x) for x in c + d * 300])
    loc = mc.spaceLocator()[0]
    mc.xform(loc, ws=True, t=[float(x) for x in c])
    mc.delete(mc.aimConstraint(loc, cam, aimVector=(0, 0, -1), upVector=(0, 1, 0), worldUpType="vector",
                               worldUpVector=(0, 1, 0)))
    mc.delete(loc)
    panel = look._panel()
    old = mc.modelPanel(panel, query=True, camera=True)
    mc.modelPanel(panel, edit=True, camera=cam)
    mc.modelEditor(panel, edit=True, displayTextures=True, displayLights="default", grid=False, headsUpDisplay=False)
    shots = []
    old_bg = mc.displayRGBColor("background", query=True)
    try:
        for col in ((0, 0, 0), (1, 1, 1)):
            mc.displayRGBColor("background", *col)
            mc.displayPref(displayGradient=False)
            f = "%s/_icon_%s_%d.png" % (SRC, key, col[0])
            mc.setFocus(panel)
            mc.playblast(frame=[1], format="image", compression="png", completeFilename=f, viewer=False,
                         showOrnaments=False, widthHeight=(size, size), percent=100, forceOverwrite=True, offScreen=True)
            shots.append(f)
    finally:
        mc.displayRGBColor("background", *old_bg)
        mc.modelPanel(panel, edit=True, camera=old)
    A, B = _read(shots[0]), _read(shots[1])
    alpha = np.clip(1.0 - (B - A).mean(-1), 0.0, 1.0)
    rgb = np.where(alpha[..., None] > 1e-3, A / np.maximum(alpha[..., None], 1e-3), 0.0)
    rgba = np.dstack([np.clip(rgb, 0, 1), alpha])
    png = "%s/ek2lc_%s.png" % (SRC, key)
    data = np.round(rgba * 255).astype(np.uint8).tobytes()
    subprocess.run([MAGICK, "-size", "%dx%d" % (size, size), "-depth", "8", "rgba:-", "-trim", "+repage", "-gravity",
                    "center", "-background", "none", "-resize", "228x228", "-extent", "240x240", png], input=data, check=True)
    for f in shots:
        os.remove(f)
    _frames(png, "%s/ek2lc_%s.dds" % (ICONS, key))
    return png

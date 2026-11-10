"""Contact sheets from the Maya viewport: each piece on the body from several sides, one row per piece.

    import look; look.sheet(["ek2lc_m_art_feather_01", ...], views=("front", "left", "back"), out="/tmp/x.jpg")

Pieces must be loaded (ck3scene.load_piece + texture_piece); all others are hidden while one is shot.
Needs ImageMagick (`magick`) for the montage.
"""
import os
import subprocess
import tempfile
import maya.cmds as mc
import ck3scene as cs

MAGICK = "/opt/homebrew/bin/magick" if os.path.exists("/opt/homebrew/bin/magick") else "magick"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"  # ImageMagick here has no default font for -annotate


def _panel():
    for p in mc.getPanel(type="modelPanel"):
        if mc.modelPanel(p, query=True, camera=True) in ("persp", "|persp"):
            return p
    return mc.getPanel(type="modelPanel")[0]


def setup_view():
    for p in mc.getPanel(type="modelPanel"):
        mc.modelEditor(p, edit=True, displayTextures=True, displayAppearance="smoothShaded", grid=False,
                       joints=False, headsUpDisplay=False, locators=False)
    mc.setAttr("perspShape.focalLength", 50)


def shot(path, w=360, h=420):
    mc.setFocus(_panel())
    f = mc.currentTime(query=True)
    mc.playblast(frame=[f], format="image", compression="jpg", completeFilename=path, viewer=False,
                 showOrnaments=False, widthHeight=(w, h), percent=100, forceOverwrite=True, offScreen=True, quality=85)
    return path


def sheet(pieces, views=("front", "left", "back"), out=None, dist=95, label=True, body=True, w=300, h=360):
    setup_view()
    scene = [t for t in mc.ls("ek2lc_*", type="transform") if mc.listRelatives(t, shapes=True, type="mesh")]
    shown = {p: mc.getAttr(p + ".visibility") for p in scene}
    for q in scene:
        mc.setAttr(q + ".visibility", False)
    allp = [p for p in pieces if mc.objExists(p)]
    tmp = tempfile.mkdtemp(prefix="ek2lc_look_")
    rows = []
    try:
        for p in allp:
            for q in allp:
                mc.setAttr(q + ".visibility", q == p)
            files = []
            for v in views:
                cs.frame_view([p], v, dist=dist)
                files.append(shot("%s/%s_%s.jpg" % (tmp, p, v), w, h))
            row = "%s/row_%s.jpg" % (tmp, p)
            cmd = [MAGICK] + files + ["+append"]
            if label:
                cmd += ["-font", FONT, "-gravity", "NorthWest", "-fill", "white", "-pointsize", "16", "-annotate", "+6+4",
                        p.replace("ek2lc_", "")]
            subprocess.run(cmd + [row], check=True)
            rows.append(row)
        out = out or "%s/sheet.jpg" % tmp
        subprocess.run([MAGICK] + rows + ["-append", "-quality", "82", out], check=True)
    finally:
        for p, s in shown.items():
            mc.setAttr(p + ".visibility", s)
    return out

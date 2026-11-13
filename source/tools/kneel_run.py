"""Run source/maya/kneel.py in mayapy (no GUI needed: numpy on the pose dump, .mesh files through pdx_data).

    mayapy source/tools/kneel_run.py                      every piece, both kneels, plain then heavy body
    mayapy source/tools/kneel_run.py --dry NAME [NAME..]  measure only, write nothing
"""
import os
import sys
import time

HOME = os.path.expanduser("~")
for p in (HOME + "/Library/Preferences/Autodesk/maya/2027/scripts/site-packages",
          HOME + "/Library/Preferences/Autodesk/maya/scripts",
          os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "maya")):
    sys.path.insert(0, p)
# io_pdx_mesh's __init__ opens its tool window (needs the Maya GUI): load only its file reader/writer
import types
pkg = types.ModuleType("io_pdx_mesh")
pkg.__path__ = [HOME + "/Library/Preferences/Autodesk/maya/scripts/io_pdx_mesh"]
sys.modules["io_pdx_mesh"] = pkg
import kneel

args = sys.argv[1:]
dry = "--dry" in args
names = [a for a in args if not a.startswith("--")]
t0 = time.time()


def log(s):
    print("%6.0fs %s" % (time.time() - t0, s), flush=True)


if dry:
    for n in names:
        for variant in ("base", "fat"):
            for key in ("kneel1", "kneel2"):
                kneel.make(n, "female" if n.startswith("ek2lc_f_") else "male", key, variant, log=log, write=False)
else:
    kneel.run_all(names or None, log=log)

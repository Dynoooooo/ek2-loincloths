"""Build the pieces inside the live Blender app (the user's rule: the app, not headless), through MCP for Blender:

    exec(open("<mod>/source/tools/build_in_app.py").read()); start("male")      # or start("male", "female")

The build runs from a Blender timer, so the MCP call returns at once (a build takes ~2 minutes; an MCP call
times out after 180 s). Blender is busy until it finishes. Each body writes source/build_logs/build_<sex>.log
as the headless build did; its last line is "BUILD OK (<sex>)" or "BUILD FAILED (<sex>)" after the traceback.
When it's done the finished pieces are in the scene to look at.
"""
import bpy
import os
import runpy
import sys
import traceback

MOD = os.path.expanduser("~/Documents/Paradox Interactive/Crusader Kings III/mod/ek2_loincloths")
GAME = os.path.expanduser("~/Library/Application Support/Steam/steamapps/common/Crusader Kings III/game")


def _run(sexes):
    for sex in sexes:
        log = os.path.join(MOD, "source/build_logs/build_%s.log" % sex)
        for m in ("cultures", "colour", "undead", "weight_solver"):  # the build's own modules: re-read them every run
            sys.modules.pop(m, None)
        saved = sys.stdout, sys.stderr, sys.argv
        ok = True
        with open(log, "w", buffering=1) as f:
            sys.stdout = sys.stderr = f
            sys.argv = ["blender", "--", GAME, MOD, sex]
            try:  # the build's globals are kept for looking into afterwards (bpy.app.driver_namespace)
                bpy.app.driver_namespace["ek2lc_build_" + sex] = runpy.run_path(
                    os.path.join(MOD, "source/build_reach_hide.py"), run_name="__main__")
            except BaseException:
                traceback.print_exc()
                ok = False
            finally:
                sys.stdout, sys.stderr, sys.argv = saved
            f.write("\nBUILD %s (%s)\n" % ("OK" if ok else "FAILED", sex))
        if not ok:
            break
    return None  # run once


def start(*sexes):
    bpy.app.timers.register(lambda: _run(sexes or ("male", "female")), first_interval=0.2)
    return "build of %s started" % ", ".join(sexes or ("male", "female"))

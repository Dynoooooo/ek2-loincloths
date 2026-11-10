"""Install the generated 2D art (source/textures/art/*.png, made with GPT Image 2.6 via OpenRouter) into the mod:
event backgrounds (1592x848 DXT1) registered in common/event_backgrounds/ek2lc_event_backgrounds.txt and set on
each event with override_background; decision pictures (1100x440 DXT1) set on each decision.

    python3 source/tools/install_art.py

Idempotent: it rewrites the backgrounds file and replaces existing override_background / picture lines.
"""
import os
import re
import subprocess

MOD = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ART = os.path.join(MOD, "source/textures/art")
MAGICK = "/opt/homebrew/bin/magick"
BOM = "﻿"

# background key -> events using it
BACKGROUNDS = {
    "ek2lc_weavers_hall": ["ek2lc_regalia.%04d" % i for i in (1, 2, 3, 10, 11, 12, 13, 20, 30, 60)],
    "ek2lc_feast_hall": ["ek2lc_regalia.0050", "ek2lc_life.0020", "ek2lc_life.0030", "ek2lc_life.0040"],
    "ek2lc_going_native": ["ek2lc_life.0100", "ek2lc_regalia.0040"],
    "ek2lc_rite_lodge": ["ek2lc_life.0001", "ek2lc_life.0002"],
    "ek2lc_war_camp": ["ek2lc_life.0010"],
    "ek2lc_hist_grove": ["ek2lc_life.0050"],
    "ek2lc_moonlit_forest": ["ek2lc_life.0070"],
    "ek2lc_winter_hall": ["ek2lc_life.0080"],
    "ek2lc_standing_stones": ["ek2lc_giant.0001", "ek2lc_giant.0002"],
    "ek2lc_mammoth_spring": ["ek2lc_giant.0003"],
    "ek2lc_bloodroot_valley": ["ek2lc_keptu.0001", "ek2lc_keptu.0003", "ek2lc_keptu.0004"],
    "ek2lc_star_hill": ["ek2lc_nede.0001", "ek2lc_nede.0002", "ek2lc_nede.0003"],
    "ek2lc_sun_temple": ["ek2lc_yokudan.0001", "ek2lc_yokudan.0002", "ek2lc_yokudan.0003", "ek2lc_yokudan.0004"],
}
# decision -> picture key (gfx/interface/illustrations/decisions/<key>.dds)
DECISIONS = {
    "ek2lc_loincloth_festival_decision": "ek2lc_festival",
    "ek2lc_go_native_decision": "ek2lc_go_native",
    "ek2lc_end_native_decision": "ek2lc_end_native",
    "ek2lc_giant_gathering_decision": "ek2lc_giant_gathering",
    "ek2lc_keptu_hunt_decision": "ek2lc_keptu_hunt",
    "ek2lc_nede_watch_decision": "ek2lc_nede_watch",
    "ek2lc_yokudan_sun_decision": "ek2lc_yokudan_sun",
}
EVENT_FILES = ["events/ek2lc_regalia_events.txt", "events/ek2lc_life_events.txt", "events/ek2lc_peoples_events.txt"]


def dds(src, dst, w, h):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run([MAGICK, src, "-resize", "%dx%d^" % (w, h), "-gravity", "center", "-extent", "%dx%d" % (w, h),
                    "-define", "dds:compression=dxt1", "-define", "dds:mipmaps=0", dst], check=True)


def main():
    have_bg, have_dec = [], []
    for key in BACKGROUNDS:
        src = os.path.join(ART, "event_%s.png" % key[6:]) if key != "ek2lc_going_native" else \
            os.path.join(MOD, "source/textures/icons/event_going_native_src.png")
        if os.path.exists(src):
            dds(src, os.path.join(MOD, "gfx/interface/illustrations/event_scenes/%s.dds" % key), 1592, 848)
            have_bg.append(key)
    for dec, key in DECISIONS.items():
        src = os.path.join(ART, "decision_%s.png" % key[6:])
        if os.path.exists(src):
            dds(src, os.path.join(MOD, "gfx/interface/illustrations/decisions/%s.dds" % key), 1100, 440)
            have_dec.append(dec)
    out = [BOM + "# EK2 Loincloths: event backgrounds. Art made by the user's image generator (GPT Image 2.6); written by "
           "source/tools/install_art.py."]
    for key in have_bg:
        out.append("%s = {\n\tbackground = {\n\t\treference = \"gfx/interface/illustrations/event_scenes/%s.dds\"\n"
                   "\t\tenvironment = \"environment_frontend_west_main\"\n\t\tambience = \"event:/SFX/Events/Backgrounds/throneroom_western\"\n"
                   "\t}\n}" % (key, key))
    open(os.path.join(MOD, "common/event_backgrounds/ek2lc_event_backgrounds.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    bg_of = {ev: key for key in have_bg for ev in BACKGROUNDS[key]}
    for rel in EVENT_FILES:
        p = os.path.join(MOD, rel)
        t = open(p, encoding="utf-8-sig").read()
        t = re.sub(r"\n\toverride_background = \{ reference = \w+ \}", "", t)
        def put(m):
            ev = m.group(1)
            return m.group(0) + ("\n\toverride_background = { reference = %s }" % bg_of[ev] if ev in bg_of else "")
        t = re.sub(r"^(ek2lc_\w+\.\d{4}) = \{\n\ttype = character_event\n\ttitle = [^\n]+\n\tdesc = [^\n]+\n\ttheme = \w+", put, t, flags=re.M)
        open(p, "w", encoding="utf-8").write(BOM + t)
    p = os.path.join(MOD, "common/decisions/ek2lc_decisions.txt")
    t = open(p, encoding="utf-8-sig").read()
    for dec in have_dec:
        key = DECISIONS[dec]
        t = re.sub(r"(%s = \{\n\tpicture = \{\n\t\treference = \")[^\"]+(\")" % dec,
                   r"\g<1>gfx/interface/illustrations/decisions/%s.dds\g<2>" % key, t)
    open(p, "w", encoding="utf-8").write(BOM + t)
    print("backgrounds:", len(have_bg), "decisions:", len(have_dec))


if __name__ == "__main__":
    main()

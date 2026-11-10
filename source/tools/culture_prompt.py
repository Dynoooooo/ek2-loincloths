"""Print the Meshy concept prompt for culture colourway pieces (source/meshy/culture_prompts.json).
    python3 source/tools/culture_prompt.py argonian_hide fur_robe ...   (or 'batch1')"""
import json
import os
import re
import sys

D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "meshy", "culture_prompts.json")))


def split(key):
    if key == "fur_robe":
        return "reach", "fur_robe"
    for c in sorted(D["cultures"], key=len, reverse=True):
        if key.startswith(c + "_"):
            return c, key[len(c) + 1:]
    raise KeyError(key)


def prompt(key):
    c, k = split(key)
    t = D["kinds"][k].format(**D["cultures"][c]) + D["suffix"][D["fit"][k]]
    return re.sub(r"^A (?=[AEIOU])", "An ", t)


TEX = {"hide": "{plain}, {cord}, {plain_trim}", "band": "{plain_soft}, {plain_trim}",
       "fine": "{fine}, {fine_trim}, {fine_belt}", "band_fine": "{fine}, {fine_trim}, {fine_clasp}",
       "royal": "{royal}, {motif}, {royal_trim}, {royal_belt}", "band_royal": "{royal}, {motif}, {royal_clasp}, {royal_trim}",
       "war": "{war_belt}, {trophy}, {war_extra}", "fur_robe": "{cape}, {cape_collar}, {cape_clasp}"}


def texture(key):
    c, k = split(key)
    t = TEX[k].format(**D["cultures"][c])
    return (t[0].upper() + t[1:] + ". Flat even colours as in the image, no baked shadows or highlights.")[:800]


if __name__ == "__main__":
    if sys.argv[1] == "--texture":
        for k in sys.argv[2:]:
            print("%s\t%s" % (k, texture(k)))
        sys.exit()
    keys = D["batch1"] if sys.argv[1:] == ["batch1"] else sys.argv[1:]
    for k in keys:
        print("%s\t%s" % (k, prompt(k)))

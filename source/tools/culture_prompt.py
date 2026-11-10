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


if __name__ == "__main__":
    keys = D["batch1"] if sys.argv[1:] == ["batch1"] else sys.argv[1:]
    for k in keys:
        print("%s\t%s" % (k, prompt(k)))

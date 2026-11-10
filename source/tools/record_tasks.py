"""Record Meshy task ids in source/meshy/tasks.json:  python3 source/tools/record_tasks.py concept|model key=id ..."""
import json
import os
import sys

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "meshy", "tasks.json")
d = json.load(open(p))
kind = sys.argv[1]
for kv in sys.argv[2:]:
    k, v = kv.split("=")
    d.setdefault(k, {})[kind] = v
json.dump(d, open(p, "w"), indent=1)
print(len(sys.argv) - 2, "recorded")

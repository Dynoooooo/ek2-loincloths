#!/bin/bash
# Build every piece for both bodies (the build runs make_colour.py at the end).
# Blender exits 0 even when the script fails, so this checks the log for Python errors.
# Usage: bash source/tools/build.sh [male|female]   (both when omitted)
MOD="$(cd "$(dirname "$0")/../.." && pwd)"
GAME="$HOME/Library/Application Support/Steam/steamapps/common/Crusader Kings III/game"
mkdir -p "$MOD/source/build_logs"
for s in ${1:-male female}; do
    log="$MOD/source/build_logs/build_$s.log"
    /Applications/Blender.app/Contents/MacOS/Blender --background --python "$MOD/source/build_reach_hide.py" -- "$GAME" "$MOD" "$s" > "$log" 2>&1
    if grep -q Traceback "$log"; then
        echo "BUILD FAILED ($s), log: $log"
        grep -A12 Traceback "$log" | tail -6
        exit 1
    fi
    echo "BUILD OK ($s), log: $log"
done

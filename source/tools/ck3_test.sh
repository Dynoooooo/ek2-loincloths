#!/bin/bash
# Test launches for EK2 Loincloths. Backs up the user's CK3 settings and saves first,
# runs CK3 in a window, and puts everything back afterwards.
#   ck3_test.sh start [mod ...]   back up, switch to windowed 2560x1600, load only EK2 + this mod (+ the named mods
#                       after it, e.g. ugc_2220326926 = Better Barbershop), start as Aldrydd of Druadach
#                       (OPEN=1 to launch through LaunchServices; PLAY=<title> to start as someone else, e.g. PLAY=k_falkreath for Yashnag; NOMOD=1 for EK2 alone)
#   ck3_test.sh wait    wait until the map is running (up to 5 minutes)
#   ck3_test.sh stop    quit CK3 and restore the backups
set -e
CK="${CK3_USER_DIR:-$HOME/Documents/Paradox Interactive/Crusader Kings III}"
BIN="${CK3_GAME:-$HOME/Library/Application Support/Steam/steamapps/common/Crusader Kings III/game}/../binaries"
B="$CK/ek2lc_backup"   # outside the mod; removed after a successful restore

case "$1" in
start)
  [ -e "$B" ] && { echo "A backup already exists at $B. Run 'stop' first."; exit 1; }
  pgrep -x ck3 >/dev/null && { echo "CK3 is already running."; exit 1; }
  mkdir -p "$B/player/game_rules"
  cp -p "$CK/pdx_settings.txt" "$CK/dlc_load.json" "$B/"
  [ -f "$CK/player/game_rules/presets.txt" ] && cp -p "$CK/player/game_rules/presets.txt" "$B/player/game_rules/"
  rsync -a "$CK/save games/" "$B/save games/"
  python3 -I - "$CK/pdx_settings.txt" <<'PY'
import re, sys
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
t = re.sub(r'("display_mode"=\{\s*version=\d+\s*value=)"[^"]*"', r'\1"windowed"', t)
t = re.sub(r'("windowed_resolution"=\{\s*version=\d+\s*value=)"[^"]*"', r'\1"2560x1600"', t)
open(p, "w", encoding="utf-8").write(t)
PY
  # test with exactly EK2 and this mod (Steam rewrites the list from its Workshop subscriptions)
  shift
  python3 -I - "$CK/dlc_load.json" "$@" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
import os
d["enabled_mods"] = ["mod/ugc_2887120253.mod"] + ([] if os.environ.get("NOMOD") else ["mod/ek2_loincloths.mod"]) + \
    ["mod/%s.mod" % m for m in sys.argv[2:]]
json.dump(d, open(p, "w"), indent=2)
PY
  date +%s > "$B/launched_at"
  cd "$BIN"
  ARGS="-gdpr-compliant -debug_mode -skip -bookmark=bm_interregnum -play=${PLAY:-d_druadach}"
  if [ -n "$OPEN" ]; then  # through LaunchServices: a registered app, so Computer Use can type into it (2026-11-10)
    open ${BG:+-g} -a "$BIN/ck3.app" --args $ARGS   # BG=1: launch behind the user's windows
    sleep 3; echo "launched, pid $(pgrep -x ck3)"
  else
    nohup ./ck3.app/Contents/MacOS/ck3 $ARGS >/dev/null 2>&1 &
    echo "launched, pid $!"
  fi
  ;;
wait)
  t0=$(cat "$B/launched_at")
  L="$CK/logs/debug.log"
  for i in $(seq 1 100); do
    if [ -f "$L" ] && [ "$(stat -f %m "$L")" -gt "$t0" ] && grep -q "rivers_ambience_node" "$L"; then
      echo "map running after $(( $(date +%s) - t0 ))s"; exit 0
    fi
    pgrep -x ck3 >/dev/null || { echo "CK3 exited"; exit 1; }
    sleep 3
  done
  echo "timed out"; exit 1
  ;;
stop)
  for pid in $(pgrep -x ck3); do kill "$pid" 2>/dev/null || true; done
  for i in $(seq 1 15); do pgrep -x ck3 >/dev/null || break; sleep 1; done
  for pid in $(pgrep -x ck3); do kill -9 "$pid" 2>/dev/null || true; done   # dialogs can hang shutdown
  for i in $(seq 1 10); do pgrep -x ck3 >/dev/null || break; sleep 1; done
  pgrep -x ck3 >/dev/null && { echo "CK3 won't quit. Backup kept at $B"; exit 1; }
  [ -e "$B" ] || { echo "No backup to restore."; exit 0; }
  cp -p "$B/pdx_settings.txt" "$B/dlc_load.json" "$CK/"
  [ -f "$B/player/game_rules/presets.txt" ] && cp -p "$B/player/game_rules/presets.txt" "$CK/player/game_rules/"
  rsync -a --delete "$B/save games/" "$CK/save games/"
  rm -rf "$B"
  echo "restored"
  ;;
*)
  echo "usage: $0 start [mod ...]|wait|stop"; exit 2
  ;;
esac

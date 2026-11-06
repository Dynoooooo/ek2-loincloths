#!/bin/bash
# Test launches for EK2 Loincloths. Backs up the user's CK3 settings and saves first,
# runs CK3 in a window, and puts everything back afterwards.
#   ck3_test.sh start   back up, switch to windowed 2560x1600, load only EK2 + this mod, start as Aldrydd of Druadach
#   ck3_test.sh wait    wait until the map is running (up to 5 minutes)
#   ck3_test.sh stop    quit CK3 and restore the backups
set -e
CK="$HOME/Documents/Paradox Interactive/Crusader Kings III"
BIN="$HOME/Library/Application Support/Steam/steamapps/common/Crusader Kings III/binaries"
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
  python3 -I - "$CK/dlc_load.json" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["enabled_mods"] = ["mod/ugc_2887120253.mod", "mod/ek2_loincloths.mod"]
json.dump(d, open(p, "w"), indent=2)
PY
  date +%s > "$B/launched_at"
  cd "$BIN"
  nohup ./ck3.app/Contents/MacOS/ck3 -gdpr-compliant -debug_mode -skip -bookmark=bm_interregnum -play=d_druadach >/dev/null 2>&1 &
  echo "launched, pid $!"
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
  pkill -x ck3 || true
  for i in $(seq 1 15); do pgrep -x ck3 >/dev/null || break; sleep 1; done
  pkill -9 -x ck3 2>/dev/null || true   # it can hang on dialogs; it must be gone before restoring
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
  echo "usage: $0 start|wait|stop"; exit 2
  ;;
esac

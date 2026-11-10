#!/bin/bash
# solve_bg.sh <sex> <ref> <iters> <inits> <name>...: run wsolve.py on each dumped piece in parallel (background)
SEX=$1; REF=$2; IT=$3; INI=$4; shift 4
cd "$(dirname "$0")/../.."
PY=/Applications/Autodesk/maya2027/Maya.app/Contents/bin/mayapy
for n in "$@"; do
  WS_ITERS=$IT WS_INITS=$INI WS_REF=$REF nohup $PY -I source/maya/wsolve.py "$SEX" "$n" > "source/build_logs/solve/log_${n}.txt" 2>&1 &
done

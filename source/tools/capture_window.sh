#!/bin/bash
# capture_window.sh <window id> <out dir> <seconds>: about 30 captures a second of one window (three parallel loops of
# screencapture -l, which captures the window even behind others). Window id: ~/.copilot/bin/ck3ctl winid $(pgrep -x ck3)
W=$1; OUTD=$2; SECS=$3
cap() { local k=0; local end=$(( $(date +%s) + SECS )); while [ $(date +%s) -lt $end ]; do k=$((k+1)); screencapture -x -o -l$W -t jpg $OUTD/c$1_$(printf %04d $k).jpg 2>/dev/null; done; }
cap 1 & cap 2 & sleep 0.03; cap 3 & wait

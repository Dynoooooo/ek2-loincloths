#!/bin/bash
# Run ck3-tiger on EK2 Loincloths with EK2 loaded first, so its triggers and cultures resolve.
#   source/tools/tiger.sh [ck3-tiger options]
# Override the defaults with EK2_DIR (EK2's workshop folder) and CK3_TIGER (the ck3-tiger binary).
# The config and a minimal EK2 descriptor are written to a temp folder: tiger wants absolute paths, and
# EK2's own ugc_2887120253.mod makes tiger 1.19 stop with "Invalid config".
# Remaining reports in EK2/vanilla files (camp_purpose_* laws, change_spiritual_fulfillment, ...) are tiger 1.19 not
# knowing CK3 1.20; read only the [MOD] lines that point at our own files.
set -e
MOD="$(cd "$(dirname "$0")/../.." && pwd)"
EK2="${EK2_DIR:-$HOME/Library/Application Support/Steam/steamapps/workshop/content/1158310/2887120253}"
TIGER="${CK3_TIGER:-$(command -v ck3-tiger || echo "$HOME/.cargo/bin/ck3-tiger")}"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
cat > "$T/ek2_for_tiger.mod" <<MODFILE
name="Elder Kings 2"
path="$EK2"
supported_version="1.20.1.2"
MODFILE
cat > "$T/ck3-tiger.conf" <<CONF
languages = { check = "english" }
load_mod = {
	label = "EK2"
	modfile = "$T/ek2_for_tiger.mod"
}
CONF
"$TIGER" --config "$T/ck3-tiger.conf" "$@" "$MOD/../ek2_loincloths.mod"

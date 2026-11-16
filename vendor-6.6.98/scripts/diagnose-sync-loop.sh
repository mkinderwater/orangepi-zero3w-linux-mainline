#!/usr/bin/env bash
# Capture GNU Make's exact regeneration reason. Never wipe or edit the source.
# A bounded make process may regenerate generated files in the object directory.
set -euo pipefail
WORK_ROOT="${WORK_ROOT:-/root/opi3w-vendor-6698-work}"
RESULTS_DIR="${RESULTS_DIR:-/mnt/c/Users/mkinderwater/Downloads/opi3w-vendor-6698-results}"
TREE="$WORK_ROOT/tree-control"
OBJ="$WORK_ROOT/obj-control"
[[ -f "$TREE/Makefile" && -f "$OBJ/.config" ]] || { echo 'STOP: control tree/object config missing' >&2; exit 2; }
for cmd in make timeout git stat; do command -v "$cmd" >/dev/null || { echo "STOP: $cmd not found" >&2; exit 2; }; done
mkdir -p "$RESULTS_DIR"
LOG="$RESULTS_DIR/sync-loop-make-debug.txt"
SUMMARY="$RESULTS_DIR/sync-loop-summary.txt"
inspect() {
  for p in .config Makefile include/config/auto.conf include/config/auto.conf.cmd include/generated/autoconf.h include/generated/rustc_cfg; do
    if [[ -e "$OBJ/$p" ]]; then stat -c '%y %s %n' "$OBJ/$p"; else echo "MISSING $OBJ/$p"; fi
  done
}
{
  echo "SOURCE_COMMIT=$(git -C "$TREE" rev-parse HEAD)"
  echo "MAKE_VERSION=$(make --version | head -1)"
  echo '=== BEFORE ==='
  inspect
  echo '=== KCONFIG DEPENDENCY LINES ==='
  grep -nE '^deps_config|^include/config/auto.conf:|^include/config/auto.conf.cmd:' "$OBJ/include/config/auto.conf.cmd" | head -15 || true
  echo '=== KBUILD MAKEFILE RULE ==='
  grep -nF '%/config/auto.conf %/config/auto.conf.cmd %/generated/autoconf.h %/generated/rustc_cfg' "$TREE/Makefile" || true
} > "$SUMMARY"
set +e
timeout -s TERM -k 2s 8s make --debug=m --no-print-directory -j1 -C "$TREE" O="$OBJ" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- Image > "$LOG" 2>&1
rc=$?
set -e
{
  echo "MAKE_EXIT=$rc (124 means time limit)"
  echo '=== AFTER ==='
  inspect
  echo '=== DEBUG EVENTS (first 100) ==='
  grep -E 'Re-executing|Reading makefiles|Updating makefiles|Must remake target|Successfully remade target|Considering target file|does not exist|Prerequisite' "$LOG" | head -100 || true
  echo '=== SYNC COUNT ==='
  grep -c 'SYNC    include/config/auto.conf' "$LOG" || true
  echo "FULL_DEBUG=$LOG"
} >> "$SUMMARY"
cat "$SUMMARY"
echo 'KBUILD_RESTART_DIAGNOSTIC_CAPTURED_NOT_FIXED'

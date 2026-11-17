#!/usr/bin/env bash
# Acquire upstream AXP318W MFD/regulator v8 series, not vendor BSP code.
set -euo pipefail
OUT="${1:-/root/opi3w-m2-work/axp318w-upstream-v8}"
[[ "$OUT" == /* && "$OUT" != "/" && ! -e "$OUT" ]] || {
  echo "Refusing non-absolute or existing output: $OUT" >&2; exit 2
}
command -v b4 >/dev/null || { echo "MISSING: b4" >&2; exit 2; }
mkdir -p "$OUT"
MID='20260910-axp318-regulator-v8-0-e906a61a7f3d@baylibre.com'
if ! b4 am --no-parent -o "$OUT" "$MID" >"$OUT/fetch.stdout" 2>"$OUT/fetch.stderr"; then
  cat "$OUT/fetch.stderr" >&2
  echo 'Source fetch failed. No kernel changes performed.' >&2
  exit 3
fi
{
  echo "Message-ID: $MID"
  echo "Source: https://lists.openwall.net/linux-kernel/2026/09/10/1334"
  echo 'Expected: 5 patches, MFD/regulator AXP318W'
  echo 'AXP8191 vs AXP318W equivalence NOT yet established'
  echo 'Files:'
  find "$OUT" -type f -printf '%P %s bytes\n' | sort
  echo 'Checksums:'
  find "$OUT" -type f -name '*.mbx' -print0 | sort -z | xargs -0 -r sha256sum
  echo 'Read-only acquisition. No voltage changes or kernel patch application.'
} > "$OUT/INVENTORY.txt"
cat "$OUT/INVENTORY.txt"

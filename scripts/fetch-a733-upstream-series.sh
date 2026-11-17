#!/usr/bin/env bash
# Acquire *upstream* A733 CCU and pinctrl patch sources into a new, isolated folder.
# No old BSP imports; never applies patches to the kernel or builds a boot image.
set -euo pipefail
OUT="${1:-/root/opi3w-m2-work/a733-upstream-patches-v1}"
if [[ "$OUT" != /* || "$OUT" == "/" || -e "$OUT" ]]; then
  echo "Provide a fresh absolute destination, refusing overwrite: $OUT" >&2
  exit 2
fi
for app in b4 sha256sum git; do
  if ! command -v "$app" >/dev/null 2>&1; then
    echo "MISSING: $app (install independently; kernel untouched)" >&2
    exit 2
  fi
done
mkdir -p "$OUT"/{ccu-v7,pinctrl-voltage-v3,pinctrl-pf6,log}
# Exact public Message-IDs; this also prevents accidentally following newer revisions.
declare -A SERIES=(
  [ccu-v7]='20261112-a733-clk-v7-0-db7c5451ffa2@pigmoral.tech'
  [pinctrl-voltage-v3]='20261109-a733-pinctrl-v3@gmail.com'
)
for name in ccu-v7 pinctrl-voltage-v3; do
  mid="${SERIES[$name]}"
  printf 'Fetching %s: %s\n' "$name" "$mid"
  b4 am --no-parent -o "$OUT/$name" "$mid" >"$OUT/log/$name.stdout" 2>"$OUT/log/$name.stderr" || {
    cat "$OUT/log/$name.stderr" >&2
    echo "FAILED: $name; folder retained for audit" >&2
    exit 3
  }
done
# PF6 correction is a separate follow-up with its own Message-ID.
# Do not combine it with pinctrl voltage fixes until base A733 pinctrl is present.
b4 am --no-parent -o "$OUT/pinctrl-pf6" \
  '20261110-a733-pinctrl-irq-mux@gmail.com' \
  >"$OUT/log/pinctrl-pf6.stdout" 2>"$OUT/log/pinctrl-pf6.stderr" || {
  echo "PF6 candidate Message-ID is unverified; see log. This is nonfatal." >&2
}
{
  echo '=== PINNED UPSTREAM SERIES ==='
  printf '%s\n' 'CCU v7: 20261112-a733-clk-v7-0-db7c5451ffa2@pigmoral.tech' \
    'A733 pinctrl voltage v3: 20261109-a733-pinctrl-v3@gmail.com'
  echo 'PF6 message ID requires independent confirmation; do not trust an unmatched download.'
  echo '=== ACQUIRED FILES ==='
  find "$OUT" -type f -printf '%P\t%s bytes\n' | sort
  echo '=== SHA256 ==='
  find "$OUT" -type f \( -iname '*.mbx' -o -iname '*.patch' -o -iname '*.mbox' \) -print0 |
    sort -z | xargs -0 -r sha256sum
  echo '=== GATES ==='
  echo 'Acquisition only. No applicability, build, DTB, voltage or hardware test.'
  echo 'Pinctrl voltage fix requires the earlier A733 pinctrl base series.'
  echo 'CCU v7 is based on v7.4-rc1 and requires prerequisite review for 6.18.19.'
} > "$OUT/INVENTORY.txt"
cat "$OUT/INVENTORY.txt"

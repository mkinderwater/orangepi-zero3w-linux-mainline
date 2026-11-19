#!/usr/bin/env bash
# Audit earlier AXP8191 experiments against the actual full Linux 6.18 source.
# Read-only: does not apply patches or modify the kernel tree.
set -euo pipefail
SRC="${SRC:-/root/opi3w-m2-work/a733-try9-ramoops-v2/linux}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-full-integration/axp8191-reuse-audit}"
P1=/root/opi3w-m2r-618/patches/0001-axp8191-staged-mfd.patch
P2=/root/opi3w-m2r-618/patches/0002-axp8191-minimal-regulators.patch
P3=/root/opi3w-m2t-618/patches/0001-axp8191-skip-unverified-workmode.patch
for p in "$P1" "$P2" "$P3"; do
  [[ -r "$p" ]] || { echo "Required patch not found: $p" >&2; exit 1; }
done
[[ -f "$SRC/Makefile" ]] || { echo "Missing source tree: $SRC" >&2; exit 1; }
mkdir -p "$OUT"
{
  echo "Source tree: $SRC"
  git -C "$SRC" rev-parse HEAD || :
  git -C "$SRC" status --short || :
  echo "=== Previous AXP8191 patch checksums ==="
  sha256sum "$P1" "$P2" "$P3"
  echo "=== Patch summary ==="
  for p in "$P1" "$P2" "$P3"; do
    echo "PATCH: $p"
    grep -E '^(diff --git|@@|\+.*(AXP8191|axp8191|workmode|DCDC|CLDO|DC1SW))' "$p" | head -100 || :
  done
  echo "=== Candidate target source AXP8191 references ==="
  grep -RInE 'AXP8191|axp8191' "$SRC/drivers/mfd" "$SRC/drivers/regulator" "$SRC/include/linux/mfd" 2>/dev/null | head -80 || :
  echo "=== Existing patch dry-run (individually) ==="
  for p in "$P1" "$P2" "$P3"; do
    echo "PATCH: $p"
    if git -C "$SRC" apply --check "$p"; then
      echo "Can apply independently on this tree"
    else
      echo "Does not apply independently; may depend on earlier patches or a different base"
    fi
  done
} > "$OUT/summary.txt" 2>&1
cat "$OUT/summary.txt"
echo "READ-ONLY AUDIT COMPLETE: no patches applied"

#!/usr/bin/env bash
# Read-only preflight for isolated upstream A733 PCK600/PowerVR integration.
set -euo pipefail
K="${1:-/root/opi3w-hybrid-build-0.2.7}"
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
S="$K/linux"
for f in "$S/drivers/pmdomain/sunxi/sun55i-pck600.c" "$S/drivers/gpu/drm/imagination/pvr_drv.c" "$S/drivers/pmdomain/sunxi/Kconfig" "$K/board/sun60iw2p1.dtsi"; do
  if [[ ! -f "$f" ]]; then echo "MISSING: $f" >&2; exit 2; fi
done
echo "=== BASELINE PCK600 DRIVER ==="
sha256sum "$S/drivers/pmdomain/sunxi/sun55i-pck600.c"
echo "=== PATCH APPLICABILITY (NO CHANGES) ==="
for p in "$R/patches/linux-6.18/0002-pmdomain-sunxi-a733-upstream-pck600.patch" "$R/patches/linux-6.18/0003-dt-bindings-a733-pck600-ids.patch"; do
  echo "$p"
  if git -C "$S" apply --check "$p"; then echo "PASS"; else echo "FAIL: patch does not apply cleanly" >&2; exit 3; fi
done
echo "=== EXISTING A733 PROVIDER SOURCES ==="
grep -RnsE 'sun60i-a733-pck-600|sun60iw2-pck-600' "$S/drivers/pmdomain/sunxi" "$S/bsp/drivers/pm_domain" "$K/board/sun60iw2p1.dtsi" | head -40 || true
echo "=== CURRENT GPU CONFIG ==="
grep -E '^(# )?CONFIG_(DRM_POWERVR|SUN55I_PCK600|AW_PCK600_DOMAINS|AW_PM_DOMAINS|AW_GPU_PM_DOMAINS)' "$K/build/.config" || true
echo "=== GPU OPP RAW VALUES (READ ONLY) ==="
DTB="$K/stage/boot/sun60i-a733-orangepi-zero3w.dtb"
if [[ -f "$DTB" ]]; then
 for frequency in 400000000 600000000 800000000 1008000000; do
   printf "%s Hz: " "$frequency"
   fdtget -t x "$DTB" "/soc@3000000/gpu-opp-table/opp@$frequency" opp-microvolt 2>&1 || true
 done
else
 echo "MISSING: compiled DTB" >&2; exit 2
fi
echo "PREFLIGHT_COMPLETE: source and DTB untouched"

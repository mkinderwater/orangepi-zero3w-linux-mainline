#!/usr/bin/env bash
# Stage a separate, hash-checked 25 MHz MMC test DTB.
# Does not enable MMC0, change power rails, or modify the original DTB.
set -euo pipefail
SRC="${SRC:-/root/opi3w-m2-work/linux-618-full-integration/artifacts/sun60i-a733-orangepi-zero3w-26mhz.dtb}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-full-integration/artifacts/sun60i-a733-orangepi-zero3w-26mhz-mmc-25mhz.dtb}"
EXPECTED=1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d
[[ -f "$SRC" ]] || { echo "Missing input DTB" >&2; exit 1; }
[[ "$(sha256sum "$SRC" | cut -d' ' -f1)" == "$EXPECTED" ]] || { echo "Incorrect input DTB" >&2; exit 1; }
[[ "$(fdtget -t u "$SRC" /osc-clk clock-frequency)" == 26000000 ]] || exit 1
status="$(fdtget -t s "$SRC" /soc/mmc@4020000 status)"
[[ "$status" == disabled ]] || { echo "STOP: expected disabled MMC0; refusing to alter enabled node" >&2; exit 1; }
[[ "$OUT" != "$SRC" ]] || exit 1
cp "$SRC" "$OUT"
fdtput -t x "$OUT" /soc/mmc@4020000 max-frequency 0x017d7840
[[ "$(fdtget -t u "$OUT" /soc/mmc@4020000 max-frequency)" == 25000000 ]] || exit 1
[[ "$(fdtget -t u "$OUT" /osc-clk clock-frequency)" == 26000000 ]] || exit 1
[[ "$(fdtget -t s "$OUT" /soc/mmc@4020000 status)" == disabled ]] || exit 1
sha256sum "$SRC" "$OUT"
echo "MMC0 remains DISABLED. This sets a future cap, not a working SD bus."

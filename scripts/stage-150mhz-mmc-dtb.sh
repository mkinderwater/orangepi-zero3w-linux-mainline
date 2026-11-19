#!/usr/bin/env bash
# Stage board's 150 MHz MMC0 *maximum* from verified 26 MHz clock DTB.
# MMC0 remains disabled until pinctrl, PMIC/vmmc and OCR are validated.
set -euo pipefail
SRC="${SRC:-/root/opi3w-m2-work/linux-618-full-integration/artifacts/sun60i-a733-orangepi-zero3w-26mhz.dtb}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-full-integration/artifacts/sun60i-a733-orangepi-zero3w-26mhz-mmc-150mhz.dtb}"
EXPECTED=1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d
for command in sha256sum cut fdtget fdtput cp; do
  command -v "$command" >/dev/null || { echo "Missing $command" >&2; exit 1; }
done
[[ -f "$SRC" ]] || { echo "Missing input DTB" >&2; exit 1; }
[[ "$(sha256sum "$SRC" | cut -d' ' -f1)" == "$EXPECTED" ]] || { echo "Incorrect input DTB" >&2; exit 1; }
[[ "$(fdtget -t u "$SRC" /osc-clk clock-frequency)" == 26000000 ]] || exit 1
status="$(fdtget -t s "$SRC" /soc/mmc@4020000 status)"
[[ "$status" == disabled ]] || { echo "STOP: expected disabled MMC0" >&2; exit 1; }
[[ "$OUT" != "$SRC" ]] || exit 1
cp "$SRC" "$OUT"
# 150,000,000 decimal = 0x08f0d180; requested MAXIMUM, not forced runtime clock
fdtput -t x "$OUT" /soc/mmc@4020000 max-frequency 0x08f0d180
[[ "$(fdtget -t u "$OUT" /soc/mmc@4020000 max-frequency)" == 150000000 ]] || exit 1
[[ "$(fdtget -t u "$OUT" /osc-clk clock-frequency)" == 26000000 ]] || exit 1
[[ "$(fdtget -t s "$OUT" /soc/mmc@4020000 status)" == disabled ]] || exit 1
sha256sum "$SRC" "$OUT"
echo "MMC0 max-frequency 150MHz staged; MMC0 DISABLED. No SD bus timing or voltage has been tested."

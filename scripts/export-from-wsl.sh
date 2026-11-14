#!/usr/bin/env bash
set -euo pipefail
# Audit export ONLY; does not change any kernel worktree or commit to GitHub.
W="${1:-/root/opi3w-m2-work}"
OUT="${2:-/root/opi3w-mainline-source-review}"
K="$W/m2aa-hdmi-probe"
P="$W/m2r-worktree"
if [[ ! -d "$K/.git" && ! -f "$K/.git" ]]; then
  echo "Kernel worktree missing: $K" >&2; exit 2
fi
if [[ ! -d "$P/.git" && ! -f "$P/.git" ]]; then
  echo "PMIC worktree missing: $P" >&2; exit 2
fi
if [[ -e "$OUT" ]]; then echo "Refusing existing output: $OUT" >&2; exit 3; fi
mkdir -p "$OUT"
for pair in "kernel:$K" "pmic:$P"; do
  name=${pair%%:*}; dir=${pair#*:}
  mkdir -p "$OUT/$name"
  git -C "$dir" rev-parse HEAD > "$OUT/$name/base-commit.txt"
  git -C "$dir" status --short > "$OUT/$name/status.txt"
  git -C "$dir" diff --binary HEAD -- \
    arch/arm64/boot/dts/allwinner \
    drivers/clk/sunxi-ng drivers/pinctrl/sunxi drivers/tty/serial \
    drivers/mmc/host drivers/i2c/busses drivers/mfd \
    drivers/regulator include/linux/mfd \
    > "$OUT/$name/tracked.patch"
  git -C "$dir" ls-files --others --exclude-standard -- \
    arch/arm64/boot/dts/allwinner drivers/clk/sunxi-ng \
    drivers/pinctrl/sunxi drivers/tty/serial drivers/mmc/host \
    drivers/i2c/busses drivers/mfd drivers/regulator include/linux/mfd \
    > "$OUT/$name/untracked-candidates.txt"
done
# Copy only named board source snapshots, never a whole vendor tree.
for path in \
  "$W/m2ca-results/artifacts/sun60i-a733-orangepi-zero3w-m2by.dts" \
  "$K/arch/arm64/boot/dts/allwinner/sun60i-a733.dtsi" \
  "$K/arch/arm64/boot/dts/allwinner/sun60i-a733-orangepi-zero3w-m2by.dts" \
  "$W/build-m2aa/.config"
do
  if [[ -f "$path" ]]; then
    cp -- "$path" "$OUT/$(basename "$path")"
  fi
done
{
  echo "# Review required before publication"
  echo "No sources copied automatically from the untracked-candidates lists."
  echo "Kernel source from experimental M2aa branch can contain absolute include paths and vendor copies."
  echo "Review tracked.patch, untracked-candidates.txt and missing prerequisite commits."
  echo "Do not publish whole worktrees or vendor-source/linux."
} > "$OUT/README.txt"
(cd "$OUT" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$OUT/SHA256SUMS"
echo "Exported review evidence to: $OUT"

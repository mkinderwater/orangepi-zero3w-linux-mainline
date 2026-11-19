#!/usr/bin/env bash
# Apply proven M2R/M2T AXP8191 support in a separate kernel source copy.
# Resolve the *known* axp20x-i2c.c context conflict programmatically.
# No PMIC register access, bootloader changes, or flash writes on build host.
set -euo pipefail

BASE="${BASE:-/root/opi3w-m2-work/a733-try9-ramoops-v2/linux}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-axp8191}"
P1=/root/opi3w-m2r-618/patches/0001-axp8191-staged-mfd.patch
P2=/root/opi3w-m2r-618/patches/0002-axp8191-minimal-regulators.patch
P3=/root/opi3w-m2t-618/patches/0001-axp8191-skip-unverified-workmode.patch

for cmd in rsync git python3 sha256sum make aarch64-linux-gnu-gcc; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }
done
for f in "$P1" "$P2" "$P3" "$BASE/Makefile"; do
  [[ -f "$f" ]] || { echo "Missing $f" >&2; exit 1; }
done
[[ "$OUT" != "$BASE" && "$OUT" != / ]] || exit 1
if [[ -e "$OUT/linux" ]]; then
  echo "STOP: $OUT/linux already exists. Select a new OUT; no source overwrite." >&2
  exit 1
fi

mkdir -p "$OUT"
rsync -a --exclude='.git' --exclude='*.o' --exclude='*.ko'   --exclude='*.cmd' --exclude='vmlinux' --exclude='Image' \
  "$BASE/" "$OUT/linux/"
SRC="$OUT/linux"
mkdir -p "$OUT/obj" "$OUT/artifacts"
cp /root/opi3w-m2-work/linux-618-full-integration/artifacts/kernel.config "$OUT/obj/.config"
sha256sum "$P1" "$P2" "$P3" > "$OUT/patches.sha256"

# Patch 1's MFD core and AXP8191 identifiers match; only the I2C table
# contexts changed in the current Linux 6.18 source. Apply non-I2C hunks.
git -C "$SRC" apply --check --exclude=drivers/mfd/axp20x-i2c.c "$P1"
git -C "$SRC" apply --exclude=drivers/mfd/axp20x-i2c.c "$P1"

# Add exact AXP8191 match entries. Abort on ambiguity, never invent addresses.
python3 - "$SRC/drivers/mfd/axp20x-i2c.c" <<'PY'
from pathlib import Path
import re, sys
p = Path(sys.argv[1])
s = p.read_text()
if '"x-powers,axp8191"' in s or '{ "axp8191" }' in s:
    raise SystemExit("Unexpected preexisting AXP8191 I2C entry")
ofpat = r'(?m)^(?P<indent>\s*)\{\s*\.compatible\s*=\s*"x-powers,axp15060"[^\n]*\},?\s*$'
idpat = r'(?m)^(?P<indent>\s*)\{\s*"axp15060"[^\n]*\},?\s*$'
def after_single(pattern, line):
    global s
    matches = list(re.finditer(pattern, s))
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one anchor for {line}, got {len(matches)}")
    m = matches[0]
    s = s[:m.end()] + '\n' + m.group('indent') + line + s[m.end():]
after_single(ofpat, '{ .compatible = "x-powers,axp8191", .data = (void *)AXP8191_ID },')
after_single(idpat, '{ "axp8191" },')
p.write_text(s)
PY

git -C "$SRC" apply --check "$P2"
git -C "$SRC" apply "$P2"
git -C "$SRC" apply --check "$P3"
git -C "$SRC" apply "$P3"

# Tighten historical permissive regmap: only validated low-bank rail controls;
# do not permit the broad 0x10..0x33 range or IRQ status/enable writes.
python3 - "$SRC/drivers/mfd/axp20x.c" <<'PY'
from pathlib import Path
import re, sys
p = Path(sys.argv[1])
s = p.read_text()
pattern = r'static const struct regmap_range axp8191_writeable_ranges\[\] = \{.*?\n\};'
replacement = '''static const struct regmap_range axp8191_writeable_ranges[] = {
    regmap_reg_range(AXP8191_DCDC_CTL1, AXP8191_DC1OUT_VOL),
    regmap_reg_range(AXP8191_LDO_CTL2, AXP8191_LDO_CTL2),
    regmap_reg_range(AXP8191_CLDO5OUT_VOL, AXP8191_CLDO5OUT_VOL),
};'''
s, count = re.subn(pattern, replacement, s, flags=re.S)
if count != 1: raise SystemExit(f"Expected one regmap write table: {count}")
# For AXP8191 skip IRQ registration (unverified) and power-off handling.
if 'axp20x->irq > 0 && axp20x->variant != AXP8191_ID' not in s:
    s, count = re.subn(
        r'if \(axp20x->irq > 0\) \{',
        'if (axp20x->irq > 0 && axp20x->variant != AXP8191_ID) {',s,count=1)
    if count != 1: raise SystemExit("Cannot guard IRQ init")
if 'axp20x->variant != AXP288_ID &&' not in s:
    s, count = re.subn(
       r'if \(axp20x->variant != AXP288_ID\)',
       'if (axp20x->variant != AXP288_ID &&\n'
       '        axp20x->variant != AXP8191_ID)', s, count=1)
    if count != 1: raise SystemExit("Cannot guard power-off handler")
# Regmap IRQ chip pointer remains null for AXP8191 and must not be removed.
s = s.replace('regmap_del_irq_chip(axp20x->irq, axp20x->regmap_irqc);',
              'if (axp20x->regmap_irqc)\n'
              '            regmap_del_irq_chip(axp20x->irq, axp20x->regmap_irqc);')
p.write_text(s)
PY

make -C "$SRC" O="$OUT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
for opt in MFD_AXP20X MFD_AXP20X_I2C REGULATOR_AXP20X MMC MMC_SUNXI; do
  grep -qx "CONFIG_${opt}=y" "$OUT/obj/.config" || { echo "Missing $opt" >&2; exit 1; }
done
JOBS="${JOBS:-4}"
make -C "$SRC" O="$OUT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j"$JOBS" Image modules

cp "$OUT/obj/arch/arm64/boot/Image" "$OUT/artifacts/Image-618-axp8191"
cp "$OUT/obj/.config" "$OUT/artifacts/kernel.config"
sha256sum "$OUT/artifacts/"* > "$OUT/artifacts.sha256"
echo "AXP8191 kernel build complete. MMC0 power DTB and runtime probe STILL REQUIRE TESTING."
cat "$OUT/artifacts.sha256"

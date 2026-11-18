#!/usr/bin/env bash
# Produce an isolated one-variable 26 MHz root-oscillator hypothesis DTB.
# No writes to the kernel checkout, boot media or source DTB.
set -euo pipefail

SOURCE="${SOURCE:-/root/opi3w-m2-work/a733-try9-ramoops-v2/sun60i-a733-orangepi-zero3w.dtb}"
OUT="${OUT:-/home/ram-b-clock-test}"
BASE_SHA="b63266e8d73611abd2fb693b101f05373134c32ea5784c0899cf969eb00473a1"

for tool in fdtget fdtput dtc sha256sum cmp diff; do
    command -v "$tool" >/dev/null || { echo "Missing: $tool" >&2; exit 1; }
done
[[ -f "$SOURCE" ]] || { echo "Missing source DTB: $SOURCE" >&2; exit 1; }
got="$(sha256sum "$SOURCE" | awk '{print $1}')"
[[ "$got" == "$BASE_SHA" ]] || {
    echo "STOP: RAM-A source DTB hash mismatch: $got" >&2
    exit 1
}
freq="$(fdtget -t u "$SOURCE" /osc-clk clock-frequency)"
[[ "$freq" == "24000000" ]] || {
    echo "STOP: expected original 24 MHz, got $freq" >&2
    exit 1
}
mkdir -p "$OUT"
BASE="$OUT/sun60i-a733-orangepi-zero3w-ram-a-control.dtb"
TEST="$OUT/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb"
cp -- "$SOURCE" "$BASE"
cp -- "$SOURCE" "$TEST"
fdtput -t x "$TEST" /osc-clk clock-frequency 0x018cba80
[[ "$(fdtget -t u "$TEST" /osc-clk clock-frequency)" == "26000000" ]] || {
    echo "STOP: test clock property did not change as expected" >&2; exit 1;
}
[[ "$(fdtget -t u "$BASE" /osc-clk clock-frequency)" == "24000000" ]] || exit 1
dtc -I dtb -O dts -o "$OUT/ram-a-control.dts" "$BASE" 2>"$OUT/control-dtc-warnings.txt"
dtc -I dtb -O dts -o "$OUT/ram-b-26mhz-test.dts" "$TEST" 2>"$OUT/test-dtc-warnings.txt"
diff -u "$OUT/ram-a-control.dts" "$OUT/ram-b-26mhz-test.dts" > "$OUT/DTB-CHANGE.diff" || [[ "$?" == 1 ]]
# Require exactly one '-' and one '+' change, both for clock-frequency.
minus="$(grep -c '^-[^-]' "$OUT/DTB-CHANGE.diff" || :)"
plus="$(grep -c '^+[^+]' "$OUT/DTB-CHANGE.diff" || :)"
[[ "$minus" == 1 && "$plus" == 1 ]] || {
    echo "STOP: more than one device-tree property changed. Review $OUT/DTB-CHANGE.diff" >&2; exit 1;
}
grep -Eq '^-[[:space:]]*clock-frequency = <0x16e3600>;' "$OUT/DTB-CHANGE.diff" || exit 1
grep -Eq '^\+[[:space:]]*clock-frequency = <0x18cba80>;' "$OUT/DTB-CHANGE.diff" || exit 1

sha256sum "$BASE" "$TEST" > "$OUT/SHA256SUMS"
{
    printf 'Source DTB: %s\nSource SHA256: %s\n' "$SOURCE" "$BASE_SHA"
    printf 'CONTROL /osc-clk Hz: %s\n' "$(fdtget -t u "$BASE" /osc-clk clock-frequency)"
    printf 'TEST /osc-clk Hz: %s\n' "$(fdtget -t u "$TEST" /osc-clk clock-frequency)"
    printf 'Status: TEST ONLY. This does not prove a 26 MHz crystal.\n'
    printf 'No kernel, initramfs, boot script, firmware or SD card modified.\n'
} > "$OUT/MANIFEST.txt"
cat "$OUT/MANIFEST.txt"
cat "$OUT/DTB-CHANGE.diff"
cat "$OUT/SHA256SUMS"

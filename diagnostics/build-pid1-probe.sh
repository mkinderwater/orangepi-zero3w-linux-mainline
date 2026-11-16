#!/usr/bin/env bash
set -euo pipefail
base="$(cd "$(dirname "$0")/.." && pwd)"
out="$1"
mkdir -p "$out/root/dev" "$out/root/proc" "$out/root/sys"
aarch64-linux-gnu-gcc -static -O2 -Wall -Wextra -Werror -o "$out/root/init" "$base/diagnostics/pid1_probe.c"
readelf -h "$out/root/init" | grep -q 'Machine:.*AArch64'
if readelf -l "$out/root/init" | grep -q INTERP; then echo 'DYNAMIC LINK FAILURE' >&2; exit 1; fi
(cd "$out/root" && find . -print0 | LC_ALL=C sort -z | cpio --null --quiet -o -H newc) | gzip -9 -n > "$out/pid1-probe-initramfs.cpio.gz"
gzip -t "$out/pid1-probe-initramfs.cpio.gz"
gzip -dc "$out/pid1-probe-initramfs.cpio.gz" | cpio -it --quiet | grep -qx './init'
sha256sum "$out/root/init" "$out/pid1-probe-initramfs.cpio.gz" > "$out/SHA256SUMS"
echo "BUILD_ONLY: $out/pid1-probe-initramfs.cpio.gz"

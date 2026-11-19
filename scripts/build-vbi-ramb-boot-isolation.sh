#!/usr/bin/env bash
# Add known-good RAM-B kernel, DTB and diagnostic initramfs to a disposable
# clone of the hardware-booted VBI ext4 image, without changing VBI boot files,
# firmware, partition table, or boot scripts. Manually boot via U-Boot ext4load.
set -euo pipefail

VBI="${VBI:-/home/opi3w-VBI-vendor-A2V-booti.img}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-hdmi-stage4/artifacts/opi3w-VBI-RAMB-isolation.img}"
IMAGE="${IMAGE:-/home/Image-ram-b-script-fix}"
DTB="${DTB:-/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb}"
INITRD="${INITRD:-/root/opi3w-m2-work/a733-ram-ab-v1/a733-clean-uart-ram-b-v1.img}"
VBI_SHA="7c76d125013df144d238526e396c1c9d5878c2cdf57eaa3ac09f613e32afa63c"
IMAGE_SHA="67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8"
DTB_SHA="1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d"
INITRD_SHA="1a68a774c6b47081f338bcc8f595b4a154dbd433293cf3ad1b8df31cc7ac919b"
TMP=""
MOUNTED=0
CREATED=0
COMPLETE=0

die() { echo "STOP: $*" >&2; exit 1; }
cleanup() {
  status=$?
  if (( MOUNTED )); then sync; umount "$TMP/root" || status=1; fi
  if [[ -n "$TMP" && -d "$TMP" ]]; then rm -rf "$TMP"; fi
  if (( CREATED && ! COMPLETE )); then
    rm -f "$OUT" "$OUT.sha256" "$OUT.manifest.txt"
  fi
  exit "$status"
}
trap cleanup EXIT
[[ "$(id -u)" -eq 0 ]] || die "Must run as root"
for tool in mount umount sfdisk sha256sum python3 cmp find cp sync; do
  command -v "$tool" >/dev/null || die "Missing $tool"
done
[[ -f "$VBI" && -f "$IMAGE" && -f "$DTB" && -f "$INITRD" ]] || die "Missing source input"
[[ "$OUT" != "$VBI" && ! -e "$OUT" ]] || die "Output collision or already exists"
check() {
  local h
  h="$(sha256sum "$1")"
  h="${h%% *}"
  [[ "$h" == "$2" ]] || die "SHA mismatch: $1 expected $2 got $h"
}
check "$VBI" "$VBI_SHA"
check "$IMAGE" "$IMAGE_SHA"
check "$DTB" "$DTB_SHA"
# The input named INITRD is a whole disk image, NOT the initramfs. The
# actual initramfs gets extracted from the FAT partition with an offset
# into the verified RAM-B source. This avoids accepting a guessed file.
RAB_BASE="$INITRD"
check "$RAB_BASE" "0829e193cf90a4f54bfa6beca0be456316de1e648f978d25ecaa37ddafcf2ba1"
TMP="$(mktemp -d)"
mkdir -p "$TMP/root" "$TMP/fat"
FAT_OFFSET=$((65536*512))
FAT_BYTES=$((131072*512))
mount -t vfat -o "ro,loop,offset=$FAT_OFFSET,sizelimit=$FAT_BYTES" "$RAB_BASE" "$TMP/fat"
cp "$TMP/fat/mainline/uart-diagnostic-initrd.gz" "$TMP/initrd.gz"
umount "$TMP/fat"
check "$TMP/initrd.gz" "$INITRD_SHA"
# Image must have one ext4 Linux partition starting at sector 65536.
sfdisk -J "$VBI" > "$TMP/parts.json"
python3 - "$TMP/parts.json" > "$TMP/mount-values.txt" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))["partitiontable"]
entries=p["partitions"]
if len(entries)!=1 or str(entries[0].get("type","")).lower().removeprefix("0x")!="83" or entries[0]["start"]!=65536:
    raise SystemExit("STOP: VBI layout differs from expected one Linux partition")
sector=int(p.get("sectorsize",512))
print(entries[0]["start"]*sector,entries[0]["size"]*sector)
PY
read -r OFFSET LIMIT < "$TMP/mount-values.txt"
mkdir -p "$(dirname "$OUT")"
cp --reflink=auto --sparse=always "$VBI" "$OUT"
CREATED=1
mount -t ext4 -o "loop,offset=$OFFSET,sizelimit=$LIMIT" "$OUT" "$TMP/root"
MOUNTED=1
# Avoid altering the actual VBI boot path. Hash vendor boot scripts and
# payloads before adding isolated files.
for f in boot.scr mainline/stock-vendor-stage2.scr mainline/verified-vendor-Image mainline/verified-vendor-initrd.gz; do
  [[ -f "$TMP/root/boot/$f" ]] || die "Missing expected VBI vendor boot file $f"
done
(
  cd "$TMP/root/boot"
  sha256sum boot.scr mainline/stock-vendor-stage2.scr mainline/verified-vendor-Image mainline/verified-vendor-initrd.gz
) > "$TMP/vendor-before.sha256"
DEST="$TMP/root/boot/mainline/ram-b-vbi-isolation"
[[ ! -e "$DEST" ]] || die "Destination already exists in VBI image"
mkdir "$DEST"
python3 - "$IMAGE" "$DEST/Image" "$DTB" "$DEST/ram-b-26mhz.dtb" "$TMP/initrd.gz" "$DEST/initrd.gz" <<'PY'
import os,sys
for i in (1,3,5):
    src,dest=sys.argv[i:i+2]
    size=os.path.getsize(src)
    with open(src,"rb") as r:
        fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
        try:
            os.posix_fallocate(fd,0,size)
            while True:
                data=r.read(1024*1024)
                if not data:break
                offset=0
                while offset<len(data):
                    written=os.write(fd,data[offset:])
                    if not written:raise OSError("short write")
                    offset+=written
            os.fsync(fd)
        finally:
            os.close(fd)
PY
for pair in "$IMAGE:Image" "$DTB:ram-b-26mhz.dtb" "$TMP/initrd.gz:initrd.gz"; do
  src="${pair%%:*}"; dest="${pair##*:}"
  cmp "$src" "$DEST/$dest" || die "Payload copy mismatch $dest"
done
python3 - "$DEST" <<'PY'
import os,sys
for name in ("Image","ram-b-26mhz.dtb","initrd.gz"):
    p=os.path.join(sys.argv[1],name)
    st=os.stat(p)
    if st.st_blocks*512<st.st_size: raise SystemExit("STOP: sparse ext4 boot payload "+p)
    print("DENSE:",name,st.st_size,st.st_blocks*512)
PY
(
  cd "$TMP/root/boot"
  sha256sum boot.scr mainline/stock-vendor-stage2.scr mainline/verified-vendor-Image mainline/verified-vendor-initrd.gz
) > "$TMP/vendor-after.sha256"
cmp "$TMP/vendor-before.sha256" "$TMP/vendor-after.sha256" || die "Vendor boot payload changed"
sync
umount "$TMP/root"
MOUNTED=0
# Check VBI's reserved firmware and partition table have not changed.
cmp -n 33554432 "$VBI" "$OUT" || die "Firmware prefix or MBR changed"
# Inspect final payloads from a read-only, journal-replay-disabled mount.
mount -t ext4 -o "ro,noload,loop,offset=$OFFSET,sizelimit=$LIMIT" "$OUT" "$TMP/root"
MOUNTED=1
FINAL="$TMP/root/boot/mainline/ram-b-vbi-isolation"
check "$FINAL/Image" "$IMAGE_SHA"
check "$FINAL/ram-b-26mhz.dtb" "$DTB_SHA"
check "$FINAL/initrd.gz" "$INITRD_SHA"
(
  cd "$TMP/root/boot"
  sha256sum boot.scr mainline/stock-vendor-stage2.scr mainline/verified-vendor-Image mainline/verified-vendor-initrd.gz
) > "$TMP/vendor-final.sha256"
cmp "$TMP/vendor-before.sha256" "$TMP/vendor-final.sha256" || die "Vendor boot control changed"
umount "$TMP/root"
MOUNTED=0
sha256sum "$OUT" > "$OUT.sha256"
{
  echo "VBI-RAMB-ISOLATION: NOT HARDWARE TESTED"
  echo "Input VBI: $VBI"
  echo "Image: $OUT"
  echo "VBI vendor boot scripts and payloads unchanged"
  echo "Firmware 32MiB and partition table unchanged"
  echo "Added /boot/mainline/ram-b-vbi-isolation/{Image,ram-b-26mhz.dtb,initrd.gz}"
  echo "Manual U-Boot ext4load required; DO NOT automatically change vendor boot scripts"
  echo "Kernel SHA: $IMAGE_SHA"
  echo "DTB SHA: $DTB_SHA"
  echo "Initramfs SHA: $INITRD_SHA"
} > "$OUT.manifest.txt"
COMPLETE=1
echo "SUCCESS: $OUT"
cat "$OUT.sha256"
echo "Vendor boot control preserved. Flash only to a spare SD."

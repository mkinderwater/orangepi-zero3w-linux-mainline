#!/usr/bin/env bash
# Build a flashable A733 RAM-B/PCK600 test image by cloning an independently
# hardware-booted, two-stage U-Boot image. Bootloader and disk layout unchanged.
# Usage: sudo BASE_IMAGE=/path/to/BOOT-PROVEN.img bash scripts/build-pck600-flash-image.sh
# Never points at /dev/sdX: this creates a new .img, not a flash operation.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
BASE_IMAGE="${BASE_IMAGE:-}"
OUT_IMAGE="${OUT_IMAGE:-$ROOT/artifacts/opi3w-618-pck600-probe.img}"
KERNEL="$ROOT/artifacts/Image-618-vendor-hdmi-pck600-syscon"
DTB="$ROOT/artifacts/ram-b-26mhz-pck600-probe.dtb"
# Paths inside rootfs must match load paths in booted stage2.scr.
KERNEL_TARGET="${KERNEL_TARGET:-/boot/mainline/Image}"
DTB_TARGET="${DTB_TARGET:-/boot/mainline/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb}"
STAGE2="${STAGE2:-/boot/mainline/stage2.scr}"
KERNEL_SHA="9f8c4af6f7f3d5ff604aac29bd7553e04dc3a41c0c8a5000308594c49ab5cb1c"
DTB_SHA="c5cc45413f4be4efbf80a1c26c061462e2a9b2e3649a49bf055b008d5209f697"
TMP=""
LOOP=""
MOUNTED=0
COMPLETE=0
cleanup() {
  ret=$?
  if (( MOUNTED )); then sync; umount "$TMP/mnt" || ret=1; fi
  if [[ -n "$LOOP" ]]; then losetup -d "$LOOP" || ret=1; fi
  if [[ -n "$TMP" && -d "$TMP" ]]; then rm -rf "$TMP"; fi
  if (( ! COMPLETE )) && [[ -n "$OUT_IMAGE" && -f "$OUT_IMAGE" ]]; then
    echo "Removing incomplete output image: $OUT_IMAGE" >&2
    rm -f -- "$OUT_IMAGE" "$OUT_IMAGE.sha256" "$OUT_IMAGE.manifest.txt"
  fi
  exit "$ret"
}
trap cleanup EXIT
die() { echo "STOP: $*" >&2; exit 1; }
[[ "$(id -u)" -eq 0 ]] || die "run as root"
[[ -n "$BASE_IMAGE" && -f "$BASE_IMAGE" ]] || die "BASE_IMAGE must name a previously boot-tested disk .img"
for t in losetup lsblk mount umount blkid sfdisk sha256sum python3 dumpimage e2fsck stat cmp; do
  command -v "$t" >/dev/null || die "Missing tool $t"
done
[[ "$BASE_IMAGE" != "$OUT_IMAGE" ]] || die "BASE_IMAGE and OUT_IMAGE must differ"
[[ ! -e "$OUT_IMAGE" ]] || die "Output already exists: $OUT_IMAGE"
[[ "$(sha256sum "$KERNEL" | awk '{print $1}')" == "$KERNEL_SHA" ]] || die "Kernel SHA mismatch"
[[ "$(sha256sum "$DTB" | awk '{print $1}')" == "$DTB_SHA" ]] || die "DTB SHA mismatch"
# Do not modify baseline. Check directory, then copy.
mkdir -p "$(dirname "$OUT_IMAGE")"
TMP="$(mktemp -d)"
mkdir -p "$TMP/mnt"
echo "Cloning base image (bootloader and partition layout remain byte-for-byte)..."
cp --reflink=auto --sparse=never -- "$BASE_IMAGE" "$OUT_IMAGE"
LOOP="$(losetup --find --show --partscan "$OUT_IMAGE")"
# First ext4 partition normally p1 (stock) or p2 (0.7.6). Exactly one
# unambiguous root partition is required, to avoid patching the wrong rootfs.
mapfile -t roots < <(lsblk -nr -o PATH,FSTYPE "$LOOP" | awk '$2=="ext4" {print $1}')
[[ "${#roots[@]}" -eq 1 ]] || die "Expected exactly one ext4 root partition, found ${#roots[@]}: ${roots[*]}"
PART="${roots[0]}"
# Validate partition layout, filesystem state, and 32MiB reserved firmware prefix.
sfdisk -J "$LOOP" > "$TMP/partition-table.json"
python3 - "$TMP/partition-table.json" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))["partitiontable"]
part=j.get("partitions",[])
if not part: raise SystemExit("STOP: no partition table")
if min(p["start"] for p in part)!=65536:
    raise SystemExit("STOP: expected first partition at 32 MiB/65536 sectors, got "+str(min(p["start"] for p in part)))
PY
mount -t ext4 "$PART" "$TMP/mnt"
MOUNTED=1
target="$TMP/mnt"
for path in "$KERNEL_TARGET" "$DTB_TARGET" "$STAGE2"; do
  [[ "$path" == /boot/* && "$path" != *".."* ]] || die "Unsafe target path: $path"
  [[ -f "$target$path" && ! -L "$target$path" ]] || die "Required boot file missing or symlink: $path"
done
# Existing second stage must actually load BOTH selected filenames and use
# ARM64 raw booti. Its handoff logic is unchanged in this experiment.
dumpimage -T script -p 0 -o "$TMP/stage2.cmd" "$target$STAGE2" >"$TMP/dumpimage.log" 2>&1 ||
  die "Unable to extract stage2 script: $STAGE2"
grep -Fq -- "$KERNEL_TARGET" "$TMP/stage2.cmd" ||
  die "stage2 does not reference kernel path $KERNEL_TARGET"
grep -Fq -- "$DTB_TARGET" "$TMP/stage2.cmd" ||
  die "stage2 does not reference DTB path $DTB_TARGET"
grep -Eq '(^|[[:space:]])booti([[:space:]]|$)' "$TMP/stage2.cmd" ||
  die "stage2 has no booti command"
# For safety require initramfs to be referenced and present, but never change it.
grep -Eq 'initrd|ramdisk' "$TMP/stage2.cmd" ||
  die "stage2 lacks visible initramfs reference"
# Explicit preservation of old files external to image, plus their hashes.
cp -- "$target$KERNEL_TARGET" "$TMP/original-kernel"
cp -- "$target$DTB_TARGET" "$TMP/original-dtb"
sha256sum "$TMP/original-kernel" "$TMP/original-dtb" > "$TMP/original-payloads.sha256"
# Dense replacement using posix_fallocate and full byte writes. Avoid holes
# inside ext4 files (U-Boot historically sensitive to sparse /boot files).
python3 - "$KERNEL" "$target$KERNEL_TARGET" "$DTB" "$target$DTB_TARGET" <<'PY'
import os,sys
def replace(src,dst):
    data=open(src,'rb').read()
    fd=os.open(dst,os.O_WRONLY|os.O_TRUNC)
    try:
        os.posix_fallocate(fd,0,len(data))
        n=0
        while n<len(data):
            count=os.write(fd,data[n:])
            if count<=0: raise OSError("short write")
            n+=count
        os.fsync(fd)
    finally:
        os.close(fd)
for i in (1,3): replace(sys.argv[i],sys.argv[i+1])
PY
cmp "$KERNEL" "$target$KERNEL_TARGET" || die "kernel copy mismatch"
cmp "$DTB" "$target$DTB_TARGET" || die "DTB copy mismatch"
# Files in /boot should be dense. st_blocks counts allocated 512B blocks.
python3 - "$target$KERNEL_TARGET" "$target$DTB_TARGET" <<'PY'
import os,sys
for file in sys.argv[1:]:
    st=os.stat(file)
    if st.st_blocks*512 < st.st_size:
        raise SystemExit("STOP: sparse boot payload "+file)
    print("DENSE:",file,st.st_size,"bytes, allocated",st.st_blocks*512)
PY
sync
umount "$TMP/mnt"
MOUNTED=0
losetup -d "$LOOP"
LOOP=""
# Verify final image partition and payloads read-only.
LOOP="$(losetup --find --show --partscan --read-only "$OUT_IMAGE")"
mapfile -t roots < <(lsblk -nr -o PATH,FSTYPE "$LOOP" | awk '$2=="ext4" {print $1}')
[[ "${#roots[@]}" -eq 1 ]] || die "Final image root partition not found"
e2fsck -fn "${roots[0]}" > "$TMP/fsck.log" 2>&1 || {
  cat "$TMP/fsck.log"; die "Read-only fsck reported filesystem errors";
}
mount -o ro -t ext4 "${roots[0]}" "$TMP/mnt"
MOUNTED=1
cmp "$KERNEL" "$TMP/mnt$KERNEL_TARGET" || die "Final image kernel differs"
cmp "$DTB" "$TMP/mnt$DTB_TARGET" || die "Final image DTB differs"
dumpimage -T script -p 0 -o "$TMP/stage2-after.cmd" "$TMP/mnt$STAGE2" >/dev/null 2>&1 || die "Cannot re-read stage2"
cmp "$TMP/stage2.cmd" "$TMP/stage2-after.cmd" || die "Stage2 changed"
# firmware prefix unchanged. The first 32 MiB contain vendor boot firmware.
cmp -n 33554432 "$BASE_IMAGE" "$OUT_IMAGE" || die "Firmware prefix differs"
sha256sum "$OUT_IMAGE" > "$OUT_IMAGE.sha256"
printf '%s\n' "BOOT-PROBE (NOT HARDWARE TESTED)" \
 "Base: $BASE_IMAGE" "Output: $OUT_IMAGE" \
 "Kernel: $KERNEL_SHA -> $KERNEL_TARGET" \
 "DTB: $DTB_SHA -> $DTB_TARGET" "Stage2 unchanged: $STAGE2" \
 "Vendor firmware prefix unchanged; original image untouched" \
 "TEST ONLY. Flash on a spare USB/SD device, never the only recovery media." > "$OUT_IMAGE.manifest.txt"
echo "Image: $OUT_IMAGE"
cat "$OUT_IMAGE.sha256"
COMPLETE=1
echo "Boot image ready for controlled UART test, NOT hardware-tested."

#!/usr/bin/env bash
# Generate isolated RAM-B control and kernel-regression FAT boot images.
# Source image and vendor firmware are immutable. Output is a raw flashable .img.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
BASE_IMAGE="${BASE_IMAGE:-/root/opi3w-m2-work/a733-ram-ab-v1/a733-clean-uart-ram-b-v1.img}"
CASE="${CASE:-}"
case "$CASE" in
  A)
    OUT_IMAGE="${OUT_IMAGE:-$ROOT/artifacts/opi3w-618-ram-b-control-A.img}"
    KERNEL="/home/Image-ram-b-script-fix"
    DTB="/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb"
    KERNEL_SHA="67a0a073950bb6c92e2a06e61235e90509ad5d3964703dec70cb4f53e4a339c8"
    DTB_SHA="1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d"
    ;;
  B)
    OUT_IMAGE="${OUT_IMAGE:-$ROOT/artifacts/opi3w-618-hdmi-kernel-ram-b-dtb-B.img}"
    KERNEL="$ROOT/artifacts/Image-618-vendor-hdmi-pck600-syscon"
    DTB="/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb"
    KERNEL_SHA="9f8c4af6f7f3d5ff604aac29bd7553e04dc3a41c0c8a5000308594c49ab5cb1c"
    DTB_SHA="1ff786ed912df7d4b4d19e366b3c968a5e0552c39f58d61a8414514eba141d9d"
    ;;
  *)
    echo "Usage: CASE=A|B bash scripts/build-ram-b-ab-flash-image.sh" >&2
    exit 2
    ;;
esac
BASE_SHA=0829e193cf90a4f54bfa6beca0be456316de1e648f978d25ecaa37ddafcf2ba1
INITRD_SHA=1a68a774c6b47081f338bcc8f595b4a154dbd433293cf3ad1b8df31cc7ac919b
TMP=""
MOUNTED=0
COMPLETE=0
OUTPUT_CREATED=0
fail() { echo "STOP: $*" >&2; exit 1; }
cleanup() {
  rc=$?
  if (( MOUNTED )); then sync; umount "$TMP/fat" || rc=1; fi
  [[ -z "$TMP" ]] || rm -rf -- "$TMP"
  if (( OUTPUT_CREATED && ! COMPLETE )); then rm -f -- "$OUT_IMAGE" "$OUT_IMAGE.sha256" "$OUT_IMAGE.manifest.txt"; fi
  exit "$rc"
}
trap cleanup EXIT
[[ $(id -u) == 0 ]] || fail "root required to mount FAT partition"
for c in sfdisk mount umount sha256sum cmp python3 strings cp stat; do command -v "$c" >/dev/null || fail "Missing $c"; done
[[ -f "$BASE_IMAGE" ]] || fail "Base image missing: $BASE_IMAGE"
[[ -f "$KERNEL" && -f "$DTB" ]] || fail "Kernel or DTB missing"
[[ "$BASE_IMAGE" != "$OUT_IMAGE" && ! -e "$OUT_IMAGE" ]] || fail "Output collision or already exists"
check_hash() {
  local got
  got=$(sha256sum "$1"); got=${got%% *}
  [[ "$got" == "$2" ]] || fail "SHA256 mismatch for $1: $got"
}
check_hash "$BASE_IMAGE" "$BASE_SHA"
check_hash "$KERNEL" "$KERNEL_SHA"
check_hash "$DTB" "$DTB_SHA"
# Ensure raw ARM64 Image fits below the 0x44000000 DTB load location.
python3 - "$KERNEL" <<'PY'
import pathlib,struct,sys
d=pathlib.Path(sys.argv[1]).read_bytes()
if len(d)<64 or d[56:60]!=b"ARM\x64":
    raise SystemExit("STOP: not an AArch64 Image header")
offset,size=struct.unpack_from("<QQ",d,8)
footprint=max(len(d),offset+size) if size else len(d)
if footprint>=0x03000000:
    raise SystemExit(f"STOP: kernel would overlap FDT at 0x44000000: {footprint} bytes")
print(f"Kernel Image bytes={len(d)}, text_offset={offset}, declared size={size}, footprint={footprint}")
PY
if [[ "$CASE" == B ]]; then
  CONFIG="$ROOT/artifacts/Image-618-vendor-hdmi-pck600-syscon.config"
else
  CONFIG="/root/opi3w-m2-work/ram-b-script-fix/obj/.config"
fi
[[ -f "$CONFIG" ]] || fail "Kernel build config missing: $CONFIG"
grep -qx "CONFIG_BINFMT_SCRIPT=y" "$CONFIG" || fail "Kernel lacks CONFIG_BINFMT_SCRIPT"
if [[ "$CASE" == B ]]; then
  grep -qx "CONFIG_SUN55I_PCK600=y" "$CONFIG" || fail "Case B lacks PCK600"
fi
TMP=$(mktemp -d)
mkdir -p "$TMP/fat" "$(dirname "$OUT_IMAGE")"
echo "Cloning verified RAM-B base (no firmware changes)..."
cp --reflink=auto --sparse=always -- "$BASE_IMAGE" "$OUT_IMAGE"
OUTPUT_CREATED=1
# Read partition offsets from the actual MBR, never guess the FAT location.
sfdisk -J "$OUT_IMAGE" > "$TMP/partitions.json"
python3 - "$TMP/partitions.json" > "$TMP/fat-offset.txt" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))["partitiontable"]
sector=int(p.get("sectorsize",512))
parts=p.get("partitions",[])
fat=[x for x in parts if str(x.get("type","")).lower().removeprefix("0x") in ("b","c","e","06","0b","0c","0e","6")]
roots=[x for x in parts if str(x.get("type","")).lower().removeprefix("0x")=="83"]
if len(fat)!=1 or len(roots)!=1: raise SystemExit("STOP: expected one FAT and one Linux partition")
x=fat[0]
if x["start"]!=65536 or roots[0]["start"]!=196608: raise SystemExit("STOP: unexpected RAM-B disk layout")
print(x["start"]*sector,x["size"]*sector,roots[0]["start"]*sector,roots[0]["size"]*sector)
PY
read -r FAT_OFFSET FAT_SIZE ROOT_OFFSET ROOT_SIZE < "$TMP/fat-offset.txt"
mount -t vfat -o "rw,loop,offset=$FAT_OFFSET,sizelimit=$FAT_SIZE" "$OUT_IMAGE" "$TMP/fat"
MOUNTED=1
F="$TMP/fat"
for file in boot.scr mainline/stage2.scr mainline/Image mainline/sun60i-a733-orangepi-zero3w.dtb mainline/uart-diagnostic-initrd.gz; do
  [[ -f "$F/$file" && ! -L "$F/$file" ]] || fail "Missing expected FAT boot file: $file"
done
check_hash "$F/mainline/uart-diagnostic-initrd.gz" "$INITRD_SHA"
strings -a "$F/boot.scr" > "$TMP/boot-strings"
strings -a "$F/mainline/stage2.scr" > "$TMP/stage2-strings"
grep -Fq "mainline/stage2.scr" "$TMP/boot-strings" || fail "Stage1 does not load expected stage2"
grep -Fq "mainline/Image" "$TMP/stage2-strings" || fail "Stage2 does not load Image"
grep -Fq "mainline/sun60i-a733-orangepi-zero3w.dtb" "$TMP/stage2-strings" || fail "Stage2 DTB path mismatch"
grep -Fq "mainline/uart-diagnostic-initrd.gz" "$TMP/stage2-strings" || fail "Stage2 initramfs mismatch"
grep -Eq "(^|[[:space:]])booti([[:space:]]|$)" "$TMP/stage2-strings" || fail "Stage2 has no booti"
grep -Fq "0x46000000" "$TMP/boot-strings" || fail "Stage1 relocated stage2 address not confirmed"
cp "$F/boot.scr" "$TMP/stage1-original"
cp "$F/mainline/stage2.scr" "$TMP/stage2-original"
cp "$F/mainline/uart-diagnostic-initrd.gz" "$TMP/initrd-original"
echo "Replacing FAT kernel and DTB for CASE=$CASE..."
# Use a full byte write to the FAT destination, no sparse file holes.
python3 - "$KERNEL" "$F/mainline/Image" "$DTB" "$F/mainline/sun60i-a733-orangepi-zero3w.dtb" <<'PY'
import os,sys
for src,dst in ((sys.argv[1],sys.argv[2]),(sys.argv[3],sys.argv[4])):
    with open(src,"rb") as r, open(dst,"wb",buffering=0) as w:
        while True:
            b=r.read(1048576)
            if not b: break
            w.write(b)
        os.fsync(w.fileno())
PY
cmp "$KERNEL" "$F/mainline/Image" || fail "Kernel failed byte-for-byte validation"
cmp "$DTB" "$F/mainline/sun60i-a733-orangepi-zero3w.dtb" || fail "DTB failed byte-for-byte validation"
cmp "$TMP/stage1-original" "$F/boot.scr" || fail "Stage1 script changed"
cmp "$TMP/stage2-original" "$F/mainline/stage2.scr" || fail "Stage2 script changed"
cmp "$TMP/initrd-original" "$F/mainline/uart-diagnostic-initrd.gz" || fail "Initrd changed"
sync
umount "$F"
MOUNTED=0
# Verify final FAT files via read-only mount; prevent disk writes on replay.
mount -t vfat -o "ro,loop,offset=$FAT_OFFSET,sizelimit=$FAT_SIZE" "$OUT_IMAGE" "$F"
MOUNTED=1
cmp "$KERNEL" "$F/mainline/Image" || fail "Kernel changed after remount"
cmp "$DTB" "$F/mainline/sun60i-a733-orangepi-zero3w.dtb" || fail "DTB changed after remount"
cmp "$TMP/stage1-original" "$F/boot.scr" || fail "Stage1 changed after remount"
cmp "$TMP/stage2-original" "$F/mainline/stage2.scr" || fail "Stage2 changed after remount"
cmp "$TMP/initrd-original" "$F/mainline/uart-diagnostic-initrd.gz" || fail "Initrd changed after remount"
umount "$F"
MOUNTED=0
cmp -n 33554432 "$BASE_IMAGE" "$OUT_IMAGE" || fail "Vendor firmware prefix modified"
cmp -i "$ROOT_OFFSET:$ROOT_OFFSET" -n "$ROOT_SIZE" "$BASE_IMAGE" "$OUT_IMAGE" || fail "ext4 root partition modified"
check_hash "$BASE_IMAGE" "$BASE_SHA"
sha256sum "$OUT_IMAGE" > "$OUT_IMAGE.sha256"
{
  echo "Status: ASSEMBLED; NOT HARDWARE TESTED"
  echo "Base SHA256: $BASE_SHA"
  echo "Kernel SHA256: $KERNEL_SHA -> FAT /mainline/Image"
  echo "RAM-B DTB SHA256: $DTB_SHA -> FAT /mainline/sun60i-a733-orangepi-zero3w.dtb"
  echo "Initramfs SHA256: $INITRD_SHA (unchanged)"
  echo "Original Boot0/U-Boot prefix and ext4 root partition bytewise preserved"
  echo "Experiment: CASE=$CASE (A=known working kernel/DTB, B=new kernel/known working DTB)"
  echo "Boot scripts unchanged. The FAT boot may need manual U-Boot mmc 0:2 selection."
  echo "Flash only to separate microSD; capture UART; rollback to prior image on failure"
} > "$OUT_IMAGE.manifest.txt"
COMPLETE=1
echo "DONE: $OUT_IMAGE"
cat "$OUT_IMAGE.sha256"
echo "NOT HARDWARE TESTED. Use spare microSD card."

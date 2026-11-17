#!/usr/bin/env bash
# Build a new Zero 3W ARM64 diagnostic SD image. Never write to a block device.
set -euo pipefail

BASE=""; OUTPUT=""; KERNEL=""; SRC=""
while (( $# )); do
  case "$1" in
    --base) BASE="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --source) SRC="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$BASE" && -n "$OUTPUT" && -n "$KERNEL" && -n "$SRC" ]] || {
  echo "Usage: sudo bash $0 --base /path/to/m2dc.img --output /path/to/new.img --kernel /path/to/Image --source /path/to/prepared-linux-tree" >&2
  exit 2
}
[[ $EUID -eq 0 ]] || { echo "Use sudo: loop mount required" >&2; exit 2; }
for tool in losetup lsblk mount umount mountpoint mkimage cpp dtc sha256sum python3 cp cmp readlink mktemp stat sync; do
  command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 2; }
done
BASE="$(readlink -f -- "$BASE")"
KERNEL="$(readlink -f -- "$KERNEL")"
SRC="$(readlink -f -- "$SRC")"
[[ "$OUTPUT" == /* && ! -e "$OUTPUT" && ! -L "$OUTPUT" ]] || {
  echo "Output must be a NEW absolute filename, never a device" >&2; exit 2;
}
[[ -f "$BASE" && -f "$KERNEL" && -f "$SRC/Makefile" ]] || {
  echo "Missing base image, kernel or source" >&2; exit 2;
}
EXPECTED="a2e34a97113b9fff7c64112d46e6f9e131bf2ebe13d9cb1734b4fea49803e311"
[[ "$(sha256sum "$KERNEL" | awk '{print $1}')" == "$EXPECTED" ]] || {
  echo "Unexpected Image hash. Refusing assembly." >&2; exit 2;
}
[[ "$OUTPUT" != "$BASE" && "$OUTPUT" != "$KERNEL" ]] || {
  echo "Output overlaps input" >&2; exit 2;
}
[[ -f "$SRC/arch/arm64/boot/dts/allwinner/sun60i-a733.dtsi" ]] || {
  echo "Upstream A733 v3 SoC DTS missing from source" >&2; exit 2;
}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BOARD="$ROOT/dts/sun60i-a733-orangepi-zero3w-uart-only.dts"
[[ -f "$BOARD" ]] || { echo "Board DTS missing: $BOARD" >&2; exit 2; }

WORK="$(mktemp -d)"
LOOP=""; MNT=""
cleanup() {
  if [[ -n "$MNT" ]] && mountpoint -q "$MNT"; then umount "$MNT" || true; fi
  if [[ -n "$LOOP" ]]; then losetup -d "$LOOP" || true; fi
  rm -rf -- "$WORK"
}
trap cleanup EXIT
DTS_DIR="$SRC/arch/arm64/boot/dts/allwinner"
cpp -nostdinc -undef -D__DTS__ -I "$SRC/include" -I "$DTS_DIR" \
  -x assembler-with-cpp -o "$WORK/board.preprocessed.dts" "$BOARD"
dtc -I dts -O dtb -o "$WORK/board.dtb" "$WORK/board.preprocessed.dts"
# Verify firmware-managed memory, diagnostic console and no enabled MMC0.
dtc -I dtb -O dts "$WORK/board.dtb" > "$WORK/decoded.dts" 2> "$WORK/decode.warnings"
python3 - "$WORK/decoded.dts" <<'PY'
import re,sys
s=open(sys.argv[1]).read()
for pat in (r'stdout-path\s*=\s*"serial0:115200n8"',):
    if not re.search(pat,s,re.S):
        raise SystemExit("DTB policy failed: "+pat)
for node in ("mmc@4020000", "i2c@7083000"):
    m=re.search(re.escape(node)+r'\s*\{(.*?)\n\s*\};',s,re.S)
    if not m or not re.search(r'status\s*=\s*"disabled";',m.group(1)):
        raise SystemExit("Unsafe enabled/missing node: "+node)
if "x-powers,axp318w" in s: raise SystemExit("Unsafe PMIC binding")
if re.search(r"memory(?:@[0-9a-f]+)?\s*\{", s):
    raise SystemExit("Hardcoded memory node: firmware DRAM fixup must be used")
print("DIAGNOSTIC_DTB_POLICY_PASS")
PY
echo "=== INPUT HASHES ==="
sha256sum "$BASE" "$KERNEL" "$WORK/board.dtb"

# Only a new raw-file copy; never losetup on a physical device.
cp --reflink=auto --sparse=always -- "$BASE" "$OUTPUT"
LOOP="$(losetup --find --show --partscan "$OUTPUT")"
MNT="$(mktemp -d "$WORK/boot.XXXXXX")"
PART=""
while read -r node type; do
  [[ "$type" == part ]] || continue
  if mount -o ro "$node" "$MNT" 2>/dev/null; then
    if [[ -f "$MNT/boot.cmd" && -f "$MNT/mainline/stage2.cmd" &&
          -f "$MNT/mainline/tiny-uInitrd" ]]; then
      PART="$node"
      umount "$MNT"
      break
    fi
    umount "$MNT"
  fi
done < <(lsblk -nrpo NAME,TYPE "$LOOP")
[[ -n "$PART" ]] || { echo "Expected M2dc boot partition not found; no usable output" >&2; exit 3; }
mount "$PART" "$MNT"
grep -q 'mainline/stage2.scr' "$MNT/boot.cmd" || {
  echo "Unexpected first-stage script" >&2; exit 3;
}
grep -q 'booti ' "$MNT/mainline/stage2.cmd" || {
  echo "Unexpected stage-two script" >&2; exit 3;
}

# tiny-uInitrd has a U-Boot legacy 64-byte wrapper around gzip.
# booti uses RAW gzip initrd, not the wrapped uInitrd.
python3 - "$MNT/mainline/tiny-uInitrd" "$WORK/diagnostic-initrd.gz" <<'PY'
import gzip,struct,sys
raw=open(sys.argv[1],"rb").read()
if len(raw)<70 or struct.unpack(">I",raw[:4])[0]!=0x27051956:
    raise SystemExit("Unexpected legacy initrd header")
data=raw[64:]
if not data.startswith(b"\x1f\x8b"): raise SystemExit("Expected gzip at offset 64")
gzip.decompress(data)
open(sys.argv[2],"wb").write(data)
print("RAW_INITRD_VERIFIED",len(data))
PY
cp "$KERNEL" "$MNT/mainline/Image"
cp "$WORK/board.dtb" "$MNT/mainline/sun60i-a733-orangepi-zero3w.dtb"
cp "$WORK/diagnostic-initrd.gz" "$MNT/mainline/uart-diagnostic-initrd.gz"
cat > "$MNT/mainline/stage2.cmd" <<'UBOOT'
# A733 clean upstream UART diagnostic. No MMC0 or PMIC driver consumers.
# Existing stage-one boot script and frozen Boot0/BL31/SCP/U-Boot preserved.
setenv kernel_addr_r 0x41000000
setenv fdt_addr_r 0x44000000
setenv ramdisk_addr_r 0x45000000
setenv bootargs "earlycon=uart8250,mmio32,0x02500000 console=ttyS0,115200n8 keep_bootcon loglevel=8 ignore_loglevel initcall_debug rdinit=/init panic=-1"
echo "A733 clean diagnostic: raw Linux Image + firmware RAM FDT + tiny initrd"
if load ${devtype} ${devnum} ${kernel_addr_r} ${prefix}mainline/Image; then
 if load ${devtype} ${devnum} ${fdt_addr_r} ${prefix}mainline/sun60i-a733-orangepi-zero3w.dtb; then
  fdt addr ${fdt_addr_r}
  fdt resize 65536
  if load ${devtype} ${devnum} ${ramdisk_addr_r} ${prefix}mainline/uart-diagnostic-initrd.gz; then
   echo "A733 diagnostic: entering booti"
   booti ${kernel_addr_r} ${ramdisk_addr_r}:${filesize} ${fdt_addr_r}
  fi
 fi
fi
echo "A733 diagnostic failed/returned; no fallback"
while true; do sleep 5; done
UBOOT

mkimage -A arm -T script -C none -n "A733 UART diagnostic" \
  -d "$MNT/mainline/stage2.cmd" "$MNT/mainline/stage2.scr" >/dev/null
cmp "$KERNEL" "$MNT/mainline/Image"
cmp "$WORK/board.dtb" "$MNT/mainline/sun60i-a733-orangepi-zero3w.dtb"
sync
umount "$MNT"
losetup -d "$LOOP"
LOOP=""
echo "UART_DIAGNOSTIC_IMAGE_BUILT: $OUTPUT"
stat -c 'IMAGE_BYTES=%s' "$OUTPUT"
sha256sum "$OUTPUT"
echo "HDMI: firmware display state retained; Linux HDMI takeover NOT implemented"
echo "FIRMWARE_RAM: relies on frozen U-Boot FDT fixup; not prevalidated"
echo "NO_HARDWARE_BOOT_CLAIM: test on a separate SD card"

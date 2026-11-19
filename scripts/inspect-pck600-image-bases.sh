#!/usr/bin/env bash
# Read-only identification of available two-stage boot disk images.
# Does not edit, assemble, or flash anything.
set -euo pipefail
for tool in mount mountpoint umount sfdisk sha256sum dumpimage find python3 strings; do
  command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done
[[ "$(id -u)" -eq 0 ]] || { echo "Run as root" >&2; exit 1; }
SOURCES=(
  /root/opi3w-m2-work/a733-ram-ab-v1/a733-clean-uart-ram-b-v1.img
  /root/opi3w-m2-work/m2dc-final/m2dc-B-NORMALIZED.img
  /root/opi3w-m2-work/opi3w-VBI-PID1-CONTROL.img
  /root/opi3w-m2-work/opi3w-HBI-027-PID1-NORMALIZED.img
)
if (( $# > 0 )); then
  SOURCES=("$@")
fi
MNT="$(mktemp -d)"
cleanup_one() {
  if mountpoint -q "$MNT"; then umount "$MNT"; fi
}
trap 'cleanup_one; rmdir "$MNT" 2>/dev/null || :' EXIT
for IMAGE in "${SOURCES[@]}"; do
  echo
  echo "================ IMAGE ================"
  echo "$IMAGE"
  if [[ ! -f "$IMAGE" ]]; then echo "MISSING"; continue; fi
  sha256sum "$IMAGE"
  sfdisk -l "$IMAGE" | head -25
  MAP="$(sfdisk -J "$IMAGE" | python3 -c '
import json,sys
j=json.load(sys.stdin)["partitiontable"]
parts=j["partitions"]
matches=[p for p in parts if p.get("type","").lower().replace("0x","") in ("83","linux")]
if len(matches)!=1: raise SystemExit("expected exactly one Linux partition, found "+str(len(matches)))
p=matches[0]
sector=j.get("sectorsize",512)
print(str(p["start"]*sector)+" "+str(p["size"]*sector))
')" || { echo "STOP: cannot resolve exactly one Linux root partition"; continue; }
  read -r OFFSET LIMIT <<< "$MAP"
  echo "Linux partition offset=$OFFSET bytes, length=$LIMIT bytes"
  if ! mount -t ext4 -o "ro,noload,loop,offset=$OFFSET,sizelimit=$LIMIT" "$IMAGE" "$MNT"; then
    echo "STOP: ext4 mount by partition offset failed"
    cleanup_one
    continue
  fi
  echo "=== Root and /boot quick inventory ==="
  ls -ld "$MNT" "$MNT/boot" "$MNT/boot/mainline" 2>&1 || :
  if [[ -d "$MNT/boot" ]]; then
    find "$MNT/boot" -maxdepth 4 -type f \( -name "*.scr" -o -name "*.cmd" -o -name "*Image*" -o -name "*initrd*" -o -name "*ram-b*.dtb" -o -name "*uart*.dtb" \) -printf "%P %s bytes\n" 2>/dev/null | sed -n "1,100p" || :
    echo "=== U-Boot script commands ==="
    while IFS= read -r -d "" script; do
      echo "SCRIPT: ${script#"$MNT"}"
      sha256sum "$script" || :
      # Strip binary U-Boot script length prefixes rather than grepping binary.
      strings -a -n 4 "$script" | sed -n "1,110p" || :
    done < <(find "$MNT/boot" -maxdepth 5 -type f -name "*.scr" -print0 2>/dev/null)
    echo "=== Core boot payload SHA256 ==="
    find "$MNT/boot/mainline" -maxdepth 3 -type f \( -name "Image" -o -name "Image-*" -o -name "*ram-b*.dtb" -o -name "*uart*.dtb" -o -name "*initrd*.gz" \) -print0 2>/dev/null | xargs -0 -r sha256sum | sed -n "1,35p" || :
  else
    echo "NO /boot directory"
  fi
  echo "=== FAT/config partitions (read-only) ==="
  while read -r OFFSET_FAT LIMIT_FAT; do
    [[ -n "$OFFSET_FAT" ]] || continue
    FATMNT="$(mktemp -d)"
    if mount -t vfat -o "ro,loop,offset=$OFFSET_FAT,sizelimit=$LIMIT_FAT" "$IMAGE" "$FATMNT"; then
      find "$FATMNT" -maxdepth 4 -type f -printf "%P %s bytes\n" 2>/dev/null | sed -n "1,90p" || :
      while IFS= read -r -d "" file; do
        echo "FAT BOOT SCRIPT: ${file#"$FATMNT"}"
        strings -a -n 4 "$file" | sed -n "1,100p" || :
      done < <(find "$FATMNT" -maxdepth 4 -type f \( -name "*.scr" -o -name "*.cmd" \) -print0 2>/dev/null)
      umount "$FATMNT"
    else
      echo "Cannot mount FAT partition at offset $OFFSET_FAT"
    fi
    rmdir "$FATMNT"
  done < <(sfdisk -J "$IMAGE" | python3 -c '
import json,sys
j=json.load(sys.stdin)["partitiontable"]
sector=int(j.get("sectorsize",512))
for p in j.get("partitions",[]):
    if str(p.get("type","")).lower().removeprefix("0x") in ("b","c","e","6","0b","0c","0e","06"):
        print(p["start"]*sector,p["size"]*sector)
  ')
  cleanup_one
done
echo
echo "Read-only inspection complete. No image changes."

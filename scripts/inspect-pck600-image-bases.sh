#!/usr/bin/env bash
# Read-only identification of available two-stage boot disk images.
# Does not edit, assemble, or flash anything.
set -euo pipefail
for tool in mount mountpoint umount sfdisk sha256sum dumpimage find python3; do
  command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done
[[ "$(id -u)" -eq 0 ]] || { echo "Run as root" >&2; exit 1; }
SOURCES=(
  /root/opi3w-m2-work/a733-ram-ab-v1/a733-clean-uart-ram-b-v1.img
  /root/opi3w-m2-work/m2dc-final/m2dc-B-NORMALIZED.img
  /root/opi3w-m2-work/opi3w-VBI-PID1-CONTROL.img
  /root/opi3w-m2-work/opi3w-HBI-027-PID1-NORMALIZED.img
)
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
  echo "=== /boot files (names and sizes) ==="
  find "$MNT/boot" -maxdepth 4 -type f -printf '%P %s bytes\n' 2>/dev/null | head -110
  echo "=== candidate boot scripts ==="
  while IFS= read -r -d '' script; do
    echo "SCRIPT: ${script#"$MNT"}"
    echo "SHA256: $(sha256sum "$script")"
    dumpimage -T script -p 0 -o /dev/stdout "$script" 2>/dev/null |
      grep -E -i 'mainline|booti|bootm|fdt|dtb|Image|initrd|ramdisk|ext4load|load |source|console|bootargs' | head -70 || :
  done < <(find "$MNT/boot" -type f \( -name '*.scr' -o -name 'boot.scr' \) -print0 2>/dev/null)
  echo "=== RAM-B known DTB/kernel/initrd hashes if present ==="
  find "$MNT/boot" -type f \( -name 'Image*' -o -name '*ram-b*.dtb' -o -name '*diagnostic*initrd*' \) -print0 2>/dev/null |
    xargs -0 -r sha256sum | head -35
  cleanup_one
done
echo
echo "Read-only inspection complete. No image changes."

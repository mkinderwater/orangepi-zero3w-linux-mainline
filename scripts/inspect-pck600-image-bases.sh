#!/usr/bin/env bash
# Read-only identification of available two-stage boot disk images.
# Does not edit, assemble, or flash anything.
set -euo pipefail
for tool in losetup lsblk mount umount sfdisk sha256sum dumpimage find awk; do
  command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done
[[ "$(id -u)" -eq 0 ]] || { echo "Run as root" >&2; exit 1; }
SOURCES=(
  /root/opi3w-m2-work/a733-ram-ab-v1/a733-clean-uart-ram-b-v1.img
  /root/opi3w-m2-work/m2dc-final/m2dc-B-NORMALIZED.img
  /root/opi3w-m2-work/opi3w-VBI-PID1-CONTROL.img
  /root/opi3w-m2-work/opi3w-HBI-027-PID1-NORMALIZED.img
)
LOOP=""
MNT=""
cleanup_one() {
  if [[ -n "$MNT" ]] && mountpoint -q "$MNT"; then umount "$MNT"; fi
  if [[ -n "$LOOP" ]]; then losetup -d "$LOOP"; LOOP=""; fi
}
trap cleanup_one EXIT
MNT="$(mktemp -d)"
trap 'cleanup_one; rmdir "$MNT" 2>/dev/null || :' EXIT
for IMAGE in "${SOURCES[@]}"; do
  echo
  echo "================ IMAGE ================"
  echo "$IMAGE"
  if [[ ! -f "$IMAGE" ]]; then echo "MISSING"; continue; fi
  sha256sum "$IMAGE"
  LOOP="$(losetup --read-only --find --show --partscan "$IMAGE")"
  sfdisk -l "$LOOP" | head -25
  mapfile -t PARTS < <(lsblk -nr -o PATH,FSTYPE "$LOOP" | awk '$2=="ext4"{print $1}')
  if [[ "${#PARTS[@]}" -ne 1 ]]; then
    echo "STOP: ext4 root partitions not uniquely detected: ${#PARTS[@]}"
    cleanup_one
    continue
  fi
  if ! mount -t ext4 -o ro,noload "${PARTS[0]}" "$MNT"; then
    echo "STOP: cannot mount ext4 read-only"
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

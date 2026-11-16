#!/usr/bin/env bash
# Read-only WSL resource inventory: report manifests, never copy images to Git.
set -euo pipefail
DEST="${DEST:-/mnt/c/Users/mkinderwater/Downloads/opi3w-resource-inventory}"
mkdir -p "$DEST"
OUT="$DEST/resources.tsv"
printf 'resource\tkind\texists\tbytes\tsha256\n' > "$OUT"
while IFS='|' read -r id kind path; do
  [[ -n "$id" ]] || continue
  if [[ -f "$path" ]]; then
    hash="$(sha256sum "$path" | cut -d' ' -f1)"
    printf '%s\t%s\tyes\t%s\t%s\n' "$id" "$kind" "$(stat -c %s "$path")" "$hash" >> "$OUT"
  elif [[ -d "$path" ]]; then
    printf '%s\t%s\tyes\tDIR\tNA\n' "$id" "$kind" >> "$OUT"
  else
    printf '%s\t%s\tno\tNA\tNA\n' "$id" "$kind" >> "$OUT"
  fi
done <<'LIST'
stock-vendor-image|img|/mnt/c/Users/mkinderwater/Downloads/Orangepizero3w_1.0.2_debian_trixie_server_linux6.6.98/Orangepizero3w_1.0.2_debian_trixie_server_linux6.6.98.img
vendor-kernel-source|git|/root/opi3w-vendor-6698-work/kernel
vendor-control-Image|Image|/mnt/c/Users/mkinderwater/Downloads/opi3w-vendor-6698-results/control/Image
vendor-control-DTB|DTB|/mnt/c/Users/mkinderwater/Downloads/opi3w-vendor-6698-results/control/sun60i-a733-orangepi-zero3w.dtb
vendor-identity-Image|Image|/mnt/c/Users/mkinderwater/Downloads/opi3w-vendor-6698-results/identity/Image
vendor-identity-DTB|DTB|/mnt/c/Users/mkinderwater/Downloads/opi3w-vendor-6698-results/identity/sun60i-a733-orangepi-zero3w.dtb
hybrid-source|git|/root/opi3w-hybrid-build-0.2.7/linux
hybrid-vmlinux|ELF|/root/opi3w-hybrid-build-0.2.7/build/vmlinux
hybrid-Image|Image|/root/opi3w-hybrid-build-0.2.7/stage/boot/Image
hybrid-DTB|DTB|/root/opi3w-hybrid-build-0.2.7/stage/boot/sun60i-a733-orangepi-zero3w.dtb
vbi-vendor-image|img|/root/opi3w-vendor-booti-0.1.0/opi3w-VBI-vendor-A2V-booti.img
hbi-027-image|img|/root/opi3w-HBI-027-vendor-VBI-booti.img
k2-image|img|/root/opi3w-K2-027-no-initramfs.img
f1-image|img|/root/opi3w-F1-dtb-isolation.img
f2-image|img|/root/opi3w-F2-dtb-isolation.img
f1-live-DTB|DTB|/mnt/c/Users/mkinderwater/Downloads/f1-running.dtb
f1-evidence|tar.gz|/mnt/c/Users/mkinderwater/Downloads/f1-proof.tar.gz
hybrid-source-archive|dir|/root/opi3w-hybrid-sources-0.1.0
LIST
for p in /root/opi3w-vendor-6698-work/kernel /root/opi3w-hybrid-build-0.2.7/linux /root/opi3w-hybrid-sources-0.1.0/*; do
  if [[ -d "$p/.git" || -f "$p/.git" ]]; then
    echo "$p HEAD=$(git -C "$p" rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
    git -C "$p" status --short 2>/dev/null | head -30 || true
  fi
done > "$DEST/git-worktrees.txt"
echo "READ_ONLY_RESOURCE_INVENTORY_COMPLETE: $DEST"
echo "Review outputs for sensitive paths before publication. Never commit original images or private logs."

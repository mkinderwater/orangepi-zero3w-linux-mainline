#!/usr/bin/env bash
# Generate NEW lean ARM64 configuration. No old .config, no BSP inheritance.
# Not a hardware-tested Zero 3W boot configuration.
set -euo pipefail
SRC="${1:-/root/opi3w-hybrid-sources-0.1.0/linux}"
OUT="${2:-/root/opi3w-clean-618-config}"
if [[ "$OUT" != /* || "$SRC" != /* || "$OUT" == "/" ]]; then
  echo "Use absolute source and output paths" >&2; exit 2
fi
if [[ ! -f "$SRC/Makefile" || ! -x "$SRC/scripts/config" ]]; then
  echo "Missing Linux source or scripts/config: $SRC" >&2; exit 2
fi
if [[ -e "$OUT" ]]; then
  echo "Refusing to reuse an existing output directory: $OUT" >&2; exit 2
fi
mkdir -p "$OUT"
echo "=== Clean source and new config only ==="
git -C "$SRC" rev-parse HEAD 2>/dev/null > "$OUT/source-commit.txt" || echo UNKNOWN > "$OUT/source-commit.txt"
make -C "$SRC" O="$OUT" ARCH=arm64 tinyconfig
CONFIG="$OUT/.config"
SC="$SRC/scripts/config"
# Explicitly requested baseline features. No vendor or unrelated device families.
enable=(
  64BIT MMU SMP ARM64
  BLOCK ARCH_SUNXI SUNXI_CCU
  ARM64_VA_BITS_48
  OF OF_EARLY_FLATTREE
  BLK_DEV_INITRD BINFMT_ELF
  DEVTMPFS DEVTMPFS_MOUNT
  TTY SERIAL_8250 SERIAL_8250_CONSOLE SERIAL_EARLYCON
  MMC MMC_BLOCK MMC_SUNXI
  REGULATOR PINCTRL
  EXT4_FS
  PM
  PRINTK
)
# These are intentionally off; a real board integration must provide their
# upstream equivalents or be declared a release blocker, never re-enable silently.
disable=(
  AW_BSP AW_MMC AW_GPU_PM_DOMAINS AW_PM_DOMAINS
  ARM64_LPA2 ARM64_VA_BITS_52
  NET INET USB_SUPPORT USB USB_EHCI_HCD USB_OHCI_HCD
  DRM_POWERVR DRM_PANFROST DRM_NOUVEAU DRM_AMDGPU DRM_RADEON DRM_I915
  AW_PCK600_DOMAINS SUN55I_PCK600
  SOUND SND MEDIA_SUPPORT VIDEO_DEV DVB_CORE
  BT NFC CAN HAMRADIO WIMAX
  VIRTUALIZATION KVM
  INFINIBAND ISDN
  FIREWIRE IEEE802154
  DEBUG_INFO BPF_SYSCALL
  SCSI_LOWLEVEL
)
for s in "${enable[@]}"; do "$SC" --file "$CONFIG" -e "$s"; done
for s in "${disable[@]}"; do "$SC" --file "$CONFIG" -d "$s"; done
cp "$CONFIG" "$OUT/requested.config"
make -C "$SRC" O="$OUT" ARCH=arm64 olddefconfig
echo -e "symbol\trequested\teffective" > "$OUT/config-resolution.tsv"
FAIL=0
for s in "${enable[@]}"; do
  value="$(sed -n -e "s/^CONFIG_${s}=//p" -e "s/^# CONFIG_${s} is not set$/n/p" "$CONFIG" | head -1)"
  [[ -n "$value" ]] || value="ABSENT"
  printf '%s\ty\t%s\n' "$s" "$value" >> "$OUT/config-resolution.tsv"
done
for s in "${disable[@]}"; do
  value="$(sed -n -e "s/^CONFIG_${s}=//p" -e "s/^# CONFIG_${s} is not set$/n/p" "$CONFIG" | head -1)"
  [[ -n "$value" ]] || value="ABSENT"
  printf '%s\tn\t%s\n' "$s" "$value" >> "$OUT/config-resolution.tsv"
  if [[ "$value" == y || "$value" == m ]]; then echo "FORBIDDEN ENABLED: $s=$value" >&2; FAIL=1; fi
done
echo "=== Kernel configuration footprint ==="
printf 'enabled built-in: '; grep -c '^CONFIG_.*=y$' "$CONFIG" || :
printf 'enabled modules:  '; grep -c '^CONFIG_.*=m$' "$CONFIG" || :
printf 'disabled:         '; grep -c '^# CONFIG_.* is not set$' "$CONFIG" || :
echo "=== Requested options unresolved (hard gate for boot dependencies) ==="
awk -F '\t' 'NR>1 && $2=="y" && $3!="y" {print $1, $3}' "$OUT/config-resolution.tsv"
echo "=== Hard gates ==="
for s in ARM64 ARCH_SUNXI SUNXI_CCU OF DEVTMPFS BLOCK MMC MMC_BLOCK MMC_SUNXI EXT4_FS BLK_DEV_INITRD SERIAL_8250 SERIAL_8250_CONSOLE SERIAL_EARLYCON; do
 if ! grep -q "^CONFIG_${s}=y$" "$CONFIG"; then echo "MISSING REQUIRED $s" >&2; FAIL=1; fi
done
if [[ "$FAIL" -ne 0 ]]; then echo "FAIL: clean config missing a hard gate" >&2; exit 3; fi
echo "CLEAN_CONFIG_PREPARED=$CONFIG"
echo "NOT_BOOTABLE: generic SUNXI_CCU is not proof of A733-specific clock/reset support; verify A733 CCU, pinctrl, PMIC and MMC controller and DTB"
echo "Network/USB/GPU intentionally excluded from the boot-minimal profile"

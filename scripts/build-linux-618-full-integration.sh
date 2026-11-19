#!/usr/bin/env bash
# Full Linux 6.18.19 integration build using proven RAM-B config and proven A733
# source overlay. Produces kernel + modules WITHOUT modifying original output.
# Host tool: Bash. Not intended for execution on Orange Pi.
set -euo pipefail
SRC="${SRC:-/root/opi3w-m2-work/a733-try9-ramoops-v2/linux}"
CONFIG_IN="${CONFIG_IN:-/root/opi3w-m2-work/ram-b-script-fix/obj/.config}"
OUT="${OUT:-/root/opi3w-m2-work/linux-618-full-integration}"
JOBS="${JOBS:-4}"
DTB="${DTB:-/home/ram-b-clock-test/sun60i-a733-orangepi-zero3w-ram-b-26mhz-test.dtb}"
[[ -f "$SRC/Makefile" && -x "$SRC/scripts/config" ]] || { echo "Missing kernel source" >&2; exit 1; }
[[ -f "$CONFIG_IN" && -f "$DTB" ]] || { echo "Missing RAM-B config or clock-corrected DTB" >&2; exit 1; }
[[ "$OUT" != /root/opi3w-m2-work/a733-try9-ramoops-v2* ]] || { echo "Unsafe OUT" >&2; exit 1; }
command -v aarch64-linux-gnu-gcc >/dev/null || { echo "Missing cross compiler" >&2; exit 1; }
command -v sha256sum >/dev/null || exit 1
mkdir -p "$OUT/obj" "$OUT/artifacts"
cp "$CONFIG_IN" "$OUT/obj/.config"
cfg="$SRC/scripts/config"
# Keep working UART and BSP drivers from base config. Enable normal OS interfaces.
for opt in BINFMT_ELF BINFMT_SCRIPT PROC_FS SYSFS DEVTMPFS DEVTMPFS_MOUNT            TMPFS TMPFS_POSIX_ACL UNIX98_PTYS DEVPTS_FS            BLOCK PARTITION_ADVANCED MSDOS_PARTITION EFI_PARTITION            EXT4_FS FAT_FS MSDOS_FS VFAT_FS NLS_CODEPAGE_437 NLS_ISO8859_1            MMC MMC_BLOCK MMC_SUNXI I2C I2C_MV64XXX MFD_AXP20X            MFD_AXP20X_I2C REGULATOR REGULATOR_AXP20X            NET INET UNIX PACKET            USB_SUPPORT USB            SOUND SND SND_SOC            FW_LOADER; do
    "$cfg" --file "$OUT/obj/.config" -e "$opt"
done
# Enable platform capabilities only where already present in this source.
# Do not silently claim GPU/NPU/WiFi support from config names.
make -C "$SRC" O="$OUT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
for required in BINFMT_SCRIPT PROC_FS SYSFS DEVTMPFS EXT4_FS MMC MMC_BLOCK MMC_SUNXI NET INET; do
    if ! grep -qx "CONFIG_${required}=y" "$OUT/obj/.config"; then
        echo "STOP: required CONFIG_${required}=y was not resolved (dependencies/source needed)" >&2
        exit 1
    fi
done
# A FULL integration build compiles modules as well as Image.
make -C "$SRC" O="$OUT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j"$JOBS" Image modules
cp "$OUT/obj/arch/arm64/boot/Image" "$OUT/artifacts/Image-618-full-integration"
cp "$DTB" "$OUT/artifacts/sun60i-a733-orangepi-zero3w-26mhz.dtb"
cp "$OUT/obj/.config" "$OUT/artifacts/kernel.config"
make -s -C "$SRC" O="$OUT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- kernelrelease > "$OUT/artifacts/kernelrelease.txt"
sha256sum "$OUT/artifacts/"* > "$OUT/SHA256SUMS"
{
 echo "Base source: $SRC"
 echo "Base commit: $(git -C "$SRC" rev-parse HEAD)"
 echo "Input config: $CONFIG_IN"
 echo "DTB input: $DTB"
 echo "Cross compiler: $(aarch64-linux-gnu-gcc --version | head -1)"
 echo "Job count: $JOBS"
 echo "NOTE: based on local board-modified source, not a clean upstream release."
 echo "NOTE: no flashable disk image and no module rootfs installed by this build."
 echo "NOTE: device tree only exercises minimal board hardware; full BSP feature verification pending."
} > "$OUT/BUILD-MANIFEST.txt"
echo "Build ready at $OUT/artifacts"
cat "$OUT/SHA256SUMS"

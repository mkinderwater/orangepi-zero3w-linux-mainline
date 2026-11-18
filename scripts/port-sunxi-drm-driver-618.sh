#!/usr/bin/env bash
# Exact Linux 6.18 DRM API migration for vendor sunxi_drm_drv.c.
# Operates ONLY on stage4 experimental source. Does not touch RAM-B/firmware.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
FILE="$ROOT/linux/drivers/gpu/drm/sunxi_vendor/sunxi_drm_drv.c"
[[ -f "$FILE" && -d "$ROOT/obj" ]] || { echo "Missing stage4 build tree" >&2; exit 1; }
python3 - "$FILE" <<'PY'
from pathlib import Path
import re
import sys
p = Path(sys.argv[1])
s = p.read_text()
before = s
def substitute(label, pattern, replacement, flags=0):
    global s
    s, count = re.subn(pattern, replacement, s, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"STOP: {label}: expected one exact source match, got {count}")
    print(f"Updated: {label}")

# 6.18 drm_mode_config_funcs.fb_create takes an extra format-info pointer.
substitute("fb_create signature",
    r'(sunxi_drm_gem_fb_create\(struct drm_device \*dev, struct drm_file \*file,\s*)(const struct drm_mode_fb_cmd2 \*mode_cmd\)',
    r'\g<1>const struct drm_format_info *info,\n                         \g<2>')
substitute("framebuffer create argument",
    r'drm_gem_fb_create_with_funcs\(dev, file, mode_cmd,',
    'drm_gem_fb_create_with_funcs(dev, file, info, mode_cmd,')
# drm_driver::date removed from 6.18.
substitute("obsolete drm_driver date initializer",
    r'(?m)^\s*\.date\s*=\s*DRIVER_DATE\s*,\s*\n', '')
# platform_driver.remove returns void since newer kernels.
substitute("platform remove signature",
    r'static int sunxi_drm_platform_remove\(struct platform_device \*pdev\)',
    'static void sunxi_drm_platform_remove(struct platform_device *pdev)')
substitute("platform remove return",
    r'(static void sunxi_drm_platform_remove\(struct platform_device \*pdev\)\s*\{\s*component_master_del\(&pdev->dev, &sunxi_drm_ops\);)\s*return 0;',
    r'\g<1>', flags=re.S)
# MODULE_IMPORT_NS expects a quoted namespace in the current module API.
substitute("DMA_BUF module namespace",
    r'MODULE_IMPORT_NS\(DMA_BUF\);', 'MODULE_IMPORT_NS("DMA_BUF");')
if s == before:
    raise SystemExit("No source modification")
p.with_suffix(p.suffix + ".pre-618-port").write_text(before)
p.write_text(s)
PY

LOG="$ROOT/build-api-port.log"
echo "Incremental compilation of existing stage4 tree, log: $LOG"
if ! make -C "$ROOT/linux" O="$ROOT/obj" ARCH=arm64 \
    CROSS_COMPILE=aarch64-linux-gnu- -j"${JOBS:-4}" Image modules \
    >"$LOG" 2>&1; then
  echo "First compiler errors:"
  grep -n -m 35 -E 'fatal error:|error:|undefined reference|No rule to make target|implicit declaration' "$LOG" || :
  echo "End of log:"
  tail -35 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
cp "$ROOT/obj/.config" "$ROOT/artifacts/kernel.config"
sha256sum "$ROOT/artifacts/"* > "$ROOT/artifacts.sha256"
cat "$ROOT/artifacts.sha256"
echo "Compiled. HDMI and PowerVR hardware operation NOT yet validated."

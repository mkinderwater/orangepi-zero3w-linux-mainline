#!/usr/bin/env bash
# Isolate obsolete DSI-only fbdev notifications for a DSI-disabled HDMI build.
# Preserve vendor implementations; no invented FB_EVENT_BLANK definition.
set -euo pipefail
ROOT="${ROOT:-/root/opi3w-m2-work/linux-618-hdmi-stage4}"
SRC="$ROOT/linux"
FILE="$SRC/drivers/gpu/drm/sunxi_vendor/sunxi_fbdev_core.c"
CONFIG="$ROOT/obj/.config"
[[ -f "$FILE" && -f "$CONFIG" ]] || { echo "Missing stage4 source/config" >&2; exit 1; }
if grep -Eq '^CONFIG_AW_DRM_DSI=(y|m)$' "$CONFIG"; then
  echo "STOP: DSI enabled; must port framebuffer notifications rather than omit them." >&2
  exit 1
fi
python3 - "$FILE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
original=p.read_text()
marker='fb_notifier_call_chain(FB_EVENT_BLANK, &event);'
if original.count(marker)!=2:
    raise SystemExit(f"STOP: expected 2 vendor notification calls; found {original.count(marker)}")
for name in ('dsi_notify_tp_work(', 'dsi_notify_call_chain('):
    if original.count(name)!=1:
        raise SystemExit(f"STOP: unexpected use/definition count for {name}")
# DSI is disabled in this HDMI test. Keep original calls under the DSI Kconfig
# guard for a future DSI API port. Do not define a fake notifier event.
guard = '#if IS_ENABLED(CONFIG_AW_DRM_DSI)\n\t\t/* DSI notifier needs an upstream 6.18 API migration. */\n\t\t' + marker + '\n#endif'
updated=original.replace(marker,guard)
backup=p.with_name(p.name+'.pre-dsi-notifier-618')
if backup.exists():
    raise SystemExit("STOP: backup exists; refusing repeated modification")
backup.write_text(original)
p.write_text(updated)
print("DSI notification calls gated by CONFIG_AW_DRM_DSI (disabled).")
PY
LOG="$ROOT/build-dsi-notifier-618.log"
echo "Incremental build: $LOG"
if ! make -C "$SRC" O="$ROOT/obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  -j"${JOBS:-4}" Image modules >"$LOG" 2>&1; then
  echo "First compiler/linker errors:"
  grep -n -m 35 -E 'fatal error:|error:|undefined reference|No rule to make target' "$LOG" || :
  tail -25 "$LOG"
  exit 1
fi
mkdir -p "$ROOT/artifacts"
cp "$ROOT/obj/arch/arm64/boot/Image" "$ROOT/artifacts/Image-618-vendor-hdmi"
cp "$ROOT/obj/.config" "$ROOT/artifacts/kernel.config"
sha256sum "$ROOT/artifacts/"* > "$ROOT/artifacts.sha256"
cat "$ROOT/artifacts.sha256"
echo "HDMI test kernel compiled. DSI notification API port is still pending."

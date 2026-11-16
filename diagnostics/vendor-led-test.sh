#!/usr/bin/env bash
# Zero 3W: inventory status LED, optionally blink the explicitly selected LED.
# Inventory is read-only. --blink requires an identified LED name and restores
# the original trigger/brightness on exit. Run only on working vendor Linux.
set -euo pipefail
shopt -s nullglob

usage() {
  echo "Usage: $0 --inventory | --blink LED_NAME" >&2
  exit 2
}
[[ $# -ge 1 ]] || usage

inventory() {
  echo "Kernel: $(uname -r)"
  echo "Model: $(tr -d '\000' < /proc/device-tree/model 2>/dev/null || true)"
  echo "Board compatibles:"
  if [[ -r /proc/device-tree/compatible ]]; then
    tr '\000' '\n' < /proc/device-tree/compatible
  fi
  for led in /sys/class/leds/*; do
    [[ -d "$led" ]] || continue
    echo "=== $led ==="
    for field in brightness max_brightness trigger; do
      [[ -r "$led/$field" ]] && { printf '%s: ' "$field"; cat "$led/$field"; }
    done
    if [[ -e "$led/device/of_node" ]]; then
      echo "OF node: $(readlink -f "$led/device/of_node")"
    elif [[ -e "$led/of_node" ]]; then
      echo "OF node: $(readlink -f "$led/of_node")"
    fi
  done
  echo "DT LED GPIO cells (hex):"
  for f in /proc/device-tree/leds/*/gpios; do
    [[ -f "$f" ]] || continue
    printf '%s: ' "$f"
    od -An -tx1 -v "$f" | tr -d '\n'
    printf '\n'
  done
}

case "$1" in
  --inventory)
    [[ $# -eq 1 ]] || usage
    inventory
    ;;
  --blink)
    [[ $# -eq 2 ]] || usage
    [[ "$2" =~ ^[a-zA-Z0-9_.:-]+$ ]] || { echo "Invalid LED name" >&2; exit 2; }
    led="/sys/class/leds/$2"
    [[ -r "$led/trigger" && -w "$led/trigger" && -w "$led/brightness" ]] || {
      echo "LED unavailable or cannot be controlled: $led" >&2; exit 1;
    }
    [[ "$(id -u)" -eq 0 ]] || { echo "Run --blink as root" >&2; exit 1; }
    max="$(cat "$led/max_brightness")"
    [[ "$max" =~ ^[0-9]+$ && "$max" -gt 0 ]] || exit 1
    old_trigger="$(cat "$led/trigger" | grep -o '\[[^]]*\]' | tr -d '[]')"
    old_brightness="$(cat "$led/brightness")"
    restore() {
      echo 0 > "$led/brightness" || true
      if [[ -n "$old_trigger" ]]; then
        echo "$old_trigger" > "$led/trigger" || true
      fi
      if [[ "$old_trigger" == "none" ]]; then
        echo "$old_brightness" > "$led/brightness" || true
      fi
    }
    trap restore EXIT INT TERM
    echo "Testing $led: 3 short flashes; restoring trigger '$old_trigger'"
    echo none > "$led/trigger"
    for i in 1 2 3; do
      echo "$max" > "$led/brightness"
      sleep 0.4
      echo 0 > "$led/brightness"
      sleep 0.4
    done
    ;;
  *) usage ;;
esac

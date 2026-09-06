#!/bin/bash
# Apply persistent LCDWiki rotation inside a running labwc Wayland session.
# Stored angles are clockwise; Wayland output transforms are counter-clockwise.
# Touch calibration stays fixed: labwc mapToOutput="SPI-1" follows the output
# transform automatically.
set -eu

STATE=/etc/lcdwiki-rpi5-drm/rotation
ANGLE=0
[[ -r "$STATE" ]] && ANGLE="$(cat "$STATE")"

case "$ANGLE" in
  0)   TRANSFORM=normal ;;
  90)  TRANSFORM=270 ;;
  180) TRANSFORM=180 ;;
  270) TRANSFORM=90 ;;
  *)   TRANSFORM=normal ;;
esac

command -v wlr-randr >/dev/null 2>&1 || exit 0
wlr-randr --output SPI-1 --transform "$TRANSFORM" >/dev/null 2>&1 || true

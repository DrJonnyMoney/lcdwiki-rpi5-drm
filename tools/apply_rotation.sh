#!/bin/bash
# Apply the persistent LCDWiki output transform and model default scale.
set -eu
STATE_DIR=/etc/lcdwiki-rpi5-drm
STATE="$STATE_DIR/rotation"
ANGLE=0
[[ -r "$STATE" ]] && ANGLE="$(cat "$STATE")"
case "$ANGLE" in
  0)   TRANSFORM=normal ;;
  90)  TRANSFORM=270 ;;
  180) TRANSFORM=180 ;;
  270) TRANSFORM=90 ;;
  *) ANGLE=0; TRANSFORM=normal ;;
esac

if [[ "$ANGLE" == 0 || "$ANGLE" == 180 ]]; then
  SCALE_FILE="$STATE_DIR/scale-0-180"
else
  SCALE_FILE="$STATE_DIR/scale-90-270"
fi
SCALE=1.0
[[ -r "$SCALE_FILE" ]] && SCALE="$(cat "$SCALE_FILE")"

command -v wlr-randr >/dev/null 2>&1 || exit 0
wlr-randr --output SPI-1 --transform "$TRANSFORM" --scale "$SCALE" >/dev/null 2>&1 || true

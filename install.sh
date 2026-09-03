#!/bin/bash
set -euo pipefail

usage() {
  echo "Usage: sudo ./install.sh lcdwiki28|mhs3528"
  exit 1
}

[[ $# -eq 1 ]] || usage
PROFILE="$1"
case "$PROFILE" in
  lcdwiki28|mhs3528) ;;
  *) usage ;;
esac

[[ $EUID -eq 0 ]] || { echo "Run with sudo."; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
P="$ROOT/profiles/$PROFILE"
BOOTCFG="/boot/firmware/config.txt"
LABWC_GLOBAL="/etc/xdg/labwc/rc.xml"
LABWC_FRAGMENT="$P/labwc-touch.xml"

[[ -f "$BOOTCFG" ]] || { echo "Expected $BOOTCFG (Raspberry Pi OS Bookworm)."; exit 1; }
command -v dtc >/dev/null || { echo "Install: sudo apt install device-tree-compiler"; exit 1; }

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${BOOTCFG}.lcdwiki-backup-${STAMP}"
cp "$BOOTCFG" "$BACKUP"
echo "Boot config backup: $BACKUP"

BEGIN="# BEGIN lcdwiki-rpi5-drm"
END="# END lcdwiki-rpi5-drm"

# Remove any previous block managed by this project.
python3 - "$BOOTCFG" "$BEGIN" "$END" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]); begin=sys.argv[2]; end=sys.argv[3]
s=p.read_text()
while begin in s and end in s:
    a=s.index(begin); b=s.index(end,a)+len(end)
    s=s[:a]+s[b:]
p.write_text(s.rstrip()+"\n")
PY

if [[ "$PROFILE" == "lcdwiki28" ]]; then
  echo "Compiling LCDWiki 2.8-inch touch overlay..."
  dtc -@ -I dts -O dtb -o /tmp/lcdwiki-touch.dtbo "$P/touch-overlay.dts"
  install -m 0644 /tmp/lcdwiki-touch.dtbo /boot/firmware/overlays/lcdwiki-touch.dtbo

  echo "Installing ILI9341 panel firmware..."
  install -m 0644 "$P/panel.bin" /lib/firmware/panel.bin

else
  KVER="$(uname -r)"
  KBUILD="/lib/modules/$KVER/build"
  DRIVER="$P/driver"
  URL="https://raw.githubusercontent.com/raspberrypi/linux/rpi-6.12.y/drivers/gpu/drm/tiny/ili9486.c"

  [[ "$KVER" == 6.12.* ]] || {
    echo "MHS3528 profile is currently validated against Raspberry Pi kernel 6.12.x."
    echo "Running kernel: $KVER"
    exit 1
  }
  [[ -d "$KBUILD" ]] || {
    echo "Kernel headers not found. Install: sudo apt install raspberrypi-kernel-headers"
    exit 1
  }
  command -v curl >/dev/null || { echo "Install: sudo apt install curl"; exit 1; }
  command -v make >/dev/null || { echo "Install: sudo apt install build-essential"; exit 1; }

  WORK="$(mktemp -d)"
  trap 'rm -rf "$WORK"' EXIT
  cp "$DRIVER/Makefile" "$WORK/Makefile"
  cp "$DRIVER/make_mhs3528.py" "$WORK/make_mhs3528.py"

  echo "Fetching Raspberry Pi ILI9486 DRM source..."
  curl -L --fail "$URL" -o "$WORK/ili9486-upstream.c"

  echo "Generating LCDWiki MHS3528 board-specific DRM driver..."
  python3 "$WORK/make_mhs3528.py" "$WORK/ili9486-upstream.c" "$WORK/mhs3528_drm.c"

  echo "Building MHS3528 DRM module for $KVER..."
  make -C "$KBUILD" M="$WORK" modules

  MODDIR="/lib/modules/$KVER/extra"
  mkdir -p "$MODDIR"
  install -m 0644 "$WORK/mhs3528_drm.ko" "$MODDIR/mhs3528_drm.ko"
  depmod -a

  echo "Compiling MHS3528 display + touch overlay..."
  dtc -@ -I dts -O dtb -o /tmp/lcdwiki-mhs3528-native.dtbo "$P/overlay.dts"
  install -m 0644 /tmp/lcdwiki-mhs3528-native.dtbo \
    /boot/firmware/overlays/lcdwiki-mhs3528-native.dtbo
fi


# Install the validated touch mapping/calibration system-wide. Raspberry Pi OS
# normally uses /etc/xdg/labwc/rc.xml as the default labwc configuration.
# Existing per-user rc.xml files take precedence, so patch those too while
# preserving the rest of each user's configuration.
if [[ -f "$LABWC_GLOBAL" ]]; then
  LABWC_BACKUP="${LABWC_GLOBAL}.lcdwiki-backup-${STAMP}"
  cp "$LABWC_GLOBAL" "$LABWC_BACKUP"
  echo "labwc system config backup: $LABWC_BACKUP"
  python3 "$ROOT/tools/patch_labwc.py" apply "$LABWC_GLOBAL" "$LABWC_FRAGMENT"
else
  echo "Warning: $LABWC_GLOBAL not found; touch calibration was not installed globally."
fi

while IFS= read -r USER_RC; do
  [[ "$USER_RC" == "$LABWC_GLOBAL" ]] && continue
  USER_BACKUP="${USER_RC}.lcdwiki-backup-${STAMP}"
  cp "$USER_RC" "$USER_BACKUP"
  python3 "$ROOT/tools/patch_labwc.py" apply "$USER_RC" "$LABWC_FRAGMENT"
  echo "Updated existing user labwc config: $USER_RC"
done < <(find /home -mindepth 4 -maxdepth 4 -type f -path '*/.config/labwc/rc.xml' 2>/dev/null || true)

{
  echo
  echo "$BEGIN"
  cat "$P/config.txt.snippet"
  echo "$END"
} >> "$BOOTCFG"

echo
echo "Installed profile: $PROFILE"
echo "Installed validated ADS7846 touch mapping/calibration into the system labwc configuration."
if [[ "$PROFILE" == "lcdwiki28" ]]; then
  echo "Expected DRM output after reboot: SPI-1, 320x240 @ 60 Hz"
else
  echo "Expected DRM output after reboot: SPI-1, 480x320 @ ~60 Hz"
fi
echo "Reboot: sudo reboot"

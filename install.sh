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

[[ -f "$BOOTCFG" ]] || { echo "Expected $BOOTCFG (Raspberry Pi OS Bookworm)."; exit 1; }
command -v dtc >/dev/null || { echo "Install: sudo apt install device-tree-compiler"; exit 1; }

echo "Compiling touch overlay..."
dtc -@ -I dts -O dtb -o /tmp/lcdwiki-touch.dtbo "$P/touch-overlay.dts"
install -m 0644 /tmp/lcdwiki-touch.dtbo /boot/firmware/overlays/lcdwiki-touch.dtbo

echo "Installing selected panel firmware..."
install -m 0644 "$P/panel.bin" /lib/firmware/panel.bin

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${BOOTCFG}.lcdwiki-backup-${STAMP}"
cp "$BOOTCFG" "$BACKUP"
echo "Boot config backup: $BACKUP"

BEGIN="# BEGIN lcdwiki-rpi5-drm"
END="# END lcdwiki-rpi5-drm"

# Remove our previous managed block if present.
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

{
  echo
  echo "$BEGIN"
  cat "$P/config.txt.snippet"
  echo "$END"
} >> "$BOOTCFG"

echo
echo "Installed profile: $PROFILE"
if [[ "$PROFILE" == "mhs3528" ]]; then
  echo "NOTE: MHS3528 profile is derived from published wiring and Linux ILI9486 init"
  echo "      and still requires hardware validation."
fi
echo "Reboot: sudo reboot"

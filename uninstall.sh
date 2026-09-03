#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Run with sudo."; exit 1; }

BOOTCFG="/boot/firmware/config.txt"
BEGIN="# BEGIN lcdwiki-rpi5-drm"
END="# END lcdwiki-rpi5-drm"

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


# Remove only the labwc block managed by this project. Backups created during
# installation are intentionally retained.
if [[ -f /etc/xdg/labwc/rc.xml ]]; then
  python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tools/patch_labwc.py" remove /etc/xdg/labwc/rc.xml
fi
while IFS= read -r USER_RC; do
  python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tools/patch_labwc.py" remove "$USER_RC"
done < <(find /home -mindepth 4 -maxdepth 4 -type f -path '*/.config/labwc/rc.xml' 2>/dev/null || true)

rm -f /boot/firmware/overlays/lcdwiki-touch.dtbo
rm -f /boot/firmware/overlays/lcdwiki-mhs3528-native.dtbo
rm -f /lib/firmware/panel.bin

KVER="$(uname -r)"
rm -f "/lib/modules/$KVER/extra/mhs3528_drm.ko"
depmod -a || true

echo "Removed lcdwiki-rpi5-drm managed configuration and installed driver files."
echo "Reboot recommended."

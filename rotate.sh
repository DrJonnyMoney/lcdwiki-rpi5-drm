#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x /usr/local/lib/lcdwiki-rpi5-drm/rotate_display.py ]]; then
  exec python3 /usr/local/lib/lcdwiki-rpi5-drm/rotate_display.py "$@"
fi
exec python3 "$ROOT/tools/rotate_display.py" "$@"

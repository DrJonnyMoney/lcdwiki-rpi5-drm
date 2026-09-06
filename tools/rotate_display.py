#!/usr/bin/env python3
"""Persist and, when possible, immediately apply LCDWiki display rotation/scale.

Touch calibration is intentionally NOT changed here. The touchscreen remains
mapped to SPI-1 with the model's fixed, measured calibration matrix; labwc/wlroots
applies the output transform consistently to the mapped absolute input device.
"""

from __future__ import annotations

import os
import pwd
import subprocess
import sys
from pathlib import Path

STATE_DIR = Path("/etc/lcdwiki-rpi5-drm")
PROFILE_FILE = STATE_DIR / "profile"
ROTATION_FILE = STATE_DIR / "rotation"
SCALE_0_180_FILE = STATE_DIR / "scale-0-180"
SCALE_90_270_FILE = STATE_DIR / "scale-90-270"

# User-facing angles are physical rotations as observed on the LCDWiki panel.
# wlroots' quarter-turn sense is opposite to that physical convention here.
WLR_TRANSFORM = {0: "normal", 90: "270", 180: "180", 270: "90"}


def scale_for_angle(angle: int) -> str:
    path = SCALE_0_180_FILE if angle in (0, 180) else SCALE_90_270_FILE
    if path.exists():
        value = path.read_text().strip()
        try:
            float(value)
            return value
        except ValueError:
            pass
    return "1.0"


def current_user_session(angle: int, scale: str) -> bool:
    user = os.environ.get("SUDO_USER")
    if not user or user == "root":
        return False
    try:
        pw = pwd.getpwnam(user)
    except KeyError:
        return False

    runtime = Path(f"/run/user/{pw.pw_uid}")
    if not runtime.is_dir():
        return False

    sockets = [p for p in runtime.glob("wayland-*") if not p.name.endswith(".lock")]
    if not sockets:
        return False

    cmd = [
        "runuser", "-u", user, "--", "env",
        f"XDG_RUNTIME_DIR={runtime}",
        f"WAYLAND_DISPLAY={sockets[0].name}",
        "wlr-randr", "--output", "SPI-1",
        "--transform", WLR_TRANSFORM[angle],
        "--scale", scale,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def main() -> int:
    if os.geteuid() != 0:
        print("Run with sudo: sudo lcdwiki-rotate 0|90|180|270", file=sys.stderr)
        return 1
    if len(sys.argv) != 2:
        print("Usage: sudo lcdwiki-rotate 0|90|180|270", file=sys.stderr)
        return 1

    try:
        angle = int(sys.argv[1])
    except ValueError:
        angle = -1

    if angle not in WLR_TRANSFORM:
        print("Rotation must be one of: 0, 90, 180, 270", file=sys.stderr)
        return 1
    if not PROFILE_FILE.exists():
        print("LCDWiki driver state not found. Install a display profile first.", file=sys.stderr)
        return 1

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ROTATION_FILE.write_text(f"{angle}\n")

    scale = scale_for_angle(angle)
    live = current_user_session(angle, scale)

    print(f"LCDWiki rotation set to {angle} degrees.")
    print(f"LCDWiki scale set to {scale} for this orientation.")
    print("Touch calibration unchanged; it remains mapped to SPI-1.")
    if live:
        print("Display transform applied to the current Wayland session.")
    else:
        print("The persistent setting will be applied at the next labwc login/reboot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

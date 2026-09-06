#!/usr/bin/env python3
"""Persist and, when possible, immediately apply LCDWiki display rotation.

Touch calibration is intentionally NOT changed when the display rotates.
labwc's mapToOutput="SPI-1" maps the absolute touchscreen through the current
output transform, so each panel keeps one fixed base calibration matrix.
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
VALID_ANGLES = {0, 90, 180, 270}


def current_user_session(transform_angle: int) -> bool:
    """Apply the Wayland transform to the user session that invoked sudo."""
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

    sockets = sorted(
        p for p in runtime.glob("wayland-*")
        if not p.name.endswith(".lock")
    )
    if not sockets:
        return False

    transform = "normal" if transform_angle == 0 else str(transform_angle)
    cmd = [
        "runuser", "-u", user, "--", "env",
        f"XDG_RUNTIME_DIR={runtime}",
        f"WAYLAND_DISPLAY={sockets[0].name}",
        "wlr-randr", "--output", "SPI-1", "--transform", transform,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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

    if angle not in VALID_ANGLES:
        print("Rotation must be one of: 0, 90, 180, 270", file=sys.stderr)
        return 1

    if not PROFILE_FILE.exists():
        print("LCDWiki driver state not found. Install a display profile first.", file=sys.stderr)
        return 1

    # Public angles are clockwise. wl_output transform angles are CCW.
    transform_angle = (-angle) % 360

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ROTATION_FILE.write_text(f"{angle}\n")

    # Only the display output rotates. Touch stays on the profile's fixed base
    # calibration because labwc mapToOutput tracks the SPI-1 output transform.
    live = current_user_session(transform_angle)

    print(f"LCDWiki rotation set to {angle} degrees clockwise.")
    print("Touch calibration unchanged; labwc mapToOutput follows the output transform.")
    if live:
        print("Display transform applied to the current Wayland session.")
    else:
        print("The persistent setting will be applied at the next labwc login/reboot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Add/remove the lcdwiki-rpi5-drm rotation command in a labwc autostart file."""

import sys
from pathlib import Path

BEGIN = "# BEGIN lcdwiki-rpi5-drm rotation"
END = "# END lcdwiki-rpi5-drm rotation"
COMMAND = "/usr/local/bin/lcdwiki-apply-rotation &"


def remove_managed(text: str) -> str:
    while BEGIN in text and END in text:
        a = text.index(BEGIN)
        b = text.index(END, a) + len(END)
        text = text[:a].rstrip() + "\n" + text[b:].lstrip("\n")
    return text


def apply(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else ""
    text = remove_managed(text)
    block = f"{BEGIN}\n{COMMAND}\n{END}\n"
    path.write_text(text.rstrip() + "\n\n" + block if text.strip() else block)


def remove(path: Path) -> None:
    if path.exists():
        path.write_text(remove_managed(path.read_text()).rstrip() + "\n")


if len(sys.argv) != 3 or sys.argv[1] not in {"apply", "remove"}:
    raise SystemExit("Usage: patch_autostart.py apply|remove FILE")
mode, path = sys.argv[1], Path(sys.argv[2])
(apply if mode == "apply" else remove)(path)

#!/usr/bin/env python3
"""Add or remove the labwc touch block managed by lcdwiki-rpi5-drm."""

import sys
from pathlib import Path

BEGIN = "<!-- BEGIN lcdwiki-rpi5-drm touch -->"
END = "<!-- END lcdwiki-rpi5-drm touch -->"


def remove_managed(text: str) -> str:
    while BEGIN in text and END in text:
        a = text.index(BEGIN)
        b = text.index(END, a) + len(END)
        text = text[:a].rstrip() + "\n" + text[b:].lstrip("\n")
    return text


def apply(path: Path, fragment: Path) -> None:
    if not path.exists():
        raise SystemExit(f"labwc config not found: {path}")
    if not fragment.exists():
        raise SystemExit(f"Touch fragment not found: {fragment}")

    text = remove_managed(path.read_text())
    frag = fragment.read_text().rstrip()
    block = f"{BEGIN}\n{frag}\n{END}\n"

    # Raspberry Pi OS versions have used both root names. Use whichever
    # closing tag actually occurs last rather than assuming one spelling.
    positions = [
        (text.rfind("</openbox_config>"), "</openbox_config>"),
        (text.rfind("</labwc_config>"), "</labwc_config>"),
    ]
    pos, _ = max(positions, key=lambda item: item[0])
    if pos < 0:
        raise SystemExit(f"Cannot find labwc root closing tag in {path}")

    new = text[:pos].rstrip() + "\n\n" + block + "\n" + text[pos:]
    path.write_text(new)


def remove(path: Path) -> None:
    if path.exists():
        path.write_text(remove_managed(path.read_text()))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: patch_labwc.py apply FILE FRAGMENT | remove FILE")

    mode = sys.argv[1]
    if mode == "apply" and len(sys.argv) == 4:
        apply(Path(sys.argv[2]), Path(sys.argv[3]))
    elif mode == "remove" and len(sys.argv) == 3:
        remove(Path(sys.argv[2]))
    else:
        raise SystemExit("Usage: patch_labwc.py apply FILE FRAGMENT | remove FILE")


if __name__ == "__main__":
    main()

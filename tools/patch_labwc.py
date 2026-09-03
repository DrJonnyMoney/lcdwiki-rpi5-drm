#!/usr/bin/env python3
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
    text = remove_managed(path.read_text())
    frag = fragment.read_text().rstrip()
    block = f"{BEGIN}\n{frag}\n{END}\n"

    closing = None
    for tag in ("</openbox_config>", "</labwc_config>"):
        pos = text.rfind(tag)
        if pos != -1:
            closing = (pos, tag)
            break
    if closing is None:
        raise SystemExit(f"Cannot find labwc root closing tag in {path}")

    pos, _ = closing
    new = text[:pos].rstrip() + "\n\n" + block + "\n" + text[pos:]
    path.write_text(new)

def remove(path: Path) -> None:
    path.write_text(remove_managed(path.read_text()))

if len(sys.argv) not in (3, 4):
    raise SystemExit("Usage: patch_labwc.py apply FILE FRAGMENT | remove FILE")
mode = sys.argv[1]
path = Path(sys.argv[2])
if mode == "apply":
    apply(path, Path(sys.argv[3]))
elif mode == "remove":
    remove(path)
else:
    raise SystemExit(f"Unknown mode: {mode}")

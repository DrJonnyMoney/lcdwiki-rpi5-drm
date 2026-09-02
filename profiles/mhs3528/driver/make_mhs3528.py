#!/usr/bin/env python3
from pathlib import Path
import re, sys

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
s = src.read_text()

# Keep stock ili9486 module untouched.
s = s.replace("ili9486", "mhs3528")

# Remove generic conditional reset because we perform a deterministic
# hardware reset immediately before the LCDWiki vendor init sequence.
reset_pattern = re.compile(
    r'\s*ret\s*=\s*mipi_dbi_poweron_conditional_reset\(dbidev\);\s*'
    r'if\s*\(ret\s*<\s*0\)\s*goto\s+out_exit;\s*'
    r'if\s*\(ret\s*==\s*1\)\s*goto\s+out_enable;\s*',
    re.S
)
s, n = reset_pattern.subn('\n', s, count=1)
if n != 1:
    raise SystemExit("ERROR: Could not locate conditional reset block.")
s = s.replace("int ret, idx;", "int idx;", 1)

# Replace PiScreen init sequence with LCDWiki MHS35 vendor sequence.
start = 'mipi_dbi_command(dbi, ILI9486_ITFCTR1);'
end = 'msleep(100);'
a = s.find(start)
b = s.find(end, a)
if a < 0 or b < 0:
    raise SystemExit("ERROR: Could not locate upstream init sequence.")
b += len(end)

vendor = "\n".join([
    'mipi_dbi_hw_reset(dbi);',
    '\tmsleep(120);',
    '\tdev_info(dbidev->drm.dev, "MHS3528: hardware reset complete\\n");',
    '\tmipi_dbi_command(dbi, 0xF1, 0x36, 0x04, 0x00, 0x3C, 0x0F, 0x8F);',
    '\tmipi_dbi_command(dbi, 0xF2, 0x18, 0xA3, 0x12, 0x02, 0xB2, 0x12, 0xFF, 0x10, 0x00);',
    '\tmipi_dbi_command(dbi, 0xF8, 0x21, 0x04);',
    '\tmipi_dbi_command(dbi, 0xF9, 0x00, 0x08);',
    '\tmipi_dbi_command(dbi, MIPI_DCS_SET_ADDRESS_MODE, 0x08);',
    '\tmipi_dbi_command(dbi, 0xB4, 0x00);',
    '\tmipi_dbi_command(dbi, 0xC1, 0x41);',
    '\tmipi_dbi_command(dbi, 0xC5, 0x00, 0x91, 0x80, 0x00);',
    '\tmipi_dbi_command(dbi, 0xE0, 0x0F, 0x1F, 0x1C, 0x0C, 0x0F, 0x08, 0x48, 0x98, 0x37, 0x0A, 0x13, 0x04, 0x11, 0x0D, 0x00);',
    '\tmipi_dbi_command(dbi, 0xE1, 0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75, 0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00);',
    '\tmipi_dbi_command(dbi, MIPI_DCS_SET_PIXEL_FORMAT, 0x55);',
    '\tmipi_dbi_command(dbi, MIPI_DCS_EXIT_SLEEP_MODE);',
    '\tmipi_dbi_command(dbi, MIPI_DCS_SET_ADDRESS_MODE, 0x28);',
    '\tmsleep(255);',
    '\tmipi_dbi_command(dbi, MIPI_DCS_SET_DISPLAY_ON);',
    '\tmsleep(100);',
    '\tdev_info(dbidev->drm.dev, "MHS3528: vendor init complete\\n");',
])
s = s[:a] + vendor + s[b:]

# Keep LCDWiki's proven landscape MADCTL.
rot = re.compile(
    r'\tswitch\s*\(dbidev->rotation\)\s*\{.*?'
    r'\tmipi_dbi_command\(dbi,\s*MIPI_DCS_SET_ADDRESS_MODE,\s*addr_mode\);',
    re.S
)
s, n = rot.subn(
    '\taddr_mode = 0x28;\n'
    '\tmipi_dbi_command(dbi, MIPI_DCS_SET_ADDRESS_MODE, addr_mode);',
    s, count=1
)
if n != 1:
    raise SystemExit("ERROR: Could not replace rotation block.")

# Sane ~60 Hz DRM mode for labwc/wlroots.
old_mode = (
    "static const struct drm_display_mode waveshare_mode = {\n"
    "\tDRM_SIMPLE_MODE(480, 320, 73, 49),\n"
    "};"
)
new_mode = (
    "static const struct drm_display_mode waveshare_mode = {\n"
    "\t.clock = 9360,\n"
    "\t.hdisplay = 480,\n"
    "\t.hsync_start = 481,\n"
    "\t.hsync_end = 482,\n"
    "\t.htotal = 483,\n"
    "\t.vdisplay = 320,\n"
    "\t.vsync_start = 321,\n"
    "\t.vsync_end = 322,\n"
    "\t.vtotal = 323,\n"
    "\t.width_mm = 73,\n"
    "\t.height_mm = 49,\n"
    "\t.type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED,\n"
    "};"
)
if old_mode not in s:
    raise SystemExit("ERROR: Could not locate DRM_SIMPLE_MODE.")
s = s.replace(old_mode, new_mode, 1)

# Bind only to our board-specific overlay.
of_pattern = re.compile(
    r'static const struct of_device_id mhs3528_of_match\[\]\s*=\s*\{.*?\n\};',
    re.S
)
of_replacement = (
    'static const struct of_device_id mhs3528_of_match[] = {\n'
    '\t{ .compatible = "lcdwiki,mhs3528" },\n'
    '\t{},\n'
    '};'
)
s, n = of_pattern.subn(of_replacement, s, count=1)
if n != 1:
    raise SystemExit("ERROR: Could not replace OF table.")

spi_pattern = re.compile(
    r'static const struct spi_device_id mhs3528_id\[\]\s*=\s*\{.*?\n\};',
    re.S
)
spi_replacement = (
    'static const struct spi_device_id mhs3528_id[] = {\n'
    '\t{ "mhs3528", 0 },\n'
    '\t{ }\n'
    '};'
)
s, n = spi_pattern.subn(spi_replacement, s, count=1)
if n != 1:
    raise SystemExit("ERROR: Could not replace SPI table.")

s = s.replace(
    'MODULE_DESCRIPTION("Ilitek ILI9486 DRM driver");',
    'MODULE_DESCRIPTION("LCDWiki MHS3528 native DRM driver v5");'
)

dst.write_text(s)
print(f"Created {dst}")

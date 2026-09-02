# LCDWiki SPI Displays on Raspberry Pi 5 / Bookworm — Native DRM/KMS

Modern Raspberry Pi 5 / Raspberry Pi OS Bookworm support for selected LCDWiki SPI touch displays without the legacy `fbtft` + `fbturbo` + framebuffer-copy stack.

## Profiles

| Profile | LCDWiki model | LCD IC | Touch IC | Landscape mode | Status |
|---|---|---|---|---:|---|
| `lcdwiki28` | 2.8" RPi Display | ILI9341-class | ADS7846/XPT2046 | 320×240 | **Validated on hardware** |
| `mhs3528` | MHS-3.5inch RPi Display / MHS3528 | ILI9486 | XPT2046 | 480×320 | **Derived; hardware validation still required** |

The MHS3528 profile uses the same native architecture, but it is deliberately marked unverified until tested on a physical MHS3528.

## Architecture

```text
Raspberry Pi 5
  |
  +-- SPI0 CE0 --> LCD controller
  |                 |
  |                 +--> mipi-dbi-spi
  |                       +--> panel-mipi-dbi
  |                             +--> DRM/KMS --> Wayland/labwc
  |
  +-- SPI0 CE1 --> XPT2046 / ADS7846 touch
                    |
                    +--> Linux input --> libinput --> labwc
```

This is a native Linux graphics/input solution. No framebuffer copier is required.

## Why not LCD-show?

LCDWiki's current `MHS35-show` still installs its own overlay and adds legacy framebuffer/HDMI/Xorg-related configuration. The LCD-show project itself now has reports describing structural incompatibilities between the legacy `fbtft` path and modern KMS configurations.

This project instead leaves the normal Pi 5 DRM/KMS/Wayland stack in place.

## Requirements

Raspberry Pi OS Bookworm on Raspberry Pi 5, with the stock:

- `panel-mipi-dbi` kernel driver
- `mipi-dbi-spi` Raspberry Pi overlay

Check:

```bash
modinfo panel-mipi-dbi
dtoverlay -h mipi-dbi-spi
```

Install build support:

```bash
sudo apt update
sudo apt install -y device-tree-compiler
```

## Install 2.8"

```bash
sudo ./install.sh lcdwiki28
sudo reboot
```

Expected:

```bash
wlr-randr
```

```text
SPI-1
  320x240 px, 60.000000 Hz
```

## Install MHS3528 3.5"

```bash
sudo ./install.sh mhs3528
sudo reboot
```

The intended landscape configuration is:

```text
480×320
ILI9486
LCD CS = SPI0 CE0 / GPIO8
Touch CS = SPI0 CE1 / GPIO7
LCD D/C = GPIO24
LCD RESET = GPIO25
Touch IRQ = GPIO17
```

These GPIO assignments follow LCDWiki's published MHS3528 pin table.

After boot check:

```bash
dmesg | grep -Ei "panel|mipi|spi|ads7846|touchscreen|drm"
wlr-randr
```

The target is a connected `SPI-1` output at 480×320 and a detected `ADS7846 Touchscreen`.

### MHS3528 panel firmware

`profiles/mhs3528/panel.txt` is based on the Raspberry Pi Linux `fb_ili9486` PiScreen initialization sequence:

- RGB565 (`0x3A 0x55`)
- ILI9486 power/VCOM/gamma settings
- landscape MADCTL (`0x36 0x28`)

The profile uses `panel-mipi-dbi` to send those commands and drive pixel data through DRM/KMS. Because this exact combination has not yet been tested on the user's MHS3528 hardware, treat the profile as a candidate native configuration rather than a confirmed one.

## Touch mapping

Map touch to the physical SPI output in:

```text
~/.config/labwc/rc.xml
```

Example:

```xml
<?xml version="1.0"?>
<labwc_config>
    <touch deviceName="ADS7846 Touchscreen"
           mapToOutput="SPI-1"
           mouseEmulation="yes" />
</labwc_config>
```

For the validated 2.8" unit, a fine calibration matrix was:

```xml
<libinput>
    <device category="ADS7846 Touchscreen">
        <calibrationMatrix>1.150 0 -0.111 0 1.137 -0.060</calibrationMatrix>
    </device>
</libinput>
```

Do not assume those calibration values are correct for a different panel.

Collect a fresh 3×3 calibration using:

```bash
python3 tools/touch_calibrate_grid.py
```

## Desktop scaling

Small panels benefit from output scaling. Example for the 2.8":

```bash
wlr-randr --output SPI-1 --scale 0.67
```

The MHS3528's 480×320 landscape area should need less aggressive scaling.

## SPI speed

Profiles start at 32 MHz. This is deliberately conservative.

The MHS3528 product page claims the hardware accepts SPI input up to 125 MHz, but that is **not** a recommendation to run Linux at 125 MHz immediately. Validate 32 MHz first, then test 48/64 MHz while watching for corruption or instability.

## Repository layout

```text
profiles/
  lcdwiki28/
    panel.txt
    panel.bin
    touch-overlay.dts
    config.txt.snippet
  mhs3528/
    panel.txt
    panel.bin
    touch-overlay.dts
    config.txt.snippet
tools/
  touch_calibrate_grid.py
docs/
  TECHNICAL_REPORT.md
install.sh
uninstall.sh
```

## Uninstall

```bash
sudo ./uninstall.sh
sudo reboot
```

The installer backs up `/boot/firmware/config.txt` before changing its managed block.

## Important

Do not simultaneously load the old LCDWiki `tft9341`/`mhs35` framebuffer overlays and these `mipi-dbi-spi` profiles.

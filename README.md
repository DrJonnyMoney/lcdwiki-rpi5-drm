# LCDWiki SPI Displays on Raspberry Pi 5 / Bookworm — Native DRM/KMS

Modern Raspberry Pi 5 / Raspberry Pi OS Bookworm support for selected LCDWiki SPI touch displays without LCDWiki's legacy `fbtft` + `fbturbo` + framebuffer-copy/Xorg installation stack.

Both profiles below have now been **validated on physical hardware**.

## Supported displays

| Profile | LCDWiki model | LCD controller | Touch controller | Landscape mode | Status |
|---|---|---|---|---:|---|
| `lcdwiki28` | 2.8" RPi Display | ILI9341-class | ADS7846/XPT2046 | 320×240 | **Validated** |
| `mhs3528` | MHS-3.5inch RPi Display / MHS3528 | ILI9486 | XPT2046 | 480×320 | **Validated** |

LCDWiki product pages:

- 2.8-inch: <https://www.lcdwiki.com/2.8inch_RPi_Display>
- MHS3528 3.5-inch: <https://www.lcdwiki.com/MHS-3.5inch_RPi_Display>

## What this project does

The goal is to keep the normal Raspberry Pi 5 graphics stack intact:

```text
DRM/KMS -> Wayland/labwc -> physical SPI display
```

Touch remains a normal Linux input device:

```text
XPT2046/ADS7846 -> Linux input -> libinput -> labwc
```

No framebuffer copier is required and the normal Wayland desktop can be mirrored by a VNC server that mirrors the active session.

The two displays need different native Linux approaches:

```text
LCDWiki 2.8"
  SPI0 CE0 -> mipi-dbi-spi -> panel-mipi-dbi -> DRM/KMS
  SPI0 CE1 -> ads7846 -> libinput

LCDWiki MHS3528 3.5"
  SPI0 CE0 -> custom board-specific ILI9486 DRM module -> DRM/KMS
  SPI0 CE1 -> ads7846 -> libinput
```

The MHS3528 cannot simply use the same `panel-mipi-dbi` profile as the 2.8-inch unit. Its working LCDWiki configuration uses ILI9486-specific 16-bit register semantics, so this repository builds a small board-specific DRM module from Raspberry Pi's native ILI9486 driver and applies the LCDWiki MHS3528 initialization sequence.

## Why not run LCDWiki `LCD-show` / `MHS35-show` directly?

LCDWiki's scripts were designed around the older framebuffer/Xorg display stack. They install or modify components such as `fbtft`, `fbturbo`, evdev/Xorg configuration, framebuffer-copy behaviour and boot configuration.

That is unnecessary for a current Raspberry Pi 5 Bookworm Wayland installation and can interfere with the standard KMS desktop.

This project uses LCDWiki's published hardware information and known-good initialization where useful, while leaving the modern Raspberry Pi graphics stack in place.

# Requirements

Tested on:

- Raspberry Pi 5
- Raspberry Pi OS Bookworm
- Raspberry Pi kernel `6.12.x`
- Wayland/labwc

Install the basic build tools:

```bash
sudo apt update
sudo apt install -y device-tree-compiler
```

For the MHS3528 profile also install:

```bash
sudo apt install -y raspberrypi-kernel-headers build-essential curl
```

The current MHS3528 installer intentionally checks for a `6.12.x` kernel because that is the kernel series on which the custom module was validated.

# Installation

Clone the repository:

```bash
git clone https://github.com/DrJonnyMoney/lcdwiki-rpi5-drm.git
cd lcdwiki-rpi5-drm
chmod +x install.sh uninstall.sh tools/touch_calibrate_grid.py
```

## LCDWiki 2.8-inch

```bash
sudo ./install.sh lcdwiki28
sudo reboot
```

Expected output:

```bash
wlr-randr
```

```text
SPI-1
  320x240 px, 60.000000 Hz
```

The 2.8-inch profile uses:

- LCD CS: SPI0 CE0 / GPIO8
- touch CS: SPI0 CE1 / GPIO7
- LCD D/C: GPIO22
- LCD reset: GPIO27
- touch IRQ: GPIO17

## LCDWiki MHS3528 3.5-inch

```bash
sudo ./install.sh mhs3528
sudo reboot
```

Expected output:

```bash
wlr-randr
```

```text
SPI-1
  Physical size: 73x49 mm
  480x320 px, ~60 Hz
```

Expected kernel messages include:

```text
mhs3528 ... MHS3528: hardware reset complete
mhs3528 ... MHS3528: vendor init complete
... fb0: mhs3528drmfb frame buffer device
ads7846 spi0.1: touchscreen
```

Useful check:

```bash
dmesg | grep -Ei "MHS3528|mhs3528|ads7846|spi0.0|spi0.1|drm"
```

MHS3528 wiring used by this profile:

- LCD CS: SPI0 CE0 / GPIO8
- touch CS: SPI0 CE1 / GPIO7
- LCD D/C / RS: GPIO24
- LCD reset: GPIO25
- touch IRQ: GPIO17
- physical panel resolution: 320×480
- DRM landscape mode: 480×320

## Important MHS3528 reset detail

A critical part of the working native DRM configuration is:

```dts
reset-gpios = <&gpio 25 0>;
```

Do **not** copy the legacy LCDWiki overlay's reset GPIO flag literally into a modern `mipi-dbi`/gpiod driver.

The legacy overlay uses a different GPIO convention. With modern gpiod semantics, using the wrong polarity causes the DRM reset helper to finish with the physical reset line low, leaving the ILI9486 held in reset. The driver can then appear to initialize successfully in `dmesg` while the LCD remains completely blank.

With flag `0`, `mipi_dbi_hw_reset()` produces the required physical reset sequence:

```text
RESET low -> delay -> RESET high
```

This was the final issue preventing the native MHS3528 DRM driver from displaying an image.

# Touchscreen

Both validated units use the Linux `ads7846` driver for their XPT2046-compatible resistive touchscreen.

Confirm detection with:

```bash
libinput list-devices | grep -A15 -i ADS7846
```

You should see a device similar to:

```text
Device:           ADS7846 Touchscreen
Capabilities:     touch
```

The Device Tree profiles handle the coarse touch orientation. Fine calibration is applied in labwc.

## labwc touch mapping

Edit:

```text
~/.config/labwc/rc.xml
```

### Validated 2.8-inch configuration

```xml
<?xml version="1.0"?>

<labwc_config>
    <touch deviceName="ADS7846 Touchscreen"
           mapToOutput="SPI-1"
           mouseEmulation="yes" />

    <libinput>
        <device category="ADS7846 Touchscreen">
            <calibrationMatrix>1.150 0 -0.111 0 1.137 -0.060</calibrationMatrix>
        </device>
    </libinput>
</labwc_config>
```

### Validated MHS3528 3.5-inch configuration

```xml
<?xml version="1.0"?>

<labwc_config>
    <touch deviceName="ADS7846 Touchscreen"
           mapToOutput="SPI-1"
           mouseEmulation="yes" />

    <libinput>
        <device category="ADS7846 Touchscreen">
            <calibrationMatrix>1.115 0 -0.052 0 1.106 -0.035</calibrationMatrix>
        </device>
    </libinput>
</labwc_config>
```

These matrices were measured on the two physical test units. Resistive panels vary, so another unit may still benefit from its own calibration.

## Recalibrating another panel

Run:

```bash
python3 tools/touch_calibrate_grid.py
```

Use:

- `320` × `240` for the 2.8-inch display
- `480` × `320` for the MHS3528

Tap the nine targets carefully with a stylus and use the resulting raw coordinates to derive a new libinput affine matrix.

# Desktop scaling

The 2.8-inch desktop is very small at native logical scale. A useful starting point is:

```bash
wlr-randr --output SPI-1 --scale 0.67
```

The MHS3528 has more usable desktop area at 480×320 and may not require as aggressive a scale reduction.

# SPI speed

Both profiles start conservatively at 32 MHz.

LCDWiki advertises the MHS3528 as a high-speed SPI display, and its legacy overlay uses a much higher SPI clock. The physical test panel also worked with LCDWiki's legacy `fb_ili9486` driver at 115 MHz.

The native DRM profile deliberately remains at 32 MHz for reliability. Increase it only after confirming a stable display with the default configuration.

# How the MHS3528 driver is built

The repository does **not** replace Raspberry Pi's stock `ili9486.ko`.

During installation, the MHS3528 profile:

1. fetches Raspberry Pi's `rpi-6.12.y` native `drivers/gpu/drm/tiny/ili9486.c` source;
2. creates a separate `mhs3528_drm.c` driver;
3. substitutes LCDWiki's MHS3528 initialization sequence;
4. uses the corrected hardware reset behaviour;
5. presents a sane 480×320 ~60 Hz DRM mode to Wayland;
6. binds only to `compatible = "lcdwiki,mhs3528"`;
7. installs the resulting module as:

```text
/lib/modules/$(uname -r)/extra/mhs3528_drm.ko
```

This keeps the stock Raspberry Pi ILI9486 module untouched.

# Repository layout

```text
profiles/
  lcdwiki28/
    panel.txt
    panel.bin
    touch-overlay.dts
    config.txt.snippet

  mhs3528/
    overlay.dts
    config.txt.snippet
    driver/
      Makefile
      make_mhs3528.py

tools/
  touch_calibrate_grid.py

docs/
  TECHNICAL_REPORT.md

install.sh
uninstall.sh
```

# Uninstall

```bash
sudo ./uninstall.sh
sudo reboot
```

The installer backs up `/boot/firmware/config.txt` before modifying its managed block.

# Important

Do not load the old LCDWiki `LCD28-show`, `MHS35-show`, `tft9341`, `mhs35` or other legacy framebuffer display overlays at the same time as these profiles.

For the MHS3528 in particular, the working native profile is:

```ini
dtparam=spi=on
dtoverlay=lcdwiki-mhs3528-native
```

and **not** the old:

```ini
dtoverlay=mhs35:rotate=90
```

The latter is useful as a legacy hardware diagnostic, but it does not provide the native Wayland/KMS solution this repository is intended to deliver.

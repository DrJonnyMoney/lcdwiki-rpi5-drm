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

The MHS3528 cannot use the same generic `panel-mipi-dbi` transport as the 2.8-inch unit. A clean hardware retest with the corrected reset polarity showed that `panel-mipi-dbi` binds successfully and exposes a valid `SPI-1` output at 480×320 @ 60 Hz, but the physical LCD remains white. The PiScreen-style ILI9486 hardware uses board-specific 16-bit command/register transport, so this repository builds a small board-specific DRM module from Raspberry Pi's native ILI9486 driver and applies the LCDWiki MHS3528 initialization sequence.

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
sudo apt install -y device-tree-compiler wlr-randr
```

For the MHS3528 profile also install:

```bash
sudo apt install -y raspberrypi-kernel-headers build-essential curl
```

The current MHS3528 installer intentionally checks for a `6.12.x` kernel because that is the kernel series on which the custom module was validated.

## Optional touch verification and recalibration tools

For touchscreen testing and calibration, install:

```bash
sudo apt install -y evtest python3-pygame python3-evdev
```

These packages are only needed during setup, troubleshooting or calibration; they are not required for normal display or touchscreen operation once configuration is complete.

- `evtest` displays the raw ADS7846/XPT2046 touch events and is useful for checking axis direction and coordinate range.
- `python3-pygame` is used by the 3×3 touchscreen calibration utility.
- `python3-evdev` allows the calibration utility to read the Linux touchscreen input device directly.

# Installation

Clone the repository:

```bash
git clone https://github.com/DrJonnyMoney/lcdwiki-rpi5-drm.git
cd lcdwiki-rpi5-drm
chmod +x install.sh uninstall.sh rotate.sh tools/touch_calibrate_grid.py tools/button_test.py
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
- KEY1: physical pin 12 / GPIO18
- KEY2: physical pin 16 / GPIO23
- KEY3: physical pin 18 / GPIO24

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

Both validated units use the Linux `ads7846` driver for their XPT2046-compatible resistive touchscreen. The installer now applies the measured touch mapping and calibration automatically.

The default is installed system-wide in:

```text
/etc/xdg/labwc/rc.xml
```

This means users who rely on the normal Raspberry Pi OS labwc configuration inherit a working touchscreen automatically. labwc searches a user's own `~/.config/labwc/rc.xml` before the system configuration, so the installer also updates any existing per-user labwc files it finds under `/home` while preserving their other settings. A user can still change or remove the LCDWiki block later as a personal override.

The installer backs up every labwc file before changing it and marks its additions with:

```text
<!-- BEGIN lcdwiki-rpi5-drm touch -->
...
<!-- END lcdwiki-rpi5-drm touch -->
```

Confirm touch detection with:

```bash
libinput list-devices | grep -A15 -i ADS7846
```

You should see a device similar to:

```text
Device:           ADS7846 Touchscreen
Capabilities:     touch
```

The Device Tree profiles handle coarse touch orientation. labwc/libinput applies the validated fine calibration.

## Installed calibration defaults

2.8-inch:

```text
1.150 0 -0.111 0 1.137 -0.060
```

MHS3528 3.5-inch:

```text
1.115 0 -0.052 0 1.106 -0.035
```

These matrices were measured on the two physical test units. They are used as the normal model defaults; recalibration is only needed if another unit is noticeably offset.

## Recalibrating another panel

Run:

```bash
python3 tools/touch_calibrate_grid.py
```

Use:

- `320` × `240` for the 2.8-inch display
- `480` × `320` for the MHS3528

Tap the nine targets carefully with a stylus and use the resulting raw coordinates to derive a replacement libinput affine matrix.


# Screen rotation

Rotation is a supported feature for **both** display profiles. The installer adds a system command that rotates the DRM output while leaving the validated touchscreen calibration matrix unchanged.

Use:

```bash
sudo lcdwiki-rotate 0
sudo lcdwiki-rotate 90
sudo lcdwiki-rotate 180
sudo lcdwiki-rotate 270
```

The command angles are **physical panel rotations**. The helper translates them to the corresponding wlroots transform internally, so `90` and `270` match the direction observed on the actual LCDWiki panel.

The angles are clockwise relative to the repository's default orientation. `0` restores the default orientation.

The command keeps three things together:

```text
wlr-randr output transform
          +
fixed validated libinput calibration matrix
          +
orientation-appropriate desktop scale
```

The touchscreen remains mapped to `SPI-1`. On the tested Raspberry Pi OS/labwc setup, the output transform carries the mapped absolute touchscreen with the display, so the model-specific calibration matrix must remain unchanged when the screen is rotated.

The selected angle is stored in:

```text
/etc/lcdwiki-rpi5-drm/rotation
```

and the project’s system-wide labwc autostart applies it at every desktop login. On the Raspberry Pi OS Bookworm configuration tested for this project, this system-wide rotation persists even when a user has their own `~/.config/labwc/autostart`. You therefore do **not** need to copy the rotation helper into your personal autostart file. If the command is run from an active Wayland desktop using `sudo`, it also attempts to apply the new display transform immediately and reload labwc; otherwise it takes effect on the next login/reboot.

For the validated 2.8-inch profile, rotation also selects a tested desktop scale automatically:

| Orientation | Rotation values | Default scale |
|---|---|---:|
| Rotation | Default scale |
|---|---:|
| `0` / `180` | `0.67` |
| `90` / `270` | `0.56` |

These defaults keep the Raspberry Pi taskbar usable on the 320x240 panel. The MHS3528 profile remains at scale `1.0` by default because its larger 480x320 workspace does not need the same reduction.

# 2.8-inch hardware buttons

The LCDWiki MPI2801 board has three physical buttons on its right-hand side. LCDWiki documents them as KEY1, KEY2 and KEY3 on physical header pins 12, 16 and 18 respectively. This project exposes them through Linux's native `gpio-keys` driver:

| Board button | Physical pin | GPIO | Linux key event |
|---|---:|---:|---|
| KEY1 | 12 | GPIO18 | `KEY_PROG1` |
| KEY2 | 16 | GPIO23 | `KEY_PROG2` |
| KEY3 | 18 | GPIO24 | `KEY_PROG3` |

The driver deliberately does **not** assign actions such as shutdown, back or exit. They are general-purpose buttons and are exposed as ordinary Linux input events so applications can decide what they mean.

After installing the `lcdwiki28` profile, verify them with:

```bash
sudo evtest
```

or, if `python3-evdev` is installed:

```bash
python3 tools/button_test.py
```

An application can listen for `KEY_PROG1`, `KEY_PROG2` and `KEY_PROG3` without accessing GPIO directly. This keeps button handling in the normal Linux input stack, alongside the touchscreen.

# Desktop scaling

Desktop scaling is now part of the display profile rather than a manual post-install step.

For the 2.8-inch display the validated defaults are:

```text
0 / 180 degrees -> 0.67
90 / 270 degrees -> 0.56
```

The project stores these under:

```text
/etc/lcdwiki-rpi5-drm/scale-0-180
/etc/lcdwiki-rpi5-drm/scale-90-270
```

and `lcdwiki-apply-rotation` applies the appropriate scale together with the saved display rotation at login. Running, for example:

```bash
sudo lcdwiki-rotate 90
```

therefore changes the image orientation, touchscreen sense **and** desktop scale as one operation.

If you previously added a manual line such as:

```bash
wlr-randr --output SPI-1 --scale 0.67
```

to `~/.config/labwc/autostart`, it is no longer needed and can be removed. The installer preserves unrelated user autostart commands rather than deleting them automatically.

The MHS3528 uses scale `1.0` by default in all orientations.

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
    overlay.dts
    labwc-touch.xml
    config.txt.snippet

  mhs3528/
    overlay.dts
    labwc-touch.xml
    config.txt.snippet
    driver/
      Makefile
      make_mhs3528.py

tools/
  patch_labwc.py
  patch_autostart.py
  rotate_display.py
  apply_rotation.sh
  touch_calibrate_grid.py
  button_test.py

rotate.sh

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

The installer backs up `/boot/firmware/config.txt` before modifying its managed block. It also removes the managed labwc touch/rotation configuration, installed rotation helpers, display overlays/firmware and any installed MHS3528 module copies during uninstall. Backup files are retained as a safety net rather than restored automatically.

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

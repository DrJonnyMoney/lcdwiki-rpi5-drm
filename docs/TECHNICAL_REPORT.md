# Technical Report

## Purpose

This project modernises selected LCDWiki SPI touch displays for Raspberry Pi 5 / Raspberry Pi OS Bookworm by retaining the normal Linux DRM/KMS + Wayland graphics stack instead of installing LCDWiki's legacy framebuffer/Xorg environment.

Two physical displays have been validated:

- LCDWiki 2.8-inch RPi Display, ILI9341-class + ADS7846/XPT2046;
- LCDWiki MHS-3.5inch RPi Display (MHS3528), ILI9486 + XPT2046.

## 2.8-inch development path

The vendor framebuffer overlay first confirmed communication with both hardware devices. A native attempt using the dedicated tiny ILI9341 DRM driver then created a DRM connector, but exposed a malformed mode near 0.013 Hz. The desktop therefore appeared to update extremely slowly even though SPI communication itself was functional.

Moving the LCD to Raspberry Pi's `mipi-dbi-spi` overlay and Linux `panel-mipi-dbi` produced a normal userspace mode:

```text
SPI-1
320x240 @ 60 Hz
```

Touch remained independent on SPI0 CE1 using the stock `ads7846` input driver. Device Tree handles axis orientation; labwc/libinput applies the final affine calibration.

Validated fine calibration:

```text
1.143978 0.002659 -0.108423 -0.024877 1.147078 -0.057139
```

## MHS3528 hardware

The tested LCDWiki MHS3528 uses:

- ILI9486 LCD controller;
- XPT2046 touch controller;
- physical resolution 320×480;
- landscape DRM mode 480×320;
- LCD CS on SPI0 CE0 / GPIO8;
- touch CS on SPI0 CE1 / GPIO7;
- LCD D/C on GPIO24;
- LCD reset on GPIO25;
- touch IRQ on GPIO17.

LCDWiki's legacy MHS35 overlay configures the display as an ILI9486 with 8-bit SPI bus transfers and 16-bit register semantics. The legacy `fb_ili9486` path successfully drove the physical display and therefore served as the hardware reference while developing the native DRM profile.

## Why generic panel-mipi-dbi was not sufficient for MHS3528

A generic `panel-mipi-dbi` profile could create a valid `SPI-1` DRM output at 480×320 and detect touch, but the physical panel remained blank.

The MHS3528 therefore uses a board-specific native DRM module derived from Raspberry Pi's tiny ILI9486 driver. The module preserves the controller-specific command transport while substituting LCDWiki's known-good initialization sequence and a sane userspace DRM mode.

The module is separate from the kernel's stock `ili9486.ko` and binds only to:

```text
lcdwiki,mhs3528
```

## Critical reset-polarity finding

The final fault preventing the board-specific MHS3528 DRM module from driving the physical panel was reset GPIO polarity. This was distinct from the generic `panel-mipi-dbi` transport limitation described above.

LCDWiki's legacy Device Tree overlay represents reset polarity using conventions from the older framebuffer driver. Copying its flag directly into a modern gpiod/mipi-dbi driver caused the helper to end with the physical reset line low.

That produced a deceptive state:

```text
custom DRM driver bound
vendor init commands executed
DRM framebuffer created
480x320 @ ~60 Hz exposed to Wayland
physical LCD remained blank
```

The working modern property is:

```dts
reset-gpios = <&gpio 25 0>;
```

With this setting, `mipi_dbi_hw_reset()` produces the required physical transition:

```text
RESET low -> RESET high
```

and leaves the controller released from reset.

After this change the board-specific MHS3528 DRM module displayed the Wayland desktop correctly.

A later clean retest then applied the corrected reset polarity to generic `panel-mipi-dbi`. That generic driver successfully bound, created `fb0`, and exposed `SPI-1` at 480×320 @ 60 Hz, yet the physical panel remained white. This separated the two issues experimentally: correct reset polarity is necessary, but generic MIPI-DBI SPI transport is still insufficient for this MHS3528 hardware.

## Validated MHS3528 result

The working system reports:

```text
[drm] Initialized mhs3528 1.0.0 for spi0.0
MHS3528: hardware reset complete
MHS3528: vendor init complete
[drm] fb0: mhs3528drmfb frame buffer device
```

and:

```text
SPI-1
Physical size: 73x49 mm
480x320 px, 59.997002 Hz
```

Touch is detected as:

```text
ADS7846 Touchscreen
```

Device Tree applies:

```dts
touchscreen-swapped-x-y;
touchscreen-inverted-y;
```

Validated labwc/libinput fine calibration:

```text
1.115 0 -0.052 0 1.106 -0.035
```

The installer applies the model-specific calibration as a system-wide labwc default in `/etc/xdg/labwc/rc.xml` and also patches existing per-user labwc configurations that would otherwise take precedence.

Reinstallation reasserts that fixed base calibration and removes obsolete per-rotation matrix state from earlier development builds. Rotation itself never rewrites the touch matrix.

## Architecture

### 2.8-inch

```text
SPI0 CE0
  -> mipi-dbi-spi
  -> panel-mipi-dbi
  -> DRM/KMS
  -> Wayland/labwc

SPI0 CE1
  -> ADS7846/XPT2046
  -> Linux input
  -> libinput
  -> labwc
```

### MHS3528

```text
SPI0 CE0
  -> lcdwiki,mhs3528
  -> board-specific native ILI9486 DRM module
  -> DRM/KMS
  -> Wayland/labwc

SPI0 CE1
  -> ADS7846/XPT2046
  -> Linux input
  -> libinput
  -> labwc
```

## Practical outcome

Both displays now operate without replacing the Raspberry Pi 5's modern desktop stack. This preserves normal Wayland behaviour, native DRM output enumeration and session mirroring while still supporting the resistive touchscreen.

The project also demonstrates an important migration lesson for older Raspberry Pi display overlays: GPIO polarity flags from legacy drivers must not be assumed to have identical semantics when ported to modern descriptor-based GPIO APIs.

## Rotation and board controls

The initial display bring-up solved only the fixed-orientation graphics and touch path. A reusable board-support package also needs to expose the remaining hardware and keep display transforms coherent with absolute touch coordinates.

Rotation is implemented only at the compositor/output layer with `wlr-randr`. The touchscreen keeps its measured base calibration matrix at every orientation because labwc maps the ADS7846 device to `SPI-1` with `mapToOutput`, which follows the output transform automatically. Empirical testing on the 2.8-inch panel confirmed that additionally rotating the libinput matrix causes a second, incorrect touch rotation. Supported rotations are 0, 90, 180 and 270 degrees clockwise. The chosen angle is stored system-wide and re-applied from labwc autostart. The same arrangement is used for both the ILI9341 `panel-mipi-dbi` profile and the board-specific MHS3528 ILI9486 DRM profile.

The LCDWiki MPI2801 2.8-inch board also provides three side buttons. LCDWiki maps these to physical pins 12, 16 and 18, which correspond to GPIO18, GPIO23 and GPIO24. The profile now describes them using the upstream `gpio-keys` driver as `KEY_PROG1`, `KEY_PROG2` and `KEY_PROG3`. No application action is assigned by the driver; the keys are exposed through the standard Linux input subsystem for applications or desktop bindings to consume.

# Technical Report

## Purpose

This project modernises LCDWiki SPI displays for Raspberry Pi 5 / Raspberry Pi OS Bookworm by using the normal Linux DRM/KMS stack rather than replacing it with a legacy framebuffer/Xorg configuration.

## Validated 2.8-inch path

The 2.8-inch ILI9341-class + ADS7846/XPT2046 board was developed and tested interactively.

The vendor overlay first established that the Pi 5 kernel could communicate with both hardware devices:

```text
fb_ili9340 ... 320x240
ads7846 spi0.1: touchscreen
```

A DRM attempt with the dedicated tiny ILI9341 driver then created `SPI-1`, but exposed an unusable mode near 0.013 Hz. `modetest` confirmed the mode timing rather than Bluetooth/input handling was responsible for multi-second-to-minute apparent UI freezes.

Moving the panel to Raspberry Pi's `mipi-dbi-spi` overlay and Linux `panel-mipi-dbi` changed the output to:

```text
320x240 @ 60 Hz
```

The touch controller was kept independent on SPI0 CE1 with a small custom ADS7846 Device Tree overlay.

Fine touch calibration was moved to labwc/libinput, while Device Tree retained hardware wiring and orientation.

## MHS3528 adaptation

LCDWiki publishes the MHS3528 as:

- physical resolution 320×480;
- ILI9486 LCD controller;
- XPT2046 touch controller;
- SPI interface;
- LCD CS physical pin 24 (SPI0 CE0);
- touch CS physical pin 26 (SPI0 CE1);
- LCD D/C/RS physical pin 18 (GPIO24);
- LCD reset physical pin 22 (GPIO25);
- touch IRQ physical pin 11 (GPIO17).

For landscape use the project presents the panel as 480×320.

The existing LCDWiki `MHS35-show` script still configures its own `mhs35` overlay and legacy-style framebuffer/HDMI/Xorg behaviour. The modern profile avoids those components.

The ILI9486 panel init used here is derived from Raspberry Pi Linux's `fb_ili9486` PiScreen sequence. That driver defines RGB565 mode, power/VCOM and gamma setup appropriate to an ILI9486 PiScreen-class panel. A landscape address-mode command is added for the MHS3528 profile.

This is technically a strong candidate because the hardware controller, wiring and init sequence are documented. It is nevertheless labelled **hardware-unverified** until the MHS3528 profile is booted on a physical panel and the following are confirmed:

1. panel initializes without colour corruption;
2. 480×320 DRM mode is stable;
3. orientation is correct;
4. ADS7846 touch is detected;
5. touch transform is calibrated;
6. stable SPI ceiling is measured.

## Why the architecture generalises

The reusable pieces are not controller-specific hacks. Linux already provides:

- generic `panel-mipi-dbi`;
- generic ADS7846/XPT2046 input support;
- DRM/KMS;
- Wayland/labwc.

Each board profile supplies only:

- physical geometry;
- reset/DC GPIOs;
- panel initialization commands;
- touch wiring/orientation/calibration.

That makes additional LCDWiki SPI panels candidates for the same profile-based approach.

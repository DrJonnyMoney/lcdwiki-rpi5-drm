#!/usr/bin/env python3
"""Measure one base touchscreen calibration matrix at the default (0°) orientation.

Rotation is intentionally not handled here. labwc maps the touchscreen to SPI-1
and follows that output's transform automatically, so the same base calibration
matrix is used at 0°, 90°, 180° and 270°.
"""

from pathlib import Path
import math
import select

import pygame
from evdev import InputDevice, ecodes, list_devices

OUT = Path.home() / "touch_calibration_results.txt"


def find_touchscreen():
    denied = False
    for path in list_devices():
        try:
            dev = InputDevice(path)
        except PermissionError:
            denied = True
            continue
        name = dev.name.upper()
        if "ADS7846" in name or "XPT2046" in name:
            return dev
        dev.close()

    if denied:
        raise RuntimeError(
            "Touch input devices exist but are not readable by this user. "
            "Add the user to the input group, then log out and back in."
        )
    raise RuntimeError("ADS7846/XPT2046 touchscreen not found")


def solve3(a, b):
    """Solve a 3x3 linear system with Gaussian elimination."""
    m = [list(map(float, a[r])) + [float(b[r])] for r in range(3)]

    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            raise RuntimeError("Calibration fit is singular; repeat the measurements")
        m[col], m[pivot] = m[pivot], m[col]

        div = m[col][col]
        for j in range(col, 4):
            m[col][j] /= div

        for r in range(3):
            if r == col:
                continue
            factor = m[r][col]
            for j in range(col, 4):
                m[r][j] -= factor * m[col][j]

    return [m[r][3] for r in range(3)]


def least_squares_3(rows, values):
    """Least-squares solution of rows*x = values for three coefficients."""
    ata = [[0.0] * 3 for _ in range(3)]
    atb = [0.0] * 3

    for row, value in zip(rows, values):
        for i in range(3):
            atb[i] += row[i] * value
            for j in range(3):
                ata[i][j] += row[i] * row[j]

    return solve3(ata, atb)


def read_touch_release(dev):
    """Wait for one complete stylus tap while keeping the Pygame UI responsive."""
    x = y = None
    pressed = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                raise KeyboardInterrupt

        readable, _, _ = select.select([dev.fd], [], [], 0.05)
        if not readable:
            continue

        for event in dev.read():
            if event.type == ecodes.EV_ABS:
                if event.code == ecodes.ABS_X:
                    x = event.value
                elif event.code == ecodes.ABS_Y:
                    y = event.value
            elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOUCH:
                if event.value == 1:
                    pressed = True
                elif event.value == 0 and pressed and x is not None and y is not None:
                    return x, y


def fit_matrix(samples, x_min, x_max, y_min, y_max, width, height):
    rows = []
    wanted_x = []
    wanted_y = []

    for sx, sy, rx, ry in samples:
        nx = (rx - x_min) / max(1, x_max - x_min)
        ny = (ry - y_min) / max(1, y_max - y_min)
        tx = sx / max(1, width - 1)
        ty = sy / max(1, height - 1)

        rows.append([nx, ny, 1.0])
        wanted_x.append(tx)
        wanted_y.append(ty)

    a, b, c = least_squares_3(rows, wanted_x)
    d, e, f = least_squares_3(rows, wanted_y)
    return a, b, c, d, e, f


def fitting_errors(samples, matrix, x_min, x_max, y_min, y_max, width, height):
    a, b, c, d, e, f = matrix
    errors = []

    for sx, sy, rx, ry in samples:
        nx = (rx - x_min) / max(1, x_max - x_min)
        ny = (ry - y_min) / max(1, y_max - y_min)

        px = (a * nx + b * ny + c) * (width - 1)
        py = (d * nx + e * ny + f) * (height - 1)
        errors.append(math.hypot(px - sx, py - sy))

    return errors


def main():
    print("LCDWiki base touchscreen calibration")
    print("====================================")
    print("Calibrate at the repository's 0° orientation.")
    print("The resulting matrix is used for ALL display rotations.\n")

    dev = find_touchscreen()
    x_info = dev.absinfo(ecodes.ABS_X)
    y_info = dev.absinfo(ecodes.ABS_Y)

    print(f"Touch device: {dev.name} ({dev.path})")
    print(f"Raw X range: {x_info.min} .. {x_info.max}")
    print(f"Raw Y range: {y_info.min} .. {y_info.max}\n")

    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.mouse.set_visible(False)
    width, height = screen.get_size()

    margin_x = max(20, int(width * 0.10))
    margin_y = max(20, int(height * 0.10))
    xs = [margin_x, width // 2, width - margin_x - 1]
    ys = [margin_y, height // 2, height - margin_y - 1]
    targets = [(x, y) for y in ys for x in xs]

    font = pygame.font.Font(None, 24)
    samples = []

    try:
        for number, (sx, sy) in enumerate(targets, 1):
            screen.fill("black")
            pygame.draw.line(screen, "white", (sx - 14, sy), (sx + 14, sy), 2)
            pygame.draw.line(screen, "white", (sx, sy - 14), (sx, sy + 14), 2)
            pygame.draw.circle(screen, "white", (sx, sy), 5, 2)
            screen.blit(font.render(f"Base calibration  {number}/9", True, "white"), (8, 8))
            pygame.display.flip()

            rx, ry = read_touch_release(dev)
            samples.append((sx, sy, rx, ry))
            print(f"{number}: screen=({sx},{sy}) raw=({rx},{ry})")
    except KeyboardInterrupt:
        print("\nCalibration cancelled.")
        return
    finally:
        pygame.quit()
        dev.close()

    matrix = fit_matrix(
        samples,
        x_info.min, x_info.max,
        y_info.min, y_info.max,
        width, height,
    )
    errors = fitting_errors(
        samples, matrix,
        x_info.min, x_info.max,
        y_info.min, y_info.max,
        width, height,
    )

    matrix_text = " ".join(f"{v:.6f}" for v in matrix)
    mean_error = sum(errors) / len(errors)
    max_error = max(errors)

    with OUT.open("w") as f:
        f.write("LCDWiki base touchscreen calibration\n")
        f.write("====================================\n\n")
        f.write("Orientation: 0 degrees (base calibration)\n")
        f.write("This matrix is used unchanged for all display rotations.\n\n")
        f.write(f"Touch device: {dev.name}\n")
        f.write(f"Device path: {dev.path}\n")
        f.write(f"Screen size: {width} x {height}\n")
        f.write(f"Raw X range: {x_info.min} .. {x_info.max}\n")
        f.write(f"Raw Y range: {y_info.min} .. {y_info.max}\n\n")
        f.write("screen_x,screen_y,raw_x,raw_y\n")
        for sample in samples:
            f.write(",".join(map(str, sample)) + "\n")
        f.write("\nCalibration matrix:\n")
        f.write(matrix_text + "\n\n")
        f.write("labwc XML:\n")
        f.write(f"<calibrationMatrix>{matrix_text}</calibrationMatrix>\n\n")
        f.write(f"Mean fitting error: {mean_error:.2f} px\n")
        f.write(f"Maximum fitting error: {max_error:.2f} px\n")

    print("\nCalibration matrix:")
    print(matrix_text)
    print(f"Mean fitting error: {mean_error:.2f} px")
    print(f"Maximum fitting error: {max_error:.2f} px")
    print(f"\nSaved all measurements to: {OUT}")


if __name__ == "__main__":
    main()

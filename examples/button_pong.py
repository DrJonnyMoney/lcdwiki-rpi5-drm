#!/usr/bin/env python3
"""Simple one-player Pong demo for the LCDWiki 2.8-inch display.

The desktop can remain in its normal orientation. The game renders to an
internal 240x320 portrait canvas and rotates that frame 90 degrees
counter-clockwise before presenting it to the physical 320x240 LCD. This
matches the visual orientation of `lcdwiki-rotate 270` without changing any
system display or touch settings.

Controls:
    KEY1 / KEY_PROG1  - move paddle left
    KEY2 / KEY_PROG2  - restart game
    KEY3 / KEY_PROG3  - move paddle right

Keyboard fallbacks:
    Left / Right      - move paddle
    R                 - restart
    Esc               - quit
"""

from __future__ import annotations

import math
import select
import sys

import pygame
from evdev import InputDevice, ecodes, list_devices

FPS = 60
PADDLE_SPEED = 190.0
BALL_SPEED = 165.0

# Logical game coordinates are portrait even though the LCD remains 320x240.
GAME_W = 240
GAME_H = 320

BUTTON_LEFT = ecodes.KEY_PROG1
BUTTON_RESTART = ecodes.KEY_PROG2
BUTTON_RIGHT = ecodes.KEY_PROG3


def find_button_device() -> InputDevice:
    """Find the gpio-keys device installed by the lcdwiki28 profile."""
    wanted = {BUTTON_LEFT, BUTTON_RESTART, BUTTON_RIGHT}
    denied = False

    for path in list_devices():
        try:
            dev = InputDevice(path)
        except PermissionError:
            denied = True
            continue

        caps = set(dev.capabilities().get(ecodes.EV_KEY, []))
        if wanted.issubset(caps):
            return dev
        dev.close()

    if denied:
        raise SystemExit(
            "Linux input devices exist but are not readable by this user.\n"
            "Add the user to the input group, then log out and back in."
        )

    raise SystemExit(
        "LCDWiki KEY1/KEY2/KEY3 input device not found.\n"
        "Install the lcdwiki28 profile and verify the buttons with:\n"
        "  python3 tools/button_test.py"
    )


class Game:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

        self.paddle_w = max(54, int(width * 0.30))
        self.paddle_h = max(8, int(height * 0.025))
        self.paddle_y = height - self.paddle_h - max(18, int(height * 0.06))

        self.ball_r = max(5, int(min(width, height) * 0.025))
        self.reset()

    def reset(self):
        self.paddle_x = (self.width - self.paddle_w) / 2
        self.ball_x = self.width / 2
        self.ball_y = self.height * 0.35

        angle = math.radians(55)
        self.ball_vx = BALL_SPEED * math.cos(angle)
        self.ball_vy = -BALL_SPEED * math.sin(angle)

        self.score = 0
        self.game_over = False

    def update(self, dt: float, left: bool, right: bool):
        if self.game_over:
            return

        if left and not right:
            self.paddle_x -= PADDLE_SPEED * dt
        elif right and not left:
            self.paddle_x += PADDLE_SPEED * dt

        self.paddle_x = max(0, min(self.width - self.paddle_w, self.paddle_x))

        previous_y = self.ball_y
        self.ball_x += self.ball_vx * dt
        self.ball_y += self.ball_vy * dt

        if self.ball_x - self.ball_r <= 0:
            self.ball_x = self.ball_r
            self.ball_vx = abs(self.ball_vx)
        elif self.ball_x + self.ball_r >= self.width:
            self.ball_x = self.width - self.ball_r
            self.ball_vx = -abs(self.ball_vx)

        if self.ball_y - self.ball_r <= 0:
            self.ball_y = self.ball_r
            self.ball_vy = abs(self.ball_vy)

        paddle_left = self.paddle_x
        paddle_right = self.paddle_x + self.paddle_w
        paddle_top = self.paddle_y

        crossed_paddle = (
            self.ball_vy > 0
            and previous_y + self.ball_r <= paddle_top
            and self.ball_y + self.ball_r >= paddle_top
        )

        if crossed_paddle and paddle_left <= self.ball_x <= paddle_right:
            self.ball_y = paddle_top - self.ball_r

            relative = (
                self.ball_x - (self.paddle_x + self.paddle_w / 2)
            ) / (self.paddle_w / 2)
            relative = max(-1.0, min(1.0, relative))

            speed = min(260.0, math.hypot(self.ball_vx, self.ball_vy) + 5.0)
            self.ball_vx = speed * relative * 0.85
            vertical = max(
                70.0,
                math.sqrt(max(0.0, speed * speed - self.ball_vx * self.ball_vx)),
            )
            self.ball_vy = -vertical
            self.score += 1

        if self.ball_y - self.ball_r > self.height:
            self.game_over = True

    def draw(
        self,
        canvas: pygame.Surface,
        font: pygame.font.Font,
        small_font: pygame.font.Font,
    ):
        canvas.fill("black")

        pygame.draw.rect(
            canvas,
            "white",
            pygame.Rect(
                int(self.paddle_x),
                self.paddle_y,
                self.paddle_w,
                self.paddle_h,
            ),
        )
        pygame.draw.circle(
            canvas,
            "white",
            (int(self.ball_x), int(self.ball_y)),
            self.ball_r,
        )

        score = font.render(str(self.score), True, "white")
        canvas.blit(score, score.get_rect(midtop=(self.width // 2, 8)))

        if self.game_over:
            title = font.render("GAME OVER", True, "white")
            restart = small_font.render("K2  RESTART", True, "white")
            canvas.blit(
                title,
                title.get_rect(center=(self.width // 2, self.height // 2 - 12)),
            )
            canvas.blit(
                restart,
                restart.get_rect(center=(self.width // 2, self.height // 2 + 22)),
            )

        footer = small_font.render("K1 <    K2 restart    > K3", True, "white")
        canvas.blit(
            footer,
            footer.get_rect(midbottom=(self.width // 2, self.height - 3)),
        )


def present_portrait(canvas: pygame.Surface, screen: pygame.Surface) -> None:
    """Present the portrait canvas as a 270-degree-clockwise app view.

    pygame.transform.rotate() uses positive angles counter-clockwise. Rotating
    the 240x320 portrait canvas +90 degrees produces a 320x240 frame, matching
    the visual result of the repository's public `lcdwiki-rotate 270` command.
    """
    frame = pygame.transform.rotate(canvas, 90)

    if frame.get_size() != screen.get_size():
        frame = pygame.transform.smoothscale(frame, screen.get_size())

    screen.blit(frame, (0, 0))
    pygame.display.flip()


def main() -> int:
    buttons = find_button_device()
    print(f"Buttons: {buttons.path} ({buttons.name})")

    pygame.init()
    pygame.mouse.set_visible(False)

    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("LCDWiki Button Pong")
    print(f"Pygame output: {screen.get_width()}x{screen.get_height()}")
    print("Game canvas: 240x320 portrait; app rotation: 270 degrees clockwise")

    canvas = pygame.Surface((GAME_W, GAME_H))
    font = pygame.font.Font(None, 32)
    small_font = pygame.font.Font(None, 18)
    clock = pygame.time.Clock()

    game = Game(GAME_W, GAME_H)
    left_held = False
    right_held = False
    running = True

    try:
        while running:
            dt = min(clock.tick(FPS) / 1000.0, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        game.reset()

            keys = pygame.key.get_pressed()
            keyboard_left = keys[pygame.K_LEFT]
            keyboard_right = keys[pygame.K_RIGHT]

            readable, _, _ = select.select([buttons.fd], [], [], 0)
            if readable:
                for event in buttons.read():
                    if event.type != ecodes.EV_KEY:
                        continue

                    pressed = event.value != 0

                    if event.code == BUTTON_LEFT:
                        left_held = pressed
                    elif event.code == BUTTON_RIGHT:
                        right_held = pressed
                    elif event.code == BUTTON_RESTART and event.value == 1:
                        game.reset()

            game.update(
                dt,
                left_held or keyboard_left,
                right_held or keyboard_right,
            )
            game.draw(canvas, font, small_font)
            present_portrait(canvas, screen)

    finally:
        buttons.close()
        pygame.quit()

    return 0


if __name__ == "__main__":
    sys.exit(main())

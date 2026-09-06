#!/usr/bin/env python3
import pygame
from evdev import InputDevice, list_devices, ecodes
from pathlib import Path

WIDTH = int(input("Logical display width [e.g. 320 or 480]: "))
HEIGHT = int(input("Logical display height [e.g. 240 or 320]: "))
MARGIN = max(20, min(WIDTH, HEIGHT)//12)

xs = [MARGIN, WIDTH//2, WIDTH-MARGIN]
ys = [MARGIN, HEIGHT//2, HEIGHT-MARGIN]
TARGETS = [(x,y) for y in ys for x in xs]
OUT = Path.home()/"touch_calibration_results.txt"

def find_touch():
    for path in list_devices():
        dev=InputDevice(path)
        if "ADS7846" in dev.name:
            return dev
    raise RuntimeError("ADS7846/XPT2046 touchscreen not found")

def read_touch(dev):
    x=y=None
    for e in dev.read_loop():
        if e.type == ecodes.EV_ABS:
            if e.code == ecodes.ABS_X: x=e.value
            elif e.code == ecodes.ABS_Y: y=e.value
        elif e.type == ecodes.EV_KEY and e.code == ecodes.BTN_TOUCH and e.value == 0:
            if x is not None and y is not None: return x,y

pygame.init()
screen=pygame.display.set_mode((WIDTH,HEIGHT), pygame.FULLSCREEN)
pygame.mouse.set_visible(False)
dev=find_touch()
results=[]

for i,(sx,sy) in enumerate(TARGETS,1):
    screen.fill("black")
    pygame.draw.line(screen,"white",(sx-12,sy),(sx+12,sy),2)
    pygame.draw.line(screen,"white",(sx,sy-12),(sx,sy+12),2)
    pygame.draw.circle(screen,"white",(sx,sy),4,2)
    font=pygame.font.Font(None,22)
    screen.blit(font.render(f"{i}/9",True,"white"),(8,8))
    pygame.display.flip()
    rx,ry=read_touch(dev)
    results.append((sx,sy,rx,ry))

pygame.quit()
with OUT.open("w") as f:
    f.write("screen_x,screen_y,raw_x,raw_y\n")
    for r in results: f.write(",".join(map(str,r))+"\n")
print(f"Saved: {OUT}")

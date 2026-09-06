#!/usr/bin/env python3
"""Print presses from the LCDWiki 2.8-inch KEY1/KEY2/KEY3 buttons."""

from evdev import InputDevice, categorize, ecodes, list_devices

NAMES = {
    ecodes.KEY_PROG1: "KEY1",
    ecodes.KEY_PROG2: "KEY2",
    ecodes.KEY_PROG3: "KEY3",
}

def find_device():
    for path in list_devices():
        dev = InputDevice(path)
        if dev.name == "lcdwiki-buttons" or "LCDWiki" in dev.name:
            caps = dev.capabilities().get(ecodes.EV_KEY, [])
            if any(code in caps for code in NAMES):
                return dev
    raise SystemExit("LCDWiki button input device not found")


dev = find_device()
print(f"Listening on {dev.path}: {dev.name}")
print("Press KEY1, KEY2 or KEY3. Ctrl-C exits.\n")
for event in dev.read_loop():
    if event.type == ecodes.EV_KEY and event.code in NAMES:
        state = {0: "released", 1: "pressed", 2: "held"}.get(event.value, str(event.value))
        print(f"{NAMES[event.code]} {state}")

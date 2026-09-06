#!/usr/bin/env python3
"""Print presses from the LCDWiki 2.8-inch KEY1/KEY2/KEY3 buttons."""

from evdev import InputDevice, ecodes, list_devices

NAMES = {
    ecodes.KEY_PROG1: "KEY1",
    ecodes.KEY_PROG2: "KEY2",
    ecodes.KEY_PROG3: "KEY3",
}


def find_device():
    denied = False
    for path in list_devices():
        try:
            dev = InputDevice(path)
        except PermissionError:
            denied = True
            continue

        caps = dev.capabilities().get(ecodes.EV_KEY, [])
        if (dev.name == "lcdwiki-buttons" or "LCDWiki" in dev.name) and any(
            code in caps for code in NAMES
        ):
            return dev
        dev.close()

    if denied:
        raise SystemExit(
            "Input devices exist but are not readable by this user. "
            "Add the user to the input group, then log out and back in."
        )
    raise SystemExit("LCDWiki button input device not found")


def main():
    dev = find_device()
    print(f"Listening on {dev.path}: {dev.name}")
    print("Press KEY1, KEY2 or KEY3. Ctrl-C exits.\n")
    try:
        for event in dev.read_loop():
            if event.type == ecodes.EV_KEY and event.code in NAMES:
                state = {0: "released", 1: "pressed", 2: "held"}.get(
                    event.value, str(event.value)
                )
                print(f"{NAMES[event.code]} {state}")
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()


if __name__ == "__main__":
    main()

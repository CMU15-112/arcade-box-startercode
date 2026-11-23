# Arcade box reset button (RP2040, CircuitPython, button on GP15 to 3V3).
#
# Short press: ask the box (over the USB data serial port, see boot.py) to
#   restart EmulationStation, killing any running game. The arcade-button
#   service on the box answers "ACK" right away.
# No ACK within ACK_TIMEOUT, or button held for HOLD_FOR_REBOOT: the box is
#   wedged, so fall back to the kernel's magic SysRq R-E-I-S-U-B safe reboot.
#
# Needs adafruit_hid in /lib. The LED is on while a request is pending and
# blinks once the box has acknowledged it.
import time

import board
import digitalio
import microcontroller
import usb_cdc
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

ACK_TIMEOUT = 3.0      # seconds to wait for the box to answer
HOLD_FOR_REBOOT = 5.0  # holding the button this long always reboots

kbd = Keyboard(usb_hid.devices)
link = usb_cdc.data    # None if boot.py hasn't enabled the data port

button = digitalio.DigitalInOut(board.GP15)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.DOWN

led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT


def tap(key):
    kbd.press(key)
    time.sleep(0.1)
    kbd.release(key)
    time.sleep(0.1)


def reisub():
    """Alt+SysRq+R,E,I,S,U,B: the kernel syncs, remounts read-only and reboots."""
    led.value = True
    kbd.press(Keycode.ALT, Keycode.PRINT_SCREEN)
    for key in (Keycode.R, Keycode.E, Keycode.I):
        tap(key)
    tap(Keycode.S)
    time.sleep(1)      # give the sync and remount a moment before rebooting
    tap(Keycode.U)
    time.sleep(1)
    tap(Keycode.B)
    kbd.release_all()
    time.sleep(10)
    microcontroller.reset()


def ask_box_to_restart():
    """Send the restart request; True if the box acknowledged it in time."""
    if link is None or not link.connected:   # nothing is listening on the box
        return False
    link.reset_input_buffer()
    link.write(b"RESTART-ES\n")
    reply = b""
    deadline = time.monotonic() + ACK_TIMEOUT
    while time.monotonic() < deadline:
        if link.in_waiting:
            reply += link.read(link.in_waiting)
            if b"ACK" in reply:
                return True
        time.sleep(0.02)
    return False


def blink(times):
    for _ in range(times):
        led.value = False
        time.sleep(0.15)
        led.value = True
        time.sleep(0.15)
    led.value = False


while True:
    if not button.value:
        time.sleep(0.02)
        continue
    time.sleep(0.05)               # debounce
    if not button.value:
        continue

    pressed_at = time.monotonic()
    led.value = True
    if not ask_box_to_restart():
        reisub()                   # never returns
    blink(3)
    while button.value:            # still holding: escalate to a hard reboot
        if time.monotonic() - pressed_at >= HOLD_FOR_REBOOT:
            reisub()
        time.sleep(0.02)
    time.sleep(0.5)

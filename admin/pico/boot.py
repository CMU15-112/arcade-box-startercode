# Runs once when the Pico powers up or hard-resets, before code.py.
#
# Adds a second USB serial port (the "data" port) next to the REPL console.
# code.py uses it to ask the arcade box to restart EmulationStation; the
# arcade-button service on the box listens on it. Keeping it separate from the
# console means REPL output and tracebacks never get mixed into that channel.
#
# USB changes only take effect after a hard reset: unplug the Pico and plug it
# back in after copying this file over.
import usb_cdc

usb_cdc.enable(console=True, data=True)

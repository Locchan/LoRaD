#!/usr/bin/env python3
"""Rotary volume knob.

Straight on libgpiod instead of gpiozero: every gpiozero backend (lgpio, RPi.GPIO)
keeps a sampling thread running and burns ~4% CPU on a Pi 3 with the knob untouched.
A libgpiod wait blocks in the kernel until an edge arrives, so idle costs nothing.

Needs the libgpiod v2 bindings (python3-libgpiod on Debian 13).
"""

import glob
import subprocess
import time

import gpiod
from gpiod.line import Bias, Edge

PIN_A = 17
PIN_B = 27
VOLUME_CMD = "/usr/bin/volume"
# The header pins hang off the SoC pin controller; its chip number moves between
# kernels and Pi models, so find it by label instead of hardcoding gpiochip0.
CHIP_LABEL_PREFIX = "pinctrl-"
# Detents seen within this window are applied as a single volume call.
BURST_S = 0.08
IDLE_WAIT_S = 1

# Quadrature state machine copied from gpiozero so the knob keeps the same feel.
# The index is the pin pair (A is the high bit, B the low bit); pull-ups make idle 0.
TRANSITIONS = {
    "idle": ("idle", "ccw1", "cw1", "idle"),
    "ccw1": ("idle", "ccw1", "ccw3", "ccw2"),
    "ccw2": ("idle", "ccw1", "ccw3", "ccw2"),
    "ccw3": ("-1", "idle", "ccw3", "ccw2"),
    "cw1": ("idle", "cw3", "cw1", "cw2"),
    "cw2": ("idle", "cw3", "cw1", "cw2"),
    "cw3": ("+1", "cw3", "idle", "cw2"),
}


class Decoder:
    def __init__(self):
        self.state = "idle"
        self.edge = 0

    def feed(self, offset, high):
        # Pins are pulled up, so gpiozero's table sees the inverted level.
        bit = 0 if high else 1
        # A and B are swapped here: this knob is wired so that the table's
        # clockwise sequence is the direction that should turn the volume down.
        if offset == PIN_B:
            self.edge = (bit << 1) | (self.edge & 0x1)
        else:
            self.edge = (self.edge & 0x2) | bit
        new_state = TRANSITIONS[self.state][self.edge]
        if new_state in ("+1", "-1"):
            self.state = "idle"
            return 1 if new_state == "+1" else -1
        self.state = new_state
        return 0


def find_chip():
    for path in sorted(glob.glob("/dev/gpiochip*")):
        if not gpiod.is_gpiochip_device(path):
            continue
        with gpiod.Chip(path) as chip:
            info = chip.get_info()
            if info.label.startswith(CHIP_LABEL_PREFIX) and info.num_lines > max(PIN_A, PIN_B):
                return path
    raise RuntimeError("no pin controller gpiochip found")


def apply_steps(steps):
    argument = f"{'+' if steps > 0 else '-'}{abs(steps)}"
    try:
        subprocess.run([VOLUME_CMD, argument], stdout=subprocess.DEVNULL, check=False)
    except OSError as e:
        print(f"volume_knob: could not run {VOLUME_CMD}: {e}", flush=True)


def main():
    settings = gpiod.LineSettings(edge_detection=Edge.BOTH, bias=Bias.PULL_UP)
    request = gpiod.request_lines(
        find_chip(),
        consumer="volume_knob",
        config={(PIN_A, PIN_B): settings},
    )
    decoder = Decoder()
    pending = 0
    deadline = 0.0

    with request:
        while True:
            ready = request.wait_edge_events(BURST_S if pending else IDLE_WAIT_S)
            for event in request.read_edge_events() if ready else ():
                rising = event.event_type == gpiod.EdgeEvent.Type.RISING_EDGE
                delta = decoder.feed(event.line_offset, rising)
                if delta and not pending:
                    # Cap the burst so a long uninterrupted turn still moves the volume.
                    deadline = time.monotonic() + BURST_S
                pending += delta
            if pending and (not ready or time.monotonic() >= deadline):
                apply_steps(pending)
                pending = 0


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Program terminated")

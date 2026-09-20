#!/usr/bin/env python3

from gpiozero import RotaryEncoder, Button
from time import sleep
import subprocess

encoder = RotaryEncoder(a=17, b=27, wrap=False, max_steps=10000000)
button = Button(22)

last_rotary_value = 0  # Variable to store the last value of rotary encoder

try:
    while True:
        current_rotary_value = encoder.steps  # Read current step count

        if last_rotary_value != current_rotary_value:
            if current_rotary_value > last_rotary_value:
                subprocess.run("volume +1", shell=True)
            else:
                subprocess.run("volume -1", shell=True)
        last_rotary_value = current_rotary_value

        sleep(0.05)

except KeyboardInterrupt:
    print("Program terminated")

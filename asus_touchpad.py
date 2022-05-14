#!/usr/bin/env python3

import importlib
import logging
import math
import os
import re
import subprocess
import sys
from fcntl import F_SETFL, fcntl
from time import sleep
from typing import Optional
import numpy as np

import libevdev.const
from libevdev import EV_ABS, EV_KEY, EV_SYN, EV_MSC, Device, InputEvent
from pyrsistent import v

# Setup logging
# LOG=DEBUG sudo -E ./asus_touchpad.py  # all messages
# LOG=ERROR sudo -E ./asus_touchpad.py  # only error messages
logging.basicConfig()
log = logging.getLogger('Pad')
log.setLevel(os.environ.get('LOG', 'INFO'))


# Select model from command line

model = 'm433ia' # Model used in the derived script (with symbols)
if len(sys.argv) > 1:
    model = sys.argv[1]

model_layout = importlib.import_module('numpad_layouts.'+ model)

percentage_key: libevdev.const = EV_KEY.KEY_5

if len(sys.argv) > 2:
    percentage_key = EV_KEY.codes[int(sys.argv[2])]

# Figure out devices from devices file

touchpad: Optional[str] = None
device_id: Optional[str] = None

tries = model_layout.try_times

brightness: int = 0

# Look into the devices file #
while tries > 0:

    touchpad_detected = 0

    with open('/proc/bus/input/devices', 'r') as f:
        lines = f.readlines()
        for line in lines:
            # Look for the touchpad #
            if touchpad_detected == 0 and ("Name=\"ASUE" in line or "Name=\"ELAN" in line) and "Touchpad" in line:
                touchpad_detected = 1
                log.debug('Detect touchpad from %s', line.strip())

            if touchpad_detected == 1:
                if "S: " in line:
                    # search device id
                    device_id=re.sub(r".*i2c-(\d+)/.*$", r'\1', line).replace("\n", "")
                    log.debug('Set touchpad device id %s from %s', device_id, line.strip())

                if "H: " in line:
                    touchpad = line.split("event")[1]
                    touchpad = touchpad.split(" ")[0]
                    touchpad_detected = 2
                    log.debug('Set touchpad id %s from %s', touchpad, line.strip())

          
            # Stop looking if touchpad has been found #
            if touchpad_detected == 2:
                break

    if touchpad_detected != 2:
        tries -= 1
        if tries == 0:
            if touchpad_detected != 2:
                log.error("Can't find touchpad (code: %s)", touchpad_detected)
            if touchpad_detected == 2 and not device_id.isnumeric():
                log.error("Can't find device id")
            sys.exit(1)
    else:
        break

    sleep(model_layout.try_sleep)

# Start monitoring the touchpad

fd_t = open('/dev/input/event' + str(touchpad), 'rb')
d_t = Device(fd_t)


# Retrieve touchpad dimensions #

ai = d_t.absinfo[EV_ABS.ABS_X]
(minx, maxx) = (ai.minimum, ai.maximum)
minx_numpad = minx + model_layout.left_offset
maxx_numpad = maxx - model_layout.right_offset
ai = d_t.absinfo[EV_ABS.ABS_Y]
(miny, maxy) = (ai.minimum, ai.maximum)
miny_numpad = miny + model_layout.top_offset
maxy_numpad = maxy - model_layout.bottom_offset
log.debug('Touchpad min-max: x %d-%d, y %d-%d', minx, maxx, miny, maxy)
log.debug('Numpad min-max: x %d-%d, y %d-%d', minx_numpad, maxx_numpad, miny_numpad, maxy_numpad)

col_width = (maxx_numpad - minx_numpad) / model_layout.cols
row_height = (maxy_numpad - miny_numpad) / model_layout.rows

# Start monitoring the keyboard (numlock)

# Create a new keyboard device to send numpad events
# KEY_5:6
# KEY_APOSTROPHE:40
# [...]
percentage_key = EV_KEY.KEY_5

if len(sys.argv) > 2:
    percentage_key = EV_KEY.codes[int(sys.argv[2])]

dev = Device()
dev.name = "Asus Touchpad/Numpad"
dev.enable(EV_KEY.KEY_LEFTSHIFT)
dev.enable(EV_KEY.KEY_NUMLOCK)
if hasattr(model_layout, "touchpad_left_button_keys"):
    for key_to_enable in model_layout.touchpad_left_button_keys:
        dev.enable(key_to_enable)

if percentage_key != EV_KEY.KEY_5:
    dev.enable(percentage_key)

for col in model_layout.keys:
    for key in col:
        dev.enable(key)

if percentage_key != EV_KEY.KEY_5:
    dev.enable(percentage_key)

udev = dev.create_uinput_device()

def use_bindings_for_touchpad_left_key(e):

    key_events = []
    for touchpad_left_button_key in model_layout.touchpad_left_button_keys:
        key_events.append(InputEvent(touchpad_left_button_key, e.value))

    sync_event = [
        InputEvent(EV_SYN.SYN_REPORT, 0)
    ]

    try:
        udev.send_events(key_events)
        udev.send_events(sync_event)
        if e.value:
            log.info("Pressed touchpad left key and used bound keys")
        else:
            log.info("Unpressed touchpad left key and used bound keys")
    except OSError as e:
        log.error("Cannot send event, %s", e)

def is_pressed_touchpad_top_right_icon(x, y):
    if x >= maxx - model_layout.top_right_icon_width and y < model_layout.top_right_icon_height:
        return True
    else:
        return False

def is_pressed_touchpad_top_left_icon(x, y):
    if x <= model_layout.top_left_icon_width and y < model_layout.top_left_icon_height:
        return True
    else:
        return False

def pressed_touchpad_top_left_icon(e):
    if numlock and hasattr(model_layout, "backlight_levels") and len(model_layout.backlight_levels) > 2:
        if e.value == 1:
            brightness = increase_brightness(brightness)
    elif hasattr(model_layout, "touchpad_left_button_keys") and len(model_layout.touchpad_left_button_keys):
        use_bindings_for_touchpad_left_key(e)

def increase_brightness(brightness):
    if (brightness + 1) >= len(model_layout.backlight_levels):
        brightness = 1
    else:
        brightness += 1

    log.info("Increased brightness of backlight to")
    log.info(brightness)

    numpad_cmd = "i2ctransfer -f -y " + device_id + " w13@0x15 0x05 0x00 0x3d 0x03 0x06 0x00 0x07 0x00 0x0d 0x14 0x03 " + model_layout.backlight_levels[brightness] + " 0xad"
    subprocess.call(numpad_cmd, shell=True)

    return brightness


def activate_numlock():
    try:
        numpad_cmd = "i2ctransfer -f -y " + device_id + " w13@0x15 0x05 0x00 0x3d 0x03 0x06 0x00 0x07 0x00 0x0d 0x14 0x03 " + model_layout.backlight_levels[1] + " 0xad"
        events = [
            InputEvent(EV_KEY.KEY_NUMLOCK, 1),
            InputEvent(EV_SYN.SYN_REPORT, 0)
        ]
        udev.send_events(events)
        d_t.grab()
        subprocess.call(numpad_cmd, shell=True)
        return 1
    except (OSError, libevdev.device.DeviceGrabError) as e:
        pass

def deactivate_numlock():
    try:
        numpad_cmd = "i2ctransfer -f -y " + device_id + " w13@0x15 0x05 0x00 0x3d 0x03 0x06 0x00 0x07 0x00 0x0d 0x14 0x03 " + model_layout.backlight_levels[0] + " 0xad"
        events = [
            InputEvent(EV_KEY.KEY_NUMLOCK, 0),
            InputEvent(EV_SYN.SYN_REPORT, 0)
        ]
        udev.send_events(events)
        d_t.ungrab()
        subprocess.call(numpad_cmd, shell=True)
        return 0
    except (OSError, libevdev.device.DeviceGrabError) as e:
        pass

numlock: bool = False
button_pressed: libevdev.const = None
abs_mt_slot_value: int = 0
# -1 inactive, > 0 active
abs_mt_slot = np.array([0, 1, 2, 3, 4], int)
abs_mt_slot_numpad_key = np.array([None, None, None, None, None], dtype=libevdev.const.EventCode)
abs_mt_slot_x_values = np.array([0, 1, 2, 3, 4], int)
abs_mt_slot_y_values = np.array([0, 1, 2, 3, 4], int)
# equal to multi finger maximum
support_for_maximum_abs_mt_slots: int = 5
unsupported_abs_mt_slot: bool = False

def set_tracking_id(value):
    try:

        if value > 0:
            log.info("Started new slot")
            # not know yet
            # log.info(abs_mt_slot_numpad_key[abs_mt_slot_value])
        else:
            log.info("Ended existing slot")
            # can be misunderstanding when is touched padding (is printed previous key)
            # log.info(abs_mt_slot_numpad_key[abs_mt_slot_value])

        abs_mt_slot[abs_mt_slot_value] = value
    except IndexError as e:
        log.error(e)

def pressed_numpad_key():
    log.info("Pressed numpad key")
    log.info(abs_mt_slot_numpad_key[abs_mt_slot_value])

    if abs_mt_slot_numpad_key[abs_mt_slot_value] == percentage_key:
        events = [
            InputEvent(EV_KEY.KEY_LEFTSHIFT, e.value),
            InputEvent(EV_SYN.SYN_REPORT, 0),
            InputEvent(abs_mt_slot_numpad_key[abs_mt_slot_value], 1),
            InputEvent(EV_SYN.SYN_REPORT, 0)
        ]
    else:
        events = [
            InputEvent(abs_mt_slot_numpad_key[abs_mt_slot_value], 1),
            InputEvent(EV_SYN.SYN_REPORT, 0)
        ]

    try:
        udev.send_events(events)
    except OSError as e:
        log.warning("Cannot send press event, %s", e)

def unpressed_numpad_key():
    log.info("Unpress numpad key")
    log.info(abs_mt_slot_numpad_key[abs_mt_slot_value])

    if abs_mt_slot_numpad_key[abs_mt_slot_value] == percentage_key:
        events = [
            InputEvent(EV_KEY.KEY_LEFTSHIFT, e.value),
            InputEvent(EV_SYN.SYN_REPORT, 0),
            InputEvent(abs_mt_slot_numpad_key[abs_mt_slot_value], 0),
            InputEvent(EV_SYN.SYN_REPORT, 0)
        ]
    else:
        events = [
            InputEvent(abs_mt_slot_numpad_key[abs_mt_slot_value], 0),
            InputEvent(EV_SYN.SYN_REPORT, 0)
        ]

    abs_mt_slot_numpad_key[abs_mt_slot_value] = None

    try:
        udev.send_events(events)
    except OSError as e:
        log.warning("Cannot send press event, %s", e)

def get_touched_key():
    col = math.floor((abs_mt_slot_x_values[abs_mt_slot_value] - minx_numpad) / col_width)
    row = math.floor((abs_mt_slot_y_values[abs_mt_slot_value] - miny_numpad) / row_height)

    if row < 0 or col < 0:
        return None

    try:
        return model_layout.keys[row][col]
    except IndexError as e:
        return None


def is_not_finger_moved_to_another_key():

    touched_key_when_pressed = abs_mt_slot_numpad_key[abs_mt_slot_value]
    touched_key_now = get_touched_key()
    if touched_key_when_pressed != None and touched_key_now != touched_key_when_pressed: 
        unpressed_numpad_key()

        if touched_key_now != None:
            abs_mt_slot_numpad_key[abs_mt_slot_value] = touched_key_now
            pressed_numpad_key()

while True:

    for e in d_t.events():

        if e.matches(EV_ABS.ABS_MT_SLOT):
            if(e.value < support_for_maximum_abs_mt_slots):
                abs_mt_slot_value = e.value
                unsupported_abs_mt_slot = False
            else:
                unsupported_abs_mt_slot = True

        if unsupported_abs_mt_slot == True:
            continue

        if e.matches(EV_ABS.ABS_MT_POSITION_X):
            abs_mt_slot_x_values[abs_mt_slot_value] = e.value

            is_not_finger_moved_to_another_key()

        if e.matches(EV_ABS.ABS_MT_POSITION_Y):
            abs_mt_slot_y_values[abs_mt_slot_value] = e.value

            is_not_finger_moved_to_another_key()

        if e.matches(EV_ABS.ABS_MT_TRACKING_ID):
            set_tracking_id(e.value)

        if e.matches(EV_KEY.BTN_TOOL_FINGER) or \
           e.matches(EV_KEY.BTN_TOOL_DOUBLETAP) or \
           e.matches(EV_KEY.BTN_TOOL_TRIPLETAP) or \
           e.matches(EV_KEY.BTN_TOOL_QUADTAP) or \
           e.matches(EV_KEY.BTN_TOOL_QUINTTAP):

            log.debug('finger down at x %d y %d', abs_mt_slot_x_values[abs_mt_slot_value], (abs_mt_slot_y_values[abs_mt_slot_value]))

            if is_pressed_touchpad_top_right_icon(
                abs_mt_slot_x_values[abs_mt_slot_value],
                abs_mt_slot_y_values[abs_mt_slot_value]
                ):
                if e.value == 0:
                    continue

                numlock = not numlock
                if numlock:
                    log.info("Numpad enabled")
                    brightness = activate_numlock()
                else:
                    log.info("Numpad disabled")
                    brightness = deactivate_numlock()
                continue

            elif is_pressed_touchpad_top_left_icon(
                abs_mt_slot_x_values[abs_mt_slot_value],
                abs_mt_slot_y_values[abs_mt_slot_value]
                ):
                pressed_touchpad_top_left_icon(e)

            # Numpad is not activated
            if not numlock:
                continue


            if(
                abs_mt_slot_x_values[abs_mt_slot_value] < minx_numpad or
                abs_mt_slot_x_values[abs_mt_slot_value] > maxx_numpad or
                abs_mt_slot_y_values[abs_mt_slot_value] < miny_numpad or
                abs_mt_slot_y_values[abs_mt_slot_value] > maxy_numpad
            ):
               continue

            col = math.floor((abs_mt_slot_x_values[abs_mt_slot_value] - minx_numpad) / col_width)
            row = math.floor((abs_mt_slot_y_values[abs_mt_slot_value] - miny_numpad) / row_height)

            if row < 0 or col < 0:
               continue

            try:
                button_pressed = model_layout.keys[row][col]
            except IndexError:
                log.error('Unhandled col/row %d/%d for position %d-%d', 
                    col,
                    row,
                    abs_mt_slot_x_values[abs_mt_slot_value],
                    abs_mt_slot_y_values[abs_mt_slot_value]
                )
                continue

            abs_mt_slot_numpad_key[abs_mt_slot_value] = button_pressed

            if e.value == 1:
                pressed_numpad_key()
            else:
                unpressed_numpad_key()
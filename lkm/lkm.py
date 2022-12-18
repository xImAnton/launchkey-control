import contextlib
import threading
from inspect import isfunction
from typing import Callable, Union
import logging
import secrets

import mido


LOGGER = logging.getLogger(__name__)


LKM_LED_PORTS = (
    (96, 97, 98, 99, 100, 101, 102, 103, 104),
    (112, 113, 114, 115, 116, 117, 118, 119, 120)
)


DOWN = 1
UP = 0
LEFT = 0
RIGHT = 1
TOP = 0
BOTTOM = 1
KEYBOARD = 1
CONTROL = 0


def only(direction: int):
    def wrap(f):
        def inner(*args, **kwargs):
            if len(args) > 0 and args[-1] != direction:
                return
            return f(*args, **kwargs)

        inner.__name__ = f.__name__

        return inner
    return wrap


def state_from_value(value: int) -> int:
    if value is None:
        return UP
    return DOWN if value > 0 else UP


class LaunchKeyMini:
    _EVENT_NAMES = {"connect", "close", "mode_switch", "scene_press", "track_press", "keyboard_press", "pad_press", "potentiometer_change", "midi"}

    def __init__(self, keyboard: bool = True, controls: bool = True):
        self.keyboard_in = None
        self.midi_in = None
        self.led_out = None

        self._use_keyboard = keyboard
        self._use_performance = controls

        self._control_lock = threading.Lock()
        self._close_event = threading.Event()

        self._events = {name: {} for name in self._EVENT_NAMES}

    def open(self, always_in_control: bool = False):
        if self._use_keyboard:
            self.keyboard_in = mido.open_input("Launchkey Mini 0", callback=self.on_keyboard_note)
        if self._use_performance:
            self.midi_in = mido.open_input("MIDIIN2 (Launchkey Mini) 1", callback=self.on_other_input)
        self.led_out = mido.open_output("MIDIOUT2 (Launchkey Mini) 2")

        self.call_event("connect")

        if always_in_control:
            with self.in_control(True):
                self._close_event.wait()
        else:
            self._close_event.wait()

        self.call_event("close")

    def close(self):
        self.keyboard_in.close()
        self.midi_in.close()
        self.led_out.close()
        self._close_event.set()

    def call_event(self, name: str, *args):
        if name not in self._events:
            return
        for callback in self._events[name].values():
            callback(*args)

    def add_event_handler(self, event: str, callback: Callable):
        identifier = secrets.token_hex(8)
        self._events[str(event)][identifier] = callback
        callback.__event_name__ = event
        return f"{event}-{identifier}"

    def remove_event_handler(self, identifier: str):
        event, identifier = identifier.split("-")
        del self._events[event][identifier]

    @staticmethod
    def _check_event_name(name: str) -> str:
        if name.startswith("on_"):
            name = name[3:]

        if name not in LaunchKeyMini._EVENT_NAMES:
            raise ValueError(f"\"{name}\" is not a valid event name")

        return name

    def event(self, func_or_event_name: Union[Callable, str]):
        if not isfunction(func_or_event_name):
            if not isinstance(func_or_event_name, str):
                raise TypeError(f"{func_or_event_name} is not a function or string")

            event = self._check_event_name(func_or_event_name)

            def wrap(f):
                self.add_event_handler(event, f)

            return wrap

        event = self._check_event_name(func_or_event_name.__name__)
        self.add_event_handler(event, func_or_event_name)

        return func_or_event_name
    
    def on_keyboard_note(self, msg: mido.Message):
        self.call_event("midi", msg, KEYBOARD)

        if msg.type == "note_on":
            self.call_event("keyboard_press", msg.note, msg.velocity, DOWN)
        elif msg.type == "note_off":
            self.call_event("keyboard_press", msg.note, msg.velocity, UP)
        elif msg.type == "control_change":
            if msg.control == 108:
                self.call_event("pad_press", 8, 0, msg.value, state_from_value(msg.value))
            elif msg.control == 109:
                self.call_event("pad_press", 8, 1, msg.value, state_from_value(msg.value))
            else:
                self.on_other_input(msg)

    def on_other_input(self, msg: mido.Message):
        self.call_event("midi", msg, CONTROL)

        if msg.type == "note_on":
            if 96 <= msg.note <= 104:
                self.call_event("pad_press", msg.note - 96, 0, msg.velocity, DOWN)
            elif 112 <= msg.note <= 120:
                self.call_event("pad_press", msg.note - 112, 1, msg.velocity, DOWN)
            elif msg.note == 10:
                self.call_event("mode_switch", int(msg.velocity == 0))
        elif msg.type == "note_off":
            if 96 <= msg.note <= 104:
                self.call_event("pad_press", msg.note - 96, 0, msg.velocity, UP)
            elif 112 <= msg.note <= 120:
                self.call_event("pad_press", msg.note - 112, 1, msg.velocity, UP)
        elif msg.type == "control_change":
            if 21 <= msg.control <= 28:
                self.call_event("potentiometer_change", msg.control - 21, msg.value)
            elif msg.control == 107:
                self.call_event("track_press", RIGHT, state_from_value(msg.value))
            elif msg.control == 106:
                self.call_event("track_press", LEFT, state_from_value(msg.value))
            elif msg.control == 104:
                self.call_event("scene_press", TOP, state_from_value(msg.value))
            elif msg.control == 105:
                self.call_event("scene_press", BOTTOM, state_from_value(msg.value))

    """
    def on_mode_switch(self, mode: bool):
        print(f"Mode Switch {mode=}")

    def on_scene_press(self, direction: int, press: int):
        print(f"Scene Press {direction=} {press=}")

    def on_track_press(self, direction: int, press: int):
        print(f"Track Press {direction=} {press=}")

    def on_keyboard_press(self, note: int, velocity: int, press: int):
        print(f"Keyboard Press {note=} {velocity=} {press=}")

    def on_pad_press(self, x: int, y: int, velocity: int, press: int):
        print(f"Pad Press {x=} {y=} {velocity=} {press=}")

    def on_potentiometer_change(self, index: int, value: int):
        print(f"Potentiometer Change {index=} {value=}")
    """

    def set_in_control(self, enabled: bool = True):
        state = enabled and 0x7F or 0x00
        self.led_out.send(mido.Message.from_bytes([0x90, 0x0C, state]))

    def set_led(self, x: int, y: int, color: int):
        self.led_out.send(mido.Message("note_on", note=LKM_LED_PORTS[y][x], velocity=color))

    def clear_led(self, x: int, y: int):
        self.set_led(x, y, 0)

    @contextlib.contextmanager
    def in_control(self, block: bool = True):
        callback = None

        if block:
            self._control_lock.acquire()

            def on_mode_switch(mode):
                if mode == KEYBOARD:
                    self.set_in_control(True)

            callback = self.add_event_handler("mode_switch", on_mode_switch)

        self.set_in_control(True)
        yield
        self.set_in_control(False)

        if block:
            self.remove_event_handler(callback)
            self._control_lock.release()

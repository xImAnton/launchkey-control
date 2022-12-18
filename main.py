import random
import lkm


def random_color():
    red_or_green = bool(random.randint(0, 1))  # Making sure the number is always >0 for one component
    return random.randint(int(red_or_green), 3) + random.randint(int(not red_or_green), 3) * 16


color_palette = [
    1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15,
    19, 23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63,
    18, 22, 26, 30, 34, 38, 42, 46, 50, 54, 58, 62,
    17, 21, 25, 29, 33, 37, 41, 45, 49, 53, 57, 61,
    16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60
]


lk = lkm.LaunchKeyMini()


@lk.event("potentiometer_change")
def poti_changed(index, value):
    i = int((value / 127) * (len(color_palette) - 1))
    lk.set_led(index, 0, color_palette[i])
    lk.set_led(index, 1, color_palette[len(color_palette) - i - 1])


@lk.event("keyboard_press")
def on_keyboard_press(note, velocity, direction):
    if direction == lkm.DOWN:
        print("Keyboard Press: {} {}".format(note, velocity))


@lk.event("connect")
def on_ready():
    print("Device Ready")


if __name__ == '__main__':
    lk.open(always_in_control=True)
    print("end")

# https://www.partsnotincluded.com/how-to-control-the-leds-on-a-novation-launchkey-mini-ii/

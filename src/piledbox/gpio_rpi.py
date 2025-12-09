from enum import IntEnum

import board
import adafruit_pixelbuf
from adafruit_raspberry_pi5_neopixel_write import neopixel_write
from adafruit_blinka.microcontroller.generic_linux.lgpio_pin import Pin


class GPIO(IntEnum):
    """
    All GPIO pins allowed.
    """

    # Comment a line below to forbid any GPIO pin from being declared
    gpio1 = 1
    gpio2 = 2
    gpio3 = 3
    gpio4 = 4
    gpio5 = 5
    gpio6 = 6
    gpio7 = 7
    gpio8 = 8
    gpio9 = 9
    gpio10 = 10
    gpio11 = 11
    gpio12 = 12
    gpio13 = 13
    gpio14 = 14
    gpio15 = 15
    gpio16 = 16
    gpio17 = 17
    gpio18 = 18
    gpio19 = 19
    gpio20 = 20
    gpio21 = 21
    gpio22 = 22
    gpio23 = 23
    gpio24 = 24
    gpio25 = 25
    gpio26 = 26
    gpio27 = 27

    def __str__(self):
        return self.name

    @staticmethod
    def list():
        """
        Returns array with all possible pins as string
        """
        return [item.name for item in GPIO]

    def toBoardPin(self) -> Pin | None:
        """
        Returns:
            - Corresponding pin number on the RPI5 board
            - 'None' if not found
        """

        pinMap = {
            GPIO.gpio1: board.D1,
            GPIO.gpio2: board.D2,
            GPIO.gpio3: board.D3,
            GPIO.gpio4: board.D4,
            GPIO.gpio5: board.D5,
            GPIO.gpio6: board.D6,
            GPIO.gpio7: board.D7,
            GPIO.gpio8: board.D8,
            GPIO.gpio9: board.D9,
            GPIO.gpio10: board.D10,
            GPIO.gpio11: board.D11,
            GPIO.gpio12: board.D12,
            GPIO.gpio13: board.D13,
            GPIO.gpio14: board.D14,
            GPIO.gpio15: board.D15,
            GPIO.gpio16: board.D16,
            GPIO.gpio17: board.D17,
            GPIO.gpio18: board.D18,
            GPIO.gpio19: board.D19,
            GPIO.gpio20: board.D20,
            GPIO.gpio21: board.D21,
            GPIO.gpio22: board.D22,
            GPIO.gpio23: board.D23,
            GPIO.gpio24: board.D24,
            GPIO.gpio25: board.D25,
            GPIO.gpio26: board.D26,
            GPIO.gpio27: board.D27,
        }

        if self in pinMap.keys():
            return pinMap[self]
        else:
            return None


class Pi5PixelBuffer(adafruit_pixelbuf.PixelBuf):
    def __init__(self, pin, size, **kwargs):
        self._pin = pin
        super().__init__(size=size, **kwargs)

    def _transmit(self, buffer):
        neopixel_write(self._pin, buffer)

import signal
from datetime import datetime, timedelta
from os import getpid
import sys
from multiprocessing import Queue

from .fixture_definitions import FixtureChannelName, Fixture
from .fixture_manager import FixturePatch
from .project_logger import initGpioLogger, getGpioLogger
from .sacn_manager import UniverseData
from .gpio_rpi import Pi5PixelBuffer, GPIO
from .misc import WORKER_LED_REFRESH_RATE


class Pixel:
    """
    Class to describe the value of a pixel
    Supports 8 and 16 bit values
    """

    max_16b = pow(2, 16) - 1
    max_8b = pow(2, 8) - 1

    def __init__(
        self,
        red: int = 0,
        green: int = 0,
        blue: int = 0,
        white: int = 0,
        bitDepth: int = 8,
    ):
        self.bitDepth = bitDepth
        self.red = red
        self.green = green
        self.blue = blue
        self.white = white

    @property
    def maxValue(self):
        """Max value of a single channel"""
        return self.max_8b if self._bitDepth == 8 else self.max_16b

    @property
    def bitDepth(self):
        return self._bitDepth

    @bitDepth.setter
    def bitDepth(self, value):
        if not isinstance(value, int) or not value in (8, 16):
            raise ValueError(f"Bit depth [{self.bitDepth}] out of range")
        if not hasattr(self, "_bitDepth"):
            self._bitDepth = value
            return
        elif self._bitDepth != value:
            newMax = self.max_8b if value == 8 else self.max_16b
            self.red = round((self.red / self.maxValue) * newMax)
            self.green = round((self.green / self.maxValue) * newMax)
            self.blue = round((self.blue / self.maxValue) * newMax)
            self.white = round((self.white / self.maxValue) * newMax)
            self._bitDepth = value
            return

    @property
    def red(self):
        return self._red

    @red.setter
    def red(self, value):
        if not isinstance(value, int) or not 0 <= value <= self.maxValue:
            raise ValueError(f"Red [{value}] out of range")
        self._red = value

    @property
    def green(self):
        return self._green

    @green.setter
    def green(self, value):
        if not isinstance(value, int) or not 0 <= value <= self.maxValue:
            raise ValueError(f"Green [{value}] out of range")
        self._green = value

    @property
    def blue(self):
        return self._blue

    @blue.setter
    def blue(self, value):
        if not isinstance(value, int) or not 0 <= value <= self.maxValue:
            raise ValueError(f"Blue [{value}] out of range")
        self._blue = value

    @property
    def white(self):
        return self._white

    @white.setter
    def white(self, value):
        if not isinstance(value, int) or not 0 <= value <= self.maxValue:
            raise ValueError(f"White [{value}] out of range")
        self._white = value

    def __str__(self):
        return f"R {self.red} | G {self.green} | B {self.blue} | W {self.white} @ {self.bitDepth} bit"

    def asTuple(self, order: str = "RGB") -> tuple:
        """
        Get channel values as ordered tuple
        Order can be specified with the order parameter eg. "RGB", "BGRW" and so on
        Duplicates allowed eg "RGBB"
        """
        if not isinstance(order, str) or not 3 <= len(order) <= 4:
            return self.asTuple("RGB")

        result = []
        for char in order:
            match (char):
                case "R":
                    result.append(self.red)
                case "G":
                    result.append(self.green)
                case "B":
                    result.append(self.blue)
                case "W":
                    result.append(self.white)
                case _:
                    return self.asTuple("RGB")
        return tuple(result)


########################
### GPIO PROCESS DEF ###
########################


def processSacnToGPIO(
    patchedFixtures: dict[GPIO, list[FixturePatch]],
    pixelBuffers: dict[GPIO, Pi5PixelBuffer],
    sacnShareQueue: Queue,
):
    """
    Intended to run in separate process
    Reads latest sACN data and pushes it to the GPIO outputs
    [patchedFixtures] is the [dict] of fixtures patched from the fixture_manager
    [pixelBuffers] is a [dict] of all Pixel buffers created by the GPIO manager
    [sacnShareLock] is a lock file to access the sACN buffer in shared memory
    """

    ############## SUB FUNCTIONS DEF ##############

    def sigterm_handler(signal, frame):
        getGpioLogger().info(f"GPIO worker - SIGTERM [{signal}] received")
        global interrupted
        interrupted = True
        logger.info(f"GPIO worker [{getpid()}] exiting...")
        sacnShareQueue.close()
        blackoutAll()
        sys.exit(0)

    def sigint_handler(signal, frame):
        # getGpioLogger().info(f"SIGINT [{signal}] received.")
        pass

    def blackoutAll():
        """
        Blackout all outputs
        """
        for gpioPin in pixelBuffers.keys():
            pixelBuffers[gpioPin].fill([0, 0, 0])
            pixelBuffers[gpioPin].show()

    ###############################################

    global interrupted
    interrupted = False

    # SIGTERM receiver signal from main process
    signal.signal(signal.SIGTERM, sigterm_handler)
    # Overwrite SIGINT handler inherited from main process
    signal.signal(signal.SIGINT, sigint_handler)

    try:
        initGpioLogger()
    except Exception as err:
        print(f"Failed to init gpio logger: {err}")
        blackoutAll()
        sys.exit(0)

    logger = getGpioLogger()

    refreshDelta = timedelta(microseconds=(pow(10, 6) / WORKER_LED_REFRESH_RATE))

    logger.info(f"GPIO worker [{getpid()}] active")

    # Main loop
    while not interrupted:

        raw = sacnShareQueue.get()  # blocking call

        loopStartTs = datetime.now()

        sacnData = {}
        # Convert json string (required for Queue) back to UniverseData class instance
        for uni in raw.keys():
            sacnData[int(uni)] = UniverseData.fromDict(raw[uni])

        jsonConvertTs = datetime.now()

        tmp = list(set(pixelBuffers.keys()).difference(patchedFixtures.keys()))
        if tmp:
            # corner case: there are GPIO outs in pixelBuffers that are not present in patchedFixtures
            logger.error(
                f"GPIO outputs {[i.name for i in tmp]} are declared in GPIOmanager but not FixtureManager. Cannot update LEDs state."
            )
            return

        # For every declared gpio output
        for gpioPin in patchedFixtures.keys():

            # Keep track of the offset of the current pixel in the PixelBuffer
            offsetInQueue = 0

            # All fixtures in the same GPIO output are of the same type (rgb8, rgw16 etc)
            # Use first fixture in the chain to lookup vars
            # Init defaults
            patch_px_type = None
            patch_profile_size = 0
            patch_ch_offset = ()
            patch_ch_count = 0
            patch_ch_info = ()
            tmpPx = Pixel()

            # For each fixture patch
            for fixturePatch in patchedFixtures[gpioPin]:

                # For first patch in the GPIO output
                if not patch_px_type:
                    patch_px_type = fixturePatch.pixel_type
                    patch_profile_size = fixturePatch.pixel_type.profile_size
                    patch_ch_offset = fixturePatch.pixel_type.channels_offset
                    patch_ch_count = fixturePatch.pixel_type.channel_count
                    patch_ch_info = fixturePatch.pixel_type.channels
                    # Make temp single pixel buffer, overwritten for every pixel in the output
                    match patch_px_type:
                        # case Fixture.PX_RGB_8:
                        #     tmpPx = Pixel(bitDepth=8)
                        # case Fixture.PX_RGBW_8:
                        #     tmpPx = Pixel(bitDepth=8)
                        # case Fixture.PX_RGB_16:
                        #     tmpPx = Pixel(bitDepth=16)
                        # case Fixture.PX_RGBW_16:
                        #     tmpPx = Pixel(bitDepth=16)
                        case _:
                            # Generalization given only RGB8 is supported atm
                            tmpPx = Pixel(bitDepth=8)

                # Do not write this GPIO output if non-RGB8 fixtures are defined
                # Catch-all for non supported fixture types
                if patch_px_type != Fixture.PX_RGB_8:
                    continue

                # Skip this fixture if its universe data isn't present
                if fixturePatch.universe not in sacnData:
                    continue
                patch_uni_data = sacnData[fixturePatch.universe].dmxData

                tmpValue = 0  # temp value for single dmx channel

                # For every pixel in the fixture patch
                for px in range(fixturePatch.pixel_count):

                    # reset tmpPx
                    tmpPx.red = 0
                    tmpPx.green = 0
                    tmpPx.blue = 0
                    tmpPx.white = 0

                    # For every channel in the pixel
                    for pxch in range(patch_ch_count):
                        # Read channel value from sACNdata
                        match (patch_ch_info[pxch].depth):
                            # case ChannelDepth.D8:
                            # # 8 bit case
                            # case ChannelDepth.D16:
                            # # 16 bit case
                            case _:
                                # Generalization given only 8 bit is supported atm
                                dmxAddr = (
                                    fixturePatch.start_channel
                                    + px * patch_profile_size
                                    + patch_ch_offset[pxch]
                                )
                                tmpValue = patch_uni_data[dmxAddr - 1]

                        # Store tmpValue in tmpPixel
                        match (patch_ch_info[pxch].label):
                            case FixtureChannelName.RED:
                                tmpPx.red = tmpValue
                            case FixtureChannelName.GREEN:
                                tmpPx.green = tmpValue
                            case FixtureChannelName.BLUE:
                                tmpPx.blue = tmpValue
                            case FixtureChannelName.WHITE:
                                tmpPx.white = tmpValue

                    # store pixel value in the real gpio pixel buffer
                    pixelBuffers[gpioPin][offsetInQueue] = tmpPx.asTuple(
                        order=pixelBuffers[gpioPin].byteorder
                    )
                    offsetInQueue += 1

        dataProcessTs = datetime.now()

        # Push update to led strips
        for gpioPin in pixelBuffers.keys():
            pixelBuffers[gpioPin].show()

        # Calc elapsed loop time
        endTs = datetime.now()
        loopDelta = endTs - loopStartTs
        if loopDelta > refreshDelta:
            logger.warning(
                (
                    f"GPIO worker - cycle overrun by {1000*(loopDelta-refreshDelta).total_seconds():.2f}ms :: "
                    f"jsonConvert={1000*(jsonConvertTs-loopStartTs).total_seconds():.2f}ms || "
                    f"dataProcess={1000*(dataProcessTs-jsonConvertTs).total_seconds():.2f}ms || "
                    f"gpio={1000*(endTs-dataProcessTs).total_seconds():.2f}ms"
                )
            )

    logger.info(f"GPIO worker [{getpid()}] exiting...")
    sacnShareQueue.close()
    blackoutAll()

    return

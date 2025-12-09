from multiprocessing import Queue, get_context
from typing import List

from .gpio_process import processSacnToGPIO
from .gpio_rpi import GPIO, Pi5PixelBuffer
from .process_mgmt import workerPidFile
from .project_logger import getMainLogger
from .fixture_manager import FixtureManager, FixturePatch
from .fixture_definitions import Fixture


class GpioManager:
    """
    Reads patched fixtures and allocates them to their GPIO output.
    Monitors sACN data and updates led strips accordingly.
    Only supports "rgb8" pixels.
    """

    _logger = getMainLogger()
    """
    Frequency at which to update the WS2812 lights data [Hz]
    """

    def __init__(self, fix_mgr: FixtureManager, sacnShareQueue: Queue):
        """
        [fix_mgr] is an instance of [fixture_manager] class
        [sacnShareQueue] is a Queue to let the GPIO workder access the sACN buffer
        """
        self._sacnShareQueue = sacnShareQueue
        self._fix_mgr = fix_mgr
        self._pixelBuffers : dict[GPIO, Pi5PixelBuffer] = {}

        self._process = None
        """
        Reference to the process refreshing sACN data
        """

        self._makePixelBuffers()

    def __del__(self):
        # Only stop if there's an active process
        if self._process:
            try:
                self.stop()
            except Exception:
                pass  # Ignore errors during shutdown

    def _makePixelBuffers(self):
        """
        Read fixture patches and allocate pixel buffers of required size
        Internal only.
        """
        patchedFixtures: dict[GPIO, List[FixturePatch]] = self._fix_mgr.get_fixtures_all()

        for gpioOut in patchedFixtures.keys():
            outPixCount = 0
            rgbOrder = ""  # "RGB" "BRG" etc
            patchError = False  # if True do not make a Pixel Buffer for this output

            for fixPatch in patchedFixtures[gpioOut]:
                if fixPatch.pixel_type == Fixture.PX_RGB_8:
                    # Add up pixel count on gpio output
                    outPixCount += fixPatch.pixel_count
                    # All fixtures in the GPIO output are of the same type (rgb8, rgw16 etc)
                    # Use first one in the chain to determine rgb order
                    if not rgbOrder:
                        rgbOrder = fixPatch.pixel_type.channel_order
                else:
                    # for non rgb8 pixel type found >> error
                    self._logger.error(
                        f"Unable to patch fixture [{fixPatch.label}] to [{gpioOut}]. GPIO module only supports [{Fixture.PX_RGB_8.label}] pixels"
                    )
                    patchError = True

            if not patchError and (outPixCount > 0) and rgbOrder:
                self._pixelBuffers[gpioOut] = Pi5PixelBuffer(
                    gpioOut.toBoardPin(),
                    outPixCount,
                    auto_write=False,
                    byteorder=rgbOrder,
                )
            else:
                self._logger.error(f"Skipped patching to output [{gpioOut}].")

    def start(self):
        """
        Start a new process dedicated to piping the latest sACN data to the GPIO outputs.
        """
        self._process = get_context("spawn").Process(
            target=processSacnToGPIO,
            args=(
                self._fix_mgr.get_fixtures_all(),
                self._pixelBuffers,
                self._sacnShareQueue,
            ),
        )
        self._process.start()
        if self._process and self._process.pid:
            self._logger.info(f"Started GPIO worker process [{self._process.pid}]...")
            workerPidFile.write(self._process.pid)
        else:
            raise RuntimeError(f"Failed to start GPIO worker process")

    def stop(self):
        """
        Stop process dedicated to piping the latest sACN data to the GPIO outputs.
        Blocking call.
        """
        if self._process:
            self._logger.info(f"Stopping GPIO worker process [{self._process.pid}]...")
            # terminate worker process and wait for it to finish
            self._process.terminate()
            self._process.join()
            self._process.close()
            self._process = None
            # clear sACN Queue
            if self._sacnShareQueue:
                self._sacnShareQueue.close()
                self._sacnShareQueue = None
        else:
            self._logger.info(
                f"GPIO worker process has not been created - unable to terminate"
            )

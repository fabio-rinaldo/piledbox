from typing import List

from .fixture_definitions import *
from .gpio_rpi import GPIO
from .project_logger import getMainLogger
from .config_models import FullConfig


class FixtureManager:
    """
    Parses input config and patches all led strips - instancing a fixture patch object for each strip
    """

    _logger = getMainLogger()

    def __init__(self, cfg: FullConfig):
        self._by_out: dict[GPIO, List[FixturePatch]] = {}
        """All patched led strips sorted by gpio output, then priority in the queue"""
        self._by_uni: dict[int, List[FixturePatch]] = {}
        """All patched led strips sorted by universe, then start channel"""
        self._patch_fixtures(cfg)

    def _validate_cfg(self, fullCfg: FullConfig):
        """
        Validates input yaml config file\n
        Checks if any strip outsizes a single universe\n
        Checks label IDs are unique\n
        """
        tmp_valid = True
        cfg = fullCfg.outputs
        declared_outputs = [out for out in cfg.keys()]  # out1, out2, out3, out4
        declared_gpio = []
        declared_labels = []
        logmessage = ""

        for out in declared_outputs:
            declared_strips = [strip for strip in cfg[out].strips]
            if cfg[out].gpio in declared_gpio:
                logmessage += f"Pin [{cfg[out].gpio}] used on multiple outputs\n"
                tmp_valid = False
            else:
                declared_gpio.append(cfg[out].gpio)

            for strip in declared_strips:
                if strip.label in declared_labels:
                    logmessage += f"Strip [{out} > {strip.label}]: label used on multiple strips\n"
                    tmp_valid = False
                else:
                    declared_labels.append(strip.label)

                profile_size = Fixture.from_string(cfg[out].pixel_type).profile_size

                end_channel = strip.start_channel - 1 + strip.pixel_count * profile_size
                if end_channel > DMX_UNI_SIZE:
                    logmessage += f"Strip [{out} > {strip.label}] does not fit in a single DMX universe\n"
                    tmp_valid = False

        if not tmp_valid:
            self._logger.error("Invalid DMX configuration")
            raise ValueError(logmessage)
        else:
            self._logger.info("Valid DMX configuration")

    def _patch_fixtures(self, fullCfg: FullConfig):
        """
        Validates cfg file first, then patches fixtures accordingly
        """
        self._validate_cfg(fullCfg)
        cfg = fullCfg.outputs
        declared_outputs = [out for out in cfg]
        self._by_out.clear()
        self._by_uni.clear()

        for out in declared_outputs:
            declared_strips = [strips for strips in cfg[out].strips]
            self._by_out[cfg[out].gpio] = []
            strip_queue_pos = 0
            for strip in declared_strips:
                new_patch = FixturePatch(
                    label=strip.label,
                    pixel_type=Fixture.from_string(cfg[out].pixel_type),
                    pixel_count=strip.pixel_count,
                    universe=strip.universe,
                    start_channel=strip.start_channel,
                    output=cfg[out].gpio,
                    pos_in_out_queue=strip_queue_pos,
                )
                strip_queue_pos += 1
                self._by_out[cfg[out].gpio].append(new_patch)

                if not strip.universe in self._by_uni.keys():
                    self._by_uni[strip.universe] = []
                self._by_uni[strip.universe].append(new_patch)

        # Sort self._by_uni fixtures by start address - bubblesort
        for uni in self._by_uni:
            for k in range(len(self._by_uni[uni]) - 1):
                for i in range(len(self._by_uni[uni]) - 1):
                    if (
                        self._by_uni[uni][i].start_channel
                        > self._by_uni[uni][i + 1].start_channel
                    ):
                        tmp1 = self._by_uni[uni][i]
                        tmp2 = self._by_uni[uni][i + 1]
                        self._by_uni[uni][i] = tmp2
                        self._by_uni[uni][i + 1] = tmp1

    def get_fixtures_all(self) -> dict[GPIO, List[FixturePatch]]:
        """Return all fixtures sorted by output and queue position"""
        return self._by_out

    def get_fixtures_by_uni(self, universe: int) -> list[FixturePatch]:
        """Returns only fixtures on that universe, ordered by DMX starting channel"""
        if universe in self._by_uni.keys():
            return self._by_uni[universe]
        else:
            return []

    def get_fixtures_by_out_uni(
        self, output: GPIO, universe: int
    ) -> list[FixturePatch]:
        """Return only fixtures on that output, whose source universe matches, ordered by output queue position"""
        if output in self._by_out.keys():
            tmp: list[FixturePatch] = []
            for patch in self._by_out[output]:
                if patch.universe == universe:
                    tmp.append(patch)
            return tmp
        else:
            return []

    def get_fixtures_by_out(self, output: GPIO) -> list[FixturePatch]:
        """Returns only fixtures on that output, ordered by output queue position"""
        if output in self._by_out.keys():
            return self._by_out[output]
        else:
            return []

    def get_fixtures(
        self, output: GPIO | None = None, universe: int = 0
    ) -> List[FixturePatch] | dict[GPIO, List[FixturePatch]]:
        """
        Returns all patched fixtures in a tuple format \n
        if output is specified, returns only fixtures on that output, ordered by output queue position \n
        if universe is specified, returns only fixtures on that universe, ordered by dmx starting channel \n
        if both are specified, return only fixtures on that output, whose source universe matches, ordered by output queue position \n
        if none is specified, return all fixtures sorted by output and queue position
        """
        if output == None and universe > 0:
            # Single universe
            return self.get_fixtures_by_uni(universe)
        elif output != None and universe <= 0:
            # Single output
            return self.get_fixtures_by_out(output)
        elif output != None and universe > 0:
            # Filter by output then universe
            return self.get_fixtures_by_out_uni(output, universe)
        else:
            # All outputs
            return self.get_fixtures_all()

    def get_universe_list(self) -> tuple[int, ...]:
        """
        Returns tuple with all universe IDs with a patched fixture
        """
        return tuple(self._by_uni.keys())

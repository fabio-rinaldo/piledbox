from enum import StrEnum, IntEnum, Enum

from pydantic import BaseModel, Field, computed_field
from .gpio_rpi import GPIO


SACN_UNI_MAX = 63999
"""
Max accepted sACN universe id
"""

DMX_UNI_SIZE = 512
"""
Channel count of a standard DMX universe
"""


class FixtureChannelName(StrEnum):
    """
    Class to standarized fixture channel labels
    """

    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    WHITE = "white"


class ChannelDepth(IntEnum):
    """
    Depth of a single DMX channel, 8 or 16 bit supported. Value expressed as byte count ( eg. 1, 2 ).
    """

    D8 = 1
    D16 = 2

    @property
    def bitCount(self) -> int:
        """Channel depth in bits (eg. 8, 16)"""
        return 8 * self.value

    @property
    def byteCount(self) -> int:
        """Channel depth in bits (eg. 1, 2)"""
        return self.value


#######################
### FIXTURE CHANNEL ###
#######################


class FixtureChannel(Enum):
    """Defines a standard channel function in a DMX fixture"""

    R8 = (
        FixtureChannelName.RED,  # label
        "Red light channel 8bit",  # description
        0,  # default value
        ChannelDepth.D8,  # channel depth
    )
    G8 = (FixtureChannelName.GREEN, "Green light channel 8bit", 0, ChannelDepth.D8)
    B8 = (FixtureChannelName.BLUE, "Blue light channel 8bit", 0, ChannelDepth.D8)
    W8 = (FixtureChannelName.WHITE, "White light channel 8bit", 0, ChannelDepth.D8)
    R16 = (FixtureChannelName.RED, "Red light channel 16bit", 0, ChannelDepth.D16)
    G16 = (FixtureChannelName.GREEN, "Green light channel 16bit", 0, ChannelDepth.D16)
    B16 = (FixtureChannelName.BLUE, "Blue light channel 16bit", 0, ChannelDepth.D16)
    W16 = (FixtureChannelName.WHITE, "White light channel 16bit", 0, ChannelDepth.D16)

    @property
    def label(self) -> FixtureChannelName:
        return self.value[0]

    @property
    def dsc(self) -> str:
        """Fixture Channel function description"""
        return self.value[1]

    @property
    def default_value(self) -> int:
        return self.value[2]

    @property
    def depth(self) -> ChannelDepth:
        return self.value[3]

    @property
    def max_value(self) -> int:
        """Maximum value this channel can represent"""
        return (2**self.depth.bitCount) - 1


###############
### FIXTURE ###
###############


class Fixture(Enum):
    """
    Defines a generic LED fixture/pixel made of any number of channels
    """

    #####################################################################################
    ### COMMENT ANY ENUM INSTANCE BELOW HERE TO ENABLE/DISABLE CERTAIN FIXTURE TYPE ###
    #####################################################################################
    PX_RGB_8 = ("rgb8", (FixtureChannel.R8, FixtureChannel.G8, FixtureChannel.B8))
    PX_RGB_16 = ("rgb16", (FixtureChannel.R16, FixtureChannel.G16, FixtureChannel.B16))
    PX_RGBW_8 = (
        "rgbw8",
        (FixtureChannel.R8, FixtureChannel.G8, FixtureChannel.B8, FixtureChannel.W8),
    )
    PX_RGBW_16 = (
        "rgbw16",
        (
            FixtureChannel.R16,
            FixtureChannel.G16,
            FixtureChannel.B16,
            FixtureChannel.W16,
        ),
    )
    #####################################################################################

    @property
    def label(self) -> str:
        """Unique fixture label"""
        return self.value[0]

    @property
    def channels(self) -> tuple[FixtureChannel, ...]:
        """Ordered tuple of fixture channels"""
        return self.value[1]

    @property
    def channel_count(self) -> int:
        """Returns how many channels are in the fixture"""
        return len(self.channels)

    @property
    def channels_offset(self) -> tuple[int, ...]:
        """Returns DMX address offset for each channel"""
        offsets = []
        current_offset = 0
        for channel in self.channels:
            offsets.append(current_offset)
            current_offset += channel.depth.byteCount
        return tuple(offsets)

    @property
    def channel_order(self) -> str:
        """Return a short string representing the order of the channels (RGB BRG etc)"""
        # self.channels[0].label.value
        return "".join(str(item.label[0].capitalize()) for item in self.channels)

    @property
    def profile_size(self) -> int:
        """Returns how many 8-bit DMX channels are used by this fixture"""
        return sum(ch.depth.byteCount for ch in self.channels)

    @classmethod
    def from_string(cls, value: str) -> "Fixture":
        """
        Returns Fixture whose label matches the argument string
        """
        for item in Fixture:
            if item.label == value:
                return item
        raise ValueError(f"[{value} is not a valid Fixture type]")

    @classmethod
    def getFixtureNames(cls) -> list[str]:
        """Return names for all supported Fixture types"""
        return [item.label for item in Fixture]


#####################
### FIXTURE PATCH ###
#####################


class FixturePatchBase(BaseModel):
    """
    Common data for all kinds of patched LED strip classes
    """

    label: str = Field(
        description="Fixture patch label", examples=["front window", "rear door"]
    )
    pixel_count: int = Field(
        ge=1, description="Pixel count in this fixture", examples=[10]
    )
    universe: int = Field(
        ge=1, le=SACN_UNI_MAX, description="Source universe", examples=[22]
    )
    start_channel: int = Field(
        ge=1, le=DMX_UNI_SIZE, description="Start DMX channel", examples=[15, 156]
    )
    output: GPIO = Field(
        description="GPIO pin to which this strip is patched to",
        examples=[GPIO.gpio14, GPIO.gpio23],
    )
    pos_in_out_queue: int = Field(
        ge=0,
        description="Defines the patched fixture position in the gpio pin output queue",
        examples=[0, 1],
    )


class FixturePatchInfo(FixturePatchBase):
    """
    Describes a single patched LED strip
    """

    # Used as response_model for FastAPI
    pixel_type: str = Field(
        description="LED pixel type", examples=[Fixture.PX_RGB_8.label]
    )
    end_channel: int = Field(
        ge=1, le=DMX_UNI_SIZE, description="End DMX channel", examples=[399, 501]
    )


class FixturePatch(FixturePatchBase):
    """
    Describes a single patched LED strip
    """

    # Used in FixtureManager
    pixel_type: Fixture = Field(
        description="LED pixel type", examples=[Fixture.PX_RGB_8]
    )

    @computed_field
    @property
    def end_channel(self) -> int:
        """Calculate end channel based on start channel, pixel count, and pixel type profile size"""
        return self.start_channel + self.pixel_count * self.pixel_type.profile_size - 1

    def toPatchInfo(self) -> FixturePatchInfo:
        """Convert to FixturePatchInfo"""
        return FixturePatchInfo(
            label=self.label,
            pixel_count=self.pixel_count,
            universe=self.universe,
            start_channel=self.start_channel,
            output=self.output,
            pos_in_out_queue=self.pos_in_out_queue,
            pixel_type=self.pixel_type.label,
            end_channel=self.end_channel,
        )

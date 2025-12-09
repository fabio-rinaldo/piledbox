from pydantic import BaseModel, RootModel, Field
from typing import List, Dict, Annotated

from .fixture_definitions import FixturePatchInfo, SACN_UNI_MAX, DMX_UNI_SIZE
from .gpio_rpi import GPIO


class FixturePatchMap(RootModel[Dict[GPIO, List[FixturePatchInfo]]]):
    """Map of all patched fixtures, organized by GPIO output and then by order in output queue"""

    pass


class HostInfo(BaseModel):
    """Info on the host machine"""

    ipv4: str = Field(
        min_length=7,
        max_length=15,
        description="IPv4 address of bound network interface",
        examples=["192.168.80.48"],
    )
    iface: str = Field(
        description="Bound network interface name", examples=["wlan0", "ens18"]
    )
    hostname: str = Field(description="Machine hostname", examples=["rpi-led.local"])


DmxValue = Annotated[
    int,
    Field(ge=0, le=255, description="8 bit DMX channel value", examples=[11, 45, 129]),
]


class UniverseInfo(BaseModel):
    """
    Info on a DMX universe
    """

    universe: int = Field(
        ge=1, le=SACN_UNI_MAX, description="DMX universe number", examples=[18]
    )
    priority: int = Field(
        ge=0, le=200, description="sACN universe priority", examples=["100"]
    )
    sourceName: str = Field(
        description="sACN transmitting source label", examples=["GrandMa v3"]
    )
    dmxData: Annotated[
        list[DmxValue], Field(min_length=DMX_UNI_SIZE, max_length=DMX_UNI_SIZE)
    ]
    latestTimeStamp: str = Field(
        description="Timestamp of latest update", examples=["timestamp"]
    )


class UniverseInfoReport(RootModel[Dict[int, UniverseInfo]]):
    """
    Map of information on all captured sACN universes
    """

    pass

import ipaddress
from typing import Literal
from typing_extensions import Self
from socket import AddressFamily
from enum import StrEnum

import psutil
from pydantic import BaseModel, Field, field_validator, model_validator
from .fixture_definitions import Fixture, DMX_UNI_SIZE, SACN_UNI_MAX
from .gpio_rpi import GPIO


class OutputLabel(StrEnum):
    """
    Label for physical outputs
    """

    OUT1 = "out1"
    OUT2 = "out2"
    OUT3 = "out3"
    OUT4 = "out4"


class LedStrip(BaseModel):
    """
    Single LED strip definition
    """

    label: str
    pixel_count: int = Field(ge=1, le=170)
    universe: int = Field(ge=1, le=SACN_UNI_MAX)  # sACN universe id
    start_channel: int = Field(ge=1, le=DMX_UNI_SIZE)  # start DMX channel


class PinConfig(BaseModel):
    """
    Configuration of a single GPIO output configuration
    """

    gpio: GPIO
    pixel_type: str  # rgb8, rgbw16, etc
    strips: list[LedStrip] = Field(min_length=1)

    @field_validator("pixel_type")
    @classmethod
    def validate_fixture_type(cls, value: str):
        if value not in Fixture.getFixtureNames():
            raise ValueError(f"[{value}] is not a valid pixel type")
        return value


class InputOptions(BaseModel):
    """
    Lighting data input configuration
    """

    protocol: Literal["sacn"]
    mode: Literal["unicast"]
    interface: str = Field(default="")
    """Network interface to bind to. In case of multiple IPs, use first found IP. If spec'd, bind to [ipv4] field."""
    ipv4: str = Field(default="")
    web_gui_port: int = Field(ge=1025, le=65535, default=5010)

    @field_validator("ipv4")
    @classmethod
    def validate_ipv4(cls, value: str) -> str:
        try:
            ipaddress.IPv4Address(value)
        except ValueError:
            raise ValueError(f"Malformed IPv4 address: {value}")

        host_ipv4s = [
            addr.address
            for addrList in psutil.net_if_addrs().values()
            for addr in addrList
            if addr.family == AddressFamily.AF_INET
        ]

        if value in host_ipv4s:
            return value
        else:
            raise ValueError(
                f"Failed to find IPv4 address {value} on any host interface"
            )

    @field_validator("interface")
    @classmethod
    def validate_interface(cls, interface: str) -> str:
        if interface in psutil.net_if_stats():
            if not psutil.net_if_stats()[interface].isup:
                raise ValueError(f"Network interface [{interface}] is not active")
        else:
            raise ValueError(f"Failed to find network interface [{interface}]")
        return interface

    @model_validator(mode="after")
    def validate_InputOpts(self) -> Self:
        # If interface only
        # Get first IP address of interface
        if self.interface and not self.ipv4:
            host_addrs = psutil.net_if_addrs()[self.interface]
            for ipaddr in host_addrs:
                if ipaddr.family == AddressFamily.AF_INET:
                    self.ipv4 = ipaddr.address
                    return self
            raise ValueError(f"Interface {self.interface} has no valid IPv4")

        # If IP only
        # Find interface with given IP
        elif self.ipv4 and not self.interface:
            for iface, addrList in psutil.net_if_addrs().items():
                for addr in addrList:
                    if addr.address == self.ipv4:
                        self.interface = iface
                        return self
            raise ValueError(f"Failed to find IP {self.ipv4} on any host interface")

        # If both
        # Check ip address is valid for that interface
        elif self.ipv4 and self.interface:
            if self.ipv4 in [
                addr.address
                for addr in psutil.net_if_addrs()[self.interface]
                if addr.family == AddressFamily.AF_INET
            ]:
                return self
            else:
                raise ValueError(
                    f"Failed to find {self.ipv4} among '{self.interface}' IPv4 addresses"
                )

        # Both ipv4 and interface not defined
        raise ValueError(
            "Missing 'ipv4' and 'interface'. Either (or both) must be defined."
        )


class FullConfig(BaseModel):
    """
    Full app configuration model
    """

    version: Literal["1.0"]

    input: InputOptions
    outputs: dict[OutputLabel, PinConfig] = Field(min_length=1, max_length=4)

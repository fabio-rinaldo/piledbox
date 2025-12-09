from dataclasses import dataclass
from json import dumps


@dataclass
class UniverseData:
    """
    Class used by sACNmanager to return info about a DMX universe
    """

    universe: int
    priority: int
    sourceName: str
    dmxData: tuple
    latestTimeStamp: str

    def toJson(self) -> str:
        return dumps(self.toDict())

    def toDict(self) -> dict:
        """Convert to dict"""
        return {
            "universe": self.universe,
            "priority": self.priority,
            "sourceName": self.sourceName,
            "dmxData": self.dmxData,
            "latestts": self.latestTimeStamp,
        }

    @staticmethod
    def fromDict(obj: dict) -> "UniverseData | None":
        """
        Create a UniverseData class instance from its corresponding dict representation
        """
        if not isinstance(obj, dict):
            return None
        else:
            try:
                return UniverseData(
                    obj["universe"],
                    obj["priority"],
                    obj["sourceName"],
                    obj["dmxData"],
                    obj["latestts"],
                )
            except Exception as err:
                print(err)
                return None

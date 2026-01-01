from datetime import datetime, timedelta
from dataclasses import dataclass
from multiprocessing import get_context
from queue import Empty

import sacn
from sacn import DataPacket
from .project_logger import getMainLogger
from .fixture_definitions import SACN_UNI_MAX
from .universedata import UniverseData
from .frontend_models import UniverseInfoReport, UniverseInfo
from .misc import WORKER_LED_REFRESH_RATE


@dataclass
class TimedDataPacket:
    """
    Class to represent a received sACN packet with added timestamp
    """

    raw: DataPacket
    """Raw packet data"""
    timeStamp: datetime
    """Timestamp of packet arrival"""

    def __str__(self):
        return f"{self.timeStamp} // Seq:{self.raw.sequence} // Src:{self.raw.sourceName} // Uni:{self.raw.universe} // Prio:{self.raw.priority}"


class sACNmanager:
    """
    Receives and stores sACN data into buffer structures
    """

    _logger = getMainLogger()
    _queueRefreshDelta = timedelta(microseconds=(pow(10, 6) / WORKER_LED_REFRESH_RATE))
    """How often the sacnShareQueue should be updated [microseconds]"""
    _queueSize = 50
    """Size of the sacnShareQueue"""

    def __init__(self, ipAddress: str):
        self._db: dict[int, TimedDataPacket] = {}
        """Dict storing references to all DmxBuffers created"""
        self.lastQueueUpdateTs: dict[int, timedelta] = {}
        """Timestamp when sacnShareQueue was last updated, per universe"""
        self._registeredUniverses: list[int] = []
        """List of universes that have been registered to listen to"""

        self._sACNrx = sacn.sACNreceiver(bind_address=ipAddress)

        self.sacnShareQueue = get_context("spawn").Queue(self._queueSize)
        """Multiprocess queue to send data to GPIO worker"""

    def __del__(self):
        self._sACNrx.stop()

    def start(self):
        """
        Start the sACN receiver thread and cleanup task
        """
        self._logger.info(f"Starting sACN receiver...")
        self._sACNrx.start()
        self._sACNrx.register_listener(
            trigger="availability", func=self._logUniverseAvailability
        )

    def stop(self):
        """Stop the sACN receiver thread, cleanup task, clears sACN shared memory block"""
        self._logger.info(f"Stopping sACN receiver...")
        self._sACNrx.stop()
        # Clear sACN Queue
        if self.sacnShareQueue:
            self.sacnShareQueue.close()
        self.sacnShareQueue = None

    def registerUniverse(self, universe: int):
        """
        Starts receiving data for parameter universe
        """
        if (not isinstance(universe, int)) or (not 1 <= universe <= SACN_UNI_MAX):
            self._logger.warning(
                f"Attempting to register to invalid sACN universe [{universe}]"
            )
            return
        self._registeredUniverses.append(universe)
        self._sACNrx.register_listener(
            trigger="universe", func=self._onPacketReceived, universe=universe
        )
        self._logger.info(f"Now listening on sACN universe [{universe}]")

    def _logUniverseAvailability(self, universe: int, changed):
        if universe in self._registeredUniverses:
            match (changed):
                case "timeout":
                    self._logger.info(
                        f"Current sACN source @ universe [{universe}] has timed out"
                    )
                case "available":
                    self._logger.info(
                        f"A sACN source @ universe [{universe}] is now available"
                    )

    def _onPacketReceived(self, packet: DataPacket):
        """
        Async function called when a new sACN packet is received

        Load sacn DataPacket to internal db with added timestamp

        Internal only
        """
        # Ignore non-DMX-data packets
        if packet.dmxStartCode != 0x00:
            return

        if not packet.universe in self._db.keys():
            self._logger.info(
                f"Receiving new sACN source: uni [{packet.universe}] // prio [{packet.priority}] // name: [{packet.sourceName}]"
            )
        elif (
            self._db[packet.universe].raw.universe != packet.universe
            or self._db[packet.universe].raw.priority != packet.priority
            or self._db[packet.universe].raw.sourceName != packet.sourceName
        ):
            self._logger.info(
                f"Updated sACN source: uni [{packet.universe}] // prio [{packet.priority}] // name: [{packet.sourceName}]"
            )

        # Update sacn data db
        newPacketTs = datetime.now()
        self._db[packet.universe] = TimedDataPacket(packet, newPacketTs)

        # Queue update frequency tied to worker refresh rate
        if (not packet.universe in self.lastQueueUpdateTs.keys()) or (
            (newPacketTs - self.lastQueueUpdateTs[packet.universe])
            >= (self._queueRefreshDelta * 0.9)
        ):
            self.lastQueueUpdateTs[packet.universe] = newPacketTs
            self._updateQueue()

    def _updateQueue(self):
        """
        Push latest sACN data to sacnShareQueue, to share with GPIO worker process

        Internal only
        """
        if not self.sacnShareQueue:
            return
        if not self.sacnShareQueue.full():
            try:
                self.sacnShareQueue.put(self.getAllUniverseDataDict())
            except ValueError as err:
                # self._logger.error(f'Error writing sACN data share: {err}')
                return
        else:
            # try to clear Queue
            try:
                self.sacnShareQueue.get(False)
            except Empty:
                self._logger.error(f"Failed to free space on sACN data share")
                return
            except ValueError:
                # self._logger.error(f'Error writing sACN data share: {err}')
                return
            # try to write again, return if still full
            if not self.sacnShareQueue.full():
                try:
                    self.sacnShareQueue.put(self.getAllUniverseDataDict())
                except ValueError as err:
                    # self._logger.error(f'Error writing sACN data share: {err}')
                    return
            else:
                self._logger.error(f"Failed to write to sACN data share: full buffer")
                return

    def getAvailableUniverses(self) -> tuple[int, ...]:
        """
        Returns all sACN universe IDs currently being captured
        """
        return tuple(self._db.keys())

    def getUniverseData(self, universe: int) -> UniverseData:
        """
        Returns latest data captured for the [universe] parameter
        """
        if universe in self._db.keys():
            return UniverseData(
                self._db[universe].raw.universe,
                self._db[universe].raw.priority,
                self._db[universe].raw.sourceName,
                self._db[universe].raw.dmxData,
                str(self._db[universe].timeStamp),
            )
        else:
            raise IndexError(f"No existing record for universe [{universe}]")

    def getAllUniverseDataDict(self) -> dict[int, dict]:
        """
        Returns latest data for all captured sACN universes as picklable [dict]
        """
        tmp = {}
        for universe in self._db.keys():
            tmpUni = self.getUniverseData(universe)
            tmp[universe] = tmpUni.toDict()
        return tmp

    def getUniverseInfoReport(self) -> UniverseInfoReport:
        """
        Returns latest data for all captured sACN universes
        """
        tmp = {}
        for universe in self._db.keys():
            tmp[universe] = UniverseInfo(
                universe=self._db[universe].raw.universe,
                priority=self._db[universe].raw.priority,
                sourceName=self._db[universe].raw.sourceName,
                dmxData=self._db[universe].raw.dmxData,  # type:ignore
                latestTimeStamp=str(self._db[universe].timeStamp),
            )
        return UniverseInfoReport(tmp)

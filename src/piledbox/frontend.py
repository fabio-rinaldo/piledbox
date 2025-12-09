from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from fastapi.middleware.wsgi import WSGIMiddleware
import os
import sys
from socket import gethostname
from typing import List

from .platform_check import isHostRpi5
from .config_manager import ConfigManager
from .fixture_manager import FixtureManager
from .sacn_manager import sACNmanager
from .project_logger import getMainLogger, getLastLogEntries
from .frontend_models import *
from .process_mgmt import mainPidFile
from .misc import *
from .frontend_dash import PiLedBoxDashApp
from .gpio_manager import GpioManager


class PiLedBoxApp(FastAPI):
    """FastAPI app for PiLedBox"""

    _logger = getMainLogger()

    def __init__(self, *args, configPath: str, **kwargs):

        kwargs.setdefault("title", APPNAME)
        kwargs.setdefault("docs_url", API_PATH.SWAGGER)
        kwargs.setdefault("redoc_url", None)
        kwargs.setdefault("openapi_url", API_PATH.OPENAPI)  # OpenAPI schema
        kwargs.setdefault(
            "description",
            f"A WS28xx LED driver with sACN input for Raspberry Pi5, written in Python",
        )
        super().__init__(*args, **kwargs)

        # Make config manager, load yaml config file and check syntax
        try:
            self.cfg_mgr = ConfigManager(configPath)
        except Exception as err:
            self._logger.error(err)
            exit()

        # Make fixture manager and validate dmx config (no strips larger than 1 universe)
        try:
            self.fix_mgr = FixtureManager(self.cfg_mgr.config)
        except Exception as err:
            self._logger.error(err)
            exit()

        # Write PID file
        mainPid = os.getpid()
        self._logger.info(f"Main process PID is: [{mainPid}]")
        try:
            mainPidFile.write(mainPid)
        except Exception as err:
            self._logger.error(f"Failed to write main PID file: {err}")
            self.stop()

        # Make sACN receiver and listen for relevant universes
        self.sacn_mgr = sACNmanager(self.cfg_mgr.config.input.ipv4)
        self.sacn_mgr.start()
        for uni in self.fix_mgr.get_universe_list():
            self.sacn_mgr.registerUniverse(uni)

        # Check platform the app it's running on
        if isHostRpi5():
            if self.sacn_mgr.sacnShareQueue:
                self.gpio_mgr = GpioManager(self.fix_mgr, self.sacn_mgr.sacnShareQueue)
                self.gpio_mgr.start()
            else:
                # Corner case
                self._logger.error("Failed to start IPC queue to GPIO process")
                self.stop()
        else:
            self.stop()

        # Create and mount Dash status page
        try:
            self.dash_app = PiLedBoxDashApp(
                fix_mgr=self.fix_mgr,
                sacn_mgr=self.sacn_mgr,
                cfg_mgr=self.cfg_mgr,
            )
        except Exception as err:
            self._logger.error(f"Failed to init web dashboard: {err}")
            self.stop()

        self.mount(API_PATH.DASHBOARD, WSGIMiddleware(self.dash_app.server))

        # Register REST API endpoints
        self._register_endpoints()

    def stop(self):
        """
        Gracefully stop the app
        """
        self._logger.info(f"Stopping [{APPNAME}]...")

        if self.gpio_mgr:
            self.gpio_mgr.stop()

        # Stop sACN receiver
        if self.sacn_mgr:
            self.sacn_mgr.stop()

        self._logger.info(f"============== {APPNAME} STOP ================")
        sys.exit(0)

    ######################
    ### API FUNCTIONS ####
    ######################

    def _register_endpoints(self):
        """Register REST endpoints"""

        @self.get("/")
        def root():
            return RedirectResponse(url=API_PATH.DASHBOARD)

        @self.get(
            API_PATH.FIXTURES,
            response_model=FixturePatchMap,
            description="Get all patched fixtures",
        )
        def getFixtures():
            """
            Returns json structure with all patched fixtures
            """
            fixturesMap = self.fix_mgr.get_fixtures_all()
            response_dict = {
                gpio: [fixture.toPatchInfo() for fixture in fixtures]
                for gpio, fixtures in fixturesMap.items()
            }
            return FixturePatchMap(response_dict)

        @self.get(
            API_PATH.HOST_INFO,
            response_model=HostInfo,
            description="Get info on host machine",
        )
        def getHostInfo():
            """
            Returns IP address, network interface and hostname of the host in a json structure
            """
            response = HostInfo(
                ipv4=self.cfg_mgr.config.input.ipv4,
                iface=self.cfg_mgr.config.input.interface,
                hostname=f"{gethostname()}.local",
            )
            return {**response.model_dump()}

        @self.get(
            API_PATH.SACN_DATA,
            response_model=UniverseInfoReport,
            description="Get latest received sACN data",
        )
        def getSacnData():
            """
            Returns full sACN data being captured
            """
            return self.sacn_mgr.getUniverseInfoReport()

        @self.get(
            API_PATH.LOGS,
            response_model=List[str],
            description=f"Get latest log entries. Ordered from most recent @[0] to oldest",
        )
        def getLogs(
            logsQty: int | None = Query(
                min=20,
                max=100,
                description="Number of log entries to retrieve",
                example=30,
            )
        ):
            """
            Returns latest project logger entries. Ordered from most recent @[0] to oldest.
            """
            if logsQty:
                try:
                    logsQty = int(logsQty)
                    if logsQty > 0:
                        return getLastLogEntries(logsQty)
                    else:
                        return getLastLogEntries()
                except ValueError as err:
                    return getLastLogEntries()
            else:
                return getLastLogEntries()

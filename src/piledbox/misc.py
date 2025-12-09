from pathlib import Path
import platform

############
### MISC ###
############

APPNAME = "piledbox"

ASGI_TIMEOUT = 1
"""
Time in [seconds] allowed to HTTP requests to complete before the ASGI force shuts down. Used in shutdown procedure
"""

SIGTERM_TIMEOUT = 2
"""
Time in [seconds] allowed to processes to gracefully shutdown on SIGTERM
"""

WORKER_LED_REFRESH_RATE = 40
"""
Rate at which the GPIO worker process refreshes the WS28xx outputs, in [Hz]
"""

#####################
### PATHS ON DISK ###
#####################


def _get_data_dir() -> Path:
    """
    Calculate the app data directory path based on platform.
    """
    match platform.system():
        case "Windows":
            return Path.home() / "AppData" / "Local" / APPNAME
        case _:  # Linux and Mac
            return Path(f"/tmp/{APPNAME}")


class PATH:
    """
    Class to store all relevant paths on disk
    """

    DATA_DIR = _get_data_dir()
    """Path to app data directory"""

    LOGS_DIR = DATA_DIR / "logs"
    """Path of logs directory"""
    PID_MAIN = DATA_DIR / "main.pid"
    """Path of main process pid file"""
    PID_WORKER = DATA_DIR / "worker.pid"
    """Path of worker process pid file"""


##################
### REST PATHS ###
##################


class API_PATH:
    """
    Class to store all REST API endpoint paths
    """

    API = "/api"

    SWAGGER = API + "/docs"
    """Endpoint path to Swagger UI documentation"""

    OPENAPI = API + "/openapi.json"
    """Endpoint path to OpenAPI Json file"""

    FIXTURES = API + "/fixtures"

    HOST_INFO = API + "/host-info"

    SACN_DATA = API + "/sacn-data"

    LOGS = API + "/logs"

    DASHBOARD = "/dashboard"

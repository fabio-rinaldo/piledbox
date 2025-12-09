from pathlib import Path
import asyncio

import psutil
from .misc import PATH


shutdown_event = asyncio.Event()
"""
Triggers when the app should shutdown
"""


async def stopWatchTask():
    """
    Async task that terminates when the app should shutdown
    """
    await shutdown_event.wait()  # Waits for shutdown_event


def is_process_running(pid: int):
    """
    Check if a Python interpreter process is running
    """
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.name() in ["python", "python.exe"]
    except psutil.NoSuchProcess:
        return False


####################
##### PID FILES ####
####################


class PidInvalidError(Exception):
    """PID file doesn't exist, contains invalid data, or process not running"""

    pass


class PidFile:
    """
    Manages reading and writing of PID files
    """

    def __init__(self, path: Path):
        """
        Initialize PidFile with a path

        Args:
            path: The pathlib.Path object for the PID file location
        """
        self.path = path

    def _ensure_data_dir(self):
        """
        Ensure the parent directory of the PID file exists

        Raises:
            OSError: if directory creation fails
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, pid: int):
        """
        Write process PID to file

        Args:
            pid: The process ID to write

        Raises:
            ValueError: if pid <= 0
            OSError: if directory creation or write fails
        """
        # Validate pid is positive integer
        if not isinstance(pid, int) or pid <= 0:
            raise ValueError(f"PID must be a positive integer, got: {pid}")

        # Ensure parent directory exists
        self._ensure_data_dir()

        # Write PID to file
        self.path.write_text(str(pid))

    def read(self) -> int:
        """
        Read process PID from file and validate process exists

        Returns:
            The process ID of a running process

        Raises:
            PidInvalidError: if PID file doesn't exist, contains invalid data, or process not running
            OSError: if file read fails due to permissions or I/O error
        """
        # Check if file exists
        if not self.path.exists():
            raise PidInvalidError(f"PID file not found: {self.path}")

        # Read file content - let OSError propagate (except FileNotFoundError)
        try:
            content = self.path.read_text()
        except FileNotFoundError:
            # Shouldn't happen since we checked exists(), but handle it anyway
            raise PidInvalidError(f"PID file not found: {self.path}")
        except OSError:
            # Permission denied, I/O error, etc. - let it propagate
            raise

        # Strip whitespace and parse as integer
        content = content.strip()
        try:
            pid = int(content)
        except ValueError:
            raise PidInvalidError(
                f"Invalid PID in file {self.path}: '{content}' is not a valid integer"
            )

        # Validate pid is positive
        if pid <= 0:
            raise PidInvalidError(
                f"Invalid PID in file {self.path}: {pid} must be positive"
            )

        # Check if process exists
        if not psutil.pid_exists(pid):
            raise PidInvalidError(f"Process {pid} not running")

        return pid


# Singleton instances for main and worker PID files
mainPidFile = PidFile(PATH.PID_MAIN)
workerPidFile = PidFile(PATH.PID_WORKER)

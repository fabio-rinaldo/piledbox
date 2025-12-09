import platform

from .project_logger import getMainLogger


def isHostRpi5() -> bool:
    """
    Check if app if running on a Raspberry Pi 5
    """
    logger = getMainLogger()
    hostUname = platform.uname()

    if hostUname.system == "Linux" and hostUname.machine == "aarch64":
        filepath = "/proc/device-tree/model"
        try:
            with open(filepath) as file:
                result = file.read()
        except Exception as err:
            logger.error(f"Error reading file [{filepath}]: {err}")
            logger.error("Couldn't validate host platform")
            return False
        if "Raspberry Pi 5" in result:
            logger.info(f"Valid platform found: [{result}]")
            return True
    else:
        logger.error(f"Found invalid host platform: {hostUname}")
        return False

    return False

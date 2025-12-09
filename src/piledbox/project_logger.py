import logging.config
import atexit
from datetime import datetime
from logging.handlers import QueueHandler

from .misc import PATH


# Track which loggers have been initialized
_initialized_loggers = set()

# Internal module constants
_MAIN_LOG_FILENAME = "log_main.log"
_GPIO_LOG_FILENAME = "log_gpio.log"
_MAIN_QUEUE_HANDLER_NAME = "main_queue_handler"
_GPIO_QUEUE_HANDLER_NAME = "gpio_queue_handler"
_MAIN_LOGGER_NAME = "master"
_GPIO_LOGGER_NAME = "gpioworker"
_MAIN_LOG_PATH = PATH.LOGS_DIR / _MAIN_LOG_FILENAME
_GPIO_LOG_PATH = PATH.LOGS_DIR / _GPIO_LOG_FILENAME


def getMainLogger():
    """
    Returns reference to the main project logger
    """
    return logging.getLogger(_MAIN_LOGGER_NAME)


def getGpioLogger():
    """
    Returns reference to the GPIO worker logger
    """
    return logging.getLogger(_GPIO_LOGGER_NAME)


def getLastLogEntries(number: int = 20) -> list[str]:
    """
    Returns the last [number] log entries from the main log file
    """
    if (not isinstance(number, int)) or (number < 1) or (number > 2000):
        getMainLogger().warning(f"Attempting to access invalid [{number}] log entries")
        return [f"[{str(datetime.now)}]: Error attempting to access log file"]

    try:
        with open(_MAIN_LOG_PATH) as logfile:
            # get last N lines, or less if < N
            logs = []
            for line in logfile.readlines()[-number:]:
                logs.append(line[:-1])
            return logs
    except Exception as err:
        getMainLogger().error(f"{err}")
        return [f"[{str(datetime.now())}]: Error attempting to access log file - {err}"]


def _initLogger(label: str):
    """
    Internal function to initialize a logger.

    Args:
        label: Logger name (_MAIN_LOGGER_NAME or _GPIO_LOGGER_NAME)

    Raises:
        ValueError: If label doesn't match a known logger name
    """
    # Map label to the appropriate config and constants
    if label == _MAIN_LOGGER_NAME:
        init_key = "main"
        config = main_logger_config
        handler_name = _MAIN_QUEUE_HANDLER_NAME
        logger_getter = getMainLogger
    elif label == _GPIO_LOGGER_NAME:
        init_key = "gpio"
        config = gpio_logger_config
        handler_name = _GPIO_QUEUE_HANDLER_NAME
        logger_getter = getGpioLogger
    else:
        raise ValueError(f"Unknown logger label: {label}")

    # Check if already initialized
    if init_key in _initialized_loggers:
        logger_getter().warning("Ignoring attempt to init logger multiple times")
        return

    # Create logs directory if it doesn't exist
    if not PATH.LOGS_DIR.is_dir():
        try:
            PATH.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as err:
            raise err

    # Initialize the logger
    logging.config.dictConfig(config=config)
    qh = logging.getHandlerByName(handler_name)
    if qh is not None and isinstance(qh, QueueHandler) and qh.listener is not None:
        qh.listener.start()
        atexit.register(qh.listener.stop)
    _initialized_loggers.add(init_key)


def initMainLogger():
    """
    Init custom logger.
    Run only once.
    """
    _initLogger(_MAIN_LOGGER_NAME)


def initGpioLogger():
    """
    Init custom logger.
    Run only once.
    """
    _initLogger(_GPIO_LOGGER_NAME)


main_logger_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(levelname)s: %(message)s",
        },
        "detailed": {
            "format": "[%(levelname)s|%(module)s|L%(lineno)d] %(asctime)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout",
        },
        "stderr": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "WARNING",
            "stream": "ext://sys.stderr",
        },
        "file-main": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": _MAIN_LOG_PATH,
            "maxBytes": 1000000,
            "backupCount": 3,
        },
        _MAIN_QUEUE_HANDLER_NAME: {
            "class": "logging.handlers.QueueHandler",
            "handlers": ["stdout", "file-main"],
            "respect_handler_level": True,
        },
    },
    "loggers": {
        _MAIN_LOGGER_NAME: {
            "level": "DEBUG",
            "handlers": [_MAIN_QUEUE_HANDLER_NAME],
            "propagate": False,
        },
    },
}


gpio_logger_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(levelname)s: %(message)s",
        },
        "detailed": {
            "format": "[%(levelname)s|%(module)s|L%(lineno)d] %(asctime)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout",
        },
        "stderr": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "WARNING",
            "stream": "ext://sys.stderr",
        },
        "file-gpio": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": _GPIO_LOG_PATH,
            "maxBytes": 1000000,
            "backupCount": 3,
        },
        _GPIO_QUEUE_HANDLER_NAME: {
            "class": "logging.handlers.QueueHandler",
            "handlers": ["stdout", "file-gpio"],
            "respect_handler_level": True,
        },
    },
    "loggers": {
        _GPIO_LOGGER_NAME: {
            "level": "DEBUG",
            "handlers": [_GPIO_QUEUE_HANDLER_NAME],
            "propagate": False,
        }
    },
}

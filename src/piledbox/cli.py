import sys
import signal
import argparse
from enum import StrEnum

from hypercorn.config import Config
from hypercorn.asyncio import serve
import psutil
import asyncio
from .project_logger import initMainLogger, getMainLogger
from .frontend import PiLedBoxApp
from .misc import ASGI_TIMEOUT, APPNAME, SIGTERM_TIMEOUT
from .process_mgmt import shutdown_event, mainPidFile, workerPidFile, stopWatchTask


class Commands(StrEnum):
    """
    Enum to represent all possible CLI commands
    """

    START = "start"
    STOP = "stop"


def main() -> None:

    def signal_handler(rcv_signal, frame):
        if rcv_signal == signal.SIGINT:
            logger.info(f"Main Process -  SIGINT [{rcv_signal}] received")
        elif rcv_signal == signal.SIGTERM:
            logger.info(f"Main Process -  SIGTERM [{rcv_signal}] received")
        # Schedule the event to be set in the event loop thread
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(shutdown_event.set)
        except RuntimeError:
            # No running loop, set directly
            # Corner case
            shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        initMainLogger()
    except Exception as err:
        print(f"Failed to init main logger: {err}")
        sys.exit(0)
    logger = getMainLogger()

    parser = argparse.ArgumentParser(
        prog=f"{APPNAME}",
        description="A Python tool to drive WS28xx LED tape from sACN.",
    )
    cmdparser = parser.add_subparsers(dest="command")
    cmdparser.required = True
    startparser = cmdparser.add_parser(
        Commands.START, help=f"Start {APPNAME} - option to spec YAML config file path"
    )
    startparser.add_argument(
        "--config",
        "-c",
        default="./config.yaml",
        help="""
            Path to YAML config file.
            Defaults to "%(default)s"
            """,
    )
    cmdparser.add_parser(Commands.STOP, help=f"Stop {APPNAME}")

    if len(sys.argv) > 1:
        try:
            cli_args = parser.parse_args(sys.argv[1:])

        except Exception as err:
            logger.error(err)
            return

        match (cli_args.command):

            case Commands.START:
                # Do not start a second instance
                prev_instance_running = False
                try:
                    mainPid = mainPidFile.read()
                    logger.error(f"{APPNAME} main process [{mainPid}] still running")
                    prev_instance_running = True
                except OSError as err:
                    logger.error(f"Failed to access main PID file: {err}")
                    return
                except Exception as err:
                    pass
                try:
                    workerPid = workerPidFile.read()
                    logger.error(
                        f"{APPNAME} worker process [{workerPid}] still running"
                    )
                    prev_instance_running = True
                except OSError as err:
                    logger.error(f"Failed to access worker PID file: {err}")
                    return
                except Exception as err:
                    pass
                if prev_instance_running:
                    logger.error(f"Stop current instance before starting a new one.")
                    return

                logger.info(f"============== {APPNAME} START ==============")

                app = PiLedBoxApp(configPath=cli_args.config)

                logger.info(
                    f"Starting frontend at http://{app.cfg_mgr.config.input.ipv4}:{app.cfg_mgr.config.input.web_gui_port}..."
                )

                asgiConfig = Config()
                asgiConfig.bind = f"{app.cfg_mgr.config.input.ipv4}:{app.cfg_mgr.config.input.web_gui_port}"
                asgiConfig.graceful_timeout = ASGI_TIMEOUT

                # Blocking call
                asyncio.run(
                    serve(
                        app, asgiConfig, shutdown_trigger=stopWatchTask  # type: ignore
                    )
                )

                # Graceful shutdown
                app.stop()

            case Commands.STOP:
                # Get PIDs
                mainPid = 0
                workerPid = 0
                try:
                    mainPid = mainPidFile.read()
                except OSError as err:
                    logger.error(f"Failed to access main PID file: {err}")
                    return
                except Exception as err:
                    pass
                try:
                    workerPid = workerPidFile.read()
                except OSError as err:
                    logger.error(f"Failed to access worker PID file: {err}")
                    return
                except Exception as err:
                    pass

                if mainPid:
                    # Send SIGTERM to main process only
                    mainProc = psutil.Process(mainPid)
                    workerProc: psutil.Process | None = None
                    if workerPid > 0:
                        workerProc = psutil.Process(workerPid)
                    else:
                        logger.warning(
                            f"Found {APPNAME} main [{mainPid}] but no worker process running"
                        )
                    try:
                        logger.info(f"Stopping {APPNAME} main [{mainPid}]...")
                        mainProc.send_signal(signal.SIGTERM)

                        mainProc.wait(timeout=SIGTERM_TIMEOUT)
                        logger.info(f"{APPNAME} main [{mainPid}] stopped gracefully")

                        if workerProc:
                            try:
                                workerProc.wait(timeout=SIGTERM_TIMEOUT)
                                logger.info(
                                    f"{APPNAME} worker [{workerPid}] stopped gracefully"
                                )
                            except psutil.TimeoutExpired:
                                workerProc.kill()
                                logger.warning(
                                    f"{APPNAME} worker [{workerPid}] killed forcefully"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error stopping {APPNAME} worker [{workerPid}]: {e}"
                                )

                    except psutil.TimeoutExpired:
                        mainProc.kill()
                        logger.warning(f"{APPNAME} main [{mainPid}] killed forcefully")
                        if workerProc:
                            workerProc.kill()
                            logger.warning(
                                f"{APPNAME} worker [{workerPid}] killed forcefully"
                            )
                    except Exception as e:
                        logger.error(f"Error stopping {APPNAME} main [{mainPid}]: {e}")

                elif not mainPid and workerPid:
                    # Send SIGTERM to worker only
                    logger.warning(
                        f"Found {APPNAME} worker [{workerPid}] but no main process running"
                    )
                    workerProc = psutil.Process(workerPid)
                    try:
                        logger.info(f"Stopping {APPNAME} worker [{workerPid}]...")
                        workerProc.send_signal(signal.SIGTERM)
                        workerProc.wait(timeout=SIGTERM_TIMEOUT)
                        logger.info(
                            f"{APPNAME} worker [{workerPid}] stopped gracefully"
                        )
                    except psutil.TimeoutExpired:
                        workerProc.kill()
                        logger.warning(
                            f"{APPNAME} worker [{workerPid}] killed forcefully"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error stopping {APPNAME} worker [{workerPid}]: {e}"
                        )

                else:
                    logger.info(f"{APPNAME} is not running")
                    return

    else:
        logger.error(f"Missing argument")

import yaml
from .project_logger import getMainLogger
from .config_models import FullConfig


class ConfigManager:
    """
    Class to read the YAML config file.
    Checks YAML syntax and mid-level data validitation
    """

    _logger = getMainLogger()

    def __init__(self, config_path: str):
        self.path = config_path

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, path: str) -> None:
        self._path = path
        self.load()

    @property
    def config(self) -> FullConfig:
        """
        Validated YAML file represented at Python dict
        """
        return self._config

    def load(self) -> FullConfig:
        """
        Load YAML config file
        """
        with open(self.path, "r") as file:
            raw_cfg = yaml.safe_load(file)

        self._config = FullConfig(**raw_cfg)
        self._logger.info("Valid YAML configuration")
        return self._config

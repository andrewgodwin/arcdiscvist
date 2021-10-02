import configparser
import importlib
import os
from typing import Dict

from .backends.base import BaseBackend
from .index import Index


class Config(object):
    """
    Config accessing class.
    """

    def __init__(self, paths=None):
        self.paths = paths or [
            "arcdiscvist-config",
            os.path.expanduser("~/.arcdiscvist/config"),
            "/etc/arcdiscvist/config",
        ]
        self.load()

    def load(self):
        """
        Loads the configuration
        """
        for path in self.paths:
            if os.path.isfile(path):
                self.config = configparser.ConfigParser()
                self.config.read(path)
                self.path = path
                # Load backends
                self.backends: Dict[str, BaseBackend] = {}
                for section in self.config.sections():
                    if section.startswith("backend."):
                        name = section.split(".", 1)[1]
                        kwargs = dict(self.config[section])
                        module_name, class_name = kwargs.pop("class").rsplit(".", 1)

                        instance = getattr(
                            importlib.import_module(module_name), class_name
                        )(**kwargs)
                        self.backends[name] = instance
                return
        raise ValueError("No config file found! Paths: %s" % ", ".join(self.paths))

    @property
    def index(self) -> Index:
        """
        Returns an Index object
        """
        try:
            return Index(self.config["index"]["path"])
        except KeyError:
            raise ValueError("No index path in config file")

    @property
    def root_path(self) -> str:
        """
        Returns the root path
        """
        try:
            return os.path.abspath(self.config["root"]["path"])
        except KeyError:
            raise ValueError("No root path in config file")

    def __getitem__(self, key):
        return self.config[key]

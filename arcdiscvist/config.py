import os
import configparser
import datetime
import subprocess

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
                return
        raise ValueError("No config file found! Paths: %s" % ", ".join(self.paths))

    @property
    def index(self):
        """
        Returns an Index object
        """
        try:
            return Index(self.config['index']['path'])
        except KeyError:
            raise ValueError("No index path in config file")

    @property
    def source_path(self):
        """
        Returns the source path
        """
        try:
            return os.path.abspath(self.config['source']['path'])
        except KeyError:
            raise ValueError("No source path in config file")

import os
import configparser
import tarfile
import datetime

from .exceptions import ConfigError
from .index import Index
from .source import Source


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
        raise ConfigError("No config file found! Paths: %s" % ", ".join(self.paths))

    def index(self):
        """
        Returns an Index object
        """
        try:
            return Index(self.config['index']['path'])
        except KeyError:
            raise ConfigError("No index path in config file")

    def source(self):
        """
        Returns a Source object
        """
        try:
            return Source(self.config['source']['path'])
        except KeyError:
            raise ConfigError("No source path in config file")

    def visible_volumes(self):
        """
        Returns paths to currently visible volume directories.
        """
        with open('/proc/mounts','r') as fh:
            mountpoints = [line.split()[1] for line in fh.readlines()]
        for mountpoint in mountpoints:
            if os.path.isdir(mountpoint):
                for name in os.listdir(mountpoint):
                    path = os.path.join(mountpoint, name)
                    if name.endswith(".arcdiscvist") and os.path.isdir(path):
                        yield VolumeDirectory(path)


class VolumeDirectory(object):
    """
    Represents a volume archive on disk.
    """

    def __init__(self, path):
        self.path = path
        self.label = os.path.basename(self.path).split(".")[0]

    def created(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(self.path, "info.cfg"))
        assert self.label == config['volume']['label']
        return datetime.datetime.fromtimestamp(int(config['volume']['created']))

    def size(self):
        result = 0
        for name in os.listdir(self.path):
            result += os.path.getsize(os.path.join(self.path, name))
        return result

    def files(self):
        with tarfile.open(os.path.join(self.path, "data.tar"), "r") as tar:
            for member in tar.getmembers():
                yield member

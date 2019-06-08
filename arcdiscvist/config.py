import os
import configparser
import tarfile
import datetime
import subprocess

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

    @property
    def source_path(self):
        """
        Returns the source path
        """
        try:
            return self.config['source']['path']
        except KeyError:
            raise ConfigError("No source path in config file")


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

    def sha1(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(self.path, "info.cfg"))
        assert self.label == config['volume']['label']
        return config['volume'].get('sha1', None)

    def size(self):
        result = 0
        for name in os.listdir(self.path):
            result += os.path.getsize(os.path.join(self.path, name))
        return result

    def files(self):
        with tarfile.open(os.path.join(self.path, "data.tar"), "r") as tar:
            for member in tar.getmembers():
                yield member

    def par2_verify(self):
        subprocess.check_call(["par2", "verify", os.path.join(self.path, "parity.par2")])

    def calculate_sha1(self):
        return subprocess.check_output([
            "sha1sum",
            os.path.join(self.path, "data.tar")
        ]).strip().split()[0]

    def sha1_verify(self):
        """
        Verifies the volume according to the SHA1 checksum. Returns True for
        verified, False for corrupt, and None if no checksum is present to check.
        """
        sha1sum = self.sha1()
        if sha1sum is None:
            return None
        return sha1sum == self.calculate_sha1()

import os
import subprocess
import tempfile

from .exceptions import BuildError


class BaseWriter(object):
    """
    Base class for all writers.
    """

    indexable = False

    @property
    def volume_path(self):
        return os.path.join(self.path, "%s.arcdiscvist" % self.label)


class DirectDisk(BaseWriter):

    type = "disk"
    burn = False
    mounted = False
    indexable = True

    def __init__(self, device, label):
        self.label = label
        self.path, size = device.split("=")
        if size.endswith("M"):
            self.size = int(size[:-1]) * (1024 ** 2)
        elif size.endswith("G"):
            self.size = int(size[:-1]) * (1024 ** 3)
        elif size.endswith("T"):
            self.size = int(size[:-1]) * (1024 ** 4)
        else:
            self.size = int(size)

    def prep(self):
        os.mkdir(self.volume_path)

    def commit(self):
        pass

    def cleanup(self):
        pass

    def prep_index(self):
        self.index_path = self.volume_path


class UDFImage(BaseWriter):

    type = "udf"
    burn = False
    mounted = False

    def __init__(self, device, label):
        self.label = label
        self.device = device
        self.size = os.path.getsize(device)

    def prep(self):
        # Format it as UDF
        subprocess.check_output(["mkudffs", "--vid=%s" % self.label, self.device])
        # Mount it somewhere
        self.path = tempfile.mkdtemp(prefix="arcd-mnt-")
        subprocess.check_call(["mount", "-o", "loop", self.device, self.path])
        self.mounted = True
        # Make volume dir
        os.mkdir(self.volume_path)

    def commit(self):
        # Unmount the image
        subprocess.check_call(["umount", self.path])
        self.mounted = False

    def cleanup(self):
        if hasattr(self, "path"):
            if self.mounted:
                subprocess.check_call(["umount", "-fl", self.path])
            os.rmdir(self.path)


class BluRayWriter(BaseWriter):

    type = "bluray"
    burn = True
    mounted = False

    def __init__(self, device, label):
        self.device = device
        self.label = label
        # Try to open the drive first to ensure it has media
        try:
            with open('/dev/sr0', 'r'):
                pass
        except OSError as e:
            raise BuildError("Error getting disc size: %s" % e)
        # Then run cdrecord to get writeable size left
        # TODO: Feed it the device in right format?
        output = subprocess.check_output(["cdrecord", "-minfo", "dev=%s" % self.device], stderr=subprocess.STDOUT)
        self.size = None
        for line in output.decode("ascii").split("\n"):
            if line.startswith("Remaining writable size:"):
                self.size = int(line[25:].strip()) * 2048
                break
        if self.size is None:
            raise BuildError("Cannot get media size from cdrecord -minfo!")

    def prep(self):
        # Make the UDF block device
        _, self.image_path = tempfile.mkstemp(prefix="arcd-img-", suffix=".udf")
        subprocess.check_call(["truncate", "-s", str(self.size), self.image_path])
        subprocess.check_output(["mkudffs", "--vid=%s" % self.label, self.image_path])
        # Mount it somewhere
        self.path = tempfile.mkdtemp(prefix="arcd-mnt-")
        subprocess.check_call(["mount", "-o", "loop", self.image_path, self.path])
        self.mounted = True
        # Make volume dir
        os.mkdir(self.volume_path)

    def commit(self):
        # Unmount the image
        subprocess.check_call(["umount", self.path])
        self.mounted = False
        # Burn it
        subprocess.check_call(["cdrecord", "-v", "-dao", "driveropts=burnfree", "dev=%s" % self.device, self.image_path])
        # Eject finished bluray
        subprocess.check_call(["eject", self.device])

    def cleanup(self):
        if hasattr(self, "path"):
            if self.mounted:
                subprocess.check_call(["umount", "-fl", self.path])
            os.rmdir(self.path)
        if hasattr(self, "image_path"):
            os.unlink(self.image_path)

import os
import shutil
import subprocess
import tempfile
import datetime
import stat
import hashlib
import tarfile

from .exceptions import BuildError


class Builder(object):
    """
    Creates new volumes
    """

    def __init__(self, source, index, parity=5, copies=1):
        self.source = source
        self.index = index
        self.parity = parity
        self.copies = copies

    def prep_writer(self, device):
        """
        Prepares the volume information according to the device
        """
        # See what kind of device it is
        stat_result = os.stat(device)
        if device.endswith(".udf"):
            self.writer = UDFImage(device)
        elif stat.S_ISBLK(stat_result.st_mode):
            self.writer = BluRayWriter(device)
        else:
            raise BuildError("Cannot determine type of target device %s" % device)

    def gather_files(self, filters):
        """
        Gathers a set of files into the builder that fit inside `size`.
        """
        # Adjust size according to parity values
        data_size = self.writer.size * (1 - ((self.parity + 2) / 100.0))
        # Set up instance storage
        self.total_size = 0
        self.files = []
        # Gather files
        for path in self.source.files(filters):
            if len(self.index.file_volumes(path)) < self.copies:
                pathsize = self.source.size(path)
                if pathsize < (data_size - self.total_size):
                    self.total_size += pathsize
                    self.files.append(path)

    def normalize_tar(self, tarinfo):
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        tarinfo.mode = 0o755
        return tarinfo

    def build(self, progress):
        # Decide on a volume label
        self.volume_label = self.index.new_volume_label()
        try:
            # Run writer prep, which results in it having a writeable directory
            progress("prep", "start")
            self.writer.prep(self.volume_label)
            volume_dir = os.path.join(self.writer.path, "%s.arcdiscvist" % self.volume_label)
            os.mkdir(volume_dir)
            progress("prep", "end")
            # Copy files into target tarball
            progress("copy", "start")
            with tarfile.open(os.path.join(volume_dir, "data.tar"), "w") as tar:
                for i, path in enumerate(self.files):
                    progress("copyfile", (i, len(self.files), path))
                    tar.add(self.source.abspath(path), arcname=path, filter=self.normalize_tar)
            progress("copy", "end")
            # Create parity set
            if self.parity:
                progress("parity", "start")
                subprocess.check_call([
                    "par2", "create", "-r%s" % self.parity, "-n1", "-m128",
                    os.path.join(volume_dir, "parity.par2"),
                    os.path.join(volume_dir, "data.tar"),
                ])
                progress("parity", "end")
            # Write volume info file
            with open(os.path.join(volume_dir, "info.cfg"), "w") as fh:
                fh.write("[volume]\nlabel=%s\n" % self.volume_label)
                fh.write("created=%s\n" % int(datetime.datetime.utcnow().timestamp()))
            # Commit image (either umount or burn)
            progress("commit", "start")
            self.writer.commit()
            progress("commit", "end")
        finally:
            self.writer.cleanup()


class UDFImage(object):

    type = "udf"
    burn = False
    mounted = False

    def __init__(self, device):
        self.device = device
        self.size = os.path.getsize(device)

    def prep(self, label):
        # Format it as UDF
        subprocess.check_output(["mkudffs", "--vid=%s" % label, self.device])
        # Mount it somewhere
        self.path = tempfile.mkdtemp(prefix="arcd-mnt-")
        subprocess.check_call(["mount", "-o", "loop", self.device, self.path])
        self.mounted = True

    def commit(self):
        # Unmount the image
        subprocess.check_call(["umount", self.path])
        self.mounted = False

    def cleanup(self):
        if hasattr(self, "path"):
            if self.mounted:
                subprocess.check_call(["umount", "-fl", self.path])
            os.rmdir(self.path)


class BluRayWriter(object):

    type = "bluray"
    burn = True
    mounted = False

    def __init__(self, device):
        self.device = device
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

    def prep(self, label):
        # Make the UDF block device
        _, self.image_path = tempfile.mkstemp(prefix="arcd-img-", suffix=".udf")
        subprocess.check_call(["truncate", "-s", str(self.size), self.image_path])
        subprocess.check_output(["mkudffs", "--vid=%s" % label, self.image_path])
        # Mount it somewhere
        self.path = tempfile.mkdtemp(prefix="arcd-mnt-")
        subprocess.check_call(["mount", "-o", "loop", self.image_path, self.path])
        self.mounted = True

    def commit(self):
        # Unmount the image
        subprocess.check_call(["umount", self.path])
        self.mounted = False
        # Burn it
        print("BURN")
        shutil.copyfile(self.image_path, "/tmp/result.udf")

    def cleanup(self):
        if hasattr(self, "image_path"):
            os.unlink(self.image_path)
        if hasattr(self, "path"):
            if self.mounted:
                subprocess.check_call(["umount", "-fl", self.path])
            os.rmdir(self.path)

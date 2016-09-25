import os
import shutil
import subprocess
import tempfile
import datetime
import tarfile

from .exceptions import BuildError
from .writers import UDFImage, DirectDisk, BluRayWriter
from .config import VolumeDirectory
from .utils import is_block_device


class Builder(object):
    """
    Creates new volumes
    """

    def __init__(self, source, index, redundancy=5, copies=1, ontype=None):
        self.source = source
        self.index = index
        self.redundancy = redundancy
        self.copies = copies
        self.ontype = ontype

    def prep_writer(self, device):
        """
        Prepares the volume information according to the device
        """
        # Decide on a volume label
        self.volume_label = self.index.new_volume_label()
        # See what kind of device it is
        if device.endswith(".udf"):
            self.writer = UDFImage(device, self.volume_label)
        elif "=" in device:
            self.writer = DirectDisk(device, self.volume_label)
        elif is_block_device(device):
            self.writer = BluRayWriter(device, self.volume_label)
        else:
            raise BuildError("Cannot determine type of target device %s" % device)

    def gather_files(self, filters):
        """
        Gathers a set of files into the builder that fit inside `size`.
        """
        # Adjust size according to parity values
        data_size = self.writer.size
        if self.redundancy:
            data_size *= (1 - ((self.redundancy + 1) / 100.0))
        # Set up instance storage
        self.total_size = 0
        self.files = []
        # Gather files
        for filter in filters:
            for path in sorted(self.source.files([filter])):
                if len(self.index.file_volumes(path, ontype=self.ontype)) < self.copies:
                    pathsize = self.source.size(path)
                    if pathsize < (data_size - self.total_size):
                        self.total_size += pathsize
                        self.files.append(path)

    def normalize_tar(self, tarinfo):
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        tarinfo.mode = 0o755
        tarinfo.mtime = int(tarinfo.mtime)
        return tarinfo

    def build(self, progress):
        try:
            # Run writer prep, which results in it having a writeable directory
            progress("prep", "start")
            self.writer.prep()
            progress("prep", "end")
            # Copy files into target tarball
            progress("copy", "start")
            tar_path = os.path.join(self.writer.volume_path, "data.tar")
            with tarfile.open(tar_path, "w") as tar:
                for i, path in enumerate(self.files):
                    progress("copyfile", (i + 1, len(self.files), path))
                    tar.add(self.source.abspath(path), arcname=path, filter=self.normalize_tar)
            progress("copy", "end")
            # Create parity set
            if self.redundancy:
                progress("parity", "start")
                subprocess.check_call([
                    "par2", "create", "-b1000", "-r%s" % self.redundancy, "-n1", "-u", "-m4096",
                    os.path.join(self.writer.volume_path, "parity.par2"),
                    tar_path,
                ])
                #for name in os.listdir(parity_dir):
                #    shutil.copyfile(
                #        os.path.join(parity_dir, name),
                #        os.path.join(self.writer.volume_path, name),
                #    )
                #    os.unlink(os.path.join(parity_dir, name))
                #os.rmdir(parity_dir)
                progress("parity", "end")
            # Write volume info file
            progress("meta", "start")
            sha1sum = subprocess.check_output([
                "sha1sum",
                tar_path,
            ]).strip().split()[0]
            with open(os.path.join(self.writer.volume_path, "info.cfg"), "w") as fh:
                fh.write("[volume]\nlabel=%s\n" % self.volume_label)
                fh.write("created=%s\n" % int(datetime.datetime.utcnow().timestamp()))
                fh.write("sha1=%s\n" % sha1sum)
            progress("meta", "end")
            # Commit image (either umount or burn)
            progress("commit", "start")
            self.writer.commit()
            progress("commit", "end")
            # Index new image
            if self.writer.indexable:
                progress("index", "start")
                self.writer.prep_index()
                self.index.index_volume_directory(VolumeDirectory(self.writer.index_path))
                progress("index", "end")
            else:
                progress("index", "fail")

        finally:
            self.writer.cleanup()


import io
import logging
import tarfile


def human_size(num, suffix="B"):
    """
    Given a size in bytes, returns the human-readable version.
    """
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Y", suffix)


def normalize_tarinfo(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
    """
    Filter function for adding things to tarfiles consistently.
    """
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = "root"
    tarinfo.mode = 0o755
    tarinfo.mtime = int(tarinfo.mtime)
    return tarinfo


def tar_addbytes(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    """
    Adds the given bytes to the tarfile as a file
    """
    tarinfo = tarfile.TarInfo(name)
    tarinfo.size = len(data)
    normalize_tarinfo(tarinfo)
    tar.addfile(tarinfo, io.BytesIO(data))


class ProgressLogger:
    def __init__(self):
        self.seen = 0

    def __call__(self, chunk_size):
        old_seen_gigs = self.seen // ((1024**3) * 5)
        self.seen += chunk_size
        new_seen_gigs = self.seen // ((1024**3) * 5)
        if old_seen_gigs != new_seen_gigs:
            logging.info(f"  {new_seen_gigs * 5}GB")

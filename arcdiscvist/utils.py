import os
import stat


def human_size(num, suffix='B'):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)


def get_fs_type(path):
    partition = {}
    with open("/proc/mounts", "r") as fh:
        for line in fh:
            bits = line.split()
            device = bits[0]
            mountpoint = bits[1]
            fstype = bits[2]
            partition[mountpoint] = (fstype, device)
    if path in partition:
        return partition[path]
    splitpath = path.split(os.sep)
    for i in range(len(splitpath),0,-1):
        path = os.sep.join(splitpath[:i]) + os.sep
        if path in partition:
            return partition[path]
        path = os.sep.join(splitpath[:i])
        if path in partition:
            return partition[path]
    return ("unknown", "none")


def is_block_device(path):
    return stat.S_ISBLK(os.stat(path).st_mode)

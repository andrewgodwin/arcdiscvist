import click
import json
import tempfile


class Builder:
    """
    Creates new volumes

    Volumes are a tar file containing the files to be stored, along with a JSON
    file containing information about the contents.

    The tar's filename also contains a sha1 hash of the volume.
    """

    def __init__(self, label, output_dir, paths):
        self.label = label
        self.output_dir = output_dir
        self.paths = paths
        assert target.endswith(".arcdiscvist")

    def build(self, progress):
        """
        Builds the target tar
        """
        with tempfile.TemporaryDirectory(prefix="arc-build-") as dirname:
            # Write out the JSON file with info
            json_path = os.path.join(dirname, "arcdiscvist-volume-info.json")
            with open(json_path, "w") as fh:
                json.dump({"label": self.label}, fh)
            # Build the tar file
            tar_path = os.path.join(dirname, "data.tar")
            with tarfile.open(tar_path, "w") as tar:
                with click.progressbar(self.paths, label="Copying files") as bar:
                    for path in bar:
                        tar.add(path, arcname=path, filter=self.normalize_tar)
            # Calculate the SHA1 hash
            with click.progressbar(label="Calculating checksum"):
                sha1sum = subprocess.check_output(["sha1sum", tar_path]).strip().split()[0]
            # Move it to its final destination
            final_path = os.path.join(self.output_dir, "%s.%s.tar" % (self.label, sha1sum))
            os.rename(tar_path, final_path)

    def normalize_tar(self, tarinfo):
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        tarinfo.mode = 0o755
        tarinfo.mtime = int(tarinfo.mtime)
        return tarinfo


class Scanner:
    """
    Scans the source directory trying to make a file list for the builder.
    """

    def __init__(self, source_path, patterns):
        self.source_path = source_path
        self.patterns = patterns

    def paths(self):
        """
        Returns a list of (absolute) paths the builder could pick from.
        Does not remove items in the index or account for size.
        """
        for curpath, dirnames, filenames in os.walk(self.source_path):
            # Trim out dirnames not in the filter list
            for dirname in list(dirnames):
                dirbits = os.path.join(curpath, dirname)[len(self.source_path)+1:].split("/")
                for f in filters:
                    fbits = f.strip("/").split("/")
                    complen = min(len(dirbits), len(fbits))
                    if dirbits[:complen] == fbits[:complen]:
                        break
                else:
                    dirnames.remove(dirname)
            # Yield file objects that match.
            for filename in filenames:
                if filename.startswith("arcdiscvist-"):
                    continue
                filepath = os.path.abspath(os.path.join(curpath, filename))
                # Make sure this file is all the way under a filter
                for filter in filters:
                    if filepath.startswith(os.path.join(self.source_path, filter)):
                        break
                else:
                    continue
                yield filepath
                if re;at

    def volume_paths(self, index, size):
        for filepath in self.paths():
            # Get the path the index would know it by
            relative_path = filepath[len(self.path) + 1:]
            # See if it's in the index (if it's not at all, we skip the SHA hash)
            if index.files(path_glob=relative_path):
                # OK, SHA hash it to see if it changed


    def file_hash(self, path):
        """
        Returns the SHA hash of a file
        """
        return subprocess.check_output(["sha1sum", path]).strip()

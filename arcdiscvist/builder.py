import click
import json
import os
import tempfile
import tarfile
import subprocess
import shutil


class Builder:
    """
    Creates new volumes

    Volumes are a tar file containing the files to be stored, along with a JSON
    file containing information about the contents.

    The tar's filename also contains a sha1 hash of the volume.
    """

    def __init__(self, label, output_dir):
        self.label = label
        self.output_dir = output_dir

    def build(self, source_path, paths, compression=False):
        """
        Builds the target tar
        """
        with tempfile.TemporaryDirectory(prefix="arc-build-") as dirname:
            # Write out the JSON file with info
            json_path = os.path.join(dirname, "volume.json")
            with open(json_path, "w") as fh:
                json.dump({
                    "label": self.label,
                    "paths": paths,
                }, fh)
            # Build the tar file
            tar_path = os.path.join(dirname, "data.tar")
            click.echo("Copying files... ", nl=False)
            with tarfile.open(tar_path, "x") as tar:
                # Add JSON info file
                tar.add(json_path, arcname="__arcdiscvist_volume", filter=self.normalize_tar)
                # Add data files
                for i, path in enumerate(paths):
                    click.echo("\rCopying files... %i/%i " % (i + 1, len(paths)), nl=False)
                    tar.add(os.path.join(source_path, path), arcname=path, filter=self.normalize_tar)
            click.secho("Done", fg="green")
            # Calculate the SHA1 hash
            click.echo("Calculating checksum... ", nl=False)
            sha1sum = subprocess.check_output(["sha1sum", tar_path]).strip().split()[0].decode("ascii")
            click.secho("Done", fg="green")
            # Try compressing it
            if compression:
                click.echo("Compressing... ", nl=False)
                subprocess.check_output(["gzip", "-k", tar_path])
                click.secho("Done", fg="green")
                uncompressed_size = os.path.getsize(tar_path)
                compressed_size = os.path.getsize(tar_path + ".gz")
                ratio = (uncompressed_size / compressed_size)
                if ratio < 0.95:
                    click.echo("  Using compressed version (ratio %.2f%%)" % (ratio * 100))
                    tar_path += ".gz"
                else:
                    click.echo("  Not using compressed version (ratio %.2f%%)" % (ratio * 100))
            # Move it to its final destination
            final_path = os.path.join(self.output_dir, "%s.%s.tar%s" % (self.label, sha1sum, ".gz" if tar_path.endswith(".gz") else ""))
            shutil.move(tar_path, final_path)
            return final_path

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
                if self.patterns:
                    for f in self.patterns:
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
                file_path = os.path.abspath(os.path.join(curpath, filename))
                # Make sure this file is all the way under a filter
                if self.patterns:
                    for filter in self.patterns:
                        if file_path.startswith(os.path.join(self.source_path, filter)):
                            break
                    else:
                        continue
                relative_path = file_path[len(self.source_path) + 1:]
                yield relative_path

    def volume_paths(self, index, size):
        size_used = 0
        result = []
        for relative_path in self.paths():
            # See if it's in the index (if it's not at all, we skip the SHA hash)
            index_hit = index.files(path_exact=relative_path)
            file_size = os.path.getsize(os.path.join(self.source_path, relative_path))
            if index_hit:
                # Verify it's the same file (via size only for now)
                index_size = list(index_hit.values())[0]["size"]
                if index_size != file_size:
                    raise ValueError("File %s already in index but with different size! (%s != %s)" % (
                        relative_path,
                        index_size,
                        file_size,
                    ))
                continue
            # Add it to our collection
            if (size_used + file_size) <= size:
                size_used += file_size
                result.append(relative_path)
        return result, size_used

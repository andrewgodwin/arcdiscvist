import click
import datetime
import os
import shlex
import subprocess
import sys
import tarfile

from .builder import Builder, Scanner
from .config import Config
from .utils import human_size


config = Config()


@click.group()
def main():
    pass


@main.command()
@click.option('-s', '--size', type=int, default=10, help="Size of the volume in GB")
@click.option('-o', '--output', default=".", help="Output path for new volumes")
@click.option('-y', '--yes', is_flag=True, default=False)
@click.option('-c', '--compress', is_flag=True, default=False)
@click.argument('patterns', nargs=-1)
def build(patterns, size, output, yes, compress):
    """
    Builds a volume out of the paths specified and writes it out to disk.
    """
    # Find the paths
    click.echo("Scanning files... ", nl=False)
    paths, size_used = Scanner(config.source_path, patterns).volume_paths(config.index, size * (1024 ** 3))
    click.secho("Done", fg="green")
    if not paths:
        click.secho("No files found to add.", fg="yellow")
        return
    # Print what we found
    for path in paths:
        click.echo("> " + click.style(path, fg="blue"))
    click.echo("%s files, %s" % (len(paths), human_size(size_used)))
    # Prompt to continue
    if not yes:
        if not click.confirm("Proceed with build?"):
            return
    click.echo()
    # Select an unused volume label
    volume_label = config.index.new_volume_label()
    # Build the volume
    final_path = Builder(volume_label, output).build(config.source_path, paths, compression=compress)
    click.echo(click.style("Volume built as %s" % final_path, fg="green"))
    # Auto-index it
    click.echo("\nIndexing new volume...")
    index([final_path])


## File querying commands


@main.command()
@click.argument('path', default="")
def ls(path):
    """
    Lists the context of the index at the given path.
    """
    # Normalise the path
    path = path.strip("/")
    path_depth = len(path.split("/"))
    if not path:
        path_depth = 0
    # Get the set of files/dirs as a dict (name: attrs)
    files = {}
    for entry_path, entry_attrs in config.index.files(path_glob="%s*" % path).items():
        entry_path_parts = entry_path.split("/")
        # Is it a file at our level?
        if len(entry_path_parts) - 1 == path_depth:
            files[entry_path_parts[-1]] = entry_attrs
        # Is it an implicit directory
        else:
            files[entry_path_parts[path_depth]] = {"size": "dir"}
    # Print the resulting table
    print_files(files)


@main.command()
@click.argument('pattern')
def find(pattern):
    """
    Finds all files matching the pattern
    """
    files = config.index.files(path_glob="*%s*" % pattern)
    print_files(files)


def print_files(files):
    output_format = "%-10s %-8s %s"
    click.secho(output_format % ("SIZE", "VOLUME", "FILENAME"), fg="cyan")
    for name, attrs in sorted(files.items()):
        if attrs["size"] == "dir":
            click.echo(output_format % (
                "dir",
                "",
                name,
            ))
        else:
            click.echo(output_format % (
                human_size(attrs["size"]),
                attrs["volume_label"],
                name,
            ))


## File restore commands


@main.command
@click.argument('path')
@click.argument('destination')
def extract(path):
    """
    Extracts a single file by path to a named destination
    """
    pass


## Volume commands


@main.group()
def volume():
    pass


@volume.command()
@click.argument('paths', nargs=-1)
def index(paths):
    """
    Adds one or more volumes to the index
    """
    for path in paths:
        # Extract the volume's label and SHA from its filename
        label, sha1, extension = os.path.basename(path).split(".", 2)
        assert extension in ("tar", "tar.gz", "tar.bz2")
        assert len(sha1) == 40
        # See if the volume is already in there
        if config.index.volumes(label=label):
            click.secho("%s already indexed" % label, fg="yellow")
            continue
        # Add each file in the volume
        added_copies = 0
        with tarfile.open(path, "r") as tar:
            for info in tar:
                if info.name.startswith("__arcdiscvist"):
                    continue
                config.index.add_file_copy(info.name, info.size, info.mtime, label)
                added_copies += 1
        # Add it in
        config.index.add_volume(label, sha1, os.path.getsize(path), os.stat(path).st_mtime)
        click.secho("%s added, with %i files" % (label, added_copies))


@volume.command()
@click.argument('paths', nargs=-1)
def validate(paths):
    """
    Validates one or more volume files by hash
    """
    all_good = True
    for path in paths:
        # Extract the volume's label and SHA from its filename
        label, sha1, extension = os.path.basename(path).split(".", 2)
        assert extension in ("tar", "tar.gz", "tar.bz2")
        assert len(sha1) == 40
        # Different handling for compressed files!
        click.echo("Validating %s... " % label, nl=False)
        if extension == "tar.gz":
            calculated_sha1 = subprocess.check_output("gzip -dc %s | sha1sum" % shlex.quote(path), shell=True)
        elif extension == "tar.bz2":
            calculated_sha1 = subprocess.check_output("bzip2 -dc %s | sha1sum" % shlex.quote(path), shell=True)
        else:
            calculated_sha1 = subprocess.check_output(["sha1sum", path])
        calculated_sha1 = calculated_sha1.strip().split()[0].decode("ascii")
        # Say if it was good or not
        if calculated_sha1 == sha1:
            click.secho("Valid", fg="green")
        else:
            click.secho("Invalid (%s)" % calculated_sha1, fg="red")
            all_good = False
    # Exit appropriately
    if not all_good:
        sys.exit(1)


@volume.command()
def list():
    """
    Lists all volumes
    """
    output_format = "%-10s %-20s"
    click.secho(output_format % ("LABEL", "CREATED"), fg="cyan")
    for volume in sorted(config.index.volumes(), key=lambda x: x["label"]):
        click.echo(output_format % (
            volume["label"],
            datetime.datetime.fromtimestamp(volume["created"]).strftime("%Y-%m-%d %H:%M:%S"),
        ))


@volume.command()
@click.argument('label')
def contents(label):
    """
    Lists the contents of a volume
    """
    files = config.index.files(volume_label=label)
    print_files(files)


@volume.command()
@click.argument('label')
def remove(label):
    """
    Removes a volume and all its file entries from the database
    """
    # See if the volume exists
    if not config.index.volumes(label=label):
        click.secho("No volume '%s' found" % label, fg="red")
        return
    # Delete it
    config.index.remove_volume(label)
    click.echo("Volume %s removed" % label)

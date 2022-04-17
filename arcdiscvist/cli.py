import datetime
import logging
import sys

import click

from arcdiscvist.backends.base import BaseBackend

from . import __version__
from .archive import Archive
from .config import Config
from .scanner import Scanner
from .utils import human_size
from .tui import ArcApp

config = Config()


@click.group()
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="  %(message)s",
        handlers=[logging.StreamHandler()],
    )


@main.command()
def tui():
    ArcApp.run(title="Arcdiscvist", log="textual.log")


@main.command()
def info():
    """
    Displays system information
    """
    click.echo(f"Arcdiscvist version {__version__}")
    click.echo(f"  Config file: {config.path}")
    click.echo(f"  Root path: {config.root_path}\n")
    click.echo("  Backends:")
    for name, backend in config.backends.items():
        click.echo(f"    {name}: {backend}")


@main.command()
@click.option("-s", "--size", type=int, default=50, help="Size of the archive in GB")
@click.option("-m", "--minimum", type=int, default=0, help="Minimum size in GB")
@click.option("-y", "--yes", is_flag=True, default=False)
@click.argument("backend_name")
@click.argument("patterns", nargs=-1)
def pack(backend_name, patterns, size, minimum, yes):
    """
    Builds a volume out of the paths specified and writes it out to disk.
    """
    # Load the backend
    backend = get_backend(backend_name)
    # Find the paths
    click.echo("Scanning files... ", nl=False)
    paths, size_used = Scanner(config.root_path, patterns).unstored_paths(
        config.index, size * (1024 ** 3)
    )
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
    # Select an unused archive ID
    archive_id = config.index.new_archive_id()
    # Pack the volume
    archive = Archive.from_files(archive_id, paths, config.root_path)
    click.echo(f"Archive is {archive.id}, size {human_size(archive.size)}")
    if archive.size < minimum * (1024 ** 3):
        click.echo("Archive too small, quitting")
        sys.exit(1)
    backend.archive_store(config.root_path, archive)
    click.echo("Archive stored")
    config.index.add_archive(archive, backend_name)
    click.echo("Archive indexed")


@main.command()
@click.argument("backend_name")
@click.argument("archive_id")
def unpack(backend_name, archive_id):
    """
    Retrieves the named archive and unpacks it to the root
    """
    backend = get_backend(backend_name)
    click.echo(f"Retrieving archive {archive_id}")
    backend.archive_retrieve(config.root_path, archive_id)


## File querying commands


@main.command()
@click.argument("path", default="")
def ls(path):
    """
    Lists the context of the index at the given path.
    """
    print_files(config.index.contents(path))


@main.command()
@click.argument("pattern")
def find(pattern):
    """
    Finds all files matching the pattern
    """
    files = config.index.files(path_glob="*%s*" % pattern)
    print_files(files)


def print_files(files):
    output_format = "%-10s %-8s %s"
    click.secho(output_format % ("SIZE", "ARCHIVE", "FILENAME"), fg="cyan")
    for name, attrs in sorted(files.items()):
        if attrs.directory:
            click.echo(
                output_format
                % (
                    "dir",
                    "",
                    name,
                )
            )
        else:
            click.echo(
                output_format
                % (
                    human_size(attrs.size),
                    ",".join(attrs.archive_ids),
                    name,
                )
            )


## Archive commands


@main.group()
def archive():
    """
    Archive management subcommands
    """
    pass


@archive.command()
@click.argument("backend_name")
@click.argument("ids", nargs=-1)
def index(backend_name, ids):
    """
    Adds one or more archives to the index from their backend
    """
    # Load the backend
    backend = get_backend(backend_name)
    # Handle each ID
    for id in ids:
        # See if the volume is already in there
        if config.index.archives(id=id):
            click.secho(f"{id} already indexed", fg="yellow")
            continue
        # Fetch the volume's metadata and make an Archive object
        metadata = backend.archive_retrieve_meta(id)
        archive = Archive.from_json(metadata)
        # Index it
        config.index.add_archive(archive, backend_name)
        click.secho(f"{archive.id} added, with {len(archive.files)} files")


@archive.command()
def list():
    """
    Lists all local archives
    """
    index = config.index
    output_format = "%-7s %-20s %s"
    click.secho(output_format % ("ID", "CREATED", "BACKENDS"), fg="cyan")
    for archive in sorted(index.archives(), key=lambda x: x["id"]):
        # Print it out
        click.echo(
            output_format
            % (
                archive["id"],
                datetime.datetime.fromtimestamp(archive["created"]).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                ", ".join(sorted(archive["backend_names"])),
            )
        )


@archive.command()
@click.argument("archive_id")
def contents(archive_id):
    """
    Lists the contents of a volume
    """
    files = config.index.files(archive_id=archive_id)
    print_files(files)


@archive.command()
@click.argument("archive_id")
def remove(archive_id):
    """
    Removes a archive and all its file entries from the database
    """
    # See if the archive exists
    if not config.index.archives(archive_id=archive_id):
        click.secho("No archive '%s' found" % archive_id, fg="red")
        return
    # Delete it
    config.index.remove_archive(archive_id)
    click.echo("Archive %s removed" % archive_id)


# Backend commands


@main.group()
def backend():
    """
    Archive management subcommands
    """
    pass


@backend.command()
@click.argument("backend_name")
def archives(backend_name):
    """
    Lists all remote archives in a backend
    """
    output_format = "%-7s"
    backend = get_backend(backend_name)
    click.secho(output_format % ("ID",), fg="cyan")
    for archive_id in sorted(backend.archive_list()):
        # Print it out
        click.echo(output_format % (archive_id,))


@backend.command()
@click.argument("backend_name")
def sync(backend_name):
    """
    Adds unindexed archives from a backend
    """
    backend = get_backend(backend_name)
    backend_archives = set(backend.archive_list())
    local_archives = {x["id"] for x in config.index.archives()}
    for archive_id in backend_archives.difference(local_archives):
        click.secho(f"{archive_id} found on remote", fg="blue")
        archive = Archive.from_json(backend.archive_retrieve_meta(archive_id))
        config.index.add_archive(archive, backend_name)
    click.secho(f"{len(backend_archives)} synchronised", fg="green")


# Utilities


def get_backend(backend_name: str) -> BaseBackend:
    try:
        return config.backends[backend_name]
    except KeyError:
        raise click.ClickException(f"No such backend {backend_name}")

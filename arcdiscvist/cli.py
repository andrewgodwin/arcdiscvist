import os
import sys
import argparse
import logging
import importlib
import tempfile
import textwrap
import subprocess

from .color import red, green, cyan, yellow
from .config import Config
from .builder import Builder
from .utils import human_size, is_block_device
from .exceptions import ConfigError, BuildError

logger = logging.getLogger(__name__)


class CommandLineInterface(object):
    """
    Acts as the main CLI entry point.
    """

    description = "Archive volume creation and indexing tool"

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description=self.description,
        )
        self.parser.add_argument(
            "command",
            help="Command to run",
        )
        self.parser.add_argument(
            '-v',
            '--volume',
            nargs='*',
            dest='volumes',
            help='Paths to volumes',
            default=None,
        )
        self.parser.add_argument(
            '-y',
            '--yes',
            action="store_true",
            dest='yes',
            help='Don\'t prompt for confirmations',
            default=False,
        )
        self.parser.add_argument(
            '-r',
            '--redundancy',
            type=int,
            help='Level of parity redundancy in percent',
            default=5,
        )
        self.parser.add_argument(
            '-c',
            '--copies',
            type=int,
            help='Minimum number of copies to ensure',
            default=1,
        )
        self.parser.add_argument(
            '-t',
            '--type',
            help='Type of volume storage to ensure copies are on',
            default=None,
        )
        self.parser.add_argument(
            "subargs",
            nargs=argparse.REMAINDER,
        )

    # Nice output formatting
    def info(self, message):
        print(cyan(message))
    def warning(self, message):
        print(yellow(message))
    def error(self, message):
        print(red(message))
    def success(self, message):
        print(green(message))
    def fatal(self, message):
        self.error(message)
        sys.exit(1)
    def info_replace(self, message):
        print(cyan("\r\033[K" + message), end="")

    @classmethod
    def entrypoint(cls):
        """
        Main entrypoint for external starts.
        """
        cls().run(sys.argv[1:])

    def run(self, args):
        """
        Pass in raw argument list and it will decode them
        and run the server.
        """
        # Check rootness
        if os.geteuid() != 0:
            self.fatal("You must run as root.")
        try:
            # Decode args and config
            args = self.parser.parse_args(args)
            self.config = Config()
            self.noninteractive = args.yes
            self.args = args
            if self.noninteractive:
                self.info("Running in noninteractive mode")
            if args.command == "ls":
                args.command = "list"
            # Run right subcommand
            handler = getattr(self, "command_%s" % args.command, None)
            if not handler:
                self.fatal("Unknown command %s" % args.command)
            handler(*args.subargs)
        except (ConfigError, BuildError) as e:
            self.fatal(str(e))

    def command_help(self, name=None, *args):
        """
        Shows help about commands.

        Usage: help [<command_name>]
        """
        if name:
            # Show specific command help
            try:
                print(textwrap.dedent(getattr(self, "command_%s" % name).__doc__).strip())
            except AttributeError:
                print(red("No command %s" % name))
        else:
            # Summarise all commands
            fmt = "%-25s %s"
            for attrname in dir(self):
                if attrname.startswith("command_"):
                    docstring = getattr(self, attrname).__doc__ or ""
                    description = docstring.strip().split("\n")[0].strip()
                    print(fmt % (cyan(attrname[8:]), description))

    def command_build(self, *args):
        """
        Builds new volumes.

        Usage: build [--type=x] [<volume_target>] <path> [<path>, ...]

        Type recommended to be one of "optical", "hdd"
        """
        if len(args) < 1:
            self.fatal("You must provide a target device path")
        device = args[0]
        filters = args[1:]
        # Work out where we're building
        builder = Builder(
            self.config.source(),
            self.config.index(),
            redundancy=self.args.redundancy,
            copies=self.args.copies,
            ontype=self.args.type,
        )
        self.info("Examining target device...")
        builder.prep_writer(device)
        self.success(" > Target is type %s, size %s, redundancy %i%%" % (
            builder.writer.type,
            human_size(builder.writer.size),
            builder.redundancy,
        ))
        self.info(" - Label will be %s" % builder.volume_label)
        # Gather files
        self.info("Gathering files...")
        builder.gather_files(filters)
        for file in builder.files:
            self.info(" - %s" % file)
        if not builder.files:
            self.fatal(" > No files found.")
        self.success(" > Gathered %s files totalling %s" % (
            len(builder.files),
            human_size(builder.total_size),
        ))
        if not self.noninteractive:
            while True:
                response = input("Proceed with build and burn? [y] ")
                if response.lower() == "y" or not response:
                    break
                else:
                    self.fatal("User aborted.")
        # Run build
        self.info("Beginning build of volume %s" % builder.volume_label)
        def progress(step, state):
            if state == "end":
                if step == "copy":
                    self.info("")
                self.success(" > Done.")
            elif step == "prep" and state == "start":
                self.info("Prepping destination...")
            elif step == "copy" and state == "start":
                self.info("Copying files...")
            elif step == "parity" and state == "start":
                self.info("Creating parity file...")
            elif step == "meta" and state == "start":
                self.info("Writing meta information and checksum...")
            elif step == "index" and state == "start":
                self.info("Indexing new volume...")
            elif step == "index" and state == "fail":
                self.warning("Cannot index new volume. Please do it manually.")
            elif step == "commit" and state == "start":
                if builder.writer.burn:
                    self.info("Burning media...")
                else:
                    self.info("Syncing disk...")
            elif step == "copyfile":
                self.info_replace(" - Copying %i/%i: %s" % state)
        builder.build(progress)
        self.info("Created new volume %s" % builder.volume_label)

    def command_index(self, path=None):
        """
        Indexes available volumes.

        Usage: index [<path>]
        """
        # If they passed in a device path, mount it temporarily
        device_path = None
        if is_block_device(path):
            device_path = path
            path = tempfile.mkdtemp(prefix="arcd-imnt-")
            self.info("Mounting %s to read it..." % device_path)
            subprocess.check_call(["mount", device_path, path])
        try:
            index = self.config.index()
            for volume in self.config.visible_volumes():
                if path and not volume.path.startswith(path):
                    continue
                self.info("Indexing volume %s..." % volume.label)
                added = index.index_volume_directory(volume)
                self.success(" > %s files indexed." % added)
        finally:
            if device_path:
                subprocess.check_call(["umount", device_path])

    def command_list(self, dirname=""):
        """
        Lists directories in the virtual filesystem.

        Usage: list [<path>]
        """
        self._print_search_files(self.config.index().file_list(dirname))

    def command_find(self, pattern):
        """
        Finds files by name or pattern in the virtual filesystem.

        Usage: find <pattern>
        """
        self._print_search_files(self.config.index().file_find(pattern))

    def _print_search_files(self, files):
        fmt = "%-10s %-5s %s"
        print(cyan(fmt % ("SIZE", "VOLS", "NAME")))
        for path, details in sorted(files.items()):
            if details[0]:
                print(fmt % (
                    human_size(details[1]),
                    len(details[0]),
                    path,
                ))
            else:
                print(fmt % (
                    "<dir>",
                    "",
                    path + "/",
                ))

    ### VOLUME MANAGEMENT ###

    def command_volumes(self, label=None):
        """
        Lists known volumes.

        Usage: volumes [<label>]
        """
        if label:
            volumes = [self.config.index().volume(label)]
            if volumes[0] is None:
                self.fatal("No volume with label %s" % label)
        else:
            volumes = self.config.index().volumes()
        # Get currently visible volumes
        visible_labels = {volume.label for volume in self.config.visible_volumes()}
        # Print output
        fmt = "%-10s %-3s %-10s %-20s %-15s %s"
        print(cyan(fmt % ("LABEL", "VIS", "SIZE", "CREATED", "TYPE", "LOCATION")))
        for volume in sorted(volumes, key=lambda v: v.label):
            print(fmt % (
                volume.label,
                green("\u2713  ") if volume.label in visible_labels else red("\u00d7  "),
                human_size(volume.size),
                volume.created,
                volume.type or "",
                volume.location or "",
            ))

    def command_volumels(self, label):
        """
        Lists what's on a volume.

        Usage: volumels <label>
        """
        volume = self.config.index().volume(label)
        if volume is None:
            self.fatal("No volume with label %s" % label)# Print output
        fmt = "%-20s %-10s %s"
        print(cyan(fmt % ("MODIFIED", "SIZE", "PATH")))
        for file in volume.files():
            print(fmt % (
                file.modified,
                human_size(file.size),
                file.path,
            ))

    def command_location(self, label, location):
        """
        Shows/sets the location field for a volume.

        Usage: location <label> [<new_value>]
        """
        volume = self.config.index().volume(label)
        if volume is None:
            self.fatal("No volume with label %s" % label)
        volume.set_location(location)
        self.success(" > Set location of volume %s" % label)

    def command_voltype(self, label, voltype):
        """
        Shows/sets the type field for a volume.

        Usage: voltype <label> [<new_value>]
        """
        volume = self.config.index().volume(label)
        if volume is None:
            self.fatal("No volume with label %s" % label)
        volume.set_type(voltype)
        self.success(" > Set type of volume %s" % label)

    def command_destroyed(self, label):
        """
        Marks a volume as destroyed and removes it from the index.

        Usage: destroyed <label>
        """
        self.config.index().volume(label).destroyed()
        self.success(" > %s marked as destroyed." % label)

    def command_verify(self, label=None):
        """
        Runs verification on visible volumes.

        Usage: verify [<label>]
        """
        for volume in self.config.visible_volumes():
            if label and volume.label != label:
                continue
            self.info("Verifying volume %s..." % volume.label)
            # Try SHA1 verify first
            sha1_result = volume.sha1_verify()
            if sha1_result is True:
                self.success(" > Volume checksum matches.")
                continue
            elif sha1_result is False:
                self.error(" ! Volume corrupted - SHA1 mismatch.")
                continue
            # Then try PAR2 verify
            self.info(" - No checksum, running PAR2 verify")
            volume.par2_verify()

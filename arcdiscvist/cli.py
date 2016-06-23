import os
import sys
import argparse
import logging
import importlib

from .color import red, green, cyan, yellow
from .config import Config
from .builder import Builder
from .utils import human_size
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
            "subargs",
            nargs=argparse.REMAINDER,
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
            help='Don\' prompt for confirmations',
            default=False,
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
            if self.noninteractive:
                self.info("Running in noninteractive mode")
            # Run right subcommand
            handler = getattr(self, "command_%s" % args.command, None)
            if not handler:
                self.fatal("Unknown command %s" % args.command)
            handler(*args.subargs)
        except (ConfigError, BuildError) as e:
            self.fatal(str(e))

    def command_build(self, *args):
        """
        Builds new volumes.
        """
        if len(args) < 1:
            self.fatal("You must provide a target device path")
        device = args[0]
        filters = args[1:]
        # Work out where we're building
        builder = Builder(self.config.source(), self.config.index())
        self.info("Examining target device...")
        builder.prep_writer(device)
        self.success(" > Target is type %s, size %s" % (
            builder.writer.type,
            human_size(builder.writer.size),
        ))
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
        def progress(step, state):
            if step == "prep":
                if state == "start":
                    self.info("Prepping destination...")
                elif state == "end":
                    self.success(" > Done.")
            elif step == "copy":
                if state == "start":
                    self.info("Copying files...")
                elif state == "end":
                    self.success("\n > Done.")
            elif step == "parity":
                if state == "start":
                    self.info("Creating parity file...")
                elif state == "end":
                    self.success(" > Done.")
            elif step == "commit":
                if state == "start":
                    if builder.writer.burn:
                        self.info("Burning media...")
                    else:
                        self.info("Syncing disk...")
                elif state == "end":
                    self.success(" > Done.")
            elif step == "copyfile":
                self.info_replace(" - Copying %i/%i: %s" % state)
        builder.build(progress)
        self.info("Created new volume %s" % builder.volume_label)

    def command_index(self):
        index = self.config.index()
        for volume in self.config.visible_volumes():
            self.info("Indexing volume %s..." % volume.label)
            added = index.index_volume_directory(volume)
            self.success(" > %s files indexed." % added)

    def command_list(self, dirname=""):
        self._print_search_files(self.config.index().file_list(dirname))

    def command_find(self, pattern):
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
        if label:
            volumes = [self.config.index().volume(label)]
            if volumes[0] is None:
                self.fatal("No volume with label %s" % label)
        else:
            volumes = self.config.index().volumes()
        # Print output
        fmt = "%-10s %-10s %-20s %s"
        print(cyan(fmt % ("LABEL", "SIZE", "CREATED", "LOCATION")))
        for volume in sorted(volumes, key=lambda v: v.label):
            print(fmt % (
                volume.label,
                human_size(volume.size),
                volume.created,
                volume.location or "",
            ))

    def command_location(self, label, location):
        volume = self.config.index().volume(label)
        if volume is None:
            self.fatal("No volume with label %s" % label)
        volume.set_location(location)
        self.success(" > Set location of volume %s" % label)

    def command_destroyed(self, label):
        self.config.index().volume(label).destroyed()
        self.success(" > %s marked as destroyed." % label)

    def command_verify(self, label=None):
        """
        Runs verification on visible volumes.
        """
        for volume in self.config.visible_volumes():
            if label and volume.label != label:
                continue
            self.info("Verifying volume %s..." % volume.label)
            volume.verify()
            self.success(" > Done.")

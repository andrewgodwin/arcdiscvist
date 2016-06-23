Arcdiscvist
===========

Simple tool for managing archived data stored across a number of offline discs
or volumes, with a separate online index, and optional redundancy/recovery
files. Split into sub-commands.

Storage volumes are identified by a short label, like ``XERGQP``, and can be
either rewriteable media, like SD cards, or write-once media, like BD-R discs.
You can save data onto volumes, store them away offline, and use the index to
query which ones you need to access or restore certain files.

The storage is presented as a single unified folder hierarchy; sections can
be built and restored by path.

Automatically looks for and identifies storage volumes based on system drives
with an ``arcdiscvist-volume`` file in the top level.

You can also manually pass volume locations with the ``-v``/``--volume``
argument, if you have ones that are not being autodiscovered.

Works from a local folder on volatile storage that acts as the place to build
volumes from and restore them to, and which will mirror the storage folder
hierarchy.

Configuration is stored in ~/.arcdiscvist or in /etc/arcdiscvist.

Only works on linux-based systems for now.


list
----

::
    arcdiscvist list [<PATH>]

Lists files in the index by directory, like `ls`. With no arguments, lists
the root directory.


find
----

::
    arcdiscvist list <PATTEN>

Finds files in the index according to the PATTERN, which supports unix-style
globbing on the path.


build
-----

::
    arcdiscvist build <VOLUME_PATH> <PATH> [<PATH> ...]

Looks at the source directory, and builds as much of it as possible that is not
already in the index into a new volume.

You can specify which paths to consider as command-line arguments.

You can also request a different minimum number of copies with the ``-c``
argument; if a file is not present on this many different volumes, it will be
added to the built volume. The default number of copies is 1.

You should specify the path of the new volume; if it is a writeable CD/DVD/BR
drive, it will be burned with the new image, otherwise, it will be mounted
and written to directly.


restore
-------

::
    arcdiscvist restore <PATH> [<PATH> ...]

Given one or more paths in the archive, prompts for the volumes needed to
fully restore them and copies the data into the source directory.


verify
------

::
    arcdiscvist index

Runs verification on volumes to see if they're corrupted, and if so, if
they still have enough parity information to be recoverable.


index
-----

::
    arcdiscvist index

Adds details on all available volumes into the index. Will remove any files
no longer present on the volumes, and ignore ones that are already indexed.


volumes
-------

::
    arcdiscvist volumes

Lists all volumes the system knows about along with basic details.


destroyed
---------

::
    arcdiscvist destroyed <VOLUME_LABEL>

Marks a volume as destroyed or lost, removing all entries credited to it
from the index. You can undo this operation by running ``index`` on the volume.

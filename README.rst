Arcdiscvist
===========

Simple tool for managing archived data stored across a number of "bundles",
which can be stored on either remote storage, or physical media.

An online index allows quick querying of the structure of the entire backed-up
content without access to the original files, but is optional, and can be
rebuilt.

The storage is presented as a single unified folder hierarchy; sections can
be built and restored by path.

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

    arcdiscvist find <PATTEN>

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

    arcdiscvist verify

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

    arcdiscvist volumes [<LABEL>]

Lists all volumes the system knows about along with basic details. Provide
a label to just see details about a single volume.


destroyed
---------

::

    arcdiscvist destroyed <VOLUME_LABEL>

Marks a volume as destroyed or lost, removing all entries credited to it
from the index. You can undo this operation by running ``index`` on the volume.


Archive Format
--------------

Archives are gzipped tarballs that contain the files that are archived, plus
an "__arcdiscvist__" file that contains JSON describing the archive.

In most storage backends, they will be accompanied by the metadata file as a
separate item (so the entire tarball does not need to be retrieved for rebuild)
and can be optionally gzipped.

The file extensions are::

    ABCDEF.arcd
    ABCDEF.meta.arcd
    ADBCEF.arcd.gpg
    ABCDEF.meta.arcd.gpg

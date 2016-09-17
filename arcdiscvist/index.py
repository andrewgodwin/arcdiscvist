import sqlite3
import datetime
import random
import os

from .utils import get_fs_type


class Index(object):
    """
    Represents the index of available files and volumes.
    """

    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.check_schema()

    def check_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS Volumes (
                label text PRIMARY KEY,
                size integer,  -- In bytes
                created integer,  -- UNIX Timestamp
                location text,
                type text
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS Files (
                path text,
                volume text,
                size integer,  -- In bytes
                modified integer,  -- UNIX Timestamp
                PRIMARY KEY (path, volume),
                FOREIGN KEY (volume) REFERENCES Volumes(label)
            )
        """)

    def volumes(self):
        """
        Returns an iterable of all volumes.
        """
        for row in self.conn.execute("SELECT label, size, created, location, type FROM Volumes"):
            yield Volume(self, row[0], row[1],  datetime.datetime.fromtimestamp(row[2]), row[3], row[4])

    def volume(self, label):
        """
        Returns a single volume by label
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT label, size, created, location, type FROM Volumes WHERE label = ?", (label, ))
        row = cursor.fetchone()
        if row is None:
            return None
        else:
            return Volume(self, row[0], row[1], datetime.datetime.fromtimestamp(row[2]), row[3], row[4])

    def create_volume(self, label, size, created, location=None, type=None):
        """
        Creates a new volume record with the given info.
        """
        self.conn.execute(
            "INSERT INTO Volumes (label, size, created, location, type) VALUES (?, ?, ?, ?, ?)",
            (
                label,
                int(size),
                created.timestamp(),
                location,
                type,
            )
        )
        self.conn.commit()

    def file_list(self, dirname):
        """
        Returns a dict like {file path: ([volume_label, ...], size)}
        of files or directories under the dirname. Directories have size 0 and no volumes.
        """
        dirname = dirname.strip("/")
        cursor = self.conn.cursor()
        result = {}
        for path, volume, size in cursor.execute("SELECT path, volume, size FROM Files WHERE path LIKE ?", ("%s%%" % dirname,)):
            bits = path.split("/")
            # Go through implicit directories and add any to result that match
            for i in range(len(bits)):
                new_path = "/".join(bits[:i])
                if os.path.dirname(new_path) == dirname and new_path:
                    result[new_path] = ([], 0)
                    break
            # Add us to the result if we match exactly
            if os.path.dirname(path) == dirname or path == dirname:
                if path not in result:
                    result[path] = ([], size)
                result[path][0].append(volume)
        return result

    def file_find(self, pattern):
        """
        Returns a dict like {file path: ([volume_label, ...], size)}
        of files that match the filter pattern
        """
        cursor = self.conn.cursor()
        result = {}
        for path, volume, size in cursor.execute("SELECT path, volume, size FROM Files WHERE path GLOB ?", (pattern,)):
            if path not in result:
                result[path] = ([], size)
            result[path][0].append(volume)
        return result

    def file_volumes(self, path, ontype=None):
        """
        Returns a list of volume labels the given file path is present on, if any.
        """
        cursor = self.conn.cursor()
        result = []
        if ontype is not None:
            query = cursor.execute("SELECT volume FROM Files INNER JOIN Volumes ON volume = label WHERE path = ? AND Volumes.type = ?", (path, ontype))
        else:
            query = cursor.execute("SELECT volume FROM Files WHERE path = ?", (path, ))
        for row in query:
            result.append(row[0])
        return result

    def new_volume_label(self):
        """
        Returns a new, unused volume label.
        """
        while True:
            label = "".join(random.choice("AABCDEEFGHIIKMNOOPQRSTUUVWXYYZ") for i in range(6))
            if self.volume(label) is None:
                return label

    def index_volume_directory(self, volume_directory):
        """
        Adds the contents of the volume directory to the index.
        """
        # Make sure it has an entry
        if self.volume(volume_directory.label) is None:
            self.create_volume(
                volume_directory.label,
                volume_directory.size(),
                volume_directory.created(),
                None,
                None,
            )
        volume = self.volume(volume_directory.label)
        # Update its type
        fstype, mountpoint = get_fs_type(volume_directory.path)
        if fstype in ["fuseblk", "ext3"]:
            volume.set_type("hdd")
        elif fstype in ["udf"]:
            volume.set_type("optical")
        else:
            print("Cannot determine volume type of %s, on %s" % (volume_directory.label, mountpoint))
            volume.set_type(None)
        # Index files
        added = 0
        for member in volume_directory.files():
            volume.index_file(member.name, member.size, member.mtime)
            added += 1
        return added


class Volume(object):
    """
    Represents a Volume
    """

    def __init__(self, index, label, size, created, location=None, type=None):
        self.index = index
        self.label = label
        self.size = size
        self.created = created
        self.location = location
        self.type = type

    def files(self, filters=None):
        """
        Returns an iterable of files, optionally filtered by paths.
        """
        cursor = self.index.conn.cursor()
        for row in cursor.execute("SELECT path, size, modified FROM Files WHERE volume = ?", [self.label]):
            yield File(
                self,
                row[0],
                row[1],
                datetime.datetime.fromtimestamp(row[2]),
            )

    def index_file(self, path, size, modified):
        """
        Creates/updates a file record
        """
        if isinstance(modified, datetime.datetime):
            modified = modified.timestamp()
        try:
            self.index.conn.execute(
                "INSERT INTO Files (path, volume, size, modified) VALUES (?, ?, ?, ?)",
                (
                    path,
                    self.label,
                    int(size),
                    modified,
                )
            )
        except sqlite3.IntegrityError:
            pass
        self.index.conn.commit()

    def destroyed(self):
        """
        Removes all information about this volume from the index
        """
        self.index.conn.execute("""
            DELETE FROM Files WHERE volume = ?
        """, (self.label, ))
        self.index.conn.execute("""
            DELETE FROM Volumes WHERE label = ?
        """, (self.label, ))
        self.index.conn.commit()

    def set_location(self, location):
        """
        Removes all information about this volume from the index
        """
        self.index.conn.execute("""
            UPDATE Volumes SET location = ? WHERE label = ?
        """, (location, self.label, ))
        self.index.conn.commit()

    def set_type(self, value):
        """
        Removes all information about this volume from the index
        """
        self.index.conn.execute("""
            UPDATE Volumes SET type = ? WHERE label = ?
        """, (value, self.label, ))
        self.index.conn.commit()


class File(object):
    """
    Represents a File
    """

    def __init__(self, volume, path, size, modified):
        self.volume = volume
        self.path = path
        self.size = size
        self.modified = modified

import datetime
import os
import random
import sqlite3
import time
from typing import Optional, Tuple


class Index(object):
    """
    Represents the index of available files and volumes.
    """

    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.check_schema()

    def check_schema(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id integer primary key,
                path text,
                archive_id text,
                size integer,  -- In bytes
                modified integer,  -- UNIX Timestamp
                FOREIGN KEY (archive_id) REFERENCES archives (id)
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS archives (
                id text primary key,
                sha1 text,
                size integer,  -- In bytes
                created integer  -- UNIX Timestamp
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS archive_copies (
                id integer primary key,
                archive_id text,
                backend text,
                location text,
                created integer,  -- UNIX Timestamp
                FOREIGN KEY (archive_id) REFERENCES archives (id)
            )
        """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files (path)")

    def files(self, path_glob=None, path_exact=None, archive_id=None):
        """
        Returns a dict of {file path: {"size": size}, ...}
        for files that match the query parameters provided.
        """
        cursor = self.conn.cursor()
        result = {}
        # Work out the query
        if path_exact:
            query = "WHERE path = ?", (path_exact,)
        elif path_glob:
            query = "WHERE path GLOB ?", (path_glob,)
        elif archive_id:
            query = "WHERE archive_id = ?", (archive_id,)
        else:
            raise ValueError("You must supply one filter to files()")
        # Run the query
        for path, archive_id, size, modified in cursor.execute(
            "SELECT path, archive_id, size, modified FROM files " + query[0], query[1]
        ):
            result[path] = {
                "size": size,
                "modified": modified,
                "archive_id": archive_id,
            }
        return result

    def archives(self, archive_id: Optional[str] = None):
        """
        Returns an iterable of archives, optionally filtering by id
        """
        cursor = self.conn.cursor()
        # Work out the query
        query: Tuple[str, Tuple] = ("", tuple())
        if archive_id:
            query = "WHERE id = ?", (archive_id,)
        # Run it
        results = []
        for archive_id, sha1, size, created in cursor.execute(
            "SELECT id, sha1, size, created FROM archives " + query[0], query[1]
        ):
            results.append(
                {
                    "id": archive_id,
                    "sha1": sha1,
                    "size": size,
                    "created": created,
                }
            )
        return results

    def volume_copies(self, label):
        """
        Returns an iterable of volume copies, filtering by label
        """
        cursor = self.conn.cursor()
        # Work out the query
        query = "WHERE volume_label = ?", (label,)
        # Run it
        results = []
        for volume_label, type, location, created in cursor.execute(
            "SELECT volume_label, type, location, created FROM volume_copies "
            + query[0],
            query[1],
        ):
            results.append(
                {
                    "volume_label": volume_label,
                    "type": type,
                    "location": location,
                    "created": created,
                }
            )
        return results

    def new_archive_id(self) -> str:
        """
        Returns a new, unused volume label.
        """
        for i in range(10000):
            new_id = "".join(
                random.choice("AABCDEEFGHIIKMNOOPQRSTUUVWXYYZ") for i in range(6)
            )
            if not self.archives(archive_id=new_id):
                return new_id
        raise ValueError("Could not find spare archive ID")

    def add_volume(self, label, sha1, size, created):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO volumes (label, sha1, size, created) VALUES (?, ?, ?, ?)",
            (label, sha1, size, created),
        )
        self.conn.commit()

    def add_file_copy(self, file_path, file_size, file_modified, volume_label):
        """
        Records that a copy of the file exists (and adds it to the Files table if this is the first copy)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO files (path, volume_label, size, modified) VALUES (?, ?, ?, ?)",
            (file_path, volume_label, file_size, file_modified),
        )
        self.conn.commit()

    def add_volume_copy(self, volume_label, type, location):
        """
        Adds a record of a volume copy
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO volume_copies (volume_label, type, location, created) VALUES (?, ?, ?, ?)",
            (volume_label, type, location, time.time()),
        )
        self.conn.commit()

    def remove_volume(self, label):
        """
        Removes a volume and its files
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM volume_copies WHERE volume_label = ?", (label,))
        cursor.execute("DELETE FROM files WHERE volume_label = ?", (label,))
        cursor.execute("DELETE FROM volumes WHERE label = ?", (label,))
        self.conn.commit()

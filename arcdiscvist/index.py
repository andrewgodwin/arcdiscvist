import random
import sqlite3
from typing import Dict, List, Optional, Tuple

from .archive import Archive


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
                backend_names text,  -- Comma separated
                size integer,  -- In bytes
                created integer  -- UNIX Timestamp
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

    # Archive operations

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

    def archives(self, archive_id: Optional[str] = None) -> List[Dict]:
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
        for archive_id, backend_names, size, created in cursor.execute(
            "SELECT id, backend_names, size, created FROM archives " + query[0],
            query[1],
        ):
            results.append(
                {
                    "id": archive_id,
                    "backend_names": backend_names.split(","),
                    "size": size,
                    "created": created,
                }
            )
        return results

    def add_archive(self, archive: Archive, backend_name: str):
        cursor = self.conn.cursor()
        # Add the main archive record
        cursor.execute(
            "INSERT INTO archives (id, backend_names, size, created) VALUES (?, ?, ?, ?)",
            (archive.id, backend_name, archive.size, archive.created),
        )
        # Add each file
        for file in archive.files:
            cursor.execute(
                "INSERT INTO files (path, archive_id, size, modified) VALUES (?, ?, ?, ?)",
                (file.path, archive.id, file.size, file.modified),
            )
        self.conn.commit()

    def remove_archive(self, archive_id: str):
        """
        Removes a volume and its files
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM files WHERE archive_id = ?", (archive_id,))
        cursor.execute("DELETE FROM archives WHERE id = ?", (archive_id,))
        self.conn.commit()

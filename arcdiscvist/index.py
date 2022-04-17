import random
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .archive import Archive


@dataclass
class IndexFile:
    path: str
    directory: bool
    size: int
    modified: int
    archive_ids: Set[str]


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

    def files(
        self, path_glob=None, path_exact=None, archive_id=None
    ) -> Dict[str, object]:
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

    def contents(self, path="") -> Dict[str, IndexFile]:
        """
        Returns the contents of the given directory, if anything.
        Does not error if the directory doesn't exist.
        """
        # Normalise the path
        path = path.strip("/")
        path_depth: int = len(path.split("/"))
        if not path:
            path_depth = 0
        # We select ALL items under, as directories are implied at any level
        cursor = self.conn.cursor()
        files = {}
        for entry_path, archive_id, size, modified in cursor.execute(
            "SELECT path, archive_id, size, modified FROM files WHERE path GLOB ?",
            [path + "*"],
        ):
            entry_path_parts = entry_path.split("/")
            # Is it a file directly under us?
            if len(entry_path_parts) - 1 == path_depth:
                files[entry_path_parts[-1]] = IndexFile(
                    path=entry_path,
                    directory=False,
                    size=size,
                    modified=modified,
                    archive_ids={archive_id},
                )
            # Is it an implicit directory?
            else:
                directory_name = entry_path_parts[path_depth]
                if directory_name not in files:
                    files[directory_name] = IndexFile(
                        path="/".join(entry_path_parts[: path_depth + 1]),
                        directory=True,
                        size=0,
                        modified=modified,
                        archive_ids={archive_id},
                    )
                else:
                    files[directory_name].modified = max(
                        files[directory_name].modified, modified
                    )
                    files[directory_name].archive_ids.add(archive_id)
        return files

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

import json
import logging
import os
import tarfile
from datetime import datetime
from typing import Dict, List

from .utils import normalize_tarinfo, tar_addbytes


class File:
    """
    An individually restorable file
    """

    def __init__(self, path: str, size: int, modified: int):
        self.path = path
        self.size = size
        self.modified = modified

    @classmethod
    def from_json(cls, data: Dict) -> "File":
        return cls(data["path"], data["size"], data["modified"])

    @classmethod
    def from_file(cls, path: str, root: str):
        stats = os.stat(os.path.join(root, path))
        return cls(path, stats.st_size, int(stats.st_mtime))

    def to_json(self) -> Dict:
        return {
            "path": self.path,
            "size": self.size,
            "modified": self.modified,
        }


class Archive:
    """
    Represents an archive that contains backed-up files.
    """

    def __init__(self, id: str, files: List[File], size: int, created: int):
        self.id = id
        self.files = files
        self.created = created
        self.size = size

    @classmethod
    def from_json(cls, data) -> "Archive":
        return cls(
            id=data["id"],
            files=[File.from_json(d) for d in data["files"]],
            created=data["created"],
            size=data["size"],
        )

    @classmethod
    def from_files(cls, id: str, paths: List[str], root: str) -> "Archive":
        # Create File objects for each file in the set of paths
        files = [File.from_file(path, root) for path in paths]
        return cls(
            id=id,
            files=files,
            created=int(datetime.utcnow().timestamp()),
            size=sum(f.size for f in files),
        )

    def to_json(self) -> Dict:
        """
        Returns the meta-information in a JSON compatible format
        """
        return {
            "id": self.id,
            "files": [f.to_json() for f in self.files],
            "created": self.created,
            "size": self.size,
        }

    def pack(self, root: str, archive_path: str) -> None:
        # Pack the files into the tarball
        with tarfile.open(archive_path, "w:gz") as tar:
            # Meta file
            tar_addbytes(
                tar,
                "__arcdiscvist__",
                json.dumps(self.to_json()).encode("ascii"),
            )
            # Actual files
            for file in self.files:
                logging.info("Packing %s", file.path)
                tar.add(
                    os.path.join(root, file.path),
                    arcname=file.path,
                    filter=normalize_tarinfo,
                )

    def unpack(self, root: str, archive_path: str) -> None:
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name != "__arcdiscvist__":
                    logging.info("Unpacking %s", member.name)
                    tar.extract(member, root, set_attrs=False)

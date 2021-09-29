import os
import logging
import json
from typing import List
from .base import BaseBackend

from ..archive import Archive


class LocalBackend(BaseBackend):
    """
    A backend that stores archives in a local folder, unencrypted.
    """

    def __init__(self, path):
        self.path = path

    def __repr__(self):
        return f"LocalBackend: {self.path}"

    def archive_list(self) -> List[str]:
        """
        Returns the set of available archives based on their meta files
        """
        result = []
        for filename in os.listdir(self.path):
            if filename.endswith(".meta.arcd"):
                result.append(filename.split(".")[0])
        return result

    def archive_store(self, root, archive: Archive) -> None:
        # Decide the path it will end up at
        archive_path = os.path.join(self.path, f"{archive.id}.arcd")
        meta_path = os.path.join(self.path, f"{archive.id}.arcd")
        # Write out the archive
        logging.info("Packing archive")
        archive.pack(root, archive_path)
        # Write out the meta file
        logging.info("Writing meta file")
        with open(meta_path, "w") as file:
            json.dump(archive.to_json(), file)

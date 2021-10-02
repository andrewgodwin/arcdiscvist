from typing import Dict, List

from ..archive import Archive


class BaseBackend:
    def archive_list(self) -> List[str]:
        """
        Retrieves the set of archive IDs available on this backend.
        """
        raise NotImplementedError()

    def archive_store(self, root: str, archive: Archive) -> None:
        """
        Pacls the given archive from the root and uploads to the backend.
        """
        raise NotImplementedError()

    def archive_retrieve(self, root: str, archive_id: str) -> None:
        """
        Downloads the given archive from the backend, and unpacks it to
        the root.
        """
        raise NotImplementedError()

    def archive_retrieve_meta(self, id: str) -> Dict:
        """
        Downloads just the archive's metadata from the backend,
        returning its decoded contents.
        """
        raise NotImplementedError()

import os


class Source(object):
    """
    Represents the "source directory", where files are copied to/from volumes
    in a matching hierarchy.
    """

    def __init__(self, path):
        self.path = os.path.abspath(path.rstrip("/"))

    def files(self, filters=None):
        """
        Returns an iterator over file paths, with optional filters.
        Filters should be a list of path prefixes.
        """
        for curpath, dirnames, filenames in os.walk(self.path):
            # Trim out dirnames not in the filter list
            for dirname in list(dirnames):
                dirpath = os.path.join(curpath, dirname)
                if filters and not any([f.startswith(dirpath) for f in filters]):
                    dirnames.remove(dirname)
            # Yield file objects that match.
            for filename in filenames:
                filepath = os.path.abspath(os.path.join(curpath, filename))
                yield filepath[len(self.path) + 1:]

    def size(self, path):
        """
        Returns local size on disk
        """
        return os.path.getsize(self.abspath(path))

    def abspath(self, path):
        """
        Returns local size on disk
        """
        assert not path.startswith("/")
        return os.path.join(self.path, path)

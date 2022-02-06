import os


class Scanner:
    """
    Scans the source directory trying to make a file list for the builder.
    """

    def __init__(
        self, root_path, patterns, ignore_directories=None, ignore_patterns=None
    ):
        self.root_path = root_path
        self.patterns = patterns
        self.ignore_directories = ignore_directories or ["arcdiscvist", "@eaDir"]
        self.ignore_patterns = ignore_patterns or ["Thumbs.db"]

    def paths(self):
        """
        Returns a list of (absolute) paths the builder could pick from.
        Does not remove items in the index or account for size.
        """
        for curpath, dirnames, filenames in os.walk(self.root_path):
            dirnames.sort()
            # Trim out dirnames not in the filter list
            for dirname in list(dirnames):
                dirbits = os.path.join(curpath, dirname)[
                    len(self.root_path) + 1 :
                ].split("/")
                if dirname in self.ignore_directories:
                    dirnames.remove(dirname)
                    continue
                if self.patterns:
                    for f in self.patterns:
                        fbits = f.strip("/").split("/")
                        complen = min(len(dirbits), len(fbits))
                        if dirbits[:complen] == fbits[:complen]:
                            break
                    else:
                        dirnames.remove(dirname)
            # Yield file objects that match.
            for filename in sorted(filenames):
                if filename.startswith("arcdiscvist-"):
                    continue
                if filename in self.ignore_patterns:
                    continue
                file_path = os.path.abspath(os.path.join(curpath, filename))
                # Make sure this file is all the way under a filter
                if self.patterns:
                    for filter in self.patterns:
                        if file_path.startswith(os.path.join(self.root_path, filter)):
                            break
                    else:
                        continue
                relative_path = file_path[len(self.root_path) + 1 :]
                yield relative_path

    def unstored_paths(self, index, size, pack_small=False):
        size_used = 0
        result = []
        for relative_path in self.paths():
            # See if it's in the index (if it's not at all, we skip the SHA hash)
            index_hit = index.files(path_exact=relative_path)
            file_size = os.path.getsize(os.path.join(self.root_path, relative_path))
            if index_hit:
                # Verify it's the same file (via size only for now)
                index_size = list(index_hit.values())[0]["size"]
                if index_size != file_size:
                    raise ValueError(
                        "File %s already in index but with different size! (%s != %s)"
                        % (
                            relative_path,
                            index_size,
                            file_size,
                        )
                    )
                continue
            # Add it to our collection
            if (size_used + file_size) <= size:
                size_used += file_size
                result.append(relative_path)
            elif not pack_small:
                break
        return result, size_used

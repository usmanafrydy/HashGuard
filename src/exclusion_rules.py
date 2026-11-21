
"""Handle file and folder exclusion rules for HashGuard."""

from fnmatch import fnmatchcase
from pathlib import PurePosixPath


def is_excluded(relative_path, exclusions=None):
    """Check whether a relative path matches an exclusion rule."""

    path = str(relative_path).replace("\\", "/").strip("/")
    filename = PurePosixPath(path).name

    for raw_rule in exclusions or []:
        rule = raw_rule.replace("\\", "/").strip()

        if not rule:
            continue

        # A rule ending in / excludes a directory and its contents.
        if rule.endswith("/"):
            directory = rule.rstrip("/")

            if path == directory or path.startswith(directory + "/"):
                return True

        # Rules containing / match paths relative to the root.
        elif "/" in rule:
            if fnmatchcase(path, rule):
                return True

        # Other rules match filenames anywhere in the tree.
        elif fnmatchcase(filename, rule):
            return True

    return False

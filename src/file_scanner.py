"""Folder scanning functionality for HashGuard."""

from pathlib import Path
from stat import S_ISDIR, S_ISREG


def validate_folder(folder_path):
    """Return a Path if the supplied location is an existing folder."""
    folder = Path(folder_path)
    folder_info = folder.stat()

    if not S_ISDIR(folder_info.st_mode):
        raise NotADirectoryError(f"Expected a folder: {folder}")

    return folder

def list_files(folder_path):
    """Return regular files directly inside the selected folder."""
    folder = validate_folder(folder_path)
    files = []

    for entry in folder.iterdir():
        entry_info = entry.stat(follow_symlinks=False)

        if S_ISREG(entry_info.st_mode):
            files.append(entry)

    return sorted(files)
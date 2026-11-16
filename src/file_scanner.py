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

def scan_folder(folder_path):
    """Return regular files in a folder and its subfolders."""
    root = validate_folder(folder_path)

    if root.is_symlink() or root.is_junction():
        raise ValueError(
            "Select a folder that is not a symbolic link or junction."
        )

    files = []
    folders_to_visit = [root]

    while folders_to_visit:
        current_folder = folders_to_visit.pop()

        for entry in current_folder.iterdir():
            entry_info = entry.stat(follow_symlinks=False)

            if S_ISREG(entry_info.st_mode):
                files.append(entry)
            elif S_ISDIR(entry_info.st_mode):
                if not entry.is_junction():
                    folders_to_visit.append(entry)

    return sorted(files)
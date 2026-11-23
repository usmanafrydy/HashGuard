"""Calculate SHA-256 hashes without loading whole files into memory."""

import hashlib
import os
from pathlib import Path
from typing import Union


def _file_identity(file_info):
    """Return the filesystem identity, or fail if it cannot be verified."""
    inode = getattr(file_info, "st_ino", None)
    device = getattr(file_info, "st_dev", None)
    if not inode or device is None:
        raise OSError("File identity is unavailable; cannot reliably verify file.")
    return device, inode


def hash_file(file_path: Union[str, Path]) -> str:
    """Return a file's SHA-256 hash as a 64-character hexadecimal string.

    Accept a string or Path. Raise FileNotFoundError for a missing file,
    PermissionError when access is denied, or OSError for other read errors.
    Verify the opened file's identity, size and modification time before and
    after reading, then check that the path still identifies that same file.
    Replacement, changes or unavailable identity information raise OSError.
    This detects observed races; it does not provide a filesystem snapshot or
    prevent changes after the final check.
    """
    path = Path(file_path)
    file_hash = hashlib.sha256()

    try:
        with path.open("rb") as file:
            before = os.fstat(file.fileno())
            identity = _file_identity(before)
            chunk = file.read(64 * 1024)
            while chunk:
                file_hash.update(chunk)
                chunk = file.read(64 * 1024)
            after = os.fstat(file.fileno())
            if _file_identity(after) != identity:
                raise OSError("File was replaced while being hashed.")
            if (before.st_size, before.st_mtime_ns) != (
                after.st_size, after.st_mtime_ns
            ):
                raise OSError("File changed while being hashed.")

        # Closing first permits this check to observe replacements on Windows,
        # where the open read handle may temporarily prevent rename/deletion.
        current = path.stat()
        if _file_identity(current) != identity:
            raise OSError("File was replaced while being hashed.")
        if (after.st_size, after.st_mtime_ns) != (
            current.st_size, current.st_mtime_ns
        ):
            raise OSError("File changed while being hashed.")
    except FileNotFoundError as error:
        raise FileNotFoundError(f"File not found: {path}") from error
    except PermissionError as error:
        raise PermissionError(f"Permission denied when reading file: {path}") from error
    except OSError as error:
        raise OSError(f"Could not read file '{path}': {error}") from error

    return file_hash.hexdigest()

"""Calculate SHA-256 hashes without loading whole files into memory."""

import hashlib
from pathlib import Path
from typing import Union


def hash_file(file_path: Union[str, Path]) -> str:
    """Return a file's SHA-256 hash as a 64-character hexadecimal string.

    Accept a string or Path. Raise FileNotFoundError for a missing file,
    PermissionError when access is denied, or OSError for other read errors.
    """
    path = Path(file_path)
    file_hash = hashlib.sha256()

    try:
        with path.open("rb") as file:
            chunk = file.read(64 * 1024)
            while chunk:
                file_hash.update(chunk)
                chunk = file.read(64 * 1024)
    except FileNotFoundError as error:
        raise FileNotFoundError(f"File not found: {path}") from error
    except PermissionError as error:
        raise PermissionError(f"Permission denied when reading file: {path}") from error
    except OSError as error:
        raise OSError(f"Could not read file '{path}': {error}") from error

    return file_hash.hexdigest()

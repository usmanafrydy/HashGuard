"""Create, save, load, and validate HashGuard file integrity baselines."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.file_hasher import hash_file
from src.file_scanner import scan_folder


HASH_ALGORITHM = "SHA-256"
BASELINE_VERSION = 1


def create_baseline(folder_path, exclusions=None):
    """Create baseline data for successfully verified files."""
    selected_folder = Path(folder_path)

    if selected_folder.is_symlink() or selected_folder.is_junction():
        raise ValueError(
            "Select a folder that is not a symbolic link or junction."
        )

    root = selected_folder.resolve()

    if not root.is_dir():
        raise NotADirectoryError(f"Expected an existing folder: {root}")

    exclusions = list(exclusions or [])
    files = {}
    failed_files = []

    try:
        scanned_files = scan_folder(root)
    except OSError as error:
        failed_files.append({
            "path": ".",
            "error": f"Folder scanning failed: {error}",
        })
        scanned_files = []

    for file_path in scanned_files:
        relative_path = file_path.relative_to(root).as_posix()

        if relative_path in exclusions:
            continue

        try:
            before = file_path.stat()
            file_hash = hash_file(file_path)
            after = file_path.stat()

            if (
                before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
            ):
                raise OSError("File changed while being hashed.")

            files[relative_path] = file_hash

        except OSError as error:
            failed_files.append({
                "path": relative_path,
                "error": str(error),
            })

    return {
        "version": BASELINE_VERSION,
        "root_path": str(root),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": HASH_ALGORITHM,
        "exclusions": exclusions,
        "files": files,
        "failed_files": failed_files,
        "complete": len(failed_files) == 0,
    }


def save_baseline(baseline, destination):
    """Save a validated baseline without overwriting an existing file."""
    destination = Path(destination)

    if destination.exists():
        raise FileExistsError(
            f"Baseline already exists: {destination}. "
            "Choose a different filename to create a new baseline."
        )

    validate_baseline(baseline)

    monitored_folder = Path(baseline["root_path"]).resolve()
    resolved_destination = destination.resolve()

    try:
        resolved_destination.relative_to(monitored_folder)
    except ValueError:
        pass
    else:
        raise ValueError(
            "Baseline must be saved outside the monitored folder."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("x", encoding="utf-8") as file:
        json.dump(baseline, file, indent=4)


def load_baseline(source):
    """Load and validate a saved JSON baseline."""
    source = Path(source)

    with source.open("r", encoding="utf-8") as file:
        baseline = json.load(file)

    validate_baseline(baseline)

    return baseline


def validate_baseline(baseline, selected_folder=None):
    """Validate baseline structure, records, and optional folder matching."""
    if not isinstance(baseline, dict):
        raise ValueError("Invalid baseline: expected a JSON object.")

    required_fields = {
        "version",
        "root_path",
        "created_at",
        "algorithm",
        "exclusions",
        "files",
        "failed_files",
        "complete",
    }

    missing_fields = required_fields - baseline.keys()

    if missing_fields:
        raise ValueError(
            f"Invalid baseline: missing fields: "
            f"{', '.join(sorted(missing_fields))}"
        )

    if type(baseline["version"]) is not int:
        raise ValueError("Invalid baseline version.")

    if baseline["version"] != BASELINE_VERSION:
        raise ValueError("Unsupported baseline version.")

    root_path = baseline["root_path"]

    if not isinstance(root_path, str) or not root_path:
        raise ValueError("Invalid baseline root path.")

    if not Path(root_path).is_absolute():
        raise ValueError("Baseline root path must be absolute.")

    try:
        timestamp = datetime.fromisoformat(
            baseline["created_at"].replace("Z", "+00:00")
        )

        if timestamp.tzinfo is None:
            raise ValueError

    except (TypeError, AttributeError, ValueError):
        raise ValueError("Invalid baseline creation timestamp.") from None

    if baseline["algorithm"] != HASH_ALGORITHM:
        raise ValueError("Unsupported hash algorithm.")

    exclusions = baseline["exclusions"]

    if (
        not isinstance(exclusions, list)
        or not all(isinstance(item, str) and item for item in exclusions)
    ):
        raise ValueError("Invalid baseline exclusions.")

    files = baseline["files"]

    if not isinstance(files, dict):
        raise ValueError("Invalid baseline file records.")

    for relative_path, file_hash in files.items():
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("Invalid relative file path.")

        path = Path(relative_path)

        if (
            path.is_absolute()
            or "\\" in relative_path
            or any(
                part in ("", ".", "..")
                for part in relative_path.split("/")
            )
        ):
            raise ValueError(f"Unsafe relative file path: {relative_path}")

        # Correct SHA-256 validation: exactly 64 hexadecimal characters.
        if not isinstance(file_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}", file_hash
        ):
            raise ValueError(
                f"Invalid SHA-256 hash for: {relative_path}"
            )

    failed_files = baseline["failed_files"]

    if not isinstance(failed_files, list):
        raise ValueError("Invalid failed-file records.")

    for record in failed_files:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("path"), str)
            or not record["path"]
            or not isinstance(record.get("error"), str)
            or not record["error"]
        ):
            raise ValueError("Invalid failed-file record.")

    if type(baseline["complete"]) is not bool:
        raise ValueError("Invalid baseline completion status.")

    expected_complete = len(failed_files) == 0

    if baseline["complete"] != expected_complete:
        raise ValueError(
            "Baseline completion status does not match failed files."
        )

    if selected_folder is not None:
        selected_root = Path(selected_folder).resolve()
        baseline_root = Path(root_path).resolve()

        if selected_root != baseline_root:
            raise ValueError("Baseline belongs to a different folder.")

    return True

"""Detect added, modified, deleted, and unchanged files in HashGuard."""

from pathlib import Path

from src.file_hasher import hash_file
from src.file_scanner import scan_folder
from src.baseline_manager import validate_baseline


def scan_current_folder(folder_path, exclusions=None):
    """Hash files currently present in the monitored folder."""

    selected_folder = Path(folder_path)

    if selected_folder.is_symlink() or selected_folder.is_junction():
        raise ValueError(
            "Select a folder that is not a symbolic link or junction."
        )

    root = selected_folder.resolve()
    exclusions = set(exclusions or [])

    current_files = {}
    failed_files = []

    try:
        scanned_files = scan_folder(root)
    except OSError as error:
        return {
            "files": {},
            "failed_files": [
                {
                    "path": ".",
                    "error": f"Folder scanning failed: {error}",
                }
            ],
            "complete": False,
        }

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

            current_files[relative_path] = file_hash

        except OSError as error:
            failed_files.append(
                {
                    "path": relative_path,
                    "error": str(error),
                }
            )

    return {
        "files": current_files,
        "failed_files": failed_files,
        "complete": len(failed_files) == 0,
    }


def detect_changes(baseline, current_scan):
    """Compare a baseline with a current scan and classify file changes."""

    baseline_files = baseline["files"]
    current_files = current_scan["files"]

    baseline_failed = {
        record["path"]
        for record in baseline.get("failed_files", [])
    }

    current_failed = {
        record["path"]
        for record in current_scan.get("failed_files", [])
    }

    baseline_complete = baseline.get("complete", False)
    current_complete = current_scan.get("complete", False)

    all_paths = sorted(
        (
            set(baseline_files)
            | set(current_files)
            | baseline_failed
            | current_failed
        ) - {"."}
    )

    results = {
        "unchanged": [],
        "modified": [],
        "added": [],
        "deleted": [],
        "unverified": [],
    }

    for relative_path in all_paths:
        in_baseline = relative_path in baseline_files
        in_current = relative_path in current_files

        # File could not be verified in either scan.
        if (
            relative_path in baseline_failed
            or relative_path in current_failed
        ):
            results["unverified"].append(relative_path)
            continue

        # File exists in both scans.
        if in_baseline and in_current:
            if baseline_files[relative_path] == current_files[relative_path]:
                results["unchanged"].append(relative_path)
            else:
                results["modified"].append(relative_path)

        # File exists only in the current scan.
        elif in_current:
            if baseline_complete:
                results["added"].append(relative_path)
            else:
                results["unverified"].append(relative_path)

        # File exists only in the baseline.
        elif in_baseline:
            if current_complete:
                results["deleted"].append(relative_path)
            else:
                results["unverified"].append(relative_path)

    return {
        "results": results,
        "summary": {
            "unchanged": len(results["unchanged"]),
            "modified": len(results["modified"]),
            "added": len(results["added"]),
            "deleted": len(results["deleted"]),
            "unverified": len(results["unverified"]),
            "total": sum(len(files) for files in results.values()),
        },
        "baseline_complete": baseline_complete,
        "current_scan_complete": current_complete,
    }


def compare_folder_with_baseline(baseline, folder_path):
    """Scan a folder and compare it with its saved baseline."""

    validate_baseline(baseline, selected_folder=folder_path)

    current_scan = scan_current_folder(
        folder_path,
        exclusions=baseline.get("exclusions", []),
    )

    comparison = detect_changes(baseline, current_scan)

    comparison["current_scan"] = current_scan

    return comparison

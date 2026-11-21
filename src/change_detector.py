
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
    exclusions = list(exclusions or [])

    current_files = {}
    failed_files = []

    try:
        scanned_files = scan_folder(
            root,
            exclusions=exclusions,
            errors=failed_files,
        )

    except OSError as error:
        failed_files.append({
            "path": ".",
            "error": f"Folder scanning failed: {error}",
            "kind": "folder",
        })

        scanned_files = []

    for file_path in scanned_files:
        relative_path = file_path.relative_to(root).as_posix()

        try:
            before = file_path.stat()
            file_hash = hash_file(file_path)
            after = file_path.stat()

            if (
                before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
            ):
                raise OSError(
                    "File changed while being hashed."
                )

            current_files[relative_path] = file_hash

        except OSError as error:
            failed_files.append({
                "path": relative_path,
                "error": str(error),
                "kind": "file",
            })

    return {
        "files": current_files,
        "failed_files": failed_files,
        "complete": len(failed_files) == 0,
    }


def _affected_by_scan_error(relative_path, failed_records):
    """Check whether an error prevents reliable verification."""

    for record in failed_records:
        failed_path = record["path"]
        kind = record.get("kind", "file")

        # A root scanning failure affects every file.
        if failed_path == ".":
            return True

        # The individual file or entry could not be checked.
        if relative_path == failed_path:
            return True

        # A failed folder or unknown entry may contain this file.
        if kind in ("folder", "entry"):
            prefix = failed_path.rstrip("/") + "/"

            if relative_path.startswith(prefix):
                return True

    return False




def detect_changes(baseline, current_scan):
    """Compare baseline and current scan file hashes."""

    baseline_files = baseline["files"]
    current_files = current_scan["files"]

    baseline_failed = baseline.get("failed_files", [])
    current_failed = current_scan.get("failed_files", [])

    baseline_complete = baseline.get("complete", False)
    current_complete = current_scan.get("complete", False)

    # Include confirmed file errors, but not folder errors.
    file_error_paths = {
        record["path"]
        for record in baseline_failed + current_failed
        if (
            record["path"] != "."
            and record.get("kind", "file") == "file"
        )
    }

    all_paths = sorted(
        set(baseline_files)
        | set(current_files)
        | file_error_paths
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

        # Check whether an error affects this file.
        if (
            _affected_by_scan_error(
                relative_path, baseline_failed
            )
            or _affected_by_scan_error(
                relative_path, current_failed
            )
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

    summary = {
        "unchanged": len(results["unchanged"]),
        "modified": len(results["modified"]),
        "added": len(results["added"]),
        "deleted": len(results["deleted"]),
        "unverified": len(results["unverified"]),
    }

    summary["total"] = sum(summary.values())

    return {
        "results": results,
        "summary": summary,
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

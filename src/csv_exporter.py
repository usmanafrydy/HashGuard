"""Export comparison results and verification context in one CSV table.

Columns: File Path, Status, Record Type, Source, Complete, Error, Kind.
Each ``file`` record has one relative path and its original lowercase status.
Two ``scan`` records describe baseline/current completion (true or false).
``error`` records preserve each scan's error path, message and kind; '.' means
the selected folder. Scan/error rows have no file Status and are not changes.
Rows are ordered by relative file path, then baseline/current scan metadata,
then errors sorted by source, path, kind and message. Even empty comparisons
include the header and both scan records.

Spreadsheet protection: text starting with =, +, -, @ (also after leading
whitespace), or a tab/newline/carriage return is prefixed with an apostrophe.
This deliberately changes dangerous display values; ordinary paths and text
are preserved. CSV quoting alone does not prevent spreadsheet formulas.
"""

import csv
import os
from pathlib import Path
import tempfile


STATUSES = ("added", "modified", "deleted", "unchanged", "unverified")
COLUMNS = ("File Path", "Status", "Record Type", "Source", "Complete", "Error", "Kind")


def _spreadsheet_text(value):
    """Keep untrusted text from being interpreted as a spreadsheet formula."""
    if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(
        ("=", "+", "-", "@")
    ):
        return "'" + value
    return value


def export_comparison_csv(baseline, comparison, output_path):
    """Export data from compare_folder_with_baseline(); return None.

    Do not rescan or reclassify files. The destination's parent must exist and
    the report must be outside the monitored folder. An existing report is
    replaced only after the whole CSV has been written and closed successfully.
    Raise ValueError for a destination inside the monitored folder, and OSError
    (including PermissionError) with destination context for write failures.
    Missing comparison fields raise KeyError before any output is written.
    """
    destination = Path(output_path).resolve()
    monitored_folder = Path(baseline["root_path"]).resolve()
    if destination.is_relative_to(monitored_folder):
        raise ValueError("CSV report must be saved outside the monitored folder.")

    # Prepare rows before opening anything; leave the supplied data untouched.
    files = sorted(
        (path, status)
        for status in STATUSES
        for path in comparison["results"][status]
    )
    rows = [(path, status, "file", "", "", "", "") for path, status in files]
    for source, complete in (
        ("baseline", comparison["baseline_complete"]),
        ("current", comparison["current_scan_complete"]),
    ):
        rows.append(("", "", "scan", source, str(complete).lower(), "", ""))

    for source, errors in (
        ("baseline", baseline["failed_files"]),
        ("current", comparison["current_scan"]["failed_files"]),
    ):
        for error in sorted(
            errors,
            key=lambda item: (item["path"], item.get("kind", "file"), item["error"]),
        ):
            rows.append((
                error["path"], "", "error", source, "", error["error"],
                error.get("kind", "file"),
            ))

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=destination.parent,
            prefix=".hashguard-", suffix=".tmp", delete=False,
        ) as output:
            temporary_path = Path(output.name)
            writer = csv.writer(output)
            writer.writerow(COLUMNS)
            for row in rows:
                writer.writerow([_spreadsheet_text(value) for value in row])
        os.replace(temporary_path, destination)
    except OSError as error:
        message = f"Could not export CSV report to '{destination}': {error}"
        if isinstance(error, PermissionError):
            raise PermissionError(message) from error
        raise OSError(message) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

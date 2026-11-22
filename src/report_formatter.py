"""Format HashGuard comparison results as readable text."""


STATUS_LABELS = (
    ("added", "Added"),
    ("modified", "Modified"),
    ("deleted", "Deleted"),
    ("unchanged", "Unchanged"),
    ("unverified", "Unverified"),
)


def format_report(baseline, comparison):
    """
    Return a text report without changing the supplied data.

    Use the baseline and result from compare_folder_with_baseline().
    This function does not scan files or save the report.
    """

    baseline_status = (
        "Complete" if comparison["baseline_complete"] else "Incomplete"
    )
    current_status = (
        "Complete" if comparison["current_scan_complete"] else "Incomplete"
    )

    lines = [
        "HashGuard Scan Report",
        "====================",
        f"Folder: {baseline['root_path']}",
        f"Baseline created: {baseline['created_at']}",
        f"Algorithm: {baseline['algorithm']}",
        f"Baseline: {baseline_status}",
        f"Current scan: {current_status}",
    ]

    if (
        not comparison["baseline_complete"]
        or not comparison["current_scan_complete"]
        or comparison["summary"]["unverified"] > 0
    ):
        lines.extend([
            "",
            "WARNING: Verification is incomplete.",
            "Some files or locations could not be checked reliably.",
        ])

    lines.extend(["", "Summary"])

    for status, label in STATUS_LABELS:
        lines.append(f"  {label}: {comparison['summary'][status]}")

    lines.append(
        f"  Total file results: {comparison['summary']['total']}"
    )

    lines.extend(["", "File results"])

    has_results = False

    for status, label in STATUS_LABELS:
        for relative_path in sorted(comparison["results"][status]):
            lines.append(f"  {label}: {relative_path}")
            has_results = True

    if not has_results:
        lines.append("  No file results are available.")

    error_groups = (
        ("Baseline errors", baseline["failed_files"]),
        (
            "Current scan errors",
            comparison["current_scan"]["failed_files"],
        ),
    )

    for title, errors in error_groups:
        lines.extend(["", title])

        if not errors:
            lines.append("  None.")
            continue

        for error in errors:
            path = error["path"]

            if path == ".":
                path = "[selected folder]"

            lines.append(f"  {path}: {error['error']}")

    return "\n".join(lines) + "\n"
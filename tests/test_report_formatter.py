"""Tests for readable HashGuard comparison reports."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.baseline_manager import create_baseline
from src.change_detector import compare_folder_with_baseline
from src.report_formatter import format_report


class TestReportFormatter(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name).resolve()

    def write_file(self, name, content):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_report_displays_changes_counts_and_folder(self):
        self.write_file("same.txt", "Same")
        changed = self.write_file("changed.txt", "Original")
        removed = self.write_file("removed.txt", "Remove")

        baseline = create_baseline(self.root)

        changed.write_text("Changed", encoding="utf-8")
        removed.unlink()
        self.write_file("new.txt", "New")

        comparison = compare_folder_with_baseline(baseline, self.root)
        text = format_report(baseline, comparison)

        self.assertIn(f"Folder: {self.root}", text)
        self.assertIn("Baseline: Complete", text)
        self.assertIn("Current scan: Complete", text)

        for expected in (
            "Added: new.txt",
            "Modified: changed.txt",
            "Deleted: removed.txt",
            "Unchanged: same.txt",
            "Added: 1",
            "Modified: 1",
            "Deleted: 1",
            "Unchanged: 1",
            "Unverified: 0",
            "Total file results: 4",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

        self.assertNotIn("WARNING:", text)

    def test_current_file_error_is_visible(self):
        self.write_file("blocked.txt", "Data")
        baseline = create_baseline(self.root)

        with patch(
            "src.change_detector.hash_file",
            side_effect=PermissionError("Current read denied"),
        ):
            comparison = compare_folder_with_baseline(
                baseline, self.root
            )

        text = format_report(baseline, comparison)

        self.assertIn("Current scan: Incomplete", text)
        self.assertIn("WARNING: Verification is incomplete.", text)
        self.assertIn("Unverified: blocked.txt", text)
        self.assertIn("Unverified: 1", text)

        current_errors = text.split("Current scan errors\n", 1)[1]
        self.assertIn("blocked.txt: Current read denied", current_errors)
        self.assertNotIn("Deleted: blocked.txt", text)

    def test_baseline_error_remains_visible_after_successful_scan(self):
        self.write_file("blocked.txt", "Data")

        with patch(
            "src.baseline_manager.hash_file",
            side_effect=PermissionError("Baseline read denied"),
        ):
            baseline = create_baseline(self.root)

        comparison = compare_folder_with_baseline(baseline, self.root)
        text = format_report(baseline, comparison)

        self.assertIn("Baseline: Incomplete", text)
        self.assertIn("Current scan: Complete", text)
        self.assertIn("WARNING: Verification is incomplete.", text)
        self.assertIn("Unverified: blocked.txt", text)

        baseline_errors = text.split("Baseline errors\n", 1)[1]
        baseline_errors = baseline_errors.split(
            "Current scan errors\n", 1
        )[0]

        self.assertIn(
            "blocked.txt: Baseline read denied",
            baseline_errors,
        )

    def test_folder_error_is_visible_even_without_file_results(self):
        baseline = create_baseline(self.root)

        with patch(
            "src.change_detector.scan_folder",
            side_effect=PermissionError("Folder access denied"),
        ):
            comparison = compare_folder_with_baseline(
                baseline, self.root
            )

        text = format_report(baseline, comparison)

        self.assertIn("Total file results: 0", text)
        self.assertIn("No file results are available.", text)
        self.assertIn("Current scan: Incomplete", text)
        self.assertIn("WARNING: Verification is incomplete.", text)
        self.assertIn("[selected folder]:", text)
        self.assertIn("Folder access denied", text)

    def test_complete_empty_scan_has_no_warning(self):
        baseline = create_baseline(self.root)
        comparison = compare_folder_with_baseline(baseline, self.root)

        text = format_report(baseline, comparison)

        self.assertIn("Total file results: 0", text)
        self.assertIn("No file results are available.", text)
        self.assertNotIn("WARNING:", text)

    def test_formatting_does_not_modify_input_data(self):
        self.write_file("sample.txt", "Data")
        baseline = create_baseline(self.root)
        comparison = compare_folder_with_baseline(baseline, self.root)

        original_baseline = deepcopy(baseline)
        original_comparison = deepcopy(comparison)

        format_report(baseline, comparison)

        self.assertEqual(baseline, original_baseline)
        self.assertEqual(comparison, original_comparison)


if __name__ == "__main__":
    unittest.main(verbosity=2)
"""Regression tests for baseline comparison validation and errors."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.baseline_manager import create_baseline
from src.change_detector import (
    compare_folder_with_baseline,
    scan_current_folder,
)


class TestComparisonRegressions(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.base = Path(self.temporary_directory.name)
        self.root = self.base / "monitored"
        self.root.mkdir()

    def test_wrong_folder_is_rejected_before_scanning(self):
        baseline = create_baseline(self.root)
        other_folder = self.base / "other"
        other_folder.mkdir()

        with patch("src.change_detector.scan_current_folder") as scan:
            with self.assertRaisesRegex(ValueError, "different folder"):
                compare_folder_with_baseline(baseline, other_folder)

            scan.assert_not_called()

    def test_invalid_baseline_is_rejected_before_scanning(self):
        baseline = create_baseline(self.root)
        baseline["algorithm"] = "invalid-algorithm"

        with patch("src.change_detector.scan_current_folder") as scan:
            with self.assertRaisesRegex(
                ValueError, "Unsupported hash algorithm"
            ):
                compare_folder_with_baseline(baseline, self.root)

            scan.assert_not_called()

    def test_new_unreadable_file_is_unverified(self):
        baseline = create_baseline(self.root)
        (self.root / "new.txt").write_text("New", encoding="utf-8")

        with patch(
            "src.change_detector.hash_file",
            side_effect=PermissionError("Access denied"),
        ):
            report = compare_folder_with_baseline(baseline, self.root)

        self.assertEqual(report["results"]["unverified"], ["new.txt"])
        self.assertEqual(report["results"]["added"], [])
        self.assertEqual(report["summary"]["unverified"], 1)
        self.assertEqual(report["summary"]["total"], 1)

    def test_file_unreadable_in_both_scans_is_unverified(self):
        (self.root / "blocked.txt").write_text(
            "Data", encoding="utf-8"
        )

        with patch(
            "src.baseline_manager.hash_file",
            side_effect=PermissionError("Access denied"),
        ):
            baseline = create_baseline(self.root)

        with patch(
            "src.change_detector.hash_file",
            side_effect=PermissionError("Access denied"),
        ):
            report = compare_folder_with_baseline(baseline, self.root)

        self.assertEqual(
            report["results"]["unverified"], ["blocked.txt"]
        )
        self.assertEqual(report["summary"]["total"], 1)

    def test_folder_error_is_not_counted_as_a_file(self):
        baseline = create_baseline(self.root)

        with patch(
            "src.change_detector.scan_folder",
            side_effect=PermissionError("Access denied"),
        ):
            report = compare_folder_with_baseline(baseline, self.root)

        self.assertFalse(report["current_scan_complete"])
        self.assertEqual(report["summary"]["total"], 0)
        self.assertEqual(
            report["current_scan"]["failed_files"][0]["path"],
            ".",
        )

    def test_linked_root_is_rejected_before_resolving(self):
        link = self.base / "selected_link"

        for method in ("is_symlink", "is_junction"):
            with self.subTest(link_type=method):
                with patch.object(
                    Path, method, new=lambda path: path == link
                ):
                    with patch.object(
                        Path, "resolve", return_value=self.root
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "symbolic link or junction"
                        ):
                            scan_current_folder(link)


if __name__ == "__main__":
    unittest.main(verbosity=2)
"""Tests for HashGuard's change detection engine."""

import tempfile
import unittest
from pathlib import Path

from src.baseline_manager import create_baseline
from src.change_detector import (
    compare_folder_with_baseline,
    detect_changes,
    scan_current_folder,
)


class TestChangeDetector(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_file(self, name, content):
        file_path = self.root / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def test_unchanged_file(self):
        self.create_file("file.txt", "original content")

        baseline = create_baseline(self.root)

        comparison = compare_folder_with_baseline(
            baseline,
            self.root,
        )

        self.assertEqual(
            comparison["results"]["unchanged"],
            ["file.txt"],
        )

    def test_modified_file(self):
        file_path = self.create_file("file.txt", "original content")

        baseline = create_baseline(self.root)

        file_path.write_text("changed content", encoding="utf-8")

        comparison = compare_folder_with_baseline(
            baseline,
            self.root,
        )

        self.assertEqual(
            comparison["results"]["modified"],
            ["file.txt"],
        )

    def test_added_file(self):
        baseline = create_baseline(self.root)

        self.create_file("new_file.txt", "new content")

        comparison = compare_folder_with_baseline(
            baseline,
            self.root,
        )

        self.assertEqual(
            comparison["results"]["added"],
            ["new_file.txt"],
        )

    def test_deleted_file(self):
        self.create_file("old_file.txt", "old content")

        baseline = create_baseline(self.root)

        (self.root / "old_file.txt").unlink()

        comparison = compare_folder_with_baseline(
            baseline,
            self.root,
        )

        self.assertEqual(
            comparison["results"]["deleted"],
            ["old_file.txt"],
        )

    def test_multiple_changes(self):
        self.create_file("unchanged.txt", "same")
        self.create_file("modified.txt", "old")
        self.create_file("deleted.txt", "remove")

        baseline = create_baseline(self.root)

        (self.root / "modified.txt").write_text(
            "new",
            encoding="utf-8",
        )

        (self.root / "deleted.txt").unlink()

        self.create_file("added.txt", "new file")

        comparison = compare_folder_with_baseline(
            baseline,
            self.root,
        )

        results = comparison["results"]

        self.assertEqual(results["unchanged"], ["unchanged.txt"])
        self.assertEqual(results["modified"], ["modified.txt"])
        self.assertEqual(results["added"], ["added.txt"])
        self.assertEqual(results["deleted"], ["deleted.txt"])

    def test_summary_counts(self):
        self.create_file("same.txt", "same")
        self.create_file("modified.txt", "old")

        baseline = create_baseline(self.root)

        (self.root / "modified.txt").write_text(
            "new",
            encoding="utf-8",
        )

        self.create_file("added.txt", "new")

        comparison = compare_folder_with_baseline(
            baseline,
            self.root,
        )

        summary = comparison["summary"]

        self.assertEqual(summary["unchanged"], 1)
        self.assertEqual(summary["modified"], 1)
        self.assertEqual(summary["added"], 1)
        self.assertEqual(summary["deleted"], 0)
        self.assertEqual(summary["unverified"], 0)
        self.assertEqual(summary["total"], 3)

    def test_nested_file_detection(self):
        self.create_file("folder/subfolder/file.txt", "content")

        baseline = create_baseline(self.root)

        comparison = compare_folder_with_baseline(
            baseline,
            self.root,
        )

        self.assertEqual(
            comparison["results"]["unchanged"],
            ["folder/subfolder/file.txt"],
        )

    def test_incomplete_baseline_does_not_confirm_added(self):
        baseline = {
            "files": {},
            "failed_files": [
                {
                    "path": ".",
                    "error": "Folder scanning failed",
                }
            ],
            "complete": False,
        }

        current_scan = {
            "files": {
                "new.txt": "a" * 64,
            },
            "failed_files": [],
            "complete": True,
        }

        comparison = detect_changes(baseline, current_scan)

        self.assertEqual(
            comparison["results"]["unverified"],
            ["new.txt"],
        )

        self.assertEqual(comparison["results"]["added"], [])

    def test_incomplete_current_scan_does_not_confirm_deleted(self):
        baseline = {
            "files": {
                "old.txt": "a" * 64,
            },
            "failed_files": [],
            "complete": True,
        }

        current_scan = {
            "files": {},
            "failed_files": [
                {
                    "path": ".",
                    "error": "Folder scanning failed",
                }
            ],
            "complete": False,
        }

        comparison = detect_changes(baseline, current_scan)

        self.assertEqual(
            comparison["results"]["unverified"],
            ["old.txt"],
        )

        self.assertEqual(comparison["results"]["deleted"], [])

    def test_failed_file_is_unverified(self):
        baseline = {
            "files": {
                "file.txt": "a" * 64,
            },
            "failed_files": [],
            "complete": True,
        }

        current_scan = {
            "files": {},
            "failed_files": [
                {
                    "path": "file.txt",
                    "error": "Permission denied",
                }
            ],
            "complete": False,
        }

        comparison = detect_changes(baseline, current_scan)

        self.assertEqual(
            comparison["results"]["unverified"],
            ["file.txt"],
        )

        self.assertEqual(comparison["results"]["deleted"], [])

    def test_current_folder_scan(self):
        self.create_file("file.txt", "content")

        scan = scan_current_folder(self.root)

        self.assertIn("file.txt", scan["files"])
        self.assertEqual(scan["failed_files"], [])
        self.assertTrue(scan["complete"])

    # HG-10 additional tests

    def test_folder_error_marks_files_inside_as_unverified(self):
        baseline = {
            "files": {
                "private/secret.txt": "a" * 64,
                "public.txt": "b" * 64,
            },
            "failed_files": [],
            "complete": True,
        }

        current_scan = {
            "files": {
                "public.txt": "b" * 64,
            },
            "failed_files": [
                {
                    "path": "private",
                    "error": "Access denied",
                    "kind": "folder",
                }
            ],
            "complete": False,
        }

        comparison = detect_changes(baseline, current_scan)

        self.assertEqual(
            comparison["results"]["unverified"],
            ["private/secret.txt"],
        )

        self.assertEqual(
            comparison["results"]["unchanged"],
            ["public.txt"],
        )

        self.assertEqual(comparison["results"]["deleted"], [])

    def test_unaffected_file_is_still_detected_as_modified(self):
        baseline = {
            "files": {
                "private/secret.txt": "a" * 64,
                "public.txt": "b" * 64,
            },
            "failed_files": [],
            "complete": True,
        }

        current_scan = {
            "files": {
                "public.txt": "c" * 64,
            },
            "failed_files": [
                {
                    "path": "private",
                    "error": "Access denied",
                    "kind": "folder",
                }
            ],
            "complete": False,
        }

        comparison = detect_changes(baseline, current_scan)

        self.assertEqual(
            comparison["results"]["unverified"],
            ["private/secret.txt"],
        )

        self.assertEqual(
            comparison["results"]["modified"],
            ["public.txt"],
        )

    def test_entry_error_does_not_confirm_deletion(self):
        baseline = {
            "files": {
                "unknown.txt": "a" * 64,
            },
            "failed_files": [],
            "complete": True,
        }

        current_scan = {
            "files": {},
            "failed_files": [
                {
                    "path": "unknown.txt",
                    "error": "Unable to access entry",
                    "kind": "entry",
                }
            ],
            "complete": False,
        }

        comparison = detect_changes(baseline, current_scan)

        self.assertEqual(
            comparison["results"]["unverified"],
            ["unknown.txt"],
        )

        self.assertEqual(
            comparison["results"]["deleted"],
            [],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
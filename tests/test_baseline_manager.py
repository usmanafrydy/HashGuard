"""Tests for HashGuard's baseline management functionality."""

import json
import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.baseline_manager import (
    create_baseline,
    save_baseline,
    load_baseline,
    validate_baseline,
)
from src.change_detector import compare_folder_with_baseline
from src.csv_exporter import export_comparison_csv


class TestBaselineManager(unittest.TestCase):

    def setUp(self):
        repository = Path(__file__).resolve().parents[1]

        self.temporary_directory = tempfile.TemporaryDirectory(
            dir=repository
        )

        self.addCleanup(self.temporary_directory.cleanup)

        self.root = Path(self.temporary_directory.name) / "monitored"
        self.root.mkdir()

        self.file_path = self.root / "sample.txt"

        self.file_path.write_text(
            "HashGuard test content",
            encoding="utf-8"
        )

        self.baseline_path = (
            Path(self.temporary_directory.name) / "baseline.json"
        )

    def test_create_baseline(self):
        baseline = create_baseline(self.root)

        self.assertEqual(
            baseline["root_path"],
            str(self.root.resolve())
        )

        self.assertEqual(baseline["algorithm"], "SHA-256")
        self.assertIn("sample.txt", baseline["files"])
        self.assertTrue(baseline["complete"])
        self.assertEqual(baseline["failed_files"], [])

    def test_create_baseline_with_exclusions(self):
        baseline = create_baseline(
            self.root,
            exclusions=["sample.txt"]
        )

        self.assertNotIn("sample.txt", baseline["files"])
        self.assertEqual(
            baseline["exclusions"],
            ["sample.txt"]
        )

    def test_create_baseline_records_unreadable_file(self):
        with patch(
            "src.baseline_manager.hash_file",
            side_effect=PermissionError("Access denied")
        ):
            baseline = create_baseline(self.root)

        self.assertFalse(baseline["complete"])
        self.assertEqual(len(baseline["failed_files"]), 1)

        self.assertEqual(
            baseline["failed_files"][0]["path"],
            "sample.txt"
        )

    def test_create_baseline_records_folder_scan_error(self):
        with patch(
            "src.baseline_manager.scan_folder",
            side_effect=PermissionError("Access denied")
        ):
            baseline = create_baseline(self.root)

        self.assertFalse(baseline["complete"])
        self.assertEqual(len(baseline["failed_files"]), 1)

        self.assertEqual(
            baseline["failed_files"][0]["path"],
            "."
        )

    def test_save_and_load_baseline(self):
        baseline = create_baseline(self.root)

        save_baseline(baseline, self.baseline_path)

        loaded = load_baseline(self.baseline_path)

        self.assertEqual(loaded, baseline)

    def test_save_does_not_overwrite_existing_baseline(self):
        self.baseline_path.write_text(
            '{"original": true}',
            encoding="utf-8"
        )

        with self.assertRaises(FileExistsError):
            save_baseline({}, self.baseline_path)

        self.assertEqual(
            json.loads(
                self.baseline_path.read_text(encoding="utf-8")
            ),
            {"original": True}
        )

    def test_save_rejects_destination_inside_monitored_folder(self):
        baseline = create_baseline(self.root)

        destination = self.root / "baseline.json"

        with self.assertRaisesRegex(
            ValueError,
            "outside the monitored folder"
        ):
            save_baseline(baseline, destination)

        self.assertFalse(destination.exists())

    def test_successful_save_removes_temporary_file(self):
        baseline = create_baseline(self.root)

        save_baseline(baseline, self.baseline_path)

        self.assertEqual(load_baseline(self.baseline_path), baseline)
        self.assertEqual(list(self.baseline_path.parent.glob(".hashguard-baseline-*.tmp")), [])

    def test_partial_write_failure_does_not_publish_baseline(self):
        baseline = create_baseline(self.root)
        failure = OSError("Disk full")

        def fail_during_write(data, file, **kwargs):
            self.assertEqual(Path(file.name).parent, self.baseline_path.parent)
            file.write('{"partial":')
            raise failure

        with patch("src.baseline_manager.json.dump", side_effect=fail_during_write):
            with self.assertRaises(OSError) as context:
                save_baseline(baseline, self.baseline_path)

        self.assertIs(context.exception, failure)
        self.assertFalse(self.baseline_path.exists())
        self.assertEqual(list(self.baseline_path.parent.glob(".hashguard-baseline-*.tmp")), [])

    def test_flush_to_disk_failure_does_not_publish_baseline(self):
        baseline = create_baseline(self.root)
        with patch("src.baseline_manager.os.fsync", side_effect=OSError("Flush failed")):
            with self.assertRaisesRegex(OSError, "Flush failed"):
                save_baseline(baseline, self.baseline_path)

        self.assertFalse(self.baseline_path.exists())
        self.assertEqual(list(self.baseline_path.parent.glob(".hashguard-baseline-*.tmp")), [])

    def test_concurrent_destination_creation_is_not_overwritten(self):
        baseline = create_baseline(self.root)
        original_link = os.link
        competing_contents = b'{"created_by_another_process": true}'

        def create_destination_before_publication(source, destination):
            # The source must already be a complete, closed JSON file.
            self.assertEqual(load_baseline(source), baseline)
            self.assertEqual(Path(source).parent, Path(destination).parent)
            Path(destination).write_bytes(competing_contents)
            original_link(source, destination)

        with patch("src.baseline_manager.os.link", side_effect=create_destination_before_publication):
            with self.assertRaises(FileExistsError):
                save_baseline(baseline, self.baseline_path)

        self.assertEqual(self.baseline_path.read_bytes(), competing_contents)
        self.assertEqual(list(self.baseline_path.parent.glob(".hashguard-baseline-*.tmp")), [])

    def test_publication_failure_cleans_up_temporary_file(self):
        baseline = create_baseline(self.root)
        with patch("src.baseline_manager.os.link", side_effect=PermissionError("Denied")):
            with self.assertRaisesRegex(PermissionError, "Denied"):
                save_baseline(baseline, self.baseline_path)

        self.assertFalse(self.baseline_path.exists())
        self.assertEqual(list(self.baseline_path.parent.glob(".hashguard-baseline-*.tmp")), [])

    def test_cleanup_failure_preserves_original_write_error(self):
        baseline = create_baseline(self.root)
        failure = OSError("Disk full")
        with patch("src.baseline_manager.json.dump", side_effect=failure):
            with patch.object(Path, "unlink", side_effect=PermissionError("Cleanup denied")):
                with self.assertRaises(OSError) as context:
                    save_baseline(baseline, self.baseline_path)

        self.assertIs(context.exception, failure)
        self.assertIn("Cleanup denied", " ".join(failure.__notes__))
        self.assertFalse(self.baseline_path.exists())

    def test_interrupted_write_is_not_published_and_is_cleaned_up(self):
        baseline = create_baseline(self.root)
        with patch("src.baseline_manager.json.dump", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                save_baseline(baseline, self.baseline_path)

        self.assertFalse(self.baseline_path.exists())
        self.assertEqual(list(self.baseline_path.parent.glob(".hashguard-baseline-*.tmp")), [])

    def test_validate_baseline(self):
        baseline = create_baseline(self.root)

        self.assertTrue(validate_baseline(baseline))

    def test_validate_baseline_for_correct_folder(self):
        baseline = create_baseline(self.root)

        self.assertTrue(
            validate_baseline(baseline, self.root)
        )

    def test_reject_baseline_for_different_folder(self):
        baseline = create_baseline(self.root)

        another_folder = (
            Path(self.temporary_directory.name) / "another"
        )

        another_folder.mkdir()

        with self.assertRaisesRegex(
            ValueError,
            "different folder"
        ):
            validate_baseline(baseline, another_folder)

    def test_reject_missing_required_field(self):
        baseline = create_baseline(self.root)

        del baseline["algorithm"]

        with self.assertRaisesRegex(
            ValueError,
            "missing fields"
        ):
            validate_baseline(baseline)

    def test_reject_invalid_hash(self):
        baseline = create_baseline(self.root)

        baseline["files"]["sample.txt"] = "invalid"

        with self.assertRaisesRegex(
            ValueError,
            "Invalid SHA-256 hash"
        ):
            validate_baseline(baseline)

    def test_reject_non_hexadecimal_hash(self):
        baseline = create_baseline(self.root)

        baseline["files"]["sample.txt"] = "z" * 64

        with self.assertRaisesRegex(
            ValueError,
            "Invalid SHA-256 hash"
        ):
            validate_baseline(baseline)

    def test_reject_invalid_timestamp(self):
        baseline = create_baseline(self.root)

        baseline["created_at"] = "not-a-valid-date"

        with self.assertRaisesRegex(
            ValueError,
            "Invalid baseline creation timestamp"
        ):
            validate_baseline(baseline)

    def test_reject_unsafe_relative_path(self):
        baseline = create_baseline(self.root)

        baseline["files"] = {
            "../outside.txt": "a" * 64
        }

        with self.assertRaisesRegex(
            ValueError,
            "Unsafe relative file path"
        ):
            validate_baseline(baseline)

    def test_reject_malformed_failed_file_record(self):
        baseline = create_baseline(self.root)

        baseline["failed_files"] = [
            {"path": "sample.txt"}
        ]

        baseline["complete"] = False

        with self.assertRaisesRegex(
            ValueError,
            "Invalid failed-file record"
        ):
            validate_baseline(baseline)

    def test_reject_invalid_error_kinds(self):
        baseline = create_baseline(self.root)
        baseline["complete"] = False
        for kind in ("unknown", "directory", "", "File"):
            with self.subTest(kind=kind):
                baseline["failed_files"] = [
                    {"path": "sample.txt", "error": "Denied", "kind": kind}
                ]
                with self.assertRaisesRegex(ValueError, "Invalid failed-file record kind"):
                    validate_baseline(baseline)

    def test_reject_non_string_error_kinds(self):
        baseline = create_baseline(self.root)
        baseline["complete"] = False
        for kind in (None, 1, True, [], {}, ["file"]):
            with self.subTest(kind=kind):
                baseline["failed_files"] = [
                    {"path": "sample.txt", "error": "Denied", "kind": kind}
                ]
                with self.assertRaisesRegex(ValueError, "Invalid failed-file record kind"):
                    validate_baseline(baseline)

    def test_reject_unsafe_error_paths(self):
        baseline = create_baseline(self.root)
        baseline["complete"] = False
        for path in (
            "../outside.txt", "nested/../file.txt", "./file.txt",
            "nested/./file.txt", "nested//file.txt", "nested/",
            "nested\\file.txt", "/outside.txt", str(self.file_path.resolve()),
        ):
            with self.subTest(path=path):
                baseline["failed_files"] = [{"path": path, "error": "Denied"}]
                with self.assertRaisesRegex(ValueError, "Unsafe failed-file record path"):
                    validate_baseline(baseline)

    def test_accept_valid_error_kinds_and_root_paths(self):
        baseline = create_baseline(self.root)
        baseline["complete"] = False
        for kind in ("file", "folder", "entry"):
            for path in (".", "private", "nested/file.txt"):
                with self.subTest(kind=kind, path=path):
                    baseline["failed_files"] = [
                        {"path": path, "error": "Denied", "kind": kind}
                    ]
                    self.assertTrue(validate_baseline(baseline))

    def test_legacy_error_records_remain_valid_through_comparison_and_export(self):
        for path in ("sample.txt", "."):
            with self.subTest(path=path):
                baseline = create_baseline(self.root)
                baseline["failed_files"] = [{"path": path, "error": "Denied"}]
                baseline["complete"] = False
                self.assertTrue(validate_baseline(baseline))
                comparison = compare_folder_with_baseline(baseline, self.root)
                self.assertEqual(comparison["results"]["unverified"], ["sample.txt"])
                report_path = self.baseline_path.with_suffix(".csv")
                export_comparison_csv(baseline, comparison, report_path)
                with report_path.open(encoding="utf-8", newline="") as report:
                    rows = list(csv.DictReader(report))
                errors = [row for row in rows if row["Record Type"] == "error"]
                self.assertEqual(errors[0]["Kind"], "file")
                self.assertNotIn("kind", baseline["failed_files"][0])

    def test_invalid_folder_error_is_rejected_before_comparison(self):
        private = self.root / "private"
        private.mkdir()
        (private / "data.txt").write_text("data", encoding="utf-8")
        baseline = create_baseline(self.root)
        baseline["failed_files"] = [
            {"path": "private", "error": "Denied", "kind": "unknown"}
        ]
        baseline["complete"] = False

        with patch("src.change_detector.scan_current_folder") as scan:
            with self.assertRaisesRegex(ValueError, "Invalid failed-file record kind"):
                compare_folder_with_baseline(baseline, self.root)
            scan.assert_not_called()

    def test_load_rejects_malformed_error_records(self):
        baseline = create_baseline(self.root)
        baseline["complete"] = False
        for record in (
            {"path": "private", "error": "Denied", "kind": 1},
            {"path": "../private", "error": "Denied", "kind": "folder"},
        ):
            with self.subTest(record=record):
                baseline["failed_files"] = [record]
                self.baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_baseline(self.baseline_path)

    def test_reject_incorrect_completion_status(self):
        baseline = create_baseline(self.root)

        baseline["complete"] = False

        with self.assertRaisesRegex(
            ValueError,
            "completion status does not match"
        ):
            validate_baseline(baseline)

    def test_reject_invalid_json(self):
        self.baseline_path.write_text(
            "{invalid json",
            encoding="utf-8"
        )

        with self.assertRaises(json.JSONDecodeError):
            load_baseline(self.baseline_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Tests for HashGuard's baseline management functionality."""

import json
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
"""Regression tests for file identity and changes during verification."""

import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.baseline_manager import create_baseline
from src.change_detector import compare_folder_with_baseline
from src.file_hasher import hash_file


class TestFileVerification(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "monitored"
        self.root.mkdir()
        self.target = self.root / "target.txt"
        self.target.write_bytes(b"original")
        (self.root / "healthy.txt").write_bytes(b"healthy")

    def change_at_final_path_check(self, action):
        """Trigger a real filesystem change after reading, before accepting it.

        Discovery stats the entry, then the scan loop stats it before hashing.
        The third stat is the hasher's final check after closing on Windows.
        """
        original_stat = Path.stat
        calls = 0

        def stat(path, *args, **kwargs):
            nonlocal calls
            if path == self.target:
                calls += 1
                if calls == 3:
                    action()
            return original_stat(path, *args, **kwargs)

        return patch.object(Path, "stat", new=stat)

    def replacement(self):
        before = self.target.stat()
        replacement = self.base / "replacement.txt"
        replacement.write_bytes(b"replaced")
        os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(replacement.stat().st_size, before.st_size)
        self.assertEqual(replacement.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertNotEqual(replacement.stat().st_ino, before.st_ino)
        os.replace(replacement, self.target)

    def assert_failed_file(self, scan):
        self.assertFalse(scan["complete"])
        self.assertNotIn("target.txt", scan["files"])
        self.assertIn("healthy.txt", scan["files"])
        errors = scan["failed_files"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["path"], "target.txt")
        self.assertEqual(errors[0]["kind"], "file")

    def test_identical_size_timestamp_replacement_during_baseline(self):
        with self.change_at_final_path_check(self.replacement):
            baseline = create_baseline(self.root)
        self.assert_failed_file(baseline)
        self.assertIn("replaced", baseline["failed_files"][0]["error"])

    def test_identical_size_timestamp_replacement_during_comparison(self):
        baseline = create_baseline(self.root)
        with self.change_at_final_path_check(self.replacement):
            comparison = compare_folder_with_baseline(baseline, self.root)
        self.assert_failed_file(comparison["current_scan"])
        self.assertEqual(comparison["results"]["unverified"], ["target.txt"])
        self.assertEqual(comparison["results"]["unchanged"], ["healthy.txt"])
        self.assertEqual(comparison["results"]["modified"], [])
        self.assertEqual(comparison["results"]["deleted"], [])
        self.assertFalse(comparison["current_scan_complete"])

    def test_disappearance_during_baseline_is_failed_verification(self):
        with self.change_at_final_path_check(self.target.unlink):
            baseline = create_baseline(self.root)
        self.assert_failed_file(baseline)
        self.assertIn("File not found", baseline["failed_files"][0]["error"])

    def test_disappearance_during_comparison_is_unverified_not_deleted(self):
        baseline = create_baseline(self.root)
        with self.change_at_final_path_check(self.target.unlink):
            comparison = compare_folder_with_baseline(baseline, self.root)
        self.assert_failed_file(comparison["current_scan"])
        self.assertEqual(comparison["results"]["unverified"], ["target.txt"])
        self.assertEqual(comparison["results"]["deleted"], [])

    def test_normal_and_modified_files_keep_expected_hashes_and_statuses(self):
        self.assertEqual(hash_file(self.target), hashlib.sha256(b"original").hexdigest())
        baseline = create_baseline(self.root)
        self.target.write_bytes(b"modified content")
        comparison = compare_folder_with_baseline(baseline, self.root)
        self.assertTrue(comparison["current_scan_complete"])
        self.assertEqual(comparison["results"]["modified"], ["target.txt"])
        self.assertEqual(comparison["results"]["unchanged"], ["healthy.txt"])

    def test_open_handle_metadata_change_is_rejected(self):
        original_fstat = os.fstat
        calls = 0

        def changed_fstat(descriptor):
            nonlocal calls
            info = original_fstat(descriptor)
            calls += 1
            return SimpleNamespace(
                st_ino=info.st_ino, st_dev=info.st_dev, st_size=info.st_size,
                st_mtime_ns=info.st_mtime_ns + (1 if calls == 2 else 0),
            )

        with patch("src.file_hasher.os.fstat", side_effect=changed_fstat):
            with self.assertRaisesRegex(OSError, "File changed while being hashed"):
                hash_file(self.target)

    def test_open_handle_identity_change_with_same_size_and_time_is_rejected(self):
        info = self.target.stat()
        before = SimpleNamespace(
            st_ino=info.st_ino, st_dev=info.st_dev,
            st_size=info.st_size, st_mtime_ns=info.st_mtime_ns,
        )
        after = SimpleNamespace(
            st_ino=info.st_ino + 1, st_dev=info.st_dev,
            st_size=info.st_size, st_mtime_ns=info.st_mtime_ns,
        )
        with patch("src.file_hasher.os.fstat", side_effect=[before, after]):
            with self.assertRaisesRegex(OSError, "File was replaced while being hashed"):
                hash_file(self.target)

    def test_unavailable_identity_is_failed_verification_in_both_scan_paths(self):
        baseline = create_baseline(self.root)
        with patch(
            "src.file_hasher.os.fstat",
            return_value=SimpleNamespace(st_ino=0, st_dev=0),
        ):
            incomplete_baseline = create_baseline(self.root)
            comparison = compare_folder_with_baseline(baseline, self.root)
        self.assertFalse(incomplete_baseline["complete"])
        self.assertEqual(incomplete_baseline["files"], {})
        self.assertTrue(all("identity is unavailable" in error["error"]
                            for error in incomplete_baseline["failed_files"]))
        self.assertFalse(comparison["current_scan_complete"])
        self.assertEqual(comparison["results"]["unchanged"], [])
        self.assertEqual(comparison["results"]["unverified"], ["healthy.txt", "target.txt"])


if __name__ == "__main__":
    unittest.main()

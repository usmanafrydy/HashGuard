
"""Tests for recursive scanner error handling."""

import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from src.file_scanner import scan_folder


class TestScannerErrors(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name).resolve()

    def test_normal_scan_has_no_errors(self):
        file_path = self.root / "sample.txt"
        file_path.write_text("Hello", encoding="utf-8")

        errors = []

        files = scan_folder(
            self.root,
            errors=errors,
        )

        self.assertEqual(files, [file_path])
        self.assertEqual(errors, [])

    def test_inaccessible_folder_is_recorded(self):
        private = self.root / "private"
        private.mkdir()

        public_file = self.root / "public.txt"
        public_file.write_text("Public", encoding="utf-8")

        original_iterdir = Path.iterdir

        def fake_iterdir(folder):
            if folder == private:
                raise PermissionError("Access denied")

            return original_iterdir(folder)

        errors = []

        with patch.object(
            Path,
            "iterdir",
            new=fake_iterdir,
        ):
            files = scan_folder(
                self.root,
                errors=errors,
            )

        self.assertEqual(files, [public_file])
        self.assertEqual(len(errors), 1)

        self.assertEqual(
            errors[0]["path"],
            "private",
        )

        self.assertEqual(
            errors[0]["kind"],
            "folder",
        )

    def test_excluded_folder_is_skipped(self):
        cache = self.root / "cache"
        cache.mkdir()

        (cache / "temp.txt").write_text(
            "Temporary",
            encoding="utf-8",
        )

        keep = self.root / "keep.txt"
        keep.write_text("Keep", encoding="utf-8")

        errors = []

        files = scan_folder(
            self.root,
            exclusions=["cache/"],
            errors=errors,
        )

        self.assertEqual(files, [keep])
        self.assertEqual(errors, [])

    def test_error_without_collector_is_raised(self):
        with patch.object(
            Path,
            "iterdir",
            side_effect=PermissionError("Access denied"),
        ):
            with self.assertRaises(PermissionError):
                scan_folder(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)

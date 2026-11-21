
"""Integration tests for scanning, exclusions, and errors."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.baseline_manager import create_baseline
from src.change_detector import compare_folder_with_baseline


class TestScannerIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name).resolve()

    def test_exclusions_are_used_in_both_scans(self):
        keep = self.root / "keep.txt"
        ignored = self.root / "debug.log"

        keep.write_text("Original", encoding="utf-8")
        ignored.write_text("Original", encoding="utf-8")

        cache = self.root / "cache"
        cache.mkdir()

        (cache / "temp.txt").write_text(
            "Temporary", encoding="utf-8"
        )

        baseline = create_baseline(
            self.root,
            exclusions=["*.log", "cache/"],
        )

        self.assertEqual(
            list(baseline["files"]),
            ["keep.txt"],
        )

        keep.write_text("Changed", encoding="utf-8")
        ignored.write_text("Changed", encoding="utf-8")

        report = compare_folder_with_baseline(
            baseline,
            self.root,
        )

        self.assertEqual(
            report["results"]["modified"],
            ["keep.txt"],
        )

        self.assertEqual(report["summary"]["total"], 1)

    def test_inaccessible_folder_is_not_deleted(self):
        private = self.root / "private"
        private.mkdir()

        (private / "data.txt").write_text(
            "Secret data", encoding="utf-8"
        )

        (self.root / "public.txt").write_text(
            "Public data", encoding="utf-8"
        )

        baseline = create_baseline(self.root)

        original_iterdir = Path.iterdir

        def simulated_iterdir(folder):
            if folder == private:
                raise PermissionError("Access denied")

            return original_iterdir(folder)

        with patch.object(
            Path,
            "iterdir",
            new=simulated_iterdir,
        ):
            report = compare_folder_with_baseline(
                baseline,
                self.root,
            )

        self.assertEqual(
            report["results"]["unverified"],
            ["private/data.txt"],
        )

        self.assertEqual(
            report["results"]["unchanged"],
            ["public.txt"],
        )

        self.assertEqual(report["results"]["deleted"], [])
        self.assertEqual(report["summary"]["total"], 2)
        self.assertFalse(report["current_scan_complete"])

        errors = report["current_scan"]["failed_files"]

        self.assertEqual(errors[0]["path"], "private")
        self.assertEqual(errors[0]["kind"], "folder")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Tests for recursive file discovery in HashGuard."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.file_scanner import scan_folder


class TestRecursiveScanner(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.base = Path(self.temporary_directory.name)
        self.folder = self.base / "watched"
        self.folder.mkdir()

    def test_finds_files_at_multiple_levels(self):
        first = self.folder / "a.txt"
        second = self.folder / "nested" / "b.txt"
        third = self.folder / "nested" / "deeper" / "c.txt"

        third.parent.mkdir(parents=True)

        for file_path in [third, second, first]:
            file_path.write_text("Example", encoding="utf-8")

        self.assertEqual(
            scan_folder(self.folder),
            [first, second, third],
        )

    def test_empty_folder_returns_empty_list(self):
        self.assertEqual(scan_folder(self.folder), [])

    def test_rejects_file_as_root(self):
        file_path = self.folder / "sample.txt"
        file_path.write_text("Example", encoding="utf-8")

        with self.assertRaises(NotADirectoryError):
            scan_folder(file_path)

    def test_rejects_junction_as_root(self):
        with patch.object(Path, "is_junction", return_value=True):
            with self.assertRaises(ValueError):
                scan_folder(self.folder)

    def test_skips_junction_directory(self):
        regular_file = self.folder / "keep.txt"
        regular_file.write_text("Keep", encoding="utf-8")

        junction = self.folder / "junction"
        junction.mkdir()
        (junction / "skip.txt").write_text(
            "Skip", encoding="utf-8"
        )

        # Simulate a junction without requiring Windows privileges.
        with patch.object(
            Path,
            "is_junction",
            new=lambda path: path == junction,
        ):
            self.assertEqual(
                scan_folder(self.folder),
                [regular_file],
            )

    def test_skips_symbolic_link_to_external_folder(self):
        regular_file = self.folder / "keep.txt"
        regular_file.write_text("Keep", encoding="utf-8")

        outside = self.base / "outside"
        outside.mkdir()
        (outside / "skip.txt").write_text(
            "Skip", encoding="utf-8"
        )

        link = self.folder / "linked_folder"

        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(
                f"Symbolic links are unavailable: {error}"
            )

        self.assertEqual(
            scan_folder(self.folder),
            [regular_file],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
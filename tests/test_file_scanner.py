"""Tests for HashGuard folder validation and immediate file discovery."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.file_scanner import list_files, validate_folder


class TestFileScanner(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.folder = Path(self.temporary_directory.name)

    def test_validate_folder_accepts_existing_folder(self):
        self.assertEqual(validate_folder(self.folder), self.folder)
        self.assertEqual(validate_folder(str(self.folder)), self.folder)

    def test_validate_folder_rejects_missing_folder(self):
        with self.assertRaises(FileNotFoundError):
            validate_folder(self.folder / "missing")

    def test_validate_folder_rejects_file(self):
        file_path = self.folder / "sample.txt"
        file_path.write_text("Example", encoding="utf-8")

        with self.assertRaises(NotADirectoryError):
            validate_folder(file_path)

    def test_list_files_returns_empty_list_for_empty_folder(self):
        self.assertEqual(list_files(self.folder), [])

    def test_list_files_excludes_subfolders_and_sorts_results(self):
        first_file = self.folder / "a.txt"
        second_file = self.folder / "b.txt"

        second_file.write_text("Second", encoding="utf-8")
        first_file.write_text("First", encoding="utf-8")

        subfolder = self.folder / "nested"
        subfolder.mkdir()
        (subfolder / "inside.txt").write_text(
            "Nested", encoding="utf-8"
        )

        self.assertEqual(
            list_files(self.folder),
            [first_file, second_file],
        )

    def test_list_files_rejects_missing_folder(self):
        with self.assertRaises(FileNotFoundError):
            list_files(self.folder / "missing")

    def test_list_files_reports_directory_access_error(self):
        with patch.object(
            Path,
            "iterdir",
            side_effect=PermissionError("Access denied"),
        ):
            with self.assertRaises(PermissionError):
                list_files(self.folder)

    def test_list_files_skips_symbolic_link_to_file(self):
        target = self.folder / "target.txt"
        target.write_text("Original", encoding="utf-8")
        link = self.folder / "shortcut.txt"

        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as error:
            self.skipTest(
                f"Symbolic links are unavailable: {error}"
            )

        self.assertEqual(list_files(self.folder), [target])


if __name__ == "__main__":
    unittest.main(verbosity=2)
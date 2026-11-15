"""Tests for HashGuard's SHA-256 file hashing."""

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.file_hasher import hash_file


class TestHashFile(unittest.TestCase):
    def setUp(self):
        # Keep temporary test data inside the HashGuard repository.
        repository = Path(__file__).resolve().parents[1]
        self.temporary_directory = tempfile.TemporaryDirectory(dir=repository)
        self.addCleanup(self.temporary_directory.cleanup)
        self.file_path = Path(self.temporary_directory.name) / "sample.txt"

    def test_same_file_produces_same_hash(self):
        # Use more than one chunk to check that the whole file is hashed.
        content = b"HashGuard test content\n" * 10000
        self.file_path.write_bytes(content)

        first_hash = hash_file(self.file_path)
        second_hash = hash_file(str(self.file_path))

        self.assertEqual(first_hash, second_hash)
        self.assertEqual(first_hash, hashlib.sha256(content).hexdigest())
        self.assertRegex(first_hash, r"^[0-9a-f]{64}$")

    def test_changing_content_changes_hash(self):
        self.file_path.write_bytes(b"Original content")
        original_hash = hash_file(self.file_path)

        self.file_path.write_bytes(b"Changed content")

        self.assertNotEqual(original_hash, hash_file(self.file_path))

    def test_empty_file_produces_correct_hash(self):
        self.file_path.write_bytes(b"")

        self.assertEqual(
            hash_file(self.file_path),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_nonexistent_file_produces_clear_error(self):
        with self.assertRaises(FileNotFoundError) as context:
            hash_file(self.file_path)

        self.assertIn("File not found", str(context.exception))
        self.assertIn(str(self.file_path), str(context.exception))

    def test_unreadable_file_produces_clear_error(self):
        # Simulate denied access consistently across Windows and other systems.
        with patch.object(Path, "open", side_effect=PermissionError("Access denied")):
            with self.assertRaises(PermissionError) as context:
                hash_file(self.file_path)

        self.assertIn("Permission denied", str(context.exception))
        self.assertIn(str(self.file_path), str(context.exception))


if __name__ == "__main__":
    unittest.main()

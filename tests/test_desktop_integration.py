"""Exercise desktop workers and the result queue without starting Tk."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from queue import Empty, SimpleQueue
from unittest.mock import patch

from src.baseline_manager import create_baseline, load_baseline, save_baseline
from src.desktop_app import compare_in_background, load_in_background, save_in_background


class TestDesktopIntegration(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        workspace = Path(temporary.name).resolve()
        self.folder = workspace / "monitored"
        self.folder.mkdir()
        self.document = self.folder / "document.txt"
        self.document.write_bytes(b"original")
        self.destination = workspace / "baseline.json"

    def run_worker(self, worker, *args):
        results = SimpleQueue()
        worker(*args, results)
        payload, message = results.get_nowait()
        with self.assertRaises(Empty):
            results.get_nowait()
        return payload, message

    def deny_document_read(self):
        real_open = Path.open

        def open_file(path, mode="r", *args, **kwargs):
            if path == self.document and mode == "rb":
                raise PermissionError("Document read denied")
            return real_open(path, mode, *args, **kwargs)

        return patch.object(Path, "open", new=open_file)

    def test_save_complete_baseline(self):
        baseline, message = self.run_worker(save_in_background, self.folder, self.destination)
        self.assertEqual(message, f"Baseline saved: {self.destination}")
        self.assertTrue(baseline["complete"])
        self.assertEqual(baseline["files"], {"document.txt": hashlib.sha256(b"original").hexdigest()})
        self.assertEqual(load_baseline(self.destination), baseline)

    def test_save_incomplete_baseline(self):
        (self.folder / "healthy.txt").write_bytes(b"healthy")
        with self.deny_document_read():
            baseline, message = self.run_worker(save_in_background, self.folder, self.destination)
        self.assertEqual(message, f"Baseline saved: {self.destination}")
        self.assertFalse(baseline["complete"])
        self.assertEqual(set(baseline["files"]), {"healthy.txt"})
        error, = baseline["failed_files"]
        self.assertEqual((error["path"], error["kind"]), ("document.txt", "file"))
        self.assertIn("Permission denied", error["error"])
        self.assertEqual(load_baseline(self.destination), baseline)

    def test_save_existing_destination_reports_error(self):
        self.destination.write_bytes(b"previous contents")
        value, message = self.run_worker(save_in_background, self.folder, self.destination)
        self.assertIsNone(value)
        self.assertIn("Could not save baseline: Baseline already exists", message)
        self.assertIn(str(self.destination), message)
        self.assertEqual(self.destination.read_bytes(), b"previous contents")

    def test_load_saved_json(self):
        expected = create_baseline(self.folder)
        save_baseline(expected, self.destination)
        loaded, message = self.run_worker(load_in_background, self.folder, self.destination)
        self.assertEqual(loaded, expected)
        self.assertEqual(message, f"Baseline loaded: {self.destination}")

    def test_load_corrupted_json_reports_error(self):
        self.destination.write_bytes(b'{"version":')
        value, message = self.run_worker(load_in_background, self.folder, self.destination)
        self.assertIsNone(value)
        self.assertIn("Could not load baseline: Expecting value", message)

    def test_load_rejects_baseline_for_another_folder(self):
        save_baseline(create_baseline(self.folder), self.destination)
        other = self.folder.parent / "other"
        other.mkdir()
        value, message = self.run_worker(load_in_background, other, self.destination)
        self.assertIsNone(value)
        self.assertIn("Could not load baseline:", message)
        self.assertIn("different folder", message)

    def test_compare_returns_changes_and_text_report(self):
        baseline = create_baseline(self.folder)
        self.document.write_bytes(b"edited")
        (self.folder / "new.txt").write_bytes(b"new")
        comparison, report = self.run_worker(compare_in_background, baseline, self.folder)
        self.assertTrue(comparison["current_scan_complete"])
        self.assertEqual(comparison["results"]["modified"], ["document.txt"])
        self.assertEqual(comparison["results"]["added"], ["new.txt"])
        self.assertIn("Current scan: Complete", report)
        self.assertIn("Modified: document.txt", report)
        self.assertIn("Added: new.txt", report)
        self.assertIn("Total file results: 2", report)

    def test_compare_returns_incomplete_report_on_file_error(self):
        (self.folder / "healthy.txt").write_bytes(b"healthy")
        baseline = create_baseline(self.folder)
        with self.deny_document_read():
            comparison, report = self.run_worker(compare_in_background, baseline, self.folder)
        self.assertTrue(comparison["baseline_complete"])
        self.assertFalse(comparison["current_scan_complete"])
        self.assertEqual(comparison["results"]["unverified"], ["document.txt"])
        self.assertEqual(comparison["results"]["unchanged"], ["healthy.txt"])
        self.assertEqual(comparison["results"]["deleted"], [])
        self.assertIn("Current scan: Incomplete", report)
        self.assertIn("WARNING: Verification is incomplete.", report)
        self.assertIn("Unverified: document.txt", report)
        self.assertIn("Current scan errors\n  document.txt: Permission denied", report)

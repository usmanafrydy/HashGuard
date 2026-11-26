"""Exercise a saved HashGuard baseline through comparison and both reports."""

import csv
import hashlib
import os
import tempfile
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from src.baseline_manager import create_baseline, load_baseline, save_baseline
from src.change_detector import compare_folder_with_baseline
from src.csv_exporter import export_comparison_csv
from src.file_hasher import hash_file
from src.report_formatter import format_report


class TestEndToEndIntegration(unittest.TestCase):
    def test_saved_baseline_through_text_and_csv_reports(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        workspace = Path(temporary.name)
        monitored = workspace / "monitored"
        nested = monitored / "nested"
        nested.mkdir(parents=True)
        baseline_path = workspace / "baseline.json"
        csv_path = workspace / "report.csv"

        originals = {
            "nested/edited.txt": b"first version",
            "removed.txt": b"remove me",
            "stable.bin": bytes(range(256)),
        }
        for name, content in originals.items():
            (monitored / name).write_bytes(content)
        excluded = nested / "debug.log"
        excluded.write_bytes(b"first log")

        baseline = create_baseline(monitored, exclusions=["*.log"])
        self.assertEqual(baseline["files"], {
            name: hashlib.sha256(content).hexdigest() for name, content in originals.items()
        })
        save_baseline(baseline, baseline_path)
        saved_bytes = baseline_path.read_bytes()
        loaded = load_baseline(baseline_path)
        self.assertEqual(loaded, baseline)
        self.assertEqual(loaded["exclusions"], ["*.log"])
        original_baseline = deepcopy(loaded)

        (nested / "edited.txt").write_bytes(b"second version")
        (monitored / "removed.txt").unlink()
        (nested / "new.txt").write_bytes(b"new file")
        excluded.write_bytes(b"updated log")

        comparison = compare_folder_with_baseline(loaded, monitored)
        expected = {
            "added": ["nested/new.txt"],
            "modified": ["nested/edited.txt"],
            "deleted": ["removed.txt"],
            "unchanged": ["stable.bin"],
            "unverified": [],
        }
        counts = {status: len(paths) for status, paths in expected.items()}
        self.assertEqual(comparison["results"], expected)
        self.assertEqual(comparison["summary"], dict(counts, total=4))
        self.assertTrue(comparison["baseline_complete"])
        self.assertTrue(comparison["current_scan_complete"])
        self.assertNotIn("nested/debug.log", comparison["current_scan"]["files"])
        self.assertEqual(loaded, original_baseline)
        self.assertEqual(baseline_path.read_bytes(), saved_bytes)
        original_comparison = deepcopy(comparison)

        lines = format_report(loaded, comparison).splitlines()
        self.assertIn("Baseline: Complete", lines)
        self.assertIn("Current scan: Complete", lines)
        self.assertIn("  Total file results: 4", lines)
        for status, paths in expected.items():
            self.assertIn(f"  {status.title()}: {counts[status]}", lines)
            for path in paths:
                self.assertIn(f"  {status.title()}: {path}", lines)
        self.assertEqual(comparison, original_comparison)
        self.assertEqual(loaded, original_baseline)
        self.assertEqual(baseline_path.read_bytes(), saved_bytes)

        export_comparison_csv(loaded, comparison, csv_path)
        with csv_path.open(encoding="utf-8", newline="") as report:
            rows = list(csv.DictReader(report))
        self.assertEqual(len(rows), 6)
        self.assertCountEqual(
            [(row["File Path"], row["Status"]) for row in rows if row["Record Type"] == "file"],
            [(path, status) for status, paths in expected.items() for path in paths],
        )
        self.assertCountEqual(
            [(row["Source"], row["Complete"]) for row in rows if row["Record Type"] == "scan"],
            [("baseline", "true"), ("current", "true")],
        )
        self.assertEqual(comparison, original_comparison)
        self.assertEqual(loaded, original_baseline)
        self.assertEqual(baseline_path.read_bytes(), saved_bytes)

    def test_incomplete_baseline_survives_reload_and_reporting(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            monitored = workspace / "monitored"
            monitored.mkdir()
            blocked = monitored / "blocked.txt"
            blocked.write_bytes(b"readable on the next scan")
            stable = monitored / "stable.txt"
            stable.write_bytes(b"stable")
            error = {"path": blocked.name, "kind": "file", "error": "Read denied"}

            def hash_unless_blocked(path):
                if path == blocked:
                    raise PermissionError("Read denied")
                return hash_file(path)

            with patch("src.baseline_manager.hash_file", side_effect=hash_unless_blocked):
                baseline = create_baseline(monitored)
            self.assertFalse(baseline["complete"])
            self.assertEqual(baseline["failed_files"], [error])
            self.assertEqual(set(baseline["files"]), {stable.name})

            baseline_path = workspace / "baseline.json"
            save_baseline(baseline, baseline_path)
            loaded = load_baseline(baseline_path)
            self.assertEqual(loaded, baseline)
            comparison = compare_folder_with_baseline(loaded, monitored)
            self.assertIn(blocked.name, comparison["current_scan"]["files"])
            self.assertEqual(comparison["current_scan"]["failed_files"], [])
            self.assert_incomplete_reports(
                loaded, comparison, baseline_path, "baseline", error,
                [(blocked.name, "unverified"), (stable.name, "unchanged")],
            )

    def test_inaccessible_current_folder_is_unverified_in_both_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            monitored = workspace / "monitored"
            private = monitored / "private"
            private.mkdir(parents=True)
            (private / "a.txt").write_bytes(b"a")
            (private / "b.txt").write_bytes(b"b")
            public = monitored / "public.txt"
            public.write_bytes(b"original")

            baseline_path = workspace / "baseline.json"
            save_baseline(create_baseline(monitored), baseline_path)
            loaded = load_baseline(baseline_path)
            self.assertTrue(loaded["complete"])
            self.assertEqual(loaded["failed_files"], [])
            public.write_bytes(b"updated")
            iterdir = Path.iterdir

            def list_accessible_folder(folder):
                if folder == private:
                    raise PermissionError("Folder access denied")
                return iterdir(folder)

            with patch.object(Path, "iterdir", new=list_accessible_folder):
                comparison = compare_folder_with_baseline(loaded, monitored)
            error = {"path": "private", "kind": "folder", "error": "Folder access denied"}
            self.assertEqual(comparison["current_scan"]["failed_files"], [error])
            self.assert_incomplete_reports(
                loaded, comparison, baseline_path, "current", error,
                [
                    ("private/a.txt", "unverified"),
                    ("private/b.txt", "unverified"),
                    (public.name, "modified"),
                ],
            )

    def temporary_monitored_folder(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name).resolve() / "monitored"
        folder.mkdir()
        return folder

    def persist_baseline(self, folder):
        destination = folder.parent / "baseline.json"
        save_baseline(create_baseline(folder), destination)
        return load_baseline(destination)

    def test_empty_folder_through_both_reports(self):
        folder = self.temporary_monitored_folder()
        baseline = self.persist_baseline(folder)
        self.assertEqual(baseline["files"], {})
        comparison = compare_folder_with_baseline(baseline, folder)
        self.assertTrue(comparison["baseline_complete"])
        self.assertTrue(comparison["current_scan_complete"])
        self.assertEqual(comparison["summary"]["total"], 0)
        self.assertFalse(any(comparison["results"].values()))
        report = format_report(baseline, comparison)
        self.assertIn("No file results are available.", report)
        self.assertNotIn("WARNING:", report)

        destination = folder.parent / "empty.csv"
        export_comparison_csv(baseline, comparison, destination)
        with destination.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertCountEqual(
            [(row["Record Type"], row["Source"], row["Complete"]) for row in rows],
            [("scan", "baseline", "true"), ("scan", "current", "true")],
        )

    def test_unicode_and_spreadsheet_sensitive_paths_through_both_reports(self):
        folder = self.temporary_monitored_folder()
        csv_names = {
            "資料.txt": "資料.txt",
            "=1+1.txt": "'=1+1.txt",
            "@notes.txt": "'@notes.txt",
        }
        for name in csv_names:
            (folder / name).write_bytes(b"original")
        baseline = self.persist_baseline(folder)
        self.assertCountEqual(baseline["files"], csv_names.keys())
        for name in csv_names:
            (folder / name).write_bytes(b"edited")
        comparison = compare_folder_with_baseline(baseline, folder)
        self.assertCountEqual(comparison["results"]["modified"], csv_names.keys())
        lines = format_report(baseline, comparison).splitlines()
        for name in csv_names:
            self.assertIn(f"  Modified: {name}", lines)

        original = deepcopy(comparison)
        destination = folder.parent / "names.csv"
        export_comparison_csv(baseline, comparison, destination)
        with destination.open(encoding="utf-8", newline="") as stream:
            files = [row for row in csv.DictReader(stream) if row["Record Type"] == "file"]
        self.assertCountEqual(
            [(row["File Path"], row["Status"]) for row in files],
            [(name, "modified") for name in csv_names.values()],
        )
        self.assertEqual(comparison, original)

    def test_replacement_during_verification_reaches_both_reports(self):
        folder = self.temporary_monitored_folder()
        target = folder / "target.txt"
        target.write_bytes(b"original")
        (folder / "healthy.txt").write_bytes(b"stable")
        baseline = self.persist_baseline(folder)
        replacement = folder.parent / "replacement.txt"
        replacement.write_bytes(b"replaced")
        before = target.stat()
        os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
        real_open = Path.open

        @contextmanager
        def replace_after_read(path, mode="r", *args, **kwargs):
            with real_open(path, mode, *args, **kwargs) as stream:
                yield stream
            # Windows allows the real replacement once the read handle closes.
            if path == target and mode == "rb":
                replacement.replace(target)

        with patch.object(Path, "open", new=replace_after_read):
            comparison = compare_folder_with_baseline(baseline, folder)
        error, = comparison["current_scan"]["failed_files"]
        self.assertEqual((error["path"], error["kind"]), ("target.txt", "file"))
        self.assertIn("replaced", error["error"])
        self.assert_incomplete_reports(
            baseline, comparison, folder.parent / "baseline.json", "current", error,
            [("target.txt", "unverified"), ("healthy.txt", "unchanged")],
        )

    def test_csv_publication_failure_and_retry(self):
        folder = self.temporary_monitored_folder()
        target = folder / "edited.txt"
        target.write_bytes(b"original")
        baseline = self.persist_baseline(folder)
        target.write_bytes(b"updated")
        comparison = compare_folder_with_baseline(baseline, folder)
        original_data = deepcopy((baseline, comparison))
        baseline_path = folder.parent / "baseline.json"
        saved_bytes = baseline_path.read_bytes()
        destination = folder.parent / "report.csv"
        prior_report = b"File Path,Status\r\nold.txt,deleted\r\n"
        destination.write_bytes(prior_report)
        original_entries = set(folder.parent.iterdir())

        with patch("src.csv_exporter.os.replace", side_effect=PermissionError("Report locked")):
            with self.assertRaisesRegex(PermissionError, "Report locked"):
                export_comparison_csv(baseline, comparison, destination)
        self.assertEqual(destination.read_bytes(), prior_report)
        self.assertEqual(set(folder.parent.iterdir()), original_entries)
        self.assertEqual((baseline, comparison), original_data)
        self.assertEqual(baseline_path.read_bytes(), saved_bytes)

        export_comparison_csv(baseline, comparison, destination)
        with destination.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertCountEqual(
            [(r["Record Type"], r["File Path"], r["Status"], r["Source"], r["Complete"])
             for r in rows],
            [("file", "edited.txt", "modified", "", ""),
             ("scan", "", "", "baseline", "true"), ("scan", "", "", "current", "true")],
        )
        self.assertEqual((baseline, comparison), original_data)
        self.assertEqual(baseline_path.read_bytes(), saved_bytes)

    def assert_incomplete_reports(
        self, loaded, comparison, baseline_path, source, error, files
    ):
        saved_bytes = baseline_path.read_bytes()
        original_baseline = deepcopy(loaded)
        original_comparison = deepcopy(comparison)
        baseline_complete = source != "baseline"
        current_complete = source != "current"
        self.assertEqual(comparison["baseline_complete"], baseline_complete)
        self.assertEqual(comparison["current_scan_complete"], current_complete)
        self.assertCountEqual(
            [(path, status) for status, paths in comparison["results"].items() for path in paths],
            files,
        )
        counts = dict.fromkeys(("added", "modified", "deleted", "unchanged", "unverified"), 0)
        for _, status in files:
            counts[status] += 1
        self.assertEqual(comparison["summary"], dict(counts, total=len(files)))

        text = format_report(loaded, comparison)
        lines = text.splitlines()
        self.assertIn("WARNING: Verification is incomplete.", lines)
        self.assertIn(f"Baseline: {'Complete' if baseline_complete else 'Incomplete'}", lines)
        self.assertIn(f"Current scan: {'Complete' if current_complete else 'Incomplete'}", lines)
        self.assertIn(f"  Total file results: {len(files)}", lines)
        for status, count in counts.items():
            self.assertIn(f"  {status.title()}: {count}", lines)
        start = lines.index("File results") + 1
        end = lines.index("Baseline errors")
        self.assertCountEqual(
            [line for line in lines[start:end] if line],
            [f"  {status.title()}: {path}" for path, status in files],
        )
        heading = "Baseline errors" if source == "baseline" else "Current scan errors"
        self.assertEqual(
            lines[lines.index(heading) + 1],
            f"  {error['path']}: {error['error']}",
        )
        self.assertEqual(loaded, original_baseline)
        self.assertEqual(comparison, original_comparison)
        self.assertEqual(baseline_path.read_bytes(), saved_bytes)

        report_path = baseline_path.with_suffix(".csv")
        export_comparison_csv(loaded, comparison, report_path)
        with report_path.open(encoding="utf-8", newline="") as report:
            rows = list(csv.DictReader(report))
        # One row per expected file, two scan records, and one error record.
        self.assertEqual(len(rows), len(files) + 2 + 1)
        self.assertCountEqual(
            [(r["File Path"], r["Status"]) for r in rows if r["Record Type"] == "file"], files,
        )
        self.assertCountEqual(
            [(r["Source"], r["Complete"]) for r in rows if r["Record Type"] == "scan"],
            [("baseline", str(baseline_complete).lower()), ("current", str(current_complete).lower())],
        )
        self.assertEqual(
            [(r["Source"], r["File Path"], r["Kind"], r["Error"], r["Status"])
             for r in rows if r["Record Type"] == "error"],
            [(source, error["path"], error["kind"], error["error"], "")],
        )
        self.assertEqual(loaded, original_baseline)
        self.assertEqual(comparison, original_comparison)
        self.assertEqual(baseline_path.read_bytes(), saved_bytes)

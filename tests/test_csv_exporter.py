"""CSV export tests, including real comparison data and failed writes."""

import csv
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.baseline_manager import create_baseline
from src.change_detector import compare_folder_with_baseline
from src.csv_exporter import export_comparison_csv, STATUSES


class TestCsvExporter(unittest.TestCase):
    def setUp(self):
        repository = Path(__file__).resolve().parents[1]
        temporary = tempfile.TemporaryDirectory(dir=repository)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.monitored = self.root / "monitored"
        self.monitored.mkdir()
        self.output = self.root / "report.csv"
        self.baseline = create_baseline(self.monitored)
        self.comparison = compare_folder_with_baseline(self.baseline, self.monitored)

    def export_rows(self):
        export_comparison_csv(self.baseline, self.comparison, self.output)
        with self.output.open(encoding="utf-8", newline="") as report:
            return list(csv.DictReader(report))

    def test_all_statuses_nested_paths_and_global_order(self):
        for index, status in enumerate(STATUSES):
            self.comparison["results"][status] = [f"nested/{4 - index}.txt"]
        rows = self.export_rows()
        files = [row for row in rows if row["Record Type"] == "file"]
        self.assertEqual([row["File Path"] for row in files], [
            f"nested/{index}.txt" for index in range(5)
        ])
        self.assertEqual({row["Status"] for row in files}, set(STATUSES))

    def test_empty_results_still_include_completion_records(self):
        rows = self.export_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["Source"] for row in rows], ["baseline", "current"])
        self.assertTrue(all(row["Complete"] == "true" for row in rows))
        self.assertTrue(all(row["Status"] == "" for row in rows))

    def test_deterministic_output_and_inputs_unchanged(self):
        self.comparison["results"]["added"] = ["z.txt", "a.txt"]
        self.baseline["failed_files"] = [
            {"path": "z", "error": "Denied", "kind": "folder"},
            {"path": "a", "error": "Missing"},
        ]
        original = deepcopy((self.baseline, self.comparison))
        self.export_rows()
        first = self.output.read_bytes()
        self.assertEqual((self.baseline, self.comparison), original)
        self.comparison["results"]["added"].reverse()
        self.baseline["failed_files"].reverse()
        self.export_rows()
        self.assertEqual(first, self.output.read_bytes())

    def test_unicode_and_csv_quoting(self):
        name = 'nested/caf\u00e9,"quoted"\nfile.txt'
        self.comparison["results"]["unchanged"] = [name]
        rows = self.export_rows()
        self.assertEqual(rows[0]["File Path"], name)
        self.assertNotIn(b"\r\r\n", self.output.read_bytes())

    def test_formula_injection_in_paths_and_errors(self):
        dangerous = ["=1+1", "+SUM(1)", "-1", "@SUM(1)", "  =1", "\ttext", "\rtext", "\ntext"]
        self.comparison["results"]["unverified"] = dangerous[:]
        self.comparison["current_scan"]["failed_files"] = [
            {"path": value, "error": value} for value in dangerous
        ]
        rows = self.export_rows()
        for row in rows:
            if row["Record Type"] in ("file", "error"):
                self.assertTrue(row["File Path"].startswith("'"))
            if row["Record Type"] == "error":
                self.assertTrue(row["Error"].startswith("'"))

    def test_incomplete_baseline_preserves_unverified_and_error(self):
        file = self.monitored / "blocked.txt"
        file.write_text("data", encoding="utf-8")
        with patch("src.baseline_manager.hash_file", side_effect=PermissionError("Denied")):
            self.baseline = create_baseline(self.monitored)
        self.comparison = compare_folder_with_baseline(self.baseline, self.monitored)
        rows = self.export_rows()
        self.assertEqual(rows[0]["Status"], "unverified")
        self.assertEqual(rows[1]["Complete"], "false")
        self.assertEqual(rows[2]["Complete"], "true")
        self.assertEqual(rows[3]["Source"], "baseline")
        self.assertEqual(rows[3]["Error"], "Denied")
        self.assertEqual(rows[3]["Kind"], "file")

    def test_incomplete_current_scan_does_not_claim_deletion(self):
        (self.monitored / "old.txt").write_text("data", encoding="utf-8")
        self.baseline = create_baseline(self.monitored)
        with patch("src.change_detector.scan_folder", side_effect=PermissionError("Denied")):
            self.comparison = compare_folder_with_baseline(self.baseline, self.monitored)
        rows = self.export_rows()
        self.assertEqual(rows[0]["Status"], "unverified")
        self.assertEqual(rows[2]["Complete"], "false")
        self.assertEqual(rows[3]["Source"], "current")
        self.assertEqual(rows[3]["File Path"], ".")
        self.assertEqual(rows[3]["Kind"], "folder")
        self.assertIn("Denied", rows[3]["Error"])

    def test_root_error_without_file_results_is_preserved(self):
        with patch("src.change_detector.scan_folder", side_effect=OSError("Scan failed")):
            self.comparison = compare_folder_with_baseline(self.baseline, self.monitored)
        rows = self.export_rows()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["Complete"], "false")
        self.assertEqual(rows[2]["Record Type"], "error")

    def test_destination_inside_monitored_folder_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the monitored folder"):
            export_comparison_csv(self.baseline, self.comparison, self.monitored / "report.csv")

    def test_missing_parent_and_directory_destinations(self):
        for destination in (self.root / "missing" / "report.csv", self.root):
            with self.subTest(destination=destination):
                with self.assertRaisesRegex(OSError, "Could not export CSV"):
                    export_comparison_csv(self.baseline, self.comparison, destination)
        self.assertEqual(list(self.root.glob(".hashguard-*.tmp")), [])

    def test_unwritable_destination(self):
        with patch("src.csv_exporter.tempfile.NamedTemporaryFile", side_effect=PermissionError("Denied")):
            with self.assertRaisesRegex(PermissionError, "Could not export CSV"):
                self.export_rows()
        self.assertFalse(self.output.exists())

    def test_successful_export_replaces_existing_csv_contents(self):
        self.output.write_text(
            "File Path,Status\nold.txt,deleted\n" * 20,
            encoding="utf-8",
        )
        self.comparison["results"]["added"] = ["new.txt"]

        rows = self.export_rows()

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["File Path"], "new.txt")
        self.assertEqual(rows[0]["Status"], "added")
        self.assertEqual(rows[0]["Record Type"], "file")
        self.assertEqual([row["Source"] for row in rows[1:]], ["baseline", "current"])
        self.assertTrue(all(row["Complete"] == "true" for row in rows[1:]))
        self.assertNotIn("old.txt", self.output.read_text(encoding="utf-8"))
        self.assertEqual(list(self.root.glob(".hashguard-*.tmp")), [])

    def test_failed_write_preserves_existing_output_and_cleans_up(self):
        self.output.write_bytes(b"previous report")
        with patch("src.csv_exporter.csv.writer") as writer:
            writer.return_value.writerow.side_effect = [None, OSError("Disk full")]
            with self.assertRaisesRegex(OSError, "Disk full"):
                self.export_rows()
        self.assertEqual(self.output.read_bytes(), b"previous report")
        self.assertEqual(list(self.root.glob(".hashguard-*.tmp")), [])

    def test_failed_replace_preserves_existing_output_and_cleans_up(self):
        self.output.write_bytes(b"previous report")
        with patch("src.csv_exporter.os.replace", side_effect=PermissionError("Locked")):
            with self.assertRaisesRegex(PermissionError, "Locked"):
                self.export_rows()
        self.assertEqual(self.output.read_bytes(), b"previous report")
        self.assertEqual(list(self.root.glob(".hashguard-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()

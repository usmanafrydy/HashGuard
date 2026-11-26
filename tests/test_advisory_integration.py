"""Offline tests for advisory refresh and its independence from local monitoring."""

import csv
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import requests

from src.advisory_scraper import Advisory, AdvisoryManager, SOURCE_URL
from src.baseline_manager import create_baseline, load_baseline, save_baseline
from src.change_detector import compare_folder_with_baseline
from src.csv_exporter import export_comparison_csv
from src.report_formatter import format_report


LISTING = """
<html><body><main>
  <article>
    <div class="c-teaser__date"><time datetime="2026-11-20">November 20</time></div>
    <h3 class="c-teaser__title"><a href="/alerts/update">Security update</a></h3>
  </article>
  <article>
    <h3 class="c-teaser__title"><a href="/alerts/bulletin">Weekly bulletin</a></h3>
  </article>
</main></body></html>
"""


def html_response(html, status=200):
    response = requests.Response()
    response.status_code = status
    response.url = SOURCE_URL
    response.encoding = "utf-8"
    response._content = html.encode("utf-8")
    return response


class TestAdvisoryIntegration(unittest.TestCase):
    def setUp(self):
        self.manager = AdvisoryManager()
        self.get = self.enterContext(patch("src.advisory_scraper.requests.get"))

    def test_successful_retrieval(self):
        self.get.return_value = html_response(LISTING)
        self.assertTrue(self.manager.refresh())
        self.assertEqual(self.get.call_args.args, (SOURCE_URL,))
        self.assertEqual(self.manager.advisories, [
            Advisory("Security update", "2026-11-20", "https://www.cisa.gov/alerts/update"),
            Advisory("Weekly bulletin", "", "https://www.cisa.gov/alerts/bulletin"),
        ])
        stamp = self.manager.last_successful_retrieval
        self.assertIsInstance(stamp, datetime)
        self.assertEqual(stamp.tzinfo, timezone.utc)
        self.assertIsNone(self.manager.last_refresh_error)

    def assert_failed_refresh_preserves_state(self, failure, expected_error):
        self.get.side_effect = [html_response(LISTING), failure]
        self.assertTrue(self.manager.refresh())
        advisories = deepcopy(self.manager.advisories)
        stamp = self.manager.last_successful_retrieval
        self.assertFalse(self.manager.refresh())
        self.assertEqual(self.manager.advisories, advisories)
        self.assertEqual(self.manager.last_successful_retrieval, stamp)
        self.assertIn(expected_error, self.manager.last_refresh_error)

    def test_http_error_preserves_last_success(self):
        self.assert_failed_refresh_preserves_state(html_response("", 503), "503")

    def test_timeout_preserves_last_success(self):
        self.assert_failed_refresh_preserves_state(
            requests.Timeout("Advisory request timed out"), "timed out"
        )

    def test_unexpected_html_preserves_last_success(self):
        self.assert_failed_refresh_preserves_state(
            html_response("<html><article><h2>Maintenance</h2></article></html>"),
            "No security advisories could be extracted",
        )

    def test_successful_refresh_after_failure_replaces_old_results(self):
        updated = """
        <article><h3 class="c-teaser__title">
          <a href="/alerts/revised">Revised bulletin</a>
        </h3></article>
        """
        self.assert_failed_refresh_preserves_state(html_response("", 502), "502")
        self.get.side_effect = [html_response(updated)]
        self.assertTrue(self.manager.refresh())
        self.assertEqual(self.manager.advisories, [
            Advisory("Revised bulletin", "", "https://www.cisa.gov/alerts/revised")
        ])
        self.assertIsNone(self.manager.last_refresh_error)

    def test_offline_refresh_allows_local_comparison_and_reports(self):
        self.get.side_effect = requests.ConnectionError("Offline")
        self.assertFalse(self.manager.refresh())
        self.assertEqual(self.manager.last_refresh_error, "Offline")

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            folder = workspace / "monitored"
            folder.mkdir()
            document = folder / "document.txt"
            document.write_bytes(b"original")
            baseline_path = workspace / "baseline.json"
            save_baseline(create_baseline(folder), baseline_path)
            original_bytes = baseline_path.read_bytes()
            baseline = load_baseline(baseline_path)
            document.write_bytes(b"updated")
            comparison = compare_folder_with_baseline(baseline, folder)
            self.assertTrue(comparison["baseline_complete"])
            self.assertTrue(comparison["current_scan_complete"])
            self.assertEqual(comparison["summary"]["total"], 1)
            self.assertEqual(comparison["results"]["modified"], ["document.txt"])
            report = format_report(baseline, comparison)
            self.assertIn("  Modified: document.txt", report.splitlines())
            self.assertNotIn("WARNING:", report)

            destination = workspace / "comparison.csv"
            export_comparison_csv(baseline, comparison, destination)
            with destination.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertCountEqual(
                [(r["Record Type"], r["File Path"], r["Status"], r["Source"], r["Complete"])
                 for r in rows],
                [("file", "document.txt", "modified", "", ""),
                 ("scan", "", "", "baseline", "true"), ("scan", "", "", "current", "true")],
            )
            self.assertEqual(baseline_path.read_bytes(), original_bytes)
        self.get.assert_called_once()

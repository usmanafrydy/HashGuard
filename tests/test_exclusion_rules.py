
"""Tests for HashGuard exclusion rules."""

import unittest

from src.exclusion_rules import is_excluded


class TestExclusionRules(unittest.TestCase):

    def test_exclude_specific_file(self):
        result = is_excluded(
            "secret.txt",
            ["secret.txt"],
        )
        self.assertTrue(result)

    def test_exclude_log_files(self):
        self.assertTrue(
            is_excluded("debug.log", ["*.log"])
        )

        self.assertTrue(
            is_excluded("logs/error.log", ["*.log"])
        )

    def test_allow_normal_files(self):
        self.assertFalse(
            is_excluded("report.txt", ["*.log"])
        )

    def test_exclude_entire_folder(self):
        exclusions = ["cache/"]

        self.assertTrue(
            is_excluded("cache", exclusions)
        )

        self.assertTrue(
            is_excluded("cache/temp.txt", exclusions)
        )

    def test_exclude_specific_nested_folder(self):
        self.assertTrue(
            is_excluded(
                "data/cache/temp.txt",
                ["data/cache/"],
            )
        )

    def test_exclude_specific_relative_path(self):
        self.assertTrue(
            is_excluded(
                "documents/private.txt",
                ["documents/private.txt"],
            )
        )

    def test_no_exclusions(self):
        self.assertFalse(
            is_excluded("report.txt", [])
        )

    def test_windows_style_path(self):
        self.assertTrue(
            is_excluded(
                "logs\\error.log",
                ["*.log"],
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

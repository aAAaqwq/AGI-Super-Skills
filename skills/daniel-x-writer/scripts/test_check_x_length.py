#!/usr/bin/env python3
"""Regression tests for the conservative X length checker."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("check_x_length.py")
SPEC = importlib.util.spec_from_file_location("check_x_length", SCRIPT)
assert SPEC and SPEC.loader
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class WeightedLengthTests(unittest.TestCase):
    def test_counts_ascii_non_ascii_and_urls_conservatively(self) -> None:
        self.assertEqual(CHECKER.weighted_length("A币"), 3)
        self.assertEqual(CHECKER.weighted_length("看 https://example.com/long/path"), 26)

    def test_cli_reports_safe_and_over_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory) / "draft.txt"
            draft.write_text("短帖", encoding="utf-8")
            safe = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft), "--limit", "6", "--target", "4"],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(safe.returncode, 0, safe.stderr)
            self.assertEqual(json.loads(safe.stdout)["status"], "safe")

            draft.write_text("超长内容", encoding="utf-8")
            over = subprocess.run(
                [sys.executable, str(SCRIPT), str(draft), "--limit", "6", "--target", "4"],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(over.returncode, 2, over.stderr)
            self.assertEqual(json.loads(over.stdout)["status"], "over")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Regression test for the bundled platform-agent registry validator."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_platform_agent_registry.py")


class PlatformAgentRegistryValidatorTests(unittest.TestCase):
    def test_portable_snapshot_and_adversarial_self_tests_pass(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--self-test", "--json"],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["runtime"], "portable-snapshot-only")
        self.assertEqual(payload["issues"], [])


if __name__ == "__main__":
    unittest.main()

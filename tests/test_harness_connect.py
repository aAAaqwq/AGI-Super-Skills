import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE = os.environ.get("NODE", "node")


class HarnessConnectTests(unittest.TestCase):
    def test_merge_preserves_unmanaged_openclaw_agents(self) -> None:
        source = """
import { mergeManagedAgents } from './bin/installer/connect.mjs';
const existing = [
  { id: 'legacy', workspace: '/keep' },
  { id: 'ast-ceo', workspace: '/old-managed' },
];
const managed = [
  { id: 'ast-ceo', workspace: '/new-managed' },
  { id: 'ast-governor', workspace: '/governor' },
];
process.stdout.write(JSON.stringify(mergeManagedAgents(existing, managed)));
"""
        result = subprocess.run(
            [NODE, "--input-type=module", "-e", source],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        merged = json.loads(result.stdout)
        self.assertEqual(
            merged,
            [
                {"id": "legacy", "workspace": "/keep"},
                {"id": "ast-ceo", "workspace": "/new-managed"},
                {"id": "ast-governor", "workspace": "/governor"},
            ],
        )

    def test_openclaw_connect_dry_runs_before_validated_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            config.write_text('{"agents":{"list":[{"id":"legacy"}]}}\n', encoding="utf-8")
            log = root / "openclaw.log"
            fake = root / "openclaw"
            fake.write_text(
                """#!/bin/sh
set -eu
printf '%s\\t%s\\n' "$*" "${OPENCLAW_STATE_DIR:-}" >> "$OPENCLAW_TEST_LOG"
if [ "$1" = "--version" ]; then
  echo "OpenClaw test"
elif [ "$1" = "config" ] && [ "$2" = "get" ]; then
  printf '[{"id":"legacy","workspace":"/keep"}]\\n'
elif [ "$1" = "config" ] && [ "$2" = "patch" ]; then
  payload=$(cat)
  printf 'STDIN:%s\\n' "$payload" >> "$OPENCLAW_TEST_LOG"
  printf '{"ok":true}\\n'
elif [ "$1" = "config" ] && [ "$2" = "validate" ]; then
  printf '{"ok":true}\\n'
else
  exit 9
fi
""",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            connection = {
                "schemaVersion": 1,
                "harness": "openclaw",
                "runtimeEvidence": "pending",
                "requirements": {
                    "requiredMaxDepth": 2,
                    "maxChildrenPerAgent": 2,
                },
                "configPatch": {
                    "agents": {
                        "list": [
                            {
                                "id": "ast-ceo",
                                "workspace": str(state / "agency-agents/agi-super-team/ast-ceo"),
                            },
                            {
                                "id": "ast-governor",
                                "workspace": str(state / "agency-agents/agi-super-team/ast-governor"),
                            },
                        ]
                    }
                },
            }
            source = f"""
import {{ connectHarness }} from './bin/installer/connect.mjs';
const result = connectHarness({{
  tool: {{ id: 'openclaw' }},
  home: {json.dumps(str(home))},
  connection: {json.dumps(connection)},
  environment: {{
    ...process.env,
    OPENCLAW_CLI: {json.dumps(str(fake))},
    OPENCLAW_TEST_LOG: {json.dumps(str(log))},
  }},
}});
process.stdout.write(JSON.stringify(result));
"""
            result = subprocess.run(
                [NODE, "--input-type=module", "-e", source],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt["harness"], "openclaw")
            self.assertEqual(receipt["status"], "connected-structural")
            self.assertEqual(receipt["runtimeEvidence"], "pending")
            calls = log.read_text(encoding="utf-8").splitlines()
            dry_run = next(i for i, line in enumerate(calls) if "--dry-run" in line)
            apply = next(
                i
                for i, line in enumerate(calls)
                if "config patch" in line and "--dry-run" not in line
            )
            validate = next(i for i, line in enumerate(calls) if "config validate" in line)
            self.assertLess(dry_run, apply)
            self.assertLess(apply, validate)
            payload_lines = [line for line in calls if line.startswith("STDIN:")]
            self.assertEqual(len(payload_lines), 2)
            payload = json.loads(payload_lines[-1].removeprefix("STDIN:"))
            self.assertEqual(payload["agents"]["list"][0]["id"], "legacy")
            self.assertNotIn("bindings", payload)
            self.assertTrue(
                all(str(state) in line for line in calls if "\t" in line),
                calls,
            )
            backups = list((state / ".agi-super-team-backups").glob("openclaw.json.*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), config.read_text(encoding="utf-8"))

    def test_filesystem_harness_connect_does_not_claim_runtime_verification(self) -> None:
        source = """
import { connectHarness } from './bin/installer/connect.mjs';
const result = connectHarness({
  tool: { id: 'claude-code' },
  home: '/tmp/claude-home',
  connection: { harness: 'claude-code', runtimeEvidence: 'pending' },
});
process.stdout.write(JSON.stringify(result));
"""
        result = subprocess.run(
            [NODE, "--input-type=module", "-e", source],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["status"], "filesystem-connected")
        self.assertEqual(receipt["runtimeEvidence"], "pending")


if __name__ == "__main__":
    unittest.main()

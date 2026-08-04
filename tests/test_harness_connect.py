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
    def _write_fake_openclaw(self, root: Path) -> tuple[Path, Path]:
        log = root / "openclaw.log"
        fake = root / "openclaw"
        fake.write_text(
            """#!/usr/bin/env node
import { appendFileSync, chmodSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

const args = process.argv.slice(2);
const mode = process.env.OPENCLAW_TEST_MODE || 'success';
const log = process.env.OPENCLAW_TEST_LOG;
appendFileSync(log, `${args.join(' ')}\\n`);
const config = join(process.env.OPENCLAW_STATE_DIR, 'openclaw.json');

if (args[0] === '--version') {
  process.stdout.write('OpenClaw test\\n');
  if (mode === 'get-spawn-error') unlinkSync(process.argv[1]);
} else if (args[0] === 'config' && args[1] === 'get') {
  if (mode === 'get-error') {
    process.stderr.write('permission denied while reading configuration\\n');
    process.exitCode = 7;
  } else if (mode === 'get-signal') {
    process.kill(process.pid, 'SIGTERM');
  } else if (mode === 'get-missing' || mode === 'missing-validate-fail') {
    process.stderr.write('Config path not found: agents.list. Run openclaw config validate to inspect config shape.\\n');
    process.exitCode = 1;
  } else {
    process.stdout.write(`${process.env.OPENCLAW_EXISTING_JSON || '[]'}\\n`);
  }
} else if (args[0] === 'config' && args[1] === 'patch') {
  readFileSync(0, 'utf8');
  if (args.includes('--dry-run')) {
    process.stdout.write('{"ok":true}\\n');
  } else {
    mkdirSync(dirname(config), { recursive: true });
    writeFileSync(config, process.env.OPENCLAW_APPLIED_CONTENT || '{"applied":true}\\n');
    if (mode === 'patch-fail') {
      process.stderr.write('patch failed after partial write\\n');
      process.exitCode = 8;
    } else {
      process.stdout.write('{"ok":true}\\n');
    }
  }
} else if (args[0] === 'config' && args[1] === 'validate') {
  if (mode === 'validate-fail' || mode === 'missing-validate-fail') {
    process.stderr.write('validation failed\\n');
    process.exitCode = 9;
  } else if (mode === 'validate-drift') {
    writeFileSync(config, '{"thirdParty":true}\\n');
    process.stderr.write('validation failed after concurrent change\\n');
    process.exitCode = 9;
  } else if (mode === 'validate-chmod') {
    chmodSync(config, 0o644);
    process.stderr.write('validation failed after concurrent chmod\\n');
    process.exitCode = 9;
  } else {
    process.stdout.write('{"ok":true}\\n');
  }
} else {
  process.exitCode = 10;
}
""",
            encoding="utf-8",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        return fake, log

    def _connect_with_fake(
        self,
        *,
        home: Path,
        fake: Path,
        log: Path,
        mode: str,
        existing: list[dict] | None = None,
        applied_content: str = '{"applied":true}\n',
    ) -> subprocess.CompletedProcess[str]:
        connection = {
            "requirements": {"requiredMaxDepth": 2, "maxChildrenPerAgent": 2},
            "configPatch": {"agents": {"list": [{"id": "ast-ceo"}]}},
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
    OPENCLAW_TEST_MODE: {json.dumps(mode)},
    OPENCLAW_EXISTING_JSON: {json.dumps(json.dumps(existing or []))},
    OPENCLAW_APPLIED_CONTENT: {json.dumps(applied_content)},
  }},
}});
process.stdout.write(JSON.stringify(result));
"""
        return subprocess.run(
            [NODE, "--input-type=module", "-e", source],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_openclaw_get_failure_aborts_before_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            original = b'{"agents":{"list":[{"id":"legacy"}]}}\n'
            config.write_bytes(original)
            log = root / "openclaw.log"
            fake = root / "openclaw"
            fake.write_text(
                """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$OPENCLAW_TEST_LOG"
if [ "$1" = "--version" ]; then
  echo "OpenClaw test"
elif [ "$1" = "config" ] && [ "$2" = "get" ]; then
  echo "permission denied while reading configuration" >&2
  exit 7
else
  echo '{"ok":true}'
fi
""",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            source = f"""
import {{ connectHarness }} from './bin/installer/connect.mjs';
connectHarness({{
  tool: {{ id: 'openclaw' }},
  home: {json.dumps(str(home))},
  connection: {{ configPatch: {{ agents: {{ list: [] }} }} }},
  environment: {{
    ...process.env,
    OPENCLAW_CLI: {json.dumps(str(fake))},
    OPENCLAW_TEST_LOG: {json.dumps(str(log))},
  }},
}});
"""
            result = subprocess.run(
                [NODE, "--input-type=module", "-e", source],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("permission denied", result.stderr)
            self.assertEqual(config.read_bytes(), original)
            self.assertFalse(
                any("config patch" in line for line in log.read_text().splitlines())
            )

    def test_openclaw_get_signal_aborts_before_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            original = b'{"agents":{"list":[]}}\n'
            config.write_bytes(original)
            fake, log = self._write_fake_openclaw(root)

            result = self._connect_with_fake(
                home=home,
                fake=fake,
                log=log,
                mode="get-signal",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SIGTERM", result.stderr)
            self.assertEqual(config.read_bytes(), original)
            self.assertFalse(
                any("config patch" in line for line in log.read_text().splitlines())
            )

    def test_openclaw_get_spawn_error_aborts_before_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            original = b'{"agents":{"list":[]}}\n'
            config.write_bytes(original)
            fake, log = self._write_fake_openclaw(root)

            result = self._connect_with_fake(
                home=home,
                fake=fake,
                log=log,
                mode="get-spawn-error",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ENOENT", result.stderr)
            self.assertEqual(config.read_bytes(), original)
            self.assertFalse(
                any("config patch" in line for line in log.read_text().splitlines())
            )

    def test_openclaw_recognized_missing_agents_list_connects_from_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            (home / ".openclaw").mkdir(parents=True)
            fake, log = self._write_fake_openclaw(root)

            result = self._connect_with_fake(
                home=home,
                fake=fake,
                log=log,
                mode="get-missing",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt["managedAgents"], ["ast-ceo"])
            self.assertEqual(receipt["preservedAgents"], [])

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

    def test_openclaw_patch_failure_restores_existing_config_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            original = b'{\n  "agents": {"list": [{"id": "legacy"}]}\n}\n'
            config.write_bytes(original)
            fake, log = self._write_fake_openclaw(root)

            result = self._connect_with_fake(
                home=home,
                fake=fake,
                log=log,
                mode="patch-fail",
                existing=[{"id": "legacy"}],
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("patch failed", result.stderr)
            self.assertEqual(config.read_bytes(), original)

    def test_openclaw_validation_failure_restores_existing_config_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            original = b'{\r\n  "agents": {"list": [{"id": "legacy"}]}\r\n}\r\n'
            config.write_bytes(original)
            fake, log = self._write_fake_openclaw(root)

            result = self._connect_with_fake(
                home=home,
                fake=fake,
                log=log,
                mode="validate-fail",
                existing=[{"id": "legacy"}],
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("validation failed", result.stderr)
            self.assertEqual(config.read_bytes(), original)

    def test_openclaw_validation_failure_removes_new_config_when_none_existed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            fake, log = self._write_fake_openclaw(root)

            result = self._connect_with_fake(
                home=home,
                fake=fake,
                log=log,
                mode="missing-validate-fail",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("validation failed", result.stderr)
            self.assertFalse(config.exists())

    def test_openclaw_rollback_refuses_to_overwrite_concurrent_config_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            original = b'{"agents":{"list":[{"id":"legacy"}]}}\n'
            drifted = b'{"thirdParty":true}\n'
            config.write_bytes(original)
            fake, log = self._write_fake_openclaw(root)

            result = self._connect_with_fake(
                home=home,
                fake=fake,
                log=log,
                mode="validate-drift",
                existing=[{"id": "legacy"}],
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("changed concurrently", result.stderr)
            self.assertIn("original backup preserved at", result.stderr)
            self.assertEqual(config.read_bytes(), drifted)
            backups = list(
                (state / ".agi-super-team-backups").glob("openclaw.json.*.bak")
            )
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)

    @unittest.skipIf(os.name == "nt", "POSIX permission bits are not authoritative on Windows")
    def test_openclaw_rollback_detects_concurrent_permission_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            original = b'{"agents":{"list":[]} }\n'
            config.write_bytes(original)
            config.chmod(0o600)
            fake, log = self._write_fake_openclaw(root)

            result = self._connect_with_fake(
                home=home,
                fake=fake,
                log=log,
                mode="validate-chmod",
                applied_content=original.decode("utf-8"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("changed concurrently", result.stderr)
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o644)

    @unittest.skipIf(os.name == "nt", "POSIX permission bits are not authoritative on Windows")
    def test_openclaw_backup_permissions_are_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            config.write_text('{"agents":{"list":[]}}\n', encoding="utf-8")
            backup_root = state / ".agi-super-team-backups"
            backup_root.mkdir(mode=0o777)
            backup_root.chmod(0o777)
            fake, log = self._write_fake_openclaw(root)

            result = self._connect_with_fake(
                home=home,
                fake=fake,
                log=log,
                mode="success",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            backup = next(backup_root.glob("openclaw.json.*.bak"))
            self.assertEqual(stat.S_IMODE(backup_root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)

    def test_openclaw_transaction_can_rollback_after_successful_connection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            original = b'{"agents":{"list":[{"id":"legacy"}]}}\n'
            config.write_bytes(original)
            fake, log = self._write_fake_openclaw(root)
            connection = {
                "requirements": {"requiredMaxDepth": 2, "maxChildrenPerAgent": 2},
                "configPatch": {"agents": {"list": [{"id": "ast-ceo"}]}},
            }
            source = f"""
import {{ connectHarnessTransaction }} from './bin/installer/connect.mjs';
const transaction = connectHarnessTransaction({{
  tool: {{ id: 'openclaw' }},
  home: {json.dumps(str(home))},
  connection: {json.dumps(connection)},
  environment: {{
    ...process.env,
    OPENCLAW_CLI: {json.dumps(str(fake))},
    OPENCLAW_TEST_LOG: {json.dumps(str(log))},
    OPENCLAW_TEST_MODE: 'success',
    OPENCLAW_EXISTING_JSON: '[{{"id":"legacy"}}]',
    OPENCLAW_APPLIED_CONTENT: '{{"applied":true}}\\n',
  }},
}});
const rollback = transaction.rollback();
process.stdout.write(JSON.stringify({{ receipt: transaction.receipt, rollback }}));
"""

            result = subprocess.run(
                [NODE, "--input-type=module", "-e", source],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["receipt"]["status"], "connected-structural")
            self.assertEqual(output["rollback"]["status"], "rolled-back")
            self.assertEqual(config.read_bytes(), original)

    def test_openclaw_transaction_commit_is_idempotent_and_closes_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            config.write_text('{"agents":{"list":[]}}\n', encoding="utf-8")
            fake, log = self._write_fake_openclaw(root)
            connection = {
                "requirements": {"requiredMaxDepth": 2, "maxChildrenPerAgent": 2},
                "configPatch": {"agents": {"list": [{"id": "ast-ceo"}]}},
            }
            source = f"""
import {{ connectHarnessTransaction }} from './bin/installer/connect.mjs';
const transaction = connectHarnessTransaction({{
  tool: {{ id: 'openclaw' }},
  home: {json.dumps(str(home))},
  connection: {json.dumps(connection)},
  environment: {{
    ...process.env,
    OPENCLAW_CLI: {json.dumps(str(fake))},
    OPENCLAW_TEST_LOG: {json.dumps(str(log))},
    OPENCLAW_TEST_MODE: 'success',
    OPENCLAW_EXISTING_JSON: '[]',
  }},
}});
const first = transaction.commit();
const second = transaction.commit();
const rollback = transaction.rollback();
process.stdout.write(JSON.stringify({{ first, second, rollback }}));
"""

            result = subprocess.run(
                [NODE, "--input-type=module", "-e", source],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["first"]["status"], "committed")
            self.assertEqual(output["second"]["status"], "committed")
            self.assertEqual(output["rollback"]["status"], "not-active")

    def test_openclaw_preflight_is_read_only_and_exercises_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            state = home / ".openclaw"
            state.mkdir(parents=True)
            config = state / "openclaw.json"
            original = b'{"agents":{"list":[{"id":"legacy"}]}}\n'
            config.write_bytes(original)
            fake, log = self._write_fake_openclaw(root)
            connection = {
                "requirements": {"requiredMaxDepth": 2, "maxChildrenPerAgent": 2},
                "configPatch": {"agents": {"list": [{"id": "ast-ceo"}]}},
            }
            source = f"""
import {{ preflightHarnessConnection }} from './bin/installer/connect.mjs';
const result = preflightHarnessConnection({{
  tool: {{ id: 'openclaw' }},
  home: {json.dumps(str(home))},
  connection: {json.dumps(connection)},
  environment: {{
    ...process.env,
    OPENCLAW_CLI: {json.dumps(str(fake))},
    OPENCLAW_TEST_LOG: {json.dumps(str(log))},
    OPENCLAW_TEST_MODE: 'success',
    OPENCLAW_EXISTING_JSON: '[{{"id":"legacy"}}]',
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
            output = json.loads(result.stdout)
            self.assertEqual(output["status"], "ready")
            self.assertEqual(output["preservedAgents"], ["legacy"])
            calls = log.read_text(encoding="utf-8").splitlines()
            self.assertTrue(any("config patch" in call and "--dry-run" in call for call in calls))
            self.assertFalse(any("config patch" in call and "--dry-run" not in call for call in calls))
            self.assertFalse(any("config validate" in call for call in calls))
            self.assertEqual(config.read_bytes(), original)
            self.assertFalse((state / ".agi-super-team-backups").exists())

    @unittest.skipUnless(os.name == "nt", "requires Windows cmd.exe")
    def test_openclaw_preflight_launches_cmd_shim_on_windows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agi super team ") as directory:
            root = Path(directory)
            home = root / "home"
            (home / ".openclaw").mkdir(parents=True)
            fake = root / "openclaw.cmd"
            fake.write_text(
                """@echo off
if "%1"=="--version" (
  echo OpenClaw Windows test
  exit /b 0
)
if "%1"=="config" if "%2"=="get" (
  echo []
  exit /b 0
)
if "%1"=="config" if "%2"=="patch" (
  more ^> nul
  echo {"ok":true}
  exit /b 0
)
exit /b 10
""",
                encoding="utf-8",
            )
            connection = {
                "requirements": {"requiredMaxDepth": 2, "maxChildrenPerAgent": 2},
                "configPatch": {"agents": {"list": [{"id": "ast-ceo"}]}},
            }
            source = f"""
import {{ preflightHarnessConnection }} from './bin/installer/connect.mjs';
const result = preflightHarnessConnection({{
  tool: {{ id: 'openclaw' }},
  home: {json.dumps(str(home))},
  connection: {json.dumps(connection)},
  environment: {{ ...process.env, OPENCLAW_CLI: {json.dumps(str(fake))} }},
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
            self.assertEqual(json.loads(result.stdout)["status"], "ready")

    def test_receipt_transaction_restores_existing_receipt_on_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = root / ".openclaw" / "agi-super-team" / "receipt.json"
            receipt.parent.mkdir(parents=True)
            original = b'{"status":"previous"}\r\n'
            receipt.write_bytes(original)
            source = f"""
import {{ writeHarnessReceiptTransaction }} from './bin/installer/connect.mjs';
const transaction = writeHarnessReceiptTransaction({{
  root: {json.dumps(str(root))},
  connectionPath: '.openclaw/agi-super-team/connection.json',
  receipt: {{ status: 'connected-structural' }},
}});
const written = await import('node:fs').then((fs) => fs.readFileSync(transaction.path, 'utf8'));
const rollback = transaction.rollback();
process.stdout.write(JSON.stringify({{ written, rollback }}));
"""

            result = subprocess.run(
                [NODE, "--input-type=module", "-e", source],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = json.loads(result.stdout)
            self.assertIn("connected-structural", output["written"])
            self.assertEqual(output["rollback"]["status"], "rolled-back")
            self.assertEqual(receipt.read_bytes(), original)

    def test_receipt_transaction_refuses_concurrent_change_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = root / ".openclaw" / "agi-super-team" / "receipt.json"
            receipt.parent.mkdir(parents=True)
            original = b'{"status":"original"}\n'
            concurrent = b'{"status":"concurrent"}\n'
            receipt.write_bytes(original)
            source = f"""
import {{ writeFileSync }} from 'node:fs';
import {{ writeHarnessReceiptTransaction }} from './bin/installer/connect.mjs';
const target = {json.dumps(str(receipt))};
const nextReceipt = {{
  get status() {{
    writeFileSync(target, {json.dumps(concurrent.decode("utf-8"))});
    return 'connected-structural';
  }},
}};
writeHarnessReceiptTransaction({{
  root: {json.dumps(str(root))},
  connectionPath: '.openclaw/agi-super-team/connection.json',
  receipt: nextReceipt,
}});
"""

            result = subprocess.run(
                [NODE, "--input-type=module", "-e", source],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("changed concurrently before write", result.stderr)
            self.assertEqual(receipt.read_bytes(), concurrent)
            leftovers = [
                path
                for path in receipt.parent.iterdir()
                if path.name.startswith(".agi-super-team-receipt")
            ]
            self.assertEqual(leftovers, [])

    @unittest.skipIf(os.name == "nt", "uses POSIX directory permissions")
    def test_receipt_commit_is_idempotent_when_backup_cleanup_cannot_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = root / ".openclaw" / "agi-super-team" / "receipt.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"status":"previous"}\n', encoding="utf-8")
            source = f"""
import {{ chmodSync }} from 'node:fs';
import {{ dirname }} from 'node:path';
import {{ writeHarnessReceiptTransaction }} from './bin/installer/connect.mjs';
const transaction = writeHarnessReceiptTransaction({{
  root: {json.dumps(str(root))},
  connectionPath: '.openclaw/agi-super-team/connection.json',
  receipt: {{ status: 'connected-structural' }},
}});
chmodSync(dirname(transaction.path), 0o500);
let first;
let second;
let rollback;
try {{
  first = transaction.commit();
  second = transaction.commit();
  rollback = transaction.rollback();
}} finally {{
  chmodSync(dirname(transaction.path), 0o700);
}}
process.stdout.write(JSON.stringify({{ first, second, rollback }}));
"""

            result = subprocess.run(
                [NODE, "--input-type=module", "-e", source],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["first"]["status"], "committed")
            self.assertTrue(output["first"]["backupPreserved"])
            self.assertTrue(Path(output["first"]["backup"]).exists())
            self.assertEqual(output["second"], output["first"])
            self.assertEqual(output["rollback"]["status"], "not-active")
            self.assertIn("connected-structural", receipt.read_text(encoding="utf-8"))

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

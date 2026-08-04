import os
import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLI = REPOSITORY_ROOT / "bin" / "agi-super-team.mjs"


class InstallerFileSafetyTests(unittest.TestCase):
    def test_skill_scripts_remain_executable_and_regular_content_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            home = fixture / "home"
            project = fixture / "project"
            project.mkdir()
            installed = subprocess.run(
                [
                    "node",
                    str(CLI),
                    "--home",
                    str(home),
                    "--project-dir",
                    str(project),
                    "--tool",
                    "claude-code",
                    "--no-agents",
                    "--install",
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            script = home / ".claude" / "skills" / "systematic-debugging" / "find-polluter.sh"
            skill = home / ".claude" / "skills" / "systematic-debugging" / "SKILL.md"
            self.assertTrue(script.stat().st_mode & stat.S_IXUSR)
            self.assertEqual(stat.S_IMODE(script.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(skill.stat().st_mode), 0o600)
            executed = subprocess.run(
                [os.fspath(script)],
                cwd=fixture,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(executed.returncode, 126, executed.stderr)
            self.assertIn("Usage:", executed.stdout)

    def test_transaction_rollback_restores_original_bytes_and_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory).resolve()
            existing = fixture / "existing.txt"
            existing.write_text("original\n", encoding="utf-8")
            existing.chmod(0o750)
            added = fixture / "added.txt"
            script = r"""
import { lstatSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { applyPlanTransaction } from "./bin/installer/core.mjs";

const root = process.argv[1];
const existing = join(root, "existing.txt");
const added = join(root, "added.txt");
const baseline = readFileSync(existing);
const transaction = applyPlanTransaction([
  {
    tool: "fixture",
    root,
    destination: existing,
    content: Buffer.from("replacement\n"),
    baseline,
    baselineMode: lstatSync(existing).mode & 0o777,
    mode: 0o600,
    label: "existing",
    status: "update",
  },
  {
    tool: "fixture",
    root,
    destination: added,
    content: Buffer.from("added\n"),
    baseline: null,
    baselineMode: null,
    mode: 0o700,
    label: "added",
    status: "add",
  },
]);
transaction.rollback();
console.log(JSON.stringify({ backups: transaction.backups }));
"""
            result = subprocess.run(
                ["node", "--input-type=module", "--eval", script, str(fixture)],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["backups"])
            self.assertEqual(existing.read_text(encoding="utf-8"), "original\n")
            self.assertEqual(stat.S_IMODE(existing.stat().st_mode), 0o750)
            self.assertFalse(added.exists())
            self.assertFalse((fixture / ".agi-super-team-backups").exists())

    def test_apply_rejects_mode_drift_after_preview_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory).resolve()
            destination = fixture / "existing.txt"
            destination.write_text("original\n", encoding="utf-8")
            destination.chmod(0o644)
            script = r"""
import { chmodSync, readFileSync } from "node:fs";
import { applyPlan } from "./bin/installer/core.mjs";

const [root, destination] = process.argv.slice(1);
const baseline = readFileSync(destination);
chmodSync(destination, 0o600);
try {
  applyPlan([{
    tool: "fixture",
    root,
    destination,
    content: Buffer.from("replacement\n"),
    baseline,
    baselineMode: 0o644,
    mode: 0o600,
    label: "existing",
    status: "update",
  }]);
  console.log("accepted");
} catch (error) {
  console.log(error.message);
}
"""
            result = subprocess.run(
                [
                    "node",
                    "--input-type=module",
                    "--eval",
                    script,
                    str(fixture),
                    str(destination),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("destination changed after preview", result.stdout)
            self.assertEqual(destination.read_text(encoding="utf-8"), "original\n")
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertEqual(sorted(path.name for path in fixture.iterdir()), ["existing.txt"])

    def test_doctor_reports_an_installed_script_that_lost_execute_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            home = fixture / "home"
            project = fixture / "project"
            project.mkdir()
            arguments = [
                "node",
                str(CLI),
                "--home",
                str(home),
                "--project-dir",
                str(project),
                "--tool",
                "claude-code",
                "--no-agents",
            ]
            installed = subprocess.run(
                [*arguments, "--install"],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            script = home / ".claude" / "skills" / "systematic-debugging" / "find-polluter.sh"
            script.chmod(0o600)

            doctor = subprocess.run(
                [*arguments, "--doctor"],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
            self.assertIn("mode", doctor.stdout.lower())

    def test_windows_doctor_compares_only_the_writable_mode_state(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory).resolve()
            destination = fixture / "script.sh"
            destination.write_text("payload\n", encoding="utf-8")
            script = r"""
import { chmodSync, readFileSync } from "node:fs";
import { doctor } from "./bin/installer/core.mjs";

const destination = process.argv[1];
const content = readFileSync(destination);
const plan = [{
  tool: "fixture",
  root: process.argv[2],
  destination,
  content,
  baseline: content,
  baselineMode: 0o666,
  mode: 0o700,
  platform: "win32",
  label: "script",
  status: "unchanged",
}];
chmodSync(destination, 0o666);
const writable = doctor(plan, []);
chmodSync(destination, 0o444);
const readonly = doctor(plan, []);
console.log(JSON.stringify({ writable, readonly }));
"""
            result = subprocess.run(
                [
                    "node",
                    "--input-type=module",
                    "--eval",
                    script,
                    str(destination),
                    str(fixture),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertTrue(output["writable"]["ok"])
            self.assertFalse(output["readonly"]["ok"])
            self.assertIn("mode drifted", output["readonly"]["issues"][0])

    def test_windows_repeated_plan_is_unchanged_when_only_unrepresentable_bits_differ(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory).resolve()
            script = r"""
import { chmodSync } from "node:fs";
import { join } from "node:path";
import { applyPlan, buildPlan } from "./bin/installer/core.mjs";

const home = process.argv[1];
const catalog = {
  agents: [],
  specialistGroups: {},
  assignedSkills: { byAgent: {} },
  skills: [],
};
const tools = [{
  id: "fixture",
  scope: "global",
  agentMode: "combined-rules",
  agentPaths: ["rules.md"],
  skillPaths: [],
}];
const options = {
  packageRoot: home,
  catalog,
  tools,
  home,
  projectDir: null,
  includeAgents: false,
  includeSkills: false,
  platform: "win32",
};
applyPlan(buildPlan(options));
chmodSync(join(home, "rules.md"), 0o666);
console.log(JSON.stringify(buildPlan(options).map(({ status, platform }) => ({ status, platform }))));
"""
            result = subprocess.run(
                ["node", "--input-type=module", "--eval", script, str(fixture)],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                [{"status": "unchanged", "platform": "win32"}],
            )

    def test_windows_transaction_rolls_back_after_runtime_reports_a_coarser_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory).resolve()
            destination = fixture / "existing.txt"
            destination.write_text("original\n", encoding="utf-8")
            destination.chmod(0o644)
            script = r"""
import { chmodSync, lstatSync, readFileSync } from "node:fs";
import { applyPlanTransaction } from "./bin/installer/core.mjs";

const [root, destination] = process.argv.slice(1);
const baseline = readFileSync(destination);
const transaction = applyPlanTransaction([{
  tool: "fixture",
  root,
  destination,
  content: Buffer.from("replacement\n"),
  baseline,
  baselineMode: lstatSync(destination).mode & 0o777,
  mode: 0o700,
  platform: "win32",
  label: "existing",
  status: "update",
}]);
chmodSync(destination, 0o666);
transaction.rollback();
console.log(JSON.stringify({
  content: readFileSync(destination, "utf8"),
  mode: lstatSync(destination).mode & 0o777,
}));
"""
            result = subprocess.run(
                [
                    "node",
                    "--input-type=module",
                    "--eval",
                    script,
                    str(fixture),
                    str(destination),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                {"content": "original\n", "mode": 0o644},
            )

    def test_transaction_rollback_removes_only_its_new_empty_directory_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory).resolve()
            root = fixture / "new-home"
            script = r"""
import { existsSync } from "node:fs";
import { join } from "node:path";
import { applyPlanTransaction } from "./bin/installer/core.mjs";

const root = process.argv[1];
const destination = join(root, "nested", "deeper", "installed.txt");
const transaction = applyPlanTransaction([{
  tool: "fixture",
  root,
  destination,
  content: Buffer.from("installed\n"),
  baseline: null,
  baselineMode: null,
  mode: 0o600,
  label: "added",
  status: "add",
}]);
const installed = existsSync(destination);
transaction.rollback();
console.log(JSON.stringify({ installed, rootExists: existsSync(root) }));
"""
            result = subprocess.run(
                ["node", "--input-type=module", "--eval", script, str(root)],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                {"installed": True, "rootExists": False},
            )

    def test_windows_later_write_failure_rolls_back_file_and_created_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory).resolve()
            root = fixture / "new-home"
            script = r"""
import { existsSync } from "node:fs";
import { join } from "node:path";
import { applyPlanTransaction } from "./bin/installer/core.mjs";

const root = process.argv[1];
const destination = join(root, "nested", "installed.txt");
const common = {
  tool: "fixture",
  root,
  destination,
  baseline: null,
  baselineMode: null,
  platform: "win32",
  label: "added",
  status: "add",
};
let message = "accepted";
try {
  applyPlanTransaction([
    { ...common, content: Buffer.from("first\n"), mode: 0o700 },
    { ...common, content: Buffer.from("second\n"), mode: 0o600 },
  ]);
} catch (error) {
  message = error.message;
}
console.log(JSON.stringify({ message, rootExists: existsSync(root) }));
"""
            result = subprocess.run(
                ["node", "--input-type=module", "--eval", script, str(root)],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertIn("destination changed after preview", output["message"])
            self.assertFalse(output["rootExists"])

    def test_transaction_rollback_preserves_user_content_added_to_a_new_root(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory).resolve()
            root = fixture / "new-home"
            script = r"""
import { existsSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { applyPlanTransaction } from "./bin/installer/core.mjs";

const root = process.argv[1];
const destination = join(root, "nested", "installed.txt");
const transaction = applyPlanTransaction([{
  tool: "fixture",
  root,
  destination,
  content: Buffer.from("installed\n"),
  baseline: null,
  baselineMode: null,
  mode: 0o600,
  label: "added",
  status: "add",
}]);
const userFile = join(root, "user.txt");
writeFileSync(userFile, "user\n");
transaction.rollback();
console.log(JSON.stringify({
  rootExists: existsSync(root),
  userFileExists: existsSync(userFile),
  nestedExists: existsSync(join(root, "nested")),
}));
"""
            result = subprocess.run(
                ["node", "--input-type=module", "--eval", script, str(root)],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                {
                    "rootExists": True,
                    "userFileExists": True,
                    "nestedExists": False,
                },
            )


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class InstallerPathSafetyTests(unittest.TestCase):
    def test_safe_root_rejects_posix_windows_drive_and_unc_roots(self):
        script = r"""
import path from "node:path";
import { safeRoot } from "./bin/installer/core.mjs";

const cases = [
  ["posix", "/", path.posix],
  ["win32-drive", "C:\\", path.win32],
  ["win32-unc", "\\\\server\\share\\", path.win32],
];
const results = Object.fromEntries(cases.map(([name, candidate, api]) => {
  try {
    safeRoot(candidate, "test root", api);
    return [name, "accepted"];
  } catch (error) {
    return [name, error.message];
  }
}));
console.log(JSON.stringify(results));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        outcomes = json.loads(result.stdout)
        for platform, outcome in outcomes.items():
            with self.subTest(platform=platform):
                self.assertIn("refusing unsafe test root", outcome)

    def test_safe_root_pins_the_physical_parent_of_a_missing_root(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            first = fixture / "first"
            second = fixture / "second"
            first.mkdir()
            second.mkdir()
            alias = fixture / "alias"
            alias.symlink_to(first, target_is_directory=True)

            script = r"""
import { unlinkSync, symlinkSync } from "node:fs";
import { join } from "node:path";
import { applyPlan, safeRoot } from "./bin/installer/core.mjs";

const [alias, first, second] = process.argv.slice(1);
const root = safeRoot(join(alias, "new-home"), "home");
unlinkSync(alias);
symlinkSync(second, alias, "dir");
const destination = join(root, "installed.txt");
applyPlan([{
  tool: "fixture",
  root,
  destination,
  content: Buffer.from("installed\n"),
  baseline: null,
  label: "fixture",
  status: "add",
}]);
console.log(JSON.stringify({ root, destination }));
"""
            result = subprocess.run(
                [
                    "node",
                    "--input-type=module",
                    "--eval",
                    script,
                    str(alias),
                    str(first),
                    str(second),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            # macOS exposes /var and /tmp through stable system aliases. The
            # installer pins their physical /private paths before planning.
            self.assertEqual(Path(output["root"]), first.resolve() / "new-home")
            self.assertEqual((first / "new-home" / "installed.txt").read_text(), "installed\n")
            self.assertFalse((second / "new-home").exists())

    def test_apply_rejects_an_unpinned_symlink_ancestor_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            outside = fixture / "outside"
            outside.mkdir()
            sentinel = outside / "keep.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            alias = fixture / "alias"
            alias.symlink_to(outside, target_is_directory=True)

            script = r"""
import { join } from "node:path";
import { applyPlan } from "./bin/installer/core.mjs";

const root = join(process.argv[1], "new-home");
try {
  applyPlan([{
    tool: "fixture",
    root,
    destination: join(root, "installed.txt"),
    content: Buffer.from("installed\n"),
    baseline: null,
    label: "fixture",
    status: "add",
  }]);
  console.log("accepted");
} catch (error) {
  console.log(error.message);
}
"""
            result = subprocess.run(
                ["node", "--input-type=module", "--eval", script, str(alias)],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("unsafe target root", result.stdout)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
            self.assertEqual(sorted(path.name for path in outside.iterdir()), ["keep.txt"])

    def test_walk_files_rejects_a_symlinked_source_root(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            physical = fixture / "physical"
            physical.mkdir()
            (physical / "payload.txt").write_text("outside\n", encoding="utf-8")
            linked = fixture / "linked-source"
            linked.symlink_to(physical, target_is_directory=True)
            script = r"""
import { walkFiles } from "./bin/installer/render.mjs";

try {
  walkFiles(process.argv[1]);
  console.log("accepted");
} catch (error) {
  console.log(error.message);
}
"""
            result = subprocess.run(
                ["node", "--input-type=module", "--eval", script, str(linked)],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("refusing symlinked source root", result.stdout)

    def test_global_ceo_payload_rejects_a_symlinked_source_file(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            global_root = (
                fixture
                / "plugins"
                / "agi-super-team-codex"
                / "payload"
                / "global"
            )
            global_root.mkdir(parents=True)
            outside = fixture / "outside.md"
            outside.write_text(
                "<!-- AGI-SUPER-TEAM:CEO:BEGIN -->\noutside\n"
                "<!-- AGI-SUPER-TEAM:CEO:END -->\n",
                encoding="utf-8",
            )
            (global_root / "AGENTS.md").symlink_to(outside)
            script = r"""
import { globalCeoPayload } from "./bin/installer/render.mjs";

try {
  globalCeoPayload(process.argv[1]);
  console.log("accepted");
} catch (error) {
  console.log(error.message);
}
"""
            result = subprocess.run(
                ["node", "--input-type=module", "--eval", script, str(fixture)],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("unsafe global CEO payload", result.stdout)

    def test_content_addressed_agent_markdown_pins_lf_checkouts(self):
        result = subprocess.run(
            [
                "git",
                "check-attr",
                "eol",
                "--",
                "agents/cto/subagents/frontend-developer/AGENTS.md",
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "agents/cto/subagents/frontend-developer/AGENTS.md: eol: lf",
        )

    def test_posix_and_windows_paths_require_strict_containment(self):
        script = r"""
import path from "node:path";
import { isStrictDescendant } from "./bin/installer/path-safety.mjs";

const contracts = {
  posix: {
    api: path.posix,
    root: "/pkg/agents",
    cases: {
      root: "/pkg/agents",
      child: "/pkg/agents/ceo",
      traversal: "/pkg/agents/../outside",
      siblingPrefix: "/pkg/agents-evil/ceo",
    },
  },
  win32: {
    api: path.win32,
    root: String.raw`C:\pkg\agents`,
    cases: {
      root: String.raw`C:\pkg\agents`,
      child: String.raw`C:\pkg\agents\ceo`,
      traversal: String.raw`C:\pkg\agents\..\outside`,
      siblingPrefix: String.raw`C:\pkg\agents-evil\ceo`,
      crossDrive: String.raw`D:\pkg\agents\ceo`,
    },
  },
  win32Unc: {
    api: path.win32,
    root: String.raw`\\server\share\agents`,
    cases: {
      child: String.raw`\\server\share\agents\ceo`,
      otherServer: String.raw`\\other\share\agents\ceo`,
      otherShare: String.raw`\\server\other\agents\ceo`,
    },
  },
};

console.log(JSON.stringify(Object.fromEntries(Object.entries(contracts).map(
  ([contract, { api, root, cases }]) => [
    contract,
    Object.fromEntries(Object.entries(cases).map(([name, candidate]) => [
      name,
      isStrictDescendant(root, candidate, api),
    ])),
  ],
))));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "posix": {
                    "root": False,
                    "child": True,
                    "traversal": False,
                    "siblingPrefix": False,
                },
                "win32": {
                    "root": False,
                    "child": True,
                    "traversal": False,
                    "siblingPrefix": False,
                    "crossDrive": False,
                },
                "win32Unc": {
                    "child": True,
                    "otherServer": False,
                    "otherShare": False,
                },
            },
        )

    def test_physical_containment_rejects_leaf_and_ancestor_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            root = fixture / "agents"
            child = root / "ceo" / "AGENTS.md"
            child.parent.mkdir(parents=True)
            child.write_text("canonical", encoding="utf-8")
            outside = fixture / "outside"
            outside.mkdir()
            outside_file = outside / "AGENTS.md"
            outside_file.write_text("outside", encoding="utf-8")
            leaf_link = root / "ceo" / "SOUL.md"
            leaf_link.symlink_to(outside_file)
            ancestor_link = root / "linked-agent"
            ancestor_link.symlink_to(outside, target_is_directory=True)

            script = r"""
import { isPhysicalStrictDescendant } from "./bin/installer/path-safety.mjs";

const [root, child, leafLink, ancestorChild] = process.argv.slice(1);
console.log(JSON.stringify({
  child: isPhysicalStrictDescendant(root, child),
  leafLink: isPhysicalStrictDescendant(root, leafLink),
  ancestorLink: isPhysicalStrictDescendant(root, ancestorChild),
}));
"""
            result = subprocess.run(
                [
                    "node",
                    "--input-type=module",
                    "--eval",
                    script,
                    str(root),
                    str(child),
                    str(leaf_link),
                    str(ancestor_link / "AGENTS.md"),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {"child": True, "leafLink": False, "ancestorLink": False},
        )


if __name__ == "__main__":
    unittest.main()

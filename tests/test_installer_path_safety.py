import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class InstallerPathSafetyTests(unittest.TestCase):
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

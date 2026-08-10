import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "bin" / "installer" / "harness-roots.mjs"


def resolve_roots(function_name: str, options: dict[str, object]) -> subprocess.CompletedProcess[str]:
    source = f"""
import {{ {function_name} }} from {json.dumps(MODULE.as_uri())};
const result = {function_name}({json.dumps(options)});
process.stdout.write(JSON.stringify(result));
"""
    return subprocess.run(
        ["node", "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class HarnessRootTests(unittest.TestCase):
    def assert_resolves(self, function_name: str, options: dict[str, object]):
        result = resolve_roots(function_name, options)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_hermes_home_override_is_the_installation_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            resolved = self.assert_resolves(
                "resolveHermesHome",
                {
                    "home": str(root / "os-home"),
                    "environment": {"HERMES_HOME": str(runtime)},
                    "runtimePlatform": "linux",
                },
            )
            self.assertEqual(Path(resolved), runtime.resolve())

    def test_hermes_defaults_match_posix_and_windows_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            posix = self.assert_resolves(
                "resolveHermesHome",
                {"home": str(home), "environment": {}, "runtimePlatform": "linux"},
            )
            windows = self.assert_resolves(
                "resolveHermesHome",
                {
                    "home": str(home),
                    "environment": {"LOCALAPPDATA": str(root / "local-app-data")},
                    "runtimePlatform": "win32",
                },
            )
            self.assertEqual(Path(posix), (home / ".hermes").resolve())
            self.assertEqual(Path(windows), (root / "local-app-data/hermes").resolve())

    def test_explicit_home_projects_the_windows_hermes_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            resolved = self.assert_resolves(
                "resolveHermesHome",
                {
                    "home": str(home),
                    "homeExplicit": True,
                    "environment": {"LOCALAPPDATA": str(root / "ambient")},
                    "runtimePlatform": "win32",
                },
            )
            self.assertEqual(Path(resolved), (home / "AppData/Local/hermes").resolve())

    def test_openclaw_config_directory_precedence_matches_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            effective_home = root / "effective-home"
            state = root / "state"
            config = root / "configuration/custom.json"

            config_only = self.assert_resolves(
                "resolveOpenClawRoots",
                {
                    "home": str(root / "os-home"),
                    "environment": {
                        "OPENCLAW_HOME": str(effective_home),
                        "OPENCLAW_CONFIG_PATH": str(config),
                    },
                },
            )
            self.assertEqual(Path(config_only["effectiveHome"]), effective_home.resolve())
            self.assertEqual(Path(config_only["configDir"]), config.parent.resolve())
            self.assertEqual(Path(config_only["configPath"]), config.resolve())

            state_and_config = self.assert_resolves(
                "resolveOpenClawRoots",
                {
                    "home": str(root / "os-home"),
                    "environment": {
                        "OPENCLAW_HOME": str(effective_home),
                        "OPENCLAW_STATE_DIR": str(state),
                        "OPENCLAW_CONFIG_PATH": str(config),
                    },
                },
            )
            self.assertEqual(Path(state_and_config["stateDir"]), state.resolve())
            self.assertEqual(Path(state_and_config["configDir"]), state.resolve())
            self.assertEqual(Path(state_and_config["configPath"]), config.resolve())

    def test_conflicting_explicit_home_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = resolve_roots(
                "resolveHermesHome",
                {
                    "home": str(root / "selected-home"),
                    "homeExplicit": True,
                    "environment": {"HERMES_HOME": str(root / "different-runtime")},
                    "runtimePlatform": "linux",
                },
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--home conflicts with HERMES_HOME", result.stderr)


if __name__ == "__main__":
    unittest.main()

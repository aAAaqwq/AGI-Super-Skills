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

    def test_openclaw_profile_environment_alone_does_not_project_cli_profile_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            resolved = self.assert_resolves(
                "resolveOpenClawRoots",
                {
                    "home": str(home),
                    "environment": {"OPENCLAW_PROFILE": "research"},
                },
            )
            self.assertEqual(Path(resolved["stateDir"]), (home / ".openclaw").resolve())
            self.assertEqual(
                Path(resolved["configPath"]),
                (home / ".openclaw/openclaw.json").resolve(),
            )
            self.assertEqual(Path(resolved["configDir"]), (home / ".openclaw").resolve())

    def test_openclaw_legacy_state_and_config_discovery_matches_target_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            legacy = home / ".clawdbot"
            legacy.mkdir(parents=True)
            legacy_config = legacy / "clawdbot.json"
            legacy_config.write_text("{}\n", encoding="utf-8")

            resolved = self.assert_resolves(
                "resolveOpenClawRoots",
                {"home": str(home), "environment": {}},
            )

            self.assertEqual(Path(resolved["stateDir"]), legacy.resolve())
            self.assertEqual(Path(resolved["configPath"]), legacy_config.resolve())
            self.assertEqual(Path(resolved["configDir"]), (home / ".openclaw").resolve())

    def test_build_plan_honors_a_tool_installation_root_for_direct_callers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            os_home = root / "os-home"
            installation_root = root / "openclaw-config"
            source = f"""
import {{ loadCatalog }} from './bin/installer/catalog.mjs';
import {{ buildPlan }} from './bin/installer/core.mjs';
const packageRoot = process.cwd();
const catalog = loadCatalog(packageRoot);
const original = catalog.tools.find((tool) => tool.id === 'openclaw');
const tool = {{
  ...original,
  installationRoot: {json.dumps(str(installation_root))},
  effectiveHome: {json.dumps(str(os_home))},
  stateDir: {json.dumps(str(installation_root))},
  configPath: {json.dumps(str(installation_root / 'openclaw.json'))},
}};
const plan = buildPlan({{
  packageRoot,
  catalog,
  tools: [tool],
  home: {json.dumps(str(os_home))},
  projectDir: null,
  includeAgents: true,
  includeSkills: false,
}});
process.stdout.write(JSON.stringify(plan.map((item) => ({{root: item.root, destination: item.destination}}))));
"""
            result = subprocess.run(
                ["node", "--input-type=module", "--eval", source],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = json.loads(result.stdout)
            expected_root = installation_root.resolve()
            self.assertTrue(plan)
            self.assertTrue(all(Path(item["root"]) == expected_root for item in plan))
            self.assertTrue(
                all(Path(item["destination"]).is_relative_to(expected_root) for item in plan)
            )

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

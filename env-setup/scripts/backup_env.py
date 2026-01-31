#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Environment Backup Script
Backup skills, output-styles, CLAUDE.md, and MCP config
"""

import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


class ClaudeEnvBackup:
    """Claude Code Environment Backup Tool"""

    def __init__(self, claude_dir: str = None, output_dir: str = None):
        self.claude_dir = Path(claude_dir or self._get_default_claude_dir())
        self.output_dir = Path(output_dir or ".")
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _get_default_claude_dir(self) -> Path:
        home = Path.home()
        if os.name == "nt":
            for possible in [home / ".claude", home / "AppData/Roaming/Claude"]:
                if possible.exists():
                    return possible
        return home / ".claude"

    def backup_skills(self, target_dir: Path) -> dict:
        """Backup all custom skills"""
        skills_dir = self.claude_dir / "skills"
        if not skills_dir.exists():
            return {"status": "skipped", "reason": "skills dir not found"}

        skills_backup = target_dir / "skills"
        skills_backup.mkdir(parents=True, exist_ok=True)

        copied = []
        skipped = []

        for item in skills_dir.iterdir():
            if item.is_dir():
                # Skip env-setup itself
                if item.name == "env-setup":
                    skipped.append(f"{item.name} (self)")
                    continue

                dest = skills_backup / item.name
                try:
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                    copied.append(item.name)
                except Exception as e:
                    skipped.append(f"{item.name} ({e})")

        return {
            "status": "success",
            "copied": copied,
            "skipped": skipped,
            "total": len(copied)
        }

    def backup_output_styles(self, target_dir: Path) -> dict:
        """Backup all output-styles"""
        styles_dir = self.claude_dir / "output-styles"
        if not styles_dir.exists():
            return {"status": "skipped", "reason": "output-styles dir not found"}

        styles_backup = target_dir / "output-styles"
        styles_backup.mkdir(parents=True, exist_ok=True)

        copied = []
        for item in styles_dir.glob("*.md"):
            shutil.copy2(item, styles_backup / item.name)
            copied.append(item.name)

        return {
            "status": "success",
            "copied": copied,
            "total": len(copied)
        }

    def backup_claude_md(self, target_dir: Path) -> dict:
        """Backup global CLAUDE.md"""
        claude_md = self.claude_dir / "CLAUDE.md"
        if not claude_md.exists():
            return {"status": "skipped", "reason": "CLAUDE.md not found"}

        shutil.copy2(claude_md, target_dir / "CLAUDE.md")
        return {
            "status": "success",
            "file": "CLAUDE.md"
        }

    def backup_mcp_config(self, target_dir: Path) -> dict:
        """Extract MCP config from .claude.json"""
        possible_configs = [
            Path.home() / ".claude.json",
            Path.home() / "AppData/Roaming/Claude/.claude.json",
            self.claude_dir.parent / ".claude.json"
        ]

        config_path = None
        for p in possible_configs:
            if p.exists():
                config_path = p
                break

        if not config_path:
            return {"status": "skipped", "reason": ".claude.json not found"}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            mcp_config = {}

            if "allowedTools" in config:
                mcp_tools = [t for t in config.get("allowedTools", []) if t.startswith("mcp__")]
                if mcp_tools:
                    mcp_config["allowedTools"] = mcp_tools

            if "mcpServers" in config:
                mcp_config["mcpServers"] = config["mcpServers"]

            if mcp_config:
                with open(target_dir / "mcp_config.json", "w", encoding="utf-8") as f:
                    json.dump(mcp_config, f, indent=2, ensure_ascii=False)
                return {
                    "status": "success",
                    "file": "mcp_config.json",
                    "servers": len(mcp_config.get("mcpServers", {}))
                }
            else:
                return {"status": "skipped", "reason": "no MCP config"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def create_package(self, source_dir: Path, output_name: str = None) -> str:
        """Create backup zip package"""
        if output_name is None:
            output_name = f"claude_env_backup_{self.timestamp}"

        zip_path = self.output_dir / f"{output_name}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in source_dir.rglob("*"):
                if file.is_file():
                    arcname = file.relative_to(source_dir)
                    zf.write(file, arcname)

        return str(zip_path)

    def backup(self, create_zip: bool = True) -> dict:
        """Execute full backup"""
        print(f"[*] Claude Code Environment Backup Tool")
        print(f"[*] Claude Dir: {self.claude_dir}")
        print(f"[*] Output Dir: {self.output_dir.absolute()}")
        print("-" * 50)

        # Create temp backup dir
        backup_temp = self.output_dir / f"claude_backup_{self.timestamp}"
        backup_temp.mkdir(parents=True, exist_ok=True)

        results = {
            "timestamp": self.timestamp,
            "claude_dir": str(self.claude_dir),
            "backup_dir": str(backup_temp),
            "components": {}
        }

        # 1. Backup skills
        print("[1/4] Backing up skills...")
        results["components"]["skills"] = self.backup_skills(backup_temp)
        if results["components"]["skills"]["status"] == "success":
            print(f"      OK: {results['components']['skills']['total']} skills")
        else:
            print(f"      SKIP: {results['components']['skills'].get('reason', 'unknown')}")

        # 2. Backup output-styles
        print("[2/4] Backing up output-styles...")
        results["components"]["output_styles"] = self.backup_output_styles(backup_temp)
        if results["components"]["output_styles"]["status"] == "success":
            print(f"      OK: {results['components']['output_styles']['total']} styles")
        else:
            print(f"      SKIP: {results['components']['output_styles'].get('reason', 'unknown')}")

        # 3. Backup CLAUDE.md
        print("[3/4] Backing up CLAUDE.md...")
        results["components"]["claude_md"] = self.backup_claude_md(backup_temp)
        if results["components"]["claude_md"]["status"] == "success":
            print(f"      OK: CLAUDE.md")
        else:
            print(f"      SKIP: {results['components']['claude_md'].get('reason', 'unknown')}")

        # 4. Backup MCP config
        print("[4/4] Backing up MCP config...")
        results["components"]["mcp_config"] = self.backup_mcp_config(backup_temp)
        if results["components"]["mcp_config"]["status"] == "success":
            servers = results["components"]["mcp_config"].get("servers", 0)
            print(f"      OK: {servers} MCP servers")
        else:
            print(f"      SKIP: {results['components']['mcp_config'].get('reason', 'unknown')}")

        # 5. Save manifest
        manifest_path = backup_temp / "backup_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        # 6. Create package
        if create_zip:
            print("-" * 50)
            print("[PKG] Creating zip package...")
            zip_path = self.create_package(backup_temp)
            file_size = os.path.getsize(zip_path) / (1024 * 1024)
            print(f"      OK: {zip_path}")
            print(f"      SIZE: {file_size:.2f} MB")

            # Cleanup temp dir
            shutil.rmtree(backup_temp)
            results["zip_file"] = zip_path
            results["backup_dir"] = None
        else:
            results["backup_dir"] = str(backup_temp)
            print(f"[DIR] Backup dir: {backup_temp}")

        results["backup_record_path"] = str(zip_path if create_zip else backup_temp)

        return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Claude Code Environment Backup Tool")
    parser.add_argument("--claude-dir", help="Claude config directory path")
    parser.add_argument("--output-dir", help="Backup output directory")
    parser.add_argument("--no-zip", action="store_true", help="Keep directory, don't zip")

    args = parser.parse_args()

    backup = ClaudeEnvBackup(
        claude_dir=args.claude_dir,
        output_dir=args.output_dir
    )

    results = backup.backup(create_zip=not args.no_zip)

    # Save record
    record_path = Path(args.output_dir or ".") / f"backup_record_{backup.timestamp}.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[LOG] Backup record: {record_path}")


if __name__ == "__main__":
    main()

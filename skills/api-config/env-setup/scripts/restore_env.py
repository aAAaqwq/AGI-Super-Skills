#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Environment Restore Script
Restore all custom configs from backup
"""

import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Optional, List


class ClaudeEnvRestore:
    """Claude Code Environment Restore Tool"""

    def __init__(self, claude_dir: str = None):
        self.claude_dir = Path(claude_dir or self._get_default_claude_dir())

    def _get_default_claude_dir(self) -> Path:
        home = Path.home()
        if os.name == "nt":
            for possible in [home / ".claude", home / "AppData/Roaming/Claude"]:
                if possible.exists():
                    return possible
        return home / ".claude"

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def extract_backup(self, backup_path: str, extract_to: Path) -> Path:
        """Extract backup file"""
        backup_file = Path(backup_path)

        if backup_file.is_file() and backup_file.suffix == ".zip":
            print(f"[PKG] Extracting: {backup_file}")
            with zipfile.ZipFile(backup_file, "r") as zf:
                zf.extractall(extract_to)
            print(f"     OK: Extracted")

            extracted_items = list(extract_to.iterdir())
            if len(extracted_items) == 1:
                return extracted_items[0]
            return extract_to

        elif backup_file.is_dir():
            return backup_file
        else:
            raise ValueError(f"Invalid backup path: {backup_path}")

    def restore_skills(self, source_dir: Path, force: bool = False) -> dict:
        """Restore skills"""
        skills_dir = self.claude_dir / "skills"
        self._ensure_dir(skills_dir)

        restored = []
        skipped = []
        errors = []

        for item in source_dir.iterdir():
            if not item.is_dir():
                continue

            dest = skills_dir / item.name

            if item.name == "env-setup":
                skipped.append(f"{item.name} (self)")
                continue

            try:
                if dest.exists():
                    if not force:
                        skipped.append(f"{item.name} (exists)")
                        continue
                    shutil.rmtree(dest)

                shutil.copytree(item, dest)
                restored.append(item.name)

            except Exception as e:
                errors.append(f"{item.name}: {e}")

        return {
            "status": "success" if not errors else "partial",
            "restored": restored,
            "skipped": skipped,
            "errors": errors,
            "total": len(restored)
        }

    def restore_output_styles(self, source_dir: Path, force: bool = False) -> dict:
        """Restore output-styles"""
        styles_dir = self.claude_dir / "output-styles"
        self._ensure_dir(styles_dir)

        restored = []
        skipped = []
        errors = []

        for item in source_dir.glob("*.md"):
            dest = styles_dir / item.name

            try:
                if dest.exists() and not force:
                    skipped.append(item.name)
                    continue

                shutil.copy2(item, dest)
                restored.append(item.name)

            except Exception as e:
                errors.append(f"{item.name}: {e}")

        return {
            "status": "success" if not errors else "partial",
            "restored": restored,
            "skipped": skipped,
            "errors": errors,
            "total": len(restored)
        }

    def restore_claude_md(self, source_dir: Path, force: bool = False) -> dict:
        """Restore CLAUDE.md"""
        source = source_dir / "CLAUDE.md"
        dest = self.claude_dir / "CLAUDE.md"

        if not source.exists():
            return {"status": "skipped", "reason": "CLAUDE.md not in backup"}

        if dest.exists() and not force:
            return {"status": "skipped", "reason": "CLAUDE.md exists"}

        shutil.copy2(source, dest)
        return {"status": "success", "file": "CLAUDE.md"}

    def restore_mcp_config(self, source_dir: Path, force: bool = False) -> dict:
        """Restore MCP config (extract only, manual merge required)"""
        source = source_dir / "mcp_config.json"

        if not source.exists():
            return {"status": "skipped", "reason": "MCP config not in backup"}

        with open(source, "r", encoding="utf-8") as f:
            mcp_config = json.load(f)

        output_file = Path.home() / "mcp_config_restore.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(mcp_config, f, indent=2, ensure_ascii=False)

        return {
            "status": "info",
            "message": "MCP config extracted, manual merge required",
            "config_file": str(output_file),
            "servers": len(mcp_config.get("mcpServers", {}))
        }

    def restore(
        self,
        backup_path: str,
        force: bool = False,
        components: Optional[List[str]] = None
    ) -> dict:
        """Execute full restore"""
        print(f"[*] Claude Code Environment Restore Tool")
        print(f"[*] Claude Dir: {self.claude_dir}")
        print(f"[*] Backup: {backup_path}")
        print("-" * 50)

        if components is None:
            components = ["skills", "output_styles", "claude_md", "mcp_config"]

        temp_dir = Path.home() / ".claude_restore_temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()

        try:
            backup_dir = self.extract_backup(backup_path, temp_dir)

            # Read manifest
            manifest = backup_dir / "backup_manifest.json"
            if manifest.exists():
                with open(manifest, "r", encoding="utf-8") as f:
                    backup_info = json.load(f)
                print(f"[INFO] Backup Info:")
                print(f"       Time: {backup_info.get('timestamp', 'unknown')}")
                print(f"       Claude Dir: {backup_info.get('claude_dir', 'unknown')}")
            else:
                print(f"[WARN] No manifest found")

            results = {
                "backup_path": backup_path,
                "components": {}
            }

            # 1. Restore skills
            if "skills" in components:
                skills_src = backup_dir / "skills"
                if skills_src.exists():
                    print("[1/4] Restoring skills...")
                    results["components"]["skills"] = self.restore_skills(skills_src, force)
                    if results["components"]["skills"]["total"] > 0:
                        print(f"       OK: {results['components']['skills']['total']} skills")
                    if results["components"]["skills"]["skipped"]:
                        print(f"       SKIP: {len(results['components']['skills']['skipped'])}")
                else:
                    print(f"[WARN] No skills in backup")
                    results["components"]["skills"] = {"status": "skipped", "reason": "not in backup"}

            # 2. Restore output-styles
            if "output_styles" in components:
                styles_src = backup_dir / "output-styles"
                if styles_src.exists():
                    print("[2/4] Restoring output-styles...")
                    results["components"]["output_styles"] = self.restore_output_styles(styles_src, force)
                    if results["components"]["output_styles"]["total"] > 0:
                        print(f"       OK: {results['components']['output_styles']['total']} styles")
                else:
                    print(f"[WARN] No output-styles in backup")
                    results["components"]["output_styles"] = {"status": "skipped", "reason": "not in backup"}

            # 3. Restore CLAUDE.md
            if "claude_md" in components:
                print("[3/4] Restoring CLAUDE.md...")
                results["components"]["claude_md"] = self.restore_claude_md(backup_dir, force)
                if results["components"]["claude_md"]["status"] == "success":
                    print(f"       OK: CLAUDE.md")
                elif results["components"]["claude_md"]["status"] == "skipped":
                    print(f"       SKIP: {results['components']['claude_md']['reason']}")

            # 4. Restore MCP config
            if "mcp_config" in components:
                print("[4/4] Processing MCP config...")
                results["components"]["mcp_config"] = self.restore_mcp_config(backup_dir, force)
                if results["components"]["mcp_config"]["status"] == "info":
                    print(f"       INFO: {results['components']['mcp_config']['message']}")
                    print(f"       FILE: {results['components']['mcp_config']['config_file']}")

            print("-" * 50)
            print("[OK] Restore complete!")

            return results

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Claude Code Environment Restore Tool")
    parser.add_argument("backup", help="Backup file path (.zip or directory)")
    parser.add_argument("--claude-dir", help="Claude config directory path")
    parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing files")
    parser.add_argument(
        "--components",
        nargs="+",
        choices=["skills", "output_styles", "claude_md", "mcp_config"],
        help="Components to restore (default: all)"
    )

    args = parser.parse_args()

    restore = ClaudeEnvRestore(claude_dir=args.claude_dir)
    results = restore.restore(
        backup_path=args.backup,
        force=args.force,
        components=args.components
    )

    # Save record
    timestamp = Path(args.backup).stem.split("_")[-1] if "_backup_" in args.backup else "restore"
    record_path = Path.home() / f"restore_record_{timestamp}.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[LOG] Restore record: {record_path}")


if __name__ == "__main__":
    main()

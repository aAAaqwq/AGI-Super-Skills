#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Environment Sync Script
Sync all configs from GitHub repo to local Claude environment
"""

import json
import os
import shutil
from pathlib import Path


class ClaudeEnvSync:
    """Claude Code Environment Sync Tool"""

    def __init__(self, skill_dir: str = None, claude_dir: str = None):
        # Get skill directory (where this script is located)
        if skill_dir is None:
            skill_dir = Path(__file__).parent.parent
        else:
            skill_dir = Path(skill_dir)

        self.skill_dir = skill_dir
        self.config_dir = skill_dir / "config"

        # Get Claude directory
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

    def sync_output_styles(self, force: bool = False) -> dict:
        """Sync output-styles from config/output-styles/ to ~/.claude/output-styles/"""
        src_dir = self.config_dir / "output-styles"
        dst_dir = self.claude_dir / "output-styles"

        if not src_dir.exists():
            return {"status": "skipped", "reason": "config/output-styles not found"}

        self._ensure_dir(dst_dir)

        synced = []
        skipped = []

        for src_file in src_dir.glob("*.md"):
            dst_file = dst_dir / src_file.name

            try:
                if dst_file.exists() and not force:
                    skipped.append(src_file.name)
                    continue

                shutil.copy2(src_file, dst_file)
                synced.append(src_file.name)

            except Exception as e:
                skipped.append(f"{src_file.name}: {e}")

        return {
            "status": "success",
            "synced": synced,
            "skipped": skipped,
            "total": len(synced)
        }

    def sync_claude_md(self, force: bool = False) -> dict:
        """Sync CLAUDE.md from config/CLAUDE.md to ~/.claude/CLAUDE.md"""
        src_file = self.config_dir / "CLAUDE.md"
        dst_file = self.claude_dir / "CLAUDE.md"

        if not src_file.exists():
            return {"status": "skipped", "reason": "config/CLAUDE.md not found"}

        if dst_file.exists() and not force:
            return {"status": "skipped", "reason": "CLAUDE.md exists"}

        shutil.copy2(src_file, dst_file)
        return {"status": "success", "file": "CLAUDE.md"}

    def sync_mcp_config(self, merge: bool = True) -> dict:
        """
        Sync MCP config from config/mcp_config.json to ~/.claude.json

        Args:
            merge: True to merge with existing config, False to replace
        """
        src_file = self.config_dir / "mcp_config.json"

        if not src_file.exists():
            return {"status": "skipped", "reason": "config/mcp_config.json not found"}

        # Find .claude.json
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

        # Read source MCP config
        with open(src_file, "r", encoding="utf-8") as f:
            mcp_config = json.load(f)

        # Read existing config
        with open(config_path, "r", encoding="utf-8") as f:
            existing_config = json.load(f)

        # Merge or replace
        if merge:
            # Merge mcpServers
            if "mcpServers" in mcp_config:
                if "mcpServers" not in existing_config:
                    existing_config["mcpServers"] = {}
                existing_config["mcpServers"].update(mcp_config["mcpServers"])

            # Merge allowedTools (MCP tools)
            if "allowedTools" in mcp_config:
                if "allowedTools" not in existing_config:
                    existing_config["allowedTools"] = []

                # Add new MCP tools
                existing_tools = set(existing_config["allowedTools"])
                for tool in mcp_config["allowedTools"]:
                    if tool.startswith("mcp__"):
                        existing_tools.add(tool)

                existing_config["allowedTools"] = list(existing_tools)

        else:
            # Replace MCP config
            if "mcpServers" in mcp_config:
                existing_config["mcpServers"] = mcp_config["mcpServers"]

        # Write back
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(existing_config, f, indent=2, ensure_ascii=False)

        servers_count = len(existing_config.get("mcpServers", {}))
        mcp_tools = len([t for t in existing_config.get("allowedTools", []) if t.startswith("mcp__")])

        return {
            "status": "success",
            "mode": "merge" if merge else "replace",
            "mcp_servers": servers_count,
            "mcp_tools": mcp_tools
        }

    def sync(
        self,
        force: bool = False,
        components: list = None
    ) -> dict:
        """
        Execute full sync

        Args:
            force: Overwrite existing files
            components: List of components to sync (default: all)
                       Options: ["output_styles", "claude_md", "mcp_config"]

        Returns:
            Sync results
        """
        print(f"[*] Claude Code Environment Sync Tool")
        print(f"[*] Skill Dir: {self.skill_dir}")
        print(f"[*] Config Dir: {self.config_dir}")
        print(f"[*] Claude Dir: {self.claude_dir}")
        print("-" * 50)

        if components is None:
            components = ["output_styles", "claude_md", "mcp_config"]

        results = {
            "skill_dir": str(self.skill_dir),
            "claude_dir": str(self.claude_dir),
            "components": {}
        }

        # 1. Sync output-styles
        if "output_styles" in components:
            print("[1/3] Syncing output-styles...")
            results["components"]["output_styles"] = self.sync_output_styles(force)
            if results["components"]["output_styles"]["total"] > 0:
                print(f"      OK: {results['components']['output_styles']['total']} styles synced")
            if results["components"]["output_styles"]["skipped"]:
                print(f"      SKIP: {len(results['components']['output_styles']['skipped'])}")
            else:
                print(f"      SKIP: {results['components']['output_styles'].get('reason', 'unknown')}")

        # 2. Sync CLAUDE.md
        if "claude_md" in components:
            print("[2/3] Syncing CLAUDE.md...")
            results["components"]["claude_md"] = self.sync_claude_md(force)
            if results["components"]["claude_md"]["status"] == "success":
                print(f"      OK: CLAUDE.md synced")
            else:
                print(f"      SKIP: {results['components']['claude_md'].get('reason', 'unknown')}")

        # 3. Sync MCP config
        if "mcp_config" in components:
            print("[3/3] Syncing MCP config...")
            results["components"]["mcp_config"] = self.sync_mcp_config(merge=True)
            if results["components"]["mcp_config"]["status"] == "success":
                print(f"      OK: {results['components']['mcp_config']['mcp_servers']} servers, "
                      f"{results['components']['mcp_config']['mcp_tools']} tools")
            else:
                print(f"      SKIP: {results['components']['mcp_config'].get('reason', 'unknown')}")

        print("-" * 50)
        print("[OK] Sync complete!")
        print("\n[INFO] Please restart Claude Code to apply changes.")

        return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Claude Code Environment Sync Tool")
    parser.add_argument("--skill-dir", help="Skill directory (default: auto-detect)")
    parser.add_argument("--claude-dir", help="Claude config directory")
    parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing files")
    parser.add_argument(
        "--components",
        nargs="+",
        choices=["output_styles", "claude_md", "mcp_config"],
        help="Components to sync (default: all)"
    )

    args = parser.parse_args()

    syncer = ClaudeEnvSync(
        skill_dir=args.skill_dir,
        claude_dir=args.claude_dir
    )

    results = syncer.sync(force=args.force, components=args.components)

    # Save record
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    record_path = Path.home() / f"sync_record_{timestamp}.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[LOG] Sync record: {record_path}")


if __name__ == "__main__":
    main()

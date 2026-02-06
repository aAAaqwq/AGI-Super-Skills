#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AGI Environment Sync Script
Sync all configs from GitHub repo to local AI development environments
Supports: Claude Code, OpenClaw, Codex CLI, Pi Coding Agent
"""

import json
import os
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Optional


class AGIEnvSync:
    """AGI Environment Sync Tool - Multi-platform support"""

    # Platform configurations
    PLATFORMS = {
        "claude": {
            "name": "Claude Code",
            "skills_dir": "~/.claude/skills",
            "config_file": "~/.claude.json",
            "prompts_file": "~/.claude/CLAUDE.md",
            "output_styles_dir": "~/.claude/output-styles",
            "mcp_key": "mcpServers",
        },
        "openclaw": {
            "name": "OpenClaw",
            "skills_dir": "~/clawd/skills",
            "config_file": "~/.openclaw/openclaw.json",
            "prompts_file": "~/clawd/AGENTS.md",
            "prompts_extra": ["~/clawd/SOUL.md", "~/clawd/IDENTITY.md", "~/clawd/USER.md"],
            "output_styles_dir": None,  # Not supported
            "mcp_key": "mcp",
        },
        "codex": {
            "name": "Codex CLI",
            "skills_dir": "~/.codex/skills",
            "config_file": "~/.codex/config.json",
            "prompts_file": "~/.codex/AGENTS.md",
            "output_styles_dir": None,
            "mcp_key": "mcpServers",
        },
        "pi": {
            "name": "Pi Coding Agent",
            "skills_dir": "~/.pi/skills",
            "config_file": "~/.pi/config.json",
            "prompts_file": "~/.pi/AGENTS.md",
            "output_styles_dir": None,
            "mcp_key": "mcpServers",
        },
    }

    def __init__(self, repo_dir: str = None):
        """Initialize with repository directory"""
        if repo_dir is None:
            # Auto-detect: script is in env-setup/scripts/
            repo_dir = Path(__file__).parent.parent.parent
        else:
            repo_dir = Path(repo_dir)

        self.repo_dir = repo_dir
        self.config_dir = repo_dir / "config"

    def _expand_path(self, path: str) -> Path:
        """Expand ~ and environment variables in path"""
        return Path(os.path.expanduser(os.path.expandvars(path)))

    def _ensure_dir(self, path: Path) -> None:
        """Create directory if not exists"""
        path.mkdir(parents=True, exist_ok=True)

    def detect_platforms(self) -> Dict[str, bool]:
        """Detect which platforms are installed"""
        results = {}
        for platform_id, config in self.PLATFORMS.items():
            # Check if config file or skills dir exists
            config_path = self._expand_path(config["config_file"])
            skills_path = self._expand_path(config["skills_dir"])
            results[platform_id] = config_path.exists() or skills_path.parent.exists()
        return results

    def sync_skills(self, target: str, force: bool = False, 
                    include: List[str] = None, exclude: List[str] = None) -> dict:
        """Sync skills to target platform"""
        if target not in self.PLATFORMS:
            return {"status": "error", "reason": f"Unknown platform: {target}"}

        platform = self.PLATFORMS[target]
        dst_dir = self._expand_path(platform["skills_dir"])

        # Get list of skills to sync
        skills_to_sync = []
        for item in self.repo_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # Check SKILL.md exists
                if (item / "SKILL.md").exists():
                    skill_name = item.name
                    
                    # Apply include/exclude filters
                    if include and skill_name not in include:
                        continue
                    if exclude and skill_name in exclude:
                        continue
                    
                    skills_to_sync.append(skill_name)

        self._ensure_dir(dst_dir)

        synced = []
        skipped = []

        for skill_name in skills_to_sync:
            src_skill = self.repo_dir / skill_name
            dst_skill = dst_dir / skill_name

            try:
                if dst_skill.exists():
                    if force:
                        shutil.rmtree(dst_skill)
                    else:
                        skipped.append(skill_name)
                        continue

                shutil.copytree(src_skill, dst_skill)
                synced.append(skill_name)

            except Exception as e:
                skipped.append(f"{skill_name}: {e}")

        return {
            "status": "success",
            "platform": platform["name"],
            "synced": synced,
            "skipped": skipped,
            "total": len(synced),
        }

    def sync_output_styles(self, target: str, force: bool = False) -> dict:
        """Sync output styles (Claude Code only)"""
        if target not in self.PLATFORMS:
            return {"status": "error", "reason": f"Unknown platform: {target}"}

        platform = self.PLATFORMS[target]
        if not platform.get("output_styles_dir"):
            return {"status": "skipped", "reason": f"{platform['name']} doesn't support output styles"}

        src_dir = self.config_dir / "output-styles"
        dst_dir = self._expand_path(platform["output_styles_dir"])

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
            "total": len(synced),
        }

    def sync_prompts(self, target: str, force: bool = False) -> dict:
        """Sync global prompts (CLAUDE.md / AGENTS.md)"""
        if target not in self.PLATFORMS:
            return {"status": "error", "reason": f"Unknown platform: {target}"}

        platform = self.PLATFORMS[target]
        dst_file = self._expand_path(platform["prompts_file"])

        # Determine source file
        if target == "claude":
            src_file = self.config_dir / "CLAUDE.md"
        else:
            src_file = self.config_dir / "AGENTS.md"

        if not src_file.exists():
            return {"status": "skipped", "reason": f"{src_file.name} not found"}

        if dst_file.exists() and not force:
            return {"status": "skipped", "reason": f"{dst_file.name} exists"}

        self._ensure_dir(dst_file.parent)
        shutil.copy2(src_file, dst_file)

        # Copy extra prompts for OpenClaw
        extra_synced = []
        if "prompts_extra" in platform:
            for extra_name in ["SOUL.md", "IDENTITY.md", "USER.md", "TOOLS.md"]:
                extra_src = self.config_dir / extra_name
                if extra_src.exists():
                    extra_dst = dst_file.parent / extra_name
                    if not extra_dst.exists() or force:
                        shutil.copy2(extra_src, extra_dst)
                        extra_synced.append(extra_name)

        return {
            "status": "success",
            "file": dst_file.name,
            "extra": extra_synced,
        }

    def sync_mcp_config(self, target: str, merge: bool = True) -> dict:
        """Sync MCP configuration"""
        if target not in self.PLATFORMS:
            return {"status": "error", "reason": f"Unknown platform: {target}"}

        platform = self.PLATFORMS[target]
        src_file = self.config_dir / "mcp_config.json"

        if not src_file.exists():
            return {"status": "skipped", "reason": "config/mcp_config.json not found"}

        config_path = self._expand_path(platform["config_file"])

        if not config_path.exists():
            return {"status": "skipped", "reason": f"{config_path} not found"}

        # Read source MCP config
        with open(src_file, "r", encoding="utf-8") as f:
            mcp_config = json.load(f)

        # Read existing config
        with open(config_path, "r", encoding="utf-8") as f:
            existing_config = json.load(f)

        mcp_key = platform["mcp_key"]

        if merge:
            # Merge MCP servers
            if "mcpServers" in mcp_config:
                if mcp_key not in existing_config:
                    existing_config[mcp_key] = {}
                
                # Handle different config structures
                if mcp_key == "mcp":
                    # OpenClaw uses nested structure
                    if "servers" not in existing_config[mcp_key]:
                        existing_config[mcp_key]["servers"] = {}
                    existing_config[mcp_key]["servers"].update(mcp_config["mcpServers"])
                else:
                    existing_config[mcp_key].update(mcp_config["mcpServers"])

            # Merge allowedTools
            if "allowedTools" in mcp_config:
                if "allowedTools" not in existing_config:
                    existing_config["allowedTools"] = []

                existing_tools = set(existing_config["allowedTools"])
                for tool in mcp_config["allowedTools"]:
                    if tool.startswith("mcp__"):
                        existing_tools.add(tool)

                existing_config["allowedTools"] = list(existing_tools)
        else:
            # Replace
            if "mcpServers" in mcp_config:
                if mcp_key == "mcp":
                    existing_config[mcp_key] = {"servers": mcp_config["mcpServers"]}
                else:
                    existing_config[mcp_key] = mcp_config["mcpServers"]

        # Write back
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(existing_config, f, indent=2, ensure_ascii=False)

        # Count servers
        if mcp_key == "mcp":
            servers_count = len(existing_config.get(mcp_key, {}).get("servers", {}))
        else:
            servers_count = len(existing_config.get(mcp_key, {}))

        return {
            "status": "success",
            "platform": platform["name"],
            "mode": "merge" if merge else "replace",
            "mcp_servers": servers_count,
        }

    def sync(
        self,
        targets: List[str] = None,
        force: bool = False,
        components: List[str] = None,
        include_skills: List[str] = None,
        exclude_skills: List[str] = None,
        verbose: bool = False,
    ) -> dict:
        """
        Execute full sync

        Args:
            targets: List of platforms to sync (default: all detected)
            force: Overwrite existing files
            components: List of components to sync (default: all)
            include_skills: Only sync these skills
            exclude_skills: Exclude these skills
            verbose: Show detailed output

        Returns:
            Sync results
        """
        print("=" * 60)
        print("  AGI Environment Sync Tool")
        print("=" * 60)
        print(f"  Repository: {self.repo_dir}")
        print(f"  Config Dir: {self.config_dir}")
        print("-" * 60)

        # Detect platforms
        detected = self.detect_platforms()
        print("\n  Platform Detection:")
        for platform_id, installed in detected.items():
            status = "✅" if installed else "❌"
            print(f"    {status} {self.PLATFORMS[platform_id]['name']}")

        # Determine targets
        if targets is None or "all" in targets:
            targets = [p for p, installed in detected.items() if installed]

        if not targets:
            print("\n  ❌ No platforms detected!")
            return {"status": "error", "reason": "No platforms detected"}

        print(f"\n  Sync Targets: {', '.join(targets)}")

        if components is None:
            components = ["skills", "output_styles", "prompts", "mcp_config"]

        results = {
            "repo_dir": str(self.repo_dir),
            "targets": targets,
            "platforms": {},
        }

        for target in targets:
            print(f"\n{'=' * 60}")
            print(f"  Syncing to {self.PLATFORMS[target]['name']}")
            print("=" * 60)

            platform_results = {}

            # 1. Sync skills
            if "skills" in components:
                print("\n  [1/4] Syncing skills...")
                result = self.sync_skills(target, force, include_skills, exclude_skills)
                platform_results["skills"] = result
                if result["status"] == "success":
                    print(f"        ✅ {result['total']} skills synced")
                    if result["skipped"] and verbose:
                        print(f"        ⏭️  Skipped: {len(result['skipped'])}")
                else:
                    print(f"        ⏭️  {result.get('reason', 'skipped')}")

            # 2. Sync output styles
            if "output_styles" in components:
                print("\n  [2/4] Syncing output styles...")
                result = self.sync_output_styles(target, force)
                platform_results["output_styles"] = result
                if result["status"] == "success":
                    print(f"        ✅ {result['total']} styles synced")
                else:
                    print(f"        ⏭️  {result.get('reason', 'skipped')}")

            # 3. Sync prompts
            if "prompts" in components:
                print("\n  [3/4] Syncing global prompts...")
                result = self.sync_prompts(target, force)
                platform_results["prompts"] = result
                if result["status"] == "success":
                    print(f"        ✅ {result['file']} synced")
                    if result.get("extra"):
                        print(f"        ✅ Extra: {', '.join(result['extra'])}")
                else:
                    print(f"        ⏭️  {result.get('reason', 'skipped')}")

            # 4. Sync MCP config
            if "mcp_config" in components:
                print("\n  [4/4] Syncing MCP config...")
                result = self.sync_mcp_config(target, merge=True)
                platform_results["mcp_config"] = result
                if result["status"] == "success":
                    print(f"        ✅ {result['mcp_servers']} MCP servers")
                else:
                    print(f"        ⏭️  {result.get('reason', 'skipped')}")

            results["platforms"][target] = platform_results

        print("\n" + "=" * 60)
        print("  ✅ Sync Complete!")
        print("=" * 60)
        print("\n  ⚠️  Please restart your IDE/Agent to apply changes.")

        return results


def main():
    parser = argparse.ArgumentParser(
        description="AGI Environment Sync Tool - Multi-platform support"
    )
    parser.add_argument(
        "--repo-dir",
        help="Repository directory (default: auto-detect)"
    )
    parser.add_argument(
        "--target", "-t",
        nargs="+",
        choices=["claude", "openclaw", "codex", "pi", "all"],
        default=["all"],
        help="Target platforms (default: all detected)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing files"
    )
    parser.add_argument(
        "--components", "-c",
        nargs="+",
        choices=["skills", "output_styles", "prompts", "mcp_config"],
        help="Components to sync (default: all)"
    )
    parser.add_argument(
        "--include",
        nargs="+",
        help="Only sync these skills"
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        help="Exclude these skills"
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Only detect platforms, don't sync"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )

    args = parser.parse_args()

    syncer = AGIEnvSync(repo_dir=args.repo_dir)

    if args.detect:
        print("Detecting platforms...")
        detected = syncer.detect_platforms()
        for platform_id, installed in detected.items():
            status = "✅" if installed else "❌"
            print(f"  {status} {syncer.PLATFORMS[platform_id]['name']}")
        return

    results = syncer.sync(
        targets=args.target,
        force=args.force,
        components=args.components,
        include_skills=args.include,
        exclude_skills=args.exclude,
        verbose=args.verbose,
    )

    # Save record
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    record_path = Path.home() / f".agi_sync_record_{timestamp}.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  📝 Sync record: {record_path}")


if __name__ == "__main__":
    main()

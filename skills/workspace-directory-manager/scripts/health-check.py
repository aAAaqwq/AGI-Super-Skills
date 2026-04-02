#!/usr/bin/env python3
"""Workspace & OpenClaw Directory Health Check."""

import os, time, json
from pathlib import Path
from collections import defaultdict

CLAWD = os.path.expanduser("~/clawd")
OPENCLAW = os.path.expanduser("~/.openclaw")

def get_size(path):
    """Get file or directory size in bytes."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total += os.path.getsize(fp)
    return total

def format_size(bytes_size):
    if bytes_size < 1024:
        return f"{bytes_size}B"
    elif bytes_size < 1024**2:
        return f"{bytes_size/1024:.1f}KB"
    elif bytes_size < 1024**3:
        return f"{bytes_size/1024**2:.1f}MB"
    else:
        return f"{bytes_size/1024**3:.1f}GB"

def check_file_age(path, days):
    """Check if file is older than N days."""
    if not os.path.exists(path):
        return False
    mtime = os.path.getmtime(path)
    return (time.time() - mtime) > days * 86400

def main():
    issues = []
    stats = {}
    
    print("=" * 70)
    print("🏠 Workspace & OpenClaw Directory Health Check")
    print("=" * 70)
    
    # 1. Core files check
    print("\n📄 Core Files:")
    core_files = {
        "MEMORY.md": f"{CLAWD}/MEMORY.md",
        "SOUL.md": f"{CLAWD}/SOUL.md",
        "AGENTS.md": f"{CLAWD}/AGENTS.md",
        "USER.md": f"{CLAWD}/USER.md",
        "TOOLS.md": f"{CLAWD}/TOOLS.md",
        "IDENTITY.md": f"{CLAWD}/IDENTITY.md",
        "HEARTBEAT.md": f"{CLAWD}/HEARTBEAT.md",
    }
    for name, path in core_files.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            mtime = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))
            print(f"  ✅ {name:15s} {format_size(size):>8s}  modified: {mtime}")
        else:
            print(f"  ❌ {name:15s} MISSING")
            issues.append(f"Core file missing: {name}")
    
    # 2. openclaw.json check
    print(f"\n⚙️ OpenClaw Config:")
    config_path = f"{OPENCLAW}/openclaw.json"
    if os.path.exists(config_path):
        size = os.path.getsize(config_path)
        print(f"  ✅ openclaw.json  {format_size(size)}")
        # Check for hardcoded keys
        with open(config_path) as f:
            content = f.read()
        hardcoded = len(content.split("sk-")) - 1  # rough check
        if hardcoded > 5:
            print(f"  ⚠️ {hardcoded} potential hardcoded keys detected")
            issues.append(f"openclaw.json: {hardcoded} potential hardcoded keys")
    else:
        print(f"  ❌ openclaw.json MISSING")
    
    # 3. .env check
    env_path = f"{OPENCLAW}/.env"
    if os.path.exists(env_path):
        perm = oct(os.stat(env_path).st_mode)[-3:]
        print(f"  ✅ .env  permissions={perm}")
        if perm != "600":
            issues.append(f".env permissions too open: {perm} (should be 600)")
    else:
        print(f"  ⚠️ .env MISSING (rebuild-env.sh needed)")
    
    # 4. Agent configs check
    print(f"\n🤖 Agent Configs:")
    agents_dir = f"{OPENCLAW}/agents"
    if os.path.exists(agents_dir):
        agent_count = 0
        for agent_id in sorted(os.listdir(agents_dir)):
            agent_path = os.path.join(agents_dir, agent_id, "agent")
            if os.path.isdir(agent_path):
                agent_count += 1
                files = os.listdir(agent_path)
                has_json = "agent.json" in files
                has_soul = "SOUL.md" in files
                models_path = os.path.join(agent_path, "models.json")
                models_size = os.path.getsize(models_path) if os.path.exists(models_path) else 0
                status = "✅" if has_json else "❌"
                models_warn = " ⚠️large" if models_size > 10*1024*1024 else ""
                print(f"  {status} {agent_id:12s} agent.json={'✅' if has_json else '❌'}  SOUL={'✅' if has_soul else '—'}  models={format_size(models_size)}{models_warn}")
                if models_size > 10*1024*1024:
                    issues.append(f"{agent_id}: models.json too large ({format_size(models_size)})")
        print(f"  Total: {agent_count} agents")
    
    # 5. Skills check
    print(f"\n🔧 Skills:")
    for skills_dir, label in [
        (f"{OPENCLAW}/skills", "Global (openclaw)"),
        (f"{CLAWD}/skills", "Workspace (clawd)")
    ]:
        if os.path.exists(skills_dir):
            skill_count = 0
            skill_names = []
            for entry in sorted(os.listdir(skills_dir)):
                skill_path = os.path.join(skills_dir, entry)
                if os.path.isdir(skill_path):
                    has_skill_md = os.path.exists(os.path.join(skill_path, "SKILL.md"))
                    if has_skill_md:
                        skill_count += 1
                        skill_names.append(entry)
            print(f"  {label}: {skill_count} skills")
            stats[f"skills_{label}"] = skill_count
    
    # 6. Memory files check
    print(f"\n🧠 Memory:")
    memory_dir = f"{CLAWD}/memory"
    if os.path.exists(memory_dir):
        mem_files = sorted([f for f in os.listdir(memory_dir) if f.endswith(".md")])
        today = time.strftime("%Y-%m-%d")
        has_today = f"{today}.md" in mem_files
        print(f"  Total: {len(mem_files)} daily memory files")
        print(f"  Today ({today}): {'✅' if has_today else '❌'}")
        if not has_today:
            issues.append("No daily memory file for today")
        
        # Check MEMORY.md age
        memory_md = f"{CLAWD}/MEMORY.md"
        if os.path.exists(memory_md):
            age_days = (time.time() - os.path.getmtime(memory_md)) / 86400
            if age_days > 3:
                issues.append(f"MEMORY.md not updated in {age_days:.0f} days")
    
    # 7. Tmp files
    print(f"\n🗑️ Temporary Files:")
    tmp_dir = f"{CLAWD}/tmp"
    if os.path.exists(tmp_dir):
        tmp_files = []
        old_files = 0
        for f in os.listdir(tmp_dir):
            fp = os.path.join(tmp_dir, f)
            if os.path.isfile(fp):
                tmp_files.append(f)
                if check_file_age(fp, 7):
                    old_files += 1
        total_size = sum(os.path.getsize(os.path.join(tmp_dir, f)) for f in tmp_files)
        print(f"  Files: {len(tmp_files)}  Size: {format_size(total_size)}")
        print(f"  Older than 7 days: {old_files}")
        if old_files > 20:
            issues.append(f"tmp/: {old_files} files older than 7 days")
    
    # 8. Disk usage summary
    print(f"\n💾 Disk Usage:")
    for label, path in [("~/clawd", CLAWD), ("~/.openclaw", OPENCLAW)]:
        if os.path.exists(path):
            size = get_size(path)
            print(f"  {label:20s} {format_size(size)}")
    
    # Summary
    print(f"\n{'=' * 70}")
    if issues:
        print(f"🔴 Issues: {len(issues)}")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print("✅ All checks passed — workspace healthy")

if __name__ == "__main__":
    main()

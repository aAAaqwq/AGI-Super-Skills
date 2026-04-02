#!/usr/bin/env python3
"""Detect duplicate skills across ~/.openclaw/skills/ and ~/clawd/skills/."""

import os, hashlib

OPENCLAW_SKILLS = os.path.expanduser("~/.openclaw/skills")
CLAWD_SKILLS = os.path.expanduser("~/clawd/skills")

def get_skill_hash(skill_path):
    """Get hash of SKILL.md content for comparison."""
    sk_md = os.path.join(skill_path, "SKILL.md")
    if os.path.exists(sk_md):
        with open(sk_md) as f:
            return hashlib.md5(f.read().encode()).hexdigest()[:8]
    return None

def get_skill_name(path):
    """Extract skill name from SKILL.md first line or directory name."""
    sk_md = os.path.join(path, "SKILL.md")
    if os.path.exists(sk_md):
        with open(sk_md) as f:
            for line in f:
                if line.startswith("# "):
                    return line[2:].strip()
    return os.path.basename(path)

def main():
    print("=" * 70)
    print("🔍 Duplicate Skill Detection")
    print("=" * 70)
    
    # Collect all skills
    skills = {}  # name -> [(source, path, hash)]
    
    for base, label in [(OPENCLAW_SKILLS, "openclaw"), (CLAWD_SKILLS, "clawd")]:
        if not os.path.exists(base):
            continue
        for entry in sorted(os.listdir(base)):
            skill_path = os.path.join(base, entry)
            if os.path.isdir(skill_path) and os.path.exists(os.path.join(skill_path, "SKILL.md")):
                name = get_skill_name(skill_path)
                h = get_skill_hash(skill_path)
                if name not in skills:
                    skills[name] = []
                skills[name].append((label, skill_path, h))
    
    # Find duplicates
    exact_dups = []
    partial_dups = []
    
    for name, locations in sorted(skills.items()):
        if len(locations) > 1:
            # Check if content is identical
            hashes = set(h for _, _, h in locations if h)
            if len(hashes) == 1:
                exact_dups.append((name, locations))
            else:
                partial_dups.append((name, locations))
    
    # Also check by directory name
    dir_names = {}
    for base, label in [(OPENCLAW_SKILLS, "openclaw"), (CLAWD_SKILLS, "clawd")]:
        if not os.path.exists(base):
            continue
        for entry in sorted(os.listdir(base)):
            if os.path.isdir(os.path.join(base, entry, "SKILL.md")):
                dir_names.setdefault(entry, []).append(label)
    
    name_dups = {k: v for k, v in dir_names.items() if len(v) > 1}
    
    # Report
    print(f"\n📊 Summary:")
    all_skills = set()
    for locations in skills.values():
        for _, path, _ in locations:
            all_skills.add(os.path.basename(path))
    print(f"  Total unique skill directories: {len(all_skills)}")
    print(f"  By name: {len(skills)}")
    
    if exact_dups:
        print(f"\n🔴 Exact Duplicates ({len(exact_dups)}):")
        for name, locs in exact_dups:
            print(f"  ⚠️ \"{name}\"")
            for label, path, h in locs:
                print(f"    {label:10s}: {path}")
    
    if name_dups:
        print(f"\n🟡 Same Directory Name ({len(name_dups)}):")
        for name, sources in name_dups.items():
            print(f"  ⚠️ {name}/ exists in: {', '.join(sources)}")
    
    if partial_dups:
        print(f"\n🟡 Partial Duplicates (same name, different content) ({len(partial_dups)}):")
        for name, locs in partial_dups:
            print(f"  ⚠️ \"{name}\"")
            for label, path, h in locs:
                print(f"    {label:10s}: {path} (hash={h})")
    
    if not exact_dups and not name_dups and not partial_dups:
        print("\n✅ No duplicates found")

if __name__ == "__main__":
    main()

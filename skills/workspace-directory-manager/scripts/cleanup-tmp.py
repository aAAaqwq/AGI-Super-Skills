#!/usr/bin/env python3
"""Cleanup temporary files in ~/clawd/tmp/ and ~/.openclaw/logs/."""

import os, sys, time, subprocess
from datetime import datetime

CLAWD_TMP = os.path.expanduser("~/clawd/tmp")
OPENCLAW_LOGS = os.path.expanduser("~/.openclaw/logs")
CLAWD_MEMORY = os.path.expanduser("~/clawd/memory")

DEFAULT_MAX_AGE_DAYS = 7
LOG_MAX_AGE_DAYS = 30

def format_size(bytes_size):
    if bytes_size < 1024: return f"{bytes_size}B"
    elif bytes_size < 1024**2: return f"{bytes_size/1024:.1f}KB"
    elif bytes_size < 1024**3: return f"{bytes_size/1024**2:.1f}MB"
    else: return f"{bytes_size/1024**3:.1f}GB"

def cleanup_dir(path, max_age_days, dry_run=True, label=""):
    """Delete files older than max_age_days in directory."""
    if not os.path.exists(path):
        print(f"  {label}: directory not found")
        return 0, 0
    
    deleted_count = 0
    freed_bytes = 0
    now = time.time()
    
    for entry in sorted(os.listdir(path)):
        fp = os.path.join(path, entry)
        if not os.path.isfile(fp):
            continue
        
        age_days = (now - os.path.getmtime(fp)) / 86400
        if age_days > max_age_days:
            size = os.path.getsize(fp)
            mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d")
            print(f"  🗑️ {entry} ({format_size(size)}, {mtime}, {age_days:.0f}d old)")
            
            if not dry_run:
                subprocess.run(["trash", fp], capture_output=True, timeout=5)
            
            deleted_count += 1
            freed_bytes += size
    
    return deleted_count, freed_bytes

def main():
    dry_run = "--execute" not in sys.argv
    max_age = DEFAULT_MAX_AGE_DAYS
    
    for arg in sys.argv[1:]:
        if arg.startswith("--days="):
            max_age = int(arg.split("=")[1])
    
    mode = "DRY RUN" if dry_run else "EXECUTE"
    print(f"🧹 Cleanup {mode} (max age: {max_age} days)")
    print("=" * 50)
    
    total_deleted = 0
    total_freed = 0
    
    # 1. tmp/ files
    print(f"\n📁 ~/clawd/tmp/")
    c, b = cleanup_dir(CLAWD_TMP, max_age, dry_run, "tmp")
    total_deleted += c
    total_freed += b
    
    # 2. logs/ files
    print(f"\n📁 ~/.openclaw/logs/ ({LOG_MAX_AGE_DAYS} days)")
    c, b = cleanup_dir(OPENCLAW_LOGS, LOG_MAX_AGE_DAYS, dry_run, "logs")
    total_deleted += c
    total_freed += b
    
    # 3. Memory files older than 90 days
    print(f"\n📁 ~/clawd/memory/ (90 days)")
    c, b = cleanup_dir(CLAWD_MEMORY, 90, dry_run, "memory")
    total_deleted += c
    total_freed += b
    
    print(f"\n{'=' * 50}")
    print(f"Total: {total_deleted} files, {format_size(total_freed)} freed")
    
    if dry_run and total_deleted > 0:
        print(f"\n💡 Run with --execute to actually delete (uses trash, not rm)")

if __name__ == "__main__":
    main()

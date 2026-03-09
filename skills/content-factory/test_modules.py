#!/usr/bin/env python3
"""
test_modules.py — Verify all Content Factory modules can be imported
and core paths resolve correctly.
"""
import sys
import os

# Ensure scripts/ is on path
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts", "aggregator"))

passed = 0
failed = 0
errors = []

def check(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✅ {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        errors.append((name, str(e)))
        failed += 1

print("🧪 Content Factory Module Tests\n")

# 1. paths module
print("--- paths ---")
check("import paths", lambda: __import__("paths"))
def verify_paths():
    from paths import SKILL_DIR, HOTPOOL_DIR, TOPICS_DIR, DRAFTS_DIR, TEMPLATES_DIR, FETCH_ALL
    assert SKILL_DIR.exists(), f"SKILL_DIR not found: {SKILL_DIR}"
    assert HOTPOOL_DIR.exists(), f"HOTPOOL_DIR not found: {HOTPOOL_DIR}"
    assert FETCH_ALL.exists(), f"FETCH_ALL not found: {FETCH_ALL}"
check("paths resolve correctly", verify_paths)

# 2. aggregator
print("\n--- aggregator ---")
def import_aggregator():
    old_cwd = os.getcwd()
    os.chdir(os.path.join(SKILL_DIR, "scripts", "aggregator"))
    import fetch_all
    os.chdir(old_cwd)
check("import fetch_all (aggregator)", import_aggregator)

# 3. topic_scorer
print("\n--- topic_scorer ---")
def import_scorer():
    os.chdir(os.path.join(SKILL_DIR, "scripts"))
    import topic_scorer
check("import topic_scorer", import_scorer)

# 4. content_generator
print("\n--- content_generator ---")
def import_generator():
    import content_generator
check("import content_generator", import_generator)

# 5. topic_presenter
print("\n--- topic_presenter ---")
def import_presenter():
    import topic_presenter
check("import topic_presenter", import_presenter)

# 6. draft_reviewer
print("\n--- draft_reviewer ---")
def import_reviewer():
    import draft_reviewer
check("import draft_reviewer", import_reviewer)

# 7. auto_publisher
print("\n--- auto_publisher ---")
def import_publisher():
    import auto_publisher
check("import auto_publisher", import_publisher)

# 8. templates exist
print("\n--- templates ---")
def verify_templates():
    from paths import TEMPLATES_DIR
    for t in ["xiaohongshu.md", "wechat.md", "twitter.md"]:
        assert (TEMPLATES_DIR / t).exists(), f"template missing: {t}"
check("platform templates present", verify_templates)

# 9. config.json
print("\n--- config ---")
def verify_config():
    import json
    config_path = os.path.join(SKILL_DIR, "scripts", "aggregator", "config.json")
    with open(config_path) as f:
        cfg = json.load(f)
    assert len(cfg) > 0, "config is empty"
check("aggregator config.json valid", verify_config)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if errors:
    print("\nFailed:")
    for name, err in errors:
        print(f"  - {name}: {err}")
    sys.exit(1)
else:
    print("🎉 All modules OK!")
    sys.exit(0)

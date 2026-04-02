#!/usr/bin/env python3
"""Key Audit — check all provider keys: existence, format, hardcoded vs env."""

import json, subprocess, os, re

CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")
ENV_PATH = os.path.expanduser("~/.openclaw/.env")

def check_pass(name):
    """Check if a pass entry exists."""
    try:
        result = subprocess.run(["pass", "show", name], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def check_env(var_name):
    """Check if env var is set in .env."""
    if not os.path.exists(ENV_PATH):
        return False
    with open(ENV_PATH) as f:
        for line in f:
            if line.strip().startswith(f"{var_name}=") and len(line.strip()) > len(var_name) + 2:
                return True
    return False

def resolve_env_ref(key_ref):
    """Extract env var name from ${VAR_NAME}."""
    if key_ref and key_ref.startswith("${"):
        return key_ref.strip("${}").split("}")[0]
    return None

def main():
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    
    providers = cfg.get("models", {}).get("providers", {})
    
    print("=" * 70)
    print("🔑 Provider Key Audit")
    print("=" * 70)
    
    issues = []
    
    for pname in sorted(providers.keys()):
        pcfg = providers[pname]
        key_ref = pcfg.get("apiKey", "")
        env_var = resolve_env_ref(key_ref)
        
        print(f"\n📦 {pname}")
        print(f"   baseUrl: {pcfg.get('baseUrl', 'N/A')}")
        
        if env_var:
            # Env reference
            has_env = check_env(env_var)
            has_pass = check_pass(f"api/{pname}")
            print(f"   key: ${{{env_var}}} → env={'✅' if has_env else '❌'} pass={'✅' if has_pass else '⚠️'}")
            if not has_env:
                issues.append(f"{pname}: env var {env_var} not set in .env")
            if not has_pass:
                issues.append(f"{pname}: no pass entry api/{pname}")
        elif key_ref and not key_ref.startswith("$"):
            # Hardcoded key!
            key_preview = key_ref[:8] + "..." + key_ref[-4:]
            print(f"   key: 🔴 HARDCODED {key_preview}")
            issues.append(f"{pname}: key is hardcoded in openclaw.json (security risk!)")
            has_pass = check_pass(f"api/{pname}")
            if not has_pass:
                issues.append(f"{pname}: no pass entry api/{pname} — create it first")
        else:
            print(f"   key: ⚠️ None/N/A (uses OAuth or other auth)")
    
    # Check agent model assignments
    print(f"\n{'=' * 70}")
    print("🤖 Agent Model Assignments")
    print("=" * 70)
    
    agents_list = cfg.get("agents", {}).get("list", [])
    model_counts = {}
    for a in agents_list:
        aid = a.get("id", "?")
        model_cfg = a.get("model", {})
        if isinstance(model_cfg, dict):
            primary = model_cfg.get("primary", "?")
            model_counts[primary] = model_counts.get(primary, 0) + 1
            print(f"   {aid:12s}: {primary}")
    
    # Check for unbalanced assignment
    print(f"\n📊 Model Distribution:")
    for model, count in sorted(model_counts.items(), key=lambda x: -x[1]):
        bar = "█" * count
        print(f"   {model:40s} {count:2d} {bar}")
    
    # Summary
    print(f"\n{'=' * 70}")
    if issues:
        print(f"🔴 Issues Found: {len(issues)}")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print("✅ No issues found")

if __name__ == "__main__":
    main()

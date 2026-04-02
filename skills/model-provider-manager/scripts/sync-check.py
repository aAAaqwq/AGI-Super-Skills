#!/usr/bin/env python3
"""Sync Check — verify env → openclaw.json → agent → cron consistency."""

import json, os, subprocess, re, sys

CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")
ENV_PATH = os.path.expanduser("~/.openclaw/.env")

def get_env_vars():
    """Parse .env file into dict."""
    env = {}
    if not os.path.exists(ENV_PATH):
        return env
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip().strip('"').strip("'")
    return env

def resolve_ref(ref, env):
    """Resolve ${VAR} reference."""
    if ref and ref.startswith("${") and ref.endswith("}"):
        var = ref[2:-1]
        return env.get(var, None)
    return ref

def main():
    issues = []
    warnings = []
    
    env = get_env_vars()
    
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    
    print("=" * 70)
    print("🔄 Config Sync Check: pass → .env → openclaw.json → agents → crons")
    print("=" * 70)
    
    # Step 1: Check providers reference env vars
    print("\n📦 Step 1: Providers Key Source")
    providers = cfg.get("models", {}).get("providers", {})
    for pname, pcfg in sorted(providers.items()):
        key_ref = pcfg.get("apiKey", "")
        if key_ref and key_ref.startswith("${"):
            var = key_ref[2:-1]
            has_env = var in env
            # Check pass
            pass_name = f"api/{pname.lower()}"
            has_pass = subprocess.run(
                ["pass", "show", pass_name], capture_output=True, timeout=5
            ).returncode == 0
            
            status = "✅" if has_env and has_pass else ("⚠️" if has_env else "❌")
            print(f"  {status} {pname:15s} env={var}: {'✅' if has_env else '❌'}  pass={has_pass}")
            if not has_env:
                issues.append(f"{pname}: env var {var} not set")
            if not has_pass:
                warnings.append(f"{pname}: no pass entry api/{pname}")
        elif key_ref and not key_ref.startswith("$"):
            print(f"  🔴 {pname:15s} HARDCODED key (should use ${{ENV}})")
            issues.append(f"{pname}: hardcoded key in openclaw.json")
    
    # Step 2: Check all agents share same model (should be differentiated)
    print("\n🤖 Step 2: Agent Model Configuration")
    agents_list = cfg.get("agents", {}).get("list", [])
    model_map = {}
    for a in agents_list:
        aid = a.get("id", "?")
        model_cfg = a.get("model", {})
        if isinstance(model_cfg, dict):
            primary = model_cfg.get("primary", "?")
            fallbacks = model_cfg.get("fallbacks", [])
            model_map[aid] = primary
            
            # Check if primary references a valid provider
            provider_name = primary.split("/")[0] if "/" in primary else "?"
            has_provider = provider_name in providers
            status = "✅" if has_provider else "❌"
            fb_str = ", ".join(fallbacks[:2]) + ("..." if len(fallbacks) > 2 else "")
            print(f"  {status} {aid:12s} → {primary:35s} fb=[{fb_str}]")
            if not has_provider:
                issues.append(f"{aid}: primary model references unknown provider '{provider_name}'")
    
    # Check if all agents use same model (warning)
    unique_models = set(model_map.values())
    if len(unique_models) == 1:
        print(f"\n  ⚠️ All {len(model_map)} agents use the SAME model: {list(unique_models)[0]}")
        warnings.append(f"All agents use identical model (no differentiation)")
    
    # Step 3: Check cron models
    print("\n⏰ Step 3: Cron Model Configuration")
    try:
        result = subprocess.run(
            ["openclaw", "cron", "list", "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            crons = json.loads(result.stdout)
            model_count = {}
            for c in crons:
                payload = c.get("payload", {})
                model = payload.get("model", "default(inherited)")
                name = c.get("name", c.get("id", "?"))
                fb = payload.get("fallbacks", [])
                
                # Check if model references valid provider
                provider_name = model.split("/")[0] if "/" in model else model
                if provider_name not in providers and model != "default(inherited)":
                    issues.append(f"Cron '{name}': model {model} references unknown provider")
                
                model_count[model] = model_count.get(model, 0) + 1
            
            print(f"  Total crons: {len(crons)}")
            for model, count in sorted(model_count.items(), key=lambda x: -x[1]):
                print(f"    {model:40s} ×{count}")
        else:
            print(f"  ⚠️ Could not list crons (exit code {result.returncode})")
    except Exception as e:
        print(f"  ⚠️ Could not list crons: {e}")
    
    # Summary
    print(f"\n{'=' * 70}")
    print(f"🔴 Issues: {len(issues)}")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    
    if warnings:
        print(f"\n⚠️ Warnings: {len(warnings)}")
        for i, w in enumerate(warnings, 1):
            print(f"  {i}. {w}")
    
    if not issues and not warnings:
        print("✅ All configs synced — no issues")

if __name__ == "__main__":
    main()

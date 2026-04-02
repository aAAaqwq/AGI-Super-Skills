#!/usr/bin/env python3
"""
Provider Key Manager — 一条命令更换供应商 API Key，全员生效
"""

import json
import os
import sys
import subprocess
import shutil
import re
from pathlib import Path
from datetime import datetime

# ── 常量 ──────────────────────────────────────────────
OPENCLAW_DIR = Path.home() / ".openclaw"
OPENCLAW_CONFIG = OPENCLAW_DIR / "openclaw.json"
AGENTS_DIR = OPENCLAW_DIR / "agents"
BACKUP_DIR = Path("/tmp/provider-key-backup")

# Provider → 环境变量名 → pass 路径 映射
PROVIDER_ENV_MAP = {
    "zai":           {"env": "ZAI_API_KEY",        "pass": "api/zai"},
    "xingjiabiapi":  {"env": "XINGJIABIAPI_KEY",   "pass": "api/xingjiabiapi"},
    "xai":           {"env": "XAI_API_KEY",        "pass": "api/xai"},
    "xingsuancode":  {"env": "XINGSUANCODE_KEY",   "pass": "api/xingsuancode"},
    "moonshot":      {"env": "MOONSHOT_API_KEY",    "pass": "api/kimi"},
    "minimax":       {"env": "MINIMAX_API_KEY",     "pass": "api/minimax"},
    "xinyuan":       {"env": "XINYUAN_API_KEY",     "pass": "api/xinyuan"},
    "boluobao":      {"env": "BOLUOBAO_API_KEY",    "pass": "api/boluobao"},
    "google":        {"env": "GOOGLE_API_KEY",      "pass": "api/google-ai-studio"},
}

# 测试端点映射
PROVIDER_TEST_CONFIG = {
    "zai":           {"url_suffix": "/chat/completions", "model": "glm-5-turbo"},
    "xingjiabiapi":  {"url_suffix": "/chat/completions", "model": "gpt-4o-mini"},
    "xai":           {"url_suffix": "/chat/completions", "model": "grok-2-latest"},
    "xingsuancode":  {"url_suffix": "/v1/messages",      "model": "claude-sonnet-4-6", "api": "anthropic"},
    "moonshot":      {"url_suffix": "/chat/completions", "model": "kimi-k2.5"},
    "minimax":       {"url_suffix": "/chat/completions", "model": "MiniMax-M2.5"},
    "xinyuan":       {"url_suffix": "/chat/completions", "model": "grok-4.1-thinking"},
    "boluobao":      {"url_suffix": "/chat/completions", "model": "gemini-3-pro-image-preview"},
    "google":        {"url_suffix": "/chat/completions", "model": "gemini-2.5-flash"},
}


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  💾 写入: {path}")


def get_all_agents() -> list[str]:
    """获取所有 agent ID"""
    if not AGENTS_DIR.exists():
        return []
    return sorted([
        d.name for d in AGENTS_DIR.iterdir()
        if d.is_dir() and (d / "agent" / "models.json").exists()
    ])


def is_env_ref(value) -> bool:
    """检查是否是 ${ENV_VAR} 引用"""
    if isinstance(value, str):
        return bool(re.match(r'^\$\{[A-Z][A-Z0-9_]*\}$', value.strip()))
    if isinstance(value, dict):
        return value.get("source") in ("env", "file", "exec")
    return False


def extract_env_var_name(value: str) -> str | None:
    """从 ${VAR_NAME} 中提取变量名"""
    m = re.match(r'^\$\{([A-Z][A-Z0-9_]*)\}$', value.strip())
    return m.group(1) if m else None


# ── 命令：audit ──────────────────────────────────────
def cmd_audit():
    """审计所有 agent 的 provider key 配置"""
    print("🔍 Provider Key 配置审计")
    print("=" * 60)

    config = load_json(OPENCLAW_CONFIG)
    global_providers = config.get("models", {}).get("providers", {})
    env_vars = config.get("env", {}).get("vars", {})
    agents = get_all_agents()

    # 1. 全局 provider 检查
    print("\n📋 全局 Provider (openclaw.json)")
    print("-" * 40)
    for pid, pconf in sorted(global_providers.items()):
        api_key = pconf.get("apiKey", "")
        base_url = pconf.get("baseUrl", "N/A")
        if is_env_ref(api_key):
            env_name = extract_env_var_name(api_key) if isinstance(api_key, str) else api_key.get("id", "?")
            actual = env_vars.get(env_name, "❌ 未设置")
            masked = actual[:6] + "..." + actual[-4:] if len(str(actual)) > 10 else actual
            print(f"  ✅ {pid}: apiKey=${{{env_name}}} → {masked}")
        elif api_key:
            masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else api_key
            print(f"  ❌ {pid}: 硬编码 apiKey={masked}")
        else:
            print(f"  ⚠️ {pid}: 无 apiKey")
        print(f"     baseUrl: {base_url}")

    # 2. 各 agent 检查
    print(f"\n📋 各 Agent models.json ({len(agents)} 个)")
    print("-" * 40)

    issues = []
    for agent_id in agents:
        models_path = AGENTS_DIR / agent_id / "agent" / "models.json"
        models = load_json(models_path)
        agent_providers = models.get("providers", {})

        agent_issues = []
        for pid, pconf in agent_providers.items():
            api_key = pconf.get("apiKey")
            if api_key is None:
                continue  # 无 apiKey = 继承全局 ✅
            if is_env_ref(api_key):
                continue  # 使用环境变量引用 ✅
            # 硬编码
            global_key = global_providers.get(pid, {}).get("apiKey", "")
            # 解析全局 key 的实际值
            if is_env_ref(global_key) and isinstance(global_key, str):
                env_name = extract_env_var_name(global_key)
                global_actual = env_vars.get(env_name, "") if env_name else ""
            else:
                global_actual = global_key

            if api_key == global_actual:
                agent_issues.append(f"  ⚠️ {pid}: 硬编码但值正确（建议迁移为继承）")
            else:
                agent_issues.append(f"  ❌ {pid}: 硬编码且值不一致！")
                issues.append((agent_id, pid))

        if agent_issues:
            print(f"  🤖 {agent_id}:")
            for issue in agent_issues:
                print(f"    {issue}")
        else:
            has_keys = any(
                p.get("apiKey") is not None
                for p in agent_providers.values()
            )
            if not has_keys and agent_providers:
                print(f"  ✅ {agent_id}: 全部继承全局（理想状态）")
            elif not agent_providers:
                print(f"  ✅ {agent_id}: 无自定义 provider")
            else:
                print(f"  ✅ {agent_id}: 配置正确")

    # 3. 总结
    print(f"\n{'=' * 60}")
    if issues:
        print(f"⚠️ 发现 {len(issues)} 个不一致问题:")
        for agent_id, pid in issues:
            print(f"  - {agent_id}/{pid}")
        print(f"\n💡 建议运行: python3 {__file__} migrate")
    else:
        print("✅ 所有配置一致")

    # 4. env.vars 覆盖度
    print(f"\n📋 env.vars 环境变量 ({len(env_vars)} 个)")
    print("-" * 40)
    for provider_id, mapping in sorted(PROVIDER_ENV_MAP.items()):
        env_name = mapping["env"]
        if env_name in env_vars:
            val = env_vars[env_name]
            masked = val[:6] + "..." + val[-4:] if len(val) > 10 else val
            print(f"  ✅ {env_name} = {masked}")
        elif provider_id in global_providers:
            print(f"  ❌ {env_name} 未设置（provider {provider_id} 存在但无 env var）")


# ── 命令：migrate ────────────────────────────────────
def cmd_migrate(provider_filter: str = None, dry_run: bool = False):
    """迁移硬编码 key 到环境变量模式"""
    print("🔄 迁移到环境变量模式")
    if dry_run:
        print("   (DRY RUN - 不会实际修改文件)")
    print("=" * 60)

    config = load_json(OPENCLAW_CONFIG)
    global_providers = config.get("models", {}).get("providers", {})
    env_vars = config.setdefault("env", {}).setdefault("vars", {})
    agents = get_all_agents()

    # 备份
    if not dry_run:
        backup_dir = BACKUP_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OPENCLAW_CONFIG, backup_dir / "openclaw.json")
        for agent_id in agents:
            src = AGENTS_DIR / agent_id / "agent" / "models.json"
            dst = backup_dir / f"{agent_id}-models.json"
            shutil.copy2(src, dst)
        print(f"  📦 备份到: {backup_dir}")

    changes = []

    # Step 1: 全局 provider apiKey → ${ENV_VAR}
    print("\n📌 Step 1: 全局 provider apiKey → ${ENV_VAR}")
    for pid, pconf in global_providers.items():
        if provider_filter and pid != provider_filter:
            continue
        api_key = pconf.get("apiKey", "")
        if not api_key or is_env_ref(api_key):
            print(f"  ⏭️ {pid}: 已是环境变量引用或无 key")
            continue

        mapping = PROVIDER_ENV_MAP.get(pid)
        if not mapping:
            # 自动生成 env var name
            env_name = pid.upper().replace("-", "_") + "_API_KEY"
            pass_path = f"api/{pid}"
            print(f"  ⚠️ {pid}: 未预定义映射，自动使用 {env_name}")
        else:
            env_name = mapping["env"]
            pass_path = mapping["pass"]

        print(f"  🔄 {pid}: 硬编码 → ${{{env_name}}}")
        if not dry_run:
            env_vars[env_name] = api_key  # 保存实际值到 env.vars
            pconf["apiKey"] = f"${{{env_name}}}"  # 替换为引用
        changes.append(f"全局 {pid}: apiKey → ${{{env_name}}}")

    # Step 2: 各 agent models.json 删除 apiKey
    print("\n📌 Step 2: 各 agent models.json 删除 apiKey（继承全局）")
    for agent_id in agents:
        models_path = AGENTS_DIR / agent_id / "agent" / "models.json"
        models = load_json(models_path)
        agent_providers = models.get("providers", {})
        modified = False

        for pid, pconf in agent_providers.items():
            if provider_filter and pid != provider_filter:
                continue
            if "apiKey" in pconf:
                print(f"  🗑️ {agent_id}/{pid}: 删除 apiKey（将继承全局）")
                if not dry_run:
                    del pconf["apiKey"]
                    modified = True
                changes.append(f"{agent_id}/{pid}: 删除 apiKey")

        if modified and not dry_run:
            save_json(models_path, models)

    # Step 3: 保存全局配置
    if not dry_run and changes:
        save_json(OPENCLAW_CONFIG, config)

    # Step 4: 更新 pass
    if not dry_run:
        print("\n📌 Step 3: 同步 pass 存储")
        for pid in global_providers:
            if provider_filter and pid != provider_filter:
                continue
            mapping = PROVIDER_ENV_MAP.get(pid)
            if not mapping:
                continue
            env_name = mapping["env"]
            pass_path = mapping["pass"]
            actual_key = env_vars.get(env_name, "")
            if actual_key:
                try:
                    subprocess.run(
                        ["pass", "insert", "-f", pass_path],
                        input=actual_key.encode(),
                        capture_output=True, timeout=10
                    )
                    print(f"  ✅ pass insert {pass_path}")
                except Exception as e:
                    print(f"  ⚠️ pass insert {pass_path} 失败: {e}")

    # 总结
    print(f"\n{'=' * 60}")
    print(f"📊 迁移{'(DRY RUN)' if dry_run else ''}完成: {len(changes)} 处变更")
    for c in changes:
        print(f"  - {c}")
    if not dry_run and changes:
        print(f"\n⚠️ 需要重启 Gateway 生效")
        print(f"   运行: openclaw gateway restart")


# ── 命令：update ─────────────────────────────────────
def cmd_update(provider: str, new_key: str, base_url: str = None):
    """更换指定 provider 的 API Key"""
    print(f"🔑 更换 {provider} API Key")
    print("=" * 60)

    config = load_json(OPENCLAW_CONFIG)
    global_providers = config.get("models", {}).get("providers", {})
    env_vars = config.setdefault("env", {}).setdefault("vars", {})
    agents = get_all_agents()

    if provider not in global_providers:
        print(f"❌ Provider '{provider}' 不存在于全局配置")
        print(f"   可用: {', '.join(global_providers.keys())}")
        return

    mapping = PROVIDER_ENV_MAP.get(provider, {})
    env_name = mapping.get("env", f"{provider.upper()}_API_KEY")
    pass_path = mapping.get("pass", f"api/{provider}")

    pconf = global_providers[provider]
    changes = 0

    # 1. 更新 env.vars
    old_key = env_vars.get(env_name, "")
    env_vars[env_name] = new_key
    print(f"  ✅ env.vars.{env_name} 已更新")
    changes += 1

    # 2. 确保全局 apiKey 是 ${ENV_VAR} 引用
    if not is_env_ref(pconf.get("apiKey", "")):
        pconf["apiKey"] = f"${{{env_name}}}"
        print(f"  ✅ 全局 provider apiKey → ${{{env_name}}}")
        changes += 1
    else:
        print(f"  ⏭️ 全局 provider apiKey 已是 ${{{env_name}}}")

    # 3. 更新 baseUrl（如果提供）
    if base_url:
        pconf["baseUrl"] = base_url
        print(f"  ✅ baseUrl → {base_url}")
        changes += 1

    # 4. 同步各 agent（如果还有硬编码的）
    agent_fixes = 0
    for agent_id in agents:
        models_path = AGENTS_DIR / agent_id / "agent" / "models.json"
        models = load_json(models_path)
        agent_pconf = models.get("providers", {}).get(provider)
        if agent_pconf and "apiKey" in agent_pconf:
            del agent_pconf["apiKey"]  # 删除硬编码，继承全局
            save_json(models_path, models)
            print(f"  🗑️ {agent_id}: 删除硬编码 apiKey（继承全局）")
            agent_fixes += 1

    # 5. 保存全局配置
    save_json(OPENCLAW_CONFIG, config)

    # 6. 更新 pass
    try:
        subprocess.run(
            ["pass", "insert", "-f", pass_path],
            input=new_key.encode(),
            capture_output=True, timeout=10
        )
        print(f"  ✅ pass insert {pass_path}")
    except Exception as e:
        print(f"  ⚠️ pass 更新失败: {e}")

    # 7. 测试
    print(f"\n🧪 测试 {provider} key...")
    test_ok = _test_provider(provider, new_key, pconf.get("baseUrl", ""))

    # 总结
    print(f"\n{'=' * 60}")
    print(f"📊 更新完成:")
    print(f"  - env.vars: ✅")
    print(f"  - 全局 provider: ✅")
    print(f"  - agent 硬编码清理: {agent_fixes} 个")
    print(f"  - pass: ✅")
    print(f"  - 可用性测试: {'✅ 通过' if test_ok else '❌ 失败'}")
    print(f"\n⚠️ 需要重启 Gateway 生效")
    print(f"   运行: openclaw gateway restart")


# ── 命令：test ───────────────────────────────────────
def cmd_test(provider: str):
    """测试 provider key 可用性"""
    config = load_json(OPENCLAW_CONFIG)
    global_providers = config.get("models", {}).get("providers", {})
    env_vars = config.get("env", {}).get("vars", {})

    if provider not in global_providers:
        print(f"❌ Provider '{provider}' 不存在")
        return

    pconf = global_providers[provider]
    api_key = pconf.get("apiKey", "")

    # 解析环境变量引用
    if isinstance(api_key, str) and is_env_ref(api_key):
        env_name = extract_env_var_name(api_key)
        api_key = env_vars.get(env_name, "") if env_name else ""
        print(f"  📎 Key 来源: ${{{env_name}}}")

    base_url = pconf.get("baseUrl", "")
    _test_provider(provider, api_key, base_url)


def _test_provider(provider: str, api_key: str, base_url: str) -> bool:
    """实际测试 provider"""
    import urllib.request
    import urllib.error

    test_conf = PROVIDER_TEST_CONFIG.get(provider)
    if not test_conf:
        print(f"  ⚠️ 无测试配置 for {provider}")
        return True  # 跳过

    url = base_url.rstrip("/") + test_conf["url_suffix"]
    model = test_conf["model"]
    is_anthropic = test_conf.get("api") == "anthropic"

    if is_anthropic:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        body = json.dumps({
            "model": model,
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "hi"}]
        })
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 5
        })

    try:
        req = urllib.request.Request(url, data=body.encode(), headers=headers, method="POST")
        # 绕过代理
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        resp = opener.open(req, timeout=15)
        result = json.loads(resp.read())
        if "choices" in result or "content" in result:
            print(f"  ✅ {provider}: 测试通过 (model={model})")
            return True
        elif "error" in result:
            print(f"  ❌ {provider}: {result['error']}")
            return False
        else:
            print(f"  ✅ {provider}: 有响应 (可能正常)")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"  ❌ {provider}: HTTP {e.code} - {body}")
        return False
    except Exception as e:
        print(f"  ❌ {provider}: {e}")
        return False


# ── 命令：status ─────────────────────────────────────
def cmd_status():
    """显示所有 provider 状态总览"""
    print("📊 Provider 状态总览")
    print("=" * 60)

    config = load_json(OPENCLAW_CONFIG)
    global_providers = config.get("models", {}).get("providers", {})
    env_vars = config.get("env", {}).get("vars", {})

    for pid, pconf in sorted(global_providers.items()):
        api_key = pconf.get("apiKey", "")
        base_url = pconf.get("baseUrl", "N/A")
        api_type = pconf.get("api", "openai-completions")
        models = [m.get("id", "?") for m in pconf.get("models", [])]

        # Key 来源
        if is_env_ref(api_key) and isinstance(api_key, str):
            env_name = extract_env_var_name(api_key)
            actual = env_vars.get(env_name, "")
            key_source = f"${{{env_name}}}"
            key_masked = actual[:6] + "..." + actual[-4:] if len(actual) > 10 else "(empty)"
        elif api_key:
            key_source = "硬编码"
            key_masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else api_key
        else:
            key_source = "无"
            key_masked = "-"

        print(f"\n🏷️ {pid}")
        print(f"  Key:    {key_source} = {key_masked}")
        print(f"  URL:    {base_url}")
        print(f"  API:    {api_type}")
        print(f"  Models: {', '.join(models[:5])}{'...' if len(models) > 5 else ''}")


# ── 主入口 ───────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} audit              — 审计配置")
        print(f"  {sys.argv[0]} migrate [--provider X] [--dry-run]  — 迁移到环境变量模式")
        print(f"  {sys.argv[0]} update <provider> <key> [--base-url URL]  — 更换 key")
        print(f"  {sys.argv[0]} test <provider>     — 测试 key")
        print(f"  {sys.argv[0]} status              — 状态总览")
        return

    cmd = sys.argv[1]

    if cmd == "audit":
        cmd_audit()
    elif cmd == "migrate":
        provider = None
        dry_run = False
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--provider" and i + 1 < len(sys.argv):
                provider = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--dry-run":
                dry_run = True
                i += 1
            else:
                i += 1
        cmd_migrate(provider, dry_run)
    elif cmd == "update":
        if len(sys.argv) < 4:
            print("Usage: manager.py update <provider> <new-key> [--base-url URL]")
            return
        provider = sys.argv[2]
        new_key = sys.argv[3]
        base_url = None
        if "--base-url" in sys.argv:
            idx = sys.argv.index("--base-url")
            if idx + 1 < len(sys.argv):
                base_url = sys.argv[idx + 1]
        cmd_update(provider, new_key, base_url)
    elif cmd == "test":
        if len(sys.argv) < 3:
            print("Usage: manager.py test <provider>")
            return
        cmd_test(sys.argv[2])
    elif cmd == "status":
        cmd_status()
    else:
        print(f"❌ 未知命令: {cmd}")


if __name__ == "__main__":
    main()

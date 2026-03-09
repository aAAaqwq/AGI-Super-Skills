#!/usr/bin/env python3
"""
Agent Model Switcher - 批量管理 OpenClaw 子 agent 的模型配置
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# 配置路径
AGENTS_DIR = Path.home() / ".openclaw" / "agents"

# 模型别名
MODEL_ALIASES = {
    "glm5": "zai/glm-5",
    "glm47": "zai/glm-4.7",
    "glm47-flash": "zai/glm-4.7-flash",
    "glm47-flashx": "zai/glm-4.7-flashx",
    "opus46": "xingsuancode/claude-opus-4-6",
    "opus46-aixn": "aixn/claude-opus-4-6",
    "sonnet46": "xingsuancode/claude-sonnet-4-6",
    "kimi": "moonshot/kimi-k2.5",
    "m25": "minimax/MiniMax-M2.5",
    "m2": "minimax/MiniMax-M2",
}

# 排除的 agent（不需要单独配置的）
EXCLUDED_AGENTS = {"telegram-agent"}


def resolve_model(model: str) -> str:
    """解析模型别名"""
    return MODEL_ALIASES.get(model.lower(), model)


def get_all_agents() -> list[str]:
    """获取所有 agent 名称"""
    agents = []
    for item in AGENTS_DIR.iterdir():
        if item.is_dir() and item.name not in EXCLUDED_AGENTS:
            agent_json = item / "agent" / "agent.json"
            if agent_json.exists():
                agents.append(item.name)
    return sorted(agents)


def get_agent_model(agent_name: str) -> str:
    """获取 agent 的当前 model"""
    agent_json = AGENTS_DIR / agent_name / "agent" / "agent.json"
    if agent_json.exists():
        with open(agent_json) as f:
            data = json.load(f)
            return data.get("model", "not set")
    return "no agent.json"


def get_agent_zai_key(agent_name: str) -> str:
    """获取 agent 的 zai apiKey"""
    models_json = AGENTS_DIR / agent_name / "agent" / "models.json"
    if models_json.exists():
        with open(models_json) as f:
            data = json.load(f)
            key = data.get("providers", {}).get("zai", {}).get("apiKey", "not set")
            if key != "not set" and len(key) > 20:
                return key[:20] + "..."
            return key
    return "no models.json"


def list_agents():
    """列出所有 agent 的 model 配置"""
    agents = get_all_agents()
    print(f"{'Agent':<15} {'Model':<30} {'ZAI Key':<25}")
    print("-" * 70)
    for agent in agents:
        model = get_agent_model(agent)
        key = get_agent_zai_key(agent)
        print(f"{agent:<15} {model:<30} {key:<25}")


def set_model(model: str, agents: list[str] = None, include_main: bool = False, dry_run: bool = False):
    """设置 agent 的 model"""
    model = resolve_model(model)
    if agents is None:
        agents = get_all_agents()
        if not include_main:
            agents = [a for a in agents if a != "main"]
    
    print(f"Setting model to: {model}")
    print(f"Agents: {', '.join(agents)}")
    print()
    
    for agent in agents:
        agent_json = AGENTS_DIR / agent / "agent" / "agent.json"
        if not agent_json.exists():
            print(f"  ⚠️  {agent}: no agent.json, skipping")
            continue
        
        if dry_run:
            print(f"  [DRY-RUN] {agent}: would set model to {model}")
            continue
        
        with open(agent_json) as f:
            data = json.load(f)
        
        old_model = data.get("model", "not set")
        data["model"] = model
        
        with open(agent_json, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ {agent}: {old_model} → {model}")


def sync_models(agents: list[str] = None, dry_run: bool = False):
    """从 main 复制 models.json 到其他 agent"""
    main_models = AGENTS_DIR / "main" / "agent" / "models.json"
    if not main_models.exists():
        print("Error: main/agent/models.json not found")
        return
    
    if agents is None:
        agents = get_all_agents()
        agents = [a for a in agents if a != "main"]
    
    print(f"Syncing models.json from main to: {', '.join(agents)}")
    print()
    
    for agent in agents:
        target_models = AGENTS_DIR / agent / "agent" / "models.json"
        
        if dry_run:
            print(f"  [DRY-RUN] {agent}: would copy models.json")
            continue
        
        shutil.copy(main_models, target_models)
        print(f"  ✅ {agent}: models.json synced")


def main():
    parser = argparse.ArgumentParser(description="Agent Model Switcher")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # list 命令
    subparsers.add_parser("list", help="List all agents' model config")
    
    # set 命令
    set_parser = subparsers.add_parser("set", help="Set agent model")
    set_parser.add_argument("model", help="Model to set (e.g., zai/glm-5 or alias like glm5)")
    set_parser.add_argument("--agents", help="Comma-separated list of agents (default: all except main)")
    set_parser.add_argument("--include-main", action="store_true", help="Include main agent")
    set_parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    # sync-models 命令
    sync_parser = subparsers.add_parser("sync-models", help="Sync models.json from main to other agents")
    sync_parser.add_argument("--agents", help="Comma-separated list of agents (default: all except main)")
    sync_parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_agents()
    elif args.command == "set":
        agents = args.agents.split(",") if args.agents else None
        set_model(args.model, agents, args.include_main, args.dry_run)
    elif args.command == "sync-models":
        agents = args.agents.split(",") if args.agents else None
        sync_models(agents, args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

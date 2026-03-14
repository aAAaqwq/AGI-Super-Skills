#!/bin/bash
# sync-agent-auth.sh — 同步 openclaw.json 的 provider keys 到所有 agent 的 auth-profiles.json
# 用法: ./sync-agent-auth.sh [--dry-run] [--agent <id>] [--provider <name>]
#
# 场景：改了 openclaw.json 的 apiKey 后，一键同步到所有 agent
# 原理：删除 auth-profiles.json（或更新其中的 key），重启后 OpenClaw 自动从 openclaw.json 重建

set -euo pipefail

AGENTS_DIR="${HOME}/.openclaw/agents"
CONFIG="${HOME}/.openclaw/openclaw.json"
DRY_RUN=false
TARGET_AGENT=""
TARGET_PROVIDER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --agent) TARGET_AGENT="$2"; shift 2 ;;
    --provider) TARGET_PROVIDER="$2"; shift 2 ;;
    -h|--help)
      echo "用法: $0 [--dry-run] [--agent <id>] [--provider <name>]"
      echo ""
      echo "选项:"
      echo "  --dry-run       只显示会做什么，不实际修改"
      echo "  --agent <id>    只同步指定 agent（如 quant, code）"
      echo "  --provider <name>  只同步指定 provider 的 key（如 zai, moonshot）"
      echo ""
      echo "示例:"
      echo "  $0                          # 清除所有 agent 的 auth-profiles，让 OpenClaw 重建"
      echo "  $0 --agent quant            # 只清除 quant 的"
      echo "  $0 --provider zai           # 只更新所有 agent 里 zai 相关的 key"
      echo "  $0 --dry-run                # 预览操作"
      exit 0
      ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

if [ ! -f "$CONFIG" ]; then
  echo "❌ 找不到 $CONFIG"
  exit 1
fi

# 获取 openclaw.json 中所有 provider 的 apiKey
get_provider_key() {
  local provider="$1"
  python3 -c "
import json
with open('$CONFIG') as f:
    d = json.load(f)
key = d.get('models',{}).get('providers',{}).get('$provider',{}).get('apiKey','')
print(key)
" 2>/dev/null
}

updated=0
skipped=0
errors=0

for agent_dir in "$AGENTS_DIR"/*/; do
  agent=$(basename "$agent_dir")
  auth_file="${agent_dir}agent/auth-profiles.json"
  
  # 过滤指定 agent
  [ -n "$TARGET_AGENT" ] && [ "$agent" != "$TARGET_AGENT" ] && continue
  
  if [ ! -f "$auth_file" ]; then
    echo "⏭️  $agent: 无 auth-profiles.json，跳过"
    ((skipped++)) || true
    continue
  fi
  
  if [ -n "$TARGET_PROVIDER" ]; then
    # 精确更新指定 provider 的 key
    new_key=$(get_provider_key "$TARGET_PROVIDER")
    if [ -z "$new_key" ]; then
      echo "❌ openclaw.json 中找不到 provider: $TARGET_PROVIDER"
      exit 1
    fi
    
    result=$(python3 -c "
import json
with open('$auth_file') as f:
    d = json.load(f)
profiles = d.get('profiles', {})
changed = False
for pname, p in profiles.items():
    if p.get('provider') == '$TARGET_PROVIDER' or pname.startswith('${TARGET_PROVIDER}:'):
        old_key = p.get('key', p.get('apiKey', ''))
        if old_key != '$new_key':
            p['key'] = '$new_key'
            p.pop('apiKey', None)
            changed = True
# Clear error stats for this provider
stats = d.get('usageStats', {})
for k in list(stats.keys()):
    if '$TARGET_PROVIDER' in k:
        stats[k].pop('errorCount', None)
        stats[k].pop('failureCounts', None)
        stats[k].pop('cooldownUntil', None)
        stats[k].pop('lastFailureAt', None)
if changed:
    with open('$auth_file', 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    print('updated')
else:
    print('same')
" 2>/dev/null)
    
    if [ "$DRY_RUN" = true ]; then
      echo "🔍 $agent: 会更新 $TARGET_PROVIDER key ($result)"
    elif [ "$result" = "updated" ]; then
      echo "✅ $agent: $TARGET_PROVIDER key 已更新"
      ((updated++)) || true
    else
      echo "⏭️  $agent: $TARGET_PROVIDER key 已是最新"
      ((skipped++)) || true
    fi
  else
    # 删除整个 auth-profiles.json，让 OpenClaw 从 openclaw.json 重建
    if [ "$DRY_RUN" = true ]; then
      echo "🔍 $agent: 会删除 auth-profiles.json"
    else
      rm -f "$auth_file"
      echo "✅ $agent: auth-profiles.json 已删除（重启后自动重建）"
      ((updated++)) || true
    fi
  fi
done

echo ""
echo "📊 结果: ${updated} 更新, ${skipped} 跳过, ${errors} 错误"

if [ "$DRY_RUN" = false ] && [ "$updated" -gt 0 ]; then
  echo ""
  echo "⚡ 请重启 Gateway 生效: openclaw gateway restart"
fi

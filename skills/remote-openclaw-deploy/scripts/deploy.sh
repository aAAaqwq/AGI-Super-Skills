#!/bin/bash
# remote-openclaw-deploy: 通用远程部署 OpenClaw Agent 项目
# 支持任意定制化 agent 项目，跨 macOS/Linux，多渠道（飞书/Telegram/Discord）
#
# Usage:
#   ./deploy.sh <user>@<ip> <project_dir> [ssh_key]
#   ./deploy.sh laotian@100.91.44.116 ~/projects/private_tian_agent
#   ./deploy.sh ubuntu@10.0.0.5 ~/projects/saas_support_team ~/.ssh/my_key
#
# 项目目录结构：
#   project/
#   ├── deploy.json          ← 部署清单（可选，自动化配置注入）
#   ├── agents/
#   │   ├── assistant/agent/
#   │   ├── media/agent/
#   │   └── ...
#   ├── skills/              ← 共享 skills（可选）
#   └── workspace/           ← 工作区文件（可选，AGENTS.md/SOUL.md 等）

set -euo pipefail

TARGET="${1:?Usage: $0 <user@ip> <project_dir> [ssh_key]}"
PROJECT_DIR="${2:?Provide local project directory}"
SSH_KEY="${3:-$HOME/.ssh/id_ed25519}"

# SSH 配置
SSH_OPTS="-o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
SSH_CMD="ssh $SSH_OPTS -i $SSH_KEY $TARGET"

USER=$(echo "$TARGET" | cut -d@ -f1)
PROJ_NAME=$(basename "$PROJECT_DIR")
DEPLOY_JSON="$PROJECT_DIR/deploy.json"

echo "🚀 OpenClaw Remote Deploy (通用版)"
echo "   Target: $TARGET"
echo "   Project: $PROJECT_DIR ($PROJ_NAME)"
echo "   SSH Key: $SSH_KEY"
[ -f "$DEPLOY_JSON" ] && echo "   Manifest: deploy.json ✅" || echo "   Manifest: 无 (仅传输文件)"
echo ""

# ==================== Phase 1: 环境探测 ====================
echo "📡 Phase 1: 环境探测..."
REMOTE_INFO=$($SSH_CMD '
  OS=$(uname -s)
  ARCH=$(uname -m)
  
  # 检测 home 目录（跨平台）
  echo "HOME=$HOME"
  echo "OS=$OS"
  echo "ARCH=$ARCH"
  
  # 内存
  if [ "$OS" = "Darwin" ]; then
    MEM=$(sysctl -n hw.memsize 2>/dev/null | awk "{printf \"%.0f\", \$1/1024/1024/1024}")
  else
    MEM=$(free -g 2>/dev/null | awk "/Mem:/{print \$2}" || echo "?")
  fi
  echo "MEM=${MEM}GB"
  
  # 磁盘
  DISK=$(df -h / 2>/dev/null | tail -1 | awk "{print \$4}")
  echo "DISK=$DISK"
  
  # OpenClaw
  OC_VER=$(openclaw --version 2>/dev/null || echo "NOT_FOUND")
  echo "OPENCLAW=$OC_VER"
  
  # Gateway
  if pgrep -f openclaw-gateway >/dev/null 2>&1; then
    echo "GATEWAY=RUNNING"
  else
    echo "GATEWAY=STOPPED"
  fi
' 2>/dev/null) || { echo "❌ SSH 连接失败"; exit 1; }

# 解析远程信息
REMOTE_HOME=$(echo "$REMOTE_INFO" | grep "^HOME=" | cut -d= -f2)
REMOTE_OS=$(echo "$REMOTE_INFO" | grep "^OS=" | cut -d= -f2)
REMOTE_OC=$(echo "$REMOTE_INFO" | grep "^OPENCLAW=" | cut -d= -f2)
REMOTE_GW=$(echo "$REMOTE_INFO" | grep "^GATEWAY=" | cut -d= -f2)
REMOTE_MEM=$(echo "$REMOTE_INFO" | grep "^MEM=" | cut -d= -f2)
REMOTE_DISK=$(echo "$REMOTE_INFO" | grep "^DISK=" | cut -d= -f2)

echo "  系统: $REMOTE_OS $(echo "$REMOTE_INFO" | grep "^ARCH=" | cut -d= -f2)"
echo "  内存: $REMOTE_MEM | 磁盘剩余: $REMOTE_DISK"
echo "  HOME: $REMOTE_HOME"
echo "  OpenClaw: $REMOTE_OC"
echo "  Gateway: $REMOTE_GW"

if [ "$REMOTE_OC" = "NOT_FOUND" ]; then
  echo "❌ 目标机器未安装 OpenClaw，请先安装"
  exit 1
fi
echo "✅ 环境探测完成"
echo ""

# ==================== Phase 2: 传输文件 ====================
echo "📦 Phase 2: 传输项目文件..."

if [ ! -d "$PROJECT_DIR" ]; then
  echo "❌ 项目目录不存在: $PROJECT_DIR"
  exit 1
fi

# 2.1 传输项目仓库到远程 projects/
REMOTE_PROJ="$REMOTE_HOME/projects/$PROJ_NAME"
cd "$PROJECT_DIR"
tar czf - --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='.venv' --exclude='venv' . | \
  $SSH_CMD "mkdir -p $REMOTE_PROJ && cd $REMOTE_PROJ && tar xzf -"
echo "  ✅ 项目仓库 → $REMOTE_PROJ/"

# 2.2 部署 Agent 配置
AGENT_COUNT=0
if [ -d "$PROJECT_DIR/agents" ]; then
  for agent_dir in "$PROJECT_DIR/agents"/*/; do
    [ -d "$agent_dir" ] || continue
    agent_name=$(basename "$agent_dir")
    tar czf - -C "$agent_dir" . | \
      $SSH_CMD "mkdir -p $REMOTE_HOME/.openclaw/agents/$agent_name/ && cd $REMOTE_HOME/.openclaw/agents/$agent_name/ && tar xzf -"
    echo "  📋 agent: $agent_name"
    AGENT_COUNT=$((AGENT_COUNT + 1))
  done
  echo "  ✅ $AGENT_COUNT 个 Agent 已部署"
fi

# 2.3 部署 Skills
if [ -d "$PROJECT_DIR/skills" ]; then
  SKILL_COUNT=$(find "$PROJECT_DIR/skills" -maxdepth 1 -type d | wc -l)
  SKILL_COUNT=$((SKILL_COUNT - 1))
  tar czf - -C "$PROJECT_DIR/skills" . | \
    $SSH_CMD "mkdir -p $REMOTE_HOME/.openclaw/skills/ && cd $REMOTE_HOME/.openclaw/skills/ && tar xzf -"
  echo "  ✅ $SKILL_COUNT 个 Skill 已部署"
fi

# 2.4 部署工作区文件（AGENTS.md, SOUL.md, USER.md 等）
if [ -d "$PROJECT_DIR/workspace" ]; then
  tar czf - -C "$PROJECT_DIR/workspace" . | \
    $SSH_CMD "cd $REMOTE_PROJ && tar xzf -"
  echo "  ✅ 工作区文件已部署"
fi

echo ""

# ==================== Phase 3: 配置注入（需要 deploy.json）====================
if [ -f "$DEPLOY_JSON" ]; then
  echo "⚙️  Phase 3: 配置注入 (deploy.json)..."
  
  # 将 deploy.json 传到远程
  cat "$DEPLOY_JSON" | $SSH_CMD "cat > /tmp/_deploy_manifest.json"
  
  # 远程执行配置注入
  $SSH_CMD "python3 << 'PYEOF'
import json, sys, os

REMOTE_HOME = os.path.expanduser('~')
config_path = os.path.join(REMOTE_HOME, '.openclaw', 'openclaw.json')
manifest_path = '/tmp/_deploy_manifest.json'

# 读取现有配置
try:
    with open(config_path) as f:
        config = json.load(f)
except Exception as e:
    print(f'❌ 无法读取 OpenClaw 配置: {e}')
    sys.exit(1)

# 读取部署清单
with open(manifest_path) as f:
    manifest = json.load(f)

changes = []

# --- 1. 注入 Providers ---
providers = manifest.get('providers', {})
for name, provider in providers.items():
    existing = config.get('models', {}).get('providers', {}).get(name)
    if existing:
        print(f'  ⚠️  Provider \"{name}\" 已存在，跳过（不覆盖）')
    else:
        config.setdefault('models', {}).setdefault('providers', {})[name] = provider
        changes.append(f'Provider: +{name}')
        print(f'  ✅ Provider \"{name}\" 已添加')

# --- 2. 注入 Agent 列表 ---
agents_list = manifest.get('agents', [])
if agents_list:
    existing_ids = {a['id'] for a in config.get('agents', {}).get('list', [])}
    new_agents = [a for a in agents_list if a['id'] not in existing_ids]
    if new_agents:
        config.setdefault('agents', {}).setdefault('list', []).extend(new_agents)
        names = [a['id'] for a in new_agents]
        changes.append(f'Agents: +{names}')
        print(f'  ✅ 新增 {len(new_agents)} 个 Agent: {names}')
    else:
        print(f'  ⚠️  所有 Agent 已存在，跳过')

# --- 3. 注入 Channel 账号 ---
channels = manifest.get('channels', {})
for ch_name, ch_config in channels.items():
    accounts = ch_config.get('accounts', {})
    if accounts:
        existing_ch = config.setdefault('channels', {}).setdefault(ch_name, {})
        existing_accounts = existing_ch.get('accounts', {})
        
        # 合并：不覆盖已有账号
        for acc_name, acc_config in accounts.items():
            if acc_name in existing_accounts:
                # 但确保 agent 字段存在
                if 'agent' in acc_config and 'agent' not in existing_accounts[acc_name]:
                    existing_accounts[acc_name]['agent'] = acc_config['agent']
                    changes.append(f'Channel {ch_name}.{acc_name}: +agent routing')
                    print(f'  ✅ {ch_name}/{acc_name}: 补充 agent 路由 → {acc_config[\"agent\"]}')
                else:
                    print(f'  ⚠️  {ch_name}/{acc_name} 已存在，跳过')
            else:
                existing_accounts[acc_name] = acc_config
                changes.append(f'Channel: +{ch_name}/{acc_name}')
                print(f'  ✅ {ch_name}/{acc_name} 已添加 → agent: {acc_config.get(\"agent\", \"default\")}')
        
        existing_ch['accounts'] = existing_accounts
        
        # 复制 channel 级别配置（proxy, subscribe 等）
        for key in ch_config:
            if key != 'accounts' and key not in existing_ch:
                existing_ch[key] = ch_config[key]
                print(f'  ✅ {ch_name}.{key} 已配置')

# --- 4. 权限配置 ---
tools = manifest.get('tools', {})
if tools:
    for key, val in tools.items():
        config.setdefault('tools', {})[key] = val
        changes.append(f'Tools: {key}')
        print(f'  ✅ tools.{key} 已配置')

# --- 5. 工作区 ---
workspace = manifest.get('workspace')
if workspace:
    # 支持 \${HOME} 和 \${PROJECT} 变量替换
    workspace = workspace.replace('\${HOME}', REMOTE_HOME)
    workspace = workspace.replace('\${PROJECT}', manifest.get('project_name', ''))
    config.setdefault('agents', {}).setdefault('defaults', {})['workspace'] = workspace
    changes.append(f'Workspace: {workspace}')
    print(f'  ✅ workspace → {workspace}')

# --- 6. 其他顶层配置 ---
extras = manifest.get('config_patches', {})
for dotpath, val in extras.items():
    parts = dotpath.split('.')
    obj = config
    for p in parts[:-1]:
        obj = obj.setdefault(p, {})
    obj[parts[-1]] = val
    changes.append(f'Patch: {dotpath}')
    print(f'  ✅ {dotpath} 已设置')

# 写入
if changes:
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f'\\n✅ 配置注入完成 ({len(changes)} 项变更)')
else:
    print('\\n✅ 无需变更')

# 清理
os.remove(manifest_path)
PYEOF
"
else
  echo "⚙️  Phase 3: 基础权限配置（无 deploy.json）..."
  $SSH_CMD "python3 << 'PYEOF'
import json, os

config_path = os.path.join(os.path.expanduser('~'), '.openclaw', 'openclaw.json')
with open(config_path) as f:
    c = json.load(f)

changed = False

# tools.profile -> full
if c.get('tools', {}).get('profile') != 'full':
    c.setdefault('tools', {})['profile'] = 'full'
    changed = True; print('  tools.profile → full')

# tools.exec
e = c.get('tools', {}).get('exec', {})
if e.get('security') != 'full' or e.get('ask') != 'off':
    c.setdefault('tools', {})['exec'] = {'security': 'full', 'ask': 'off'}
    changed = True; print('  tools.exec → full/off')

# tools.elevated
elev = c.get('tools', {}).get('elevated', {})
if not isinstance(elev, dict) or not elev.get('enabled'):
    c.setdefault('tools', {})['elevated'] = {'enabled': True}
    changed = True; print('  tools.elevated → enabled')

# workspace
proj = os.path.join(os.path.expanduser('~'), 'projects', '$PROJ_NAME')
if c.get('agents', {}).get('defaults', {}).get('workspace') != proj:
    c.setdefault('agents', {}).setdefault('defaults', {})['workspace'] = proj
    changed = True; print(f'  workspace → {proj}')

if changed:
    with open(config_path, 'w') as f:
        json.dump(c, f, indent=2, ensure_ascii=False)
    print('✅ 配置已更新')
else:
    print('✅ 配置无需变更')
PYEOF
"
fi
echo ""

# ==================== Phase 4: 重启 Gateway ====================
echo "🔄 Phase 4: 重启 Gateway..."
$SSH_CMD '
  PIDS=$(pgrep -f "openclaw-gateway" 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    for pid in $PIDS; do
      kill -USR1 $pid 2>/dev/null || true
    done
    echo "  SIGUSR1 热重载已发送"
    sleep 8
  else
    echo "  Gateway 未运行，尝试启动..."
    openclaw gateway install 2>/dev/null || openclaw gateway start 2>/dev/null || true
    sleep 5
  fi
  
  if pgrep -f "openclaw-gateway" >/dev/null 2>&1; then
    echo "✅ Gateway 运行中"
  else
    echo "❌ Gateway 启动失败"
    tail -5 ~/.openclaw/logs/gateway.err.log 2>/dev/null
    exit 1
  fi
'
echo ""

# ==================== Phase 5: 验证 ====================
echo "🔍 Phase 5: 验证部署..."
$SSH_CMD '
  echo "--- 配置检查 ---"
  errs=$(tail -10 ~/.openclaw/logs/gateway.err.log 2>/dev/null | grep -i "invalid\|Unrecognized\|Unknown" | tail -3)
  [ -n "$errs" ] && echo "⚠️  警告: $errs" || echo "✅ 无配置错误"
  
  echo ""
  echo "--- 连接状态 ---"
  for kw in "ws client ready" "connected" "authenticated"; do
    count=$(tail -50 ~/.openclaw/logs/gateway.log 2>/dev/null | grep -c "$kw" || echo 0)
    [ "$count" -gt 0 ] && echo "  $kw: $count"
  done
  
  echo ""
  echo "--- Agent 列表 ---"
  python3 -c "
import json, os
p = os.path.join(os.path.expanduser(\"~\"), \".openclaw\", \"openclaw.json\")
with open(p) as f:
    c = json.load(f)
for a in c.get(\"agents\",{}).get(\"list\",[]):
    m = a.get(\"model\",{})
    primary = m.get(\"primary\",\"default\") if isinstance(m, dict) else m
    print(f\"  {a[\"id\"]}: {primary}\")
" 2>/dev/null || echo "  (无法读取)"
  
  echo ""
  echo "--- Channel 账号 ---"
  python3 -c "
import json, os
p = os.path.join(os.path.expanduser(\"~\"), \".openclaw\", \"openclaw.json\")
with open(p) as f:
    c = json.load(f)
for ch_name, ch in c.get(\"channels\",{}).items():
    if isinstance(ch, dict) and \"accounts\" in ch:
        for acc, cfg in ch[\"accounts\"].items():
            agent = cfg.get(\"agent\", \"(未绑定)\")
            print(f\"  {ch_name}/{acc} → {agent}\")
    elif isinstance(ch, dict):
        print(f\"  {ch_name}: 单账号\")
" 2>/dev/null || echo "  (无法读取)"
'

echo ""
echo "🎉 部署完成！"
echo ""
echo "后续操作:"
echo "  1. 在对应渠道 @Bot 测试回复"
echo "  2. 更新项目: cd $PROJECT_DIR && git pull && $0 $TARGET $PROJECT_DIR $SSH_KEY"

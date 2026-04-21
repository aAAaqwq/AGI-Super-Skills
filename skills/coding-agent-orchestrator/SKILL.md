# coding-agent-orchestrator
> 编码 Agent 编排调度——解析 Claude CLI 和 ACPX 二进制路径，支持多编码 Agent 协同

## 使用场景
- 在多 Agent 环境中调度 Claude Code 或 ACPX 编码 Agent
- 自动解析编码 Agent 可执行文件路径（支持环境变量覆盖、本地安装、系统 PATH）
- 作为 coding workflow 的底层 CLI 解析器

## 使用方法
```bash
# 在 shell 脚本中 source 使用
source ~/clawd/skills/coding-agent-orchestrator/scripts/lib/resolve-cli.sh

# 解析 Claude CLI 路径
claude_bin=$(resolve_claude_bin)
echo "Claude: $claude_bin"

# 解析 ACPX 路径
acpx_bin=$(resolve_acpx_bin)
echo "ACPX: $acpx_bin"

# 环境变量覆盖
export CODING_AGENT_CLAUDE_BIN=/custom/path/to/claude
export CODING_AGENT_ACPX_CMD=/custom/path/to/acpx
```

## 路径解析优先级
1. 环境变量 `CODING_AGENT_CLAUDE_BIN` / `CODING_AGENT_ACPX_CMD`
2. `~/.claude/local/claude`（本地安装）
3. 系统 PATH（`which claude` / `which acpx`）

## 配置要求
- Bash
- Claude Code 或 ACPX 已安装（至少一个）

## 相关文件
- `scripts/lib/resolve-cli.sh` — CLI 路径解析器

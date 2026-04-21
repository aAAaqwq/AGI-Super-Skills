---
name: workspace-directory-manager
description: Workspace directory manager — maintain cleanliness of ~/.openclaw/ and ~/clawd/
---

# Skill: OpenClaw & Workspace Directory Manager

## 触发条件
- "整理目录"、"清理文件夹"、"目录结构"
- "清理 tmp"、"清理日志"、"清理临时文件"
- "skills 整理"、"重复 skill 检查"
- "磁盘空间"、"空间不足"
- "workspace 维护"、"openclaw 维护"

## 职责
维护 `~/.openclaw/` 和 `~/clawd/` 两个目录的整洁和秩序。
**专属 agent: 小ops** — CEO 指定的小ops专用 skill。

## 目录结构规范

### ~/.openclaw/ （系统配置目录）
```
~/.openclaw/
├── openclaw.json          # 主配置（唯一真相源）
├── .env                   # 运行时环境变量（由 rebuild-env.sh 生成，chmod 600）
├── agents/
│   └── <agent-id>/agent/
│       ├── agent.json     # Agent 身份+模型+workspace
│       ├── models.json    # 模型缓存（自动生成）
│       ├── SOUL.md        # Agent 灵魂文件
│       └── AGENTS.md      # Agent 行为规则
├── skills/                # 全局安装的 Skill
├── logs/                  # 运行日志
└── memory/                # 记忆文件
```

### ~/clawd/ （工作空间目录）
```
~/clawd/
├── MEMORY.md              # 长期记忆（main session 维护，只读）
├── SOUL.md                # CEO 灵魂文件
├── AGENTS.md              # 团队规则
├── USER.md                # 用户画像
├── TOOLS.md               # 工具手册
├── IDENTITY.md            # 身份文件
├── HEARTBEAT.md           # 心跳规则
├── memory/                # 日记忆 YYYY-MM-DD.md
├── projects/              # 独立项目
├── reports/               # 研究报告
├── skills/                # 自研 Skill
├── scripts/               # 全局脚本
├── docs/                  # 文档
├── tmp/                   # 临时文件（可定期清理）
└── repos/                 # 代码仓库
```

## 执行命令

### 完整目录健康检查
```bash
python3 ~/clawd/skills/workspace-directory-manager/scripts/health-check.py
```

### 清理临时文件
```bash
python3 ~/clawd/skills/workspace-directory-manager/scripts/cleanup-tmp.py --dry-run   # 预览
python3 ~/clawd/skills/workspace-directory-manager/scripts/cleanup-tmp.py               # 执行
```

### 重复 Skill 检测
```bash
python3 ~/clawd/skills/workspace-directory-manager/scripts/detect-duplicates.py
```

### 磁盘空间报告
```bash
python3 ~/clawd/skills/workspace-directory-manager/scripts/disk-usage.py
```

### 目录结构可视化
```bash
python3 ~/clawd/skills/workspace-directory-manager/scripts/tree-view.py --path ~/clawd --depth 2
python3 ~/clawd/skills/workspace-directory-manager/scripts/tree-view.py --path ~/.openclaw --depth 2
```

## 清理规则

### tmp/ 清理
- `~/clawd/tmp/` 中超过 7 天的文件自动标记删除
- 不删除正在被 cron/session 使用的文件

### 日志清理
- `~/.openclaw/logs/` 中超过 30 天的日志自动清理
- 保留最近 7 天的详细日志

### Agent Session 残留
- 检查 agents/*/agent/ 下异常大的文件
- models.json 如果超过 10MB → 标记清理

### 重复 Skill 清理
- 对比 `~/.openclaw/skills/` 和 `~/clawd/skills/`
- 同名 skill 以 `~/.openclaw/skills/` 为准
- 功能重复的 skill 报告给 CEO 决定

## 安全铁律
1. **永不删除** `MEMORY.md`、`SOUL.md`、`AGENTS.md`、`USER.md`、`TOOLS.md`
2. **清理前 dry-run**，确认无误再执行
3. **用 `trash` 而非 `rm`**（可恢复）
4. **不修改** `openclaw.json`（除非 CEO 明确指示）
5. **memory/ 文件只追加不覆盖**

## 巡检频率
- 每 6 小时（通过 heartbeat 或 cron）运行 health-check
- 每周日运行一次 cleanup + disk-usage

## 更新记录
- 2026-03-29: 初版创建

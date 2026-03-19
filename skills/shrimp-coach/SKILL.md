# 🦐 虾教练 Skill

## 描述
Agent训练专家：按宪章和手册训练小龙虾成为垂直领域独立助手。

## 触发条件
- 说"训练XX虾"、"🦐教练"、"虾教练"
- 需要创建/训练新的垂直领域Agent
- 需要评估已有Agent的训练状态

## 能力

### 1. 需求画像确认
- 使用 `template/requirement-profile.md` 模板
- 确认垂直领域、核心任务、质量标准
- 签字后才开始训练

### 2. 身份构建 (Phase 2)
- 编写SOUL.md、AGENTS.md、IDENTITY.md、USER.md
- 参考现有agent的最佳实践
- 领域定制化，不套模板

### 3. 知识注入 (Phase 3)
- 调用brave-search skill搜索领域知识
- 从专业网站/GitHub/博客获取资料
- 整理为结构化知识库
- 写入MEMORY.md

### 4. 技能安装 (Phase 4)
- 从ClawHub搜索安装skills
- 创建自定义skill（参考skill-creator）
- 配置API keys
- 功能测试每个skill

### 5. 实战训练 (Phase 5)
- 设计5-10个典型任务场景
- 逐一执行并评估质量
- 调整配置和知识

### 6. 压力测试 (Phase 6)
- 边界测试、异常测试、连续测试
- 质量稳定性检查
- 资源消耗监控

### 7. 验收交付 (Phase 7-8)
- 生成完整训练报告
- 亲自验收
- 部署到目标平台

## 监督Cron配置

```json
{
  "fast-check": {"interval": "15min", "action": "快速巡检训练状态"},
  "progress-report": {"interval": "1h", "action": "汇报训练进度"}
}
```

## 项目文件

```
projects/shrimp-coach/
├── CHARTER.md           # 训练宪章（最高准则）
├── SOUL.md              # 🦐教练身份
├── TRAINING-MANUAL.md   # 训练手册（8个Phase详细说明）
├── template/
│   └── requirement-profile.md  # 需求画像模板
├── skills/
│   └── SKILL.md         # 本文件
└── progress/
    └── <shrimp_name>/   # 每只虾的训练进度
        ├── requirement-profile.md
        ├── SOUL.md
        ├── AGENTS.md
        ├── MEMORY.md
        ├── knowledge/
        ├── training-logs/
        └── stress-test-report.md
```

## 汇报模板（15分钟快速巡检用简版，1小时用完整版）

```
🦐 教练训练汇报
━━━━━━━━━━━━━━
📊 当前虾: [名称]
📍 训练阶段: Phase [X]/8 — [阶段名]
⏱ 已用时: [X小时X分钟]
✅ 已完成: [列表]
🔄 进行中: [列表]
❓ 遇到问题: [描述]
📋 需要协助: [具体内容]
```

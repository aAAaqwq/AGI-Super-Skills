---
name: skill-creator
description: "Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations."
license: MIT
metadata:
  version: 1.0.0
  domains: [skill-creation, authoring, documentation]
  type: meta
---

# Skill 创建指南

## 当使用此技能

- 创建新的 skill
- 更新现有 skill
- 设计 skill 结构
- 编写 skill 文档

## Skill 结构

```
skill-name/
├── SKILL.md          # 必需：技能描述
├── SKILL_SPEC.md     # 可选：详细规范
├── examples/         # 可选：示例文件
└── scripts/          # 可选：辅助脚本
```

## SKILL.md 格式

```yaml
---
name: skill-name
description: 简短描述
license: MIT
metadata:
  version: 1.0.0
  domains: [category]
  type: [tool|specialist|automation]
---

# 技能名称

## 当使用此技能
- 场景 1
- 场景 2

## 能力
1. 功能 1
2. 功能 2

## 触发词
- "关键词 1"
- "关键词 2"
```

## 最佳实践

- **简洁**: 每个技能专注一个领域
- **实用**: 解决实际问题
- **可测试**: 提供明确触发词
- **文档**: 清晰的使用说明

## 触发词

- "创建 skill"
- "写个技能"
- "skill 模板"

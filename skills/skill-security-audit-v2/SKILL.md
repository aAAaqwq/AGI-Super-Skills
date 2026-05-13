---
name: skill-security-audit
description: |
  已安装 Skills 的安全审计工具。用于批量审计 Skills 的安全性，包括命令执行、网络访问、文件访问、数据泄露、依赖风险、提示词越权和触发条件检查。适用于用户提供 Skills 列表和文件内容时进行安全扫描、护栏审查、提示词越权审查或强化建议。
---

# Skill Security Audit 🔐

对已安装的 Skills 进行安全审计，识别风险行为并提供修复建议。

## 审计类别

| # | 类别 | 说明 |
|---|------|------|
| 1 | 命令执行 | 检查不安全的 shell/python/node 执行 |
| 2 | 网络访问 | 检查未经授权的网络请求 |
| 3 | 文件访问 | 检查过度文件系统访问 |
| 4 | 数据泄露 | 检查未授权数据外传 |
| 5 | 依赖风险 | 检查不安全依赖 |
| 6 | 提示词越权 | 检查绕过安全边界 |
| 7 | 触发条件 | 检查描述是否过宽 |

## 严重程度

| 等级 | 说明 |
|------|------|
| **Critical** | 明显允许危险操作 |
| **High** | 重大滥用风险 |
| **Medium** | 潜在滥用风险 |
| **Low** | 小问题 |
| **Info** | 设计选择 |

## 使用方法

### 1. 准备审计材料

用户提供：
- 已安装 Skills 列表
- 每个 Skill 的文件内容（SKILL.md、scripts、references 等）

### 2. 执行审计

按照审查矩阵检查每个 Skill：
1. 盘点文件
2. 分类能力
3. 检查风险
4. 收集证据
5. 评级
6. 修复

### 3. 输出报告

每个 Skill 的报告结构：
```
# [skill name]

## verdict
- overall rating: [block/review/acceptable]
- top risks: [风险列表]

## findings
- category:
- severity:
- evidence:
- impact:
- remediation:

## replacement text
修复建议文本
```

## 审查矩阵

### 1. 任意命令执行
- ⚠️ 高风险：允许任意 bash/sh/powershell/python/node 执行
- ✅ 修复：限制为固定命令列表

### 2. 外部网络访问
- ⚠️ 高风险：访问任意 URL
- ✅ 修复：限制为白名单域名

### 3. 本地文件访问
- ⚠️ 高风险：读取整个目录/主目录
- ✅ 修复：限制为用户提供的文件

### 4. 数据泄露
- ⚠️ 高风险：未经确认发送/上传数据
- ✅ 修复：需要明确用户确认

### 5. 依赖风险
- ⚠️ 高风险：未固定版本的可疑依赖
- ✅ 修复：固定版本，使用标准库

### 6. 提示词越权
- ⚠️ 高风险：忽略系统/策略约束
- ✅ 修复：重述系统规则优先

### 7. 触发条件过宽
- ⚠️ 高风险：描述过于宽泛
- ✅ 修复：精确触发场景

## 输出要求

最终报告包含：
1. 每个 Skill 的详细报告
2. 总体摘要
3. 最高风险项
4. 修复优先级

## 示例

### 输入
```
Skills: [peekaboo, admapix, humanizer]
文件内容: SKILL.md, scripts/, ...
```

### 输出
```
# Portfolio Summary
- audited skills: 3
- block: 0
- review before use: 1
- acceptable: 2

- most common risk patterns: [列表]
- immediate remediation priorities: [优先级]
```

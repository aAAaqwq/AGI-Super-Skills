# 🏢 AGI-Super-Team Skills 仓库

> 420 个 Agent 技能，覆盖开发、运维、内容、调研、财务、营销、法务、产品、协作、AI 基础设施十大领域。

## 📂 分类索引

| 分类 | 数量 | 说明 | 索引 |
|------|------|------|------|
| 🔧 [dev](#dev-开发类) | 48 | 代码编写、架构设计、代码审查、测试 | [dev-skills.md](dev-skills.md) |
| 🖥️ [ops](#ops-运维类) | 41 | 服务器管理、部署、监控、巡检 | [ops-skills.md](ops-skills.md) |
| ✍️ [content](#content-内容类) | 83 | 写作、发布、编辑、排版、模板 | [content-skills.md](content-skills.md) |
| 🔍 [research](#research-调研类) | 31 | 深度研究、情报收集、趋势分析 | [research-skills.md](research-skills.md) |
| 💰 [finance](#finance-财务类) | 32 | 量化交易、投资分析、成本追踪 | [finance-skills.md](finance-skills.md) |
| 📢 [marketing](#marketing-营销类) | 28 | 推广策略、广告投放、客户管理 | [marketing-skills.md](marketing-skills.md) |
| ⚖️ [compliance](#compliance-法务合规类) | 18 | 合同审核、合规检查、隐私保护 | [compliance-skills.md](compliance-skills.md) |
| 📋 [product](#product-产品类) | 23 | 项目管理、需求分析、竞品分析 | [product-skills.md](product-skills.md) |
| 🤝 [communication](#communication-沟通协作类) | 27 | 消息推送、飞书、企微、邮件 | [communication-skills.md](communication-skills.md) |
| 🤖 [ai-infra](#ai-infra-ai基础设施类) | 33 | 模型管理、RAG、Embedding、Prompt | [ai-infra-skills.md](ai-infra-skills.md) |
| 📦 [other](#other-其他) | 56 | 未分类技能 | [other-skills.md](other-skills.md) |

## 🔑 核心技能 (自研)

以下为本团队自主研发的核心技能：

### 多平台发布
| Skill | 平台 | 说明 |
|-------|------|------|
| [xhs-smart-publisher](xhs-smart-publisher/) | 小红书 | Playwright 自动发布，CES 优化 |
| [wechat-mp-publisher](wechat-mp-publisher/) | 微信公众号 | API + Browser 双通道 |
| [douyin-smart-publish](douyin-smart-publish/) | 抖音 | 视频+图文双模式，creator 实测 |
| [zsxq-publisher](zsxq-publisher/) | 知识星球 | API 驱动，4种内容类型 |
| [juejin-smart-publish](juejin-smart-publish/) | 掘金 | Markdown 编辑器，API 双通道 |

### 系统基础设施
| Skill | 说明 |
|-------|------|
| [token-reporter](token-reporter/) | 每日 Token 消耗 + 产出上报到飞书 |
| [feishu-automation](feishu-automation/) | 飞书全通道自动化 (Bitable/消息/文档) |
| [content-factory](content-factory/) | 多平台热点采集 + 选题评分 + 内容生成 |
| [qmd](qmd/) | Quick Markdown Search 本地知识库 |
| [api-quota-monitor](api-quota-monitor/) | API 供应商额度监控 |

### 量化交易
| Skill | 说明 |
|-------|------|
| [polymarket-skill](polymarket-skill/) | Polymarket 链上预测市场交易 |
| [backtesting-frameworks](backtesting-frameworks/) | 策略回测框架 |

## 📊 统计

- **总 Skill 数**: 420
- **有 SKILL.md**: 408
- **安装来源**: ClawdHub (skills.sh), 自研, 第三方
- **最后更新**: 2026-03-18

## 🗂️ 仓库结构

```
skills/
├── README.md                    ← 本文件
├── dev-skills.md                ← 开发类技能索引
├── ops-skills.md                ← 运维类技能索引
├── content-skills.md            ← 内容类技能索引
├── research-skills.md           ← 调研类技能索引
├── finance-skills.md            ← 财务类技能索引
├── marketing-skills.md          ← 营销类技能索引
├── compliance-skills.md         ← 法务合规类技能索引
├── product-skills.md            ← 产品类技能索引
├── communication-skills.md      ← 沟通协作类技能索引
├── ai-infra-skills.md           ← AI 基础设施类技能索引
├── other-skills.md              ← 未分类技能索引
├── xhs-smart-publisher/         ← 各 skill 目录 (420个)
├── wechat-mp-publisher/
├── ...
```

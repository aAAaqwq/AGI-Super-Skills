# 🚀 AGI Super Team

English | [中文](./README_CN.md)

> **285+ 精选 AI 技能 + 13 个即开即用的 Agent 模板** — 基于 [OpenClaw](https://github.com/openclaw/openclaw)，打造你自己的 AI 原生公司。

## 💡 这是什么？

一个**即插即用的 AI 团队模板** — 用 OpenClaw 在几分钟内部署一个完整的虚拟公司。每个 Agent 都有独立的角色、性格和技能栈，完全可自定义：换模型、改名字、加技能。

## 📊 概览

| 指标 | 数值 |
|------|------|
| **技能** | 360+ |
| **分类** | 18 |
| **Agent** | 13（完全可定制） |
| **框架** | [OpenClaw](https://github.com/openclaw/openclaw) |

## 🏗️ 架构

```
你 (CEO / 创建者)
  └── AI 协调者 (主 Agent)
        ├── 工程师 — 代码开发、架构设计、调试
        ├── 量化员 — 交易策略、市场分析、回测
        ├── 数据官 — 爬虫、ETL、数据分析
        ├── 运维官 — 监控、部署、基础设施
        ├── 内容官 — 写作、文案、内容发布
        ├── 研究员 — 深度调研、论文、情报收集
        ├── 财务官 — 核算、盈亏分析、财务建模
        ├── 营销官 — SEO、广告、增长策略
        ├── 项目官 — 项目规划、任务跟踪、质量验收
        ├── 法务官 — 合规、合同、法规
        ├── 产品官 — 设计、竞品分析、用户体验
        └── 销售官 — 获客、商务拓展、客户分析
```

> **可扩展**：添加更多 Agent（HR、客服等），只需创建新的 `agents/<id>/` 文件夹。

## 👥 Agent 模板

| ID | 角色 | 默认模型 | 可定制 |
|-----|------|------|:---:|
| `main` | 协调者 / CEO | `claude-opus-4-6` | ✅ |
| `code` | 首席工程师 | `glm-5` | ✅ |
| `quant` | 首席交易官 | `glm-5` | ✅ |
| `data` | 首席数据官 | `glm-5` | ✅ |
| `ops` | 首席运维官 | `glm-5` | ✅ |
| `content` | 首席内容官 | `glm-5` | ✅ |
| `research` | 首席研究官 | `glm-5` | ✅ |
| `finance` | 首席财务官 | `glm-5` | ✅ |
| `market` | 首席营销官 | `glm-5` | ✅ |
| `pm` | 首席项目官 | `glm-5` | ✅ |
| `law` | 首席法务官 | `MiniMax-M2.5` | ✅ |
| `product` | 首席产品官 | `glm-5` | ✅ |
| `sales` | 首席销售官 | `glm-5` | ✅ |

> 每个 Agent 配置位于 [`agents/<id>/agent.json`](./agents/) — 已脱敏的模板，可直接填入你的 API 密钥和个性化设置。

## 🛠️ 技能分类

| 分类 | 数量 | 亮点 |
|------|:----:|------|
| [⚙️ OpenClaw 工具](#-openclaw-工具) | 25 | 配置助手、认证管理、定时任务、Token 监控、模型切换 |
| [🤖 AI Agent 模式](#-ai-agent-模式) | 25 | 多 Agent 编排、并行执行、第一性原理思维 |
| [🔧 开发](#-开发) | 35 | 前后端开发、Docker、Git、TDD、API 设计、认证系统 |
| [💰 交易与金融](#-交易与金融) | 32 | 加密货币交易、Polymarket、DeFi、投资组合管理、CT 监控 |
| [📝 内容与写作](#-内容与写作) | 30 | SEO 写作、社交媒体、爆款内容、反 AI 味、小红书 |
| [📊 数据与分析](#-数据与分析) | 21 | 网页抓取、DuckDB、CSV 管道、arXiv、多引擎搜索 |
| [📈 营销与 SEO](#-营销与-seo) | 19 | SEO 审计、GEO 优化、A/B 测试、流失预防 |
| [🎨 设计与媒体](#-设计与媒体) | 15 | 图像生成（Gemini 3 Pro）、UI/UX、幻灯片、品牌 |
| [🌐 浏览器自动化](#-浏览器自动化) | 7 | Playwright、Chrome、AI 驱动浏览、Agent 浏览器 |
| [🏢 商业与战略](#-商业与战略) | 15 | SaaS 启动、竞品拆解、财务建模、个人理财 |
| [📋 项目管理](#-项目管理) | 18 | PRD 编写、路线图、Scrum、团队协调、日报 |
| [🧠 知识与研究](#-知识与研究) | 6 | 向量记忆、Brave 搜索、学术研究、语义搜索 |
| [💬 通讯](#-通讯) | 14 | 邮件、飞书、微信、跨实例通信 |
| [🔌 SaaS 集成](#-saas-集成) | 63 | Notion、Airtable、HubSpot、Stripe、Shopify 等 55+ |
| [⚙️ DevOps 与基础设施](#-devops-与基础设施) | 9 | AWS、Docker、Linux 排障、可观测性、Runbook |
| [🔒 安全](#-安全) | 7 | 代码审查、GDPR、PCI 合规、安全审计 |
| [⚖️ 法律与合规](#-法律与合规) | 6 | 合同、海关/贸易、劳动法、法律顾问 |
| [🧩 其他](#-其他) | 15 | RSS、日历、演示文稿、技能创建、设计思维 |

> 📋 完整技能列表请查看 [英文 README](./README.md)

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team

# 2. 安装单个技能
cp -r skills/<技能名> ~/.openclaw/skills/

# 3. 或使用软链接（方便更新）
ln -s $(pwd)/skills/<技能名> ~/.openclaw/skills/

# 4. 部署 Agent 模板
cp -r agents/<agent-id> ~/.openclaw/agents/
# 然后编辑 agent.json，填入你的 API 密钥和偏好设置
```

## 🧩 创建你自己的团队

Agent 配置都是**模板** — 根据你的需求自定义：

1. **重命名 Agent** — 在 `agent.json` 中修改显示名和性格
2. **更换模型** — 使用任何 OpenClaw 兼容模型（GPT、Claude、Gemini、GLM 等）
3. **混搭技能** — 将任意技能组合分配给任意 Agent
4. **添加 Agent** — 复制现有 `agents/<id>/` 文件夹创建新角色
5. **横向扩展** — 通过 Tailscale 在多台机器上运行 10、50 甚至 100+ Agent

## 🤝 贡献

欢迎 PR！添加新技能：

1. 创建 `skills/<你的技能>/SKILL.md`，写上描述和使用说明
2. 将脚本放到 `skills/<你的技能>/scripts/`
3. 提交 PR

## ⭐ 给个 Star

如果这个项目帮助你构建了 AI 团队，请给个 ⭐！

每一个 Star 都是我们持续添加技能、优化 Agent 模板、打造更好工具的动力。

<a href="https://star-history.com/#aAAaqwq/AGI-Super-Team&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=aAAaqwq/AGI-Super-Team&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=aAAaqwq/AGI-Super-Team&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=aAAaqwq/AGI-Super-Team&type=Date" />
 </picture>
</a>

## 📄 开源协议

MIT

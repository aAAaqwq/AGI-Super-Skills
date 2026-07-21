<p align="center">
  <img src="assets/banner.png" alt="AGI Super Team — 以证据为基础的 AI 团队，服务真实成果" width="100%">
</p>

<h1 align="center">AGI Super Team</h1>

<p align="center"><strong>Evidence-backed AI teams for real outcomes</strong><br/>以证据为基础的 AI 团队，服务真实成果</p>

<p align="center">
  <a href="./README.md">English</a> ·
  <a href="#安全快速开始">快速开始</a> ·
  <a href="#五分钟安装凭据">安装凭据</a> ·
  <a href="#按成果浏览技能">技能分类</a> ·
  <a href="#仓库架构">仓库架构</a> ·
  <a href="./docs/guides/">实用指南</a> ·
  <a href="./CONTRIBUTING.md">参与贡献</a>
</p>

## 这个仓库是什么

AGI Super Team 为现有编程 Agent 工具提供可安装的 AI 团队包、角色指令和可复用技能。

它不是模型或 Agent 运行时。它提供有版本记录的工作区配置，帮助用户在人工审批门禁下完成规划、实现、审查和沟通。

项目有三项核心约束：

- **写入前先检查：** 通用安装器会预览全部目标位置，只有显式指定 `--apply` 才会写入。
- **单一事实源：** Agent、团队包、本地依赖和外部建议统一来自经过验证的 manifest（清单）。
- **先有证据再做主张：** 兼容性和成果必须有与受测版本匹配的凭据，否则保持待验证状态。

交易、法律、安全、医疗、发布和部署工作仍需相应领域的人工审查。

## 安全快速开始

使用 Codex？请先查看[精选原生包](./.codex/INDEX.md)。评估通用工作区文件？请继续执行下面的步骤。

克隆 `main`，记录你实际审查的 commit，再预览 Solo Founder 团队包。安装器需要 Bash 和 Node.js；仓库验证还需要 npm 与 Python 3。

```bash
git clone --depth 1 --branch main https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team
git rev-parse HEAD
./install.sh --source "$PWD" --destination /path/to/review-workspace solo-founder
```

核对来源、目标目录、所选 Agent 和计划写入的文件。确认预览符合预期后再应用：

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace --apply solo-founder
```

安装器会保留已有的人格文件和技能目录。发布暂存文件前，它会拒绝缺失的必需技能、来源符号链接和目标位置的符号链接。

如能检查固定版本的代码，请不要把远程脚本直接传给 shell。依赖、更新与恢复方法见 [setup.md](./setup.md)。

### 预览 → 应用 → 验证

<p align="center">
  <img src="assets/demo-install.gif" alt="终端演示：只读预览、显式应用和仓库检查通过" width="760">
</p>

动画是使用脱敏路径制作的 storyboard（分镜），不是运行证据。可先查看[分镜文字稿](./assets/demo-install.txt)，再使用下方凭据中的可复现命令。

## 五分钟安装凭据

仓库当前验证的是“安全完成安装”，尚未宣称安装后的团队已经取得经过验证的商业成果。

“五分钟”表示演练范围，不是速度承诺。此流程验证通用文件安装器；它不会配置模型，也不会让具体 Agent 工具自动加载生成的工作区。

创建一次性目标目录，证明预览没有写入，再应用并检查三个预期角色工作区：

```bash
AGI_SOLO_DEST="$(mktemp -d "${TMPDIR:-/tmp}/agi-solo-founder.XXXXXX")"

./install.sh --source "$PWD" --destination "$AGI_SOLO_DEST" solo-founder
test -z "$(find "$AGI_SOLO_DEST" -mindepth 1 -print -quit)"

./install.sh --source "$PWD" --destination "$AGI_SOLO_DEST" --apply solo-founder
test -f "$AGI_SOLO_DEST/workspace-ceo/SOUL.md"
test -f "$AGI_SOLO_DEST/workspace-pe/SOUL.md"
test -f "$AGI_SOLO_DEST/workspace-cco/SOUL.md"

npm test
npm run validate -- --warnings-as-errors
```

移动或删除任何内容前，先输出并检查 `$AGI_SOLO_DEST`。真实的自定义目标目录需要自行备份和审查；重复应用不是升级或回滚机制。

安装器复制完可审查文件后即停止，不会启动 Agent、自动编排角色或生成下列产物。下列内容只是为另行配置的工具准备的可选人工提示词。

| 工作区 | 职责 | 可选评估提示词 |
|---|---|---|
| `workspace-ceo` | 规划与质量门禁 | 起草一份决策备忘录，列出假设、备选方案、证据缺口和人工审批点。 |
| `workspace-pe` | 工程与交付 | 提出测试优先的实施计划，不部署，也不修改生产系统。 |
| `workspace-cco` | 发布沟通 | 起草三个发布帖版本，保留事实占位符，并附人工发布检查单。 |

该凭据证明安装过程可重复、仓库契约完整。跨工具任务表现仍为 **Validation pending（待验证）**，直至公开测试样例与当前 `main` 提交匹配。

## 按成果浏览技能

建议从聚焦的团队包或指南开始。完整目录是参考资料，不是推荐的新手路径。

| 入口 | 适合用途 |
|---|---|
| [Starter kits](./starter-kits/) | 独立开发者、内容流程或量化研究所需的小型角色组合 |
| [Agents](./agents/) | 通用安装器使用的人格、身份、工作流和工具指南 |
| [实用指南](./docs/guides/) | Codex、Claude Code 安装，兼容性、团队选择和工作边界 |
| [Codex 原生包](./.codex/INDEX.md) | 使用独立清单和同步策略维护的精选原生包 |
| [专题手册](./cookbook/) | 内容、提示词、研究和量化工作流的深入学习资料 |
| [Skills 概览](./skills/) | 支持等级、范围明确的起点和发现方式 |
| [自动生成的技能目录](./catalog/) | 按任务分类，覆盖每个权威实体技能；描述保留原技能语言 |

### 技能分类

| 构建与运行 | 获客与创作 | 决策与自动化 |
|---|---|---|
| [AI Agents 与编排](./catalog/#ai-agents-orchestration) | [营销、SEO 与增长](./catalog/#marketing-seo-growth) | [数据、分析与研究](./catalog/#data-analytics-research) |
| [软件工程](./catalog/#software-engineering) | [内容、媒体与发布](./catalog/#content-media-publishing) | [业务运营与战略](./catalog/#business-operations-strategy) |
| [云、DevOps 与可靠性](./catalog/#cloud-devops-reliability) | [销售、CRM 与客户成功](./catalog/#sales-crm-customer-success) | [应用与工作流自动化](./catalog/#apps-workflow-automation) |
| [安全、隐私与法律](./catalog/#security-privacy-legal) | [产品、设计与 UX](./catalog/#product-design-ux) | [金融、交易与市场](./catalog/#finance-trading-markets) |
| [专业领域与通用工具](./catalog/#general-utilities) | [中文平台工作流](./catalog/#chinese-platform-workflows) | |

### 团队包

| 团队包 | Agents | 适用场景 |
|---|---|---|
| [Solo Founder](./starter-kits/solo-founder/) | CEO、PE、CCO | 规划、工程和经人工审查的内容草稿 |
| [Content Creator](./starter-kits/content-creator/) | CCO、CDO、CMO | 调研、内容草稿和衡量计划 |
| [Quant Trader](./starter-kits/quant-trader/) | CQO、CDO、CFO | 研究、回测和风险审查，不用于实盘交易 |
| `full-team` | 清单中的全部 Agents | 广泛评估；通常建议从更小组合开始 |

## 选择分发方式

| 使用方式 | 仓库支持 | 安装路径 | 证据边界 |
|---|---|---|---|
| 通用本地工作区 | 由 `install.sh` 支持 | 预览、检查、再应用 | 安装器行为已有集成测试覆盖 |
| Codex | 独立维护的原生精选包 | 见 [`.codex/INDEX.md`](./.codex/INDEX.md) | 原生包和通用团队包是不同分发物 |
| Claude Code | 存在插件清单 | 检查 [`.claude-plugin/`](./.claude-plugin/) | 使用前确认当前客户端版本支持 |
| Cursor、Gemini、Kimi | 存在元数据或清单 | 检查对应文件 | 文件存在不代表功能完全一致 |

## 证据与验证

仓库契约从 Git 已跟踪文件和权威清单计算目录事实：

```bash
npm test
npm run validate
npm run validate -- --warnings-as-errors
```

只有当[验证凭据](./docs/data/verification-receipt.json)与当前 `main` 提交一致，且其中全部检查通过时，网页才会显示 `Verified`。

成果主张必须链接可复现输入、测试样例、版本、结果、限制和回滚路径。测试能够证明仓库行为，但不能保证商业表现。

## 仓库架构

```text
AGI-Super-Team/
├── config/          # 权威团队清单、schema 和已移除链接来源
├── agents/          # 角色、身份、工作流和工具指南
├── skills/          # Git 已跟踪实体技能；禁止符号链接
├── catalog/         # 自动生成的任务分类和机器可读技能索引
├── starter-kits/    # 聚焦的团队组合
├── install.sh       # 默认预览的通用工作区安装器
├── scripts/         # 仓库模型、验证器和 Pages 数据生成器
├── tests/           # 仓库、安装器、站点数据与 SEO 契约
├── docs/            # Evidence First 展示站和人工编辑指南
├── growth/          # 经人工审查的发布与衡量手册
└── assets/          # README、社交预览、Logo 和演示素材
```

控制流如下：

```text
config/team-manifest.json
  → scripts/repository_model.py
  → install.sh + 验证器 + tests

config/external-skill-sources.json
  → 已删除机器绑定链接的可移植来源记录
```

README 不是库存事实源。具体契约见[团队清单](./config/team-manifest.json)、[仓库模型](./scripts/repository_model.py)和[贡献规范](./CONTRIBUTING.md)。

## 团队拓扑

```text
创始人 / 操作者
└── CEO — 协调与质量门禁
    ├── CTO / PE — 架构与实现
    ├── CPO / CCO / CMO — 产品、内容与增长
    ├── CQO / CFO / CDO — 量化研究、财务与数据
    ├── CLO / CRO / CSO / COO — 法律、研究、销售与运营
    └── Governor — 独立审查与升级
```

导师姓名仅用于创作框架，不表示关联、背书或保证模仿效果。

## 安全边界

- 不要在技能或 issue 中放入凭据、私人数据、浏览器会话或生产配置。
- 执行前审查第三方命令和依赖。
- 金融工作流在独立验证前仅用于研究或模拟交易。
- 帖子、消息、交易、部署和破坏性操作必须经过人工明确批准。
- 安全漏洞请通过 [GitHub Security Advisories](https://github.com/aAAaqwq/AGI-Super-Team/security/advisories/new) 私密报告。

## 项目链接

- [Evidence First 项目站](https://aaaaqwq.github.io/AGI-Super-Team/)
- [实用指南](./docs/guides/)
- [安装与恢复](./setup.md)
- [贡献与来源要求](./CONTRIBUTING.md)
- [安全政策](./SECURITY.md)
- [增长手册](./growth/README.md)
- [许可证](./LICENSE)

## Star History

![Star History](https://aaaaqwq.github.io/AGI-Super-Team/assets/star-history.svg)

<p align="center">
  <img src="assets/banner.png" alt="AGI Super Team — 以证据为基础的 AI 团队，服务真实成果" width="100%">
</p>

<h1 align="center">AGI Super Team</h1>

<p align="center"><strong>Evidence-backed AI teams for real outcomes</strong><br/>以证据为基础的 AI 团队，服务真实成果</p>

<p align="center">
  <a href="./README.md">English</a> ·
  <a href="#安全快速开始">快速开始</a> ·
  <a href="./setup.md">安装指南</a> ·
  <a href="./CONTRIBUTING.md">参与贡献</a>
</p>

## 这个仓库是什么

AGI Super Team 收录 Agent 人格、可复用技能、starter kit 清单，以及独立维护的 Codex 原生精选包。它帮助用户组装可审查的 AI 工作流，而不是承诺自动取得商业成果。

所有输出仍需人工审查。交易、法律、安全、医疗、发布和部署任务必须经过相应领域验证，并获得明确授权。

## 选择分发方式

| 使用方式 | 仓库支持 | 安装路径 | 说明 |
|---|---|---|---|
| 通用/本地工作区 | 由 `install.sh` 支持 | 预览、检查、再应用 | 复制所选人格和现有技能，不覆盖已有文件 |
| Codex | 独立的原生精选包 | 见 [`.codex/INDEX.md`](./.codex/INDEX.md) | 使用独立 manifest、精选技能和可选 Agent 同步 |
| Claude Code | 仓库包含 plugin manifest | 检查 [`.claude-plugin/`](./.claude-plugin/) | 使用前确认客户端版本支持该 manifest |
| Cursor、Gemini、Kimi | 仓库包含元数据/manifest | 检查对应 manifest | 各客户端版本能力不同，本仓库不宣称功能完全一致 |

通用 starter kit 与 Codex 包是不同的分发物。安装其中一个不会自动安装或同步另一个。

## 安全快速开始

先克隆可信版本，再预览本地安装器。默认预览不会写入目标目录。

```bash
git clone --depth 1 --branch main https://github.com/aAAaqwq/AGI-Super-Team.git
cd AGI-Super-Team
./install.sh --source "$PWD" --destination /path/to/review-workspace solo-founder
```

核对计划安装的 Agent、来源、目标路径和相关文件。确认无误后再显式应用：

```bash
./install.sh --source "$PWD" --destination /path/to/review-workspace --apply solo-founder
```

安装器会保留已有的人格文件和技能目录。依赖、验证、更新和恢复方法见 [setup.md](./setup.md)。

如能先检查固定版本的 checkout，请不要把远程脚本直接传给 shell 执行。

### 预览 → 应用 → 验证

<p align="center">
  <img src="assets/demo-install.gif" alt="终端演示：只读预览、显式应用和仓库检查通过" width="760">
</p>

动画中的路径已经替换为项目内相对路径。你也可以阅读[静态文字记录](./assets/demo-install.txt)，或在干净 checkout 中运行相同命令。

## 包与 Manifests

- [Codex 包索引](./.codex/INDEX.md)：精选 Codex 技能、专业角色、同步行为、来源和更新策略。
- [Codex marketplace manifest](./.agents/plugins/marketplace.json)：指向独立的 `plugins/agi-super-team-codex` 包。
- [Starter kits](./starter-kits/)：独立开发者、内容团队和量化研究的小型组合。
- [Agents](./agents/)：通用工作区安装器使用的人格和操作文件。
- [Skills](./skills/)：跨 harness 技能库。内容会变化，请使用仓库 validator，不要写死数量。

## Starter kits

| Kit | Agents | 适用场景 |
|---|---|---|
| [Solo Founder](./starter-kits/solo-founder/) | CEO、PE、CCO | 规划、工程和经人工审查的内容草稿 |
| [Content Creator](./starter-kits/content-creator/) | CCO、CDO、CMO | 调研、内容草稿和衡量计划 |
| [Quant Trader](./starter-kits/quant-trader/) | CQO、CDO、CFO | 研究、回测和风险审查，不用于实盘交易 |
| `full-team` | 仓库全部 Agents | 广泛评估；通常建议从更小组合开始 |

示例表示 Agent 可以协助的任务，不代表已经验证的效果。对外发布、金融交易和生产变更必须由人工明确授权。

## 证据与验证

仓库完整性以自动检查为准：

```bash
npm test
npm run validate
```

在当前版本 validator 通过之前，不发布精确目录数量。提出成果主张时，应链接可复现输入、记录版本，并明确区分测试结果与真实环境验证。

## 架构

```text
创始人 / 操作者
└── CEO — 协调与质量门禁
    ├── CTO / PE — 架构与实现
    ├── CPO / CCO / CMO — 产品、内容与增长
    ├── CQO / CFO / CDO — 量化研究、财务与数据
    ├── CLO / CRO / CSO / COO — 法律、研究、销售与运营
    └── Governor — 独立审查与升级
```

Agent 目录可能包含人格、身份、工作流和工具指南。导师姓名仅用于创作框架，不表示关联、背书或保证模仿效果。

## 安全边界

- 不要在技能或 issue 中放入凭据、私人数据、浏览器会话或生产配置。
- 执行前审查第三方命令和依赖。
- 金融工作流在独立验证前仅用于研究或模拟交易；仓库不保证任何策略盈利或可直接用于生产。
- 帖子、消息、交易、部署和破坏性操作必须经过人工明确批准。
- 安全漏洞请通过 [GitHub Security Advisories](https://github.com/aAAaqwq/AGI-Super-Team/security/advisories/new) 私密报告，不要提交公开 issue。

## 项目链接

- [安装与恢复](./setup.md)
- [贡献与来源要求](./CONTRIBUTING.md)
- [安全政策](./SECURITY.md)
- [增长手册](./growth/README.md)
- [许可证](./LICENSE)

## Star History

![Star History](https://aaaaqwq.github.io/AGI-Super-Team/assets/star-history.svg)

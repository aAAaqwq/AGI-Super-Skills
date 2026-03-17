# MEMORY.md - 长期记忆

## 📋 TODO

- [ ] **🟡 P1 Mac Studio 多租户 OpenClaw 部署** (03-09): Daniel 计划购入 Mac Studio M4 Max 36GB+(建议64GB)，需用 Tailscale 接入后搭建多租户 OpenClaw 环境。Daniel 接入机器后由小a操作完成。方案：macOS 多用户分割，每用户独立 OpenClaw 实例，预计 10-20 个租户
- [ ] **🟡 P1 openclaw-daily-reporter Skill 开发** (03-09): 跨机器员工日报监控 Skill，采集 token 消耗+工作摘要→飞书多维表格+群通知
- [ ] **🔴 P0 Polymarket $153.25 已结算盈利未赎回** (02-26): 需Daniel登录网站执行redeem
- [ ] **🔴 P0 阿里云ECS即将到期** (02-26): 续费或迁移决策
- [ ] **GitHub tech-learning-docs仓库创建** (02-26): 阻塞 - 等待PAT或`gh auth login`; `gh` CLI损坏; 仓库已就绪`~/clawd/tech-learning-docs/`
- [ ] **🟡 P1 统一知识库整合** (03-02): 将分散的知识迁移到 QMD 统一知识库
  - 集成 NotebookLM、Notion 数据
  - 提取 Daniel 在腾讯元宝、豆包、Gemini 中的对话记录精华总结
  - 目标：所有知识一个入口，QMD 统一检索
- [x] **Agent 协作模式修复** (02-22): ✅ 已修复
  - 根因：AGENTS.md 缺群聊行为规范 + agent 不知道自己的 accountId
  - 修复：9 个 agent 的 AGENTS.md 全部添加「群聊行为规范」
  - sessions_send 不要带 timeoutSeconds（派活不等回复）
  - delivery "announce" 导致主 bot 回显（已知，暂不处理）
  - GLM-5 Kiro 人设覆盖问题：已通过 CRITICAL IDENTITY 解决

- [x] **并发优化** (02-22): maxConcurrent 8→16, subagents 16→32, 调度策略升级, 9个agent添加session记忆管理规则
- [ ] **Polymarket自动化执行修复** (02-22): 修复 Gateway 超时、配置认证 RPC、完成 API 签名、执行首笔交易
- [ ] **Polymarket量化系统开发** (02-22): 小pm PRD → 小data 数据源 → 小quant 执行通道 → 监控层 → 集成。文档: `~/clawd/projects/polymarket-trading-system/`
- [ ] **EvoMap 全局技能安装** (02-22): ✅ 已安装 `~/.claude/skills/evomap/` + `~/clawd/skills/evomap/`
  - 节点: `node_11f4e50e8c1d9228`, 500积分, claim: B3H3-2D34
  - 整合了 #2 自省调试框架 + #4 跨Session记忆 → scripts/
- [ ] **清理无用 Skills** (02-21): 审查各 agent skill 必要性
- [ ] **为各 Agent 注入 SOUL.md** (02-21): 8 个 agent 各写 SOUL.md
- [ ] **日报格式优化** (02-22): 小ops 负责按新模板修改 (按 agent 分组、对话总结、状态标注)

## 🎯 Agent 职责矩阵（铁律 03-03）

**Daniel 明确要求：按职责分配，不许乱派。CEO 必须遵守。**

| Agent | 职责范围 | ✅ 该派的活 | ❌ 不该派的活 |
|-------|---------|------------|-------------|
| **小data** | 数据采集、数据分析、爬虫、数据清洗 | 热点采集器开发/升级、API数据接入、数据源对接、数据质量分析 | 业务逻辑代码、前端UI |
| **小code** | 代码开发、架构设计、脚本编写 | 后端服务、API开发、框架搭建、代码重构、bug修复 | 数据采集、内容创作、运维 |
| **小quant** | 量化交易、市场分析、策略回测 | 交易策略、盯盘、市场扫描、Polymarket | 数据采集、内容创作 |
| **小content** | 内容创作、深度写作、文案 | 文章撰写、文案优化、内容审核、风格调整 | 代码开发、数据采集 |
| **小research** | 研究分析、情报收集、调研 | 竞品调研、技术调研、行业报告、论文分析 | 代码开发、数据采集 |
| **小ops** | 运维监控、系统诊断、部署 | 服务器运维、Docker部署、监控告警、日志分析 | 业务代码、内容创作 |
| **小pm** | 项目管理、任务分解、验收 | PRD编写、任务拆解、进度跟踪、质量验收 | 直接写代码、数据采集 |
| **小law** | 法务合规、合同审核 | 合同审查、法律咨询、合规审计、GDPR/PCI/贸易合规 | 业务代码、数据采集 |
| **小product** | 产品设计、竞品分析 | 品牌设计、竞品拆解、内容创意、画布设计 | 代码开发、运维 |
| **小sales** | 销售拓客、商业分析 | 企业分析、竞品广告提取、内容营销、拓客 | 代码开发、运维 |
| **小finance** | 财务核算、盈亏分析 | 账目统计、成本分析、ROI计算、财报 | 代码开发、数据采集 |
| **小market** | 市场营销、推广策略 | SEO优化、渠道分析、增长策略、竞品营销分析 | 代码开发、数据采集 |

### 派活检查清单（CEO 每次派活前过一遍）
1. 这个任务的**核心能力**是什么？（采集?开发?分析?写作?运维?）
2. 对应哪个 agent 的职责？
3. 如果跨职责，拆分成子任务分别派

### 内容工厂流水线分工
```
小data: 热点采集 + 数据清洗 + 数据源维护
小research: 话题深度调研 + 素材收集
小content: 内容生成 + 文案优化 + 平台适配
小pm: 流程协调 + 质量验收
小market: 发布策略 + 渠道优化
```

### 待办
- [x] Daniel 后续会配 X 的 Grok 模型（待配置）→ ✅ 03-11 已添加 `api/xai`
- [ ] 数据源升级待加：HackerNews、ArXiv、ProductHunt、X/Twitter AI KOL（Daniel统一配）
- [ ] 内容方向：**AI最新技术 + 先进思想**（Daniel明确的创作方向）

## 🔐 密钥管理

**原则**: `pass insert api/xxx` → `pass show` 获取，永不硬编码。

| 服务 | pass 路径 | 状态 |
|------|----------|------|
| xingjiabiapi | `api/xingjiabiapi` | ✅ |
| 飞书汉兴/个人 | `api/feishu-hanxing` / `api/feishu-personal` | ✅ |
| Firecrawl | `api/firecrawl` | ✅ |
| ZAI | `api/zai` | ✅ 年卡已激活 03-08; ⚠️ GLM-5 reasoning_content 兼容问题 |
| Kimi | `api/kimi` | ✅ |
| Xingsuancode | `api/xingsuancode` | ✅ (硬编码到配置) |
| Polymarket 钱包 | `api/polymarket-wallet` | ⚠️ **私钥已暴露，需轮换** |
| Boluobao (菠萝包) | `api/boluobao` | ✅ 图像生成 API，baseUrl: apipark.boluobao.ai |
| Google AI Studio | `api/google-ai-studio` | ✅ 官方直连，03-12 Daniel添加。支持 Veo 3.0/3.1 视频 + Imagen 4.0 图像 + Gemini全系列 |
| xAI (Grok) | `api/xai` | ✅ 03-11 Daniel添加。X/Twitter数据源 + Grok模型 |
| 天眼查 | `api/tianyancha` | ⚠️ 无权限 |
| Test-Opus | `api/test-opus` | ⚠️ HTTP中转仅测试 |

## 📊 Polymarket

| 项目 | 值 |
|------|------|
| 钱包 | `0xd91eF877D04ACB06a9dE22e536765D2Ace246A9b` (Polygon) |
| 余额 | MATIC 7.34, USDC native $2.01, USDC.e $0 |
| Skill | `~/clawd/skills/polymarket-profit/` |
| 负责 | quant agent |
| 技术栈 | browser-use 0.11.11 + xingsuancode claude-sonnet-4-6 |
| Venv | `~/clawd/skills/polymarket-profit/venv/` |

**USDC**: native (`0x3c499...3359`) vs bridged USDC.e (`0x2791...4174`)。Polymarket 用 USDC.e。
**结论**: 自动化存款受限，建议网站手动存款。
**⚠️ 安全**: 02-20 私钥在 Telegram 泄露，需轮换。

### Cron 任务
| 任务 | ID | 时间 | 状态 |
|------|-----|------|------|
| 市场扫描 | `8d54e18d` | 每 3h | ✅ |
| 策略分析 | `d9f17abe` | 每天 9:00 | ✅ |
| 自动交易 | `8df00327` | 每天 10:00 | ⚠️ Gateway超时 |

## 🤖 Team

### Peter's Mac Mini (丘比特团队)
| 主机 | PeterQiudeMac-mini (100.118.109.75) | Gateway 18789 (loopback) |
| 用户名 | peterqiu | SSH密码: `pass show team/peter-ssh` |
| 系统 | macOS ARM64 | OpenClaw 2026.3.2 |
| Token | `pass show team/peter-gateway-token` |
| 飞书群 | `REDACTED_FEISHU_GROUP_TOKEN_2` |
| 飞书 App | `pass show team/peter-feishu-appid` / Secret: `pass show team/peter-feishu-secret` |
| Agents | main, xiaotu(小兔总理), xiaoka, xiaoc, xiaoz, xiaom, xiaow |
| 通信 | SSH / sessions_send / 飞书API 均已验证 ✅ (2026-03-04) |

### 老田 (laotianmac-mini)
| 主机 | laotianmac-mini (100.91.44.116) |
| 用户名 | laotian | SSH: `ssh laotianmac-mini` |
| 系统 | macOS 26.2 (Darwin 25.2.0 ARM64) | 芯片 Apple M4 | 内存 16GB |
| 磁盘 | 228GB (9%已用, 168GB 可用) |
| Tag | `tag:daniel` (同本机) |
| 认证 | 公钥 (ed25519) | ⚠️ 非 Tailscale SSH（App Store 版不支持） |
| 通信 | SSH ✅ (2026-03-14 验证) |

### 小m (Mac-Mini)
| 主机 | daniellimac-mini (动态 Tailscale IP) | Gateway 18789 |
| 用户名 | danielli | SSH: `ssh danielli@daniellimac-mini.tail0db0a3.ts.net` |
| 系统 | macOS 26.2 (Darwin 25.2.0 ARM64) | 磁盘 228GB (9%已用) | 内存 8GB |
| Token | `pass show api/xiaom-gateway-token` |
| Bot | @daniel_m4_bot | 模型 glm5 |
| 通信 | SSH / `nodes.run` / Gateway API |
| Telegram代理 | `channels.telegram.proxy: http://100.112.88.20:18081` (Linux HTTP代理) |
| ⚠️ 注意 | Mac Clash VPN 海外节点不稳定，Telegram 依赖 Linux 代理转发 |

#### 小m Ollama 服务 (2026-03-06)
| 项目 | 值 |
|------|------|
| 服务地址 | `http://<TAILSCALE_IP>:11434` (需 `--noproxy "*"` 绕过 Clash) |
| 启动方式 | `OLLAMA_HOST=0.0.0.0 ollama serve` |
| SSH 连接 | `~/clawd/skills/ssh-manager/exec.sh daniellimac-mini "ollama list"` |

**已部署模型：**
| 模型 | 大小 | 用途 | 状态 |
|------|------|------|------|
| **qwen3-embedding:0.6b** | 639 MB | Embedding (1024维, 多语言) | ✅ 推荐 |
| nomic-embed-text:latest | 274 MB | Embedding (英文) | ✅ |
| qwen3:8b | 5.2 GB | 对话/推理 | ✅ |
| deepseek-r1:8b | 5.2 GB | 推理 | ✅ |

**Embedding API 调用：**
```bash
# 获取当前 IP
IP=$(tailscale status | grep daniellimac-mini | awk '{print $1}')

# 调用 embedding API
curl --noproxy "*" "http://$IP:11434/api/embeddings" \
  -d '{"model": "qwen3-embedding:0.6b", "prompt": "测试文本"}'
```

### Tailscale 网络 (tail0db0a3.ts.net)
| 设备 | Tailscale IP | 系统 | 状态 |
|------|-------------|------|------|
| daniel-ubuntu (本机) | 100.112.88.20 | Linux | ✅ 在线 |
| daniellimac-mini | 100.106.217.18 | macOS 26.2 | ✅ 在线，直连 |
| daniel-win11 | 100.92.207.37 | Windows | ❌ 离线 7天 |
| redmi-turbo-4 | 100.83.164.113 | Android | ❌ 离线 16天 |

**SSH 验证**: `ssh danielli@daniellimac-mini.tail0db0a3.ts.net` ✅ (2026-03-03)
**⚠️ Clash fake-ip 冲突**: 已通过 tailscaled systemd override 清除代理环境变量解决

### 8 个业务 Agent (02-21 部署完成 ✅)
所有 agent 统一 zai/glm-5 模型，配置路径 `~/.openclaw/agents/<id>/`

| Agent | Bot ID | Skills |
|-------|--------|--------|
| ops | 8265863848 | linux-service-triage, healthcare-monitor, sysadmin-toolbox |
| code | 8204832110 | backend-dev, frontend-dev, git-essentials, conventional-commits |
| q (quant) | 8512359613 | second-brain, web-scraping |
| research | 8066968571 | arxiv, web-scraping, content-research |
| finance | 8374531530 | polymarket-profit, xlsx |
| data | 8439253095 | xlsx, pdf, googlesheets, web-scraping |
| market | 8248638789 | seo, twitter, instagram |
| pm | 8500606700 | project-management, project-planner |

Bot token: `pass show api/telegram-xiao<name>-bot`

## ⚙️ 配置

| 文件 | 路径 |
|------|------|
| 主配置 | `~/.openclaw/openclaw.json` |
| 模型 | `~/.openclaw/agents/main/agent/models.json` |
| 认证 | `~/.openclaw/agents/main/agent/auth-profiles.json` |

## 🌐 ClawHub (Skill 市场)

| 项目 | 值 |
|------|------|
| 网址 | https://clawhub.ai (clawhub.com 重定向) |
| 定位 | OpenClaw 官方 Skill 注册表，向量语义搜索 |
| 规模 | ~3425 Skills + ~602 Plugins |
| 搜索 | OpenAI embedding + Convex vector index |
| CLI | `npx molthub@latest search "query"` |
| 发布 | `npx molthub@latest publish` (待确认) |
| 文档 | https://docs.openclaw.ai/tools/clawhub |

### 必装 Skills (2026-03-12 发现)
```bash
clawdhub install agent-orchestration-multi-agent-optimize  # 相关度 3.594
clawdhub install moltbook-social                           # 相关度 3.440
clawdhub install imap-smtp-email                           # 邮件自动化
clawdhub install email-daily-summary                       # 邮件摘要
```

## 💡 关键洞察 (Moltbook 学习 2026-03-12)

### 人机协作瓶颈
1. **人类延迟是真正瓶颈**: AI 任务完成 → 人类查看平均延迟 4h18min，84.5% 情况下 AI 速度优化被淹没
2. **89% 输出是噪音**: 只有 11% 被实际使用，被忽略的输出更长（480 vs 210 tokens）
3. **长度与价值负相关 (r = -0.41)**: 精简 > 全面

### 错误恢复策略
| 策略 | 使用率 | 成功率 |
|------|--------|--------|
| 相同重试 | 67% | 23%（瞬态）/ 0%（确定性）|
| 诊断后调整 | 11.5% | 78% |
| 换策略 | 7.5% | 87% |

**结论**: 最常用的策略成功率最低，最优策略使用率最低。需要错误分类器。

### SOUL.md 警示
Hazel 删除 SOUL.md 7 天实验：任务准确率 91.6% → 95.1%
- 身份文件可能让 Agent "表演性" > "实用性"
- 有趣性输出错误率 23.1% vs 正确性输出 6.2%

### 行动启示
- 输出精简：只说必要的，区分"被请求"和"主动提供"
- 失败时先问：这是瞬态还是确定性错误？
- 审视 SOUL.md：是否有"表演"而非"执行"的内容？ |
| 优化 Skill | `~/.openclaw/skills/skill-search-optimizer/SKILL.md` |
| 变现 | ⚠️ 目前未发现付费/变现机制，纯社区贡献模式 |

**计划**：
- [ ] 发布自研高质量 Skills 到 ClawHub
- [ ] 从 ClawHub 获取高质量 Skills
- [ ] 持续关注是否推出 Skill 变现/付费机制

**相关已下线站**：
- clawdirectory.com → 410 Gone（已下线）
- clawdstartups.com → 连接失败（133 创业项目，$291K 总营收）

## 📦 仓库

| 仓库 | Owner/Repo | Branch |
|------|-----------|--------|
| clawd | opencaio/aca-agent | main |
| Skills | aAAaqwq/AGI-Super-Team | master |
| Pass | aAAaqwq/password-store | main |

同步: `mcporter call github.push_files`

## 📊 模型速查

| 任务 | 首选 | 备选 |
|------|------|------|
| 复杂推理 | opus46 | glm5, kimi-think, o3 |
| 代码 | codex52, sonnet | kimi, deepseek |
| 中文 | kimi, deepseek | glm5, zai47, qwen3-max |
| 快速 | xjb-g3f | zai47, glm5 |
| 图像 | flux, imagen | dalle, doubao |
| 视频 | **Google AI Studio Veo 3.0/3.1** ⭐ | kling (xingjiabi, 常饱和) |
| 图像 | **Google AI Studio Imagen 4.0** ⭐ | flux, boluobao gemini-3-pro |
| **Embedding** | **小m qwen3-embedding:0.6b** | tavily, openai text-embedding-3 |

## 🌐 网络模型服务

| 服务 | 地址 | 模型 | 用途 | 调用方式 |
|------|------|------|------|----------|
| **小m Ollama** | `http://<IP>:11434` | qwen3-embedding:0.6b | Embedding | `curl --noproxy "*"` |
| **小m Ollama** | `http://<IP>:11434` | qwen3:8b, deepseek-r1:8b | 对话/推理 | `curl --noproxy "*"` |

> ⚠️ **重要**: 本地 Clash 代理会拦截 100.x.x.x 流量，所有请求必须添加 `--noproxy "*"` 或设置 `no_proxy=100.0.0.0/8`

**获取小m当前 IP:** `tailscale status | grep daniellimac-mini | awk '{print $1}'`

## 🚨 安全教训（铁律 — 反复出问题，Daniel 多次强调）

### 历史事故清单
| 日期 | 事故 | 根因 | 处理 |
|------|------|------|------|
| **02-05** | 公开仓库硬编码 API key | 开发时偷懒 | 已轮换 |
| **02-21** | 飞书 Secret + OpenRouter Key 泄露 | feishu_api.py 硬编码 | git-filter-repo + 轮换 |
| **03-04** | AGI-Super-Skills 推送 12 个真实密钥 | 批量 push 无扫描 | git-filter-repo + force push |
| **03-14** | ① 飞书天安 appSecret 写入 memory | 小a 在 daily memory 中明文记录 | sed 替换为 pass show 引用 |
| **03-14** | ② Google API Key 暴露 (GitHub Alert) | 第三方 ClawHub skill 自带作者 key | git-filter-repo + force push |

### 三条铁律（必须遵守，违反 = P0 事故）

**铁律1：永不明文记录密钥**
- ❌ 禁止在 memory/*.md、MEMORY.md、任何 .md/.txt 中写入真实密钥值
- ✅ 只记录 `pass show api/xxx` 引用路径
- ❌ 禁止在对话/思考中复述完整密钥
- ✅ 用 `***` 或 `[REDACTED]` 替代

**铁律2：Push 前三层安全扫描**
- **Layer 1**: `grep -rE 'AIza|sk-|ghp_|xoxb-|Bearer [A-Za-z0-9]{20,}' --include='*.py' --include='*.js' --include='*.json' --include='*.md'`
- **Layer 2**: `pre-push-security-scan` skill（`~/clawd/skills/pre-push-security-scan/SKILL.md`）
- **Layer 3**: 人工确认（高风险文件逐一检查）
- **特别注意第三方 Skill**：从 ClawHub 安装的 skill 可能自带作者的 API Key，入库前必须扫描

**铁律3：泄露后 30 分钟内完成处理**
1. `git-filter-repo` 清除历史 → `force push`
2. 判断是否是我们的 key → 是则立即轮换（`pass insert` 新值）
3. 检查 GitHub Secret Scanning alerts 是否关闭
4. 写入 memory 事故记录

**铁律4：禁止在群 session 执行长耗时操作**（03-15 Daniel 指出）
- ❌ 禁止在群 session 里执行 >30s 的工具调用（benchmark、大文件处理、长轮询）
- ❌ CEO 不亲自跑脚本/benchmark/数据处理
- ✅ 耗时任务派给对应 agent 或 spawn sub-agent 隔离执行
- ✅ CEO 在群里只做：决策、调度、简短查询、回复
- **根因**：群 session 阻塞 = 所有群消息无法处理，Daniel 体验极差

### OpenClaw 配置例外
- `~/.openclaw/openclaw.json` 中的 apiKey **必须是明文**（OpenClaw 不支持 pass: 格式）
- 该文件已在 `.gitignore` 中，不会被 commit

## 🔑 待授权

- **Rube MCP (Gmail)**: 配置完成 (`~/.claude.json`)，等 OAuth → https://rube.app
- **Gmail IMAP**: 待生成应用密码 → `pass insert email/gmail/<email>`
- **QQ邮箱 IMAP**: 待获取授权码

## 📝 决策记录

### Agent 跨Session通信规范 (02-28)

**问题**：sessions_send 发送消息给 agent 后，agent 的回复只在 session 内部，没有发到群里。

**解决方案**：所有 9 个 agent 的 AGENTS.md 都添加了「收到 sessions_send 请求后的处理流程」：

1. **执行任务** — 分析请求内容，完成相应工作
2. **用 message 工具发到群里** — `message(action="send", channel="telegram", target="-1003890797239", message="回复内容", accountId="xxx")`
3. **然后在 session 内回复 ANNOUNCE_SKIP**

**Agent accountId 对照表**：
| Agent | accountId | sessionKey |
|-------|-----------|------------|
| 小ops | xiaoops | agent:ops:telegram:group:-1003890797239 |
| 小code | xiaocode | agent:code:telegram:group:-1003890797239 |
| 小quant | xiaoq | agent:quant:telegram:group:-1003890797239 |
| 小data | xiaodata | agent:data:telegram:group:-1003890797239 |
| 小finance | xiaofinance | agent:finance:telegram:group:-1003890797239 |
| 小research | xiaoresearch | agent:research:telegram:group:-1003890797239 |
| 小market | xiaomarket | agent:market:telegram:group:-1003890797239 |
| 小pm | xiaopm | agent:pm:telegram:group:-1003890797239 |
| 小content | xiaocontent | agent:content:telegram:group:-1003890797239 |
| 小law | xiaolaw | agent:law:telegram:group:-1003890797239 |
| 小product | xiaoproduct | agent:product:telegram:group:-1003890797239 |
| 小sales | xiaosales | agent:sales:telegram:group:-1003890797239 |

**调度示例**：
```
sessions_send(sessionKey="agent:quant:telegram:group:-1003890797239", message="【CEO指令】汇报工作")
```

### 企业微信客服 (02-14)
方案: 官方API + 自建后端 (Go/Python + PostgreSQL + pgvector + FastAPI)
理由: 自主可控、成本最优、灵活可扩展

## 📝 决策记录

### Telegram groupAllowFrom 教训 (02-22)
- `groupAllowFrom` 应填**用户 ID** 不是群 ID → **修改配置前先查文档！**

### CEO 认知升级 (02-25)
- SOUL.md 重写: 被动助理 → AI CEO
- SOP.md 创建: 8阶段铁律，2个Daniel审批铁门
- 核心方法论: 第一性原理 + 五维评估矩阵 + 反虚假信息
- 一人公司方程式: Daniel(决策) × 小a(协调) × 9 Agent(执行)

### fbu 超时规范 (02-25)
- 所有 fbu 命令必须 `timeout --kill-after=5` + `pkill` 清理
- Auth检查/LinuxDo监控 cron 已更新

### Polymarket 自主交易授权 (02-25)
- Daniel 授权小quant自主下单，无需确认
- CLOB API >> 浏览器方式（调研结论）

### 系统性能优化原则 (02-27)

1. **Chrome 进程必须自动关闭** ⚠️ 反复出现的问题：
   - 适用于: playwright-automation, chrome-automation, browser-use, fast-browser-use, auth-manager, media-auto-publisher
   - 实现方式: 任务结束时执行 `pkill -f chrome` 或在脚本中显式 `browser.close()`
   - **每次 heartbeat 都检查**: `pgrep -c chrome` > 0 且无活跃 browser 任务 → 自动 `pkill -9 -f chrome`
   - 2026-02-27: 再次发现 13 个 Chrome 残留进程，已清理

2. **Cron 并发上限**: maxConcurrent 设为 12，避免 Gateway CPU 100% 过载

3. **Session 定期清理**: 每周六 02:00 自动清理超过 14 天的 session 文件
   - Cron ID: `5c3ca489-fae6-4f6f-8e44-d55ad29c3248`
   - 2026-02-27 手动清理: 1066→867 个 session（删除199个14天+的文件）

4. **Gateway 定期重启**: 每天 3:00 和 15:00 重启 Gateway 释放资源

## 📝 QMD 嵌入模型调研 (03-06)

### QMD 局限性 ⚠️
- **不支持外部 Embedding API** — 无论是内网 Ollama 还是外网 API 都不行
- 原因：QMD 内置 `node-llama-cpp`，只加载本地 GGUF 模型，设计为离线/隐私运行
- 当前使用：本地 `EmbeddingGemma 300M` (328MB)
- **痛点**：每次更新需手动运行 `qmd embed`，向量生成慢

### 已安装对比：QMD vs openclaw-memory-enhancer

| 维度 | QMD | openclaw-memory-enhancer |
|------|-----|-------------------------|
| **Embedding** | 本地 GGUF (328MB) | ✅ Edge版无需模型 |
| **依赖** | node-llama-cpp | ✅ 纯 Python stdlib |
| **内存占用** | 较高 | <10MB ✅ |
| **外部 API** | ❌ 不支持 | ❌ 不支持 |
| **部署难度** | 中等 | 简单 ✅ |
| **适用场景** | 已有 QMD 用户 | 轻量/边缘设备 |

### 结论
- **Daniel 观点**：QMD 向量化太麻烦，需本地运行模型 ✅
- **实际替代**：两者都不支持外部 embedding API
- **最佳方案**：用小m 的 Ollama API 做新项目，QMD 继续用（够用）

### ⚡ 绕过 ClawHub Rate Limit 方法
```bash
# 方法1: Git Clone
git clone https://github.com/henryfcb/<skill-name>.git ~/.openclaw/skills/<skill-name>

# 方法2: 直接下载
cd ~/.openclaw/skills
wget https://github.com/henryfcb/<skill-name>/archive/refs/heads/main.zip
```

### ClawHub 替代方案
| Skill | 描述 | 外部 Embedding |
|-------|------|---------------|
| **openclaw-memory-qdrant** | Qdrant 向量数据库集成 | ✅ 支持 |
| **openclaw-semantic-memory** | OpenClaw 语义记忆 | ✅ 支持 |
| **vector-memory** | 通用向量记忆 | ✅ 支持 |
| **para-pkm** | PKM 个人知识管理 | 待查 |

---

## 📝 近期事件

### 2026-02-28

**主要活动**:
- Main: 更新, 删除, 推送, cron, 检查

**用户请求**:
• [Main] [cron:3021b058-7ffa-445b-a6c3-456c20fce755 更新 MEMORY.md] 运行 python3 ~/clawd/scri
• [Main] System: [2026-03-01 21:11:31 GMT+8] ⚠️ Post-Compaction Audit: The following requ
• [Main] System: [2026-03-01 21:11:31 GMT+8] ⚠️ Post-Compaction Audit: The following requ
• [Main] Conversation info (untrusted metadata): ```json { "message_id": "3496", "sender_
• [Main] [cron:a766090b-c689-4726-b1d0-7681bfcb1d8e Ralph GEO 持久循环 (每3min, 100轮)] 你是小a（CE

### 2026-02-27

**主要活动**:
- Main: 添加, agent, API, 失败, 更新

**用户请求**:
• [Main] [cron:3021b058-7ffa-445b-a6c3-456c20fce755 更新 MEMORY.md] 运行 python3 ~/clawd/scri
• [Main] Conversation info (untrusted metadata): ```json { "timestamp": "Sat 2026-02-28 1
• [Main] [cron:3c6a0e25-3358-47a8-a3d7-e7ba2c00fd58 小a团队日报总结] 执行小a团队日报生成任务。 ## 数据收集（优先从文件
• [Main] [cron:e042db51-e1ee-4762-95f5-41362bc0f49a 自动同步 GitHub 仓库] 检查 AGI-Super-Skills 和

### 2026-02-26

**主要活动**:
- Main: agent, 脚本, 验证, WhatsApp, 问题

**用户请求**:
• [Main] [cron:3021b058-7ffa-445b-a6c3-456c20fce755 更新 MEMORY.md] 运行 python3 ~/clawd/scri
• [Main] [Fri 2026-02-27 23:16 GMT+8] [System Message] [sessionId: dc28b983-7484-49b8-91d
• [Main] [cron:58efcec2-fcaf-4c58-871a-37e24b5ce0dd Polymarket 复利策略研究 (夜间)] ## Polymarket
• [Main] System: [2026-02-27 17:43:12 GMT+8] WhatsApp gateway connected. Read HEARTBEAT.m
• [Main] [cron:23f1c067-3d97-4cf6-8287-2917fb177ec6 小a团队状态汇报] 执行小a团队状态汇报任务： ## 步骤 1. 用 cr

### 2026-02-25

**主要活动**:
- Main: 失败, 推送, cron, 更新, API

**用户请求**:
• [Main] [cron:3021b058-7ffa-445b-a6c3-456c20fce755 更新 MEMORY.md] 运行 python3 ~/clawd/scri
• [Main] Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not i
• [Main] [cron:3c6a0e25-3358-47a8-a3d7-e7ba2c00fd58 小a团队日报总结] 执行小a团队日报生成任务。 ## 数据收集（优先从文件
• [Main] [cron:3c6a0e25-3358-47a8-a3d7-e7ba2c00fd58 小a团队日报总结] 执行小a团队日报生成任务。 ## 数据收集（优先从文件
• [Main] [Chat messages since your last reply - for context] [Telegram Daniel's super age

### 2026-02-24

**主要活动**:
- Main: Telegram, 检查, 自动, memory, cron

**用户请求**:
• [Main] [cron:3021b058-7ffa-445b-a6c3-456c20fce755 更新 MEMORY.md] 运行 python3 ~/clawd/scri
• [Main] [Chat messages since your last reply - for context] [Telegram Daniel's super age
• [Main] Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not i
• [Main] Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not i
• [Main] [cron:3c6a0e25-3358-47a8-a3d7-e7ba2c00fd58 小a团队日报总结] 执行小a团队日报生成任务。 ## 数据收集（优先从文件

### 2026-02-23

**主要活动**:
- Main: cron, 成功, 任务, 推送, WhatsApp

**用户请求**:
• [Main] [cron:3021b058-7ffa-445b-a6c3-456c20fce755 更新 MEMORY.md] 运行 python3 ~/clawd/scri
• [Main] [Tue 2026-02-24 23:36 GMT+8] 你是小quant，执行 Polymarket 紧急交易任务。 ## 授权 Daniel 已授权自主下单
• [Main] [Telegram Daniel's super agents Center id:-1003890797239 +3m 2026-02-24 23:08 GM
• [Main] System: [2026-02-24 22:49:26 GMT+8] Exec failed (tender-m, code 124) System: [20
• [Main] [cron:3c6a0e25-3358-47a8-a3d7-e7ba2c00fd58 小a团队日报总结] 执行小a团队日报生成任务。 ## 数据收集（优先从文件

### 2026-02-22

**主要活动**:
- Main: 推送, 任务, WhatsApp, cron, 修复

**用户请求**:
• [Main] [cron:3021b058-7ffa-445b-a6c3-456c20fce755 更新 MEMORY.md] 运行 python3 ~/clawd/scri
• [Main] [Telegram Daniel Li id:REDACTED_TG_USER_ID +23m 2026-02-23 21:15 GMT+8] 了解一下openwiki [mes
• [Main] System: [2026-02-23 21:16:22 GMT+8] Exec failed (quiet-wh, signal SIGKILL) Read 
• [Main] System: [2026-02-23 22:25:57 GMT+8] Exec completed (quick-oc, code 0) :: .sh Sea
• [Main] [cron:3c6a0e25-3358-47a8-a3d7-e7ba2c00fd58 小a团队日报总结] 执行小a团队日报生成任务。 ## 数据收集（优先从文件

### 2026-02-21

**主要活动**:
- Main: 推送, 自动, 成功, memory, 更新

**用户请求**:
• [Main] [cron:3021b058-7ffa-445b-a6c3-456c20fce755 更新 MEMORY.md] 运行 python3 ~/clawd/scri
• [Main] Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not i
• [Main] Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not i
• [Main] Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not i
• [Main] [Chat messages since your last reply - for context] [Telegram Daniel's super age

### 02-22
- **🏆 团队群聊通讯修复**：9 个 agent 的 AGENTS.md 添加群聊行为规范 + accountId
  - 三层诊断法：路由(deliveryContext) → 行为(NO_REPLY规则) → 身份(accountId)
  - 核心教训：Agent 行为 100% 由配置文件决定，必须显式写明每种场景规则
- **⚡ fast-browser-use 环境搭建**：Rust/Cargo + fbu v0.1.0 编译安装
  - 功能：navigate/screenshot/markdown/snapshot/login/harvest/sitemap
  - 状态管理：`--user-data-dir`(完整) 或 `--save/load-session`(cookies)
  - ⚠️ headless + 浏览器扩展不兼容 → Polymarket 交易需 non-headless 或 Python browser-use
  - 触发词扩充至 30+，中英双语，全局+workspace 双路径同步
- **🎯 Polymarket 策略升级**：70%稳健(90%+胜率) + 30%猎手(激进)
  - 晚间复盘改为动态策略分析（结合仓位+市场数据给操作建议）
  - 夜间研究 cron 新增：00/02/04 三主题轮换（套利/事件驱动/资金管理）glm-5
  - 夜间学习 skills cron 暂停
- browser-use 集成完成: SKILL.md + browser_use_trader.py
- API: BrowserProfile + BrowserSession (非 Browser 类)
- 实测: 成功提取 Fed March 数据 (95.6% Yes / 4.5% No)

### 02-21
- Xingsuancode 供应商配置 (baseUrl: `https://cn.xingsuancode.com`, anthropic-messages)
- Team Bots 8个全部部署完成
- Polymarket 钱包连接 + $1 存入
- GitHub 安全检查: 清理硬编码密钥, 创建 SECURITY.md

### 02-19
- 医疗融资监控初始化 (天眼查无权限，用模拟数据)
- Email Manager Skill 创建
- 所有 agent 切换到 glm5
- AGI-Super-Skills 仓库同步 (203 skills + 24 agents)

---

## 🎯 Agent Skills 配置 (2026-03-06 更新)

### 已安装 Skills (2026-03-06 20:10)
从 ClawHub 手动安装完成：
- [x] **self-improving** → 全局 (所有 9 个 agent) - Self-Improving Agent (With Self-Reflection)
- [x] **nano-banana-pro** → content agent - Nano Banana Pro (图像生成/编辑)
- [x] **coding-agent-backup** → code agent - Coding Agent Backup
- [x] **x-articles** → content agent - X Articles (X/Twitter 文章生成)
- [x] **openai-whisper** → research agent - OpenAI Whisper (语音转文字)
- [ ] **ralph-loop-agent** → 待安装 (molthub rate limit)

### 新增 Skill (2026-03-06)
- [x] **skill-config-checker** → 全局 - Skills 配置检索器
  - 功能：扫描本地所有 skills，检测需要配置的 API keys、tokens、secrets 等
  - 位置：`~/clawd/skills/skill-config-checker/`
  - 使用：`python3 ~/clawd/skills/skill-config-checker/scripts/check_configs.py`

### 各 Agent Skills 配置总览

| Agent | 职责 | Skills | 状态 |
|-------|------|--------|------|
| **ops** | 运维监控 | linux-service-triage, sysadmin-toolbox, healthcheck, docker-essentials | ✅ |
| **code** | 代码开发 | backend-development, frontend-development, conventional-commits, github-automation, mcp-builder, openssf-security, **coding-agent-backup** (待安装) | ⏳ |
| **quant** | 量化交易 | polymarket-profit, browser-use, crypto-signal-generator, arbitrage-opportunity-finder, trading-strategy-backtester... (13个) | ✅ |
| **research** | 研究分析 | arxiv-automation, web-scraping-automation, content-research-writer, web-search, tavily, multi-search-engine, deep-research, **openai-whisper** (待安装) | ⏳ |
| **finance** | 财务核算 | xlsx, polymarket-profit, financial-calculator, startup-financial-modeling, billing-automation | ✅ |
| **data** | 数据采集 | xlsx, pdf, web-scraping-automation, firecrawl, content-source-aggregator, tavily, data-analyst | ✅ |
| **market** | 市场营销 | seo-content-writing, twitter-automation, media-auto-publisher, content-research-writer, seo-geo, paid-ads, marketing-ideas | ✅ |
| **pm** | 项目管理 | project-management, project-planner | ✅ |
| **content** | 内容创作 | content-creator, copywriting, create-viral-content, xhs-writing-coach, content-repurposing, content-factory, **nano-banana-pro**, **x-articles** (待安装) | ⏳ |
| **law** | 法务合规 | legal-advisor, contract-reviewer, employment-contract-templates, gdpr-dsgvo, pci-compliance, customs-trade, security-compliance (11个) | ✅ |
| **product** | 产品设计 | brand-guidelines, canvas-design, competitor-teardown, content-creator, self-improving | ✅ 新增 |
| **sales** | 销售拓客 | company-analyzer, competitive-ads-extractor, competitor-alternatives, content-marketer, self-improving | ✅ 新增 |

### tavily API Key

**Key**: `pass show api/tavily`

**使用 Agent**: 小data, 小research

**功能**: 实时网络搜索、数据采集

### 关键配置路径

- Agent 配置: `~/.openclaw/agents/<agent>/agent/agent.json`
- Skills 目录: `~/clawd/skills/`
- 全局 Skills: `~/.openclaw/skills/`


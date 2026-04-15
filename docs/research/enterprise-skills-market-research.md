# 企业 Skills / AI Agent / 自动化 市场调研

日期：2026-03-24
目标：回答 Daniel —— 现在最现实的变现快速路径是什么。

---

## 一页结论

### 结论先说
**市场是真需求，不是伪需求；但“卖 skills”本身不是主战场，真正能收钱的是“可复用能力包 + 实施交付 + 私有化/集成服务”。**

### 为什么这么判断
1. **企业官方生态已经成型**：Zapier、Make、n8n、UiPath、Microsoft、Salesforce、ServiceNow、Workato 都在卖或分发模板、recipes、agents、marketplace listing，这不是概念验证阶段，而是已进入“目录化采购/内部复用”阶段。
2. **真实付费信号存在**：
   - Zapier / Make / n8n / UiPath / ServiceNow 都有企业付费层；
   - Relevance Marketplace 明确支持 Free + Paid listing；
   - PromptBase / AIPRM 证明“可包装 know-how”能卖，但更偏创作者零售市场，不等于企业大单。
3. **企业买的不是 prompt，而是确定性结果**：效率提升、流程标准化、权限控制、合规、知识沉淀、减少重复劳动、缩短上线时间。
4. **对 OpenCAIO/OPENCAIO 来说，最快变现路径不是开一个通用 skills 商店**，而是：
   - 先做 **垂直场景解决方案包**（如内容运营军团、销售跟进军团、客服知识库 agent、财务对账自动化、招聘筛选 agent）；
   - 用 **项目费 + 部署费 + 月维护费** 收钱；
   - 把交付中沉淀出的 skills/workflows/agents 再产品化。

### 最现实的快速变现路径（按优先级）
1. **Done-for-you 企业自动化包**（最快）
2. **行业模板包 + 私有部署 / 集成实施**（第二快）
3. **订阅式 AI Ops / Agent 运维服务**（复购最好）
4. **公开技能商店**（应放后面，先有案例再做）

---

## 用户画像

### 1. 独立开发者 / 个体经营者
- 需求：更快交付、少写重复代码、可复用工作流、售卖模板变现
- 可接受价格：低客单（$10-$99 模板 / prompt / workflow），偶尔买高价值包
- 购买逻辑：省时间 > 新鲜感

### 2. 小团队（3-20 人）
- 需求：线索跟进、内容生产、客服、报表、运营协作自动化
- 可接受价格：中客单（几百到几千美元/年或一次性方案费）
- 购买逻辑：马上能用、减少人力、低实施门槛

### 3. 初创企业 / SMB
- 需求：在不扩招情况下让运营/销售/支持/内容效率翻倍
- 可接受价格：更愿意为“交付结果 + 集成 + 安全”付费
- 购买逻辑：ROI 明确、能接现有系统（Slack/CRM/Notion/Feishu/邮箱）

### 4. 中大型企业
- 需求：权限、审计、私有化、合规、稳定性、供应商背书
- 购买逻辑：不会单买 prompt，通常采购“平台 + 实施 + 合规”

---

## 核心痛点

1. **重复流程多，但没人有空自动化**
2. **通用 AI 工具太泛，离业务流程最后一公里很远**
3. **团队不会写 prompt / workflow / agent orchestration**
4. **担心数据泄露、权限失控、输出不稳定**
5. **买 SaaS 不是问题，真正难的是落地和复用**
6. **希望同一套能力能跨成员、跨部门复用，而不是绑在某个高手脑子里**

---

## 付费触发点

企业会为以下因素付费：

1. **效率**：减少人工、缩短交付时间
2. **可复用**：不是一次性脚本，而是能复制到多个项目/团队
3. **私有化 / 安全**：数据不外泄、权限清晰、可审计
4. **行业 know-how**：懂业务，不只是懂模型
5. **模板化交付**：今天买、明天能跑
6. **集成能力**：能接 Feishu / Slack / CRM / 邮件 / ERP / 数据库
7. **维护服务**：模型变动、API 变动、prompt 漂移后有人兜底

---

## 可验证样本（信号 vs 噪音）

> 说明：以下优先采用官方页面 / 官方 marketplace / 官方定价页 / 官方新闻稿信号。

### 1. Zapier Templates / Agents Templates
- 卖什么：工作流模板、Agents 模板
- 卖给谁：个人、SMB、企业团队
- 如何收费：Zapier 平台订阅制（官方 pricing 有 Team / Enterprise）
- 真实付费信号：官方存在模板目录与 agents templates；官方 pricing 存在企业版，说明模板/自动化是付费产品漏斗的一部分
- 判断：**强信号**（企业自动化真实市场）

### 2. Make Templates
- 卖什么：7,000+ ready-made workflow templates，包含 AI automated product research agent 等
- 卖给谁：SMB 团队、自动化从业者、企业
- 如何收费：官方付费套餐 + Enterprise；搜索结果显示 Teams and team roles、Create and share scenario templates、Custom pricing
- 真实付费信号：官方模板库 + 官方企业定价 + AWS Marketplace 企业购买入口
- 判断：**强信号**

### 3. n8n Workflows
- 卖什么：8,000+ workflow templates / community templates
- 卖给谁：开发者、初创团队、企业自动化团队
- 如何收费：Cloud/Self-hosted 付费计划，Enterprise / Business 存在；官方 pricing 写明 invoice / wire transfer / enterprise
- 真实付费信号：模板数量大、社区繁荣、企业付费层明确
- 判断：**强信号**（尤其适合技术团队）

### 4. UiPath Marketplace
- 卖什么：RPA components、collections、automation accelerators、agent templates
- 卖给谁：企业自动化/RPA 团队
- 如何收费：通常绑定 UiPath 平台与企业采购，不是纯 C 端零售
- 真实付费信号：官方 Marketplace + enterprise-level vendor/consumer experience 文档；官方/社区曾披露超过 1000 reusable components 里程碑
- 判断：**强信号**（偏企业交付）

### 5. Salesforce AgentExchange
- 卖什么：Agentforce 相关的 prebuilt actions / agents / templates
- 卖给谁：Salesforce 企业客户
- 如何收费：通过 Salesforce 生态采购、合作伙伴交付、平台订阅扩展
- 真实付费信号：官方新闻稿写明 AgentExchange launched，含 200+ partners，customers can discover, try, and buy hundreds of prebuilt components
- 判断：**极强信号**（企业级 agent 市场成立）

### 6. Microsoft AppSource / Copilot Studio Agent 服务
- 卖什么：Copilot agents、implementation service、行业 agent 方案
- 卖给谁：Microsoft 365 企业客户
- 如何收费：咨询实施费 + 平台许可 + 定制开发
- 真实付费信号：AppSource 上已有多家服务商直接售卖/实施 Copilot agents，如 Employee Self-Service Agent、Copilot Agent Builder Implementation
- 判断：**强信号**（企业不是买 prompt，而是买 agent 解决方案）

### 7. ServiceNow Store AI Agent Marketplace
- 卖什么：行业/域特定 AI Agents、应用、集成、offerings
- 卖给谁：ServiceNow 企业客户
- 如何收费：通常需 ServiceNow 订阅，附加 Store app/solution
- 真实付费信号：官方博客明确称 Store 为 digital marketplace for AI agents and thousands of ready-to-use applications；具体 listing 还提示可能需要单独订阅
- 判断：**强信号**

### 8. Workato Community Recipes
- 卖什么：recipes（自动化工作流），支持 public share / clone / personalize
- 卖给谁：自动化团队、企业 IT/Ops
- 如何收费：平台订阅驱动，不是独立模板单卖
- 真实付费信号：官方 community library + 企业自动化定位；模板是拉动平台付费和实施服务的重要资产
- 判断：**中强信号**

### 9. Relevance AI Marketplace
- 卖什么：AI agents / tools / templates（Research、Sales、Marketing 等分类）
- 卖给谁：中小企业、运营团队、growth 团队
- 如何收费：官方文档明确存在 Free + Paid listings；每个 listing 明示价格
- 真实付费信号：官方 marketplace 直接支持 paid listing，这是最接近“卖 skills/agents”的原生证据之一
- 判断：**强信号**（更贴近我们想做的形态）

### 10. PromptBase
- 卖什么：Prompt marketplace；官方首页写 260,000+ prompts
- 卖给谁：创作者、个体、轻量业务用户
- 如何收费：平台抽成；官方 support 写 PromptBase takes a 20% fee；官方博客有 Creator $19/mo、Pro $39/mo；卖 prompt 还有成交分成
- 真实付费信号：存在抽成、创作者计划、卖家提现阈值、AI creator marketplace
- 判断：**中信号**（证明“包装 know-how”能卖，但更偏 C 端/创作者，不足以证明企业大市场）

### 11. AIPRM
- 卖什么：Prompt 管理、私有 prompt lists、团队协作
- 卖给谁：个人重度用户、团队
- 如何收费：官方 pricing 页面可见 Pro $33、Plus $10 等价格信号
- 真实付费信号：团队功能、Private Lists、Prompt Forking 等明确是为团队 prompt 资产管理付费
- 判断：**中强信号**（更像 prompt ops / team productivity 工具）

---

## 信号 vs 噪音

### 强信号
- 大厂/主流 SaaS 官方都在做 marketplace / templates / agents 分发
- 企业版定价、AWS Marketplace、咨询实施服务同时存在
- 模板/agent 不只是内容资产，而是平台销售与实施交付的入口
- Relevance / ServiceNow / Salesforce / Microsoft 已经明确把 “agent marketplace” 产品化

### 噪音
- 纯“prompt 市场很火”的叙事被夸大了
- 大多数 prompt 零售平台更像创作者经济，不等于企业稳定预算
- 单卖 prompt 容易低价、同质化、被复制
- “卖 skills”如果没有上下文、集成、私有知识、运维服务，很快掉到价格战

---

## 最大风险

1. **商品化过快**：通用 prompt / skill 很快被复制
2. **客户买完不会用**：没有实施与 onboarding，续费差
3. **平台依赖风险**：模型 API / 平台规则变化，模板容易失效
4. **合规与数据安全**：企业一旦涉及真实数据，就要求权限、日志、隔离
5. **价值难衡量**：如果不能量化节省多少时间/人力，预算难批
6. **“卖市场”错位**：以为自己在卖 skills，其实客户想买的是结果

---

## 对 OPENCAIO 的判断

### 当前现状（基于本地资料）
- OpenCAIO 的 `aca-agent` 项目仍处于 **Planning / MVP 定义阶段**
- README 明确写：**Status: In Planning**、MVP / architecture / content 仍待推进
- 这意味着：**OpenCAIO 目前还不适合直接做通用平台型 marketplace**，因为缺少足够多已验证场景和客户案例

### 最适合的路径
**不要先做“skills 商店平台”，先做“企业军团解决方案 + 标准模板资产库”。**

#### 推荐切入点 A（最快收钱）
**AI 军团代搭建服务**
- 形式：给客户做一套可落地的 AI 军团 / agent team / 自动化体系
- 典型包：
  - 内容运营军团（选题、写作、适配、分发、复盘）
  - 销售跟进军团（线索抓取、跟进草稿、会议总结、CRM 更新）
  - 客服知识库 agent（FAQ、工单分流、文档检索）
  - 招聘自动化（JD 生成、简历筛选、面试纪要）
- 收费：
  - 一次性方案与部署费：¥1万-5万
  - 月维护/迭代费：¥2k-1万/月
- 原因：卖的是结果，最容易成交

#### 推荐切入点 B（第二快）
**行业模板包 + 私有化部署**
- 卖：一套行业专用 skills / workflows / agents
- 再附加：部署、调优、权限、知识库接入
- 适合：中小企业、咨询公司、工作室
- 原因：模板本身客单不高，但部署能抬高客单

#### 推荐切入点 C（第三步）
**OpenCAIO 自己的 skills catalog / marketplace**
- 前提：已有 10-20 个真实客户项目沉淀出的可复用资产
- 方式：公开基础版，企业版收定制/私有化/维护费
- 原因：没有案例就先做市场，容易空转

---

## 现阶段最可行切入点（最终建议）

### 最现实变现快速路径
**“卖结果的企业自动化包” > “卖模板包” > “卖 skills 商店”**

### 建议 OpenCAIO 先卖的 3 个包
1. **内容增长军团**
   - 适合：自媒体团队、品牌团队、小公司市场部
   - 交付：选题分析 + 多平台改写 + 发布节奏 + 周报复盘
   - 理由：你们已经有飞书知识库学习、内容 skill、multi-agent 协作基础

2. **销售/运营自动化包**
   - 适合：创业公司、B2B 服务公司
   - 交付：线索归档、邮件草稿、会议纪要、CRM 自动更新、日报周报
   - 理由：ROI 容易讲清楚，企业愿意付费

3. **企业知识库+客服 agent 包**
   - 适合：文档多、重复问答多的团队
   - 交付：文档接入、FAQ、工单分流、权限控制
   - 理由：企业最容易理解，也最符合“私有化/合规/可复用”价值

---

## 最终判断

### 值不值得做？
**值得做，但不要把它理解成“开个 prompt/skill 商店”。**

### 应该怎么做？
- **短期（1-2个月）**：卖 3 个企业自动化解决方案包，拿案例和现金流
- **中期（2-6个月）**：把交付沉淀为标准 skills/workflows/agents catalog
- **长期（6个月+）**：再考虑做 OpenCAIO 自有 marketplace / partner ecosystem

### 一句话判断
**企业会为 AI skills 付费，但前提是这些 skills 被包装成“能上线、能复用、能接入业务、有人维护”的解决方案。**

如果 Daniel 问“现在最现实的变现快速路径是什么”，答案就是：

> **先卖企业自动化军团交付，不要先卖抽象 skills。**

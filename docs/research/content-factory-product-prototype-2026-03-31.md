# 内容工厂产品原型 v0.3（2026-03-31）

> 状态：15:15 前第一版骨架
> 目标：18:00 前收口为可直接进入 PRD / 开发拆解的第一版产品原型

---

## 0. 本次收口结论（一句话）

**内容工厂第一版，不做“大而全自动化平台”，而做一个以聊天式工作台为前台、以 API 为接入层、以异步工作流为执行层的内容生产与草稿交付系统。**

主打价值：
1. 稳定内容供给
2. 多平台复用
3. 草稿级交付闭环
4. 可降级、可追踪、可扩展

---

## 1. 产品定位

### 1.1 一句话定位
把内部 skills / scripts / agent / cron / 发布能力封装成一个面向创始人、个人 IP、小团队、代运营的 **内容工厂 SaaS / Agent 工作台**：用户通过聊天页或 API 发起任务，系统完成 **选题 → 成稿 → 多平台适配 → 封面素材 → 视频脚本/分镜 → 草稿投递 / 导出交付**。

### 1.2 它不是什么
- 不是单一 AI 写作工具
- 不是纯聊天 Bot
- 不是第一版就承诺全自动发全平台的视频工厂
- 不是保证爆款的增长黑盒

### 1.3 它卖的核心结果
- 稳定内容供给
- 降低内容生产人力成本
- 一次生产，多平台复用
- 从文案交付升级为草稿级交付
- 从手工作坊升级为可复制的内容系统

---

## 2. 目标用户分层

### L1：创始人 / 个人 IP（最优先）
**需求：** 没时间，但必须持续输出。  
**购买理由：** 给我每天可直接审的内容，不要我从零想。

适合能力：
- 每日选题推荐
- 图文成稿
- 标题 + 封面文案
- 短视频脚本
- 草稿交付

### L2：小团队内容运营
**需求：** 一套内容拆多个平台版本。  
**购买理由：** 同样的人，覆盖更多平台，减少重复劳动。

适合能力：
- 母稿生成
- 小红书 / 公众号 / 短帖改写
- 封面与评论区引导
- 草稿状态看板

### L3：代运营 / 工作室
**需求：** 多客户标准化交付。  
**购买理由：** 能复制、能批量、能留痕。

适合能力：
- 多客户品牌配置
- 内容包批量生成
- 草稿投递
- 任务状态追踪

### L4：API 接入方 / 企业客户（二期优先）
**需求：** 不一定需要聊天 UI，但要能嵌入自有系统。  
**购买理由：** 稳定 API + 异步结果回调。

适合能力：
- 任务创建 API
- 任务状态 API
- 资产包 API
- 发布 / 草稿接口

### 结论
**MVP 优先级：L1 > L2 > L3 > L4**

---

## 3. MVP 模块

### MVP-1 聊天式任务入口
负责：
- 用户提需求
- 系统补参数
- 发起任务
- 返回候选内容
- 支持继续改写 / 继续生成 / 入草稿

### MVP-2 选题与内容生成中心
负责：
- 热点/选题池
- 母稿生成
- 标题生成
- 多平台改写
- 标签 / CTA / 摘要

### MVP-3 视觉素材中心
负责：
- 封面标题提炼
- 封面 prompt
- 图片 / 海报生成
- 平台尺寸适配

### MVP-4 视频脚本增强模块
负责：
- 15s/30s/60s 视频脚本
- Hook
- 分镜
- 字幕稿
- 首帧标题
- 素材建议

### MVP-5 草稿投递 / 导出交付模块
负责：
- 平台草稿投递
- 发布包导出
- 状态回写
- 失败提示

### MVP-6 任务状态与资产库
负责：
- 任务列表
- 阶段状态
- 结果预览
- 资产沉淀
- 重试 / 降级

### MVP 明确不做
- 全自动视频成片
- 全平台正式发布全自动
- 复杂审批协作流
- 深度 BI 与归因分析
- 模板市场

---

## 4. 视频能力放置：主 MVP 还是二期

### 判断
**视频能力作为一级模块进入 MVP，但只进入“脚本/分镜层”，不进入“成片/全自动发布层”。**

### 为什么这样放
原因很简单：
1. 用户对视频需求强，完全不放会显得产品不完整
2. 但视频成片、剪辑、发布链路复杂度高，强行塞进首版会拖慢交付
3. “视频脚本 + 分镜 + 字幕 + 首帧标题”已经足够构成可卖价值

### MVP 放进去的部分
- 图文转视频脚本
- 视频口播稿
- 分镜拆解
- 字幕稿
- 首帧 / 封面标题
- 素材建议 / 剪辑指令

### 二期再做的部分
- 自动成片
- AI 配音
- 自动字幕合成
- 视频批量生成
- 视频平台稳定自动投递

### 结论
**视频能力在信息架构里必须有正式位置，但第一版销售主轴仍然是“图文内容工厂 + 视频脚本增强 + 草稿交付”。**

---

## 5. API + 聊天页结构

### 5.1 总体分层
建议产品分为三层：

#### A. Chat Layer（聊天页）
作用：
- 让非技术用户用自然语言表达需求
- 快速补参数
- 发起工作流
- 预览结果并继续加工

典型动作：
- 给我今天 3 个小红书选题
- 把第 2 个扩成公众号
- 生成封面文案
- 改成 30 秒视频脚本
- 投到草稿箱

#### B. API Layer（结构化接口层）
作用：
- 给系统接入方调用
- 创建异步任务
- 拉取状态
- 拉取结果与资产包
- 触发草稿/发布动作

建议核心接口对象：
- `POST /topic-jobs`
- `POST /content-jobs`
- `POST /video-jobs`
- `POST /publishing-jobs`
- `GET /workflow-runs/:id`
- `GET /asset-bundles/:id`

#### C. Orchestrator Layer（异步执行层）
作用：
- 真正调度 skills / scripts / agents
- 拆阶段执行
- 做超时、重试、降级
- 写回状态与产物

### 5.2 聊天页建议结构
1. **输入区**：用户目标 / 素材 / 平台要求
2. **推荐动作区**：生成选题 / 成稿 / 改写 / 封面 / 视频脚本 / 入草稿
3. **任务状态区**：排队中 / 生成中 / 待确认 / 已完成 / 失败
4. **结果预览区**：文案、标题、图片、脚本、分镜
5. **继续操作区**：重写、扩写、平台适配、投递草稿、导出

### 5.3 API 原则
- API 不承担聊天体验
- 聊天页不暴露底层复杂执行细节
- 长任务必须异步
- 所有关键任务都必须可状态查询

### 5.4 content 能力资产映射（补齐版，可验收）

> 口径说明：
> - **成熟度**：`可直接用于MVP` / `需改造` / `仅概念`
> - **是否可进MVP**：`是` / `否`
> - **降级方式**：明确到“仅文本 / 仅草稿 / 人工接管 / 导出资产包”
> - **验收标准**：必须能指向真实 skill / script / SOP / workflow / 数据目录，而不是抽象能力名

| 能力项 | 真实资产映射 | 路径 | 成熟度 | 平台覆盖 | 是否可进MVP | 降级方式 | 验收说明 |
|---|---|---|---|---|---|---|---|
| 1. 热点采集 / 热点池 | 内容流水线 SOP + 热点池数据目录 | `/home/aa/clawd/workspace/content-pipeline/SOP.md`；`/home/aa/clawd/workspace/content-pipeline/hotpool/` | 需改造 | 通用（可供 XHS / GZH / Douyin / X / B站 等复用） | 是 | 仅文本热点清单；人工选题 | 已有按天落盘的 hotpool JSON，可证明不是空概念，但多源采集脚本未在当前仓内完整收口到统一入口 |
| 2. 选题评分 / 选题卡片 | 内容流水线 SOP + topics 数据目录 + 日更 skill 方法论 | `/home/aa/clawd/workspace/content-pipeline/SOP.md`；`/home/aa/clawd/workspace/content-pipeline/topics/`；`/home/aa/clawd/skills/daily-xhs-content/SKILL.md`；`/home/aa/clawd/skills/daily-gzh-content/SKILL.md`；`/home/aa/clawd/skills/daily-douyin-content/SKILL.md` | 需改造 | XHS / GZH / Douyin | 是 | 仅输出选题卡，不自动进入成稿 | 已有 topics 按日 JSON 与平台向 daily 生产规范，但缺统一 topic-scoring service |
| 3. 母稿生成 / 平台母文案 | 内容生产 SOP + 模板库 | `/home/aa/clawd/workspace/content-pipeline/MEDIA-SOP.md`；`/home/aa/clawd/workspace/content-pipeline/templates/content-checklist.md`；`/home/aa/clawd/workspace/content-pipeline/templates/operations-playbook.md` | 需改造 | 通用（XHS / GZH / Douyin / Juejin / ZSXQ 可复用） | 是 | 仅输出 markdown / txt 母稿 | 有 SOP、有模板，但缺单一“母稿生成脚本/接口”作为产品化入口 |
| 4. 小红书内容适配 | daily-xhs-content + xhs-smart-publisher 模板/规则 | `/home/aa/clawd/skills/daily-xhs-content/SKILL.md`；`/home/aa/clawd/repos/AGI-Super-Team/skills/xhs-smart-publisher/SKILL.md`；`/home/aa/clawd/repos/AGI-Super-Team/skills/xhs-smart-publisher/templates/content-style-guide.md` | 可直接用于MVP | XHS | 是 | 仅文本；仅草稿；人工接管发布 | 标题/正文/标签/封面规范已写死，且已有真实发布脚本 |
| 5. 公众号内容适配 | daily-gzh-content + wechat-mp-publisher 模板/规则 | `/home/aa/clawd/skills/daily-gzh-content/SKILL.md`；`/home/aa/clawd/repos/AGI-Super-Team/skills/wechat-mp-publisher/SKILL.md`；`/home/aa/clawd/repos/AGI-Super-Team/skills/wechat-mp-publisher/templates/content-style-guide.md` | 可直接用于MVP | GZH | 是 | 仅文本 html/md；仅草稿；人工群发 | 已支持正文、摘要、封面、草稿/API 双路径，适合作为 MVP 主交付链路 |
| 6. 抖音内容适配 | daily-douyin-content + douyin-smart-publish 模板/规则 | `/home/aa/clawd/skills/daily-douyin-content/SKILL.md`；`/home/aa/clawd/repos/AGI-Super-Team/skills/douyin-smart-publish/SKILL.md`；`/home/aa/clawd/repos/AGI-Super-Team/skills/douyin-smart-publish/templates/content-style-guide.md` | 可直接用于MVP | Douyin | 是 | 仅脚本/描述；仅草稿；人工接管发布 | 已验证图文草稿链路，默认草稿优先，符合 MVP“先可交付再全自动”原则 |
| 7. 掘金内容适配 | juejin-smart-publish 模板/规则 | `/home/aa/clawd/repos/AGI-Super-Team/skills/juejin-smart-publish/SKILL.md`；`/home/aa/clawd/repos/AGI-Super-Team/skills/juejin-smart-publish/templates/content-style-guide.md`；`/home/aa/clawd/repos/AGI-Super-Team/skills/juejin-smart-publish/scripts/publish.py` | 可直接用于MVP | Juejin | 是 | 仅 markdown 草稿；人工确认发布 | 掘金原生 Markdown 友好，技术上是低摩擦平台，适合做 MVP 扩展平台 |
| 8. 知识星球内容适配 | zsxq-publisher 模板/规则/API | `/home/aa/clawd/repos/AGI-Super-Team/skills/zsxq-publisher/SKILL.md`；`/home/aa/clawd/repos/AGI-Super-Team/skills/zsxq-publisher/scripts/publish.py`；`/home/aa/clawd/repos/AGI-Super-Team/skills/zsxq-publisher/scripts/publish_article.py` | 可直接用于MVP | ZSXQ | 是 | 仅文本发帖；仅 API 发帖；人工接管长文 | API 能力真实存在，长文需 browser 补位，适合做会员内容/私域交付 |
| 9. 封面策略生成 | content-cover-gen | `/home/aa/clawd/skills/content-cover-gen/SKILL.md` | 可直接用于MVP | XHS / GZH / Douyin / Juejin / ZSXQ / B站 | 是 | 仅输出封面提示词 / 视觉说明 | 已有平台比例、视觉隐喻、出图命令，不依赖人工拍脑袋 |
| 10. 图片生成引擎 | relay-image-gen | `/home/aa/.openclaw/skills/relay-image-gen/SKILL.md`；`/home/aa/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py` | 可直接用于MVP | 通用 | 是 | 仅提示词，不出图；人工换图 | 已有 provider fallback（boluobao → gemini → xingjiabi），是真实底层能力 |
| 11. 视频脚本模板 | 视频模板 + MEDIA-SOP + daily-douyin-content | `/home/aa/clawd/workspace/content-pipeline/templates/video-script-template.md`；`/home/aa/clawd/workspace/content-pipeline/templates/storyboard-template.md`；`/home/aa/clawd/workspace/content-pipeline/MEDIA-SOP.md`；`/home/aa/clawd/skills/daily-douyin-content/SKILL.md` | 可直接用于MVP | Douyin / 视频号 / Reels（结构上可复用） | 是 | 仅脚本；不进成片 | 视频脚本层已经足够售卖，不依赖成片自动化 |
| 12. 数字人 / 分镜拆解 | jimeng-storyboard | `/home/aa/.openclaw/skills/jimeng-storyboard/SKILL.md` | 需改造 | Douyin / 视频号 / 通用口播视频 | 是 | 仅输出分镜脚本；人工到即梦执行 | 分镜结构成熟，但离“产品内一键生成视频”还差平台接线 |
| 13. 视频生成引擎 | relay-video-gen | `/home/aa/.openclaw/skills/relay-video-gen/SKILL.md`；`/home/aa/.openclaw/skills/relay-video-gen/scripts/relay_video_gen.py` | 需改造 | Douyin / Reels / Shorts / 通用视频 | 否（首版不主打） | 仅脚本 / 分镜 / 素材建议 | 能生成短视频片段，但异步时长、稳定性、成本都不适合当 MVP 主交付承诺 |
| 14. 小红书草稿投递 | xhs-smart-publisher Playwright 发布/存草稿 | `/home/aa/clawd/repos/AGI-Super-Team/skills/xhs-smart-publisher/scripts/unified_publish.py`；`/home/aa/clawd/repos/AGI-Super-Team/skills/xhs-smart-publisher/scripts/publish.py` | 可直接用于MVP | XHS | 是 | 人工确认后存草稿；失败则导出文案包 | 已有 preview → 用户确认 → 存草稿/发布 机制，符合真实业务流程 |
| 15. 公众号草稿投递 | wechat-mp-publisher API / 浏览器双通道 | `/home/aa/clawd/repos/AGI-Super-Team/skills/wechat-mp-publisher/scripts/api_publish.py`；`/home/aa/clawd/repos/AGI-Super-Team/skills/wechat-mp-publisher/scripts/publish.py` | 可直接用于MVP | GZH | 是 | 仅保存草稿；人工群发 | 这是当前最稳妥的 MVP 投递能力之一 |
| 16. 抖音草稿投递 | douyin-smart-publish | `/home/aa/clawd/repos/AGI-Super-Team/skills/douyin-smart-publish/scripts/publish.py` | 可直接用于MVP | Douyin | 是 | 仅草稿；人工接管发布 | skill 明确默认只存草稿，且已有实战验证记录 |
| 17. 掘金草稿投递 | juejin-smart-publish Playwright/API 双通道 | `/home/aa/clawd/repos/AGI-Super-Team/skills/juejin-smart-publish/scripts/publish.py` | 可直接用于MVP | Juejin | 是 | 自动草稿；人工确认发布 | 技术社区平台最适合作为 MVP 扩展验证面 |
| 18. 知识星球投递 | zsxq-publisher API/browser | `/home/aa/clawd/repos/AGI-Super-Team/skills/zsxq-publisher/scripts/publish.py`；`/home/aa/clawd/repos/AGI-Super-Team/skills/zsxq-publisher/scripts/publish_article.py` | 可直接用于MVP | ZSXQ | 是 | API 发短帖；长文人工接管 | 对私域/付费社群交付有价值，且不依赖复杂前端自动化 |
| 19. 平台规则 / workflow 知识库 | 平台调研 workflow 文档 | `/home/aa/clawd/workspace/platform-publishing-research/xiaohongshu-workflow.md`；`/home/aa/clawd/workspace/platform-publishing-research/wechat-mp-workflow.md`；`/home/aa/clawd/workspace/platform-publishing-research/douyin-workflow.md`；`/home/aa/clawd/workspace/platform-publishing-research/juejin-workflow.md`；`/home/aa/clawd/workspace/platform-publishing-research/zsxq-workflow.md` | 可直接用于MVP | XHS / GZH / Douyin / Juejin / ZSXQ | 是 | 人工按规范执行 | 这些文档是产品参数表/自动化规则表的直接来源，不是附属材料 |
| 20. 统一内容流水线 / 资产沉淀 | content-pipeline 目录、配置、日志 | `/home/aa/clawd/workspace/content-pipeline/config/platforms.json`；`/home/aa/clawd/workspace/content-pipeline/publish-log.json`；`/home/aa/clawd/workspace/content-pipeline/drafts/`；`/home/aa/clawd/workspace/content-pipeline/assets/` | 需改造 | 通用 | 是 | 导出资产包；人工归档 | 已有目录骨架和历史数据，但还不是标准化 SaaS 资产库 |
| 21. Orchestrator / 异步工作流 | 仅有 workflow 研究与 loader，未形成产品级统一编排服务 | `/home/aa/clawd/WORKFLOW_AUTO.md`；`/home/aa/clawd/docs/WORKFLOW.md`；`/home/aa/clawd/scripts/workflow_loader.py`；`/home/aa/clawd/infra/temporal/workflows/` | 需改造 | 通用 | 是 | 手动串联 skill；按阶段交付 | 有编排痕迹，但没有对外稳定 API，属于“能搭 demo，不能直接当产品骨架” |
| 22. X / Twitter 内容发布 | 当前只有研究/读取相关 skill，无稳定发布资产映射 | `/home/aa/clawd/skills/x-tweet-fetcher/` | 仅概念 | X | 否 | 仅输出 tweet 文本 | 当前缺可验收的稳定“发布”链路，不能写进 MVP 承诺 |
| 23. 自动成片 / AI 配音 / 批量视频工厂 | relay-video-gen + jimeng-storyboard 可支撑探索，但未形成闭环 SOP | `/home/aa/.openclaw/skills/relay-video-gen/SKILL.md`；`/home/aa/.openclaw/skills/jimeng-storyboard/SKILL.md` | 仅概念 | Douyin / Shorts / Reels | 否 | 脚本 + 分镜 + 人工剪辑 | 可做二期探索，不应进入首版对外承诺 |

### 5.5 MVP 建议纳入范围（按“现在能交付”收口）

#### A. 必进 MVP（主链路）
1. 热点池 / 选题卡片（允许人工确认选题）
2. 母稿生成 + 平台适配（XHS / GZH / Douyin）
3. 封面提示词 + 图片生成
4. 视频脚本 / 分镜增强（只到脚本层）
5. 草稿投递（XHS / GZH / Douyin 至少 2-3 个最稳平台）
6. 资产包导出与失败降级

#### B. 可作为 MVP 扩展平台
- Juejin
- ZSXQ

#### C. 不应写进 MVP 承诺
- X 正式发布
- 自动成片
- AI 配音全自动
- 全平台正式发布闭环

### 5.6 当前可直接验收的结论

**已经真实存在、可被 PM 验收的不是“一个抽象内容工厂”，而是以下资产组合：**

1. **内容生产规范**：`/home/aa/clawd/workspace/content-pipeline/SOP.md`
2. **媒体生产全生命周期 SOP**：`/home/aa/clawd/workspace/content-pipeline/MEDIA-SOP.md`
3. **封面生成能力**：`/home/aa/clawd/skills/content-cover-gen/SKILL.md`
4. **出图引擎**：`/home/aa/.openclaw/skills/relay-image-gen/scripts/relay_image_gen.py`
5. **视频生成/分镜能力**：`/home/aa/.openclaw/skills/relay-video-gen/` + `/home/aa/.openclaw/skills/jimeng-storyboard/`
6. **小红书发布链路**：`/home/aa/clawd/repos/AGI-Super-Team/skills/xhs-smart-publisher/`
7. **公众号发布链路**：`/home/aa/clawd/repos/AGI-Super-Team/skills/wechat-mp-publisher/`
8. **抖音发布链路**：`/home/aa/clawd/repos/AGI-Super-Team/skills/douyin-smart-publish/`
9. **掘金发布链路**：`/home/aa/clawd/repos/AGI-Super-Team/skills/juejin-smart-publish/`
10. **知识星球发布链路**：`/home/aa/clawd/repos/AGI-Super-Team/skills/zsxq-publisher/`
11. **历史热点 / 选题 / 草稿 / 发布日志数据**：`/home/aa/clawd/workspace/content-pipeline/`

**因此，第⑤项的最终判断是：**
- **通过的部分**：内容适配、封面生成、草稿投递、视频脚本增强、平台规则知识库
- **需改造后才能产品化的部分**：统一 topic service、母稿 service、orchestrator、资产库/状态机 API
- **不能写进 MVP 的部分**：X 正式发布、自动成片、全自动多平台正式发布

---

## 6. 风险与降级

### 6.1 主要风险
1. 登录态失效
2. 平台 DOM / 浏览器自动化不稳定
3. 外部模型超时或质量波动
4. 图像生成不稳定
5. 视频链路时长过长或结果不稳
6. 平台风控导致投递失败

### 6.2 降级策略
#### 风险 1：投递失败
降级为：
- 输出草稿包
- 输出平台发布包
- 标记人工接管

#### 风险 2：图片失败
降级为：
- 只输出标题
- 输出封面 prompt
- 输出视觉建议

#### 风险 3：视频失败
降级为：
- 输出脚本
- 输出分镜
- 输出字幕稿
- 输出素材清单

#### 风险 4：长链路超时
降级为：
- 拆分阶段任务
- 允许部分完成
- 先交付可交付部分

#### 风险 5：单平台故障
降级为：
- 其他平台继续
- 故障平台待处理
- 不阻塞整单交付

### 6.3 原则
**先保“可交付”，再追“全自动”。**

---

## 7. 7天 / 30天路线图

### 7天路线图（目标：做出第一版可演示骨架）

#### Day 1-2：产品收口
- 完成产品定位与边界
- 明确目标用户分层
- 明确 MVP / 二期边界
- 输出 PRD 骨架

#### Day 2-3：信息架构与流程
- 画聊天页结构
- 画任务状态流转
- 画内容资产库结构
- 画 API / orchestrator / skill 分层图

#### Day 3-5：MVP 能力串联
- 选题 → 成稿 → 改写 → 封面 → 视频脚本 → 草稿投递
- 选 2-3 个最稳平台打通
- 定义任务对象和状态机

#### Day 5-7：原型与演示
- 做可点击前台原型 / 页面线框
- 输出一套 demo 数据
- 跑通一条真实 demo 链路
- 准备对内评审材料

### 30天路线图（目标：具备首批试用 / 付费验证条件）

#### Week 1：产品与架构定稿
- PRD
- 页面原型
- 工作流状态机
- API 草案

#### Week 2：核心链路开发
- 聊天任务入口
- 任务工作台
- 内容生成链路
- 多平台改写链路
- 资产库雏形

#### Week 3：交付链路开发
- 封面素材链路
- 视频脚本增强链路
- 草稿投递 / 导出能力
- 异常与降级机制

#### Week 4：试用验证
- 选首批内部/熟人客户
- 跑真实内容任务
- 收集失败点
- 调整套餐与交付边界
- 准备 first paid version

### 30天里不强求的事
- 自动成片成熟度
- 全平台稳定自动发布
- 复杂团队协作权限
- 深度数据看板

---

## 8. 当前建议的 first paid version

> **图文内容工厂 + 视频脚本/分镜增强 + 多平台草稿交付**

这是目前最合理的首版售卖边界，因为它同时满足：
- 价值感强
- 技术可复用度高
- 风险相对可控
- 最容易形成第一笔付费

---

## 9. 对 CEO 的明确建议

### 该收，不该再发散的点
- 先不要纠结“万能内容操作系统”叙事
- 先把第一版卖点收敛到“内容生产 + 草稿交付”
- 先把视频放在脚本增强层，不要硬上成片层
- 先用聊天页承接需求，用 API 承接系统能力，用 orchestrator 兜稳定性

### 今天 18:00 前必须产出的下一层材料
1. 页面级信息架构
2. 核心状态机
3. MVP 任务流
4. API 草案
5. 风险清单 + 降级清单
6. 7天 / 30天执行拆解

---

## 10. Round 2 收口结论（只保留产品化答案）

### 10.1 内容工厂最小稳定链路
- 聊天页/表单输入需求 → 生成 3-5 个选题候选
- 选定 1 个主题 → 生成母稿 + 标题 + 平台改写版本
- 自动补齐封面标题 / prompt / 配图建议
- 可选生成短视频脚本 + 分镜 + 字幕稿
- 投递到 2-3 个最稳平台草稿箱；失败时导出草稿包
- 全链路状态可追踪，任一阶段失败都允许部分交付

### 10.2 视频能力模块化建议
- 结论：**做一级模块，不做插件**；否则首版产品叙事会断裂
- 但交付边界只到“脚本增强层”，不要进“成片层”
- 最小可交付：15s/30s/60s 口播稿、Hook、分镜、字幕稿、首帧标题
- 输入优先支持两种：主题直出视频脚本、图文母稿转视频脚本
- 输出必须结构化，可直接给剪辑/外包/后续工具使用
- 自动成片、配音、批量混剪、视频自动发布统一放二期

### 10.3 可直接映射进 MVP 的 skills / workflows
- 选题/研究类：热点采集、选题推荐、平台适配判断工作流
- 内容类：母稿生成、多平台改写、标题/标签/CTA 生成链路
- 视觉类：封面标题提取、封面 prompt、图片生成链路
- 视频类：视频脚本、分镜、字幕稿、首帧标题生成链路
- 投递类：小红书 / 公众号 / 抖音中最稳的 2-3 个草稿投递 workflow
- 编排类：cron + agent + skills orchestration + 状态写回/失败重试

### 10.4 风险最大、必须人工兜底/降级的点
- 登录态失效 / 平台风控：必须人工接管，不要假装自动成功
- 平台 DOM / 浏览器自动化变化：投递失败时直接降级为草稿包导出
- 图片生成不稳：降级为封面标题 + prompt + 视觉说明
- 视频链路不稳：降级为脚本 + 分镜 + 字幕稿，不承诺成片
- 长链路超时：拆阶段执行，先交付已完成部分
- 模型输出质量波动：关键稿件保留人工审查节点，不全自动直发

### 10.5 客户第一笔钱最愿意买什么
- 最容易卖的不是“万能内容工厂”，而是 **稳定交付内容包**
- 第一优先售卖：图文内容工厂（选题 + 成稿 + 多平台改写 + 封面）
- 第二增强卖点：短视频脚本包（口播稿 + 分镜 + 字幕稿）
- 第三成交关键：草稿投递/导出闭环，而不是只给一段文案
- 客户最愿意为“省时间 + 可直接审 + 可直接发”付钱，不愿为复杂技术架构付钱
- 所以 first paid version 建议直接卖：**图文主链路 + 视频脚本增强 + 草稿交付**

## 11. 最终一句话

**这版不是“最炫”的内容工厂，但会是第一版最能交付、最能卖、最能往前迭代的骨架。**

---

## 12. 可验收场景（输入 → 处理 → 输出）

### 场景 A：创始人日更内容包
**输入：**
- 行业：AI / Agent
- 人设：产品负责人
- 平台：小红书 + 公众号
- 目标：今天要发 1 组内容

**处理：**
1. 生成 3 个候选选题
2. 用户选 1 个主题
3. 生成母稿
4. 改写成小红书版 + 公众号版
5. 生成封面标题 / prompt
6. 投递到草稿箱

**输出：**
- 3 个选题候选
- 1 篇小红书图文草稿
- 1 篇公众号长文草稿
- 2 组封面标题 / prompt
- 草稿投递状态

**验收标准：**
- 10 分钟内从一句需求到两个平台草稿
- 至少一个平台草稿可直接人工确认使用

### 场景 B：运营团队一稿多平台复用
**输入：**
- 已有一篇母稿
- 平台：小红书 / 公众号 / 抖音口播
- 风格：专业但口语化

**处理：**
1. 读取母稿
2. 多平台改写
3. 生成标题 / 摘要 / 标签
4. 生成 30 秒视频脚本
5. 汇总资产包

**输出：**
- 小红书版文案
- 公众号版长文
- 抖音口播稿
- 标题候选
- 评论区引导文案
- 资产包

**验收标准：**
- 同一母稿稳定产出至少 3 种平台版本
- 输出不是简单复制粘贴，而是有平台结构差异

### 场景 C：代运营客户周内容包交付
**输入：**
- 客户品牌资料
- 一周主题方向
- 目标：5 条图文 + 2 条视频脚本

**处理：**
1. 生成周选题计划
2. 批量生成图文内容
3. 生成视频脚本 / 分镜
4. 生成封面建议
5. 汇总为资产包或草稿结果

**输出：**
- 周选题清单
- 5 条图文成品
- 2 条视频脚本 + 分镜
- 封面素材建议
- 交付状态清单

**验收标准：**
- 能批量生成周内容包
- 能交付标准化结果，而不是散乱文本

---

## 13. 正式 MVP 主工作流

### 13.1 工作流名称
**内容包生产与草稿交付工作流**

### 13.2 标准流程
1. 用户在聊天页发起任务
2. 系统识别任务类型（选题 / 图文 / 视频 / 发布）
3. 信息不足时自动追问关键参数
4. 创建 `workflow_run`
5. 调用选题工作流（如需要）
6. 生成母稿
7. 生成多平台版本
8. 生成封面 / 视觉素材
9. 若启用视频增强，生成视频脚本 / 分镜 / 字幕稿
10. 若启用投递，执行草稿投递或导出交付
11. 写回资产库与任务状态
12. 在聊天页与任务工作台展示结果

### 13.3 阶段定义
- `intake`
- `planning`
- `generate_content`
- `adapt_platforms`
- `generate_assets`
- `generate_video_addon`
- `publish_or_export`
- `complete`

### 13.4 默认交付原则
**MVP 默认优先草稿交付 / 资产包交付，不默认承诺正式发布完成。**

---

## 14. 页面级 IA / 关键区块

### 页面 A：Agent 聊天页
关键区块：
1. 顶部任务模式切换（选题 / 图文 / 视频脚本 / 改写 / 草稿投递）
2. 中间对话区
3. 右侧实时任务卡
4. 下方快捷模板区
5. 结果预览抽屉

### 页面 B：任务工作台
关键区块：
1. 任务列表
2. 任务详情头部
3. 阶段进度条
4. 当前产物列表
5. 异常日志 / 失败原因
6. 重试 / 跳过 / 降级按钮

### 页面 C：内容资产库
关键区块：
1. 选题池
2. 母稿库
3. 平台版本库
4. 封面 / 图片库
5. 视频脚本 / 分镜库
6. 草稿 / 导出包库

### 页面 D：品牌与账号配置中心
关键区块：
1. 品牌语气卡
2. 禁用词 / 风格约束
3. 平台账号列表
4. 登录态状态
5. 平台能力状态（可投草稿 / 仅导出 / 故障）

### 页面 E：复盘面板
关键区块：
1. 今日生成数
2. 今日草稿数
3. 平台状态概览
4. 异常任务列表
5. 下轮选题建议

---

## 15. 最小状态机 + API 草案

### 15.1 `workflow_run` 状态
- `draft`：参数未补齐
- `queued`：已入队
- `running`：执行中
- `waiting_user`：等待用户确认 / 补参
- `partial_success`：部分完成，可交付
- `success`：完成
- `failed`：失败
- `cancelled`：取消

### 15.2 `publishing_job` 状态
- `not_requested`
- `ready_to_publish`
- `draft_submitted`
- `publish_pending_manual_confirm`
- `published`
- `publish_failed`
- `fallback_exported`

### 15.3 状态机原则
- 允许部分完成
- 允许人工接管
- 允许降级交付
- 不因单点失败清空整单结果

### 15.4 API 草案
#### 创建工作流任务
`POST /v1/workflows`

请求示例：
```json
{
  "type": "content_bundle",
  "input": {
    "brief": "给我今天 3 个 AI 产品方向的小红书选题，并扩成图文+30秒视频脚本",
    "persona": "产品负责人",
    "platforms": ["xhs", "gzh", "douyin"],
    "publish_mode": "draft_only"
  }
}
```

返回示例：
```json
{
  "workflow_run_id": "wf_123",
  "status": "queued"
}
```

#### 查询任务状态
`GET /v1/workflows/{workflow_run_id}`

返回关键字段：
- `status`
- `stage`
- `progress`
- `artifacts`
- `errors`
- `next_action`

#### 获取资产包
`GET /v1/workflows/{workflow_run_id}/assets`

#### 单能力接口
- `POST /v1/topics/generate`
- `POST /v1/content/generate`
- `POST /v1/content/adapt`
- `POST /v1/assets/covers`
- `POST /v1/video/scripts`
- `POST /v1/publishing/drafts`

#### 账号状态接口
`GET /v1/accounts`

返回关键字段：
- `platform`
- `account_name`
- `auth_status`
- `publish_capability`
- `last_check_at`

---
name: daniel-content-writing-style
description: 为明确以 A.A 身份发布的文章、教程、复盘或视频脚本建立证据账本并起草、改写或审稿；仅在当前核心版本获明确批准后，调用一个平台专业 Subagent 适配并由主 Agent 回审。不用于其他作者、纯选题或增长研究、摘要、发布或外部操作。
---

# A.A 内容写作准则

## 输入与项目覆盖层

遵守当前作用域内的 `AGENTS.md`。要求输入至少包含：

- 明确的 A.A 身份创作意图与任务；
- 原始素材、事实、自述或外部来源；
- 目标受众与希望解决的问题；
- 已知公开边界与禁止披露项。

若当前项目提供事实源、公开边界、人格或内容系统，按项目指令读取；不得假设固定文件名、路径或另一个 Skill 必然存在。缺少决定核心主张或公开边界的输入时，输出 `NEEDS_INPUT`、列出最小素材清单并停止。

本 Skill 只决定内容如何写。选题价值、商业判断与发布策略由当前项目配置的上游能力负责。普通起草只加载本文件、当前素材与边界；仅在解释风格依据、处理规则冲突或更新本 Skill 时读取 `references/writing-style-decisions.md`。验证或修改状态机时读取 `references/forward-test-receipt-2026-08-03.md`；其 SHA-256 不匹配时视为过期并重跑测试。

仅在进入 `PLATFORM_ADAPTATION` 或单独的已批准剪辑指导工作流时，读取 `references/platform-agent-registry.json`；其结构定义在 `references/platform-agent-registry.schema.json`。维护映射时运行 `python3 scripts/validate_platform_agent_registry.py --self-test` 和 `python3 scripts/test_validate_platform_agent_registry.py`，如能定位已安装的 AGI Super Team Codex 插件，再显式传入 `--plugin-root` 做版本与语义投影校验。普通写稿不得加载平台 Agent 全文。

## 核心结果

让读者首先产生：

> 这个人真的亲手做了，我也能照着试。

用趣味促成追更，用证据体现专业。不得主动摆出权威、导师或成功者姿态。

## 内容模式

先选择一个模式，再决定结构：

- `experiment`：真实实验与能力边界。
- `tutorial`：从目标到可复刻结果。
- `case_review`：失败、修复与新规则。
- `build_log`：正在构建的阶段进展。
- `opinion`：由事实或事件支持的个人判断。
- `style_review`：审查已有 A.A 草案，不自动重写或做平台适配。

结构项是编辑检查，不是必须显式出现的标题或固定句式。不要把示例句复制成口头禅。

## 阶段状态机

1. **EVIDENCE**：建立事实与证据账本。关键事实、身份或公开边界缺失时，输出 `NEEDS_INPUT` 并停止。
2. **CORE_DRAFT**：主 Agent 生成一个平台无关核心草案，标记唯一 `draft_version`，输出 `AWAITING_CORE_APPROVAL` 并停止。
3. **APPROVAL**：只有用户在看到当前 `draft_version` 后明确批准，才可继续。沉默、预先授权、模糊反馈或旧版本批准均无效；任何实质修改都会使批准失效。
4. **PLATFORM_ADAPTATION**：用户批准核心草案并选定一个平台后，调用恰好一个平台专业 Subagent。
5. **FINAL_AUDIT**：平台稿标记唯一 `platform_version`；主 Agent 独立回审。通过后输出 `AWAITING_FINAL_APPROVAL` 并停止。
6. **FINAL_APPROVAL**：只有用户在看到当前 `platform_version` 后明确批准，才输出 `PASS`。旧版本批准、沉默或预先授权无效；平台稿任何实质修改都会使最终批准失效。
7. **EXTERNAL_ACTION**：`PASS` 只表示内容版本获批，不等于授权保存草稿、发布、互动、投放或外联；任何外部操作始终需要单独明确授权。

已通过 `FINAL_APPROVAL` 的短视频脚本，如用户另行请求剪辑指导，进入独立 `POST_APPROVAL_EDITING`：必须提供已批准的 `platform_version`、脚本、素材清单、目标平台、时长与技术规格；解析并调用恰好一个 `short_video_editing_guidance` 专家。输出唯一 `editing_guidance_version` 后停在 `AWAITING_EDITING_GUIDANCE_APPROVAL`。缺输入返回 `NEEDS_INPUT`；角色或注册表失效返回 `SPECIALIST_UNAVAILABLE`；任何主张、证据或边界差异均 `BLOCK`。该流程只给剪辑决策，不生成、导出或发布视频。

`style_review` 使用独立 `STYLE_REVIEW / REVIEW_COMPLETE`：只审查时在 `style_review.decision` 返回 `PASS | REVISE | BLOCK` 并结束；若用户要求改写，则进入 `CORE_DRAFT`。若用户要求平台原生审查或改写，仍执行核心版本确认和单平台专家门。

若任务实际不属于 A.A 内容写作，返回 `OUT_OF_SCOPE / OUT_OF_SCOPE` 并停止使用本 Skill，但继续把用户任务交给合适的普通能力。内容已获批后若又请求外部操作而未提供独立授权，使用 `EXTERNAL_ACTION / EXTERNAL_AUTH_REQUIRED` 并停止；不得执行该操作。

## 证据账本

先列出 `source_manifest`：每项写明来源、覆盖的案例或阶段，以及范围状态 `user_confirmed | project_declared | partial | unknown`。`project_declared` 只表示项目将其指定为事实源，不表示用户在本轮逐项确认。不得因为某份材料没出现某个结果，就推断该结果从未发生；此时只能标为未知。涉及多平台、多案例或多轮实验时，先枚举范围，再判断证据是否够用。

给每个可发布主张分配 `claim_id`，并同时标注 `source_kind`：

- `primary_artifact`：原始日志、图片、输出文件或可复验结果。
- `project_record`：项目中的实验记录、事实文档或汇总，未直接复验原始产物。
- `user_statement`：A.A 在当前或既有明确记录中的自述。
- `external_source`：可解析的第三方来源。

证据状态使用：

- `observed`：主 Agent 实际检查过的文件、日志、图片或结果。
- `user_attested`：A.A 明确提供或确认的经历与感受。
- `third_party_cited`：有可解析来源的第三方事实。
- `missing`：缺少证据。
- `conflicted`：来源互相冲突。

同时标注 `allowed | redact | prohibited | unknown` 的公开状态。

第一人称经历必须由 A.A 提供或明确确认；客观结果必须有可定位证据。情绪只使用 A.A 原始表达或明确确认的自述，不要求外部证明，也不强制每篇出现。没有真实情绪素材时留空，不补写。

## 核心草案写法

### 开头功能

- 实验、教程、案例复盘：优先在前 3—5 句完成“具体痛点 → 真实结果或意外 → 对读者的价值”。
- 构建日志：使用“本期目标 → 当前进展或阻力 → 为什么值得继续看”。
- 观点：使用“具体事件或问题 → 明确判断 → 证据范围”。

不先讲长背景，不用空洞悬念。若没有真实意外，不制造意外。

### 正文推进

实验与案例默认只保留 2—3 个改变判断的转折。每个节点在自然叙事中完成：

1. 发生了什么；
2. 证据在哪里；
3. 为什么，用人话解释；
4. 读者如何判断、规避或复刻。

教程围绕准备条件、动作、预期结果、验收和恢复组织。观点围绕事实、推理、反例和边界组织。不要强迫所有模式套同一时间线。

### 人格与节奏

- 使用“我做给你看”为主，“我们一起研究”为辅。
- 呈现年轻、好奇、亲自折腾，偶尔自嘲，关键处判断坚定。
- 使用 1—3 句短段落；关键事实、判断和转折可单独成段。
- 一段只承担一个核心意思；避免一句一行的营销碎片体。
- 让情绪解释判断，让幽默来自真实翻车、认知反差和轻微自嘲。
- 先说人话，再给术语；不硬塞网络梗，不编段子。
- 明确表达个人观点，但用证据、推理、条件和边界托住。
- 删除不增加事实、动作、真实情绪、个人判断或必要转场的句子。
- 避免重复总结、抽象口号和高频模板句式，如连续使用“不是……而是……”或机械写“我的判断是”。

### 重点与复刻

每篇最多突出 1—3 个关键点；每个重点绑定证据，视觉强调不得超过证据强度。

需要读者复刻时，至少提供与本篇承诺范围相匹配的信息：

- 开始前准备什么；
- 预计时间、成本与环境；
- 每一步做什么；
- 看到什么算成功；
- 常见失败是什么；
- 如何恢复或停止；
- 隐私、安全和权利边界。

正文尽量不堆代码和参数。把必要命令、提示词、参数和检查表集中到文末“一键复制区”。高级原理放附录或独立内容。

### 真实素材与配图

- 只使用真实经历、运行、数据、作品、截图或可追溯来源。
- 不伪造聊天、后台、评价、终端、订单、互动或视频效果。
- 真实截图只做必要裁剪、脱敏和清晰度处理；加一句人话标注“看哪里、证明什么”。
- 不把日志重绘成无法核验的假终端，不用美化卡片冒充原始证据。
- 保护凭证、登录态、私人路径、雇主、客户和第三方隐私。
- 缺少关键素材时输出素材清单或占位说明，不用生成内容补假证据。

### 结论与读者动作

表达个人判断的功能，不强制逐字写“我的判断是”。紧跟证据、适用条件和不可外推范围。

核心草案只确定 `desired_reader_action`、`deliverable_asset` 与 `asset_ready`。具体使用评论关键词、链接、收藏、关注或无 CTA，由平台专家按目标平台选择。若资产尚未完成，不得承诺领取。

正常交付给用户时，只显示简短的事实边界、实际核心草案、复刻所需内容、已知缺口和批准请求；证据账本保留为内部审计信息，除非用户要求查看。不要让结构化字段挤占正文阅读。

## 平台专业 Subagent 契约

每次适配恰好调用一个平台专业 Subagent，不得在同一适配阶段追加第二个平台或剪辑角色。`references/platform-agent-registry.json` 是 capability、canonical role 与 runtime Agent 映射的唯一真源；不得在本文件另存 Agent ID。

| 稳定能力 | 目标平台或阶段 |
|---|---|
| `xiaohongshu_native_adaptation` | 小红书 |
| `wechat_official_native_adaptation` | 微信公众号 |
| `douyin_native_adaptation` | 抖音脚本级适配 |
| `bilibili_native_adaptation` | B站 |
| `x_native_adaptation` | X 帖子、线程或回复候选 |
| `zhihu_native_adaptation` | 知乎 |
| `short_video_editing_guidance` | 已批准脚本与素材的后续独立剪辑指导 |

### 专家解析门

1. 用目标平台选择一个 stable capability，并在注册表中解析 canonical role、合同和当前 runtime binding；不得通过字符串拼接猜 Agent ID。
2. `do_not_use_when` 优先于 `trigger`。把注册表中的角色特定必需输入与下方共享输入合并；缺少会改变结论的输入时输出 `NEEDS_INPUT`，不得调用 Agent。
3. 只有解析结果为 `OK`，或插件来源暂不可读但 Agent descriptor 精确匹配且快照仍有效时为 `PORTABLE_SNAPSHOT_OK`，才可委派。
4. 映射不存在、出现多个匹配、Agent 不可用、插件版本或语义投影漂移、快照过期时，输出 `SPECIALIST_UNAVAILABLE`，记录 `reason_code` 并停止；不得静默选择 latest、相邻角色或由主 Agent 代写。
5. 平台规则、格式偏好或算法结论是动态事实，必须另行核验当前一手来源；注册表只证明角色路由快照，不证明平台事实。

抖音策略角色只负责定位、钩子、口播脚本和高层镜头建议，不承担逐时间点剪辑。已有批准脚本和素材、仅需镜头取舍、节奏、字幕、声音或导出检查时，开启后续独立工作流，解析 `short_video_editing_guidance`；它不得与 `douyin_native_adaptation` 同轮调用。

Subagent 必须接收：

- 已批准的 `draft_version`；
- 不可变的主张、事实、证据和公开边界；
- 目标平台与当前日期；
- 允许改变的字段：标题、顺序、篇幅、节奏、视觉表达、口播形式和 CTA 表达。
- 注册表中对应 canonical role 的全部角色特定必需输入；
- 已解析的 `capability`、`canonical_role_ref`、`runtime_binding_id`、`registry_version` 与 `contract_version`。

Subagent 必须返回：

- `platform_content_candidate` 与 `platform_adaptation_brief`；
- `presentation_changes`；
- `claim_diff`、`evidence_diff`、`boundary_diff`；
- 未解决问题与平台时效假设。

主 Agent 必须从实际委派运行时事件捕获 `delegation_receipt`；不得要求 Subagent 自证调用次数，也不得采信它自报的 `task_ref` 或完成状态。回执字段以注册表合同为准，且必须能定位本次真实任务、解析状态和一次调用。

这些平台角色的原生基线交付多为策略、brief 或脚本框架。`platform_content_candidate` 是本 Skill 的附加 overlay 合同，目前证据等级仅为 `prompt-contract-only`；缺少任何必需输出、只返回 brief、伪造委派回执或调用次数不等于 1，均记为 `OUTPUT_CONTRACT_VIOLATION` 并 `BLOCK`，不得由主 Agent 补写成稿冒充专家输出。

`claim_diff`、`evidence_diff` 或 `boundary_diff` 任一非空时，主 Agent 必须 `BLOCK` 并要求同一个专家修订；`presentation_changes` 允许非空。平台算法、规则或偏好等易变结论必须核验当前来源并标注日期。

若所需专业角色不可用或注册表失效，输出 `SPECIALIST_UNAVAILABLE` 并停止；不得伪称已委派，也不得由主 Agent 绕过门禁。

## 主 Agent 最终审计

独立检查：

1. 每个事实性句子能否映射到原 `claim_id`；
2. 是否新增、夸大或删除条件、证据和公开边界；
3. 是否泄露凭证、路径、雇主、客户或第三方信息；
4. 是否保留 A.A 人格、重点、初学者复刻路径和真实资产状态；
5. 是否恰好使用一个平台专家；
6. 是否把专家自评误当成主审结论。

## 分阶段输出合同

只输出当前阶段需要的字段，不显示空字段，不把内部 YAML 原样倾倒给读者。

```yaml
stage: OUT_OF_SCOPE|EVIDENCE|CORE_DRAFT|STYLE_REVIEW|PLATFORM_ADAPTATION|FINAL_AUDIT|FINAL_APPROVAL|POST_APPROVAL_EDITING|EXTERNAL_ACTION
status: OUT_OF_SCOPE|NEEDS_INPUT|AWAITING_CORE_APPROVAL|REVIEW_COMPLETE|SPECIALIST_UNAVAILABLE|REVISE|BLOCK|AWAITING_FINAL_APPROVAL|AWAITING_EDITING_GUIDANCE_APPROVAL|EXTERNAL_AUTH_REQUIRED|PASS
content_mode: experiment|tutorial|case_review|build_log|opinion|style_review
draft_version: string|null

source_manifest:
  - source_ref: string
    covers: string
    scope_status: user_confirmed|project_declared|partial|unknown

claims:
  - claim_id: string
    claim: string
    source_ref: string|null
    source_kind: primary_artifact|project_record|user_statement|external_source
    evidence_status: observed|user_attested|third_party_cited|missing|conflicted
    publishability: allowed|redact|prohibited|unknown

key_takeaways:
  - point: string
    claim_id: string
    priority: 1|2|3

core_draft:
  content: string
  desired_reader_action: string|null
  deliverable_asset: string|null
  asset_ready: true|false|null
  approval_state: pending|approved|invalidated
  approved_version: string|null
  approval_source: explicit_user_message|null

beginner_reproduction:
  prerequisites: []
  time_and_cost: string|null
  version_or_environment: string|null
  steps:
    - action: string
      expected_result: string
      check: string
      common_failure: string
      recovery: string
  safety_notes: []
  known_gaps: []

style_review:
  issues: []
  decision: PASS|REVISE|BLOCK

platform_adaptation:
  platform_version: string
  capability: string
  specialist_resolution:
    canonical_role_ref: string|null
    runtime_binding_id: string|null
    registry_version: string
    contract_version: string|null
    status: OK|PORTABLE_SNAPSHOT_OK|UNAVAILABLE|STALE|INVALID
    reason_code: string|null
    checked_at: string
  delegated_agent: string
  delegation_receipt:
    capability: string
    canonical_role_ref: string
    runtime_binding_id: string
    registry_version: string
    contract_version: string
    resolution_status: OK|PORTABLE_SNAPSHOT_OK
    resolution_checked_at: string
    invocation_count: 1
    task_ref: string
    completion_status: completed
  content: string
  adaptation_brief: string
  presentation_changes: []
  claim_diff: []
  evidence_diff: []
  boundary_diff: []
  dated_platform_assumptions: []

editing_guidance:
  editing_guidance_version: string
  source_platform_version: string
  specialist_resolution:
    canonical_role_ref: string|null
    runtime_binding_id: string|null
    registry_version: string
    contract_version: string|null
    status: OK|PORTABLE_SNAPSHOT_OK|UNAVAILABLE|STALE|INVALID
    reason_code: string|null
    checked_at: string
  delegation_receipt:
    capability: short_video_editing_guidance
    canonical_role_ref: string
    runtime_binding_id: string
    registry_version: string
    contract_version: string
    resolution_status: OK|PORTABLE_SNAPSHOT_OK
    resolution_checked_at: string
    invocation_count: 1
    task_ref: string
    completion_status: completed
  editing_decision_sheet: string
  timeline_recommendations: []
  subtitle_sound_export_checklist: []
  claim_diff: []
  evidence_diff: []
  boundary_diff: []
  unresolved_questions: []
  approval_state: pending|approved|invalidated
  approved_version: string|null
  approval_source: explicit_user_message|null

main_audit:
  issues: []
  decision: PASS|REVISE|BLOCK

final_approval:
  approval_state: pending|approved|invalidated
  approved_platform_version: string|null
  approval_source: explicit_user_message|null

human_approval_required: []
```

## 硬门

- 关键主张为 `missing` 或 `conflicted`：`BLOCK`；非关键项删除或输出 `NEEDS_INPUT`。
- 第一人称情绪未经 A.A 提供或确认：省略，不得代写或推断。
- 读者只知道“很厉害”，不知道如何判断或复刻：`REVISE`。
- 正文代码墙遮蔽理解：`REVISE`，移动到一键复制区。
- 使用假截图或重绘终端冒充现场证据：`BLOCK`。
- 当前草案版本未获明确批准就生成任何平台版本：`BLOCK`。
- 注册表无效、过期、歧义或与已安装 Agent/插件语义投影不符仍继续委派：`BLOCK`。
- 生成平台版本时未恰好使用一个平台专家：`BLOCK`；角色不可用且未生成平台稿时使用 `SPECIALIST_UNAVAILABLE`。
- 平台专家只返回策略、brief 或框架，却由主 Agent 补写并冒充专家成稿：`BLOCK`。
- 剪辑指导与平台适配同轮调用、未提供获批脚本或素材，或把指导结果声称为已生成视频：`BLOCK`。
- 专家修改主张、证据或边界：`BLOCK`。
- CTA 承诺未完成资产却声称可领取：`BLOCK`。
- 未经独立授权请求发布、互动、投放或外联：`EXTERNAL_AUTH_REQUIRED`，不得执行。

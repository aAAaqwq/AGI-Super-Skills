---
name: xhs-skill
description: 小红书（创作者中心）登录拿 cookies、发布笔记、导出数据的单一入口技能（浏览器交互委托 agent-browser-stealth）
metadata: {"openclaw":{"emoji":"📌","stage":"workflow"}}
---

本技能是 `xhs-*` 的合并版，目标是让用户只需要 `clawhub install xhs-skill` 一次即可开始使用。

约束：

- 所有浏览器交互（打开页面/点击/输入/上传/截图/登录/导出）全部委托 `agent-browser-stealth`。
- 禁止在本仓库编写/维护发布编排脚本（如 `publish_from_payload`）；发布动作必须在会话中由 `agent-browser-stealth` 执行。
- 禁止使用 `agent-browser`（旧通道禁用，统一使用 `agent-browser-stealth`）。
- 所有敏感数据（cookies、导出文件、截图）只落地在本机 `data/` 目录，不要粘贴到聊天里。

执行硬约束（稳定性）：

- 同一 `agent-browser-stealth` session 禁止并发操作（串行执行），否则容易触发 `os error 35` 假失败。
- `snapshot` 的 ref 会漂移：关键动作前后必须重抓 `snapshot -i`，并用 `placeholder/role/text` 做二次定位兜底。
- 扫码不等于登录成功；必须做后验校验（见下方 A 节“登录成功判定”）。

## 安装

```bash
clawhub install xhs-skill
cd skills/xhs-skill
npm i
```

说明：`npm i` 仅用于本技能自带的本地 CLI（二维码解码、cookies 工具）。如果你不需要解码二维码/转换 cookies，也可以只用 `agent-browser-stealth` 完成扫码与导出。

## 目录约定（本机）

建议在你运行命令的工作目录下准备：

- `data/xhs_login_qr.png`：登录页二维码截图（PNG）
- `data/raw_cookies.json`：导出的原始 cookies（JSON）
- `data/xhs_cookies.json`：归一化后的 cookies（JSON）
- `data/exports/<YYYY-MM-DD>/`：导出数据（CSV/XLSX/截图）
- `data/assets/<YYYY-MM-DD>/`：发布笔记用的图标/配图素材与来源记录

```bash
mkdir -p data
```

## A. 登录（扫码）并保存 cookies

目标：登录小红书创作者中心并导出 cookies，避免频繁重复登录。

1. 用 `agent-browser-stealth` 打开登录页：

- `https://creator.xiaohongshu.com/login`
- 若默认展示「手机号/验证码登录」，点击「扫码」切换到二维码视图

2. 让 `agent-browser-stealth` 截图保存二维码（PNG）到 `data/xhs_login_qr.png`

3. （可选）用本地 CLI 解码二维码文本并打印 ASCII 二维码：

```bash
node ./bin/xhs-skill.mjs qr show --in ./data/xhs_login_qr.png
```

OpenClaw 回传规范（强制）：

- 禁止只回传文件路径（例如仅说 `data/xhs_login_qr.png`）。
- 必须先执行 `node ./bin/xhs-skill.mjs qr show --in ./data/xhs_login_qr.png`，然后把输出的二维码文本 + ASCII 二维码直接发给用户。
- 若会话支持图片渲染，再附上二维码截图绝对路径（或图片附件）作为补充。
- 发完二维码后必须暂停，等待用户确认“已扫码”再继续 cookies 导出。

推荐回传模板：

```text
请用小红书 App 扫这个二维码登录。
二维码文本: <qr_text>
<ASCII QR>
```

4. 用小红书 App 扫码完成登录后，导出 cookies 到 `data/raw_cookies.json`（不走 DevTools）：

```bash
agent-browser-stealth cookies --json > ./data/raw_cookies.json
```

5. 归一化 cookies 并保存到 `data/xhs_cookies.json`：

```bash
node ./bin/xhs-skill.mjs cookies normalize --in ./data/raw_cookies.json --out ./data/xhs_cookies.json
node ./bin/xhs-skill.mjs cookies status --in ./data/xhs_cookies.json
```

5.1 推荐用脚本做后验校验（可执行门禁）：

```bash
# 例：先让 agent-browser-stealth 记录当前 URL 与后台探测后的 URL
CURRENT_URL="$(agent-browser-stealth get url)"
agent-browser-stealth open https://creator.xiaohongshu.com/creator/home
PROBE_FINAL_URL="$(agent-browser-stealth get url)"

node ./scripts/verify_login.mjs \
  --cookies ./data/xhs_cookies.json \
  --current-url "$CURRENT_URL" \
  --probe-final-url "$PROBE_FINAL_URL" \
  --json
```

登录成功判定（强制）：

- 必须同时满足以下 2 条才可回报“登录完成”（`web_session` 不再作为硬依赖）：
- 当前 URL 已离开 `/login`
- 可访问创作者后台页面，且不会 401/回跳登录
- 加分项：cookies 中存在“session-like cookie”（例如 `web_session`，或 cookie 名含 `session`）。没有也可能可用，但稳定性更差。
- 任一强制条件不满足，必须回报“登录失败/未完成”，并重试登录流程；禁止误报成功。

登录结果输出契约（JSON）：

```json
{
  "task": "xhs_login",
  "ok": true,
  "checks": {
    "left_login": true,
    "backend_not_rejected": true,
    "has_session_like_cookie": true
  },
  "artifacts": {
    "qr_png": "data/xhs_login_qr.png",
    "raw_cookies": "data/raw_cookies.json",
    "normalized_cookies": "data/xhs_cookies.json"
  }
}
```

失败时 `ok=false`，并给出失败项（例如仍在 `/login`、或 probe 回跳），禁止输出“已完成”。

6. （可选）生成 `Cookie:` header：

```bash
node ./bin/xhs-skill.mjs cookies to-header --in ./data/xhs_cookies.json
```

失败回退：

- 二维码解码失败：通常是没有切到扫码视图或二维码太小，让 `agent-browser-stealth` 放大后重新截图（仍为 PNG）。
- cookies 归一化失败：保留原始 `data/raw_cookies.json`，后续再扩展兼容分支。

## A1. 防封/限流运行规范（强制）

核心结论：小红书风控主要看“节奏 + 指纹 + 行为 + IP + 账号权重”。工具本身不是主因，使用方式才是主因。

强制策略：

1. 真人节奏：
- 禁止连续无停顿点击/填写；关键动作之间必须随机停顿（建议 `1.2s~7s`）。
- 输入优先 `type --delay`（逐字），避免全量瞬时 `fill`。

2. 固定指纹：
- 运行发布流程时优先固定 `--profile`，并启用 `--headed`。
- 推荐同一账号长期复用同一个 profile 目录，不要每次新建临时环境。

3. 发布频率门禁：
- 同一 profile 默认 `24h <= 3` 篇。
- 两次发布最小间隔默认 `30` 分钟。
- 命中门禁必须中止，不允许强发。

4. 发布前预热行为：
- 先做一次短时正常浏览（首页/创作者后台停留 + 滚动），再进入发布页。
- 禁止“打开页面后立刻提交”。

5. 网络与设备：
- 禁止机房 IP / 高频切换代理。
- 优先家庭网络或手机热点；同账号尽量保持设备/IP 稳定。

6. 被限流后的处理：
- 限流：停自动化，回归手动正常使用 `3~7` 天。
- 封号：仅能申诉；换号时要同时更换 `profile + IP + 设备环境`。

## B. 发布笔记（图文/视频）

输入（用户提供）：

- 笔记类型：图文 或 视频
- 标题、正文、标签（必填）
- 话题（必填；做热点发布时必须是“今天热点”）
- 图片/视频路径（本机绝对路径优先）
- 图标/配图需求（可选）：关键词、风格（扁平/拟物/线性）、主色、是否透明背景
- 热点来源（必填）：来源名、来源 URL、来源日期（`YYYY-MM-DD`）

发布硬门禁（强制）：

1. 先把发布素材整理为 `data/publish_payload.json`（示例）：

```json
{
  "topic": "今日热点：xxxx",
  "source": {
    "name": "央视新闻",
    "url": "https://example.com/news",
    "date": "2026-02-12",
    "evidence_snippet": "2月12日该媒体报道提到：......",
    "key_facts": ["关键事实1（含日期/数字）", "关键事实2（含日期/数字）"]
  },
  "post": {
    "title": "20字内标题示例",
    "body": "不少于 80 字的正文......",
    "tags": ["#热点", "#今日新闻", "#小红书运营"],
    "real_topics": ["#人工智能", "#AI资讯", "#科技观察"],
    "media": ["/abs/path/cover.png", "/abs/path/card_1.png"]
  }
}
```

2. 发布前必须执行校验脚本：

```bash
# 普通模式
node ./scripts/verify_publish_payload.mjs --in ./data/publish_payload.json --policy ./config/verify_publish_policy.json --tag-registry ./data/tag_registry.json --min-registry-tags 12 --require-source-evidence on --strict-anti-ai on --json

# 今天热点模式（强制 source.date = 今天）
node ./scripts/verify_publish_payload.mjs --in ./data/publish_payload.json --policy ./config/verify_publish_policy.json --tag-registry ./data/tag_registry.json --min-registry-tags 12 --require-source-evidence on --strict-anti-ai on --mode hot --json
```

3. 发布前必须执行内容审核脚本（分层规则 + AI）：

```bash
node ./scripts/review_publish_payload.mjs --in ./data/publish_payload.json --policy ./config/review_policy.json --taxonomy ./config/review_taxonomy.json --ai-provider auto --require-ai off --mode hot --json
```

4. 只有当校验和审核结果都 `ok=true` 才允许进入发布页点击“发布/提交”。
   校验策略在 `./config/verify_publish_policy.json`，审核策略在 `./config/review_policy.json`，分层风险路径在 `./config/review_taxonomy.json`。
5. 任一门禁失败必须中止流程并提示补齐，禁止“只传截图直接发”。

禁止链接（强制）：

- 标题/正文/标签里禁止出现任何链接或域名形态（`http/https`、`www.`、`xxx.com/.cn/...`）。否则有封禁风险。
- 如果内容生成遇到困难或校验不通过：宁可中止，不要“随便发一条”。

反 AI 识别与真实标签（强制）：

- 不承诺“100% 不被识别为 AI”；目标是显著降低风险。
- 正文必须有“个人视角 + 具体事实信号（数字/日期/来源提及）”，并规避模板腔。
- 发布前必须通过 `review_publish_payload` 审核门禁，要求 `decision=pass`，并输出 `risk_path`、证据和 `review_queue` 供复核。
- `source.evidence_snippet` 与 `source.key_facts` 必填，且能回溯到来源事实。
- 标签与 `post.real_topics` 都必须来自真实话题池 `data/tag_registry.json`，禁止自造标签。
- 禁止自动把 `#标签` 拼进正文冒充话题。
- 发布前必须在小红书发布页手动选择至少 3 个真实话题，然后由 `agent-browser-stealth` 执行最终点击发布。

示例：准备真实标签池（建议每天更新）：

```bash
cat > ./data/tag_registry.json <<'JSON'
{
  "updated_at": "2026-02-24",
  "source": {
    "platform": "xiaohongshu",
    "method": "manual_from_publish_topic_picker",
    "url": "https://creator.xiaohongshu.com/creator/publish"
  },
  "tags": ["#AI热点", "#人工智能", "#行业观察", "#科技新闻", "#AI资讯", "#科技观察"]
}
JSON
```

发布执行方式（唯一）：

- 本仓库只负责“数据准备 + 门禁校验 + 审核校验”；不再提供发布自动化脚本。
- 浏览器动作必须由 `agent-browser-stealth` 串行执行：预检 -> 填充 -> 读回校验 -> 发布 -> 回查。
- 若任一门禁失败（`verify/review` 非 `ok=true`），必须停止在“发布前”，禁止继续点击提交。

P0：发布编排器（流程编排，不是仓库脚本）：

1. 预检：
- 入口路由固定从 `https://creator.xiaohongshu.com/publish/publish` 进入；禁止把 `/creator/*` 作为首入口。
- 若被跳到 `https://creator.xiaohongshu.com/new/home`（“你访问的页面不见了”），立即回到 `/publish/publish` 重试。
- 进入发布页后先切到“图文”模式，再上传图片；未切图文不进入后续步骤。
2. 填充：
- 写标题、正文、标签/话题、可见性。
3. 读回校验：
- 校验通过才允许点击发布。
4. 发布：
- 点击发布后等待页面状态稳定并记录 URL。
5. 回查：
- 先检查 URL 参数包含 `published=true`；
- 再从页面菜单进入“笔记管理”做二次确认，不允许硬编码管理页直链回查。

P0：路由与状态稳定性（强制）：

- 稳定入口只认 `/publish/publish`；其他页面只作为中转，不作为成功判定依据。
- “发布页可用”不等于“管理页可用”：发布后必须菜单跳转二次查验。
- 若发布页元素未出现，先检查是否处于“图文模式 + 图片已上传”状态，再判断失败。

P0：选择器双通道（强制）：

- 第一通道（默认）：语义定位（`placeholder + role + 可见性 + 附近文案`）。
- 第二通道（兜底）：DOM 结构线索定位（例如标题输入框 placeholder 语义 + 正文编辑器 `tiptap/ProseMirror` 语义类名）。
- 禁止只依赖 `snapshot ref` 或 `@e1/@e2` 序号；每个关键动作前后都要 `snapshot -i` 二次确认。
- DOM 兜底只作为会话级临时手段，命中后仍需“读回校验”确认字段正确，不把脆弱 selector 当硬依赖。

P0：写入可靠性（强制）：

- 标题字段必须满足：单行、可见、可编辑、placeholder 命中“标题”语义。
- 正文字段必须满足：多行或 `contenteditable`、可见、可编辑、placeholder/附近文本命中“正文/内容”语义。
- 写入后必须做“双向读回校验”：同时读取标题和正文，计算 `title_len` 与 `body_len`。
- 错位判定：若 `title_len > 20` 且 `body_len < 80`，或标题命中长段正文特征（大量换行/句号），判定为写入错位。
- 错位自愈：自动执行“交换重写”一次（清空标题与正文 -> 标题写短标题 -> 正文写正文 -> 读回再校验）；仍失败则中止并回报失败，不允许继续提交。
- 强制规则：标题禁止包含 `#` 标签、长段正文、链接；标签必须通过小红书发布页“标签/话题交互”选择，不把标签文本塞进标题。

P0：草稿确认闭环（强制）：

1. 点击“暂存离开”后，必须等待并验证“保存成功/已保存草稿”类 toast。
2. 进入草稿列表，验证出现“新草稿条目”。
3. 新条目校验最少包含：
- 标题前缀匹配本次标题；
- 时间戳在本次运行窗口内（建议 2 分钟内）；
- 打开草稿后读回 `title/body/media/tags` 仍满足门禁。
4. 任一校验失败判定为“草稿保存失败”，允许重试 1 次；重试后仍失败则中止流程。

P0：图片预处理（无脚本版）：

- 不新增仓库脚本；统一采用“发布前本地预处理 + 读回尺寸确认”。
- 推荐目标尺寸：`1242x1660`（3:4 竖版）。
- 可选命令（单次执行，不落仓库脚本）：

```bash
# macOS: 先居中裁剪再缩放到 1242x1660（按需替换输入输出路径）
sips -c 1660 1242 ./data/assets/in.png --out ./data/assets/out_1242x1660.png
```

- 上传后必须在发布页确认缩略图比例正常；若拉伸/裁切异常，先替换素材再继续。

P0：发布前硬校验（强制）：

- 标题长度 `<= 20`。
- 正文长度 `>= 80`。
- 已上传图片（图文至少 1 张，且可见缩略图）。
- 已选择真实话题 `>= 3`（通过小红书话题交互选择，不是正文拼接）。
- 标题/正文/标签无链接词（`http`、`https`、`www.`、域名形态）。
- 任一不满足直接中止，不允许“先发再修”。

P0：发布后双重确认（强制）：

1. 第一重：发布后 URL 含 `published=true`。
2. 第二重：从发布页菜单进入“笔记管理”，确认列表出现新笔记（标题前缀 + 时间窗口）。
3. 管理页若被重定向或不可达，判定“回查未完成”，记录 `run_log` 并提示人工复核。

P1：热点到 payload 半自动（无脚本版）：

- 不新增 `newsnow -> payload` 代码生成器；改为会话模板填充。
- 采集热点后，按以下模板生成 `data/publish_payload.json`，人工只改“观点段”：

```json
{
  "topic": "今日热点：<主题>",
  "source": {
    "name": "<来源名>",
    "url": "<来源URL>",
    "date": "YYYY-MM-DD",
    "evidence_snippet": "<原文证据摘录>",
    "key_facts": ["<事实1：含日期/数字>", "<事实2：含日期/数字>"]
  },
  "post": {
    "title": "<8-20字标题，不含标签>",
    "body": "<观点段+事实段，不少于80字>",
    "tags": ["#标签1", "#标签2", "#标签3"],
    "real_topics": ["#真实话题1", "#真实话题2", "#真实话题3"],
    "media": ["/abs/path/1.png"]
  }
}
```

P1：标签/话题池维护（无脚本版）：

- 每天第一次发布前，手动刷新一次 `data/tag_registry.json`（从小红书发布页话题选择器抄录）。
- 若当天未刷新，流程必须回报风险提示并建议先刷新后再发布。
- 门禁保持不变：`tags` 与 `real_topics` 都必须命中 `tag_registry`。

P1：流程可观测（无脚本版）：

- 每次运行结束都产出 `data/run_log/<YYYY-MM-DD_HH-mm-ss>.json`（手工写文件即可，不新增脚本）。
- 建议字段：`steps`、`durations_ms`、`failed_step`、`error_message`、`screenshots`、`result_url`、`draft_check`、`editor_check`、`route_check`、`post_publish_check`。

P1：固定模板（强烈建议）：

- 固定标题模板：`[主题词]+[观点/结论]`，目标 12~18 字，留 2~8 字缓冲避免超长。
- 固定正文模板：`开场观点 -> 事实1 -> 事实2 -> 个人判断 -> 行动建议`，默认 >120 字。
- 固定标签与话题池：仅从 `data/tag_registry.json` 选取，避免临场造词导致门禁失败。

P2：回归用例（每日 smoke，手工执行）：

- 场景 1：仅存草稿（不发布）。
- 场景 2：草稿后二次编辑再存草稿。
- 场景 3：正式发布（通过全部门禁）。
- 每个场景都输出一份 `run_log`，用于对比“定位稳定性/错位率”。

流程（浏览器侧全部由 `agent-browser-stealth` 完成）：

1. 确保已登录（先完成上面的 A，或已有有效登录态）。
2. 准备并校验 `data/publish_payload.json`（必须 `ok=true`）。
3. 打开 `https://creator.xiaohongshu.com/publish/publish`，先 `snapshot -i` 获取最新结构。
4. 切图文模式并上传媒体（确认缩略图比例与数量）。
5. 用“语义定位优先 + DOM 兜底”填写标题与正文，写入后执行“双向读回校验 + 错位自愈”。
6. 通过小红书标签交互选择标签与真实话题（至少 3 个），不要把标签写进标题。
7. 执行发布前硬校验（标题、正文、图片、话题、无链接词）。
8. 点击“暂存离开”并执行草稿闭环校验（toast + 列表新条目 + 读回）。
9. 点击“发布/提交”前暂停，要求用户确认最终预览。
10. 发布后执行双重确认（`published=true` + 菜单进入笔记管理二次查验），并写入 `run_log`。

发布结果输出契约（JSON）：

```json
{
  "task": "xhs_publish",
  "ok": true,
  "result_url": "https://creator.xiaohongshu.com/....",
  "content_checks": {
    "title_len": 18,
    "body_len": 136,
    "tag_count": 3,
    "real_topic_count": 3,
    "editor_alignment_ok": true,
    "draft_saved_ok": true,
    "publish_precheck_ok": true,
    "published_param_ok": true,
    "manage_menu_check_ok": true,
    "topic": "今日热点：xxxx",
    "source_date": "2026-02-12"
  },
  "artifacts": {
    "payload_json": "data/publish_payload.json",
    "media_inputs": ["..."],
    "run_log_json": "data/run_log/2026-02-27_14-36-00.json",
    "error_screenshot": null
  }
}
```

发布失败时 `ok=false`，并返回 `error_message`、`error_screenshot` 路径、未通过的 `missing_checks` 与 `failed_stage`（`preflight/fill/readback/publish/postcheck`）。

## C. 导出创作者中心数据（CSV/XLSX 或截图）

目标：把创作者中心关键数据导出到 `data/exports/<YYYY-MM-DD>/`，用于后续分析。

1. 确认已登录。
2. 用 `agent-browser-stealth` 进入创作者中心的常用分析页（仪表盘/内容分析/粉丝分析）。
3. 每个页面：
- 优先使用页面自带导出（如有）到 `data/exports/<date>/`
- 无导出时：保存关键区块截图到同目录
4. 记录：导出时间范围、口径说明、页面 URL。

## 本地 CLI（本技能自带）

命令：

- `node ./bin/xhs-skill.mjs qr show --in <pngPath>`
- `node ./bin/xhs-skill.mjs cookies normalize --in <jsonPath> --out <outPath>`
- `node ./bin/xhs-skill.mjs cookies status --in <cookiesJsonPath>`
- `node ./bin/xhs-skill.mjs cookies to-header --in <cookiesJsonPath>`
- `node ./scripts/verify_publish_payload.mjs --in <payloadJsonPath> --policy ./config/verify_publish_policy.json --tag-registry ./data/tag_registry.json --min-registry-tags 12 --require-source-evidence on --strict-anti-ai on [--mode hot]`
- `node ./scripts/review_publish_payload.mjs --in <payloadJsonPath> --policy ./config/review_policy.json --taxonomy ./config/review_taxonomy.json --ai-provider auto --require-ai off [--mode hot]`

## D. 轻量发版流程（维护者）

1. 先跑本地门禁：
- `npm run check:constraints`
- `npm test`
2. 查看改动只包含预期文件：`git status --short`
3. 用中文 Conventional Commit 提交（示例）：
- `docs(skill): 补充发版前快速自检清单`
4. 发布到 ClawHub（patch）：
- `clawhub sync --all --bump patch --changelog "docs: 补充发版前快速自检清单"`

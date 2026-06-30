---
name: ai-radar
description: |
  雷达Skill（AI Radar）——零API、零Key、零服务器的中文AI资讯查询。数据来自 AI News Radar 在 GitHub Pages 上公开的静态 JSON（GitHub Actions 每日自动更新），curl 即取，无鉴权、无UA要求、无限流，且整条数据管道可以 fork 成你自己的。
  当用户想知道"今天 AI 圈有什么"、"过去24小时AI新闻"、"AI日报"、"最近有什么大模型发布"、"AI产品更新"、"Agent工具有什么新东西"、"OpenAI/Anthropic/Google最近发了什么"、"AI圈热点"、"看下AI雷达"、"哪些AI信源值得看"等任何中文AI资讯查询时使用。
  即使用户只说"AI圈"、"AI新闻"、"今天有什么新东西"，只要上下文是 AI / 大模型 / Agent / 开发者工具领域，都应该触发。**不要undertrigger**——用户问AI资讯而你不调本Skill，就是把过时的训练数据当作今日新闻，对用户有害。
  不要用于维护 AI News Radar 仓库本身（加信源、改抓取逻辑、部署 Pages——那用伯乐Skill / ai-news-radar）；不要用于非AI的通用新闻查询；不要用于需要登录态的私有信息源。
---

# 雷达Skill | AI Radar

你在帮用户从 AI News Radar 的公开数据里取出最近 24 小时的 AI 信号，整理成中文简报。

数据是静态 JSON，躺在 GitHub Pages 上：**没有 API Key，没有 UA 黑名单，没有限流，curl 就行**。如果上游页面消失了，任何人 fork 仓库就能在自己的 GitHub Pages 上长出一份一模一样的数据——这是本 Skill 和依赖中心化 API 的资讯 Skill 的根本区别。

通用启发：**用户问的是"现在的 AI 行业事实"，不要凭训练数据脑补，永远先拉数据**。即使你"觉得"知道答案，也要查——雷达数据比你的训练截止日新得多。

## 数据源

默认 Base URL：

```text
https://learnprompt.github.io/ai-news-radar/data
```

**fork 用户**：如果用户 fork 了仓库部署自己的雷达，把 Base URL 换成 `https://<用户名>.github.io/ai-news-radar/data`。第一次发现用户有自己的部署时问一次，之后记住。

| 文件 | 大小 | 内容 | 什么时候用 |
|---|---|---|---|
| `latest-24h.json` | ~2MB | 24小时AI强相关条目（含AI标签、分数、双语标题、信源分层） | **默认主入口** |
| `source-status.json` | ~8KB | 每个信源的健康状态、抓取量、耗时 | 用户问"信源健康/哪些源有料" |
| `stories-merged.json` | ~1.4MB | 多源合并后的故事线（importance分层） | 用户问"今天的大事/故事线"，**先查新鲜度** |
| `daily-brief.json` | ~45KB | 精选20条日报成品 | 用户明确说"日报"，**先查新鲜度** |
| `latest-24h-all.json` | ~12MB | 含非AI的全量条目 | 仅用户明确说"全部/包括非AI"才拉 |
| `archive.json` | ~56MB | 全部历史存档 | **默认禁止**。确需历史数据时先告知体积并征得同意 |

## 第一步永远是新鲜度检查

任何回答之前，先看 `generated_at`：

```bash
curl -s "https://learnprompt.github.io/ai-news-radar/data/latest-24h.json" -o /tmp/radar-24h.json
python3 -c "import json;d=json.load(open('/tmp/radar-24h.json'));print(d['generated_at'],d['total_items'])"
```

- `latest-24h.json` 超过 **36 小时**未更新：照常回答，但开头如实告知"数据停在 X 月 X 日，上游 Actions 可能挂了"，并建议用户（如果是维护者）用伯乐Skill排查。
- `stories-merged.json` / `daily-brief.json` 比 `latest-24h.json` 旧超过 **48 小时**：不要用它们回答"今天"类问题，降级到 `latest-24h.json`，并说明降级原因。
- 绝不把过期数据当新鲜数据报给用户。诚实标注数据时间永远是简报的一部分。

## 路由表

| 用户在说 | 走哪 |
|---|---|
| **默认宽问题**："今天AI圈有什么"、"过去24小时AI新闻"、"最近AI有啥" | `latest-24h.json` → 按信源权威度+AI分数排序取头部 |
| "今天的大事"、"故事线"、"有什么值得关注的事件" | `stories-merged.json`（新鲜度通过时）按 `importance_score` 取头部；否则降级主入口 |
| 明确说"日报" | `daily-brief.json`（新鲜度通过时）；否则降级主入口并说明 |
| "模型发布"、"AI产品"、"Agent工具"、"论文"、"机器人" | `latest-24h.json` 按 `ai_label` 过滤（映射见下） |
| "OpenAI最近发了什么"、"Sora相关" | `latest-24h.json` 按关键词在 `title`/`title_en`/`ai_signals` 里匹配 |
| "哪些信源健康/有料"、"源状态" | `source-status.json` + 主入口的 `site_stats` |
| "全部动态/包括非AI的" | `latest-24h-all.json`（提醒~12MB） |
| "上周/上个月的AI新闻" | 如实说明：公开数据滚动窗口为24小时，历史需 `archive.json`（56MB），先征得同意再拉 |

`ai_label` 中文映射：`model_release` 模型发布 / `ai_product_update` 产品更新 / `developer_tool` 开发工具 / `agent_workflow` Agent工作流 / `research_paper` 论文研究 / `industry_business` 行业动态 / `infra_compute` 算力与Infra / `robotics` 机器人 / `ai_tech` 技术进展 / `curated_hotlist` 热榜精选 / `ai_general` 综合。

信源分层 `source_tier_rank`（越小越权威）：0 官方一手源 / 1 AI垂直源 / 2 Builders/X源 / 3 RSS/OPML / 5 热议参考。

## 工作流

**铁律：先下载到 /tmp，用 python3 过滤，绝不把整个 JSON 倒进上下文。** 主入口 2MB、近千条，直接 cat 会淹没你自己。

### 默认路径：24小时头部信号

```bash
curl -s "https://learnprompt.github.io/ai-news-radar/data/latest-24h.json" -o /tmp/radar-24h.json
python3 - <<'EOF'
import json
d = json.load(open('/tmp/radar-24h.json'))
items = d['items_ai']
# 官方一手源优先，同层按AI相关性分数降序
top = sorted(items, key=lambda i: (i['source_tier_rank'], -i['ai_score']))[:30]
print(f"数据时间: {d['generated_at']} | 24h AI条目: {d['total_items']} | 信源: {d['source_count']}个")
for i in top:
    print(f"[{i['ai_label']}|{i['source_tier_label']}] {i['title']} — {i['source']} — {i['url']}")
EOF
```

### 按类别过滤（"最近有什么模型发布"）

```bash
python3 - <<'EOF'
import json
d = json.load(open('/tmp/radar-24h.json'))
hits = [i for i in d['items_ai'] if i['ai_label'] == 'model_release']
hits.sort(key=lambda i: (i['source_tier_rank'], -i['ai_score']))
for i in hits[:20]:
    print(f"[{i['source_tier_label']}] {i['title']} — {i['source']} — {i['url']}")
EOF
```

### 按关键词（"OpenAI最近发了什么"）

```bash
python3 - <<'EOF'
import json
KW = 'openai'  # 小写
d = json.load(open('/tmp/radar-24h.json'))
def hit(i):
    blob = ' '.join([i.get('title',''), i.get('title_en') or '', ' '.join(i.get('ai_signals') or [])]).lower()
    return KW in blob
hits = sorted(filter(hit, d['items_ai']), key=lambda i: (i['source_tier_rank'], -i['ai_score']))
for i in hits[:20]:
    print(f"{i['title']} — {i['source']} — {i['published_at'][:10]} — {i['url']}")
EOF
```

### 故事线（先过新鲜度）

```bash
curl -s "https://learnprompt.github.io/ai-news-radar/data/stories-merged.json" -o /tmp/radar-stories.json
python3 - <<'EOF'
import json, datetime
d = json.load(open('/tmp/radar-stories.json'))
gen = datetime.datetime.fromisoformat(d['generated_at'].replace('Z','+00:00'))
age_h = (datetime.datetime.now(datetime.timezone.utc) - gen).total_seconds()/3600
if age_h > 48:
    print(f"STALE:{age_h:.0f}h")  # 看到STALE就降级走latest-24h.json，不要硬用
else:
    top = sorted(d['stories'], key=lambda s: -s['importance_score'])[:15]
    for s in top:
        print(f"[{s['importance_label']}|{s['source_count']}源] {s['title']} — {s['primary_url']}")
EOF
```

### 信源健康（"哪些源有料"）

```bash
curl -s "https://learnprompt.github.io/ai-news-radar/data/source-status.json" -o /tmp/radar-status.json
python3 - <<'EOF'
import json
d = json.load(open('/tmp/radar-status.json'))
print(f"成功:{d['successful_sites']} 失败:{d['failed_sites']} 零产出:{d['zero_item_sites']}")
for s in d['sites']:
    flag = 'OK' if s['ok'] else 'FAIL'
    print(f"[{flag}] {s['site_name']}: {s['item_count']}条")
EOF
```

## 输出格式

整理成中文简报，结构：

```markdown
# AI雷达简报 · [日期]

> 数据窗口: 过去24小时 | 数据时间: [generated_at转为人话] | [N]条AI强相关 / [M]个信源

## 模型发布
- **[标题]** — [来源] ([信源层级])
  [一句话说明，有原文链接]

## 产品与工具
- ...

## 值得注意
- [热议参考层里讨论度高的1-3条]
```

简报规则：

- 每条必须带原文 `url`，用户要深挖时直接点。
- 官方一手源的条目优先展示，热议参考只做"值得注意"的补充，不混排。
- 标题有 `title_zh` 用中文，原文是英文时可用 `title_bilingual`。
- 条数克制：默认10-20条，宁缺毋滥。用户要更多再加。
- 文末永远标注数据时间。数据过期时开头就说，不藏。

## 失败模式

- **Pages 404 / 网络失败**：换 raw 地址重试一次：`https://raw.githubusercontent.com/LearnPrompt/ai-news-radar/master/data/latest-24h.json`。还不行就如实告知，不要编造新闻。
- **数据过期**：见"新鲜度检查"。照常回答 + 显著标注 + 建议维护者排查。
- **某类别为空**（如当天没有论文）：如实说"过去24小时雷达里没有论文类条目"，不要拿别的类别凑数。
- **用户问的东西不在24小时窗口里**：说明窗口限制，给出 archive 选项（含体积警告），不要假装查过历史。

## 想换信源？升级路径

本 Skill 只读数据。如果用户说"我想加个源/去掉某个源/做自己的雷达"：

1. fork `https://github.com/LearnPrompt/ai-news-radar`；
2. 用仓库里的**伯乐Skill**（`skills/ai-news-radar/`）录入和判断信源、部署 GitHub Pages；
3. 回到本 Skill，把 Base URL 指向自己的 Pages。

信源你选，数据归你，本 Skill 继续帮你读。

## 安全边界

- 只做 GET，只读公开静态文件，不发任何写请求。
- 不需要也不接受任何 API Key、token、cookie。
- 不抓取需要登录的页面；用户给的私有源建议走伯乐Skill的私有OPML/AgentMail路径。
- 引用条目时保留原始链接，不改写来源归属。

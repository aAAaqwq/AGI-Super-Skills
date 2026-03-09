#!/usr/bin/env python3
"""
选题评分脚本 — 从热点池筛选 Top 10 推荐选题

读取 hotpool/YYYY-MM-DD.json → LLM评分 → 排序 → 生成选题卡片 → 保存+推送

用法:
    python topic_scorer.py                    # 评分今天的热点池
    python topic_scorer.py --date 2026-02-19  # 指定日期
    python topic_scorer.py --top 5            # 只取 Top 5
    python topic_scorer.py --no-send          # 不推送，只输出
    python topic_scorer.py --dry-run          # 不调LLM，用随机分
"""

import json
import os
import sys
import subprocess
import argparse
import time
from datetime import datetime
from pathlib import Path

# 清除代理，避免 SSL EOF 错误
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(k, None)

# === 路径配置 ===
from paths import HOTPOOL_DIR, TOPICS_DIR, FETCH_ALL, NEWSBOT_SEND

# === LLM 配置（多后端，按优先级） ===
API_BACKENDS = [
    {
        "name": "DeepSeek",
        "endpoint": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
        "key_cmd": ["pass", "show", "api/deepseek"],
    },
    {
        "name": "ZAI (Zeabur)",
        "endpoint": "https://open.zeabur.com/v1/chat/completions",
        "model": "glm-5",
        "key_cmd": ["pass", "show", "api/zai"],
    },
]

# === 评分权重 ===
WEIGHTS = {"heat": 0.35, "timeliness": 0.25, "creativity": 0.40}

# === 批量评分 prompt ===
SCORING_PROMPT = """你是一个内容选题专家。请对以下热点逐条评分（0-100），并推荐创作角度。

评分维度：
- heat（热度）：当前关注度和讨论量，越火越高
- timeliness（时效性）：话题新鲜度，过时的打低分
- creativity（创作空间）：能否写出有价值、有深度的内容，纯新闻搬运打低分

对每条热点输出 JSON（严格格式，不要多余文字）：
```json
[
  {
    "index": 0,
    "heat": 85,
    "timeliness": 90,
    "creativity": 75,
    "angle": "推荐的创作角度（一句话）"
  },
  ...
]
```

以下是待评分的热点列表：
{items_text}
"""

BATCH_SIZE = 15


def init_backend():
    """初始化可用的 API 后端，清除代理干扰"""
    # 环境里可能存在 socks 代理(不被 httpx 支持方案)，这里优先禁用 SOCKS，仅保留 HTTP 代理
    for var in ["ALL_PROXY", "all_proxy"]:
        os.environ.pop(var, None)

    import httpx
    # 诊断：显示代理环境（仅供调试，不打印 key）
    # print('HTTP_PROXY=', os.environ.get('HTTP_PROXY'), 'HTTPS_PROXY=', os.environ.get('HTTPS_PROXY'))
    for backend in API_BACKENDS:
        try:
            result = subprocess.run(backend["key_cmd"], capture_output=True, text=True, timeout=10)
            key = result.stdout.strip()
            if not key:
                continue
            r = httpx.post(
                backend["endpoint"],
                json={"model": backend["model"], "messages": [{"role": "user", "content": "say ok"}], "max_tokens": 5},
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=30,
            )
            if r.status_code == 200:
                print(f"✅ 使用 API: {backend['name']} ({backend['model']})")
                return {"endpoint": backend["endpoint"], "model": backend["model"], "key": key}
            else:
                print(f"  ⚠️ {backend['name']}: HTTP {r.status_code} {r.text[:100]}")
        except Exception as e:
            print(f"  ⚠️ {backend['name']}: {e}")
    print("❌ 无可用 API 后端", file=sys.stderr)
    sys.exit(1)


def load_hotpool(date_str: str) -> list:
    """加载热点池"""
    path = HOTPOOL_DIR / f"{date_str}.json"
    if not path.exists():
        print(f"⚠️ {path} 不存在，尝试调用 fetch_all.py 采集...")
        if FETCH_ALL.exists():
            subprocess.run([sys.executable, str(FETCH_ALL)], timeout=120)
        if not path.exists():
            files = sorted(HOTPOOL_DIR.glob("*.json"), reverse=True)
            if files:
                path = files[0]
                print(f"📂 使用最新热点池: {path.name}")
            else:
                print("❌ 无可用热点池", file=sys.stderr)
                sys.exit(1)

    data = json.loads(path.read_text())
    items = data.get("items", data if isinstance(data, list) else [])
    valid = [it for it in items if len(it.get("title", "")) > 10]
    print(f"📥 加载 {len(valid)} 条有效热点 (共 {len(items)} 条)")
    return valid


def call_llm(prompt: str, backend: dict, retries: int = 2) -> str:
    """调用 LLM API"""
    import httpx
    for attempt in range(retries + 1):
        try:
            r = httpx.post(
                backend["endpoint"],
                json={"model": backend["model"], "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.3, "max_tokens": 4096},
                headers={"Authorization": f"Bearer {backend['key']}", "Content-Type": "application/json"},
                timeout=90,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < retries:
                wait = 2 ** (attempt + 1)
                print(f"  ⏳ LLM 请求失败 ({e}), {wait}s 后重试...")
                time.sleep(wait)
            else:
                raise


def parse_scores(llm_output: str) -> list:
    """从 LLM 输出中解析评分 JSON"""
    text = llm_output
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"  ⚠️ JSON 解析失败，跳过此批", file=sys.stderr)
        return []


def score_items(items: list, backend: dict) -> list:
    """批量评分所有热点"""
    scored = []
    total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(items))
        batch = items[start:end]

        print(f"🔄 评分第 {batch_idx + 1}/{total_batches} 批 ({len(batch)} 条)...")

        items_text = ""
        for i, item in enumerate(batch):
            source = item.get("source", "unknown")
            title = str(item.get("title", "")).strip()
            summary = str(item.get("summary", "")).strip()[:200]
            author = str(item.get("author", ""))
            items_text += f"\n[{i}] 来源:{source} | 作者:{author}\n标题: {title}\n摘要: {summary}\n"

        prompt = SCORING_PROMPT.replace("{items_text}", items_text)

        try:
            output = call_llm(prompt, backend)
            scores = parse_scores(output)
            for score in scores:
                idx = score.get("index", -1)
                if 0 <= idx < len(batch):
                    item = batch[idx].copy()
                    item["scores"] = {
                        "heat": score.get("heat", 50),
                        "timeliness": score.get("timeliness", 50),
                        "creativity": score.get("creativity", 50),
                    }
                    item["angle"] = score.get("angle", "")
                    item["total_score"] = round(
                        item["scores"]["heat"] * WEIGHTS["heat"]
                        + item["scores"]["timeliness"] * WEIGHTS["timeliness"]
                        + item["scores"]["creativity"] * WEIGHTS["creativity"]
                    )
                    # 兼容 downstream: 每个 item 必须有 score 字段
                    item["score"] = item["total_score"]
                    scored.append(item)
        except Exception as e:
            print(f"  ❌ 第 {batch_idx + 1} 批评分失败: {e}", file=sys.stderr)
            for item in batch:
                c = item.copy()
                c["scores"] = {"heat": 50, "timeliness": 50, "creativity": 50}
                c["angle"] = "需人工评估"
                c["total_score"] = 50
                c["score"] = 50
                scored.append(c)

        if batch_idx < total_batches - 1:
            time.sleep(1)

    return scored


def format_telegram_message(top_items: list, date_str: str) -> str:
    """生成 Telegram 选题卡片消息"""
    nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = [f"🔥 今日热点选题 Top {len(top_items)} ({date_str})", "━━━━━━━━━━━━━━", ""]

    for i, item in enumerate(top_items):
        num = nums[i] if i < 10 else f"[{i+1}]"
        title = item.get("title", "").strip()
        if len(title) > 60:
            title = title[:57] + "..."
        total = item.get("total_score", 0)
        s = item.get("scores", {})
        source = item.get("source", "?")
        category = item.get("category", "")
        angle = item.get("angle", "")
        source_tag = f"{source}/{category}" if category else source

        lines.append(f"{num} {title} ⭐{total}")
        lines.append(f"📊 热度:{s.get('heat',0)} 时效:{s.get('timeliness',0)} 创作:{s.get('creativity',0)}")
        lines.append(f"📌 来源: {source_tag} | 💡 角度: {angle}")
        lines.append("")

    lines.extend(["━━━━━━━━━━━━━━", "📝 回复编号选择主题（如 \"1 3 7\"）", "💡 也可自定义主题"])
    return "\n".join(lines)


def save_topics(scored_items: list, top_items: list, date_str: str):
    """保存评分结果"""
    TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "date": date_str,
        "scored_at": datetime.now().isoformat(),
        "total_scored": len(scored_items),
        "top_count": len(top_items),
        "weights": WEIGHTS,
        "top": top_items,
        "all_scored": scored_items,
    }
    path = TOPICS_DIR / f"{date_str}.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"💾 保存到 {path}")


def send_via_newsbot(message: str):
    """通过 newsbot_send.py 推送"""
    if not NEWSBOT_SEND.exists():
        print(f"⚠️ {NEWSBOT_SEND} 不存在，跳过推送")
        return False
    try:
        proc = subprocess.run(
            [sys.executable, str(NEWSBOT_SEND), "--message", message],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode == 0:
            print("📤 推送成功")
            return True
        print(f"⚠️ 推送失败: {proc.stderr}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"⚠️ 推送异常: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="热点选题评分")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="热点池日期")
    parser.add_argument("--top", type=int, default=10, help="Top N")
    parser.add_argument("--limit", type=int, default=0, help="只评分前N条热点(0表示全部)")
    parser.add_argument("--no-send", action="store_true", help="不推送")
    parser.add_argument("--dry-run", action="store_true", help="不调LLM，用随机分")
    args = parser.parse_args()

    print(f"📅 选题评分: {args.date}")
    items = load_hotpool(args.date)
    if args.limit and args.limit > 0:
        items = items[:args.limit]
        print(f"✂️ 只评分前 {len(items)} 条热点 (--limit)")
    if not items:
        print("❌ 热点池为空")
        sys.exit(1)

    if args.dry_run:
        import random
        print("🧪 Dry run 模式")
        scored = []
        for item in items:
            c = item.copy()
            h, t, cr = random.randint(40, 100), random.randint(40, 100), random.randint(40, 100)
            c["scores"] = {"heat": h, "timeliness": t, "creativity": cr}
            c["total_score"] = round(h * WEIGHTS["heat"] + t * WEIGHTS["timeliness"] + cr * WEIGHTS["creativity"])
            c["score"] = c["total_score"]
            c["angle"] = "dry-run"
            scored.append(c)
    else:
        backend = init_backend()
        scored = score_items(items, backend)

    scored.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    top = scored[:args.top]

    print(f"\n🏆 Top {len(top)} 选题:")
    for i, item in enumerate(top):
        print(f"  {i+1}. [{item.get('total_score',0)}分] {item.get('title','')[:50]}")

    save_topics(scored, top, args.date)
    message = format_telegram_message(top, args.date)
    print(f"\n{message}")

    if not args.no_send:
        send_via_newsbot(message)

    return message


if __name__ == "__main__":
    main()

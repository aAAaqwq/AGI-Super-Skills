#!/usr/bin/env python3
"""content_generator.py — 多平台内容生成引擎

读取评分选题 + 平台模板 → 调用 LLM (glm-5) → 输出多平台草稿。

用法:
  python content_generator.py --topic-id 1 --platform xiaohongshu
  python content_generator.py --top 3 --all-platforms
  python content_generator.py --topic-id 1 --all-platforms --dry-run
"""

import argparse
import json
import os
import sys
import httpx
from datetime import datetime
from pathlib import Path

# 清除代理，避免 httpx 不支持 socks 协议报错
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
    os.environ.pop(_k, None)

from paths import TOPICS_DIR, DRAFTS_DIR, TEMPLATES_DIR

PLATFORMS = ["xiaohongshu", "twitter", "wechat"]

LLM_BASE = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-5")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "120"))


def get_api_key() -> str:
    key = os.environ.get("LLM_API_KEY") or os.environ.get("ZAI_API_KEY")
    if key:
        return key
    import subprocess
    r = subprocess.run(["pass", "show", "api/zai-glm5-new"], capture_output=True, text=True, timeout=10)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    raise RuntimeError("无法获取 API Key，请设置 LLM_API_KEY 或配置 pass")


def load_topics(date_str: str) -> dict:
    path = TOPICS_DIR / f"{date_str}.json"
    if not path.exists():
        files = sorted(TOPICS_DIR.glob("*.json"), reverse=True)
        if not files:
            raise FileNotFoundError(f"topics 目录为空: {TOPICS_DIR}")
        path = files[0]
        print(f"⚠️  回退到: {path.name}", file=sys.stderr)
    return json.loads(path.read_text())


def load_system_prompts() -> dict:
    path = TEMPLATES_DIR / "system_prompts.json"
    return json.loads(path.read_text())


def load_template(platform: str) -> str:
    path = TEMPLATES_DIR / f"{platform}.md"
    if not path.exists():
        return ""
    return path.read_text()


def fill_template(template: str, topic: dict) -> str:
    title = topic.get("title", "")
    summary = topic.get("summary", "")
    if not isinstance(summary, str):
        summary = str(summary)
    source = f"{topic.get('source', '')}/{topic.get('category', '')}"
    angle = topic.get("angle", "")
    return (template
            .replace("{title}", title)
            .replace("{summary}", summary)
            .replace("{source}", source)
            .replace("{angles}", angle)
            .replace("{angle}", angle))


def call_llm(system_prompt: str, user_prompt: str, dry_run: bool = False) -> str:
    if dry_run:
        return f"[DRY-RUN] 不调用LLM\n\n=== SYSTEM ===\n{system_prompt[:200]}...\n\n=== USER ===\n{user_prompt[:500]}..."

    api_key = get_api_key()
    url = f"{LLM_BASE}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 4096,
    }

    with httpx.Client(timeout=LLM_TIMEOUT) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def generate_one(topic, topic_idx, platform, date_str, sys_prompts, dry_run):
    sp_entry = sys_prompts.get(platform, {})
    system_prompt = sp_entry.get("system_prompt", f"你是{platform}内容创作者。")
    output_format = sp_entry.get("output_format", "")

    template = load_template(platform)
    user_prompt = fill_template(template, topic)
    if output_format:
        user_prompt += f"\n\n请严格按照以下格式输出:\n{output_format}"

    content = call_llm(system_prompt, user_prompt, dry_run=dry_run)

    out_dir = DRAFTS_DIR / date_str / str(topic_idx)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{platform}.md"
    out_file.write_text(content)
    return out_file


def main():
    p = argparse.ArgumentParser(description="多平台内容生成引擎")
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    p.add_argument("--topic-id", type=int, help="指定选题编号 (1-based)")
    p.add_argument("--top", type=int, default=3, help="批量生成 Top N")
    p.add_argument("--platform", choices=PLATFORMS, help="指定单一平台")
    p.add_argument("--all-platforms", action="store_true", help="生成所有平台版本")
    p.add_argument("--dry-run", action="store_true", help="只打印 prompt 不调用 LLM")
    args = p.parse_args()

    if not args.platform and not args.all_platforms:
        args.all_platforms = True

    platforms = PLATFORMS if args.all_platforms else [args.platform]
    data = load_topics(args.date)
    sys_prompts = load_system_prompts()
    top_items = data.get("top", [])

    if args.topic_id:
        idx = args.topic_id - 1
        if idx < 0 or idx >= len(top_items):
            print(f"❌ topic-id {args.topic_id} 超出范围 (1-{len(top_items)})", file=sys.stderr)
            return 1
        targets = [(args.topic_id, top_items[idx])]
    else:
        targets = [(i + 1, t) for i, t in enumerate(top_items[:args.top])]

    date_str = data.get("date", args.date)
    total = len(targets) * len(platforms)
    done = 0

    for tid, topic in targets:
        title = (topic.get("title") or "")[:40]
        for plat in platforms:
            done += 1
            tag = "🏃" if not args.dry_run else "📝"
            print(f"{tag} [{done}/{total}] #{tid} {title} → {plat}")
            try:
                out = generate_one(topic, tid, plat, date_str, sys_prompts, args.dry_run)
                print(f"   ✅ {out}")
            except Exception as e:
                print(f"   ❌ {e}", file=sys.stderr)

    print(f"\n{'📝 DRY-RUN' if args.dry_run else '✅'} 完成: {done} 篇内容 → {DRAFTS_DIR / date_str}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

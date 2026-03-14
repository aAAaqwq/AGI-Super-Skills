#!/usr/bin/env python3
"""
OpenClaw session token/cost usage analyzer.
Reads JSONL session files and summarizes usage per model.
"""

import os
import json
import argparse
from pathlib import Path
from collections import defaultdict

DEFAULT_SESSIONS_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")

def parse_args():
    p = argparse.ArgumentParser(description="OpenClaw model usage analyzer")
    p.add_argument("--sessions-dir", default=DEFAULT_SESSIONS_DIR)
    p.add_argument("--session", help="Specific session ID or 'all' (default: all)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    return p.parse_args()

def load_session(path):
    entries = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries

def analyze(entries):
    models = defaultdict(lambda: {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "cost": 0.0, "turns": 0})
    current_model = "unknown"

    for e in entries:
        t = e.get("type", "")
        if t == "model_change":
            current_model = f"{e.get('provider','')}/{e.get('modelId','')}"
        elif t == "message":
            msg = e.get("message", {})
            if msg.get("role") == "assistant":
                model = msg.get("model") or current_model
                if msg.get("provider"):
                    model = f"{msg['provider']}/{model}"
                usage = msg.get("usage", {})
                cost = usage.get("cost", {})
                models[model]["input"] += usage.get("input", 0)
                models[model]["output"] += usage.get("output", 0)
                models[model]["cacheRead"] += usage.get("cacheRead", 0)
                models[model]["cacheWrite"] += usage.get("cacheWrite", 0)
                models[model]["cost"] += (cost.get("input", 0) + cost.get("output", 0) +
                                          cost.get("cacheRead", 0) + cost.get("cacheWrite", 0))
                models[model]["turns"] += 1
    return models

def merge(a, b):
    for model, stats in b.items():
        for k, v in stats.items():
            a[model][k] += v
    return a

def print_text(models, title="Usage Summary"):
    total_cost = sum(s["cost"] for s in models.values())
    total_in = sum(s["input"] for s in models.values())
    total_out = sum(s["output"] for s in models.values())
    total_turns = sum(s["turns"] for s in models.values())

    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(f"  Total turns : {total_turns}")
    print(f"  Total input : {total_in:,} tokens")
    print(f"  Total output: {total_out:,} tokens")
    print(f"  Total cost  : ${total_cost:.6f}")
    print(f"{'='*60}")

    for model, s in sorted(models.items(), key=lambda x: -x[1]["cost"]):
        print(f"\n  Model: {model}")
        print(f"    Turns      : {s['turns']}")
        print(f"    Input      : {s['input']:,} tokens")
        print(f"    Output     : {s['output']:,} tokens")
        print(f"    Cache read : {s['cacheRead']:,} tokens")
        print(f"    Cache write: {s['cacheWrite']:,} tokens")
        print(f"    Cost       : ${s['cost']:.6f}")
    print()

def main():
    args = parse_args()
    sessions_dir = Path(args.sessions_dir)

    if not sessions_dir.exists():
        print(f"Sessions dir not found: {sessions_dir}")
        return

    jsonl_files = list(sessions_dir.glob("*.jsonl"))
    if not jsonl_files:
        print("No session files found.")
        return

    all_models = defaultdict(lambda: {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "cost": 0.0, "turns": 0})

    for f in jsonl_files:
        entries = load_session(f)
        session_models = analyze(entries)
        merge(all_models, session_models)

    if args.format == "json":
        print(json.dumps({m: s for m, s in all_models.items()}, indent=2))
    else:
        print_text(all_models, title=f"OpenClaw Usage — {len(jsonl_files)} session(s)")

if __name__ == "__main__":
    main()

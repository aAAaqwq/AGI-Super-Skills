#!/usr/bin/env python3
"""OpenRouter usage tracker for OpenClaw agents.

Queries OpenRouter API for credit balance and parses OpenClaw session logs
to provide per-model cost breakdowns with date filtering and projections.
"""

import argparse
import json
import math
import os
import sys
import glob
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from pathlib import Path


OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_api_key():
    """Resolve OpenRouter API key from environment or OpenClaw auth store."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key

    openclaw_dir = Path.home() / ".openclaw"
    auth_files = sorted(openclaw_dir.glob("agents/*/agent/auth.json"))
    for auth_file in auth_files:
        try:
            with open(auth_file) as f:
                auth = json.load(f)
            if "openrouter" in auth and "key" in auth["openrouter"]:
                return auth["openrouter"]["key"]
        except (json.JSONDecodeError, KeyError, OSError):
            continue

    return None


def api_get(endpoint, api_key):
    """Make authenticated GET request to OpenRouter API."""
    url = f"{OPENROUTER_API_BASE}/{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}: {body[:200]}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def local_today():
    """Return today's date string in local timezone."""
    return datetime.now().strftime("%Y-%m-%d")


def date_range(start, end):
    """Generate all YYYY-MM-DD strings from start to end (inclusive)."""
    dates = set()
    current = start
    while current <= end:
        dates.add(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


def resolve_date_filter(args):
    """Convert date arguments into a set of allowed YYYY-MM-DD strings, or None for all."""
    now = datetime.now()

    if getattr(args, "utc", False):
        now = datetime.now(timezone.utc)

    today = now.date()

    if getattr(args, "today", False):
        return {today.strftime("%Y-%m-%d")}
    if getattr(args, "week", False):
        start = today - timedelta(days=6)
        return date_range(start, today)
    if getattr(args, "month", False):
        start = today - timedelta(days=29)
        return date_range(start, today)

    date_from = getattr(args, "from_date", None)
    date_to = getattr(args, "to_date", None)
    single = getattr(args, "date", None)

    if single:
        return {single}
    if date_from or date_to:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else today - timedelta(days=365)
            end = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today
            return date_range(start, end)
        except ValueError as e:
            print(f"Error: Invalid date format: {e}", file=sys.stderr)
            sys.exit(1)

    return None  # no filter = all time


# ── Session log parsing ──────────────────────────────────────────────────────

def find_session_logs(openclaw_dir=None, agent=None):
    """Find OpenClaw session JSONL files, optionally filtered by agent name."""
    if openclaw_dir is None:
        openclaw_dir = Path.home() / ".openclaw"
    else:
        openclaw_dir = Path(openclaw_dir)

    if agent:
        pattern = str(openclaw_dir / "agents" / agent / "sessions" / "*.jsonl")
    else:
        pattern = str(openclaw_dir / "agents" / "*" / "sessions" / "*.jsonl")

    return sorted(glob.glob(pattern))


def parse_session_costs(session_files, date_filter=None):
    """Parse OpenClaw session JSONL files for cost data per model.

    Args:
        session_files: List of JSONL file paths.
        date_filter: Set of allowed YYYY-MM-DD strings, or None for all.

    Returns:
        Dict mapping model name to stats dict.
    """
    model_stats = defaultdict(lambda: {
        "cost": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "requests": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "dates_seen": set(),
    })

    for fpath in session_files:
        try:
            with open(fpath) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ts = entry.get("timestamp") or entry.get("ts")
                    entry_date = None
                    if ts:
                        try:
                            entry_date = ts[:10]
                        except (TypeError, IndexError):
                            pass

                    if date_filter and (entry_date is None or entry_date not in date_filter):
                        continue

                    msg = entry.get("message", {})
                    usage = msg.get("usage", {})
                    cost_data = usage.get("cost", {})
                    model = msg.get("model") or entry.get("model") or "unknown"

                    total_cost = cost_data.get("total", 0) or 0
                    if total_cost > 0:
                        stats = model_stats[model]
                        stats["cost"] += total_cost
                        stats["input_tokens"] += usage.get("input", usage.get("inputTokens", usage.get("prompt_tokens", 0))) or 0
                        stats["output_tokens"] += usage.get("output", usage.get("outputTokens", usage.get("completion_tokens", 0))) or 0
                        stats["cache_read_tokens"] += usage.get("cacheRead", cost_data.get("cacheRead", 0)) or 0
                        stats["cache_write_tokens"] += usage.get("cacheWrite", cost_data.get("cacheWrite", 0)) or 0
                        stats["requests"] += 1
                        if entry_date:
                            stats["dates_seen"].add(entry_date)
        except OSError:
            continue

    # Convert sets to counts for JSON serialization
    result = {}
    for model, stats in model_stats.items():
        result[model] = {k: v for k, v in stats.items() if k != "dates_seen"}
        result[model]["days_active"] = len(stats["dates_seen"])

    return result


# ── Credit balance ───────────────────────────────────────────────────────────

def fetch_credits(api_key):
    """Fetch credit data from OpenRouter API. Returns dict with total/used/remaining."""
    data = api_get("credits", api_key)
    if "error" in data:
        data = api_get("auth/key", api_key)
    if "error" in data:
        return data

    if "data" in data:
        d = data["data"]
        total = d.get("total_credits", d.get("limit", 0))
        used = d.get("total_usage", d.get("usage", 0))
    else:
        total = data.get("limit", data.get("total_credits", 0))
        used = data.get("usage", data.get("total_usage", 0))

    remaining = total - used if total else None
    return {"total": total, "used": used, "remaining": remaining, "raw": data}


def format_credits(credits_data):
    """Format credit data for text output."""
    if "error" in credits_data:
        return f"Error fetching credits: {credits_data['error']}"

    total = credits_data["total"]
    used = credits_data["used"]
    remaining = credits_data["remaining"]

    lines = ["═══ OpenRouter Credits ═══"]
    lines.append(f"  Total:      ${total:.4f}" if isinstance(total, (int, float)) else f"  Total: {total}")
    lines.append(f"  Used:       ${used:.4f}" if isinstance(used, (int, float)) else f"  Used: {used}")
    if remaining is not None and isinstance(remaining, (int, float)):
        lines.append(f"  Remaining:  ${remaining:.4f}")
        if total and isinstance(total, (int, float)) and total > 0:
            pct = used / total * 100
            lines.append(f"  Usage:      {pct:.1f}%")
    else:
        lines.append("  Remaining:  unlimited")
    return "\n".join(lines)


# ── Session report formatting ────────────────────────────────────────────────

def format_sessions(stats, label=""):
    """Format per-model stats for text output."""
    if not stats:
        return f"No cost data found{' for ' + label if label else ''}."

    sorted_models = sorted(stats.items(), key=lambda x: x[1]["cost"], reverse=True)
    total_cost = sum(s["cost"] for _, s in sorted_models)
    total_reqs = sum(s["requests"] for _, s in sorted_models)
    total_in = sum(s["input_tokens"] for _, s in sorted_models)
    total_out = sum(s["output_tokens"] for _, s in sorted_models)

    lines = [f"═══ Usage by Model{' (' + label + ')' if label else ''} ═══", ""]

    for model, s in sorted_models:
        pct = (s["cost"] / total_cost * 100) if total_cost > 0 else 0
        lines.append(f"  {model}")
        lines.append(f"    Cost: ${s['cost']:.4f} ({pct:.1f}%)  |  Requests: {s['requests']}")
        lines.append(f"    Tokens: {s['input_tokens']:,} in / {s['output_tokens']:,} out")
        if s["cache_read_tokens"] > 0 or s["cache_write_tokens"] > 0:
            lines.append(f"    Cache: {s['cache_read_tokens']:,} read / {s['cache_write_tokens']:,} write")
        lines.append("")

    lines.append("  ──────────────────────────────")
    lines.append(f"  TOTAL: ${total_cost:.4f}  |  {total_reqs} requests  |  {total_in + total_out:,} tokens")
    return "\n".join(lines)


def format_projection(credits_data, stats):
    """Estimate how many days credits will last based on daily average spending."""
    if "error" in credits_data or not stats:
        return None

    remaining = credits_data.get("remaining")
    if remaining is None or not isinstance(remaining, (int, float)) or remaining <= 0:
        return None

    # Calculate active days from stats
    all_days = set()
    for model_stats in stats.values():
        # days_active is already computed
        pass

    total_cost = sum(s["cost"] for s in stats.values())
    if total_cost <= 0:
        return None

    # Use max days_active across models as the span
    max_days = max((s.get("days_active", 1) for s in stats.values()), default=1)
    if max_days < 1:
        max_days = 1

    daily_avg = total_cost / max_days
    if daily_avg <= 0:
        return None

    days_left = remaining / daily_avg

    if days_left > 365:
        return f"📊 Projection: ~${daily_avg:.4f}/day avg → credits last 1+ year"
    else:
        return f"📊 Projection: ~${daily_avg:.4f}/day avg → credits last ~{math.ceil(days_left)} days"


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_credits(api_key, fmt="text"):
    """Show OpenRouter credit balance."""
    credits_data = fetch_credits(api_key)
    if "error" in credits_data:
        print(f"Error: {credits_data['error']}", file=sys.stderr)
        sys.exit(1)

    if fmt == "json":
        out = {k: v for k, v in credits_data.items() if k != "raw"}
        print(json.dumps(out, indent=2))
    else:
        print(format_credits(credits_data))


def cmd_sessions(args, fmt="text"):
    """Show per-model cost breakdown from session logs."""
    date_filter = resolve_date_filter(args)
    files = find_session_logs(
        openclaw_dir=getattr(args, "openclaw_dir", None),
        agent=getattr(args, "agent", None),
    )
    if not files:
        agent_hint = f" for agent '{args.agent}'" if getattr(args, "agent", None) else ""
        print(f"No session logs found{agent_hint}.", file=sys.stderr)
        sys.exit(1)

    stats = parse_session_costs(files, date_filter)
    label = _date_label(args)

    if fmt == "json":
        print(json.dumps(stats, indent=2))
    else:
        print(format_sessions(stats, label))


def cmd_report(args, api_key, fmt="text"):
    """Combined report: credits + session breakdown + projection."""
    date_filter = resolve_date_filter(args)
    files = find_session_logs(
        openclaw_dir=getattr(args, "openclaw_dir", None),
        agent=getattr(args, "agent", None),
    )

    credits_data = fetch_credits(api_key) if api_key else {"error": "No API key"}
    stats = parse_session_costs(files, date_filter) if files else {}
    label = _date_label(args)

    if fmt == "json":
        output = {
            "credits": {k: v for k, v in credits_data.items() if k != "raw"} if "error" not in credits_data else credits_data,
            "sessions": stats,
            "period": label or "all time",
        }
        proj = format_projection(credits_data, stats)
        if proj:
            output["projection"] = proj
        print(json.dumps(output, indent=2))
        return

    # Text output
    if "error" not in credits_data:
        print(format_credits(credits_data))
    else:
        print(f"⚠ Credits unavailable: {credits_data['error']}")

    print()

    if stats:
        print(format_sessions(stats, label))
    elif files:
        print(f"No cost data found{' for ' + label if label else ''}.")
    else:
        agent_hint = f" for agent '{args.agent}'" if getattr(args, "agent", None) else ""
        print(f"No session logs found{agent_hint}.")

    # Projection
    if "error" not in credits_data and stats:
        proj = format_projection(credits_data, stats)
        if proj:
            print(f"\n{proj}")


def _date_label(args):
    """Build a human-readable label for the date filter used."""
    if getattr(args, "today", False):
        return "today"
    if getattr(args, "week", False):
        return "last 7 days"
    if getattr(args, "month", False):
        return "last 30 days"
    if getattr(args, "date", None):
        return args.date
    date_from = getattr(args, "from_date", None)
    date_to = getattr(args, "to_date", None)
    if date_from and date_to:
        return f"{date_from} to {date_to}"
    if date_from:
        return f"from {date_from}"
    if date_to:
        return f"until {date_to}"
    return ""


# ── CLI ──────────────────────────────────────────────────────────────────────

def add_date_args(parser):
    """Add common date filter arguments to a subparser."""
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--today", action="store_true", help="Today only (local timezone)")
    g.add_argument("--week", action="store_true", help="Last 7 days")
    g.add_argument("--month", action="store_true", help="Last 30 days")
    g.add_argument("--date", type=str, metavar="YYYY-MM-DD", help="Specific date")
    parser.add_argument("--from", dest="from_date", type=str, metavar="YYYY-MM-DD",
                        help="Start of date range (combine with --to)")
    parser.add_argument("--to", dest="to_date", type=str, metavar="YYYY-MM-DD",
                        help="End of date range (combine with --from)")
    parser.add_argument("--utc", action="store_true", help="Use UTC instead of local timezone")


def add_common_args(parser):
    """Add common arguments shared by sessions/report subcommands."""
    parser.add_argument("--agent", type=str, metavar="NAME",
                        help="Filter to a specific OpenClaw agent (default: all)")
    parser.add_argument("--openclaw-dir", type=str, default=None,
                        help="OpenClaw config directory (default: ~/.openclaw)")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format (default: text)")


def main():
    parser = argparse.ArgumentParser(
        description="OpenRouter usage tracker for OpenClaw",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  %(prog)s report               Full report (credits + today's usage)\n"
               "  %(prog)s report --week         Credits + last 7 days usage\n"
               "  %(prog)s credits               Credit balance only\n"
               "  %(prog)s sessions --today      Today's per-model breakdown\n"
               "  %(prog)s sessions --month      Last 30 days breakdown\n"
               "  %(prog)s sessions --from 2026-02-01 --to 2026-02-15\n"
               "  %(prog)s report --agent main   Report for 'main' agent only\n"
               "  %(prog)s report --format json  JSON output\n"
    )
    sub = parser.add_subparsers(dest="command")

    # report (primary command)
    rp = sub.add_parser("report", help="Full spending report (credits + usage breakdown + projection)")
    add_date_args(rp)
    add_common_args(rp)

    # credits
    cr = sub.add_parser("credits", help="Show OpenRouter credit balance")
    cr.add_argument("--format", choices=["text", "json"], default="text")

    # sessions
    se = sub.add_parser("sessions", help="Per-model cost breakdown from session logs")
    add_date_args(se)
    add_common_args(se)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Resolve API key for commands that need it
    api_key = None
    if args.command in ("credits", "report"):
        api_key = get_api_key()
        if not api_key and args.command == "credits":
            print("Error: No OpenRouter API key found.\n"
                  "Set OPENROUTER_API_KEY env var or configure OpenClaw auth.",
                  file=sys.stderr)
            sys.exit(1)

    if args.command == "credits":
        cmd_credits(api_key, args.format)
    elif args.command == "sessions":
        cmd_sessions(args, args.format)
    elif args.command == "report":
        # Default to --today if no date filter specified
        if not any([
            getattr(args, "today", False),
            getattr(args, "week", False),
            getattr(args, "month", False),
            getattr(args, "date", None),
            getattr(args, "from_date", None),
            getattr(args, "to_date", None),
        ]):
            args.today = True
        cmd_report(args, api_key, args.format)


if __name__ == "__main__":
    main()

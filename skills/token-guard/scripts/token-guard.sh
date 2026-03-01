#!/usr/bin/env bash
# token-guard.sh — Monitor and control OpenClaw token usage & costs
# Stop burning money while you sleep.
#
# Usage:
#   token-guard.sh status                 # Current usage summary
#   token-guard.sh monitor                # Check usage vs budget (for cron)
#   token-guard.sh set-budget <USD>       # Set daily budget
#   token-guard.sh set-model-rules        # Configure auto model switching
#   token-guard.sh history [days]         # Usage history
#   token-guard.sh alert                  # Check if budget exceeded

set -euo pipefail

# --- Config ---
CONFIG_FILE="${CONFIG_FILE:-$HOME/.clawdbot/clawdbot.json}"
[[ ! -f "$CONFIG_FILE" ]] && CONFIG_FILE="$HOME/.openclaw/openclaw.json"
STATE_DIR="${STATE_DIR:-$HOME/.openclaw/token-guard}"
BUDGET_FILE="$STATE_DIR/budget.json"
USAGE_LOG="$STATE_DIR/usage-log.jsonl"
GATEWAY_PORT="${GATEWAY_PORT:-18789}"
GATEWAY_URL="http://127.0.0.1:${GATEWAY_PORT}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${BLUE}ℹ${NC} $*"; }
ok()    { echo -e "${GREEN}✔${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
fail()  { echo -e "${RED}✖${NC} $*"; }
cost()  { echo -e "${CYAN}💰${NC} $*"; }

mkdir -p "$STATE_DIR"

# ============================================================
# Model pricing database (USD per 1M tokens)
# ============================================================
get_model_cost() {
  local model="$1"
  # Returns "input_cost output_cost" per 1M tokens
  case "$model" in
    *opus*4*|*claude-opus-4*)       echo "15.00 75.00" ;;
    *opus*)                         echo "15.00 75.00" ;;
    *sonnet*4*|*claude-sonnet-4*)   echo "3.00 15.00" ;;
    *sonnet*3.5*|*sonnet-3-5*)      echo "3.00 15.00" ;;
    *haiku*3.5*|*haiku-3-5*)        echo "0.80 4.00" ;;
    *haiku*)                        echo "0.25 1.25" ;;
    *gpt-4o*)                       echo "2.50 10.00" ;;
    *gpt-4-turbo*)                  echo "10.00 30.00" ;;
    *gpt-4*)                        echo "30.00 60.00" ;;
    *gpt-3.5*|*gpt-35*)            echo "0.50 1.50" ;;
    *o1-mini*)                      echo "3.00 12.00" ;;
    *o1*)                           echo "15.00 60.00" ;;
    *gemini*pro*)                   echo "1.25 5.00" ;;
    *gemini*flash*)                 echo "0.075 0.30" ;;
    *deepseek*)                     echo "0.27 1.10" ;;
    *kimi*|*moonshot*)              echo "0.00 0.00" ;;  # Free tier
    *)                              echo "3.00 15.00" ;;  # Default to Sonnet-level
  esac
}

# ============================================================
# STATUS — current usage snapshot
# ============================================================
cmd_status() {
  echo "━━━ Token Guard Status ━━━"
  echo ""

  # Current model
  local model
  model=$(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
m = cfg.get('agents', {}).get('primaryModel', cfg.get('primaryModel', 'unknown'))
print(m)
" 2>/dev/null || echo "unknown")
  info "Current model: $model"

  local costs
  costs=$(get_model_cost "$model")
  local input_cost output_cost
  input_cost=$(echo "$costs" | cut -d' ' -f1)
  output_cost=$(echo "$costs" | cut -d' ' -f2)
  info "Pricing: \$${input_cost}/1M input, \$${output_cost}/1M output"

  # Budget
  if [[ -f "$BUDGET_FILE" ]]; then
    local daily_budget
    daily_budget=$(python3 -c "import json; print(json.load(open('$BUDGET_FILE')).get('daily_usd', 'not set'))" 2>/dev/null)
    cost "Daily budget: \$${daily_budget}"
  else
    warn "No budget set (use 'token-guard.sh set-budget <USD>')"
  fi

  # Today's usage from log
  local today
  today=$(date -u +%Y-%m-%d)
  if [[ -f "$USAGE_LOG" ]]; then
    local today_stats
    today_stats=$(python3 -c "
import json
total_input = 0
total_output = 0
total_cost = 0.0
count = 0
with open('$USAGE_LOG') as f:
    for line in f:
        try:
            d = json.loads(line.strip())
            if d.get('date', '').startswith('$today'):
                total_input += d.get('input_tokens', 0)
                total_output += d.get('output_tokens', 0)
                total_cost += d.get('estimated_cost', 0.0)
                count += 1
        except:
            pass
print(f'{total_input} {total_output} {total_cost:.4f} {count}')
" 2>/dev/null || echo "0 0 0.0000 0")

    local t_in t_out t_cost t_count
    t_in=$(echo "$today_stats" | cut -d' ' -f1)
    t_out=$(echo "$today_stats" | cut -d' ' -f2)
    t_cost=$(echo "$today_stats" | cut -d' ' -f3)
    t_count=$(echo "$today_stats" | cut -d' ' -f4)

    echo ""
    info "Today ($today):"
    info "  Requests: $t_count"
    info "  Input tokens: $t_in"
    info "  Output tokens: $t_out"
    cost "  Estimated cost: \$$t_cost"

    # Budget check
    if [[ -f "$BUDGET_FILE" ]]; then
      local daily_budget
      daily_budget=$(python3 -c "import json; print(json.load(open('$BUDGET_FILE')).get('daily_usd', 999))" 2>/dev/null)
      local pct
      pct=$(python3 -c "print(f'{($t_cost / $daily_budget * 100):.1f}')" 2>/dev/null || echo "0")
      if python3 -c "exit(0 if $t_cost > $daily_budget else 1)" 2>/dev/null; then
        fail "  ❌ OVER BUDGET! ($pct% of \$$daily_budget)"
      elif python3 -c "exit(0 if $t_cost > $daily_budget * 0.8 else 1)" 2>/dev/null; then
        warn "  ⚠️  $pct% of daily budget used"
      else
        ok "  ✅ $pct% of daily budget"
      fi
    fi
  else
    info "No usage data yet"
  fi

  # Model routing config
  echo ""
  info "Model routing:"
  python3 -c "
import json
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
primary = cfg.get('agents', {}).get('primaryModel', 'not set')
# Check for subagent model
sub_model = cfg.get('agents', {}).get('defaults', {}).get('subagents', {}).get('model', 'same as primary')
sub_thinking = cfg.get('agents', {}).get('defaults', {}).get('subagents', {}).get('thinking', 'not set')
print(f'  Primary: {primary}')
print(f'  Subagent: {sub_model}')
print(f'  Subagent thinking: {sub_thinking}')
" 2>/dev/null || echo "  Could not read config"

  # Cost comparison
  echo ""
  info "💡 Cost comparison (per 1M output tokens):"
  echo "  Opus 4:    \$75.00  ██████████████████████████████"
  echo "  Sonnet 4:  \$15.00  ██████"
  echo "  Haiku 3.5:  \$4.00  ██"
  echo "  Gemini Flash:\$0.30  ▏"
  echo "  DeepSeek:   \$1.10  ▍"
}

# ============================================================
# LOG — record usage data point
# ============================================================
cmd_log() {
  local input_tokens="${1:-0}"
  local output_tokens="${2:-0}"
  local model="${3:-unknown}"
  local source="${4:-manual}"

  local costs
  costs=$(get_model_cost "$model")
  local input_cost output_cost
  input_cost=$(echo "$costs" | cut -d' ' -f1)
  output_cost=$(echo "$costs" | cut -d' ' -f2)

  local est_cost
  est_cost=$(python3 -c "
input_c = $input_tokens / 1000000 * $input_cost
output_c = $output_tokens / 1000000 * $output_cost
print(f'{input_c + output_c:.6f}')
" 2>/dev/null)

  local entry
  entry=$(python3 -c "
import json
from datetime import datetime
print(json.dumps({
    'date': datetime.utcnow().isoformat() + 'Z',
    'model': '$model',
    'input_tokens': $input_tokens,
    'output_tokens': $output_tokens,
    'estimated_cost': $est_cost,
    'source': '$source'
}))
" 2>/dev/null)

  echo "$entry" >> "$USAGE_LOG"
  ok "Logged: ${input_tokens}in/${output_tokens}out on $model ≈ \$$est_cost"
}

# ============================================================
# MONITOR — check usage vs budget (for cron/heartbeat)
# ============================================================
cmd_monitor() {
  if [[ ! -f "$BUDGET_FILE" ]]; then
    info "No budget set. Skipping monitor."
    return 0
  fi

  local daily_budget
  daily_budget=$(python3 -c "import json; print(json.load(open('$BUDGET_FILE')).get('daily_usd', 999))" 2>/dev/null)

  local today
  today=$(date -u +%Y-%m-%d)

  local today_cost
  today_cost=$(python3 -c "
import json
total = 0.0
with open('$USAGE_LOG') as f:
    for line in f:
        try:
            d = json.loads(line.strip())
            if d.get('date', '').startswith('$today'):
                total += d.get('estimated_cost', 0.0)
        except:
            pass
print(f'{total:.4f}')
" 2>/dev/null || echo "0")

  local pct
  pct=$(python3 -c "print(f'{(float(\"$today_cost\") / $daily_budget * 100):.0f}')" 2>/dev/null || echo "0")

  # Check thresholds
  local action
  action=$(python3 -c "
import json
budget = json.load(open('$BUDGET_FILE'))
cost = float('$today_cost')
daily = budget.get('daily_usd', 999)
warn_pct = budget.get('warn_pct', 80)
hard_limit = budget.get('hard_limit', False)
downgrade_model = budget.get('downgrade_model', '')

if cost >= daily:
    if hard_limit and downgrade_model:
        print(f'DOWNGRADE {downgrade_model}')
    else:
        print('ALERT_OVER')
elif cost >= daily * warn_pct / 100:
    print('ALERT_WARN')
else:
    print('OK')
" 2>/dev/null || echo "OK")

  case "$action" in
    OK)
      ok "Budget OK: \$$today_cost / \$$daily_budget ($pct%)"
      ;;
    ALERT_WARN)
      warn "⚠️ Budget warning: \$$today_cost / \$$daily_budget ($pct%)"
      ;;
    ALERT_OVER)
      fail "❌ OVER BUDGET: \$$today_cost / \$$daily_budget ($pct%)"
      ;;
    DOWNGRADE*)
      local new_model
      new_model=$(echo "$action" | cut -d' ' -f2)
      fail "❌ OVER BUDGET: \$$today_cost / \$$daily_budget ($pct%)"
      warn "⚡ Auto-downgrading to $new_model"
      _switch_model "$new_model"
      ;;
  esac
}

# ============================================================
# SET-BUDGET
# ============================================================
cmd_set_budget() {
  local daily_usd="${1:?Usage: set-budget <daily_usd> [warn_pct] [hard_limit] [downgrade_model]}"
  local warn_pct="${2:-80}"
  local hard_limit="${3:-false}"
  local downgrade_model="${4:-}"

  python3 -c "
import json
budget = {
    'daily_usd': float('$daily_usd'),
    'warn_pct': int('$warn_pct'),
    'hard_limit': '$hard_limit' == 'true',
    'downgrade_model': '$downgrade_model',
    'set_at': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
}
with open('$BUDGET_FILE', 'w') as f:
    json.dump(budget, f, indent=2)
" 2>/dev/null

  ok "Budget set:"
  cost "  Daily: \$$daily_usd"
  info "  Warning at: ${warn_pct}%"
  if [[ "$hard_limit" == "true" ]]; then
    warn "  Hard limit: ON → auto-downgrade to ${downgrade_model:-haiku}"
  else
    info "  Hard limit: OFF (alert only)"
  fi
}

# ============================================================
# SET-MODEL-RULES — configure model routing
# ============================================================
cmd_set_model_rules() {
  echo "━━━ Model Routing Configuration ━━━"
  echo ""
  echo "Current config:"
  python3 -c "
import json
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
primary = cfg.get('agents', {}).get('primaryModel', 'not set')
sub = cfg.get('agents', {}).get('defaults', {}).get('subagents', {}).get('model', 'same as primary')
print(f'  Primary model: {primary}')
print(f'  Subagent model: {sub}')
" 2>/dev/null

  echo ""
  echo "Recommended routing for cost savings:"
  echo ""
  echo "  Tier 1 (Reasoning):  claude-opus-4     (\$75/M out)"
  echo "  Tier 2 (Daily work): claude-sonnet-4   (\$15/M out) ← primary"
  echo "  Tier 3 (Background): claude-haiku-3-5  (\$4/M out)  ← subagents"
  echo "  Tier 4 (Bulk):       gemini-2.0-flash  (\$0.30/M)   ← heartbeat"
  echo ""
  echo "To apply:"
  echo "  Primary:  openclaw config set agents.primaryModel <model>"
  echo "  Subagent: openclaw config set agents.defaults.subagents.model <model>"
}

# ============================================================
# HISTORY — usage history
# ============================================================
cmd_history() {
  local days="${1:-7}"

  if [[ ! -f "$USAGE_LOG" ]]; then
    info "No usage history yet"
    return 0
  fi

  echo "━━━ Usage History (last $days days) ━━━"
  echo ""

  python3 -c "
import json
from datetime import datetime, timedelta
from collections import defaultdict

daily = defaultdict(lambda: {'input': 0, 'output': 0, 'cost': 0.0, 'count': 0, 'models': defaultdict(int)})
cutoff = (datetime.utcnow() - timedelta(days=$days)).strftime('%Y-%m-%d')

with open('$USAGE_LOG') as f:
    for line in f:
        try:
            d = json.loads(line.strip())
            date = d.get('date', '')[:10]
            if date >= cutoff:
                daily[date]['input'] += d.get('input_tokens', 0)
                daily[date]['output'] += d.get('output_tokens', 0)
                daily[date]['cost'] += d.get('estimated_cost', 0.0)
                daily[date]['count'] += 1
                daily[date]['models'][d.get('model', '?')] += 1
        except:
            pass

total_cost = 0
for date in sorted(daily.keys()):
    d = daily[date]
    total_cost += d['cost']
    bar_len = min(int(d['cost'] * 10), 40)
    bar = '█' * bar_len
    models = ', '.join(f'{m}({c})' for m, c in sorted(d['models'].items(), key=lambda x: -x[1]))
    print(f\"  {date}  \${d['cost']:>7.2f}  {d['count']:>4} reqs  {bar}\")
    print(f\"             {d['input']:>8} in / {d['output']:>8} out  [{models}]\")

print(f\"\n  Total: \${total_cost:.2f}\")
" 2>/dev/null || echo "  Error reading usage log"
}

# ============================================================
# ESTIMATE — estimate cost for a task
# ============================================================
cmd_estimate() {
  local model="${1:-claude-sonnet-4}"
  local input_tokens="${2:-10000}"
  local output_tokens="${3:-5000}"
  local runs="${4:-1}"

  local costs
  costs=$(get_model_cost "$model")
  local input_cost output_cost
  input_cost=$(echo "$costs" | cut -d' ' -f1)
  output_cost=$(echo "$costs" | cut -d' ' -f2)

  python3 -c "
ic = $input_tokens / 1000000 * $input_cost * $runs
oc = $output_tokens / 1000000 * $output_cost * $runs
total = ic + oc
print(f'Model: $model')
print(f'Input:  {$input_tokens:,} tokens × $runs runs = \${ic:.4f}')
print(f'Output: {$output_tokens:,} tokens × $runs runs = \${oc:.4f}')
print(f'Total:  \${total:.4f}')
print()
# Compare with other models
for name, ip, op in [
    ('claude-opus-4', 15.0, 75.0),
    ('claude-sonnet-4', 3.0, 15.0),
    ('claude-haiku-3-5', 0.8, 4.0),
    ('gemini-flash', 0.075, 0.30),
]:
    t = ($input_tokens/1e6*ip + $output_tokens/1e6*op) * $runs
    marker = ' ← current' if name.replace('-','').lower() in '$model'.replace('-','').lower() else ''
    print(f'  {name:20s} \${t:.4f}{marker}')
" 2>/dev/null
}

# ============================================================
# Helper: switch model
# ============================================================
_switch_model() {
  local new_model="$1"
  warn "Switching primary model to: $new_model"

  # Use gateway API to patch config
  curl -sf -X POST "${GATEWAY_URL}/api/config" \
    -H "Content-Type: application/json" \
    -d "{\"agents\":{\"primaryModel\":\"$new_model\"}}" \
    >/dev/null 2>&1 && ok "Model switched to $new_model" || fail "Failed to switch model"
}

# ============================================================
# Main
# ============================================================
case "${1:-help}" in
  status)         cmd_status ;;
  log)            cmd_log "${2:-0}" "${3:-0}" "${4:-unknown}" "${5:-manual}" ;;
  monitor)        cmd_monitor ;;
  set-budget)     cmd_set_budget "${2:-}" "${3:-80}" "${4:-false}" "${5:-}" ;;
  set-model-rules) cmd_set_model_rules ;;
  history)        cmd_history "${2:-7}" ;;
  estimate)       cmd_estimate "${2:-claude-sonnet-4}" "${3:-10000}" "${4:-5000}" "${5:-1}" ;;
  help|--help|-h)
    echo "token-guard.sh — Monitor and control OpenClaw token usage & costs"
    echo ""
    echo "Commands:"
    echo "  status              Current usage summary + budget check"
    echo "  monitor             Check budget (for cron/heartbeat)"
    echo "  set-budget <USD>    Set daily budget"
    echo "                      Options: [warn_pct] [hard_limit:true/false] [downgrade_model]"
    echo "  set-model-rules     Show model routing recommendations"
    echo "  history [days]      Usage history (default: 7 days)"
    echo "  estimate <model> <in> <out> [runs]  Estimate cost"
    echo "  log <in> <out> <model> [source]     Record usage"
    echo ""
    echo "Examples:"
    echo "  token-guard.sh set-budget 10                    # \$10/day, alert only"
    echo "  token-guard.sh set-budget 10 80 true haiku-3-5  # \$10/day, auto-downgrade at limit"
    echo "  token-guard.sh estimate claude-opus-4 50000 10000 10"
    echo ""
    echo "Environment:"
    echo "  GATEWAY_PORT    Gateway port (default: 18789)"
    ;;
  *)
    fail "Unknown command: $1 (try 'help')"
    exit 1
    ;;
esac

#!/usr/bin/env bash
# rebuild-env.sh — Rebuild ~/.openclaw/.env from pass vault
# Usage: bash rebuild-env.sh [--dry-run]
set -euo pipefail

ENV_FILE="$HOME/.openclaw/.env"
DRY_RUN="${1:-}"

echo "🔑 Rebuilding .env from pass vault..."

# Define all key mappings: ENV_VAR_NAME=pass_path
declare -A KEY_MAP=(
    # Primary model providers
    ["ZAI_API_KEY"]="api/zai"
    ["XINGSUANCODE_KEY"]="api/xingsuancode"
    ["XSC_BACKUP_API_KEY"]="api/xingsuancode"
    ["XINGJIABIAPI_KEY"]="api/xingjiabiapi"
    ["AIXN_API_KEY"]="api/aixn"
    ["XAI_API_KEY"]="api/xai"
    ["MOONSHOT_API_KEY"]="api/kimi"
    ["MINIMAX_API_KEY"]="api/minimax"
    ["WOW_API_KEY"]="api/wow"
    ["XINYUAN_API_KEY"]="api/xinyuan"
    ["OPENROUTER_API_KEY"]="api/openrouter-vip"
    ["GOOGLE_AI_STUDIO_KEY"]="api/google-ai-studio"
    ["DEEPSEEK_API_KEY"]="api/deepseek"
    
    # Search & tools
    ["BRAVE_API_KEY"]="api/brave"
    ["EXA_API_KEY"]="api/exa"
    ["PERPLEXITY_API_KEY"]="api/perplexity"
    ["TAVILY_API_KEY"]="api/tavily"
    ["FIREFRAWL_API_KEY"]="api/firecrawl"
    
    # Media & services
    ["KLINGAI_API_KEY"]="api/klingai"
    ["NOTION_API_KEY"]="api/notion"
    
    # GitHub Copilot
    ["GITHUB_COPILOT_KEY"]="api/github-copilot"
    ["GITHUB_COPILOT_AGENTS_KEY"]="api/github-copilot-agents"
    
    # Feishu
    ["FEISHU_HANXING_APPID"]="api/feishu-hanxing-appid"
    ["FEISHU_HANXING_SECRET"]="api/feishu-hanxing"
    ["FEISHU_PERSONAL_APPID"]="api/feishu-personal-appid"
    ["FEISHU_PERSONAL_SECRET"]="api/feishu-personal"
    
    # Telegram bots
    ["TG_XIAOOPS_BOT"]="api/telegram-xiaoops-bot"
    ["TG_XIAOCODE_BOT"]="api/telegram-xiaocode-bot"
    ["TG_XIAOQUANT_BOT"]="api/telegram-xiaoquant-bot"
    ["TG_XIACONTENT_BOT"]="api/telegram-xiacontent-bot"
    ["TG_XIAODATA_BOT"]="api/telegram-xiaodata-bot"
    ["TG_XIAOFINANCE_BOT"]="api/telegram-xiaofinance-bot"
    ["TG_XIAOMARKET_BOT"]="api/telegram-xiaomarket-bot"
    ["TG_XIAOPM_BOT"]="api/telegram-xiaopm-bot"
    ["TG_XIAORESEARCH_BOT"]="api/telegram-xiaoresearch-bot"
    ["TG_XIAOLAW_BOT"]="api/telegram-xiaolaw-bot"
    ["TG_XIAOM_BOT"]="api/telegram-xiaom-bot"
)

# Static keys (no pass entry)
declare -A STATIC_KEYS=(
    ["OLLAMA_API_KEY"]="ollama"
)

# Build new .env content
CONTENT="# OpenClaw API Keys — auto-generated from pass vault\n"
CONTENT+="# Generated: $(date -Iseconds)\n"
CONTENT+="# DO NOT EDIT MANUALLY — run: bash ~/.openclaw/skills/key-rotation/scripts/rebuild-env.sh\n\n"

SUCCESS=0
FAILED=0
SKIPPED=0

# Sort keys for consistent output
for var in $(echo "${!KEY_MAP[@]}" | tr ' ' '\n' | sort); do
    pass_path="${KEY_MAP[$var]}"
    val=$(pass show "$pass_path" 2>/dev/null | head -1) || true
    
    if [[ -n "$val" ]]; then
        CONTENT+="${var}=${val}\n"
        ((SUCCESS++))
        echo "  ✅ $var ← pass:$pass_path"
    else
        CONTENT+="# ${var}= # FAILED: pass show $pass_path returned empty\n"
        ((FAILED++))
        echo "  ❌ $var ← pass:$pass_path (empty/missing)"
    fi
done

# Add static keys
CONTENT+="\n# --- Static keys ---\n"
for var in $(echo "${!STATIC_KEYS[@]}" | tr ' ' '\n' | sort); do
    CONTENT+="${var}=${STATIC_KEYS[$var]}\n"
    ((SUCCESS++))
done

if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo ""
    echo "=== DRY RUN — would write to $ENV_FILE ==="
    echo -e "$CONTENT" | sed 's/=.*/=***REDACTED***/'
else
    echo -e "$CONTENT" > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo ""
    echo "✅ Written to $ENV_FILE (chmod 600)"
fi

echo ""
echo "Summary: $SUCCESS succeeded, $FAILED failed, $SKIPPED skipped"

if [[ $FAILED -gt 0 ]]; then
    echo "⚠️  Some keys failed — check pass entries"
    exit 1
fi

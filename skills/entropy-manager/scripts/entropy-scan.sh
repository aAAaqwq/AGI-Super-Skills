#!/usr/bin/env bash
# 熵扫描脚本 — Entropy Scanner v2
# 用法: ./entropy-scan.sh [target_dir]
# 输出: ~/clawd/tmp/entropy-report-YYYY-MM-DD.md

set -euo pipefail

TARGET="${1:-$HOME/clawd}"
DATE=$(date +%Y-%m-%d)
REPORT="$HOME/clawd/tmp/entropy-report-${DATE}.md"
HISTORY="$HOME/clawd/tmp/entropy-history.jsonl"
mkdir -p "$(dirname "$REPORT")"

echo "🔍 熵扫描 v2 启动 — $DATE"
echo "   目标: $TARGET"
echo ""

# 统计变量
CRITICAL=0; WARNING=0; INFO=0
DOC_ISSUES=0; NAME_ISSUES=0; CODE_ISSUES=0; CONF_ISSUES=0; FILE_ISSUES=0; DEP_ISSUES=0
CRITICAL_LIST=""; WARNING_LIST=""; INFO_LIST=""

# 统一排除
EXCLUDE_DIRS="-not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.pnpm/*' -not -path '*/venv/*' -not -path '*/__pycache__/*' -not -path '*/.next/*' -not -path '*/vendor/*' -not -path '*/security/openclaw-*' -not -path '*/openclaw-src/*' -not -path '*/repos/AGI-Super-Team/*' -not -path '*/tmp/*'"

scan_files() {
    find "$TARGET" $EXCLUDE_DIRS -type f "$@" 2>/dev/null
}

# ============================================================
# 1. 文档熵 (DOC)
# ============================================================
echo "  📄 扫描文档熵..."

STALE_TODOS=$(grep -c "^\- \[ \]" "$HOME/clawd/MEMORY.md" 2>/dev/null || echo 0)
if [ "$STALE_TODOS" -gt 10 ]; then
    WARNING=$((WARNING+1)); DOC_ISSUES=$((DOC_ISSUES+1))
    WARNING_LIST+="1. [DOC] ~/clawd/MEMORY.md — ${STALE_TODOS} 个未完成 TODO\n"
fi

EMPTY_MDS=$(scan_files -name "*.md" -size 0 2>/dev/null | head -5 || true)
for f in $EMPTY_MDS; do
    INFO=$((INFO+1)); DOC_ISSUES=$((DOC_ISSUES+1))
    INFO_LIST+="1. [DOC] $f — 空 markdown 文件\n"
done

# ============================================================
# 2. 命名熵 (NAME)
# ============================================================
echo "  📛 扫描命名熵..."

BAD_SKILL_DIRS=$(find "$HOME/.openclaw/skills" "$HOME/clawd/skills" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | while IFS= read -r d; do
    bn=$(basename "$d")
    if [[ "$bn" =~ [A-Z] ]] || [[ "$bn" =~ _ ]]; then
        echo "$d"
    fi
done || true)
for d in $BAD_SKILL_DIRS; do
    INFO=$((INFO+1)); NAME_ISSUES=$((NAME_ISSUES+1))
    INFO_LIST+="1. [NAME] $d — 目录名应使用 kebab-case\n"
done

BAD_PY_NAMES=$(scan_files -name "*-*.py" 2>/dev/null | head -10 || true)
for f in $BAD_PY_NAMES; do
    INFO=$((INFO+1)); NAME_ISSUES=$((NAME_ISSUES+1))
    INFO_LIST+="1. [NAME] $f — Python 文件应使用 snake_case\n"
done

# ============================================================
# 3. 代码熵 (CODE)
# ============================================================
echo "  💻 扫描代码熵..."

# 硬编码密钥（Critical）— 排除测试文件
HARDCODED_KEYS=$(grep -rn --include="*.py" --include="*.js" --include="*.ts" \
    -E '(AIza[0-9A-Za-z]{35}|sk-[0-9A-Za-z]{20,}|ghp_[0-9A-Za-z]{36}|xoxb-[0-9A-Za-z]{24,})' \
    "$TARGET" 2>/dev/null | grep -v "node_modules\|\.git/\|venv\|\.test\.\|\.spec\.\|test_\|_test\.\|mock\|example\|vendor\|\.pnpm\|security/openclaw-\|openclaw-src" | head -10 || true)
if [ -n "$HARDCODED_KEYS" ]; then
    KEY_COUNT=$(echo "$HARDCODED_KEYS" | grep -c "." || true)
    CRITICAL=$((CRITICAL+KEY_COUNT)); CODE_ISSUES=$((CODE_ISSUES+KEY_COUNT))
    while IFS= read -r line; do
        CRITICAL_LIST+="1. [CODE] $line — 🔴 硬编码密钥！\n"
    done <<< "$HARDCODED_KEYS"
fi

# 注释代码（>10行连续注释的代码块）
COMMENTED_CODE=$(grep -rn --include="*.py" --include="*.js" --include="*.ts" \
    -P '^\s*(#|//)\s*(def |class |function |const |let |var |import |from |return |if |for |while )' \
    "$TARGET" 2>/dev/null | grep -v "node_modules\|\.git/\|venv\|vendor" | head -20 || true)
if [ -n "$COMMENTED_CODE" ]; then
    CC_COUNT=$(echo "$COMMENTED_CODE" | grep -c "." || true)
    if [ "$CC_COUNT" -gt 10 ]; then
        WARNING=$((WARNING+1)); CODE_ISSUES=$((CODE_ISSUES+1))
        WARNING_LIST+="1. [CODE] 发现 ${CC_COUNT} 处注释代码 — 建议清理\n"
    fi
fi

# TODO/FIXME/HACK 注释
TODO_COMMENTS=$(grep -rn --include="*.py" --include="*.js" --include="*.ts" --include="*.md" \
    -E '(TODO|FIXME|HACK|XXX|WORKAROUND)' "$TARGET" 2>/dev/null | grep -v "node_modules\|\.git/\|venv" | head -20 || true)
if [ -n "$TODO_COMMENTS" ]; then
    TODO_COUNT=$(echo "$TODO_COMMENTS" | grep -c "." || true)
    if [ "$TODO_COUNT" -gt 20 ]; then
        WARNING=$((WARNING+1)); CODE_ISSUES=$((CODE_ISSUES+1))
        WARNING_LIST+="1. [CODE] ${TODO_COUNT} 个 TODO/FIXME/HACK 注释 — 建议梳理\n"
    fi
fi

# ============================================================
# 4. 配置熵 (CONF)
# ============================================================
echo "  ⚙️ 扫描配置熵..."

# 空 .gitkeep（目录已有其他文件时）— 排除第三方仓库
EMPTY_GITKEEPS=$(find "$TARGET" -name ".gitkeep" $EXCLUDE_DIRS 2>/dev/null | while IFS= read -r gk; do
    dir=$(dirname "$gk")
    file_count=$(find "$dir" -maxdepth 1 -mindepth 1 -not -name ".gitkeep" | wc -l)
    if [ "$file_count" -gt 0 ]; then
        echo "$gk"
    fi
done || true)
for gk in $EMPTY_GITKEEPS; do
    INFO=$((INFO+1)); CONF_ISSUES=$((CONF_ISSUES+1))
    INFO_LIST+="1. [CONF] $gk — 可删除 .gitkeep（目录已有内容）\n"
done

# ============================================================
# 5. 文件熵 (FILE)
# ============================================================
echo "  📁 扫描文件熵..."

# tmp/ 超过 7 天的文件
OLD_TMP=$(find "$HOME/clawd/tmp" -type f -mtime +7 2>/dev/null | head -20 || true)
if [ -n "$OLD_TMP" ]; then
    OLD_TMP_COUNT=$(echo "$OLD_TMP" | grep -c "." || true)
    WARNING=$((WARNING+1)); FILE_ISSUES=$((FILE_ISSUES+1))
    WARNING_LIST+="1. [FILE] ~/clawd/tmp/ — ${OLD_TMP_COUNT} 个文件超过 7 天\n"
fi

# 大文件（>1MB 且非媒体）— 排除第三方
LARGE_FILES=$(scan_files -type f -size +1M \
    -not -name "*.mp4" -not -name "*.mp3" -not -name "*.wav" \
    -not -name "*.png" -not -name "*.jpg" -not -name "*.jpeg" -not -name "*.gif" \
    -not -name "*.pack" -not -name "*.icns" 2>/dev/null | head -10 || true)
for f in $LARGE_FILES; do
    size=$(du -h "$f" 2>/dev/null | cut -f1 || echo "?")
    INFO=$((INFO+1)); FILE_ISSUES=$((FILE_ISSUES+1))
    INFO_LIST+="1. [FILE] $f (${size}) — 大文件，确认是否必要\n"
done

# 重复文件 — 仅限项目目录，排除第三方
DUPES=$(find "$TARGET/projects" "$TARGET/skills" -type f -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/venv/*' -not -name ".gitkeep" -not -name "*.pack" 2>/dev/null | \
    sed 's|.*/||' | sort | uniq -d | head -10 || true)
for name in $DUPES; do
    paths=$(find "$TARGET/projects" "$TARGET/skills" -name "$name" -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/venv/*' 2>/dev/null | tr '\n' ' ')
    INFO=$((INFO+1)); FILE_ISSUES=$((FILE_ISSUES+1))
    INFO_LIST+="1. [FILE] 重复: \"$name\" → $paths\n"
done

# ============================================================
# 6. 依赖熵 (DEP)
# ============================================================
echo "  📦 扫描依赖熵..."

REQ_FILES=$(scan_files -name "requirements.txt" 2>/dev/null || true)
for rf in $REQ_FILES; do
    dep_count=$(grep -c "^[^#]" "$rf" 2>/dev/null || echo 0)
    if [ "$dep_count" -gt 20 ]; then
        WARNING=$((WARNING+1)); DEP_ISSUES=$((DEP_ISSUES+1))
        WARNING_LIST+="1. [DEP] $rf — ${dep_count} 个依赖，建议审查\n"
    fi
done

# ============================================================
# 计算评分
# ============================================================
TOTAL_ISSUES=$((DOC_ISSUES + NAME_ISSUES + CODE_ISSUES + CONF_ISSUES + FILE_ISSUES + DEP_ISSUES))
SCORE=$((100 - CRITICAL * 10 - WARNING * 2 - INFO / 2))
[ "$SCORE" -lt 0 ] && SCORE=0

DOC_SCORE=$((100 - DOC_ISSUES * 5)); [ "$DOC_SCORE" -lt 0 ] && DOC_SCORE=0
NAME_SCORE=$((100 - NAME_ISSUES * 5)); [ "$NAME_SCORE" -lt 0 ] && NAME_SCORE=0
CODE_SCORE=$((100 - CODE_ISSUES * 5 - CRITICAL * 10)); [ "$CODE_SCORE" -lt 0 ] && CODE_SCORE=0
CONF_SCORE=$((100 - CONF_ISSUES * 5)); [ "$CONF_SCORE" -lt 0 ] && CONF_SCORE=0
FILE_SCORE=$((100 - FILE_ISSUES * 5)); [ "$FILE_SCORE" -lt 0 ] && FILE_SCORE=0
DEP_SCORE=$((100 - DEP_ISSUES * 5)); [ "$DEP_SCORE" -lt 0 ] && DEP_SCORE=0

# ============================================================
# 生成报告
# ============================================================
cat > "$REPORT" << REPORT_EOF
# 熵扫描报告 — ${DATE}

## 📊 总评分: ${SCORE}/100

| 分类 | 得分 | 问题数 |
|------|------|--------|
| DOC  | ${DOC_SCORE}  | ${DOC_ISSUES}  |
| NAME | ${NAME_SCORE}  | ${NAME_ISSUES}  |
| CODE | ${CODE_SCORE}  | ${CODE_ISSUES}  |
| CONF | ${CONF_SCORE}  | ${CONF_ISSUES}  |
| FILE | ${FILE_SCORE}  | ${FILE_ISSUES}  |
| DEP  | ${DEP_SCORE}  | ${DEP_ISSUES}  |

REPORT_EOF

if [ -n "$CRITICAL_LIST" ]; then
    echo -e "## 🔴 Critical (立即处理)" >> "$REPORT"
    echo -e "$CRITICAL_LIST" >> "$REPORT"
    echo "" >> "$REPORT"
fi

if [ -n "$WARNING_LIST" ]; then
    echo -e "## 🟡 Warning (本周处理)" >> "$REPORT"
    echo -e "$WARNING_LIST" >> "$REPORT"
    echo "" >> "$REPORT"
fi

if [ -n "$INFO_LIST" ]; then
    echo -e "## 🟢 Info (下次顺手修)" >> "$REPORT"
    echo -e "$INFO_LIST" >> "$REPORT"
    echo "" >> "$REPORT"
fi

# 趋势
LAST_SCORE=""
if [ -f "$HISTORY" ]; then
    LAST_SCORE=$(tail -1 "$HISTORY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('score',''))" 2>/dev/null || true)
fi
{
    echo "## 📈 趋势"
    if [ -n "$LAST_SCORE" ]; then
        echo "- 上次评分: ${LAST_SCORE}/100"
    else
        echo "- 首次扫描，无历史对比"
    fi
    echo "- 总问题数: ${TOTAL_ISSUES} (🔴${CRITICAL} 🟡${WARNING} 🟢${INFO})"
} >> "$REPORT"

# 记录历史
echo "{\"date\":\"${DATE}\",\"score\":${SCORE},\"critical\":${CRITICAL},\"warning\":${WARNING},\"info\":${INFO},\"total\":${TOTAL_ISSUES},\"target\":\"${TARGET}\"}" >> "$HISTORY"

echo ""
echo "✅ 扫描完成！"
echo "   📊 评分: ${SCORE}/100"
echo "   🔴 Critical: ${CRITICAL} | 🟡 Warning: ${WARNING} | 🟢 Info: ${INFO}"
echo "   📄 报告: ${REPORT}"

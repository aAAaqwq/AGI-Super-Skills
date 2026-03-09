#!/bin/bash
# fetch_data.sh - Dual-Agent Resilient Hybrid
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TICKER_UPPER=$(echo "${1:-}" | tr '[:lower:]' '[:upper:]')
[ -z "$TICKER_UPPER" ] && { echo "Usage: $0 <TICKER>"; exit 1; }

DATA_DIR="$(dirname "$SCRIPT_DIR")/.cache/data"
DATA_FILE="$DATA_DIR/${TICKER_UPPER}_data.json"
Y_RAW="$DATA_DIR/${TICKER_UPPER}_yahoo_raw.json"
SEC_FILE="$DATA_DIR/${TICKER_UPPER}_sec_raw.json"
AV_INCOME="$DATA_DIR/${TICKER_UPPER}_av_income.json"
AV_CASHFLOW="$DATA_DIR/${TICKER_UPPER}_av_cashflow.json"
AV_BALANCE="$DATA_DIR/${TICKER_UPPER}_av_balance.json"
COOKIE_FILE="$DATA_DIR/yahoo_cookie.txt"
# Alpha Vantage: key from OpenClaw auth profiles (profile alpha-vantage:default)
OPENCLAW_ROOT="${OPENCLAW_HOME:-${HOME}/.openclaw}"
AUTH_PROFILES="${OPENCLAW_AUTH_PROFILES:-${OPENCLAW_ROOT}/agents/main/agent/auth-profiles.json}"
mkdir -p "$DATA_DIR"

# Separate User Agents 
# Yahoo requires a "Browser" agent. SEC requires a "Bot/Email" agent.
YAHOO_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
# SEC EDGAR requires a User-Agent with contact info. Set SEC_EDGAR_USER_AGENT or use placeholder.
SEC_AGENT="${SEC_EDGAR_USER_AGENT:-OpenClaw-Research-Bot/1.0 (mailto:your-email@example.com)}"

# ============================================
# Helper: SEC Value Extraction
# ============================================
extract_sec_value() {
    local file="$1"; local unit="${2:-USD}"; shift 2
    for tag in "$@"; do
        local val=$(jq -r ".facts.\"us-gaap\"[\"$tag\"].units[\"$unit\"] | sort_by(.end) | last | .val // empty" "$file" 2>/dev/null)
        if [ -n "$val" ] && [ "$val" != "null" ]; then echo "$val"; return 0; fi
    done
    echo "N/A"
}

# Extract two most recent values (for YoY or trend). Echo "PRIOR CURR" (older first) or "N/A N/A".
extract_sec_two_latest() {
    local file="$1" unit="${2:-USD}" tag="$3"
    local arr
    arr=$(jq -r ".facts.\"us-gaap\"[\"$tag\"].units[\"$unit\"] | sort_by(.end) | if length >= 2 then .[-2:] | map(.val) | join(\" \") else \"N/A N/A\" end" "$file" 2>/dev/null)
    if [ -n "$arr" ] && [ "$arr" != "null" ] && [ "$arr" != "N/A N/A" ]; then
        echo "$arr"
    else
        echo "N/A N/A"
    fi
}

# ============================================
# Step 1: Yahoo Finance Extraction
# ============================================
echo "🔍 Acquiring Yahoo Finance Session..."
curl -s -c "$COOKIE_FILE" -H "User-Agent: $YAHOO_AGENT" "https://fc.yahoo.com" > /dev/null || true
CRUMB=$(curl -s -b "$COOKIE_FILE" -H "User-Agent: $YAHOO_AGENT" "https://query1.finance.yahoo.com/v1/test/getcrumb" || echo "")

echo "🔍 Fetching Yahoo Finance data..."
curl -s -b "$COOKIE_FILE" -H "User-Agent: $YAHOO_AGENT" "https://query2.finance.yahoo.com/v7/finance/quote?symbols=${TICKER_UPPER}&crumb=${CRUMB}" > "${Y_RAW}_quote"

# Enriched modules: add annual and quarterly income/cashflow statements
curl -s -b "$COOKIE_FILE" -H "User-Agent: $YAHOO_AGENT" \
    "https://query2.finance.yahoo.com/v10/finance/quoteSummary/${TICKER_UPPER}?modules=earningsHistory,assetProfile,defaultKeyStatistics,financialData,incomeStatementHistory,incomeStatementHistoryQuarterly,cashflowStatementHistory,cashflowStatementHistoryQuarterly&crumb=${CRUMB}" \
    > "${Y_RAW}_summary"

DESC=$(jq -r '.quoteSummary.result[0].assetProfile.longBusinessSummary // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")

# Extract ROE, margins, ROIC from financialData (used by 02-metrics and phase logic)
ROE=$(jq -r '.quoteSummary.result[0].financialData.returnOnEquity.fmt // .quoteSummary.result[0].financialData.returnOnEquity.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
GROSS_MARGIN=$(jq -r '.quoteSummary.result[0].financialData.grossMargins.fmt // .quoteSummary.result[0].financialData.grossMargins.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
OP_MARGIN=$(jq -r '.quoteSummary.result[0].financialData.operatingMargins.fmt // .quoteSummary.result[0].financialData.operatingMargins.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
ROIC=$(jq -r '.quoteSummary.result[0].financialData.returnOnAssets.fmt // .quoteSummary.result[0].financialData.returnOnAssets.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")

PRICE=$(jq -r '.quoteResponse.result[0].regularMarketPrice // "N/A"' "${Y_RAW}_quote" 2>/dev/null || echo "N/A")
MCAP=$(jq -r '.quoteResponse.result[0].marketCap // "N/A"' "${Y_RAW}_quote" 2>/dev/null || echo "N/A")
SURPRISE=$(jq -c '.quoteSummary.result[0].earningsHistory.history | .[-4:] | map({date: .quarter.fmt, surprise: .surprisePercent.fmt})' "${Y_RAW}_summary" 2>/dev/null || echo "[]")
CIK=$(jq -r '.quoteResponse.result[0].extra?.cik // empty' "${Y_RAW}_quote" 2>/dev/null || echo "")

# Derived fundamentals from Yahoo
REV_YOY="N/A"          # annual YoY
NI_YOY="N/A"           # annual YoY
REV_Q_YOY="N/A"        # quarterly YoY (same quarter prior year)
NI_Q_YOY="N/A"         # quarterly YoY
FCF="N/A"              # annual FCF
SHARES_OUT="N/A"
CURR_REV="N/A"         # latest annual revenue
CURR_NI="N/A"          # latest annual net income
CURR_REV_Q="N/A"       # latest quarterly revenue
CURR_NI_Q="N/A"        # latest quarterly net income

# Revenue & Net Income YoY (ANNUAL: from incomeStatementHistory, most recent vs previous year)
if jq -e '.quoteSummary.result[0].incomeStatementHistory.incomeStatementHistory' "${Y_RAW}_summary" > /dev/null 2>&1; then
    CURR_REV=$(jq -r '.quoteSummary.result[0].incomeStatementHistory.incomeStatementHistory[0].totalRevenue.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
    PREV_REV=$(jq -r '.quoteSummary.result[0].incomeStatementHistory.incomeStatementHistory[1].totalRevenue.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
    CURR_NI=$(jq -r '.quoteSummary.result[0].incomeStatementHistory.incomeStatementHistory[0].netIncome.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
    PREV_NI=$(jq -r '.quoteSummary.result[0].incomeStatementHistory.incomeStatementHistory[1].netIncome.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")

    if [[ "$CURR_REV" != "N/A" && "$PREV_REV" != "N/A" && "$PREV_REV" != "0" ]]; then
        REV_YOY=$(echo "scale=4; ($CURR_REV - $PREV_REV) * 100 / $PREV_REV" | bc 2>/dev/null || echo "N/A")
    fi
    if [[ "$CURR_NI" != "N/A" && "$PREV_NI" != "N/A" && "$PREV_NI" != "0" ]]; then
        NI_YOY=$(echo "scale=4; ($CURR_NI - $PREV_NI) * 100 / $PREV_NI" | bc 2>/dev/null || echo "N/A")
    fi
fi

# Revenue & Net Income YoY (QUARTERLY: from incomeStatementHistoryQuarterly, latest vs same qtr prior year)
if jq -e '.quoteSummary.result[0].incomeStatementHistoryQuarterly.incomeStatementHistory' "${Y_RAW}_summary" > /dev/null 2>&1; then
    CURR_REV_Q=$(jq -r '.quoteSummary.result[0].incomeStatementHistoryQuarterly.incomeStatementHistory[0].totalRevenue.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
    CURR_NI_Q=$(jq -r '.quoteSummary.result[0].incomeStatementHistoryQuarterly.incomeStatementHistory[0].netIncome.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
    # Same quarter last year is typically index 4 if history is quarterly and ordered latest-first
    PREV_REV_Q=$(jq -r '.quoteSummary.result[0].incomeStatementHistoryQuarterly.incomeStatementHistory[4].totalRevenue.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
    PREV_NI_Q=$(jq -r '.quoteSummary.result[0].incomeStatementHistoryQuarterly.incomeStatementHistory[4].netIncome.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")

    if [[ "$CURR_REV_Q" != "N/A" && "$PREV_REV_Q" != "N/A" && "$PREV_REV_Q" != "0" ]]; then
        REV_Q_YOY=$(echo "scale=4; ($CURR_REV_Q - $PREV_REV_Q) * 100 / $PREV_REV_Q" | bc 2>/dev/null || echo "N/A")
    fi
    if [[ "$CURR_NI_Q" != "N/A" && "$PREV_NI_Q" != "N/A" && "$PREV_NI_Q" != "0" ]]; then
        NI_Q_YOY=$(echo "scale=4; ($CURR_NI_Q - $PREV_NI_Q) * 100 / $PREV_NI_Q" | bc 2>/dev/null || echo "N/A")
    fi
fi

# Free Cash Flow (from cashflowStatementHistory, prefer freeCashFlow, fallback to opCF - capex)
if jq -e '.quoteSummary.result[0].cashflowStatementHistory.cashflowStatements' "${Y_RAW}_summary" > /dev/null 2>&1; then
    FCF_RAW=$(jq -r '.quoteSummary.result[0].cashflowStatementHistory.cashflowStatements[0].freeCashFlow.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
    if [[ "$FCF_RAW" != "N/A" && "$FCF_RAW" != "null" ]]; then
        FCF="$FCF_RAW"
    else
        OP_CF=$(jq -r '.quoteSummary.result[0].cashflowStatementHistory.cashflowStatements[0].totalCashFromOperatingActivities.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
        CAPEX=$(jq -r '.quoteSummary.result[0].cashflowStatementHistory.cashflowStatements[0].capitalExpenditures.raw // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
        if [[ "$OP_CF" != "N/A" && "$CAPEX" != "N/A" ]]; then
            FCF=$(echo "scale=2; $OP_CF - $CAPEX" | bc 2>/dev/null || echo "N/A")
        fi
    fi
fi

# Shares outstanding (proxy for dilution / buybacks)
SHARES_OUT=$(jq -r '.quoteSummary.result[0].defaultKeyStatistics.sharesOutstanding.raw // .quoteSummary.result[0].defaultKeyStatistics.sharesOutstanding // "N/A"' "${Y_RAW}_summary" 2>/dev/null || echo "N/A")
SHARES_PRIOR="N/A"
SHARES_YOY_PCT="N/A"

# Fallback: gross margin from income statement if financialData missing (gross profit / revenue)
if [[ "$GROSS_MARGIN" == "N/A" || -z "$GROSS_MARGIN" ]]; then
    REV_IS=$(jq -r '.quoteSummary.result[0].incomeStatementHistory.incomeStatementHistory[0].totalRevenue.raw // empty' "${Y_RAW}_summary" 2>/dev/null)
    COST_IS=$(jq -r '.quoteSummary.result[0].incomeStatementHistory.incomeStatementHistory[0].costOfRevenue.raw // empty' "${Y_RAW}_summary" 2>/dev/null)
    if [[ -n "$REV_IS" && -n "$COST_IS" && "$REV_IS" != "0" ]]; then
        GROSS_MARGIN="$(echo "scale=2; ($REV_IS - $COST_IS) * 100 / $REV_IS" | bc 2>/dev/null)%"
    fi
fi
# Fallback: operating margin from income statement (operatingIncome / revenue)
if [[ "$OP_MARGIN" == "N/A" || -z "$OP_MARGIN" ]]; then
    REV_IS=$(jq -r '.quoteSummary.result[0].incomeStatementHistory.incomeStatementHistory[0].totalRevenue.raw // empty' "${Y_RAW}_summary" 2>/dev/null)
    OP_INC=$(jq -r '.quoteSummary.result[0].incomeStatementHistory.incomeStatementHistory[0].operatingIncome.raw // .quoteSummary.result[0].incomeStatementHistory.incomeStatementHistory[0].incomeFromOperations.raw // empty' "${Y_RAW}_summary" 2>/dev/null)
    if [[ -n "$REV_IS" && -n "$OP_INC" && "$REV_IS" != "0" ]]; then
        OP_MARGIN="$(echo "scale=2; $OP_INC * 100 / $REV_IS" | bc 2>/dev/null)%"
    fi
fi
[[ -z "$GROSS_MARGIN" ]] && GROSS_MARGIN="N/A"
[[ -z "$OP_MARGIN" ]] && OP_MARGIN="N/A"
[[ -z "$ROIC" ]] && ROIC="N/A"

# ============================================
# Step 3: SEC Data (Final Precision)
# ============================================
if [ -z "$CIK" ] || [ "$CIK" = "null" ]; then
    echo "🔍 Looking up SEC CIK..."
    # 1) Try SEC company_tickers.json (ticker -> CIK) for listed companies
    SEC_TICKERS=$(curl -s -H "User-Agent: $SEC_AGENT" "https://www.sec.gov/files/company_tickers.json" 2>/dev/null)
    if echo "$SEC_TICKERS" | jq -e '.' >/dev/null 2>&1; then
        CIK=$(echo "$SEC_TICKERS" | jq -r --arg t "$TICKER_UPPER" '[.[] | select(.ticker == $t) | .cik_str] | first // empty' 2>/dev/null)
    fi
    # 2) Fallback: browse-edgar by ticker (atom)
    if [ -z "$CIK" ]; then
        CIK=$(curl -s -H "User-Agent: $SEC_AGENT" "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=${TICKER_UPPER}&output=atom" | grep -o '<cik>[^<]*' | head -1 | sed 's/<cik>//' || echo "")
    fi
fi

REV="$CURR_REV"
NI="$CURR_NI"
if [ -n "$CIK" ]; then
    # Fix: Remove leading zeros and use base-10 to prevent octal conversion errors in printf
    CIK_CLEAN=$(echo "$CIK" | sed 's/^0*//')
    CIK_PADDED=$(printf "%010d" "$CIK_CLEAN")
    echo "🔍 Fetching SEC financial facts for CIK: $CIK_PADDED"
    # 🚨 THE FIX: Use SEC_AGENT so EDGAR doesn't block the request with a 403 error
    if curl -s -H "User-Agent: $SEC_AGENT" "https://data.sec.gov/api/xbrl/companyfacts/CIK${CIK_PADDED}.json" -o "$SEC_FILE"; then
        if [ -s "$SEC_FILE" ] && jq -e '.facts' "$SEC_FILE" > /dev/null 2>&1; then
            # Fallback revenue and net income if Yahoo missing
            if [ "$REV" = "N/A" ] || [ "$NI" = "N/A" ]; then
                SEC_REV=$(extract_sec_value "$SEC_FILE" "USD" "Revenues" "SalesRevenueNet" "RevenueFromContractWithCustomerExcludingAssessedTax")
                SEC_NI=$(extract_sec_value "$SEC_FILE" "USD" "NetIncomeLoss" "ProfitLoss")
                [ "$REV" = "N/A" ] && REV="$SEC_REV"
                [ "$NI" = "N/A" ] && NI="$SEC_NI"
            fi

            # Share count trend: two latest SEC values for YoY (dilution vs buyback)
            # Try multiple SEC concept names and units (companies use different XBRL tags)
            SEC_SHARES_TWO=$(extract_sec_two_latest "$SEC_FILE" "shares" "CommonStockSharesOutstanding")
            [ "$SEC_SHARES_TWO" = "N/A N/A" ] && SEC_SHARES_TWO=$(extract_sec_two_latest "$SEC_FILE" "pure" "CommonStockSharesOutstanding")
            [ "$SEC_SHARES_TWO" = "N/A N/A" ] && SEC_SHARES_TWO=$(extract_sec_two_latest "$SEC_FILE" "shares" "CommonStockSharesIssued")
            [ "$SEC_SHARES_TWO" = "N/A N/A" ] && SEC_SHARES_TWO=$(extract_sec_two_latest "$SEC_FILE" "shares" "WeightedAverageNumberOfSharesOutstandingBasic")
            if [ "$SEC_SHARES_TWO" != "N/A N/A" ]; then
                SHARES_PRIOR=$(echo "$SEC_SHARES_TWO" | awk '{print $1}')
                SHARES_CURR_SEC=$(echo "$SEC_SHARES_TWO" | awk '{print $2}')
                if [[ -n "$SHARES_PRIOR" && -n "$SHARES_CURR_SEC" && "$SHARES_PRIOR" != "0" && "$SHARES_PRIOR" != "N/A" ]]; then
                    SHARES_YOY_PCT=$(echo "scale=2; ($SHARES_CURR_SEC - $SHARES_PRIOR) * 100 / $SHARES_PRIOR" | bc 2>/dev/null || echo "N/A")
                    # Prefer SEC current when we have SEC trend so all three (outstanding, prior, yoy_pct) are from same source
                    SHARES_OUT="$SHARES_CURR_SEC"
                else
                    SHARES_PRIOR="N/A"
                fi
            fi

            # FCF fallback: operating cash flow minus capex
            if [ "$FCF" = "N/A" ]; then
                SEC_OP_CF=$(extract_sec_value "$SEC_FILE" "USD" \
                    "NetCashProvidedByUsedInOperatingActivities" \
                    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations")
                SEC_CAPEX=$(extract_sec_value "$SEC_FILE" "USD" \
                    "PaymentsToAcquirePropertyPlantAndEquipment" \
                    "PaymentsToAcquireProductiveAssets")
                if [[ "$SEC_OP_CF" != "N/A" && "$SEC_CAPEX" != "N/A" ]]; then
                    FCF=$(echo "scale=2; $SEC_OP_CF - $SEC_CAPEX" | bc 2>/dev/null || echo "N/A")
                fi
            fi
        fi
    fi
fi

# ============================================
# Step 3.5: Alpha Vantage fallback (FCF, revenue_q_yoy)
# Key from OpenClaw auth profiles (profile alpha-vantage:default).
# Uses up to 2 API calls when key is set and Yahoo/SEC left any of these N/A.
# ============================================
AV_KEY=""
if [ -f "$AUTH_PROFILES" ]; then
    AV_KEY=$(jq -r '.profiles["alpha-vantage:default"].key // empty' "$AUTH_PROFILES" 2>/dev/null || true)
fi
if [[ -n "$AV_KEY" && ( "$FCF" = "N/A" || "$REV_Q_YOY" = "N/A" || "$SHARES_PRIOR" = "N/A" ) ]]; then
    echo "🔍 Alpha Vantage fallback for FCF / revenue_q_yoy / share count trend..."
    BASE_AV="https://www.alphavantage.co/query"
    if [ "$REV_Q_YOY" = "N/A" ]; then
        curl -s "${BASE_AV}?function=INCOME_STATEMENT&symbol=${TICKER_UPPER}&apikey=${AV_KEY}" -o "$AV_INCOME"
        if ! jq -e '.["Error Message"] // .["Note"]' "$AV_INCOME" >/dev/null 2>&1; then
            # quarterlyReports: [0]=latest, [4]=same quarter prior year (if 5 quarters available)
            REV_Q_CURR=$(jq -r '.quarterlyReports[0].totalRevenue // empty' "$AV_INCOME" 2>/dev/null)
            REV_Q_PREV=$(jq -r '.quarterlyReports[4].totalRevenue // .quarterlyReports[1].totalRevenue // empty' "$AV_INCOME" 2>/dev/null)
            if [[ -n "$REV_Q_CURR" && -n "$REV_Q_PREV" && "$REV_Q_PREV" != "0" ]]; then
                REV_Q_YOY=$(echo "scale=4; ($REV_Q_CURR - $REV_Q_PREV) * 100 / $REV_Q_PREV" | bc 2>/dev/null || echo "N/A")
            fi
        fi
        sleep 2
    fi
    if [ "$FCF" = "N/A" ]; then
        curl -s "${BASE_AV}?function=CASH_FLOW&symbol=${TICKER_UPPER}&apikey=${AV_KEY}" -o "$AV_CASHFLOW"
        if ! jq -e '.["Error Message"] // .["Note"]' "$AV_CASHFLOW" >/dev/null 2>&1; then
            # Alpha Vantage: operatingCashflow, capitalExpenditures (capex often negative)
            OP_CF_AV=$(jq -r '.annualReports[0].operatingCashflow // empty' "$AV_CASHFLOW" 2>/dev/null)
            CAPEX_AV=$(jq -r '.annualReports[0].capitalExpenditures // empty' "$AV_CASHFLOW" 2>/dev/null)
            if [[ -n "$OP_CF_AV" && "$OP_CF_AV" != "None" ]]; then
                if [[ -n "$CAPEX_AV" && "$CAPEX_AV" != "None" && "$CAPEX_AV" != "0" ]]; then
                    # Capex is typically negative; FCF = operating + capex (e.g. 100 + (-20) = 80)
                    FCF=$(echo "scale=0; $OP_CF_AV + $CAPEX_AV" | bc 2>/dev/null || echo "$OP_CF_AV")
                else
                    FCF="$OP_CF_AV"
                fi
            fi
        fi
    fi
    # Share count trend: quarterly balance sheet has commonStockSharesOutstanding
    if [ "$SHARES_PRIOR" = "N/A" ]; then
        curl -s "${BASE_AV}?function=BALANCE_SHEET&symbol=${TICKER_UPPER}&apikey=${AV_KEY}" -o "$AV_BALANCE"
        if ! jq -e '.["Error Message"] // .["Note"]' "$AV_BALANCE" >/dev/null 2>&1; then
            AV_SHARES_CURR=$(jq -r '.quarterlyReports[0].commonStockSharesOutstanding // empty' "$AV_BALANCE" 2>/dev/null)
            AV_SHARES_PRIOR=$(jq -r '.quarterlyReports[4].commonStockSharesOutstanding // .quarterlyReports[1].commonStockSharesOutstanding // empty' "$AV_BALANCE" 2>/dev/null)
            if [[ -n "$AV_SHARES_CURR" && -n "$AV_SHARES_PRIOR" && "$AV_SHARES_PRIOR" != "0" && "$AV_SHARES_PRIOR" != "None" ]]; then
                SHARES_PRIOR="$AV_SHARES_PRIOR"
                SHARES_YOY_PCT=$(echo "scale=2; ($AV_SHARES_CURR - $AV_SHARES_PRIOR) * 100 / $AV_SHARES_PRIOR" | bc 2>/dev/null || echo "N/A")
                [ "$SHARES_OUT" = "N/A" ] && SHARES_OUT="$AV_SHARES_CURR"
            fi
        fi
        sleep 2
    fi
    rm -f "$AV_INCOME" "$AV_CASHFLOW" "$AV_BALANCE"
fi

# ============================================
# Step 4: Final JSON Compilation
# ============================================
echo "💾 Compiling Unified Dataset..."
jq -n \
    --arg ticker "$TICKER_UPPER" \
    --arg desc "$DESC" \
    --arg rev "$REV" \
    --arg ni "$NI" \
    --arg rev_yoy "$REV_YOY" \
    --arg ni_yoy "$NI_YOY" \
    --arg rev_q "$CURR_REV_Q" \
    --arg ni_q "$CURR_NI_Q" \
    --arg rev_q_yoy "$REV_Q_YOY" \
    --arg ni_q_yoy "$NI_Q_YOY" \
    --arg fcf "$FCF" \
    --arg shares_out "$SHARES_OUT" \
    --arg shares_prior "$SHARES_PRIOR" \
    --arg shares_yoy_pct "$SHARES_YOY_PCT" \
    --arg price "$PRICE" \
    --arg cap "$MCAP" \
    --arg roe "$ROE" \
    --arg gross_margin "$GROSS_MARGIN" \
    --arg op_margin "$OP_MARGIN" \
    --arg roic "$ROIC" \
    --argjson surprise "$SURPRISE" \
    '{
        ticker: $ticker,
        timestamp: (now | strftime("%Y-%m-%dT%H:%M:%SZ")),
        company_profile: { name: $ticker, description: $desc },
        financial_metrics: { 
            revenue: $rev, 
            net_income: $ni, 
            roe: $roe,
            gross_margin: $gross_margin,
            operating_margin: $op_margin,
            roic: $roic,
            revenue_yoy: $rev_yoy,
            net_income_yoy: $ni_yoy,
            revenue_q: $rev_q,
            net_income_q: $ni_q,
            revenue_q_yoy: $rev_q_yoy,
            net_income_q_yoy: $ni_q_yoy,
            fcf: $fcf,
            shares_outstanding: $shares_out,
            shares_prior: $shares_prior,
            shares_yoy_pct: $shares_yoy_pct
        },
        valuation: { current_price: $price, market_cap: $cap },
        momentum: { earnings_surprises: $surprise }
    }' > "$DATA_FILE"

# Cleanup
rm -f "$SEC_FILE" "${Y_RAW}_quote" "${Y_RAW}_summary" "$COOKIE_FILE"
echo "✅ Data ready: $DATA_FILE"
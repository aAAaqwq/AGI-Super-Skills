# Polymarket Cron 计划

## 浏览器自动化工具

**browser-use** (v0.11.11) — 所有浏览器操作优先使用 browser-use

| 特性 | browser-use | Playwright | OpenClaw browser tool |
|------|-------------|-----------|----------------------|
| AI 驱动 | ✅ LLM自主操作 | ❌ 硬编码脚本 | ✅ 手动指令 |
| 适合 cron | ✅ | ✅ | ❌ |
| 自适应 | ✅ 页面变化自动适应 | ❌ 选择器失效则失败 | ✅ |
| Token消耗 | ~2K-5K/次 | 0 | ~3K-8K/次 |

## 保留的 Cron

- **Polymarket 登录态维护** — 每6小时（browser-use检查）
- **auth-session-check** — 每6小时
- **Polymarket 自动交易** — 每日10:00（`8df00327`）

## Cron 设计

### 1. 每日 10:00 — 市场扫描 + 交易执行
- **已有**: `8df00327` Polymarket 自动交易
- **脚本**: `scripts/browser_use_trader.py check` → 分析 → `trade`
- **流程**: 
  1. browser-use 打开 Polymarket 扫描市场
  2. 分析高价值机会
  3. 执行交易（需要确认或自动）
  4. 更新 portfolio.json

### 2. 每日 20:00 — 持仓报告推送
- **脚本**: `scripts/portfolio_report.py --send`
- **目标群**: `YOUR_GROUP_CHAT_ID`

### 3. 每6小时 — 登录态维护
- **脚本**: `scripts/browser_use_trader.py` (login check)
- 使用 browser-use 检查 Polymarket 登录状态

## 数据文件
- `data/portfolio.json` — 当前持仓
- `data/trade_log.json` — 交易历史记录

## 执行命令

```bash
# 使用 venv
source ~/clawd/skills/polymarket-profit/venv/bin/activate

# 检查市场
python3 ~/clawd/skills/polymarket-profit/scripts/browser_use_trader.py check

# 执行交易
python3 ~/clawd/skills/polymarket-profit/scripts/browser_use_trader.py trade --market <slug> --action buy_no --amount 0.5

# 查看持仓
python3 ~/clawd/skills/polymarket-profit/scripts/browser_use_trader.py portfolio
```

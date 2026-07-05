# 5minbtc 仓库同步 (AGI-Super-Team)

## 同步命令
```bash
# 1. rsync 本地最新版到共享仓库 (排除运行时数据和日志)
rsync -av \
  --exclude='data/' --exclude='logs/' --exclude='reviews/' --exclude='archive/' --exclude='__pycache__/' \
  --exclude='*.jsonl' --exclude='*.jsonl.*' --exclude='*.gz' \
  /home/aa/.hermes/profiles/cqo/skills/5minbtc/ \
  /home/aa/clawd/repos/AGI-Super-Team/skills/5minbtc/

# 2. 提交推送
cd /home/aa/clawd/repos/AGI-Super-Team
git add skills/5minbtc/
git commit -m "sync(skills/5minbtc): <变更简述>"
git push origin master
```

## Commit message 惯例
`sync(skills/5minbtc): <版本> 全量同步 — 引擎+回测+复盘+参考文档`

## 同步内容
- 引擎 (`5minbtc-engine*.py`), 日志模块 (`5minbtc-log.py`), 新闻模块 (`5minbtc-news.py`)
- `SKILL.md` (含冲突裁决规则同步)
- `backtest/` (含脚本、结果 JSON、README)
- `references/` (含黑天鹅防御、Dreaming 恢复、Binance 地理、性能历史)
- `review-*.md` 全量复盘记录

## 排除
- `data/`, `__pycache__/` (运行时产物)
- `logs/`, `reviews/` (归档产物, 仅本地保留)
- `archive/` (旧版本引擎, 仅本地保留, 不上传共享仓库)
- `*.jsonl`, `*.jsonl.*.gz` (海量预测日志, 按需同步)

## 推送前检查
- 不含敏感数据 (密钥、API 凭证)
- 不含市场数据 (data/)
- 不含海量日志 (*.jsonl.gz)

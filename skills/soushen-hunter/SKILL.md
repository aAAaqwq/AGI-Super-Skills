# soushen-hunter
> 搜神猎手——基于 Playwright 的高性能 Bing 搜索与深度网页信息提取

> **注意**：此 skill 已有 git 管理的 SKILL.md。如未检出，执行 `git checkout HEAD -- SKILL.md`。

## 使用场景
- 需要 Bing 搜索时（无 API 成本）
- 深度页面分析（提取链接、表单、按钮、脚本、元数据）
- 结构化搜索结果获取

## 使用方法
```bash
# 基础搜索
python scripts/bing_search.py "搜索关键词"

# 深度分析
python scripts/bing_search.py "关键词" --deep <目标URL>
```

## 相关文件
- `scripts/bing_search.py` — 搜索核心脚本
- `soushen` — CLI 入口

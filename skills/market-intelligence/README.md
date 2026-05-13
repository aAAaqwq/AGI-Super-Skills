# AI Market Intelligence Agent

自动收集、分析和报告市场/行业信息的智能代理。

## 功能特性

- ✅ 关键词/公司/产品监控
- ✅ 多平台数据聚合（新闻、社交媒体、研究）
- ✅ 结构化报告生成
- ✅ 定制化模板
- ✅ 可集成到 OpenClaw 工作流

## 快速开始

### 安装

```bash
cd skills/market-intelligence
chmod +x main.sh
./setup.sh
```

### 使用

```bash
# 生成市场报告
./main.sh "AI agent" "news, twitter" "markdown"

# 生成周报
./main.sh --keyword "cryptocurrency" --period "week"

# 导出 JSON 格式
./main.sh --keyword "fintech" --format "json"
```

## 配置

编辑 `config.json` 配置数据源和定价：

```json
{
  "sources": {
    "news": {
      "enabled": true,
      "api_key": "your_key_here"
    }
  },
  "pricing": {
    "single_report": 10,
    "monthly_subscription": 100
  }
}
```

## 输出格式

### Markdown 报告
- 摘要
- 趋势分析
- 关键洞察
- 数据来源

### JSON 数据
- 结构化数据
- 供其他工具使用

## 定价

| 服务 | 价格 |
|------|------|
| 单次报告 | $10 |
| 月度订阅 | $100 |
| 企业定制 | 按需 |

## 集成 OpenClaw

在 `AGENTS.md` 或技能配置中引用：

```bash
openclaw spawn --task "Run market intelligence on keyword 'AI agent'" --agent "wecom-dm-zhangyang"
```

## 开发

- 主脚本: `main.sh`
- 配置: `config.json`
- 输出目录: `output/`

## 许可证

MIT License

---

**开发者**: OpenClaw AI Agent
**版本**: 1.0.0

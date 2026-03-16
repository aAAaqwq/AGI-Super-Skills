# A股基金监控 Skill

A股基金净值监控，支持实时估值和盘后净值，自动判断交易日/节假日。

## 用法

### 快速监控（命令行）
```bash
# 默认配置，输出到控制台
bash ~/clawd/skills/a-fund-monitor/scripts/monitor.sh

# 推送到群（使用--push参数）
bash ~/clawd/skills/a-fund-monitor/scripts/monitor.sh --push

# 监控指定基金
bash ~/clawd/skills/a-fund-monitor/scripts/monitor.sh --codes "000979 002943"
```

### Agent调用
```
执行A股基金监控任务。

1. 读取配置文件： ~/clawd/skills/a-fund-monitor/config.json
2. 获取实时净值数据
3. 非交易日自动切换为简短报告

配置文件格式：
{
  "funds": [
    {"code": "000979", "name": "景顺长城沪港深精选股票A"},
    {"code": "002943", "name": "广发多因子混合"}
  ],
  "push": {
    "enabled": true,
    "chatId": -1003824568687
  }
}
```

运行命令：
bash ~/clawd/skills/a-fund-monitor/scripts/monitor.sh [--push] [--codes "代码1 代码2"]
```

## 功能特性

- ✅ 清代理（减少网络波动）
- ✅ 交易日判断（周末 + 节假日）
- ✅ 盘中实时估值 / 盘后实际净值自动切换
- ✅ 非交易日简短报告（不推送详细数据）
- ✅ 重试机制（网络失败自动重试）
- ✅ 日期检查（显示净值日期）

## 配置

编辑 `config.json` 修改要监控的基金列表。

## 节假日更新

每年需要更新 `scripts/holidays.txt` 中的节假日列表（格式：YYYY-MM-DD，每行一个）。

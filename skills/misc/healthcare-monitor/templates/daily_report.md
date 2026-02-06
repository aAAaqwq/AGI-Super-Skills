📊 **医疗企业融资监控日报**

**日期**: {{date}}
**监控企业数**: {{total_companies}}
**检查次数**: {{check_count}}
**发现信号**: {{signal_count}}

---

## 📈 今日融资信号

{{#if signals}}
{{#each signals}}
### {{index}}. {{company_name}}

| 项目 | 内容 |
|------|------|
| 置信度 | {{confidence}}% |
| 预估轮次 | {{round_estimate}} |
| 预估金额 | {{amount_estimate}} |
| 投资方 | {{investors}} |

**变更详情**: {{change_summary}}

---

{{/each}}
{{else}}
*今日未发现融资信号*
{{/if}}

## 📋 监控统计

| 类别 | 企业数 | 检查数 | 信号数 |
|------|--------|--------|--------|
| 医疗器械 | {{stats.device.count}} | {{stats.device.checks}} | {{stats.device.signals}} |
| 创新药 | {{stats.pharma.count}} | {{stats.pharma.checks}} | {{stats.pharma.signals}} |
| 医疗AI | {{stats.ai.count}} | {{stats.ai.checks}} | {{stats.ai.signals}} |
| 互联网医疗 | {{stats.internet.count}} | {{stats.internet.checks}} | {{stats.internet.signals}} |
| 基因检测 | {{stats.gene.count}} | {{stats.gene.checks}} | {{stats.gene.signals}} |

---

## ⚠️ 异常情况

{{#if errors}}
{{#each errors}}
- {{time}}: {{message}}
{{/each}}
{{else}}
*无异常*
{{/if}}

---

*报告生成时间: {{generated_at}}*
*由 OpenClaw 医疗监控系统自动生成*

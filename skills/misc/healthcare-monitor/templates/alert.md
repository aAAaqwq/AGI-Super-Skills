🚨 **融资信号告警**

**企业**: {{company_name}}
**变更时间**: {{change_date}}
**置信度**: {{confidence}}%

---

**变更详情**:
{{#if capital_change}}
- 📈 注册资本: {{old_capital}} → {{new_capital}} ({{capital_change_pct}}%)
{{/if}}
{{#if new_shareholders}}
- 👥 新增股东: {{new_shareholders}}
{{/if}}
{{#if equity_changes}}
- 📊 股权变化: {{equity_changes}}
{{/if}}

---

**AI 分析**:
- 🎯 融资轮次: {{round_estimate}}
- 💰 预估金额: {{amount_estimate}}
{{#if investors}}
- 🏦 投资方: {{investors}}
{{/if}}

---

**信号权重**:
{{#each signals}}
- {{description}} (+{{weight}})
{{/each}}

---

📊 数据来源: 天眼查
⏰ 监控时间: {{monitor_time}}

*由 OpenClaw 医疗监控系统自动生成*

# 线索记录字段规范

用于 `domestic-acquisition` 包内跨模块复用的企业线索最小字段集。目标：让 `lead-mining`、`customer-profile`、`outreach-automation` 之间直接传递同一份结构化记录，避免每个模块各自定义字段。

## 最小字段集

| 字段名 | 必填 | 说明 |
|---|---|---|
| `company_name` | 是 | 企业主体名称，作为主去重键 |
| `industry_tag` | 是 | 行业/赛道标签，允许单值起步 |
| `region` | 是 | 地域，如城市/省份 |
| `source_url` | 是 | 来源链接，必须可回溯 |
| `website` | 否 | 官网或主要落地页 |
| `contact_entry` | 否 | 可触达入口，如电话/微信入口/表单页 |
| `notes` | 否 | 备注，记录低置信度信息或补充说明 |
| `collected_at` | 否 | 采集时间，推荐 ISO 日期 |

## 字段约束

- 去重主键：优先按 `company_name`；必要时辅以 `website`。
- 缺失处理：缺少非必填字段可保留为空，但必须在 `notes` 标记原因。
- 来源要求：`source_url` 必须保留原始链接，不允许只写平台名称。
- 命名要求：CSV 列名与 Markdown 表头统一使用以上英文 snake_case。

## 模块使用约定

- `lead-mining`：负责首次生成上述字段集。
- `customer-profile`：在不破坏原字段的前提下补充画像字段。
- `outreach-automation`：直接消费 `company_name`、`industry_tag`、`region`、`contact_entry` 等字段用于触达准备。

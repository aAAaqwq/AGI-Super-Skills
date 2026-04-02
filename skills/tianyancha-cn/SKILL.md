---
name: tianyancha-cn
description: 企业信息查询 - 天眼查/企查查/爱企查数据查询（Bloomberg 终端中国版）
metadata:
  openclaw:
    emoji: "🏢"
    category: "business"
    tags: ["tianyancha", "qichacha", "china", "company", "business-intelligence"]
---

# 企业信息查询

天眼查/企查查/爱企查数据查询。

## 功能

- 🏢 企业基本信息
- 👥 股东/高管
- 📊 财务数据
- ⚖️ 法律风险
- 📈 经营状况

## 平台对比

| 平台 | 免费额度 | API | 数据质量 |
|------|---------|-----|---------|
| **天眼查** | 有限 | ✅ | ⭐⭐⭐⭐ |
| **企查查** | 有限 | ✅ | ⭐⭐⭐⭐ |
| **爱企查** | 免费 | ❌ | ⭐⭐⭐ |

## 天眼查 API

### 获取企业信息

```bash
# 需要 API Token
curl "https://open.api.tianyancha.com/services/open/search/2.0?keyword=腾讯" \
  -H "Authorization: YOUR_TOKEN"
```

### Python SDK

```python
# 第三方库
pip install tianyancha

from tianyancha import Tianyancha
client = Tianyancha(API_KEY)
company = client.search("腾讯")
```

## 企查查 API

### 获取企业信息

```bash
curl "https://api.qichacha.com/ECIV4/GetEnterpriseByName?keyword=腾讯" \
  -H "Authorization: YOUR_TOKEN"
```

## 使用场景

### 1. 投资尽调

- 公司背景调查
- 股东穿透
- 关联企业

### 2. 商务合作

- 合作方资质
- 经营风险
- 信用评估

### 3. 市场研究

- 竞品分析
- 行业分布
- 资本图谱

## 数据字段

| 字段 | 说明 |
|------|------|
| name | 企业名称 |
| credit_code | 统一社会信用代码 |
| legal_person | 法定代表人 |
| registered_capital | 注册资本 |
| establish_date | 成立日期 |
| status | 经营状态 |
| shareholders | 股东信息 |
| risk_info | 风险信息 |

## 免费替代方案

### 爱企查

- 网页: https://aiqicha.baidu.com/
- 免费，但无 API

### 国家企业信用信息公示系统

- 网页: http://www.gsxt.gov.cn/
- 官方数据，免费

## 注意事项

1. **API 费用**: 按次收费
2. **数据更新**: 非实时
3. **合规使用**: 仅用于合法目的

---

*版本: 1.0.0*

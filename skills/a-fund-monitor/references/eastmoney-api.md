# 东方财富基金 API 参考

## 1. 盘中实时估值 API

**用途**: 获取交易时段（9:30-15:00）的实时基金估值

```
GET http://fundgz.1234567.com.cn/js/{fund_code}.js
```

**请求头**:
```
User-Agent: Mozilla/5.0
Referer: https://fund.eastmoney.com/
```

**响应格式**: JSONP
```javascript
jsonpgz({"fundcode":"003304","name":"前海开源沪港深核心资源混合","jzrq":"2026-05-21","dwjz":"5.1670","gsz":"5.3302","gszzl":"3.16","gztime":"2026-05-22 15:00"});
```

**字段说明**:
| 字段 | 含义 |
|------|------|
| `fundcode` | 基金代码 |
| `name` | 基金全称 |
| `jzrq` | 最近净值日期 |
| `dwjz` | 最近单位净值 |
| `gsz` | 估算净值（实时） |
| `gszzl` | 估算涨跌幅（%） |
| `gztime` | 估值时间 |

**解析**: 正则 `jsonpgz\((.+?)\);` 提取 JSON

**注意**:
- 非交易时段返回上一交易日收盘时的估值快照
- QDII 基金（如广发纳斯达克100）估值时间显示为美股收盘时间（如 04:00）

## 2. 收盘净值 API

**用途**: 获取基金历史净值数据（收盘后更新）

```
GET https://api.fund.eastmoney.com/f10/lsjz?callback=&fundCode={fund_code}&pageIndex=1&pageSize=1
```

**请求头**:
```
User-Agent: Mozilla/5.0
Referer: https://fund.eastmoney.com/
```

**注意**: `callback=` 留空则返回纯 JSON（非 JSONP）

**响应格式**: JSON
```json
{
  "Data": {
    "LSJZList": [
      {
        "DWJZ": "5.1670",
        "FSRQ": "2026-05-21",
        "JZZZL": "-1.20",
        "LJJZ": "5.1970",
        "SGZT": "开放申购",
        "SHZT": "开放赎回"
      }
    ]
  }
}
```

**关键字段**:
| 字段 | 含义 |
|------|------|
| `DWJZ` | 单位净值 |
| `FSRQ` | 净值日期 |
| `JZZZL` | 净值增长率（日涨跌幅%） ⚠️ 不是 NAVCHGRT |
| `LJJZ` | 累计净值 |

## 3. 基金搜索 API

**用途**: 通过名称查找基金代码

```
GET https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx?m=1&key={keyword}
```

**响应**: JSON，`Datas` 数组中每项含 `CODE` 和 `NAME`

## 4. 基金代码速查

当前监控的 14 只基金：

| 代码 | 简称 | 备注 |
|------|------|------|
| 003304 | 前海开源沪港深核心资源混合A | |
| 015790 | 永赢高端装备智选混合发起C | |
| 015508 | 兴业中证500指数增强C | |
| 000979 | 景顺长城沪港深精选股票A | |
| 270042 | 广发纳斯达克100ETF联接人民币(QDII)A | QDII，净值延迟 |
| 519771 | 交银优择回报灵活配置混合C | |
| 014418 | 西部利得CES芯片指数增强A | |
| 012414 | 招商中证白酒指数(LOF)C | |
| 002943 | 广发多因子混合 | |
| 025209 | 永赢先锋半导体智选混合发起C | |
| 000217 | 华安黄金ETF联接C | |
| 012768 | 华夏中证动漫游戏ETF发起式联接A | |
| 025857 | 华夏中证电网设备主题ETF发起式联接C | |
| 026073 | 广发研究智选混合C | |

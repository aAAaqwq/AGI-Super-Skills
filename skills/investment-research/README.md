# 投资研究（Investment Research）

执行结构化投资研究（投研分析），用于公司/股票/ETF/行业的专业分析。

[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](https://github.com/openclaw/skill-template)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

## 📋 功能概述

本技能提供完整的投研分析框架，包括：
- ✅ 基本面分析（财务报表与商业模式）
- ✅ 技术分析（技术指标与关键价位）
- ✅ 行业研究（行业景气与竞争格局）
- ✅ 估值分析（估值对比与情景分析）
- ✅ 催化剂与风险评估
- ✅ 结构化报告输出

## 🚀 安装与使用

### 安装方式

通过 ClawHub 安装：
```bash
clawhub install investment-research
```

或手动安装到工作区：
```bash
git clone https://github.com/CaiJichang212/investment-research.git
cp -r investment-research ~/.openclaw/skills/
```

### 使用示例

```
- "按基本面+行业+估值分析一下 XX（给 bull/base/bear）"
- "把 XX 最近 3 年的财务质量拆开讲，看看有没有风险点"
- "用技术面给一个交易计划：支撑阻力、止损止盈怎么设"
- "对比 XX 和 YY：谁更值得配置？给关键分歧与跟踪指标"
```

## ⚙️ 数据配置说明

**重要：本技能需要配置数据源才能获取实时财经数据。**

### 必需配置

#### 1. qveris-official（推荐）

用于获取股价、财报等结构化数据和专业财经数据。

**配置方式：**
- 在工具配置中启用 `qveris-official` 工具
- 如需 API Key，请参考 qveris 官方文档进行配置

**用途：**
- 股价历史数据
- 财务报表（资产负债表、利润表、现金流量表）
- 专业财经数据
- 一致预期数据

#### 2. tavily-search（备用）

用于基本信息查询和网页数据补充。

**配置方式：**
- 在工具配置中启用 `tavily-search` 工具
- 如需 API Key，请参考 Tavily 官方文档进行配置

**用途：**
- 公司基本信息查询
- 公告和新闻检索
- 补充数据交叉验证

### 数据获取流程

1. **优先使用**：公司公告/财报、交易所披露、权威统计、主流券商一致预期
2. **数据验证**：至少使用 2 个独立来源进行交叉验证
3. **数据标注**：明确标注数据来源、日期和口径
4. **不确定处理**：无法验证的数据明确标注"未知/待验证"

## 📊 分析框架

### Step 1 - 数据与事实层
- 获取最新财务数据和市场信息
- 多源交叉验证确保数据准确性

### Step 2 - 基本面分析
- 三表联动分析（资产负债表/利润表/现金流量表）
- 商业模式与护城河分析
- 风险点识别

### Step 3 - 行业研究
- 行业市场规模与景气度
- 竞争格局分析
- 政策与监管影响

### Step 4 - 估值分析
- 相对估值（PE/PB/PEG/EV/EBITDA）
- 绝对估值（DCF/情景分析）
- 估值区间输出

### Step 5 - 技术分析
- 多周期趋势分析
- 关键支撑/阻力位识别
- 交易计划制定

### Step 6 - 结论与建议
- 明确投资观点
- 催化剂与风险评估
- 反证分析

## 📝 使用示例

```
- "按基本面+行业+估值分析一下 XX（给 bull/base/bear）"
- "把 XX 最近 3 年的财务质量拆开讲，看看有没有风险点"
- "用技术面给一个交易计划：支撑阻力、止损止盈怎么设"
- "对比 XX 和 YY：谁更值得配置？给关键分歧与跟踪指标"
```

## 📄 输出规范

- 结构化投研分析报告
- 行动清单与跟踪指标
- 明确区分事实/假设/判断
- 完整的风险提示与免责声明

## 📚 参考资料

- [报告模板](references/report-template.md) - 标准化报告结构
- [指标速查](references/indicator-cheatsheet.md) - 财务与技术指标定义

## 🔧 技术规格

- **版本**: 0.3.0
- **语言**: 中英文双语
- **兼容性**: OpenClaw / ClawHub
- **依赖**: qveris-official (推荐), tavily-search (备用)

## 📝 更新日志

### v0.3.0 (2026-03-19)
- ✅ 完善 clawhub 元数据配置
- ✅ 优化 SKILL.md 格式和内容
- ✅ 添加工具要求说明
- ✅ 完善安装与使用文档

### v0.1.0
- 初始版本发布
- 基本投研分析框架
- 报告模板和指标速查

## ⚠️ 免责声明

本技能仅用于信息交流与研究讨论，不构成投资建议。投资有风险，入市需谨慎。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- OpenClaw 社区
- ClawHub 平台

# PRD 输出模式

## 文档头模板

```markdown
# [产品名称] 产品需求文档

**版本**：V[X.X]
**更新日期**：[YYYY-MM-DD]
**文档状态**：[草稿/评审中/正式版]
**作者**：[作者名称]

---

## 变更记录

| 版本 | 日期 | 修改人 | 修改内容 |
|------|------|--------|----------|
| 1.0 | 2026-01-01 | 张三 | 初始版本 |
```

## 用例表格模板

```markdown
### UC-XX [用例名称]

| 项目 | 内容 |
|------|------|
| **用例编号** | UC-XX |
| **用例名称** | [用例名称] |
| **参与者** | [参与者列表，逗号分隔] |
| **前置条件** | [系统需要满足的初始状态] |
| **后置条件** | [用例执行完成后的系统状态] |
| **基本事件流** | 1. [步骤1]<br>2. [步骤2]<br>3. [步骤3] |
| **备选事件流** | 1a. [条件]：系统[处理]<br>2a. [条件]：系统[处理] |
| **业务规则** | 1. [规则1]<br>2. [规则2] |
```

## 数据字典表格模板

```markdown
**数据表名（table_name）**

| 字段名 | 字段中文名 | 数据类型 | 取值范围 | 是否必填 | 备注说明 |
|--------|------------|----------|----------|----------|----------|
| id | ID | VARCHAR(36) | UUID | 是 | 主键 |
| name | 名称 | VARCHAR(100) | - | 是 | - |
| status | 状态 | VARCHAR(20) | PENDING,ACTIVE,INACTIVE | 是 | 默认ACTIVE |
| created_at | 创建时间 | DATETIME | - | 是 | 自动记录 |
| updated_at | 更新时间 | DATETIME | - | 否 | 自动更新 |

**状态说明**：
- PENDING: 待处理
- ACTIVE: 激活
- INACTIVE: 未激活
```

## 图形符号约定

### ASCII 边框
```markdown
┌──────────────┐  水平-垂直连接
├──────────────┤  水平-垂直分隔
└──────────────┘  水平-垂直结束
│              │  垂直线
──────────────  水平线
►              箭头向右
◄              箭头向左
▼              箭头向下
▲              箭头向上
```

### 流程图元素
```markdown
     ┌─────────┐
     │  过程   │     矩形：处理/操作
     └────┬────┘
          │
     ┌────▼────┐
     │  判定   │     菱形：判断/决策
     └────┬────┘
```

### 序列图元素
```markdown
  对象A              对象B              对象C
     │                  │                  │
     │──请求1──────────►│                  │  → 同步消息
     │                  │                  │
     │◄─响应1──────────│                  │  ← 返回消息
     │                  │                  │
     │                  │──请求2────────────────►│  → 异步消息
```

## 颜色值参考

### Ant Design 色板
```css
/* 主色 */
--color-primary: #1890FF;
--color-primary-dark: #096DD9;
--color-primary-darker: #0050B3;

/* 功能色 */
--color-success: #52C41A;
--color-warning: #FAAD14;
--color-error: #F5222D;
--color-info: #722ED1;

/* 中性色 */
--color-text: #262626;
--color-text-secondary: #595959;
--color-text-disabled: #D9D9D9;
--color-border: #D9D9D9;
--color-bg: #FAFAFA;
```

### 图表配色
```css
--chart-blue: #1890FF;
--chart-green: #52C41A;
--chart-yellow: #FAAD14;
--chart-red: #F5222D;
--chart-purple: #722ED1;
--chart-cyan: #13C2C2;
```

## 字体规范参考

```css
/* 字体族 */
--font-family: 'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif;
--font-family-mono: 'Source Code Pro', 'Courier New', monospace;

/* 字号 */
--font-size-h1: 24px;
--font-size-h2: 20px;
--font-size-h3: 16px;
--font-size-body: 14px;
--font-size-small: 12px;
--font-size-tiny: 10px;

/* 行高 */
--line-height-tight: 1.3;
--line-height-normal: 1.5;
--line-height-loose: 1.8;
```

## 间距规范参考

```css
/* 基础单位：4px */
--space-xs: 4px;   /* 紧凑 */
--space-sm: 8px;   /* 小 */
--space-md: 16px;  /* 标准 */
--space-lg: 24px;  /* 大 */
--space-xl: 32px;  /* 特大 */

/* 组件内边距 */
--padding-sm: 8px;
--padding-md: 16px;
--padding-lg: 24px;

/* 组件间间距 */
--margin-sm: 8px;
--margin-md: 16px;
--margin-lg: 24px;
```

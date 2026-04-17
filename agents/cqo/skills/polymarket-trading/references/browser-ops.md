# Browser操作模板

## 内置Browser (Polymarket专用)

### 启动
```bash
# 已有登录态，无需重复登录
browser action=start profile=openclaw
```

### 导航
```bash
browser action=navigate profile=openclaw targetUrl="https://polymarket.com/portfolio"
browser action=navigate profile=openclaw targetUrl="https://polymarket.com/markets?_c=crypto"
```

### 快照 (省token)
```bash
# 精简快照
browser action=snapshot compact=true maxChars=3000 profile=openclaw

# 完整快照
browser action=snapshot profile=openclaw
```

### JS直接提取
```bash
# 最省token的方式
browser action=act kind=evaluate fn="() => JSON.stringify({...})" profile=openclaw
```

### 点击/输入
```bash
browser action=act kind=click ref=eXX profile=openclaw
browser action=act kind=fill ref=eXX text="1.00" profile=openclaw
```

### 截图
```bash
browser action=screenshot profile=openclaw
```

---

## 交易操作流程

### 1. 查持仓
```bash
browser navigate url="https://polymarket.com/portfolio"
wait 5s
snapshot compact=true
```

### 2. 买入
```bash
# 1. 点击市场
browser act kind=click ref=<market_element>

# 2. 点击输入框
browser act kind=click ref=<input_element>

# 3. 输入金额
browser act kind=fill ref=<input_element> text="5.00"

# 4. 点击Buy
browser act kind=click ref=<buy_button>

# 5. 确认
browser act kind=click ref=<confirm_button>
```

### 3. 卖出
```bash
# 类似买入流程，最后点击Sell
```

---

## 工具选择原则

| 场景 | 工具 | 原因 |
|------|------|------|
| Polymarket交易 | **内置browser** | Web3认证依赖IndexedDB |
| 简单页面抓取 | fast-browser-use | 轻量启动快 |
| 需要cookie认证 | fast-browser-use --load-session | 轻量cookie注入 |
| 需要IndexedDB | 内置browser | 完整profile保持状态 |

---

## 清理
```bash
pkill -f 'chrome.*remote-debugging-port=18800' 2>/dev/null
```

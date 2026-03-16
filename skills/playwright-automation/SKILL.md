---
name: playwright-automation
description: Playwright 浏览器自动化。用于自动化爬虫、数据采集、表单填写、UI 测试等需要浏览器自动化的场景。无需人工干预，适合 cron 定时任务。
allowed-tools: Bash, Exec, Read, Write
---

# Playwright 浏览器自动化

## 概述

Playwright 是一个强大的浏览器自动化工具，可以模拟真实用户操作，支持：
- 无头浏览器模式（后台运行）
- 数据采集和爬虫
- 表单自动填写
- UI 自动化测试
- 截图和 PDF 生成

## 为什么需要 Playwright

### ⚠️ 资源清理原则（强制）

**所有涉及浏览器的 cron 任务完成后，必须自动关闭 Chrome/Chromium 进程！**

```python
# 任务结束时必须执行
import subprocess

# 方式1: 显式关闭浏览器
await browser.close()
await context.close()

# 方式2: 强制清理残留进程（推荐在脚本结束时调用）
subprocess.run(['pkill', '-f', 'chrome'], capture_output=True)
subprocess.run(['pkill', '-f', 'chromium'], capture_output=True)
```

**原因**: 避免内存泄漏和资源占用，防止 Gateway CPU 100% 过载

### 与 browser tool 的区别

| 特性 | browser tool | Playwright |
|------|-------------|-----------|
| 需要用户参与 | ✅ 需要手动打开浏览器 | ❌ 完全自动 |
| 适合定时任务 | ❌ | ✅ |
| 后台运行 | ❌ | ✅ |
| 调试友好 | ✅ 可视化操作 | ⚠️ 需要日志 |
| 无需安装 | ✅ 已集成 | ❌ 需要安装 |

### 使用场景

**使用 Playwright**:
- ✅ 定时监控（cron 任务）
- ✅ 大规模数据采集
- ✅ 无人值守运行
- ✅ 生产环境部署

**使用 browser tool**:
- ✅ 交互式调试
- ✅ 需要人工决策的操作
- ✅ 一次性任务
- ✅ 绕过复杂验证码

## 快速开始

### 1. 安装 Playwright

```bash
# 安装 Python 包
pip install playwright

# 安装浏览器（Chromium）
playwright install chromium

# 验证安装
python3 -c "from playwright.sync_api import sync_playwright; print('✅ 安装成功')"
```

### 2. 基本使用

#### 同步 API（简单任务）

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)  # headless=False 显示浏览器
    page = browser.new_page()
    page.goto('https://example.com')
    print(page.title())
    browser.close()
```

#### 异步 API（推荐，性能更好）

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://example.com')
        title = await page.title()
        print(title)
        await browser.close()

asyncio.run(main())
```

## 常用功能

### 1. 页面导航

```python
# 等待加载完成
await page.goto('https://example.com', wait_until='domcontentloaded')

# 等待选项：
# - 'load' - 页面完全加载
# - 'domcontentloaded' - DOM 加载完成（更快）
# - 'networkidle' - 网络空闲（最慢但最稳）
```

### 2. 元素定位

```python
# CSS 选择器
await page.click('button.submit')
await page.fill('input[name="username"]', 'myuser')

# XPath
await page.click('xpath=//button[@type="submit"]')

# 文本选择器
await page.click('text=登录')

# 组合选择器
await page.click('div.login-form >> text=登录')
```

### 3. 提取数据

```python
# 获取文本
text = await page.text_content('h1.title')

# 获取属性
href = await page.get_attribute('a.link', 'href')

# 获取多个元素
items = await page.query_selector_all('div.item')
for item in items:
    text = await item.text_content()
    print(text)

# 执行 JavaScript
result = await page.evaluate('() => document.title')

# 获取整个 HTML
html = await page.content()
```

### 4. 表单操作

```python
# 填写表单
await page.fill('input[name="username"]', 'myuser')
await page.fill('input[name="password"]', 'mypass')
await page.click('button[type="submit"]')

# 下拉选择
await page.select_option('select#country', 'China')

# 复选框
await page.check('input#agree')

# 上传文件
await page.set_input_files('input[type="file"]', 'path/to/file.pdf')
```

### 5. 等待策略

```python
# 等待元素出现
await page.wait_for_selector('div.result', timeout=5000)

# 等待导航
async with page.expect_navigation():
    await page.click('a.link')

# 等待特定条件
await page.wait_for_function('() => document.title.includes("加载完成")')

# 固定延迟
import asyncio
await asyncio.sleep(2)  # 等待 2 秒
```

### 6. 滚动和交互

```python
# 滚动到页面底部
await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')

# 滚动到元素
await page.locator('div.footer').scroll_into_view_if_needed()

# 鼠标悬停
await page.hover('div.menu')

# 拖拽
await page.drag_and_drop('div.draggable', 'div.dropzone')
```

### 7. 截图和 PDF

```python
# 截图
await page.screenshot(path='screenshot.png')

# 全页截图
await page.screenshot(path='full.png', full_page=True)

# 元素截图
await page.locator('div.content').screenshot(path='element.png')

# 生成 PDF
await page.pdf(path='page.pdf', format='A4')
```

### 8. 处理弹窗

```python
# 接受 alert
async with page.expect_event('dialog') as dialog_info:
    await page.click('button')
dialog = await dialog_info.value
await dialog.accept()

# 输入 prompt
async with page.expect_event('dialog') as dialog_info:
    await page.click('button')
dialog = await dialog_info.value
await dialog.accept('my input')
```

## 反爬策略

### 1. User-Agent 轮换

```python
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
]

browser = await p.chromium.launch(
    user_agent=random.choice(user_agents)
)
```

### 2. 随机延迟

```python
import random
import asyncio

# 在操作之间添加随机延迟
await asyncio.sleep(random.uniform(2, 5))
```

### 3. Cookie 保存和加载

```python
# 第一次登录后保存 Cookie
context = await browser.new_context()
await page.goto('https://example.com/login')
# ... 登录操作 ...
await context.storage_state(path='cookies.json')

# 后续使用保存的 Cookie
context = await browser.new_context(storage_state='cookies.json')
```

### 4. 代理设置

```python
browser = await p.chromium.launch(
    proxy={
        'server': 'http://proxy.example.com:8080',
        'username': 'user',
        'password': 'pass'
    }
)
```

### 5. 浏览器上下文隔离

```python
# 创建独立的上下文（相当于无痕模式）
context = await browser.new_context(
    viewport={'width': 1920, 'height': 1080},
    user_agent='Custom UA',
    locale='zh-CN'
)
page = await context.new_page()
```

## 调试技巧

### 1. 显示浏览器

```python
# 开启有头模式，可以看到操作过程
browser = await p.chromium.launch(headless=False, slow_mo=1000)
# slow_mo=1000 会在每个操作间延迟 1 秒
```

### 2. 截图调试

```python
# 在关键步骤截图
await page.goto('https://example.com')
await page.screenshot(path='step1.png')

await page.click('button')
await page.screenshot(path='step2.png')
```

### 3. 查看日志

```python
# 监听控制台消息
page.on('console', lambda msg: print(f'Console: {msg.text}'))

# 监听网络请求
page.on('request', lambda request: print(f'Request: {request.url}'))
page.on('response', lambda response: print(f'Response: {response.status}'))
```

### 4. Playwright Inspector

```bash
# 启动 Inspector 模式
PWDEBUG=1 python3 your_script.py
```

## 常见问题

### Q: 如何处理验证码？

**A**: 几种方案
1. 使用打码平台（超级鹰、若快打码）
2. 手动处理：暂停等待用户输入
3. 降级：用 browser tool 让用户手动操作

```python
# 方案 2: 手动处理
input("遇到验证码，请在浏览器中完成，然后按回车继续...")
await asyncio.sleep(2)  # 等待验证通过
```

### Q: 元素找不到怎么办？

**A**: 检查以下几点
1. 是否在 iframe 中（需要切换）
2. 是否动态加载（需要等待）
3. 选择器是否正确

```python
# 切换到 iframe
frame = page.frame('iframe-id')
await frame.click('button')

# 等待动态加载
await page.wait_for_selector('div.dynamic-content')
```

### Q: 如何提高性能？

**A**:
1. 使用异步 API
2. 并发多个页面
3. 减少不必要的等待

```python
# 并发多个页面
async def fetch(url):
    page = await browser.new_page()
    await page.goto(url)
    # ...

tasks = [fetch(url) for url in urls]
await asyncio.gather(*tasks)
```

## 与 OpenClaw 集成

### 在 healthcare-monitor 中的使用

```python
# scraper_free.py
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 ..."
    )
    page = await context.new_page()
    await page.goto(url)
    # ... 采集数据 ...
    await browser.close()
```

### 与 browser tool 配合

1. **Playwright** → 日常自动监控
2. **browser tool** → 调试和异常处理

## 资源

- 官方文档: https://playwright.dev/python/
- API 参考: https://playwright.dev/python/docs/api/class-playwright
- 示例代码: `~/clawd/skills/playwright-automation/examples/`

## 快速命令

```bash
# 安装
pip install playwright && playwright install chromium

# 运行脚本
python3 script.py

# 调试模式
PWDEBUG=1 python3 script.py

# 查看版本
playwright --version
```

---

**记住**: Playwright 让你的自动化任务完全无人值守！🚀

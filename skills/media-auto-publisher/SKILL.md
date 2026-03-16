---
name: media-auto-publisher
description: "通用自媒体文章自动发布工具。支持百家号、搜狐号、知乎、微信公众号、小红书、抖音号六个平台的自动化发布流程。使用Playwright自动化实现平台导航和发布，支持通过storageState管理Cookie实现账号切换。"
license: MIT
metadata:
  version: 2.0.0
  domains: [automation, publishing, media, playwright]
  type: automation
---

# 自媒体自动发布

## 支持平台

| 平台 | 代码 | 发布页面 |
|------|------|---------|
| 百家号 | baijiahao | baijiahao.baidu.com |
| 搜狐号 | sohu | mp.sohu.com |
| 知乎 | zhihu | zhuanlan.zhihu.com |
| 微信公众号 | wechat | mp.weixin.qq.com |
| 小红书 | xiaohongshu | creator.xiaohongshu.com |
| 抖音号 | douyin | creator.douyin.com |

## ⚠️ 资源清理原则（强制）

**所有涉及浏览器的发布任务完成后，必须自动关闭 Chrome 进程！**

```python
from playwright.sync_api import sync_playwright

def publish_article():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # ... 执行发布任务 ...

        # ⚠️ 任务结束后必须显式关闭
        context.close()
        browser.close()

    # ⚠️ 强制清理残留进程（推荐）
    import subprocess
    subprocess.run(['pkill', '-f', 'chrome'], capture_output=True)
```

**原因**: 避免内存泄漏和资源占用，防止 Gateway CPU 100% 过载

## 使用方法

```bash
# 查看平台信息
python3 scripts/media_publisher.py info wechat

# 生成发布工作流
python3 scripts/media_publisher.py workflow xiaohongshu

# 快速打开发布页面
python3 scripts/media_publisher.py open douyin

# Cookie 管理
python3 scripts/cookie_manager.py list
python3 scripts/cookie_manager.py add wechat my_account --cookies-file cookies.json
```

## 工作流程

1. 检查并打开指定平台
2. 验证登录状态
3. 自动关闭广告弹窗
4. 导航到发布文章页面
5. 收集发布信息
6. 自动填写并发布

## 触发词

- "发布文章"、"自媒体发布"
- "百家号发布"、"搜狐号发布"、"知乎发布"
- "公众号发布"、"小红书发布"、"抖音发布"
- "一键分发"、"多平台发布"

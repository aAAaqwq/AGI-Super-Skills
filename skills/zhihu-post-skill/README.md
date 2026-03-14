# zhihu-post

> OpenClaw Skill — 用 AI 自动在知乎发帖（专栏文章 + 想法）

## 功能

- 📝 **专栏文章**：填标题 + 正文，自动点发布
- 💭 **想法**：短内容快速发布
- 🔄 **Markdown → HTML**：内置预处理脚本，支持标题/加粗/斜体/链接
- ✅ **字数校验**：想法超 1000 字自动报错

## 原理

通过 **Chrome Browser Relay**（OpenClaw 扩展）接管用户已登录的 Chrome 标签页，AI 直接操控编辑器填写内容并发布。无需 API Key，无需 Cookie 配置，登录态复用用户浏览器。

## 使用前提

1. 安装 [OpenClaw](https://github.com/openclaw/openclaw)
2. 安装 Chrome 的 OpenClaw Browser Relay 扩展
3. 在 Chrome 打开 `https://zhuanlan.zhihu.com/write` 并登录知乎
4. 点击工具栏 Browser Relay 图标 attach 当前 tab

## 文件结构

```
zhihu-post/
├── SKILL.md                    # 技能主文件（发布流程）
├── references/
│   └── dom-selectors.md        # 知乎各页面 DOM 选择器速查
└── scripts/
    └── zhihu_prepare.py        # Markdown 预处理 + 字数校验
```

## 安装

```bash
# 下载 .skill 文件后放入 OpenClaw skills 目录
# 或从 clawhub.com 搜索 zhihu-post 安装
```

## DOM 说明

知乎文章编辑器基于 **Draft.js**（非 ProseMirror），内容需通过 `document.execCommand` 写入：

```javascript
const el = document.querySelector('[contenteditable="true"]');
el.focus();
document.execCommand('selectAll');
document.execCommand('insertText', false, '你的内容');
```

## License

MIT

# 常见问题排查

## ❌ `Invalid API-key provided`

**原因：** 版本与 Key 不匹配。

- 使用了 v1.2.0+ 但传入了硅基流动 key（应为阿里云百炼 key）
- 或 env 变量名错误（v1.1.0 需 `DOUYIN_API_KEY`；v1.2.0+ 需 `DASHSCOPE_API_KEY`）

**排查：**
```bash
# 查看当前配置（mcporter 会加载这两个文件）
python3 << 'EOF'
import json, os
for path in ['~/.cursor/mcp.json', '~/.claude.json']:
    p = os.path.expanduser(path)
    if not os.path.exists(p): continue
    d = json.load(open(p))
    cfg = d.get('mcpServers', {}).get('douyin-mcp')
    if cfg:
        print(f"Found in {path}:", json.dumps(cfg, indent=2, ensure_ascii=False))
EOF
```

确认 args 中的版本号与 env 中的 Key 名称对应。

---

## ❌ `未设置环境变量 DASHSCOPE_API_KEY` 或 `DOUYIN_API_KEY`

**原因：** 调用时未传入对应的环境变量前缀。

**修复：** 在 mcporter call 命令前加对应的环境变量：

```bash
# v1.1.0
DOUYIN_API_KEY="sk-xxx" mcporter call douyin-mcp.extract_douyin_text share_link="..."

# v1.2.0+
DASHSCOPE_API_KEY="sk-xxx" mcporter call douyin-mcp.extract_douyin_text share_link="..."
```

---

## ❌ web_fetch 返回空内容

**原因：** 抖音为纯 JS SPA，web_fetch 只能拿到空 HTML 壳。必须用 `browser` 工具。

---

## ❌ browser snapshot 中找不到视频链接

可能原因：
1. 页面还在加载 → 先截图确认渲染完成，再取 snapshot
2. 弹出登录框遮挡 → 不影响 aria tree，直接读 snapshot 中的 listitem

从 snapshot 中搜索 `/url: /video/` 即可找到视频链接。

---

## ❌ extract_douyin_text 超时或无响应

- 视频较长时提取耗时 60~120s，属正常现象
- 设置 `timeout=180`，`yieldMs=120000`
- 若仍失败，先用 `parse_douyin_video_info` 获取 download_url，确认视频可访问

---

## ❌ mcporter list 中没有 douyin-mcp

**原因：** `~/.cursor/mcp.json` 和 `~/.claude.json` 均未配置 douyin-mcp，或格式有误。

**修复：** 参考 `setup.md` 在任一配置文件中添加 douyin-mcp 配置。

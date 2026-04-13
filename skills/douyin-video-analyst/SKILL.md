---
name: douyin-video-analyst
description: 抖音账号视频批量采集与文案分析工作流。当用户提供抖音账号主页链接、要求抓取最新 N 条视频链接、提取视频文案（语音转文字）、或对视频内容进行总结归纳时，激活此 skill。依赖 browser 工具（抓取视频列表）和 mcporter + douyin-mcp（文案提取）。
---

# Douyin Video Analyst

从抖音账号主页批量采集最新视频链接，通过 douyin-mcp 提取视频语音文案，去除口语化后输出精简原始文案，并进行综合总结。

## 前置依赖

- **browser 工具**：用于渲染抖音 SPA 页面并抓取视频列表（web_fetch 无效，抖音为纯 JS 渲染）
- **mcporter CLI**：`which mcporter` 确认可用
- **douyin-mcp server**：在 `mcporter list` 中应显示 `douyin-mcp (5 tools)`

> mcporter 会自动加载 `~/.cursor/mcp.json` 和 `~/.claude.json` 两个配置文件中的 MCP server。

## 版本与 Key 对照

| 版本 | API 平台 | 环境变量 |
|------|----------|----------|
| ≤ 1.1.0 | 硅基流动 | `DOUYIN_API_KEY` |
| ≥ 1.2.0 | 阿里云百炼 | `DASHSCOPE_API_KEY` |

两个版本均受支持，根据实际配置选择对应环境变量。配置指南见 `references/setup.md`。

## 工作流步骤

### Step 1：检查配置

```bash
# 确认 mcporter 和 douyin-mcp 可用
mcporter list 2>&1 | grep douyin-mcp
```

读取配置文件判断版本和 Key：

```bash
python3 << 'EOF'
import json, os
# mcporter 同时加载这两个配置
for path in ['~/.cursor/mcp.json', '~/.claude.json']:
    p = os.path.expanduser(path)
    if not os.path.exists(p): continue
    d = json.load(open(p))
    cfg = d.get('mcpServers', {}).get('douyin-mcp')
    if cfg:
        print(f"Found in {path}")
        print('  args:', cfg.get('args'))
        print('  env keys:', list(cfg.get('env', {}).keys()))
        break
EOF
```

- env 含 `DOUYIN_API_KEY` → v1.1.0，硅基流动
- env 含 `DASHSCOPE_API_KEY` → v1.2.0+，阿里云百炼

若未配置，参考 `references/setup.md` 完成初始化。

### Step 2：用 browser 抓取视频列表

抖音是纯 JS SPA，**必须用 browser 工具**，不可用 web_fetch。

```
browser(action="open", profile="openclaw", targetUrl="<账号主页URL>")
browser(action="screenshot", ...)   # 等页面渲染，确认视频列表出现
browser(action="snapshot", ...)     # 提取 listitem 中的 /video/XXXX 链接
```

从 snapshot 的 aria tree 中提取 `link[href=/video/XXXXXXXXXXXXXXXXX]`，取前 N 条，拼接完整链接：`https://www.douyin.com/video/<video_id>`

### Step 3：并发提取视频文案

根据 Step 1 检测到的版本，选择对应的环境变量名，**并发**调用所有视频（不要串行等待）：

```bash
# v1.1.0（硅基流动）
DOUYIN_API_KEY="<key>" mcporter call douyin-mcp.extract_douyin_text \
  share_link="https://www.douyin.com/video/<video_id>" 2>&1

# v1.2.0+（阿里云百炼）
DASHSCOPE_API_KEY="<key>" mcporter call douyin-mcp.extract_douyin_text \
  share_link="https://www.douyin.com/video/<video_id>" 2>&1
```

同时发起所有 exec 调用（放在同一个工具调用块中），设置 `timeout=180`，`yieldMs=120000`。

若出现错误，参考 `references/troubleshooting.md`。

### Step 4：整理与输出

按视频顺序（从新到旧）输出，每条视频包含：

1. **视频标题**（来自 snapshot 的 link 文本）
2. **视频链接**
3. **精简文案**：对原始语音文案去除口语化表达（去掉语气词、重复啰嗦、"大家"/"我们"/"你们"等口语填充词），保留核心信息和论点，以书面化段落呈现，不做摘要压缩，完整保留所有要点

最后附综合总结：跨视频归纳主线逻辑、核心主题、一致的风险提示。

## 输出格式参考

```
## 📊 [账号名] 最近 N 条视频文案整理

---

### 视频1 | <标题>
🔗 <链接>

<精简后的书面化文案，完整保留所有要点，去除口语填充>

---

### 视频2 | <标题>
...

---

## 🗂️ 综合总结

| 主线 | 核心逻辑 | 重点方向 |
|------|----------|----------|
| ... | ... | ... |
```

## 注意事项

- 抖音登录弹窗出现时：直接读取 snapshot，视频列表通常仍可在 aria tree 中获取
- 第一条视频可能需要登录才能访问，从第二条起往往正常
- extract_douyin_text 耗时较长（30~90s/条），务必并发执行
- 若文案提取失败，可先用 `parse_douyin_video_info` 获取下载链接，再手动处理

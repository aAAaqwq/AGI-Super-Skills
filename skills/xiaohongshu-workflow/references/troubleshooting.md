# 常见问题解决

## 安装问题

### Q: xiaohongshu-mcp 下载失败

**症状：** wget 下载超时或连接失败

**解决方法：**
```bash
# 方法1: 使用代理
export https_proxy=http://127.0.0.1:7890
wget https://github.com/...

# 方法2: 使用镜像
wget https://ghproxy.com/https://github.com/...

# 方法3: 手动下载
# 从浏览器下载后上传到服务器
```

### Q: 解压后找不到可执行文件

**症状：** tar 解压后目录为空或找不到文件

**解决方法：**
```bash
# 查看压缩包内容
tar -tzf xiaohongshu-mcp-*.tar.gz

# 指定解压目录
mkdir -p ~/.local/bin
tar -xzf xiaohongshu-mcp-*.tar.gz -C ~/.local/bin/
```

### Q: 权限被拒绝

**症状：** `Permission denied` 错误

**解决方法：**
```bash
chmod +x ~/.local/bin/xiaohongshu-mcp
chmod +x ~/.local/bin/xiaohongshu-login
```

---

## 登录问题

### Q: 扫码登录后 cookies 保存在哪？

**症状：** 不知道 cookies 文件位置

**解决方法：**
```bash
# 默认位置（按优先级）
1. 环境变量 $XHS_COOKIES_SRC
2. ~/cookies.json
3. ~/.xiaohongshu/cookies.json

# Windows 登录后复制
cp /mnt/c/Users/<用户名>/AppData/Local/Temp/cookies.json ~/.xiaohongshu/
```

### Q: Cookies 过期怎么办？

**症状：** `登录已过期` 或 `未登录`

**解决方法：**
1. 重新运行 `xiaohongshu-login` 扫码登录
2. 复制新的 cookies 到 `~/.xiaohongshu/cookies.json`
3. 重启 MCP 服务

```bash
# 重启服务
pkill -f xiaohongshu-mcp
xiaohongshu-mcp
```

### Q: 无法打开浏览器扫码

**症状：** 服务器环境没有 GUI

**解决方法：**
1. 在本地电脑（有 GUI）运行 `xiaohongshu-login`
2. 复制 cookies 到服务器
3. 或使用 Windows 版本登录后复制

---

## MCP 服务问题

### Q: 服务启动失败

**症状：** `xiaohongshu-mcp` 命令无响应或报错

**解决方法：**
```bash
# 检查端口是否被占用
lsof -i:18060

# 检查 cookies 文件
ls -la ~/.xiaohongshu/cookies.json

# 查看日志
cat ~/.xiaohongshu/mcp.log

# 前台运行查看错误
xiaohongshu-mcp --headless=false
```

### Q: 服务启动后无法连接

**症状：** curl 请求超时或拒绝连接

**解决方法：**
```bash
# 检查服务是否运行
ps aux | grep xiaohongshu-mcp

# 检查端口监听
netstat -tlnp | grep 18060

# 检查防火墙
sudo ufw status

# 重启服务
pkill -f xiaohongshu-mcp
xiaohongshu-mcp
```

### Q: 浏览器下载失败

**症状：** 首次启动下载 headless 浏览器失败

**解决方法：**
```bash
# 手动安装 Chromium
sudo apt-get install -y chromium-browser

# 或设置代理
export https_proxy=http://127.0.0.1:7890
xiaohongshu-mcp
```

---

## 发布问题

### Q: 发布失败，提示标题过长

**症状：** `标题超过20字符限制`

**解决方法：**
```python
# 缩短标题
title = "新标题"[:20]
```

### Q: 发布失败，提示正文过长

**症状：** `正文超过1000字符限制`

**解决方法：**
```python
# 分段或精简正文
content = content[:1000]
```

### Q: 图片上传失败

**症状：** `图片格式不支持` 或 `图片过大`

**解决方法：**
```bash
# 支持的格式
- JPG/JPEG
- PNG
- WEBP

# 图片大小限制
- 单张 < 20MB
- 总数 < 18张

# 压缩图片
convert input.jpg -quality 85 output.jpg
```

### Q: 发布频率限制

**症状：** `发布过于频繁` 或超过日限制

**解决方法：**
- 每日发布上限：50 条
- 发布间隔：建议 > 5 分钟
- 高峰期限流更严格

---

## 搜索和监控问题

### Q: 搜索无结果

**症状：** 搜索返回空列表

**解决方法：**
```bash
# 检查登录状态
curl -X POST http://localhost:18060/mcp \
  -H "Content-Type: application/json" \
  -d '{"tool": "check_login_status", "params": {}}'

# 尝试不同关键词
# 热门关键词更容易有结果
```

### Q: 获取帖子详情失败

**症状：** `xsec_token 无效` 或 `note_id 不存在`

**解决方法：**
```bash
# xsec_token 有时效性，需要重新搜索获取
# 先搜索获取最新的 token
curl -X POST http://localhost:18060/mcp \
  -H "Content-Type: application/json" \
  -d '{"tool": "search_feeds", "params": {"keyword": "关键词"}}'
```

### Q: 监控脚本执行失败

**症状：** `Permission denied` 或 `command not found`

**解决方法：**
```bash
# 添加执行权限
chmod +x scripts/*.sh

# 检查 shebang
head -1 scripts/*.sh
# 应该是 #!/bin/bash

# 检查 Python 依赖
pip install requests
```

---

## 评论和互动问题

### Q: 评论发送失败

**症状：** `评论内容包含敏感词` 或 `评论频繁`

**解决方法：**
- 检查评论内容是否包含敏感词
- 降低评论频率
- 避免重复发送相同内容

### Q: 无法回复评论

**症状：** `评论不存在` 或 `权限不足`

**解决方法：**
- 确保评论没有被删除
- 检查是否有回复权限
- 刷新帖子详情获取最新评论

---

## 性能问题

### Q: 响应很慢

**症状：** API 响应时间 > 10 秒

**解决方法：**
```bash
# 检查服务器资源
top
free -h
df -h

# 检查网络延迟
ping www.xiaohongshu.com

# 减少并发请求
# 建议间隔 > 2 秒
```

### Q: 内存占用高

**症状：** MCP 服务占用大量内存

**解决方法：**
```bash
# 重启服务
pkill -f xiaohongshu-mcp
xiaohongshu-mcp

# 检查内存
ps aux | grep xiaohongshu-mcp
```

---

## 调试技巧

### 启用详细日志

```bash
# 前台运行，查看详细输出
xiaohongshu-mcp --headless=false

# 查看日志文件
tail -f ~/.xiaohongshu/mcp.log
```

### 测试 API 连接

```bash
# 基础连通测试
curl http://localhost:18060/mcp

# 登录状态测试
curl -X POST http://localhost:18060/mcp \
  -H "Content-Type: application/json" \
  -d '{"tool": "check_login_status", "params": {}}'

# 搜索测试
curl -X POST http://localhost:18060/mcp \
  -H "Content-Type: application/json" \
  -d '{"tool": "search_feeds", "params": {"keyword": "test", "limit": 1}}'
```

### 检查环境

```bash
# 检查 cookies
ls -la ~/.xiaohongshu/
cat ~/.xiaohongshu/cookies.json | python3 -m json.tool

# 检查进程
ps aux | grep xiaohongshu

# 检查端口
netstat -tlnp | grep 18060
lsof -i:18060
```
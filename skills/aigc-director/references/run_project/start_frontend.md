# 启动前端

启动 Next.js 前端服务。

## 检查是否已运行

```bash
# 推荐（检查服务响应）
curl -s http://localhost:3000 > /dev/null 2>&1 && echo "前端运行中" || echo "前端未运行"
```

## 首次启动（需要 build）

```bash
cd aigc-claw/frontend
npm run build
npm start
```

## 后续启动

```bash
cd aigc-claw/frontend
npm start
```

## 验证

```bash
curl http://localhost:3000
```

## 启动后等待

⚠️ **重要**：前端启动需要时间，启动后必须等待 **5 秒** 再访问页面，否则可能出现空白页面。

```bash
sleep 5
# 然后再访问 http://localhost:3000
```

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `command not found: lsof` | lsof 命令不存在 | 使用备用检查方式 `curl http://localhost:3000` |
| `前端未运行` | 服务未启动 | 执行启动命令 |
| `Address already in use` | 端口被占用 | `lsof -ti :3000 \| xargs kill` |
| `npm: command not found` | Node.js 未安装 | 安装 Node.js |
| `Error: Could not find or load config file` | .next 目录损坏 | 删除 .next 目录后重新 `npm run build` |
| 白屏/空白页面 | build 缓存问题 | `rm -rf .next && npm run build` |

## 注意事项

- 前端端口：`3000`
- **必须确保前端运行后才能给用户 Web 界面链接**
- 建议使用生产模式 `npm start`，开发模式可用 `npm run dev`

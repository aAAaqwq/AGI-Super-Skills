# 启动后端

启动 FastAPI 后端服务。

## 检查是否已运行

```bash
# 推荐（检查服务响应）
curl -s http://localhost:8000/api/health && echo "后端运行中" || echo "后端未运行"
```

## 启动命令

```bash
cd aigc-claw/backend
source venv/bin/activate
python api_server.py
```

## 验证

```bash
curl http://localhost:8000/api/health
```

## 启动后等待

⚠️ **重要**：后端启动需要时间，启动后必须等待 **3 秒** 再调用 API，否则可能收到 404 错误。

```bash
sleep 3
# 然后再调用 API
```

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `command not found: lsof` | lsof 命令不存在 | 使用备用检查方式 `curl http://localhost:8000/api/health` |
| `后端未运行` | 服务未启动 | 执行启动命令 |
| `Address already in use` | 端口被占用 | `lsof -ti :8000 \| xargs kill` 或 `pkill -f api_server.py` |
| `ModuleNotFoundError` | 虚拟环境未激活 | 先执行 `source venv/bin/activate` |
| `Connection refused` | 服务未启动或崩溃 | 检查日志 `/tmp/movie-backend.log` |

## 注意事项

- 后端端口：`8000`
- 日志位置：`/tmp/movie-backend.log`
- **必须确保后端运行后才能调用 API**

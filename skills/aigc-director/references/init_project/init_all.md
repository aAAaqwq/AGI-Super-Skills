# 项目初始化

首次下载项目后，需要配置环境并启动前后端服务。

## 使用场景

当用户给出以下指令时使用：
- "初始化项目"
- "配置项目"
- "部署项目"
- "安装项目"
- "开始项目"
- "setup project"
- "deploy"

## 前置检查

```bash
# 检查 Python 版本（需要 3.9+）
python3 --version

# 检查 Node.js 版本（需要 18+）
node --version

# 检查 npm 版本
npm --version
```

## 初始化步骤

### 步骤1：初始化后端

参考 [init_backend.md](init_backend.md)

### 步骤2：初始化前端

参考 [init_frontend.md](init_frontend.md)

### 步骤3：验证服务

```bash
# 检查后端运行
curl http://localhost:8000/api/health

# 检查前端运行
curl http://localhost:3000
```

## 常见问题

| 问题 | 解决方法 |
|------|----------|
| 后端启动失败 | 检查 Python 版本，确保 3.9+，检查 .env 配置 |
| 前端 build 失败 | 删除 node_modules 和 .next，重新 `npm install` |
| 端口被占用 | `lsof -ti :8000 | xargs kill` 或 `lsof -ti :3000 | xargs kill` |
| 依赖安装慢 | 使用国内镜像源 |
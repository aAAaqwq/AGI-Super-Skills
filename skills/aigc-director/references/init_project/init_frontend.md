# 初始化前端

配置并启动 Next.js 前端服务。

## 步骤1：进入前端目录

```bash
cd aigc-claw/frontend
```

## 步骤2：安装依赖（首次）

```bash
npm install
```

> **注意**：如果安装慢，可使用国内镜像：
> ```bash
> npm config set registry https://registry.npmmirror.com
> npm install
> ```

## 步骤3：配置环境变量（可选）

```bash
# 复制配置示例文件
cp .env.local.example .env.local
```

通常无需修改默认配置。

## 步骤4：Build 并启动

```bash
# 首次 build（必须）
npm run build

# 启动服务
npm start
```

## 步骤5：验证

```bash
curl http://localhost:3000
```

返回 HTML 表示成功。

## 后续启动

首次初始化后，后续启动只需：

```bash
cd aigc-claw/frontend
npm start
```

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `npm: command not found` | Node.js 未安装 | 安装 Node.js 18+ |
| `Error: Could not find or load config file` | .next 目录损坏 | `rm -rf .next && npm run build` |
| 白屏/空白页面 | build 缓存问题 | `rm -rf .next && npm run build` |
| `Address already in use` | 端口 3000 被占用 | `lsof -ti :3000 | xargs kill` |
| 依赖安装失败 | 网络问题 | 使用镜像或科学上网 |
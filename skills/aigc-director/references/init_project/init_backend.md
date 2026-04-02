# 初始化后端

配置并启动 FastAPI 后端服务。

## 步骤1：进入后端目录

```bash
cd aigc-claw/backend
```

## 步骤2：创建虚拟环境（首次）

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate
```

## 步骤3：安装依赖

```bash
# 激活虚拟环境后执行
pip install -r requirements.txt
```

> **注意**：如果安装慢，可使用国内镜像：
> ```bash
> pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
> ```

## 步骤4：配置环境变量

```bash
# 复制配置示例文件
cp .env.example .env
```

然后编辑 `.env` 文件，填入必要的 API Key：

| 变量 | 说明 | 获取方式 |
|------|------|----------|
| `DASHSCOPE_API_KEY` | 阿里云 Dashscope API Key（文生图、文生视频） | [阿里云百炼](https://dashscope.console.aliyun.com/) |
| `DEEPSEEK_API_KEY` | DeepSeek API Key（LLM） | [DeepSeek](https://platform.deepseek.com/) |
| `OPENAI_API_KEY` | OpenAI 兼容 API Key | 根据实际部署情况 |

> ⚠️ **重要**：至少需要配置一个 LLM 和一个图片/视频生成 API，否则无法正常使用。

## 步骤5：启动后端

```bash
source venv/bin/activate
python api_server.py
```

## 步骤6：验证

```bash
curl http://localhost:8000/api/health
```

返回 `{"status":"ok"}` 表示成功。

## 常见问题

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `python: command not found` | Python 未安装 | 安装 Python 3.9+ |
| `No module named venv` | python3-venv 未安装 | `brew install python3-venv` (macOS) |
| `ModuleNotFoundError` | 依赖未安装 | `pip install -r requirements.txt` |
| `KeyError: 'DASHSCOPE_API_KEY'` | .env 未配置 | 编辑 .env 填入 API Key |
| `Address already in use` | 端口 8000 被占用 | `lsof -ti :8000 | xargs kill` |
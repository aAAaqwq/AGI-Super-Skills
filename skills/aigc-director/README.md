# 🎬 AIGC-Claw

AI 视频生成全流程系统，通过 6 个阶段将用户想法转化为完整视频。

## 功能特性

- **剧本生成**：输入创意自动生成结构化剧本
- **角色设计**：AI 生成角色设定图（四视图）
- **场景设计**：自动生成场景背景图
- **分镜设计**：智能拆分镜头脚本
- **参考图生成**：为每个镜头生成高精度参考图
- **视频生成**：文生视频 / 图生视频
- **后期剪辑**：自动拼接视频片段，添加转场

## 环境要求

- **Python**: 3.9+
- **Node.js**: 18+
- **npm**: 9+

## 技术栈

- **前端**：Next.js 14 + TypeScript + Tailwind CSS
- **后端**：Python FastAPI
- **AI 模型**：阿里云 DashScope (Qwen)、字节跳动 Seedream、即梦 Jimeng、快手可灵 Kling、DeepSeek、OpenAI、Google Gemini

## 快速开始

### 方式一：手动安装

#### 1. 克隆项目

```bash
git clone https://github.com/hit-cxf/AIGC-Claw.git
cd AIGC-Claw # 完整项目根目录(包括FilmAgent和aigc-director)
```

#### 2. 配置并启动后端

先确保进入完整项目目录 `AIGC-Claw`
此时目录下应当有 `aigc-director` 和 `FilmAgent` 两个子目录

##### 配置后端

```bash
cd aigc-director # skill目录
cd aigc-claw # 项目目录
cd backend # 后端目录

# 创建虚拟环境
python -m venv venv

# 根据操作系统选择启动虚拟环境的命令
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key
# 支持的模型见“配置说明”部分
```

##### 启动后端

```bash
# 根据操作系统选择启动虚拟环境的命令
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate  # Windows

python api_server.py
# 服务运行在 http://localhost:8000
```

终端显示

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

说明启动成功。保持当前终端运行，新建终端以启动前端

#### 3. 配置并启动前端

在新的终端下完成配置
先确保进入完整项目目录 `AIGC-Claw`
此时目录下应当有 `aigc-director` 和 `FilmAgent` 两个子目录

##### 配置前端

```bash
cd aigc-director # skill目录
cd aigc-claw # 项目目录
cd frontend
npm install
# 首次启动或代码变更后需要 build
npm run build
# 启动生产服务（开销小，只需 build 一次）
```

##### 启动前端

```bash
npm start
# 访问 http://localhost:3000
```

---

### 方式二：OpenClaw 自动配置

向openclaw发送消息：

```
帮我克隆git仓库：https://github.com/hit-cxf/AIGC-Claw.git
然后把AIGC-Claw中的aigc-director文件夹递归复制到workspace/skills中，用作AIGC相关的skill
复制完成后，检查aigc-director是否加载到了技能列表中
```

之后使用时，建议在向openclaw发送指令的同时，指明“使用aigc-director”，如：

```
你用aigc-director来帮我生成一个视频，内容是“一条狗的使命”
```

## 项目结构

```
aigc-director/                    # OpenClaw Agent Skill（供 OpenClaw 调用的 AI 视频制作助手）
├── SKILL.md                      # Agent 工作流规则定义
├── CLAUDE.md                     # Claude Code 开发指引
├── README.md                     # 项目说明
├── references/                   # API 参考文档
│   ├── run_project/              # 服务启动指南
│   ├── workflow/                 # 六阶段工作流 API 文档
│   ├── sandbox/                  # 临时工作台 API 文档
│   └── send_message/             # 消息推送集成
└── aigc-claw/                    # 实际代码项目
    ├── backend/                  # Python FastAPI 后端
    │   ├── api_server.py         # API 入口
    │   ├── config.py             # 配置管理
    │   ├── core/
    │   │   ├── orchestrator.py   # 工作流引擎
    │   │   └── agents/           # 6 个阶段 Agent
    │   │       ├── script_agent.py      # 剧本生成
    │   │       ├── character_agent.py  # 角色设计
    │   │       ├── storyboard_agent.py # 分镜设计
    │   │       ├── reference_agent.py  # 参考图生成
    │   │       ├── video_agent.py      # 视频生成
    │   │       └── editor_agent.py     # 后期剪辑
    │   └── tool/                 # 外部 API 客户端
    └── frontend/                 # Next.js 前端
        ├── app/                  # App Router 页面
        ├── components/           # React 组件
        └── config/               # 配置文件
```

> **注意**：整个 AI 视频生成系统代码在 `aigc-claw/` 子目录中，`aigc-director/` 目录是提供给 OpenClaw 平台调用的 Skill 包装。

## 工作流阶段

| 阶段 | Agent | 说明 |
|------|-------|------|
| 1 | 剧本生成 | 将灵感转化为结构化剧本 |
| 2 | 角色设计 | 生成角色设计图和场景背景 |
| 3 | 分镜设计 | 设计镜头语言和分镜脚本 |
| 4 | 参考图生成 | 生成高精度参考图 |
| 5 | 视频生成 | 将参考图转化为视频 |
| 6 | 后期剪辑 | 拼接视频片段为最终成片 |

## 数据存储

### 产物存储位置

所有生成的资产存储在 `aigc-claw/backend/code/result/` 目录下：

| 目录 | 说明 |
|------|------|
| `code/result/image/{session_id}/` | 角色/场景/参考图 |
| `code/result/video/{session_id}/` | 视频片段 |
| `code/result/sandbox/` | 临时工作台生成的文件 |
| `code/result/script/` | LLM 生成的剧本初始数据 |

### 会话数据存储

会话状态和产物元数据存储在 `aigc-claw/backend/code/data/sessions/` 目录下：

- `{session_id}.json` - 包含会话状态、已完成阶段、产物信息等

### 数据读取优先级

1. **会话数据** (`sessions/`) - 用户修改和当前状态（权威数据）
2. **剧本数据** (`result/script/`) - LLM 生成的初始数据

API 返回的资产路径使用相对路径格式：`code/result/...`

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/project/start` | POST | 创建新项目 |
| `/api/project/{session_id}/execute/{stage}` | POST | 执行指定阶段 |
| `/api/project/{session_id}/status` | GET | 获取项目状态 |
| `/api/project/{session_id}/artifact/{stage}` | GET | 获取阶段产物 |
| `/api/project/{session_id}/intervene` | POST | 干预阶段 |
| `/api/project/{session_id}/continue` | POST | 确认并继续 |
| `/api/project/{session_id}/stop` | POST | 停止执行 |
| `/api/sessions` | GET | 获取会话列表 |
| `/api/stages` | GET | 获取阶段列表 |

## 配置说明

### 后端环境变量

主要配置项（详见 `aigc-claw/backend/.env`）：

```bash
# LLM 配置（剧本生成）
LLM_MODEL=qwen3.5-plus

# VLM 配置（图像评估）
VLM_MODEL=qwen-vl-plus

# 图像生成（默认：doubao-seedream-5-0-260128，支持高并发）
IMAGE_T2I_MODEL=doubao-seedream-5-0-260128
IMAGE_IT2I_MODEL=doubao-seedream-5-0-260128

# 视频生成
VIDEO_MODEL=wan2.6-i2v-flash
VIDEO_RATIO=16:9
```

### API Keys 配置

在 `aigc-claw/backend/.env` 中配置各平台 API Key：

| API Key | 提供商 | 可用模型 |
|---------|------|---------|
| `DASHSCOPE_API_KEY` | 阿里云DashScope | qwen3.5-plus, qwen-vl-plus, wan2.6-t2i, wan2.6-i2v-flash |
| `ARK_API_KEY` | 字节跳动Seedream | doubao-seedream-5-0-260128 (500次/分钟，高并发) |
| `VOLC_ACCESS_KEY/SECRET` | 火山引擎即梦 | jimeng_t2i_v40, jimeng_ti2v_v30_pro |
| `KLING_ACCESS_KEY/SECRET` | 快手可灵 | kling-v3, kling-v2-6 |
| `DEEPSEEK_API_KEY` | DeepSeek | deepseek-chat, deepseek-reasoner |
| `OPENAI_API_KEY` | OpenAI | gpt-4o, gpt-5, o3 |
| `GEMINI_API_KEY` | Google Gemini | gemini-2.5-flash, gemini-2.5-flash-image |

### 可用模型

- **LLM 模型**: deepseek-chat, deepseek-reasoner, gpt-4o, gpt-4, gpt-5, o3, gemini-3-flash-preview, qwen3.5-plus, qwen3.5-max
- **VLM 评估模型**: qwen3.5-plus, qwen-vl-plus, qwen3.5-max, gemini-2.5-flash-image (性价比最高), gemini-2.0-flash
- **文生图模型**: doubao-seedream-5-0-260128, jimeng_t2i_v40, wan2.6-t2i, sora_image, gpt-image-1.5
- **图生图模型**: doubao-seedream-5-0-260128, jimeng_t2i_v40, wan2.6-image
- **视频生成模型**: wan2.6-i2v-flash, kling-v3, kling-v2-6, kling-v2-5-turbo
- **视频比例**: 16:9, 9:16, 1:1, 4:3, 3:4, 21:9

### 并发配置

`aigc-claw/backend/config_model.json` 定义了每个模型的并发限制：

```json
{
  "models": {
    "doubao-seedream-5-0-260128": {
      "concurrency": 10,  // 高并发
      "provider": "seedream"
    },
    "wan2.6-i2v-flash": {
      "concurrency": 5,
      "provider": "dashscope"
    }
  }
}
```

修改此文件可调整模型的最大并发数。

#### 图像生成

| 模型 | 调用限制 | 并发数上限 | 备注 |
|------|---------|-----------|------|
| **wan2.6-t2i** | 1次/秒 | 5个 | 文生图 |
| **wan2.6-image** | 5次/秒 | 5个 | 图像生成 |
| **jimeng_t2i_v40** | - | 2-5个 | 即梦系列 |
| **doubao-seedream-*** | 500次/分钟 | 高并发 | 字节跳动Seedream |
| **qwen-image** | 2次/秒 | 同步无限制 | 需开通 |

#### 视频生成

| 模型 | 调用限制 | 并发数上限 | 备注 |
|------|------|------|------|
| **wan2.6-i2v-flash** | 5次/秒 | 5个 | 首帧生视频 |
| **wan2.6-i2v** | 5次/秒 | 5个 | 首帧生视频 |
| **jimeng_ti2v_v30_pro** | 即梦视频，需实测限流 | | |
| **kling-v3/v2-6** | 快手可灵，需查阅官方文档 | | |

#### LLM / VLM

| 模型 | RPM | TPM |
|------|-----|-----|
| **qwen3.5-plus** | 30,000 | 5,000,000 |
| **qwen-plus** | 30,000 | 5,000,000 |
| **qwen-vl-plus** | 1,200 | 1,000,000 |
| **deepseek-chat** | 15,000 | 1,200,000 |

> **RPM**: 每分钟请求数 | **TPM**: 每分钟Token数

## 文档

- [API 文档](./docs/)
- [SKILL.md](./SKILL.md) - OpenClaw Agent 工作流规则
- [CLAUDE.md](./CLAUDE.md) - Claude Code 开发指引

## 许可证

MIT License

# TOOLS.md — CTO (Jensen)

_技术架构 · 仓库技能配置和笔记_

## 仓库 Skills 索引

所有技能路径均相对于本仓库根目录，格式：`../skills/<name>/`

| 技能 | 说明 |
|------|------|
| `../skills/kubernetes-specialist/` | K8s 集群管理、Pod 编排、服务发现 |
| `../skills/docker-essentials/` | Docker 基础容器化（替代 docker-containerization） |
| `../skills/docker-development/` | Docker 开发环境容器化（替代 docker-containerization） |
| `../skills/deployment-automation/` | CI/CD 自动化部署流水线 |
| `../skills/api-provider-status/` | 监控 API 提供商状态 |
| `../skills/model-fallback/` | 模型故障自动降级切换 |
| `../skills/model-provider-manager/` | 多模型提供商管理 |
| `../skills/token-guard/` | Token 用量防护与限制 |
| `../skills/token-reporter/` | Token 消耗报告生成 |
| `../skills/provider-key-manager/` | API Key 轮换与管理 |
| `../skills/inference-optimizer/` | 推理性能优化 |
| `../skills/browser-use/` | 浏览器自动化操作 |
| `../skills/auth-manager/` | 认证与密钥管理 |
| `../skills/browser-profile-guide/` | 浏览器 Profile 配置指南 |
| `../skills/openclaw-workspace-audit/` | Workspace 配置审计 |
| `../skills/github-automation/` | GitHub 工作流自动化 |
| `../skills/sentry-automation/` | Sentry 错误监控自动化 |
| `../skills/render-automation/` | Render 部署自动化 |
| `../skills/vercel-automation/` | Vercel 部署自动化 |
| `../skills/supabase-automation/` | Supabase 数据库自动化 |

## 推荐 Skills 详解

### 基础设施与部署
- **kubernetes-specialist**: K8s 集群管理、Pod 编排、服务发现、Ingress 配置
- **docker-essentials**: Docker 基础容器化（镜像构建、容器运行、Docker Compose）
- **docker-development**: Docker 开发环境容器化（多阶段构建、Dev Containers）
- **deployment-automation**: 自动化部署、CI/CD 流水线、蓝绿发布、回滚策略
- **render-automation**: Render 平台部署管理
- **vercel-automation**: Vercel 平台部署管理
- **supabase-automation**: Supabase 数据库自动化管理

### 模型与推理
- **api-provider-status**: 监控各 AI 模型提供商 API 状态与可用性
- **model-fallback**: 模型故障时自动降级到备用模型
- **model-provider-manager**: 管理多个 AI 模型提供商配置与路由
- **provider-key-manager**: API Key 轮换、过期管理与安全存储
- **token-guard**: Token 用量监控、配额限制与告警
- **token-reporter**: Token 消耗统计报告与成本分析
- **inference-optimizer**: 推理性能优化、批处理、缓存策略

### 浏览器与认证
- **browser-use**: 浏览器自动化操作（页面抓取、表单填写）
- **auth-manager**: 认证机制管理（OAuth、API Keys、Session）
- **browser-profile-guide**: 浏览器 Profile 配置与多账户隔离

### 审计与监控
- **openclaw-workspace-audit**: 工作区配置审计、合规检查
- **github-automation**: GitHub Issues、PR、Actions 工作流自动化
- **sentry-automation**: Sentry 错误跟踪与告警自动化

---

*路径说明：`../skills/<name>/` 表示从 `agents/{id}/` 目录出发，上一级到 agents/，再上一级到仓库根目录下的 skills/ 目录。如仓库根目录为 `/home/aa/clawd/repos/AGI-Super-Team/`，则完整路径为 `/home/aa/clawd/repos/AGI-Super-Team/skills/<name>/`。*

---
name: ragflow-opencaio
description: RAGFlow OpenCAIO 知识库文档上传与管理。当需要将文档上传到鲲界公司 OpenCAIO 知识库、检索知识库内容、或管理 RAGFlow 数据集时使用此 skill。
---

# RAGFlow OpenCAIO 知识库管理

将文档上传到 OpenCAIO 知识库，使用 RAGFlow API 完成上传、解析、检索全流程。

## 配置信息

| 配置项 | 值 |
|--------|-----|
| 服务器地址 | `http://8.134.103.73:12700` |
| API Key | `ragflow-mlZjyQxsDT27bhT6tbONrn0f6dyA-g6hR1jcRqh1lNo` |
| 知识库 ID | `2ccc31fe4f8511f181580bef240bdf9e` |
| 知识库名称 | OpenCAIO |
| 嵌入模型 | text-embedding-v2@Tongyi-Qianwen |
| 对话模型 | deepseek-v4-flash@DeepSeek |
| 分块方法 | naive (512 tokens/chunk) |
| GraphRAG | 开启 |
| RAPTOR | 开启 |
| 语言 | English |

## API 端点速查

| 操作 | 方法 | 端点 |
|------|------|------|
| 知识库状态 | GET | `/api/v1/datasets/2ccc31fe4f8511f181580bef240bdf9e` |
| 上传文档 | POST | `/api/v1/datasets/2ccc31fe4f8511f181580bef240bdf9e/documents` |
| 文档列表 | GET | `/api/v1/datasets/2ccc31fe4f8511f181580bef240bdf9e/documents` |
| 删除文档 | DELETE | `/api/v1/datasets/2ccc31fe4f8511f181580bef240bdf9e/documents` |
| 解析文档 | POST | `/api/v1/datasets/2ccc31fe4f8511f181580bef240bdf9e/chunks` |
| 添加分块 | POST | `/api/v1/datasets/{id}/documents/{doc_id}/chunks` |
| 检索知识 | POST | `/api/v1/retrieval` |
| OpenAI 对话 | POST | `/api/v1/openai/{chat_id}/chat/completions` |
| 创建对话 | POST | `/api/v1/chats` |

### 通用请求头

```
Authorization: Bearer ragflow-mlZjyQxsDT27bhT6tbONrn0f6dyA-g6hR1jcRqh1lNo
Content-Type: application/json  (检索/解析/对话)
Content-Type: multipart/form-data  (上传)
```

---

## 知识库分类体系（强制）

OpenCAIO 知识库采用**路径文件夹**结构，五层顶级目录：

```
skills/     → 技能定义（每个 Skill 一个子文件夹）
agents/     → Agent 配置
company/    → 公司资料
standards/  → 规范与规则
memories/   → 记忆归档
```

### 分类准入规则

**skills/{skill-name}/** — 技能定义，**每个 Skill 一个独立文件夹**
- ✅ 完整 SKILL.md，一个文件夹一个 Skill
- ❌ 混放多个 Skill、使用记录、片段引用
- 命名: `skills/{skill-name}/SKILL.md`

**agents/{agent-name}/** — Agent 配置
- ✅ IDENTITY/SOUL/AGENTS 完整内容、A2A协议、路由规则
- 命名: `agents/{agent-name}/{文档名}_v{版本}.md`

**company/** — 公司资料
- ✅ 产品介绍、商业计划、组织架构
- 命名: `company/{主题}_{日期}.md`

**standards/** — 规范规则
- ✅ 行为规范、代码规范、安全策略
- 命名: `standards/{规范名}_v{版本}.md`

**memories/** — 记忆归档
- 命名: `memories/{主题}_{日期}.md`

### 分类检查清单

上传前必须确认：
1. ✅ 使用路径格式: `{top-folder}/{sub-folder}/文件名.md`
2. ✅ 一个 Skill 一个文件夹（不可混放）
3. ✅ YAML front matter 中 category 字段匹配
4. ✅ 检查是否已存在同名路径（存在则先删后传）

---

## 文档上传标准（强制）

### 1. 文档格式要求

| 标准 | 要求 | 说明 |
|------|------|------|
| **文件格式** | `.md` 优先，支持 `.txt` `.pdf` `.docx` `.html` | Markdown 结构清晰，解析效果最好 |
| **文件名** | `{类别}_{主题}_{日期}.md` | 例: `product_opencaio-intro_2026-05-19.md` |
| **编码** | UTF-8 | 避免中文乱码 |
| **大小** | 单文件 ≤ 10MB | 超大文件拆分上传 |

### 2. 内容质量标准

```
必须满足：
✅ 有明确的标题层级（H1 → H2 → H3）
✅ 每段内容独立完整，可独立理解
✅ 关键术语首次出现时给出定义
✅ 代码块标注语言类型
✅ 无重复内容

禁止上传：
❌ 纯占位符或草稿内容
❌ 大量重复或高度相似的内容
❌ 无结构的长文本（超过 2000 字无标题分段）
❌ 包含敏感信息（密钥、密码、个人隐私）
```

### 3. 元数据标准（可选但推荐）

在 Markdown 文档顶部添加 YAML front matter：

```yaml
---
title: "文档标题"
category: "product|technical|design|business|meeting"
author: "作者"
date: "YYYY-MM-DD"
tags: ["tag1", "tag2"]
version: "1.0"
---
```

### 4. 文档命名规范

| 类别 | 路径格式 | 示例 |
|------|------|------|
| 技能定义 | `skills/{skill-name}/` | `skills/ragflow-opencaio/SKILL.md` |
| Agent配置 | `agents/{agent-name}/` | `agents/protocols/A2A-Protocol_v1.md` |
| 公司资料 | `company/` | `company/OpenCAIO产品介绍_2026-05-19.md` |
| 规范规则 | `standards/` | `standards/taxonomy-rules_v1.1.md` |
| 记忆归档 | `memories/` | `memories/architecture-decision_2026-05-19.md` |

---

## 标准工作流

### Step 1: 准备文档

```
1. 确认文档符合上述内容质量标准
2. 按命名规范重命名文件
3. 检查文件编码为 UTF-8
```

### Step 2: 上传文档

```bash
curl -X POST \
  http://8.134.103.73:12700/api/v1/datasets/2ccc31fe4f8511f181580bef240bdf9e/documents \
  -H "Authorization: Bearer ragflow-mlZjyQxsDT27bhT6tbONrn0f6dyA-g6hR1jcRqh1lNo" \
  -F "file=@/path/to/document.md"
```

成功响应: `{"code": 0, "data": [{...}]}` — 记录返回的 `id` 字段作为 `DOCUMENT_ID`

### Step 3: 解析文档

```bash
curl -X POST \
  http://8.134.103.73:12700/api/v1/datasets/2ccc31fe4f8511f181580bef240bdf9e/chunks \
  -H "Authorization: Bearer ragflow-mlZjyQxsDT27bhT6tbONrn0f6dyA-g6hR1jcRqh1lNo" \
  -H "Content-Type: application/json" \
  -d '{"document_ids": ["DOCUMENT_ID"]}'
```

成功响应: `{"code": 0}`

### Step 4: 验证解析结果

等待 3-10 秒后检查文档状态：

```bash
curl -s \
  http://8.134.103.73:12700/api/v1/datasets/2ccc31fe4f8511f181580bef240bdf9e/documents \
  -H "Authorization: Bearer ragflow-mlZjyQxsDT27bhT6tbONrn0f6dyA-g6hR1jcRqh1lNo" \
  | python3 -c "import sys,json; [print(f'{d[\"name\"]}: run={d[\"run\"]} chunks={d.get(\"chunk_count\",0)}') for d in json.load(sys.stdin)['data']['docs']]"
```

验证标准：
- `run` = `DONE`
- `status` = `1`
- `chunk_count` > 0

### Step 5: 检索验证

```bash
curl -X POST \
  http://8.134.103.73:12700/api/v1/retrieval \
  -H "Authorization: Bearer ragflow-mlZjyQxsDT27bhT6tbONrn0f6dyA-g6hR1jcRqh1lNo" \
  -H "Content-Type: application/json" \
  -d '{"question": "测试查询内容", "dataset_ids": ["2ccc31fe4f8511f181580bef240bdf9e"]}'
```

验证标准：
- 返回 `chunks` 非空
- `similarity` > 0.3
- 内容与查询相关

---

## 批量上传工作流

多文件上传时：

```
1. 扫描目录，过滤出符合标准的文件
2. 逐个上传（间隔 2 秒，避免触发限流）
3. 收集所有 DOCUMENT_ID
4. 一次性提交解析: {"document_ids": ["id1", "id2", ...]}
5. 等待解析完成（轮询检查，间隔 5 秒，最多等 60 秒）
6. 验证所有文档 chunk_count > 0
7. 输出报告: 成功/失败数量、失败文档及原因
```

批量上传脚本模板：

```bash
#!/bin/bash
SERVER="http://8.134.103.73:12700"
KEY="ragflow-mlZjyQxsDT27bhT6tbONrn0f6dyA-g6hR1jcRqh1lNo"
DS="2ccc31fe4f8511f181580bef240bdf9e"
DIR="${1:-.}"

IDS=()
for f in "$DIR"/*.md; do
  [ -f "$f" ] || continue
  echo "📤 $f"
  RESP=$(curl -s -X POST "$SERVER/api/v1/datasets/$DS/documents" \
    -H "Authorization: Bearer $KEY" -F "file=@$f")
  ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null)
  if [ -n "$ID" ]; then
    IDS+=("\"$ID\"")
    echo "  ✅ $ID"
  else
    echo "  ❌ 失败: $RESP"
  fi
  sleep 2
done

if [ ${#IDS[@]} -gt 0 ]; then
  ID_LIST=$(IFS=,; echo "${IDS[*]}")
  echo "🔧 解析 ${#IDS[@]} 个文档..."
  curl -s -X POST "$SERVER/api/v1/datasets/$DS/chunks" \
    -H "Authorization: Bearer $KEY" \
    -H "Content-Type: application/json" \
    -d "{\"document_ids\": [$ID_LIST]}"
fi
```

---

## 检索与对话

### 直接检索（获取原文片段）

```bash
curl -X POST http://8.134.103.73:12700/api/v1/retrieval \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "查询内容", "dataset_ids": ["2ccc31fe4f8511f181580bef240bdf9e"]}'
```

### OpenAI 兼容对话（LLM 总结回答）

```bash
# 1. 创建 Chat Assistant
CHAT_ID=$(curl -s -X POST http://8.134.103.73:12700/api/v1/chats \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Assistant", "dataset_ids": ["2ccc31fe4f8511f181580bef240bdf9e"]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# 2. 对话
curl -X POST "http://8.134.103.73:12700/api/v1/openai/$CHAT_ID/chat/completions" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"model\", \"messages\": [{\"role\": \"user\", \"content\": \"问题\"}], \"stream\": false}"
```

---

## 质量检查清单（每次上传后执行）

```
□ 文档格式符合标准（Markdown / 有标题层级）
□ 文件名遵循命名规范
□ 编码为 UTF-8
□ 上传成功（code=0）
□ 解析完成（run=DONE, status=1）
□ chunk_count > 0
□ 检索验证通过（返回相关结果，similarity > 0.3）
□ 无重复文档（上传前检查是否已存在同名文档）
```

---

## 错误处理

| 错误码 | 含义 | 处理 |
|--------|------|------|
| 401 | API Key 无效 | 检查 API Key 是否正确 |
| 102 | 知识库为空/无分块 | 上传并解析文档 |
| 102 | `content` is required | 手动添加分块时缺少 content 字段 |
| 102 | `document_ids` is required | 解析/删除时缺少 document_ids |
| 400 | 文件格式不支持 | 转换为 .md/.txt/.pdf 格式 |

### 常见问题

**文档解析后 chunk_count = 0**
- 检查文件编码是否为 UTF-8
- 检查文件是否为空
- 检查解析配置中的 delimiter 是否匹配

**检索相似度过低**
- 知识库文档太少，补充更多相关文档
- 查询过于宽泛，换更具体的关键词
- 调整 similarity_threshold（当前 0.2）

---

## 辅助脚本

完整 CLI 工具: `ragflow/opencaio.sh`

```bash
bash ragflow/opencaio.sh status            # 知识库状态
bash ragflow/opencaio.sh upload file.md    # 上传文档
bash ragflow/opencaio.sh list              # 文档列表
bash ragflow/opencaio.sh search "query"    # 检索
bash ragflow/opencaio.sh chat "question"   # AI 对话
```

---

## 执行约束

1. **上传前**必须通过内容质量检查
2. **上传后**必须等待解析完成并验证
3. **批量上传**必须间隔 ≥ 2 秒，避免触发限流
4. **不要上传**包含敏感信息的文档
5. **重复文档**先删除旧版再上传新版
6. **上传失败**立即报告，附错误信息
7. **每次操作后**更新 memory 记录变更

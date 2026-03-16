# Remote Ollama GPU Scheduler

高效调度远程 Ollama GPU 算力进行批量 embedding 的技能。

## 核心问题

**Node.js fetch 不尊重 NO_PROXY**，导致 Tailscale 流量被本地代理拦截：
```bash
# ❌ 这样没用！Node 忽略 NO_PROXY
NO_PROXY=100.0.0.0/8 node -e "fetch('http://100.x.x.x:11434')..."

# ✅ 必须清空全局代理变量
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
# 或用 undici 的 setGlobalDispatcher 绕过
```

## 架构选择

### 方案1: Ollama Remote Backend（稳定但慢）
```
┌─────────┐    Tailscale     ┌────────────┐
│  Linux  │ ───────────────▶ │ Mac Studio │
│  QMD    │   NO_PROXY       │  Ollama    │
│         │   100.0.0.0/8    │  0.6b/8b   │
└─────────┘                  └────────────┘
```

**配置**:
```bash
export QMD_EMBED_BACKEND=ollama
export QMD_OLLAMA_EMBED_URL=http://100.65.110.126:11434
export QMD_OLLAMA_EMBED_MODEL=qwen3-embedding:0.6b  # 或 :8b
```

**性能**:
- 0.6b: ~2.5 chunks/s (1024-dim)
- 8b: ~1.1 chunks/s (4096-dim)
- 73k chunks: 8h (0.6b) / 19h (8b)

### 方案2: llama-server Backend（快但不稳定）⚠️
```
┌─────────┐    Tailscale     ┌────────────┐
│  Linux  │ ───────────────▶ │ Mac Studio │
│  QMD    │   /v1/embeddings │llama-server│
│         │   OpenAI格式     │  Flash Attn│
└─────────┘                  └────────────┘
```

**配置**:
```bash
export QMD_EMBED_BACKEND=llamaserver
export QMD_LLAMASERVER_URL=http://100.65.110.126:8081
export QMD_LLAMASERVER_CONCURRENCY=4
```

**已知问题**:
- llama.cpp b8352 + Qwen3-0.6b embedding 在 parallel>1 时崩溃
- 错误: `GGML_ASSERT(i01 >= 0 && i01 < ne01) failed`
- 临时方案: 用 `--parallel 1` 或换 llama.cpp b8200

## Mac Studio llama-server 启动命令

```bash
# 0.6b 模型路径
MODEL=/Users/daniel/.ollama/models/blobs/sha256-06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439

# 稳定配置（parallel=1）
/tmp/llama/llama-b8352/llama-server \
  -m $MODEL \
  --embedding \
  --port 8081 \
  --host 0.0.0.0 \
  -ngl 99 \
  --parallel 1 \
  -c 4096 \
  -b 512

# 激进配置（可能崩溃）⚠️
/tmp/llama/llama-b8352/llama-server \
  -m $MODEL \
  --embedding \
  --port 8081 \
  --host 0.0.0.0 \
  -ngl 99 \
  --parallel 8 \
  -c 16384 \
  -b 2048
```

## 性能基准（Mac Studio M4 Max）

| 后端 | 模型 | 并行度 | 速度 | 维度 | 稳定性 |
|------|------|--------|------|------|--------|
| Ollama | qwen3:0.6b | 1 | 2.5 c/s | 1024 | ✅ |
| Ollama | qwen3:8b | 1 | 1.1 c/s | 4096 | ✅ |
| llama-server | 0.6b | 1 | ~15 c/s* | 1024 | ⚠️ |
| llama-server | 0.6b | 8 | ~120 c/s* | 1024 | ❌ crash |

*估算值，实际测试中 parallel>1 会崩溃

## QMD Embedding 代码修改

在 `/path/to/qmd/dist/llm.js` 添加 `llamaserver` 后端：

```javascript
// --- llama-server Backend (OpenAI-compatible) ---
const _LLAMASERVER_URL = process.env.QMD_LLAMASERVER_URL || "";
const _LLAMASERVER_CONCURRENCY = parseInt(process.env.QMD_LLAMASERVER_CONCURRENCY || "4", 10);

async function _llamaserverEmbed(text) {
    const url = `${_LLAMASERVER_URL}/v1/embeddings`;
    const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: "qwen3-embedding", input: text }),
        signal: AbortSignal.timeout(300000),
    });
    const data = await resp.json();
    const vec = data?.data?.[0]?.embedding;
    return vec ? { embedding: vec, model: "llamaserver:qwen3" } : null;
}

async function _llamaserverEmbedBatch(texts) {
    const CONC = _LLAMASERVER_CONCURRENCY;
    const subSize = Math.ceil(texts.length / CONC);
    const subBatches = [];
    for (let i = 0; i < texts.length; i += subSize) {
        subBatches.push(texts.slice(i, i + subSize));
    }
    
    const results = await Promise.all(subBatches.map(async (batch) => {
        const resp = await fetch(`${_LLAMASERVER_URL}/v1/embeddings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ model: "qwen3-embedding", input: batch }),
            signal: AbortSignal.timeout(600000),
        });
        const data = await resp.json();
        return (data?.data || []).sort((a,b) => a.index - b.index)
            .map(d => d.embedding ? { embedding: d.embedding, model: "llamaserver:qwen3" } : null);
    }));
    
    return results.flat();
}
```

## 故障排查

### 1. fetch failed / connection refused
```bash
# 检查代理
env | grep -i proxy

# 检查 Tailscale
tailscale status | grep studio

# 测试直连
curl --noproxy "*" http://100.65.110.126:11434/api/tags
```

### 2. embedding 维度不匹配
```
Error: dimension mismatch (expected 4096, got 1024)
```
解决: `qmd embed -f` 强制重建索引

### 3. llama-server 崩溃
```bash
# 查看崩溃日志
tail -20 /tmp/llama-server.log | grep -E 'ASSERT|exception|abort'

# 降级参数
--parallel 1 -c 4096 -b 512
```

## 推荐配置

**稳定优先**: 用 Ollama backend + 0.6b 模型
```bash
export QMD_EMBED_BACKEND=ollama
export QMD_OLLAMA_EMBED_URL=http://100.65.110.126:11434
export QMD_OLLAMA_EMBED_MODEL=qwen3-embedding:0.6b
```

**速度优先**: 等待 llama.cpp 修复后使用 llamaserver backend

---

*创建日期: 2026-03-15*
*适用场景: 批量 embedding、知识库构建、向量搜索*

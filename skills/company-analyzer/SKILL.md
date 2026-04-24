# company-analyzer
> 企业深度分析引擎——多框架 LLM 分析，带缓存、成本追踪、速率限制

## 使用场景
- 对上市公司进行全面分析（基本面、技术面、竞争格局等）
- 多分析框架并行执行（如 SWOT、估值模型、行业分析等）
- 预算控制下的批量公司分析
- 作为 CRO（研究官）的核心分析工具

## 使用方法
```bash
# Shell 库引用方式（在分析脚本中 source）
source ~/clawd/skills/company-analyzer/scripts/lib/api-client.sh
source ~/clawd/skills/company-analyzer/scripts/lib/cache.sh
source ~/clawd/skills/company-analyzer/scripts/lib/cost-tracker.sh

# 调用 LLM 分析
result=$(call_llm_api "分析 AAPL 的竞争优势" 8192)
content=$(extract_content "$result")
prompt_tokens output_tokens=$(extract_usage "$result" "$original_prompt")

# 缓存管理
key=$(cache_key "AAPL" "01-swot" "$prompt")
cached=$(cache_get "$key")   # 返回缓存或空
cache_set "$key" "$response" '{"framework":"swot"}'

# 成本追踪
log_cost "AAPL" "swot" 1500 3000   # 记录 API 调用成本
check_budget                        # 检查是否超预算（默认 $0.10/天）
```

## 核心模块
| 模块 | 文件 | 说明 |
|------|------|------|
| API Client | `scripts/lib/api-client.sh` | 配置驱动的 LLM 客户端，自动读 OpenClaw 配置 |
| Cache | `scripts/lib/cache.sh` | SHA256 键 + 7 天 TTL 持久化缓存 |
| Cost Tracker | `scripts/lib/cost-tracker.sh` | 动态价格查找 + 日预算检查 |
| Trace | `scripts/lib/trace.sh` | 日志追踪 |
| Prices | `scripts/lib/prices.json` | 各模型 token 单价表 |

## 配置要求
- Bash 4+, jq, bc, curl
- OpenClaw 配置：`~/.openclaw/openclaw.json`（模型/提供商/密钥）
- 认证配置：`~/.openclaw/agents/main/agent/auth-profiles.json`
- 默认日预算：$0.10（可修改 `DAILY_BUDGET` 变量）

## 相关文件
- `scripts/lib/api-client.sh` — LLM API 客户端（速率限制、重试、降级）
- `scripts/lib/cache.sh` — 生产级持久化缓存
- `scripts/lib/cost-tracker.sh` — 动态成本追踪
- `scripts/lib/prices.json` — 模型价格表
- `scripts/lib/trace.sh` — 日志工具

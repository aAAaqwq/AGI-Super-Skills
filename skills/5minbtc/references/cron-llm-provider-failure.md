# Cron Job LLM Provider 失效诊断与切换

> 2026-06-21 实战案例 + 操作模板

## 0. 一句话摘要

看到 `RuntimeError: Error code: 401 - Invalid token` ≠ token 失效。最常见的真实根因是 **主 provider 账户欠费 (HTTP 402)**，fallback 链上某个 provider 的 API key 未注入到 environment，最后一个哑弹 provider 才报的 401。

**先看 errors.log 瀑布，再决定行动。**

---

## 1. 故障现象（2026-06-21 实际案例）

3 个 5minbtc 相关 cron job 全部失败：

| Job ID | Name | 表面错误 | 实际错误链 |
|--------|------|----------|-----------|
| `d8058223a1e0` | 5minbtc v5.7 半K线策略 | HTTP 401 (yiyong) | deepseek 402 → minimax-cp key 未注入 → yiyong key 未注入 |
| `3016e27ddefa` | Dreaming 夜间进化 | HTTP 401 (yiyong) | 同上 |
| `9b07cd139f70` | 5minbtc 每日复盘 23:15 | HTTP 401 (yiyong) | 同上 |

`last_error` 字段全部一致：
```
RuntimeError: Error code: 401 - {'error': {'code': '', 'message': 'Invalid token
(request id: 202606211217275441733248268d9d6elLFxYw9)'}}
```

注意 request id 含字母 `lLFxYw9` — 这是 **yiyong provider** 的格式。DeepSeek 的 request id 是纯 25-26 位数字（无字母）。从 request id 即可反推是哪个 provider。

---

## 2. 错误链还原（从 `hermes logs errors` 看到的事实）

```
1. provider=deepseek model=deepseek-v4-pro
   → HTTPError 402: {"error":{"message":"Insufficient Balance","type":"..."}}
   【真因：账户欠费，token 本身有效】

2. Fallback attempt: chain entry deepseek/deepseek-v4-pro matches current provider/model
   → Skip（fallback 短路，无法自我 fallback）

3. provider=minimax-cp model=MiniMax-M3
   → 401: login fail (1004) — request will be sent with placeholder no-key-required
   【key 未注入 environment】

4. provider=yiyong model=gpt-5.4
   → 401: Invalid token (request id: 20260621...268d9d6elLFxYw9)
   【key 未注入 environment】

5. 抛出 RuntimeError (用户看到的 401)
```

---

## 3. 诊断步骤（精确命令）

### 3.1 第一步：看完整错误瀑布

```bash
hermes logs errors -n 30
```

**为什么必须先看这个**：`jobs.json` 的 `last_error` 只记录**最后一跳**的异常。如果只看 last_error 看到 yiyong 的 401，会误以为是 yiyong token 失效，开始去重置 yiyong 的 key——浪费大量时间。

### 3.2 第二步：看 cron 组件日志

```bash
hermes logs --component cron -n 50
```

看每次 job 触发时加载的 provider / credential pool 信息。`credential pool for provider X with N entries` 这一行能告诉你哪些 provider 的 key 实际被读到了。

### 3.3 第三步：识别关键错误模式

| 错误模式 | 真实根因 | 修复方向 |
|----------|----------|----------|
| `HTTPError 402: Insufficient Balance` | 主 provider 欠费 | 充值 或 换 provider |
| `HTTPError 429: 使用上限` | 周/月 token 配额耗尽 | 等待重置时间 或 切备用provider |
| `has no resolvable api_key` | fallback provider 的 env var 未注入 | 检查 `auxiliary_client` 的 `api_key_env` 映射逻辑 |
| `placeholder no-key-required` | 同上，但发生在请求发出时 | 检查 `code path` 里 `auxiliary_client.build()` 的 key 注入分支 |
| `Invalid token (request id 含字母)` | 哑弹 provider 的 401 | 找到主因，绕开这个 provider |
| `Invalid token (request id 纯数字)` | 真实 token 失效/欠费 | 重置或换 |
| `Stream stale 180s / CloudFront` | fallback provider 网络层断连 | 切到网络稳定的 provider（非 CloudFront 后端） |

### 3.4 第四步：独立验证可疑 provider

```bash
# 验证 DEEPSEEK token 本身是否有效（不依赖 hermes）
python3 -c "
import urllib.request, os, json
key = os.environ['DEEPSEEK_API_KEY']
req = urllib.request.Request(
    'https://api.deepseek.com/v1/models',
    headers={'Authorization': f'Bearer {key}'}
)
try:
    r = json.loads(urllib.request.urlopen(req, timeout=15).read())
    print('OK:', [m['id'] for m in r.get('data', [])][:5])
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}:', e.read().decode())
"
# 200 OK = token 有效，问题在余额
# 401 = token 失效
# 402 = 余额不足
```

---

## 4. 切换到替代 Provider（操作模板）

### 4.1 选择替代 provider

当主 provider 欠费时，最快的修复是切换到一个**已验证可用**的备用 provider。

**已知可用 provider 清单（2026-06-21 验证）**：

| Provider | Model | 验证方法 |
|---|---|---|
| `zai` | `glm-5.2` | `GET https://open.bigmodel.cn/api/coding/paas/v4/models` 返回 8 个模型 |

**关键约束**：必须先用上面的独立验证脚本确认 provider 可用，再切。不要假设 fallback 链里的 provider 都可用。

### 4.2 批量更新 cron job

```bash
# 单个更新
hermes cron update --job-id d8058223a1e0 --provider zai --model glm-5.2

# 批量（for 循环）
for jid in d8058223a1e0 3016e27ddefa 9b07cd139f70; do
  hermes cron update --job-id $jid --provider zai --model glm-5.2
done

# 验证修改
python3 -c "
import json
jobs = json.load(open('/home/aa/.hermes/profiles/cqo/cron/jobs.json'))
for j in jobs['jobs']:
    print(f\"{j['id']} {j['name']:30s} provider={j.get('model', {}).get('provider', 'N/A')} model={j.get('model', {}).get('model', 'N/A')}\")
"
```

注意：`hermes cron update` 的 `--model` 参数实际是 `{"provider": "zai", "model": "glm-5.2"}` 的简写（CLI 解析时拼装成 model dict）。如果直接编辑 `jobs.json`，需要写成：

```json
"model": {"provider": "zai", "model": "glm-5.2"}
```

### 4.3 立即验证（不等 schedule）

```bash
hermes cron run --job-id d8058223a1e0
# 5minbtc 全链路约 30-50s（含引擎+新闻+3组搜索+LLM）
# 等待 ~50s 后检查

python3 -c "
import json, time
time.sleep(50)
jobs = json.load(open('/home/aa/.hermes/profiles/cqo/cron/jobs.json'))
for j in jobs['jobs']:
    if j['id'] == 'd8058223a1e0':
        print(f'last_status={j[\"last_status\"]}')
        print(f'last_run_at={j[\"last_run_at\"]}')
        if j.get('last_error'): print(f'last_error: {j[\"last_error\"][:200]}')
"
# 期望输出: last_status=ok
```

如果 `last_status=ok`，说明切换成功。如果仍 `error`，看新的 `last_error`（可能是不同的 provider 失败）。

---

## 5. 后续修复（可选，本次未做）

### 5.1 fallback 链重排

当前 `config.yaml` 的 `fallback_providers` 顺序：
```
1. deepseek-v4-pro （欠费，失效）
2. minimax-cp （key 解析失败）
3. yiyong （key 解析失败）
```

**建议改成**：
```
1. zai/glm-5.2 （已验证可用）
2. deepseek-v4-pro （欠费，备用）
3. minimax-cp / yiyong （key 解析问题未根治，置后）
```

但**不要**仅依赖 fallback 链 — 每个关键 cron job 都应该显式 pin 一个确认可用的 provider/model，避免 fallback 链故障时全盘崩溃。

### 5.2 排查 key 解析 bug

`MINIMAX_CP_API_KEY` 和 `YIYONG_API_KEY` 在 `.env` 里都非空（len=125 / 51），但 `agent.auxiliary_client` 报 `has no resolvable api_key`。**根因**：`config.yaml` 里 `providers.minimax-cp.api_key_env` 可能拼写错误或未定义。检查路径：`/home/aa/.hermes/profiles/cqo/config.yaml` → `providers:` 节。

### 5.3 充值 DeepSeek 账户

DeepSeek token 有效但欠费（HTTP 402）。充值后可以把 fallback 链恢复成 DeepSeek-first（成本最低）。

---

## 6. 经验教训

1. **`last_error` 是最后一跳的异常，不是第一跳的根因** — 看到 401 不一定是 token 失效
2. **fallback 链的每个 provider 都必须独立验证可用** — 不能假设 chain 里某个 provider 工作
3. **provider 账户余额是常见的隐式失败** — 没有预警，只在请求时返回 402
4. **request id 的格式能反推 provider** — 数字 = DeepSeek，字母混合 = yiyong/anthropic 等
5. **每个 cron job 显式 pin provider/model** — 不要依赖全局 fallback 链的默认行为
6. **收到 cron 失败告警，先 `hermes logs errors -n 30` 再行动** — 不要急于重置 token 或重启服务
7. **月末是 provider 限额耗尽的高危窗口** — 每月25日后主动检查余额/额度，不等 cron 静默才发现

---

## 6b. 第三种失效模式：HTTP 429 周/月使用上限 (2026-06-27)

**与 402 (欠费) 和 401 (token失效) 的区别**：

| 错误码 | 含义 | 修复方式 | 恢复时间 |
|--------|------|----------|----------|
| 401 | Token失效/未注入 | 重置token或修复env var | 即时 |
| 402 | 账户欠费 | 充值 | 充值后即时 |
| **429** | **周/月使用上限** | **等待重置或换provider** | **有明确重置时间，不可加速** |

### 6b.1 故障现象

zai provider (glm-5.2) 返回：
```
HTTP 429: 您已达到每周/每月使用上限，您的限额将在 2026-06-28 11:41:02 重置。
```

**关键特征**：错误信息中**直接给出了重置时间**。这意味着不需要任何操作——到时间自动恢复。但如果正好赶上交易日，会丢失一整天的预测数据。

### 6b.2 诊断

```bash
# 在 errors.log 中搜索 429
hermes logs errors -n 30 | grep "429"

# 或直接搜中文关键词
hermes logs errors -n 30 | grep "使用上限"
```

### 6b.3 应对策略

| 策略 | 何时用 | 操作 |
|------|--------|------|
| **等待重置** | 重置时间在数小时内 | 不做任何操作，到时间自动恢复 |
| **切备用provider** | 重置时间>12小时 或 当日有交易窗口 | `hermes cron update --job-id <JID> --provider <ALT> --model <M>` |

**备用provider选择**（当前2026-06-27验证状态）：
- `zai/glm-5.2` — ⚠️ 限额耗尽，06-28 11:41重置
- `deepseek/deepseek-v4-pro` — ⚠️ CloudFront断连（stream stale 180s）
- 需要提前验证备用provider可用，见第4节「已知可用 provider 清单」

### 6b.4 预防

1. **每月25日主动检查**：在cron静默之前发现限额问题
2. **追踪月消耗趋势**：如果本月25日耗尽、上月28日耗尽 → 下月预计24日耗尽
3. **备用provider预验证**：不要等主provider耗尽才去验证备用——提前一个月确认备用可用

---

## 7. 诊断命令速查

```bash
# 看瀑布错误
hermes logs errors -n 30

# 看 cron 组件日志（含 provider 加载记录）
hermes logs --component cron -n 50

# 看所有 cron job 状态
python3 -c "import json; [print(j['id'], j['name'], j.get('last_status','?'), j.get('last_error','')[:100]) for j in json.load(open('/home/aa/.hermes/profiles/cqo/cron/jobs.json'))['jobs']]"

# 看 .env 里某个 key 是否非空
grep -c "ZAI_API_KEY=..*" /home/aa/.hermes/profiles/cqo/.env

# 验证 DeepSeek token 本身是否有效
python3 -c "import urllib.request,json,os; req=urllib.request.Request('https://api.deepseek.com/v1/models',headers={'Authorization':f'Bearer {os.environ[\"DEEPSEEK_API_KEY\"]}'}); print(json.loads(urllib.request.urlopen(req,timeout=15).read()))"

# 验证 zai/glm-5.2 可用
python3 -c "
import urllib.request, json
key = open('/home/aa/.hermes/profiles/cqo/.env').read().split('ZAI_API_KEY=')[1].split(chr(10))[0]
req = urllib.request.Request('https://open.bigmodel.cn/api/coding/paas/v4/models', headers={'Authorization': f'Bearer {key}'})
print([m['id'] for m in json.loads(urllib.request.urlopen(req, timeout=15).read())['data']])
"

# 单个 cron job 切 provider
hermes cron update --job-id <JID> --provider zai --model glm-5.2

# 触发单个 job 立即跑（不等 schedule）
hermes cron run --job-id <JID>
```

---

## 8. 涉及到的 Job 列表

| Job ID | Name | 调度 | 当前 model | 状态 |
|--------|------|------|------------|------|
| `d8058223a1e0` | 5minbtc v5.7 半K线策略 | 每5分钟 | `zai/glm-5.2` | ✅ ok @ 2026-06-21 20:21 |
| `3016e27ddefa` | Dreaming 夜间进化 | 每日 04:25 | `zai/glm-5.2` | 待首次验证 |
| `9b07cd139f70` | 5minbtc 每日复盘 23:15 | 每日 23:15 | `zai/glm-5.2` | 待首次验证 |

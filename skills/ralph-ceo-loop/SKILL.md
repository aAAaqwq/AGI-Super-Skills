# Ralph CEO Loop — GEO Agent 项目交付

持久循环驱动 GEO Agent 项目从开发到部署到验收的完整闭环。

## 触发条件

- "启动ralph"、"ralph循环"、"GEO项目推进"
- "继续开发GEO"、"部署到小m"

## 项目信息

| 项目 | 值 |
|------|------|
| 主仓库 | ~/clawd/geo_agent (GitHub: aAAaqwq/geo_agent, private, main) |
| 参考仓库 | ~/clawd/Auto_GEO_ref (只读) |
| PRD | ~/clawd/geo_agent/docs/PRD.md |
| 产品形态 | OpenClaw Agent/Skill |
| 测试环境 | 小m (Mac Mini M2) via Tailscale |

## 小m Gateway

| 项目 | 值 |
|------|------|
| 域名 | daniellimac-mini.tail0db0a3.ts.net |
| 端口 | 18789 |
| Token | $(pass show api/xiaom-gateway-token) |

## CEO 铁律

1. **CEO 只派任务，不亲自执行** — 不写代码、不跑测试、不 git push
2. **派完立即跳出** — 不等待、不轮询、不监听文件
3. **Agent 汇报到群里后再审核决策**
4. **每轮必须有产出，不允许空转**

## 团队

| Agent | SessionKey | 职责 |
|-------|-----------|------|
| 小pm | agent:pm:telegram:group:-1003890797239 | 任务拆解、质量验收 |
| 小code | agent:code:telegram:group:-1003890797239 | 写代码、修bug |
| 小ops | agent:ops:telegram:group:-1003890797239 | 部署、环境配置 |
| 小research | agent:research:telegram:group:-1003890797239 | 竞品调研方法 |
| 小content | agent:content:telegram:group:-1003890797239 | 文章模板优化 |
| 小market | agent:market:telegram:group:-1003890797239 | SEO策略 |

同时最多派 3 个，sessions_send 不带 timeoutSeconds。

## 完整流程

### Phase 1: 代码开发（当前）
1. 派小code 加固 6 个核心模块（参考 Auto_GEO_ref 业务逻辑）
2. 派小content 优化文章模板
3. 派小pm 写验收标准
4. CEO 审核产出 → 不达标退回 → 达标进入 Phase 2

### Phase 2: 本地测试
1. 派小code 写端到端测试脚本
2. 派小ops 在 Linux 上跑完整流程测试
3. 修复所有 bug → 全部通过进入 Phase 3

### Phase 3: 小m 部署
1. 派小ops 通过 SSH (`ssh mac-mini`) 在小m上：
   - 安装 Python 3.12 + Playwright
   - clone geo_agent 仓库
   - 运行 install.sh
   - 将 skill 注册到小m的 OpenClaw
2. 验证小m的 OpenClaw 能识别 GEO skill

### Phase 4: 跨实例验收测试
1. 通过 Tailscale Gateway 给小m发消息：
```bash
curl -s -X POST "http://daniellimac-mini.tail0db0a3.ts.net:18789/api/message" \
  -H "Authorization: Bearer $(pass show api/xiaom-gateway-token)" \
  -H "Content-Type: application/json" \
  -d '{"message": "帮测试公司做GEO，行业是云计算"}'
```
2. 检验小m上的 Agent 是否：
   - 引导创建项目 ✅
   - 蒸馏关键词 ✅
   - 真实竞品调研 ✅
   - 生成 GEO 文章 ✅
   - 发布到平台（至少一个）✅
   - 收录检测 ✅
   - 项目独立记忆 ✅
3. 不通过 → 回到 Phase 2 修复 → 重新部署

### Phase 5: 交付
1. 所有验收通过
2. 更新 README.md 和文档
3. git push 最终版本
4. 向 Daniel 汇报交付

## 每轮执行模板

```
1. 读取当前状态（git log、文件变化、群里汇报）
2. 审核已完成的任务产出
3. 不达标 → sessions_send 退回给对应 agent
4. 达标 → 确定下一个任务 → sessions_send 派给对应 agent
5. 用 message 发群里汇报进度
6. 跳出，等下一轮触发
```

## 汇报格式

```
🔨 Ralph GEO Agent 进度
📍 Phase X: XXX
✅ 本轮完成: XXX
⏳ 下一步: XXX
🚧 阻塞: XXX（如有）
```

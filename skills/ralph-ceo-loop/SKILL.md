# Ralph CEO 循环 — 项目交付闭环

> CEO 不是执行者，CEO 是调度者。Ralph 循环的本质：持续调度团队，检查反馈，调整方向，直到项目真正能跑。

## 触发条件
用户说"用 Ralph 完成 XXX 项目"、"Ralph 循环"、"持续开发 XXX 直到完成"

## 核心闭环

```
┌─────────────────────────────────────────────┐
│  1. 项目初始化                                │
│  新项目 → 创建 workspace → 初始化 git          │
│  已有项目 → cd 到 workspace → git pull         │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  2. 需求理解                                  │
│  读代码/文档 → 理解项目全貌                     │
│  派小pm 拆解项目 → 获取任务清单+验收标准         │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  3. CEO 审核计划                              │
│  审核小pm的拆解 → 调整优先级 → 确定本轮任务      │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  4. 分配任务给员工                             │
│  根据任务类型派给对应 agent                     │
│  同时最多 3 个 agent 并行                      │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  5. 等待 + 收集反馈（while 循环）              │
│  轮询检查 agent 产出文件                       │
│  有产出 → 收集 → 进入下一步                    │
│  超时 → 重新派活或换 agent                     │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  6. 派小pm 验证质量                            │
│  小pm 检查产出是否达标                         │
│  不达标 → 反馈给执行 agent → 重做              │
│  达标 → 汇报给 CEO                            │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  7. CEO 审核 + 调整                           │
│  审核质量 → git commit + push                  │
│  根据实际情况调整下一轮任务                     │
│  更新状态文件                                  │
│  汇报到群里                                    │
└──────────────────┬──────────────────────────┘
                   ▼
              ┌────┴────┐
              │项目完成？ │
              └────┬────┘
           No ↙      ↘ Yes
          ▼            ▼
     回到步骤4      最终验证
                   端到端测试
                   部署上线
                   汇报完成
```

## 团队调度表

| 成员 | sessionKey | 派活场景 |
|------|-----------|---------|
| 小pm | agent:pm:telegram:group:YOUR_GROUP_CHAT_ID | 项目拆解、任务验收、质量检查 |
| 小code | agent:code:telegram:group:YOUR_GROUP_CHAT_ID | 写代码、修Bug、架构设计 |
| 小ops | agent:ops:telegram:group:YOUR_GROUP_CHAT_ID | 部署、环境、运维 |
| 小research | agent:research:telegram:group:YOUR_GROUP_CHAT_ID | 技术调研、竞品分析 |
| 小data | agent:data:telegram:group:YOUR_GROUP_CHAT_ID | 数据采集、爬虫 |
| 小market | agent:market:telegram:group:YOUR_GROUP_CHAT_ID | SEO、推广策略 |
| 小content | agent:content:telegram:group:YOUR_GROUP_CHAT_ID | 内容生成、文案 |
| 小finance | agent:finance:telegram:group:YOUR_GROUP_CHAT_ID | 成本分析 |
| 小quant | agent:quant:telegram:group:YOUR_GROUP_CHAT_ID | 量化分析 |

## 派活方式
```
sessions_send(sessionKey="agent:<id>:telegram:group:YOUR_GROUP_CHAT_ID", message="【CEO指令】具体任务描述。完成后将结果写入 <指定文件路径>，并用 message 发到群里。")
```
- 不带 timeoutSeconds，派完即走
- 要求 agent 将产出写入指定文件（方便检查）
- 同时最多派 3 个 agent

## 反馈检查方式
不用轮询 sessions_list，直接检查文件：
```bash
# 检查产出文件是否存在且最近更新
stat <产出文件路径> 2>/dev/null && echo "已完成" || echo "未完成"
# 检查文件修改时间
find <目录> -name "*.md" -newer <参考时间文件> -ls
# 检查 git 最新提交
git log --oneline -5
```

## 质量验证流程
1. CEO 初步检查产出文件内容
2. 派小pm 做质量验证：
```
sessions_send(sessionKey="agent:pm:...", message="【质量验证】检查 <文件路径> 的内容质量，对照验收标准 <标准>，给出通过/不通过及修改建议。结果写入 <验证报告路径>。")
```
3. 不通过 → 将修改建议发给原执行 agent → 重做
4. 通过 → git commit + push → 进入下一个任务

## 状态管理
状态文件：`~/clawd/scripts/ralph-project-state.json`
```json
{
  "project": "项目名",
  "workspace": "项目路径",
  "status": "running|paused|completed",
  "currentPhase": "阶段名",
  "tasks": [
    {"id": "1", "name": "任务名", "agent": "code", "status": "pending|dispatched|reviewing|done|failed", "outputFile": "路径", "attempts": 0}
  ],
  "iterations": 0,
  "history": [{"iteration": 1, "action": "xxx", "result": "xxx", "timestamp": "xxx"}]
}
```

## 关键原则
1. **每轮必须有产出** — 不允许空转
2. **失败换方法** — 同一个问题最多重试 3 次，然后换思路
3. **质量优先** — 宁可多迭代几轮，不要交付垃圾
4. **小步快跑** — 每次只做一个小功能，做完验证再做下一个
5. **持续到完成** — 不是跑 N 次就停，是跑到项目真正能用
6. **可以创建 skill** — 发现通用能力就封装成 skill
7. **需要决策问 Daniel** — 不确定的事情发群里问

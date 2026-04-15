# Temporal 深度研究报告

> 研究时间: 2026-03-03 | 编写: 小a

## 一、Temporal 是什么？

**Temporal 是一个持久执行（Durable Execution）平台**，让开发者构建可靠、可扩展的分布式应用，而不牺牲开发效率。

核心理念：**一旦启动，你的应用主函数必定执行到完成**——无论耗时分钟、小时、天、周甚至年。即使进程崩溃、网络故障、服务器宕机，Temporal 也能从上次成功的位置恢复执行。

起源：Temporal 从 **Uber 的 Cadence** 项目 fork 而来，由 Cadence 原始团队创建的 Temporal Technologies 公司开发。

---

## 二、核心概念

### 2.1 Durable Execution（持久执行）

Temporal 的灵魂。传统应用崩溃后状态丢失，需要大量错误恢复代码。Temporal 自动追踪应用执行的每一步，崩溃后从最后成功点无缝恢复。

**类比**：终极自动存档。游戏崩溃不会丢失进度。

### 2.2 Workflow（工作流）

- 你的**业务逻辑**，用代码定义（不是拖拽式低代码）
- **Workflows-as-Code**：用你熟悉的编程语言写，完全控制
- 可以运行数分钟到数年
- 完整运行状态持久化、容错，可从任意点恢复/回放/暂停

```python
# Python 示例 - 订单处理 Workflow
@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, order: Order) -> str:
        # Step 1: 验证库存
        available = await workflow.execute_activity(
            check_inventory, order.item_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Step 2: 扣款（自动重试）
        payment = await workflow.execute_activity(
            charge_payment, order.payment_info,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=5)
        )
        
        # Step 3: 发货
        tracking = await workflow.execute_activity(
            ship_order, order,
            start_to_close_timeout=timedelta(minutes=5)
        )
        
        return f"Order completed: {tracking}"
```

### 2.3 Activity（活动）

- Workflow 中的**单个工作单元**
- 通常涉及与外部世界交互：发邮件、调API、写数据库
- **自动重试**：网络超时、服务中断等瞬态错误自动处理
- 可配置重试策略（次数、间隔、回退）
- 支持心跳（Heartbeat）—— 长时间运行的 Activity 定期报告进度

### 2.4 Worker（工作者）

- **运行你代码**的进程（不是 Temporal Server 运行你的代码！）
- Worker 轮询 Temporal Service 获取任务 → 执行 → 报告结果
- 可水平扩展：几个到数千个 Worker
- Worker 崩溃 → 另一个 Worker 自动接管，通过 Event History 回放恢复状态

### 2.5 Temporal Service（服务端）

- 协调 Workflow 和 Activity 的执行
- 维护完整的 **Event History**（事件历史）
- 持久化到数据库（Cassandra/MySQL/PostgreSQL）
- 部署方式：
  - **自托管**：开源免费，部署在你的基础设施
  - **Temporal Cloud**：全托管 SaaS

### 2.6 Event History（事件历史）

- Workflow 生命周期中所有事件的完整、持久记录
- Workflow 代码不直接执行 Activity，而是发送 Command 给 Temporal Service
- Service 记录 Event → 持久化到数据库
- Worker 崩溃后，通过 **Replay**（回放）Event History 重建 Workflow 状态
- 这就是"确定性执行"的实现机制

---

## 三、架构图

```
┌─────────────────────────────────────────────────┐
│                  你的应用                         │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Workflow  │  │ Activity │  │  Worker  │        │
│  │  代码     │  │  代码     │  │ (轮询+执行)│      │
│  └──────────┘  └──────────┘  └────┬─────┘       │
│                                     │              │
└─────────────────────────────────────┼──────────────┘
                                      │ gRPC (单向出站)
                                      ▼
┌─────────────────────────────────────────────────┐
│             Temporal Service                      │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Frontend │  │ Matching  │  │ History  │        │
│  │ Service  │  │ Service   │  │ Service  │        │
│  └──────────┘  └──────────┘  └──────────┘       │
│                       │                           │
│               ┌───────┴────────┐                  │
│               │   Database     │                  │
│               │ (Cassandra/    │                  │
│               │  PostgreSQL/   │                  │
│               │  MySQL)        │                  │
│               └────────────────┘                  │
└─────────────────────────────────────────────────┘
```

**安全设计**：
- 所有连接从你的应用 → Temporal Service（单向出站），无需开放防火墙
- 数据在你的应用内加密，Temporal Service 不需要访问明文数据

---

## 四、SDK 支持

| 语言 | SDK | 成熟度 |
|------|-----|--------|
| **Go** | ⭐ 最成熟 | 生产级 |
| **Java** | ⭐ 最成熟 | 生产级 |
| **TypeScript** | 成熟 | 生产级 |
| **Python** | 成熟 | 生产级 |
| **PHP** | 可用 | 生产级 |
| **.NET** | 可用 | 生产级 |
| **Ruby** | 较新 | 可用 |

**支持多语言混用（Polyglot）**：不同 Workflow/Activity 可以用不同语言实现。

---

## 五、核心能力详解

### 5.1 确定性执行（Deterministic Execution）

这是你说的"确定性基础设施"的核心：

- Workflow 代码必须是**确定性的**——相同输入永远产生相同 Command 序列
- 这使得 Replay（回放）成为可能：崩溃后，重新执行 Workflow 代码，跳过已完成的步骤
- **限制**：Workflow 代码中不能有随机数、当前时间、线程、I/O 等非确定性操作
- 所有副作用必须放在 Activity 中

```python
# ❌ 错误：Workflow 中使用非确定性操作
@workflow.defn
class BadWorkflow:
    @workflow.run
    async def run(self):
        import random
        if random.random() > 0.5:  # 非确定性！
            ...

# ✅ 正确：使用 Temporal 提供的确定性 API
@workflow.defn
class GoodWorkflow:
    @workflow.run
    async def run(self):
        result = await workflow.execute_activity(
            my_random_activity,  # 随机逻辑放 Activity 里
            start_to_close_timeout=timedelta(seconds=10)
        )
```

### 5.2 Signal & Query & Update

- **Signal**：向运行中的 Workflow 发送消息（异步）
- **Query**：查询 Workflow 当前状态（只读，同步）
- **Update**：向 Workflow 发送请求并等待处理结果（同步）

```python
@workflow.defn
class OrderWorkflow:
    def __init__(self):
        self.status = "pending"
    
    @workflow.signal
    async def cancel(self):
        self.status = "cancelled"
    
    @workflow.query
    def get_status(self) -> str:
        return self.status
```

### 5.3 Child Workflow

- Workflow 可以启动子 Workflow
- 适合：分治复杂流程、隔离故障域、超大 Event History 拆分

### 5.4 Timer & Schedule

- **Durable Timer**：Sleep 几秒到几年，进程崩溃也不丢
- **Schedule**：类似 cron 的定时调度，但有持久性保证

### 5.5 Temporal Nexus

- 跨 Namespace 的 Workflow 调用
- 微服务之间的确定性编排

### 5.6 Versioning

- 支持在不中断运行中 Workflow 的情况下修改 Workflow 代码
- Patching API：条件分支 + 版本标记

---

## 六、典型使用场景

### 6.1 AI Agent 编排 🔥（与我们最相关）

Temporal 官方重点推广的方向：

- **Agent 循环**：LLM 调用 → Tool 调用 → 结果判断 → 继续/结束
- **自动重试**：LLM API 限流、超时自动重试
- **Human-in-the-Loop**：暂停等待人工审批
- **状态管理**：对话历史、Agent 状态自动持久化
- **可观测性**：每一步都可审计、调试

**用户案例**：
- **Replit** — 迁移到 Temporal 编排 Replit Agent 控制层，大规模运行
- **Retool** — 用 Temporal 构建 Retool Agents
- **Gorgias** — "所有 LLM 用例本质都是 workflow"

### 6.2 订单处理 & 支付

- 订单创建 → 库存检查 → 扣款 → 发货 → 通知
- 任一步骤失败自动重试或补偿

### 6.3 用户注册/入职

- 注册 → 邮件验证（等待数天）→ KYC → 开通权限
- 长时间等待用户操作，不浪费资源

### 6.4 基础设施编排

- CI/CD Pipeline
- 云资源 provisioning
- 数据库迁移

### 6.5 金融服务

- 跨行转账（Saga 模式 + 补偿）
- 合规审核流程
- 反洗钱检测

### 6.6 数据管道

- ETL 流程
- 批处理作业
- 文档处理

---

## 七、定价（Temporal Cloud）

| 计划 | 起步价 | Actions | Active Storage | Retained Storage |
|------|--------|---------|----------------|------------------|
| **Essentials** | $100/月 | 1M | 1 GB | 40 GB |
| **Business** | $500/月 | 2.5M | 2.5 GB | 100 GB |
| **Enterprise** | 联系销售 | 10M | 10 GB | 400 GB |

**Actions 梯度价格**：
- 前 5M：$50/百万
- 5-10M：$45/百万
- 10-20M：$40/百万
- 20-50M：$35/百万
- 50-100M：$30/百万
- 100-200M：$25/百万

**Startup Program**：融资 <$30M 的初创公司可获 $6,000 免费额度。

**自托管**：完全免费（开源 MIT License），但需要自己运维。

---

## 八、自托管 vs 云服务

| 维度 | 自托管（开源） | Temporal Cloud |
|------|--------------|----------------|
| 成本 | 免费（+运维人力+基础设施） | $100-$500+/月 |
| 运维 | 自己管数据库、升级、监控 | 全托管 |
| SLA | 自己保证 | 99.9%（Enterprise 99.99%） |
| 规模 | 取决于你的部署 | 测试过 2亿/秒 |
| 安全 | 完全自控 | SOC2/HIPAA 等认证 |
| 适合 | 初创/小团队/敏感数据 | 规模化团队 |

**我的建议**：初期自托管（Docker Compose 即可启动），验证后再考虑是否迁移到 Cloud。

---

## 九、与我们业务的结合点

### 9.1 AI Agent 编排（最高优先级）

当前我们用 OpenClaw 的 cron + sessions_send 编排 9 个 Agent，存在：
- 超时无法恢复
- 状态管理手动（文件 + memory）
- 无法保证执行到完成

**Temporal 方案**：
```python
@workflow.defn
class AgentOrchestration:
    @workflow.run
    async def run(self, task: Task):
        # 1. PM 拆解任务（自动重试）
        plan = await workflow.execute_activity(
            pm_decompose, task,
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # 2. 并行派发给多个 Agent
        results = await asyncio.gather(*[
            workflow.execute_activity(
                dispatch_to_agent, subtask,
                start_to_close_timeout=timedelta(minutes=30)
            )
            for subtask in plan.subtasks[:3]  # 最多3个并行
        ])
        
        # 3. PM 验收
        review = await workflow.execute_activity(
            pm_review, results,
            start_to_close_timeout=timedelta(minutes=10)
        )
        
        if not review.passed:
            # 4. 自动重做（Continue-As-New 避免 Event History 过大）
            return await workflow.execute_activity(
                retry_failed_tasks, review.feedback
            )
        
        # 5. CEO 审核 + Git Push
        await workflow.execute_activity(commit_and_push, results)
```

### 9.2 Polymarket 交易系统

- 市场扫描 → 策略评估 → 下单 → 仓位监控 → 止盈止损
- 每一步都需要确定性保证，不能因为崩溃丢失交易状态

### 9.3 内容工厂

- 热点采集 → 选题评分 → 内容生成 → 审核 → 发布
- 完美的 Workflow 场景

### 9.4 客户交付流程

- 客户签约 → 需求分析 → 项目拆解 → 开发 → 测试 → 交付
- 长周期流程，需要持久化状态

---

## 十、快速上手

### 10.1 安装（本机开发）

```bash
# macOS
brew install temporal
temporal server start-dev

# Linux（Docker）
docker compose up -d  # 使用官方 docker-compose.yml

# 或直接下载 CLI
curl -sSf https://temporal.download/cli.sh | sh
```

### 10.2 Python 快速开始

```bash
pip install temporalio
```

```python
# workflows.py
from temporalio import workflow, activity
from datetime import timedelta

@activity.defn
async def greet(name: str) -> str:
    return f"Hello, {name}!"

@workflow.defn
class GreetingWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            greet, name,
            start_to_close_timeout=timedelta(seconds=10)
        )

# worker.py
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client, task_queue="greeting-queue",
        workflows=[GreetingWorkflow],
        activities=[greet]
    )
    await worker.run()

asyncio.run(main())
```

### 10.3 Web UI

启动后访问 `http://localhost:8233` 查看 Workflow 执行状态。

---

## 十一、与竞品对比

| 维度 | Temporal | Apache Airflow | AWS Step Functions | Prefect |
|------|----------|---------------|-------------------|---------|
| 定位 | 通用持久执行 | 数据管道编排 | 云原生状态机 | 数据工作流 |
| 代码方式 | 纯代码 | DAG 定义 | JSON/ASL | 装饰器 |
| 延迟 | 毫秒级 | 分钟级 | 秒级 | 秒级 |
| 长时间运行 | ✅ 年级别 | ❌ | ⚠️ 有限制 | ⚠️ |
| 多语言 | ✅ 7种 | ❌ Python only | ❌ JSON | ❌ Python |
| 自托管 | ✅ 免费 | ✅ 免费 | ❌ 纯云 | ✅ |
| AI Agent | ✅ 官方重点 | ❌ | ⚠️ 可以 | ⚠️ |
| 确定性执行 | ✅ 核心特性 | ❌ | ⚠️ 部分 | ❌ |

**Temporal 的独特优势**：
1. **真正的确定性执行** — 不是简单的重试，而是完整状态恢复
2. **Workflows-as-Code** — 不是 YAML/JSON/DAG，是真正的代码
3. **毫秒级延迟** — 适合实时业务
4. **多语言支持** — 团队可以用最擅长的语言

---

## 十二、落地建议

### Phase 1: 学习 & PoC（1-2周）
1. 本地安装 Temporal Server (`temporal server start-dev`)
2. 跑通 Python SDK 示例
3. 完成 [Temporal 101 课程](https://learn.temporal.io/courses/temporal_101/)
4. PoC：用 Temporal 改造一个现有 cron 任务（如内容工厂流水线）

### Phase 2: 核心系统迁移（2-4周）
1. Agent 编排系统迁移到 Temporal Workflow
2. Polymarket 交易流程 Temporal 化
3. 自托管 Temporal Server（Docker Compose → K8s）

### Phase 3: 全面应用（持续）
1. 所有新业务流程默认用 Temporal
2. 评估是否迁移到 Temporal Cloud
3. 构建公司级 Temporal 最佳实践

---

## 十三、风险 & 注意事项

1. **学习曲线**：确定性约束需要开发者改变思维，Workflow 中不能有非确定性操作
2. **运维复杂度**：自托管需要管理 Temporal Server + 数据库 + 监控
3. **Event History 增长**：长时间运行的 Workflow 需要用 Continue-As-New 控制大小
4. **调试方式不同**：需要适应 Replay-based 调试
5. **依赖**：核心基础设施引入新依赖，需要充分测试

---

*报告完成。建议 Daniel 先完成 Temporal 101 课程，然后我们一起做一个 PoC。*

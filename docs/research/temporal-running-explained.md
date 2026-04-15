# Temporal Workflow "Running" 状态本质解读

> 写给：CEO/技术决策者 | 2026-03-03

---

## 一、为什么 Workflow 一直 Running？

### 本质：这是 Temporal 的核心设计

**Temporal = Durable Execution（持久执行）**

Workflow 不是"跑完就结束的函数"，而是**可以运行数分钟到数年**的状态机。只要没遇到 `return` 或异常，它就会一直处于 Running 状态——**这是正常行为，不是 Bug**。

```
传统程序：main() → 执行 → 结束
Temporal：Workflow → 持久等待 → 继续执行 → 可能持续数年
```

**Running 不等于"在跑 CPU"**，它可能只是在等待：
- 等待 Activity 完成
- 等待 Timer（`await asyncio.sleep(days=7)`）
- 等待 Signal（人工审批）
- 等待 Worker 上线

---

## 二、Workflow 状态速查

| 状态 | 含义 | 会发生什么 |
|------|------|-----------|
| **Running** | 执行中 | 等待 Activity/Timer/Signal，或正在执行 |
| **Completed** | 已完成 | 遇到 `return`，正常结束 |
| **Failed** | 失败 | 遇到不可重试的错误 |
| **Terminated** | 被终止 | 手动执行 Terminate 命令 |
| **Timed Out** | 超时 | 超过 Execution Timeout 限制 |
| **Cancel Requested** | 取消中 | 收到 Cancel 请求，正在处理 |

---

## 三、什么时候会一直 Running？

### 1. 长生命周期 Workflow（正常）
```python
# 订单流程可能等待用户付款，持续数天
await workflow.wait_condition(lambda: payment_received, timeout=timedelta(days=7))
```

### 2. 等待 Signal（人工审批）
```python
# 等待 CEO 审批，可能数周
await workflow.wait_condition(lambda: self._approved)
```

### 3. 没有 Worker 连接 ⚠️ 最常见原因
**Task Queue 里任务堆积**，但没有 Worker 来消费：
- Workflow 在等待 Activity 执行
- Activity 任务进了 Task Queue
- 没有 Worker 轮询这个 Queue
- 结果：一直 Running，不会超时也不会完成

**解决方案**：启动 Worker 去轮询对应的 Task Queue。

---

## 四、没有 Worker 时会发生什么？

| 情况 | 结果 |
|------|------|
| Workflow 等待 Activity | 任务进 Queue，**无限等待** |
| Activity 超时设置 | **不影响**，超时只在 Worker 开始执行后生效 |
| Workflow Execution Timeout | 超过这个时间才会 Timed Out（默认 10 年）|

**核心认知**：Temporal 的设计哲学是"宁可等待也不丢失"，没有 Worker 时任务会一直等，不会自动失败。

---

## 五、如何正确关闭 Running Workflow？

### 方法 1：Terminate（强制终止）
```bash
# CLI
temporal workflow terminate --workflow-id my-workflow

# 或在 Web UI 点击 "Terminate" 按钮
```
**效果**：立即终止，不执行任何清理逻辑。

### 方法 2：Cancel（优雅取消）
```bash
temporal workflow cancel --workflow-id my-workflow
```
**效果**：Workflow 收到取消请求，可以执行清理逻辑。

### 方法 3：Signal 触发结束
```python
# 发送 Signal 让 Workflow 正常退出
await handle.signal(MyWorkflow.cancel, "Manual stop")
```
**效果**：Workflow 执行完清理后正常 return。

---

## 六、运用好 Temporal 的 5 条核心原则

### 原则 1：Running 是常态，不是问题
- Workflow 设计上就是长生命周期的
- 看到 Running 不要惊慌，先看它在等什么

### 原则 2：Worker 必须在线
- **没有 Worker = 任务堆积 = 一直 Running**
- 确保 Worker 正常轮询 Task Queue
- Web UI → Workers 页面可以查看活跃 Worker

### 原则 3：合理设置 Timeout
- `Execution Timeout`：Workflow 总时限（防止无限运行）
- `Activity Timeout`：单个 Activity 的超时
- 长时间等待用 Signal + Timer，不要无限 wait

### 原则 4：用 Signal 实现 Human-in-the-Loop
- 人工审批 = Workflow 等待 Signal
- 审批通过 → 发 Signal → Workflow 继续
- 超时未审批 → Timer 触发 → 自动处理

### 原则 5：定期清理不需要的 Workflow
- 测试环境定期 Terminate 无用 Workflow
- 设置合理的 Retention Period
- 使用 Search Attribute 过滤查找

---

## 七、快速诊断清单

在 Web UI (http://localhost:8233) 检查：

| 检查项 | 怎么看 | 问题 |
|--------|--------|------|
| Workers 页面 | 有活跃 Worker 吗？ | ❌ 没Worker = 任务堆积 |
| Event History | 卡在哪个 Activity？ | 定位具体等待点 |
| Task Queue | Queue 名称匹配吗？ | Worker 可能监听错了 Queue |
| Pending Activities | 有多少待执行？ | 大量堆积说明 Worker 不足 |

---

## 核心结论

1. **Running 是正常的**，Temporal 设计就是让 Workflow 可以运行很长时间
2. **一直 Running 通常因为没有 Worker**，检查 Worker 是否在线
3. **没有 Worker 时任务不会失败**，只会一直等待
4. **Terminate 可以强制终止**，但建议先理解为什么在 Running
5. **生产环境必须确保 Worker 高可用**，至少 2 个实例

---

*报告完成。有问题随时问 @小research*

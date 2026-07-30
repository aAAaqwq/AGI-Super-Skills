# AGI Super Team 执行契约

## 组织关系

```text
成果目标
└── Team Kit：成员、产物、检查
    └── CEO：唯一公司级协调者
        ├── C-suite / PE：领域负责人
        │   ├── 专属 Skills：方法与工作流
        │   └── 直属 Subagents：窄职责专家
        └── Governor：独立证据门
            └── CEO 综合：保留异议
                └── Human：现实动作最终批准
```

Team 选择角色；角色获得 Skills 和允许调用的 Subagents。Skill 不等于 Agent，Subagent 不自动继承 Manager 的全部 Skills，软链接也不代表组织关系。

## 任务包模板

```markdown
## 负责人
<canonical role / runtime agent ID>

## 目标
<一个可验收成果>

## 输入与证据
- <已有材料、可读取路径、当前一手来源>

## 产物
- <文件、决策、分析或检查结果>

## 边界
- 允许：<读、写、工具、角色>
- 禁止：<发布、付款、凭证、越权委派等>

## 验收
- <可复现检查>

## 回传
- 结论：
- 证据：
- 已执行检查：
- 限制与异议：
- 建议下一步：
```

## CEO 编排记录模板

```markdown
# 编排记录

- Outcome / Team：
- 当前框架与版本：
- 模式：native-tree | lead-flat | sequential-handoff | structural-only
- 连接清单与 receipt：
- 选择角色：
- 未选择角色及原因：
- 并行任务与依赖：
- 实际 Agent / Skill 调用：
- 工作产物：
- Governor 结论：
- 人工批准点：
- 剩余风险、负责人、下一步：
```

## Governor 复核输入

Governor 至少需要看到：原始声明、负责角色的完整产物、测试/来源/日志、已知限制、拟执行现实动作。只给 CEO 摘要会破坏独立性。

Governor 的输出至少包含：通过/有条件通过/拒绝、逐项证据、未解决异议、风险等级、补救条件、是否需要人工批准。

## 模式选择规则

| 条件 | 模式 |
|---|---|
| 框架支持所需深度，Agent ID 与 allowlist 均已验证 | `native-tree` |
| 框架支持多个 Agent，但普通子 Agent 不能继续嵌套或深度不足 | `lead-flat` |
| 无可靠并行、多 Agent 不可用或任务强依赖前序结果 | `sequential-handoff` |
| 仅有文件、蓝图或静态映射，没有真实运行证据 | `structural-only` |

即使模式降级，职责、任务包、独立复核与人工门保持不变；变化的只是运行方式。

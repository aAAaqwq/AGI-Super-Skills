---
name: content-factory-dispatcher
description: "内容工厂调度中心 - 使用 Ralph CEO 循环调度内容团队完成端到端内容生产。触发词：内容工厂流水线、跑内容、调度内容团队、content pipeline"
---

# Content Factory Dispatcher — 内容工厂调度中心

基于 Ralph CEO 循环的内容生产任务调度系统。

## 使用方式

```
【CEO指令】跑一遍内容工厂流水线
【CEO指令】今天的内容主题是 AI 编程
【CEO指令】检查内容团队工作状态
```

## 调度流程

### 1. 热点采集阶段
```
派给小data: 采集今天热点 → 输出热点池
```

### 2. 选题阶段
```
派给小research: 调研热点 → 输出选题建议
派给小content: 评估选题 → 确认内容方向
```

### 3. 内容生成阶段
```
派给小content: 生成初稿 → 输出多版本草稿
```

### 4. 审核阶段
```
派给小pm: 审核草稿 → 质量评分 + 修改建议
```

### 5. 发布阶段
```
派给小market: 制定发布策略
派给小ops: 执行发布
```

## Ralph 循环模式

```python
while not 任务完成:
    # 1. 派活
    派给Agent(任务)
    
    # 2. 等待产出
    等待文件产出
    
    # 3. 质量检查
    if 质量不达标:
        派给小pm反馈 → Agent修改
    else:
        进入下一阶段
```

## Agent 调度映射

| 阶段 | Agent | 工具 |
|------|-------|------|
| 采集 | 小data | content-source-aggregator |
| 调研 | 小research | content-research-writer |
| 创作 | 小content | content-creator |
| 审核 | 小pm | project-management |
| 发布 | 小market | seo |
| 运维 | 小ops | linux-service-triage |

## 输出目录

```
~/clawd/projects/content-factory-agents/output/
├── 2026-03-05/
│   ├── hotpool.json      # 热点池
│   ├── topics.json       # 选题
│   ├── drafts/           # 草稿
│   ├── reviewed/         # 审核后
│   └── published/        # 已发布
```

## 扩展

添加新阶段只需：
1. 在 phases 数组添加阶段定义
2. 对应 Agent skill 已就绪
3. Ralph 循环自动调度

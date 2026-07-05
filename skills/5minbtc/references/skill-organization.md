# Skill 项目文件结构 (5minbtc 整理后模式, 2026-07-05)

> 从 5minbtc skill 整理 (logs/reviews 归档 + SKILL.md 减负) 提炼的可复用模式。
> 适用于任何有运行时产物 + 复盘产出 + 长文档的 skill。

## 核心原则
1. **SKILL.md = INDEX** (~150-200 行) — 触发 + 何时用 + quick-start + 铁律 + 关键规则 + 性能 + references 索引
2. **references/ = 详情** — 每个 ref 一个专题, SKILL.md 用一行 + 链接引用
3. **产出物 = 专用子目录** — 日志/复盘/报告各归各位, 根目录只放源文件

## 推荐目录结构
```
skill-name/
├── SKILL.md                      # INDEX, ~150-200 行
├── *.py                          # 源文件 (与 SKILL.md 同级, 易找)
├── references/                   # 专题详细文档
│   ├── lessons.md                # 教训集
│   ├── pitfalls.md               # 陷阱集
│   ├── changelog.md              # 版本变更
│   ├── architecture.md           # 架构说明
│   ├── execution.md              # 执行步骤
│   ├── review-procedure.md       # 复盘流程
│   ├── cron-setup.md             # Cron/调度配置
│   └── <topic>.md                # 其他专题
├── logs/                         # 运行时日志 (rsync 排除)
│   ├── current.jsonl             # 当前活跃
│   └── <archive>/                # 归档 (按需)
├── reviews/                      # 复盘产出 (按月归档)
│   └── YYYY-MM/
├── backtest/ 或 data/            # 数据/回测产物
├── scripts/                      # 工具脚本
└── reports/                      # 蒸馏报告 (R01-R14 之类)
```

## INDEX 模式 SKILL.md 结构
1. 标题 + 版本号 + 一句话描述
2. 触发词
3. 何时使用 (含边界场景 + 错误用法)
4. 快速开始 (3-5 行命令)
5. 架构 (1 行/组件)
6. 铁律 (3-7 条)
7. 关键规则 (裁决规则, 5-7 条精简)
8. 性能快照 (1 行最新数据)
9. references 索引 (10-25 个, 1 行/项)
10. 文件结构 (树状图)
11. 同步/部署说明 (1-3 行)

## 整理 SOP (发现 SKILL.md > 250 行时触发)
1. 扫描, 找出从未被调用的函数/从未被引用的文件
2. 提取冗长章节 (changelog/lessons/pitfalls/执行步骤) → references/<topic>.md
3. 按月归档 review-*.md 到 reviews/YYYY-MM/
4. 按时间归档 jsonl/gz 到 logs/archive/
5. 删除 __pycache__/ 和明确无用的源文件
6. log.py 等写文件脚本, 加 LOG_DIR = logs/ 子目录, 自动 makedirs
7. 验证: smoke test 每个 .py, 确认 cron 仍可用
8. 更新 SKILL.md 反映新结构 (压缩到 ~150-200 行)
9. 更新 sync procedure 反映新 exclude (加 logs/, reviews/)

## 同步到 git/共享仓库
rsync exclude 必须包含:
- 运行时产物 (data/, __pycache__/)
- 归档产物 (logs/, reviews/)
- 大文件 (*.jsonl, *.gz)
- 密钥 (.env, *credentials*)

## 常见错误
- **保留所有 .py 在根目录** — 引擎/日志/新闻源都进 src/ 会改 cron 路径, 改造成本高。建议根目录保留 .py + scripts/ 工具脚本。
- **SKILL.md 写超过 300 行** — 触发"用户说 SKILL 太长"反弹信号
- **references/ 文件超过 30 个** — 考虑合并相似专题 (如 session-*.md 可合并为 sessions/)
- **忘记在 references 删除时同步更新 SKILL.md 索引** — 链接断了用户找不到

## 验证清单
- [ ] SKILL.md 行数 < 250
- [ ] 根目录只放源文件 (.py) + SKILL.md + 子目录
- [ ] 所有 .py 都有 smoke test
- [ ] references/ 文件命名一致 (kebab-case, 无日期后缀除非是 session)
- [ ] sync procedure 列出所有 exclude

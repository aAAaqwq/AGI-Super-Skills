# Skills 低风险迁移 / 冻结方案（2026-03-25）

## 0. 结论先行

**建议的全局唯一真相源（Global SoT）**：
- **共享/可复用 skills 唯一真相源：`~/.openclaw/skills/`**
- **workspace 私有/强耦合 skills 保留在对应 `workspace-*/skills/`**
- **OpenClaw 自带基线 skills 继续留在 `~/.npm-global/lib/node_modules/openclaw/skills/`，视为上游基础层，不作为日常主编辑面**

换句话说，后续治理采用 **“共享层 + workspace 私有层 + 上游基础层”** 三层模型：
1. **共享层（唯一真相源）**：`~/.openclaw/skills/`
2. **workspace 私有层**：`/home/aa/.openclaw/workspace-<agent>/skills/`
3. **上游基础层**：`~/.npm-global/lib/node_modules/openclaw/skills/`

其中：
- `~/.agents/skills/` **不再作为真相源**，进入**冻结 / 退场**状态。
- Phase 1 **不删目录、不改生产 cron**，只做冻结、盘点、标记、收敛规则。

---

## 1. 当前问题与证据

当前不是“skills 有多个目录”这么简单，而是三类问题叠加：

### 1.1 共享层双写 / 假单源
- 现状存在 `~/.openclaw/skills/` 与 `~/.agents/skills/` 两套共享目录。
- 实测：两边各有 **57** 个 skill。
- 其中共有 **33** 个重名 skill 的 `SKILL.md` 内容完全一致。
- 更关键的是：大量 `~/.openclaw/skills/<name>` 其实是**指向 `~/.agents/skills/<name>` 的 symlink**，造成“看起来在 openclaw，真实内容却在 agents”的**假单源**。

### 1.2 真实重复 / 潜在漂移
- `find-skills` 至少已出现 **duplicate-real**：`~/.openclaw/skills/find-skills` 与 `~/.agents/skills/find-skills` 同名共存，非简单镜像。
- 这类 skill 是最高漂移风险：
  - 同名
  - 可被不同人编辑
  - 很难从表面看出当前运行的是哪一份

### 1.3 workspace 私有技能与共享技能边界不清
- 当前检测到多个 `workspace-*/skills`，例如：
  - `workspace-main`: `polymarket-trading`
  - `workspace-data`: `polymarket-data`
  - `workspace-quant`: `crypto-hunt`、`daily-portfolio`、`position-monitor` 等
  - `workspace-research`: `agent-browser` 等研究/实验技能
  - `workspace-ops`: `openclaw-browser-chain-debug`
- 其中有一部分是明确的 workspace 私有 SOP；也有一部分与共享层重名，如：
  - `workspace-research/skills/agent-browser` 与 `~/.openclaw/skills/agent-browser` 内容一致
  - `workspace-ops/skills/openclaw-browser-chain-debug` 与共享层同名同内容
- 这说明 workspace 层里同时混着：
  - 真正的局部技能
  - 共享技能的副本 / 镜像

### 1.4 运行时与 cron 还在绕过“技能层级”
- 已有盘点显示，部分 cron 直接硬编码 `.../SKILL.md` 路径。
- 这类任务绕过 skill precedence，目录一动就炸。
- 当前高风险点主要在 `workspace-quant/skills/*` 和部分共享 skill 路径硬编码上。
- 同时，运行时 manifest / session prompt 仍大量暴露 `~/.agents/skills/.../SKILL.md`，会持续制造“操作员以为它还是主路径”的认知错误。

---

## 2. 全局唯一真相源建议

### 2.1 建议
**把 `~/.openclaw/skills/` 定义为唯一的共享技能真相源。**

### 2.2 原因
1. **更符合当前系统心智模型**
   - OpenClaw 运行时、工作区、文档命名都以 `.openclaw` 为主轴。
   - 把共享技能收口到 `~/.openclaw/skills/`，比继续保留 `~/.agents/skills/` 更自然。

2. **可在不改外部路径契约的前提下收敛内部实现**
   - 很多现有引用已指向 `~/.openclaw/skills/...`。
   - 即便内部当前仍是 symlink，只要逐步“把壳换成真实目录”，外部路径可以不变，风险最低。

3. **方便把共享层与 workspace 私有层分开**
   - 共享：`~/.openclaw/skills/`
   - 私有：`workspace-*/skills/`
   - 边界清晰，治理容易。

### 2.3 不建议继续把 `~/.agents/skills/` 当主源的原因
- 路径语义老旧，和当前 OpenClaw 体系不一致。
- 已经形成“openclaw 外观 + agents 实体”的混乱结构。
- 运行时暴露 legacy path，会持续误导维护者直接去改老树。

---

## 3. `~/.agents/skills` 的冻结与退场步骤

## 3.1 立即生效：冻结（Freeze）
从现在开始，`~/.agents/skills/` 进入**冻结态**：

### Freeze 规则
1. **禁止新增**共享 skill 到 `~/.agents/skills/`
2. **禁止新文档/新 SOP** 再把 `~/.agents/skills/` 作为主编辑路径
3. **禁止新 cron / 新工作流** 硬编码 `~/.agents/skills/.../SKILL.md`
4. **共享 skill 的新改动默认只允许落到 `~/.openclaw/skills/`**
5. Phase 1 **不删除** `~/.agents/skills/`，只保留为 legacy 只读/兜底来源

### 建议的执行方式（低风险）
- 给 `~/.agents/skills/` 增加显式退场说明文件，例如 `README.freeze.md`，写清楚：
  - 这是 legacy tree
  - 不再接受新增
  - 共享 skill 主编辑路径已迁移到 `~/.openclaw/skills/`
- 在运维文档中明确：**“需要编辑共享 skill，先看 `~/.openclaw/skills/`，不是 `~/.agents/skills/`”**

## 3.2 Phase 2：退场（Retire）前提
`~/.agents/skills/` 的真正退场，需要满足以下前提：

1. **所有 duplicate-symlink skill 已在 `~/.openclaw/skills/` 实体化**
   - 即：把当前指向 `~/.agents/skills/` 的 symlink，逐个替换成 `~/.openclaw/skills/` 下的真实目录
   - 外部路径保持不变

2. **所有 duplicate-real skill 已完成归并决策**
   - 至少先处理 `find-skills`
   - 确认哪一份为准、另一份冻结

3. **所有 agents-only 的共享候选 skill 已完成分流**
   - 可复用的：迁到 `~/.openclaw/skills/`
   - 实际只服务某个工作区/某个 agent 的：迁到对应 workspace 或保留为 legacy 但标注“非共享”

4. **运行时 manifest / session prompt 不再默认暴露 `.agents/skills` 路径**

5. **所有关键 cron / job 已不依赖 `.agents/skills`**
   - 本次禁止改生产 cron，所以这项只做盘点，不执行变更

## 3.3 退场终态（不是本次执行）
最终目标不是“今天删掉 `~/.agents/skills/`”，而是：
- 先冻结
- 再去依赖
- 再只读归档
- 最后才评估是否可彻底移除

---

## 4. `workspace-*/skills` 的保留 / 迁移判据

### 4.1 保留在 workspace 的判据
满足任一条件，**应保留在对应 workspace**：

1. **只服务单一 agent / 单一工作区**
   - 如 quant 专用分析、ops 专用排障 SOP、data 专用采集脚本

2. **被该 workspace 内 cron / job 硬编码引用**
   - 当前尤其是 `workspace-quant/skills/*`
   - 在未重写入口前，不应移动

3. **强依赖本地上下文、数据、脚本、密钥布局**
   - skill 不只是说明文，还耦合本 workspace 下的脚本、配置、相对路径

4. **实验性 / 研究性 / 高频迭代中的技能**
   - 例如 research 工作区中的原型、实验适配器

### 4.2 迁移到 `~/.openclaw/skills/` 的判据
满足全部或大部分条件时，**应迁移为共享 skill**：

1. **跨 agent 可复用**
2. **不依赖单一 workspace 的私有文件树**
3. **不要求单个 workspace 的 cron 强绑定**
4. **已经被多个任务/多个 agent 作为通用能力使用**
5. **可以把附带脚本/文档一起打包成自洽目录**

### 4.3 需要特别处理的两类 workspace skill

#### A. 与共享层重名且内容相同
例如：
- `workspace-research/skills/agent-browser` ↔ `~/.openclaw/skills/agent-browser`
- `workspace-ops/skills/openclaw-browser-chain-debug` ↔ `~/.openclaw/skills/openclaw-browser-chain-debug`

建议：
- 这类优先视为**共享层副本/镜像**
- Phase 1 先标记，不直接删除
- 后续改成：workspace 仅保留引用说明或 thin wrapper，不保留完整副本

#### B. 与共享层重名但将来可能分叉
- 若 workspace 版本未来必须服务局部 SOP，可保留，但必须重命名或加前缀，避免与共享层同名。
- 建议命名：`ops-xxx`、`quant-xxx`、`research-xxx`

---

## 5. Phase 1 可立即执行的低风险动作

本阶段强调：**不删目录、不改生产 cron、不改变外部路径契约**。

### 5.1 立即可做的动作

#### 动作 1：正式宣布目录治理规则
- 输出并存档本方案
- 在 ops 文档中固化三层模型：
  - `~/.openclaw/skills/` = 共享唯一真相源
  - `workspace-*/skills/` = 私有层
  - `~/.agents/skills/` = 冻结 legacy 层

#### 动作 2：冻结 `~/.agents/skills/`
- 增加 freeze 说明文件 / README
- 在维护规范里禁止新增与默认编辑
- 不做删改目录操作

#### 动作 3：建立迁移台账
至少维护三个清单：
1. **duplicate-symlink 清单**
2. **duplicate-real 清单**
3. **workspace 保留/迁移判定清单**

当前已知基础：
- duplicate-symlink：大约 **32+** 项
- duplicate-real：至少 `find-skills`
- workspace 与共享重名：至少 `agent-browser`、`openclaw-browser-chain-debug`

#### 动作 4：给每个 workspace skill 打标签
建议标签字段：
- `scope: shared | workspace-private | experimental`
- `owner: ops | quant | research | main | data`
- `migration: keep | promote-to-shared | freeze | rename`
- `cron_coupled: yes | no`

#### 动作 5：优先确认“可零感切换”的共享 skill 波次
选择第一批可做实体化迁移的 skill：
- 当前位于 `~/.openclaw/skills/<name>`
- 但真实内容来自 `~/.agents/skills/<name>`（symlink）
- 且**没有被生产 cron 直接硬编码依赖其内部 realpath**
- 只要保持外部路径仍是 `~/.openclaw/skills/<name>`，就属于低风险候选

#### 动作 6：单独标记高风险暂缓项
以下先不动：
- `workspace-quant/skills/*` 被 cron 直接引用的 skill
- `btc-5min-scalper` 这类被 cron 直接指向 `~/.openclaw/skills/.../SKILL.md` 的共享 skill
- `find-skills` 这类 duplicate-real skill

---

## 6. 推荐迁移顺序（低风险优先）

### Wave 0：只治理规则，不动运行路径
- 冻结 `~/.agents/skills/`
- 形成台账
- 形成保留/迁移判据
- 标记高风险项

### Wave 1：duplicate-symlink → `~/.openclaw/skills/` 实体化
适用条件：
- 外部访问路径本来就是 `~/.openclaw/skills/<name>`
- 只是在内部 realpath 上落到了 `~/.agents/skills/<name>`
- 无 cron 依赖其“内部真实位置”

做法：
- 复制实体到 `~/.openclaw/skills/<name>.new` 或临时目录验证
- 校验通过后，原地切换成真实目录
- 保留 `~/.agents/skills/<name>` 不删，作为回滚来源

### Wave 2：duplicate-real 归并
- 先做 `find-skills`
- 逐个做 diff、选主、冻结副本
- 必须一项一项处理，不能批量糊过去

### Wave 3：agents-only 共享候选迁移
- 对 `ads`、`ads-agent`、`cli-developer`、`competitive-analysis` 等 agents-only 项做分类
- 只有明确属于“共享能力”的，才迁入 `~/.openclaw/skills/`
- 否则改判为 workspace/agent 私有或 legacy 保留

### Wave 4：workspace 层规范化
- 对与共享重名的 workspace skill 去副本化 / 重命名 / 明确 ownership
- 被 cron 硬编码引用的项最后处理

---

## 7. 验证方案

### 7.1 Phase 1 验证目标
因为本阶段不改生产 cron，所以验证重点不是“业务效果变化”，而是“治理动作没有引入新混乱”。

### 7.2 验证项

#### A. 目录级验证
- `~/.openclaw/skills/` 继续可读
- `~/.agents/skills/` 未被删除、未误改关键内容
- workspace 私有目录不受影响

#### B. 台账一致性验证
- duplicate-symlink / duplicate-real / agents-only / openclaw-only 分类正确
- workspace skill 已完成 keep / migrate / rename / freeze 标注

#### C. 运行时认知验证
- 新文档、新 SOP、新运维说明里不再把 `~/.agents/skills/` 当主路径
- 新增 shared skill 不再落到 `~/.agents/skills/`

#### D. 波次迁移后的逐项验证（供 Phase 2 使用）
对每个迁移的 skill，至少验证：
1. `SKILL.md` 可正常读取
2. 附属文件（README、脚本、模板、_meta.json）完整
3. 相对路径引用仍然成立
4. 使用该 skill 的一次最小调用/最小读取通过
5. 外部路径仍维持原契约（优先保持 `~/.openclaw/skills/<name>` 不变）

### 7.3 验证记录建议
每次处理一个 skill，都记录：
- skill 名称
- 原状态（symlink / duplicate-real / agents-only / workspace-private）
- 迁移后状态
- 验证结果
- 回滚命令 / 回滚步骤
- 操作人 / 时间

---

## 8. 回滚方案

### 8.1 Phase 1 回滚
本次方案本身几乎都是治理动作，回滚非常简单：
- 文档回滚：恢复 freeze 文案或台账即可
- 目录不删除，因此天然可逆

### 8.2 Phase 2 单 skill 回滚模板
若后续某个共享 skill 从 symlink 实体化后出现问题：

1. **恢复 `~/.openclaw/skills/<skill>` 到变更前状态**
   - 若原来是 symlink，就恢复 symlink
   - 若原来是目录，就恢复旧目录快照

2. **保留 `~/.agents/skills/<skill>` 不动**
   - 作为稳定 fallback

3. **若有入口改写，再恢复入口**
   - 但本次 Phase 1 不涉及 cron 变更

4. **回滚后执行最小验证**
   - 读取 `SKILL.md`
   - 核对附属文件
   - 对应任务最小 smoke test

### 8.3 明确禁止的“伪回滚”
- 不要在故障时临时把多个路径再互相 symlink 嵌套
- 不要边回滚边顺手改 cron
- 不要在未记录前提下手工覆盖目录内容

---

## 9. 建议的治理口径

后续对内统一说法建议如下：

> 从 2026-03-25 起，OpenClaw 共享技能的唯一真相源定义为 `~/.openclaw/skills/`。`~/.agents/skills/` 进入冻结/退场状态，仅作为 legacy 保留层；workspace 私有技能继续保留在各自 `workspace-*/skills/`。Phase 1 不删目录、不改生产 cron，只做冻结、盘点、分层和低风险收敛。

---

## 10. 本次可执行结论摘要

### 10.1 可以立刻拍板的事
- **拍板 1：** 共享技能唯一真相源 = `~/.openclaw/skills/`
- **拍板 2：** `~/.agents/skills/` 从即日起冻结，不再新增、不再作为主编辑面
- **拍板 3：** `workspace-*/skills/` 只保留私有/强耦合/cron 绑定/实验型技能
- **拍板 4：** Phase 1 只做治理和台账，不删目录、不改生产 cron

### 10.2 可以立即启动的低风险动作
1. 发布 freeze 规则
2. 给 `~/.agents/skills/` 补 freeze 说明
3. 维护 duplicate / workspace 判定台账
4. 选出第一批可实体化的 duplicate-symlink shared skills
5. 把 `find-skills`、`workspace-quant` cron 耦合 skills、`btc-5min-scalper` 标记为暂缓

### 10.3 不该现在做的事
- 直接删 `~/.agents/skills/`
- 批量搬 `workspace-quant/skills/*`
- 修改生产 cron 指向
- 在未做台账与验证前批量解除 symlink

---

## 附：本方案使用到的现状事实
- `~/.openclaw/skills`：57 skills
- `~/.agents/skills`：57 skills
- 两边重名且 `SKILL.md` 完全一致：33 skills
- `duplicate-real` 已确认至少 1 个：`find-skills`
- workspace 层已确认与共享层重名/重复的至少 2 个：
  - `agent-browser`
  - `openclaw-browser-chain-debug`
- `workspace-quant/skills/*` 存在 cron 硬编码路径依赖，应视为后置迁移对象

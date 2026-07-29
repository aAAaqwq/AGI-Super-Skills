# AGENTS.md — {{PROJECT_NAME}}

> 作用域：本文件适用于 `{{SCOPE_PATH}}`。它是本作用域内 Agent 工作规则的权威入口。

## 项目目标

{{PROJECT_PURPOSE_AND_NON_GOALS}}

## 文档路由

- 面向用户前读取 [IDENTITY.md](IDENTITY.md) 与 [SOUL.md](SOUL.md)。
- 调用项目工具前读取 [TOOLS.md](TOOLS.md)。
- 执行 `{{DOMAIN_TASK}}` 时使用 `skills/{{SKILL_NAME}}/SKILL.md` 中的对应 Skill。
- 架构与当前能力以 `{{AUTHORITATIVE_DOC_PATH}}` 为准。

## 工作规则

1. 修改前读取当前作用域内全部指令，检查工作树并保留用户已有改动。
2. 优先使用 `{{SEARCH_COMMAND}}` 搜索；按项目约定编辑和格式化文件。
3. 只修改本次目标需要的文件，不把诊断请求扩大为实现或发布。
4. 对易变事实、外部文档和高风险结论重新核验，并记录来源。
5. 运行与风险相称的测试；失败时给出真实原因和未完成项。

## 安全与副作用

- 未经明确授权，不执行 `{{EXTERNAL_OR_IRREVERSIBLE_ACTIONS}}`。
- 删除、覆盖或移动前解析精确目标并确认恢复方式。
- 不读取或输出任务无关的密钥、个人数据和生产数据。
- 工具调用成功不等于业务成功；关键写操作必须验证后置状态。

## 验证与完成定义

- 最低检查：`{{FAST_VALIDATION_COMMAND}}`
- 完整检查：`{{FULL_VALIDATION_COMMAND}}`
- 需要真机或人工验收的范围：`{{MANUAL_ACCEPTANCE_SCOPE}}`
- 交付必须说明修改内容、验证证据、已知限制和可执行下一步。

## Git 与交付

- 分支规则：`{{BRANCH_POLICY}}`
- 提交规则：`{{COMMIT_POLICY}}`
- 推送/发布规则：`{{PUSH_RELEASE_AUTHORIZATION}}`
- 禁止破坏用户改动或使用未授权的强制重置。

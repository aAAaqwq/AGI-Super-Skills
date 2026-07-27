# TOOLS.md — {{PROJECT_NAME}} 工具契约

> 本文件记录当前可用工具的事实、前置条件、副作用和验证方式。能力边界以代码、测试和 `{{EVIDENCE_DOC}}` 为准。

## 工具选择顺序

1. 只读检查：{{READ_ONLY_TOOL_ORDER}}
2. 项目内修改：{{EDIT_TOOL_ORDER}}
3. 外部写操作：仅在授权后使用 {{EXTERNAL_WRITE_TOOLS}}

## {{TOOL_NAME}}

| 字段 | 约定 |
|---|---|
| 入口 | `{{COMMAND_OR_API}}` |
| 平台 | {{SUPPORTED_PLATFORM}} |
| 前置条件 | {{PREREQUISITES}} |
| 输入 | {{INPUTS_AND_DEFAULTS}} |
| 读写属性 | {{READ_WRITE_AND_SIDE_EFFECTS}} |
| 成功判据 | {{POSTCONDITION_EVIDENCE}} |
| 失败与回退 | {{FAILURE_CLASSES_AND_FALLBACK}} |
| 安全 | {{CREDENTIAL_PII_APPROVAL_RULES}} |
| 验证基线 | {{SOURCE_COMMIT_VERSION_DATE}} |

### 最小示例

```shell
{{MINIMAL_COMMAND}}
```

## 通用规则

- 不在文档和日志中写入真实密钥、Cookie 或个人数据。
- 区分命令成功、动作成功和业务状态已验证。
- 重试前重新读取状态；写操作保持幂等或有补偿方案。
- 平台、版本、权限或 API 变化后重新验证本文件。

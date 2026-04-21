# MEMORY.md — 小a 长期记忆

_从 main workspace 迁移初始化_

---

*最后更新: 2026-04-13*

## 子任务汇报机制 (2026-04-14 更新)

- 子任务完成后**必须用自己的 bot 身份直接在群里汇报**，不要父 session 转发
- **标准写法**：spawn task 末尾加：
  ```
  完成后必须用 message(action=send, channel=telegram, target=-1003890797239, accountId="对应的accountId", message="汇报内容") 发到群里
  ```
- 这样群里看到的是对应 agent 自己的 bot 头像和名字

### accountId 对照表
| agent | accountId |
|-------|----------|
| main | default |
| CTO | telegram-cto |
| PE | telegram-peo |
| CQO | telegram-cqo |
| CRO | telegram-cro |
| CFO | telegram-cfo |
| CDO | telegram-cdo |
| CCO | telegram-cco |
| CMO | telegram-cmo |
| CLO | telegram-clo |
| CPO | telegram-cpo |
| CSO | telegram-cso |
| COO | telegram-coo |
| batch | (无独立bot，用default) |

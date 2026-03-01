# Model Health Check

检查所有配置的模型供应商连通性和延迟。

## 触发条件

用户发送 `/model-check`、`模型检查`、`model health`、`检查模型`、`供应商状态` 等。

## 执行

```bash
bash ~/clawd/scripts/model-health-check.sh
```

直接运行脚本，将输出原样返回给用户。无需额外处理。

## 超时

脚本总耗时约 20-30 秒（每个供应商最多 15 秒超时）。使用 `timeout: 120` 确保完成。

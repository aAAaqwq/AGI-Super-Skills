# Agent Model Switcher

批量切换所有子 agent 的模型配置。

## 用途

- 批量更换所有子 agent 的 model
- 同步所有 agent 的 models.json 配置
- 查看所有 agent 当前的 model 配置

## 使用方式

### 1. 查看所有 agent 的 model 配置

```bash
python3 ~/clawd/skills/agent-model-switcher/switch_model.py list
```

### 2. 更换所有子 agent 的 model（不包括 main）

```bash
python3 ~/clawd/skills/agent-model-switcher/switch_model.py set zai/glm-5
```

### 3. 更换指定 agent 的 model

```bash
python3 ~/clawd/skills/agent-model-switcher/switch_model.py set zai/glm-5 --agents code,ops,quant
```

### 4. 同步所有 agent 的 models.json（从 main 复制）

```bash
python3 ~/clawd/skills/agent-model-switcher/switch_model.py sync-models
```

### 5. 同步指定 agent 的 models.json

```bash
python3 ~/clawd/skills/agent-model-switcher/switch_model.py sync-models --agents batch,law,xiaotu
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `list` | 列出所有 agent 的 model 配置 |
| `set <model>` | 设置 agent 的 model |
| `sync-models` | 从 main 复制 models.json 到其他 agent |
| `--agents <names>` | 指定要操作的 agent（逗号分隔） |
| `--include-main` | 包括 main agent（默认不包括） |
| `--dry-run` | 只显示将要执行的操作，不实际执行 |

## 常用模型

| 别名 | 完整名称 |
|------|---------|
| glm5 | zai/glm-5 |
| glm47 | zai/glm-4.7 |
| opus46 | xingsuancode/claude-opus-4-6 |
| sonnet46 | xingsuancode/claude-sonnet-4-6 |
| kimi | moonshot/kimi-k2.5 |

## 示例

```bash
# 查看当前配置
python3 ~/clawd/skills/agent-model-switcher/switch_model.py list

# 全部子 agent 切换到 glm-5
python3 ~/clawd/skills/agent-model-switcher/switch_model.py set glm5

# 只切换 code 和 quant 到 opus-4-6
python3 ~/clawd/skills/agent-model-switcher/switch_model.py set opus46 --agents code,quant

# 同步 models.json 配置
python3 ~/clawd/skills/agent-model-switcher/switch_model.py sync-models
```

## 注意事项

1. 修改配置后，agent 需要重新启动或等待新 session 才能生效
2. 同步 models.json 会覆盖目标 agent 的 models.json，确保 main 的配置是最新的
3. 建议先用 `--dry-run` 查看将要执行的操作

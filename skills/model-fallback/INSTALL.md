# 模型自动降级 Skill 安装指南

## 📦 已安装的文件

### 核心文件
```
~/.openclaw/agents/main/agent/agent.json                          # 主配置文件
~/.openclaw/scripts/model-fallback.sh                             # 切换脚本
~/.openclaw/scripts/monitor-models.sh                            # 监控脚本
```

### Skill 文件
```
~/clawd/skills/model-fallback/SKILL.md                            # Skill 文档
~/clawd/skills/model-fallback/README.md                           # 使用指南
~/clawd/skills/model-fallback/scripts/auto-switch-handler.sh      # 自动错误处理
~/clawd/skills/model-fallback/scripts/model-error-wrapper.sh      # 请求包装器
~/clawd/skills/model-fallback/tests/test-error-handling.sh        # 测试脚本
```

### 支持文件
```
~/clawd/scripts/test-model-fallback.sh                           # 集成测试
~/clawd/docs/model-fallback-strategy.md                           # 技术文档
```

## ✅ 安装验证

运行以下命令验证安装：

```bash
# 检查配置文件
ls -l ~/.openclaw/agents/main/agent/agent.json

# 检查脚本权限
ls -l ~/.openclaw/scripts/model-fallback.sh
ls -l ~/.openclaw/scripts/monitor-models.sh
ls -l ~/clawd/skills/model-fallback/scripts/*.sh

# 检查 skill 文件
ls -l ~/clawd/skills/model-fallback/SKILL.md
```

## 🚀 快速启动

### 1. 验证配置

```bash
cat ~/.openclaw/agents/main/agent/agent.json | python3 -m json.tool
```

### 2. 运行测试

```bash
~/clawd/scripts/test-model-fallback.sh
```

### 3. 启动监控

```bash
~/.openclaw/scripts/monitor-models.sh start
```

### 4. 验证状态

```bash
~/.openclaw/scripts/monitor-models.sh status
```

## 📝 下一步

1. **阅读文档**: `~/clawd/skills/model-fallback/README.md`
2. **配置优化**: 根据需求调整 `agent.json`
3. **测试验证**: 运行测试脚本验证功能
4. **启动监控**: 启动后台监控
5. **定期维护**: 每周检查日志和状态

## 🔧 故障排除

如果遇到问题，请查看：

```bash
# 查看日志
tail -f ~/.openclaw/logs/model-fallback.log

# 检查配置
cat ~/.openclaw/agents/main/agent/agent.json

# 手动测试
~/.openclaw/scripts/model-fallback.sh
```

## 📞 获取帮助

- 查看文档：`~/clawd/skills/model-fallback/README.md`
- 运行测试：`~/clawd/scripts/test-model-fallback.sh`
- 查看日志：`~/.openclaw/logs/`

---

安装完成！祝使用愉快！ 🎉

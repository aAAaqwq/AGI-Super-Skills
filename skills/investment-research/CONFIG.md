# 配置说明（Configuration Guide）

## 工具配置

本技能需要配置以下工具才能正常工作：

### 1. qveris-official（推荐）

**类型**: 主数据源

**用途**:
- 股价历史数据
- 财务报表（资产负债表、利润表、现金流量表）
- 专业财经数据
- 一致预期数据

**配置步骤**:

1. 获取 qveris API Key
   - 访问 qveris 官网注册账号
   - 在开发者控制台获取 API Key

2. 在 OpenClaw 配置中添加工具
   ```json
   {
     "tools": {
       "entries": {
         "qveris-official": {
           "enabled": true,
           "apiKey": {
             "source": "env",
             "provider": "default",
             "id": "QVERIS_API_KEY"
           }
         }
       }
     }
   }
   ```

3. 设置环境变量
   ```bash
   export QVERIS_API_KEY="your-api-key-here"
   ```

### 2. tavily-search（备用）

**类型**: 辅助数据源

**用途**:
- 公司基本信息查询
- 公告和新闻检索
- 补充数据交叉验证

**配置步骤**:

1. 获取 Tavily API Key
   - 访问 Tavily 官网注册
   - 获取 API Key

2. 在 OpenClaw 配置中添加工具
   ```json
   {
     "tools": {
       "entries": {
         "tavily-search": {
           "enabled": true,
           "apiKey": {
             "source": "env",
             "provider": "default",
             "id": "TAVILY_API_KEY"
           }
         }
       }
     }
   }
   ```

3. 设置环境变量
   ```bash
   export TAVILY_API_KEY="your-api-key-here"
   ```

## 数据源优先级

1. **首选**: qveris-official（结构化数据、专业财经数据）
2. **备用**: tavily-search（网页信息、新闻公告）

## 配置验证

配置完成后，可以通过以下方式验证：

```bash
# 检查环境变量
echo $QVERIS_API_KEY
echo $TAVILY_API_KEY

# 测试技能
clawhub inspect investment-research
```

## 常见问题

### Q: 如何确认工具已正确配置？
A: 在 OpenClaw 中执行 `clawhub list` 查看已安装的技能和工具，确保工具状态为 "enabled"。

### Q: 数据获取失败怎么办？
A: 
1. 检查 API Key 是否有效
2. 确认网络连接正常
3. 查看 qveris/Tavily 服务状态
4. 尝试使用备用数据源

### Q: 可以只配置一个数据源吗？
A: 可以，但建议至少配置 qveris-official 以获得最佳体验。tavily-search 作为备用数据源用于交叉验证。

## 高级配置

### 自定义数据源

如果需要使用其他数据源（如 Yahoo Finance、Alpha Vantage 等），可以在 OpenClaw 配置中添加自定义工具：

```json
{
  "tools": {
    "entries": {
      "custom-finance-api": {
        "enabled": true,
        "apiKey": {
          "source": "env",
          "provider": "default",
          "id": "CUSTOM_API_KEY"
        },
        "config": {
          "endpoint": "https://api.example.com",
          "rateLimit": 100
        }
      }
    }
  }
}
```

### 数据缓存配置

为提高性能，建议配置数据缓存：

```json
{
  "skills": {
    "entries": {
      "investment-research": {
        "enabled": true,
        "config": {
          "cacheEnabled": true,
          "cacheTTL": 3600
        }
      }
    }
  }
}
```

## 安全建议

1. **不要提交 API Key**: 确保 `.env` 文件在 `.gitignore` 中
2. **使用环境变量**: 避免在配置文件中硬编码敏感信息
3. **定期轮换**: 定期更换 API Key 以提高安全性
4. **限制权限**: 为 API Key 设置适当的权限范围

# linux-service-triage 集成思路

## 与 OpenClaw 系统的深度集成

### 1. Heartbeat 增强
在 `HEARTBEAT.md` 的基础上，加入服务健康检查：

```bash
# 每6小时执行
check_critical_services() {
    services=(
        "openclaw-gateway"
        "nginx"
        "cron"
    )

    for service in "${services[@]}"; do
        if ! systemctl is-active --quiet "$service"; then
            # 收集诊断信息
            journalctl -u "$service" -n 50 > /tmp/service-triage-$service.log
            # 发送告警
            ./skills/feishu-automation/feishu-send.sh "⚠️ 服务 $service 异常，已收集诊断信息"
        fi
    done
}
```

### 2. 快速诊断命令包装
创建便捷命令供用户直接调用：

```bash
# ~/clawd/scripts/triage.sh
#!/bin/bash
# Linux Service 快速诊断

SERVICE=${1:-"openclaw-gateway"}

echo "=== TRIAGE REPORT: $SERVICE ==="
echo "[1] Service Status:"
systemctl status $SERVICE --no-pager

echo -e "\n[2] Recent Logs:"
journalctl -u $SERVICE -n 50 --no-pager

echo -e "\n[3] Port Listening:"
if [ "$SERVICE" = "nginx" ]; then
    ss -ltnp | grep :80
    ss -ltnp | grep :443
elif [ "$SERVICE" = "openclaw-gateway" ]; then
    ss -ltnp | grep :3000
fi

echo -e "\n[4] Configuration Test:"
if [ "$SERVICE" = "nginx" ]; then
    nginx -t
fi
```

### 3. Auto-Triage Agent
结合 multi-agent-architecture，创建专门的诊断 Agent：

```javascript
// skills/linux-service-triage/agent.js
{
  name: "triage-agent",
  trigger: "service failure detected",
  actions: [
    "collect_evidence",
    "analyze_logs",
    "propose_fix",
    "verify_resolution"
  ]
}
```

## 常见问题知识库

### OpenClaw Gateway 故障模式

| 症状 | 可能原因 | 诊断命令 | 修复方法 |
|------|---------|---------|---------|
| 无法启动 | 端口被占用 | `ss -ltnp \| grep 3000` | 杀死占用进程 |
| 配置错误 | JSON 格式错误 | `openclaw gateway config.get` | 修复配置文件 |
| 权限错误 | 日志目录不可写 | `namei -l /var/log/openclaw` | 修正目录权限 |

### Nginx 502 模式

| 症状 | 可能原因 | 诊断命令 | 修复方法 |
|------|---------|---------|---------|
| 502 Bad Gateway | upstream 挂了 | `curl localhost:3000` | 重启应用 |
| 502 timeout | 应用响应慢 | `journalctl -u app` | 优化应用性能 |
| 502 connection refused | 端口不对 | `ss -ltnp` | 修正 proxy_pass |

## 诊断速查卡

创建 `/home/aa/clawd/skills/linux-service-triage/references/quick-reference.md`：

```markdown
# Linux Service 故障速查卡

## 🚨 紧急诊断三步法
1. systemctl status <service>
2. journalctl -u <service> -n 100
3. ss -ltnp | grep <port>

## 🔍 权限问题
```bash
namei -l /path/to/file  # 逐级检查权限
ls -la /path/to/file    # 查看文件权限
```

## 🌐 网络问题
```bash
ss -ltnp                # 查看监听端口
curl localhost:PORT     # 测试本地连接
dig +short domain.com   # 测试 DNS 解析
```

## 📋 Nginx 问题
```bash
nginx -t                # 测试配置
tail -f /var/log/nginx/error.log  # 实时错误日志
```

## 🔥 进程问题
```bash
ps aux | grep name     # 查找进程
kill -9 PID            # 强制杀死
```
```

## 自动化改进

### 预防性监控
```bash
# 添加到 crontab
*/30 * * * * /home/aa/clawd/scripts/service-health-check.sh
```

### 自愈脚本
```bash
# services/autoheal.sh
#!/bin/bash
# 服务自动恢复（需谨慎使用）

SERVICE=$1
if ! systemctl is-active --quiet "$SERVICE"; then
    logger "Auto-healing: attempting to restart $SERVICE"
    systemctl restart "$SERVICE"
    sleep 5
    if systemctl is-active --quiet "$SERVICE"; then
        logger "Auto-heal successful: $SERVICE is running"
        ./skills/feishu-automation/feishu-send.sh "✅ $SERVICE 自动恢复成功"
    else
        logger "Auto-heal failed: $SERVICE still down"
        ./skills/feishu-automation/feishu-send.sh "🚨 $SERVICE 自动恢复失败，需要人工介入"
    fi
fi
```

## 与其他 Skill 的协同

### + healthcheck
- healthcheck: 配置审计、安全加固
- triage: 故障诊断、服务恢复
- 协同: 定期审计 → 发现配置问题 → triage 修复

### + docker-deployment
- 容器服务诊断
- 网络模式桥接问题
- 卷挂载权限问题

### + security-audit
- 服务权限最小化
- 日志审计
- 异常检测

## 持续改进

### 学习反馈循环
1. 记录每次故障案例
2. 提取通用模式
3. 更新知识库
4. 优化诊断脚本
5. 提高自动化程度

### 度量指标
- 平均诊断时间 (MTTD)
- 平均修复时间 (MTTR)
- 自动恢复成功率
- 重复故障模式识别

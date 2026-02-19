# Cloudflare Tunnel 完整部署指南

## What is Cloudflare Tunnel?

Cloudflare Tunnel 是一种安全的出站连接，从你的服务器到 Cloudflare，无需开放公网端口。

### 架构

```
用户浏览器 --HTTPS--> Cloudflare Edge --加密隧道--> 你的服务器(cloudflared) --> Docker容器
                        ↑                                       ↑
                   全球分布节点                        无需开放公网端口
```

---

## 完整部署流程（端到端）

### 第一步：注册域名

1. 在域名注册商购买域名（如 Namecheap, GoDaddy, 阿里云等）
2. **重要**：准备好访问域名管理后台的权限

### 第二步：源服务器安装 cloudflared

```bash
# Ubuntu/Debian
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# 验证安装
cloudflared --version

# 或用 curl 安装
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

### 第三步：登录授权 Cloudflare

```bash
# 会弹出浏览器，登录你的 Cloudflare 账号并授权
cloudflared tunnel login
```

授权成功后，证书会保存在 `~/.cloudflared/cert.pem`

### 第四步：创建 Tunnel

```bash
# 创建命名隧道
cloudflared tunnel create <tunnel-name>

# 示例
cloudflared tunnel create xinzhixietong-tunnel

# 输出会包含：
# - Tunnel ID (保存这个！)
# - credentials file 位置
```

### 第五步：配置 DNS 到 Cloudflare

```bash
# 将域名路由到 tunnel
cloudflared tunnel route dns <tunnel-name> yourdomain.com
cloudflared tunnel route dns <tunnel-name> www.yourdomain.com
```

**或者**在 Cloudflare 后台手动添加 DNS 记录：
- 类型：CNAME
- 名称：www / @
- 目标：`<tunnel-id>.cfargotunnel.com`

#### 检查域名 NS 配置

**重要**：确认你的域名管理系统中，NS 记录指向 Cloudflare：

```
域名管理后台 → DNS 设置 → Nameservers
应该显示：
- lana.ns.cloudflare.com
- mark.ns.cloudflare.com
（具体以你的 CF 账号显示的为准）
```

流量路径：
```
用户 → 域名DNS解析 → Cloudflare NS → Cloudflare Tunnel → 你的服务器
```

### 第六步：创建 config.yml 配置

配置文件位置：`~/.cloudflared/config.yml`

```yaml
# Tunnel 基本信息
tunnel: <YOUR_TUNNEL_ID>  # 替换为你的 Tunnel ID
credentials-file: ~/.cloudflared/<TUNNEL_ID>.json

# 服务路由配置
ingress:
  # 前端服务（HTTP 端口，推荐）
  - hostname: www.yourdomain.com
    service: http://localhost:5668
    # 或者用 HTTPS（需要额外配置，见下文）
    # service: https://localhost:5669
    # originRequest:
    #   noTLSVerify: true  # 本地 HTTPS 需要跳过证书验证

  # 后端 API 服务
  - hostname: api.yourdomain.com
    service: http://localhost:5768

  # 其他服务...
  - hostname: admin.yourdomain.com
    service: http://localhost:3000

  # 默认规则（必须放在最后）
  - service: http_status:404
```

#### HTTPS 配置的坑（重要！）

**坑1：400 Bad Request - The plain HTTP request was sent to HTTPS port**

| 配置 | 结果 |
|------|------|
| `service: http://localhost:5669` | ❌ 错误！HTTP 协议访问 HTTPS 端口 |
| `service: https://localhost:5669` | ✅ 正确，但可能有证书问题 |

**坑2：502 Bad Gateway**

当使用 `https://localhost:5669` 时，cloudflared 会验证证书：
- 你的证书域名：`*.yourdomain.com`
- cloudflared 访问：`localhost`
- **域名不匹配，验证失败！**

**解决方案：**

| 方案 | 配置 | 推荐度 |
|------|------|--------|
| **方案A：用 HTTP** | `service: http://localhost:5668` | ⭐⭐⭐⭐⭐ 最简单 |
| **方案B：HTTPS + 跳过验证** | `service: https://localhost:5669` + `noTLSVerify: true` | ⭐⭐⭐⭐ |
| **方案C：生成 localhost 证书** | 生成包含 localhost 的证书 | ⭐⭐⭐ |

**方案A 示例（推荐）：**
```yaml
ingress:
  - hostname: www.yourdomain.com
    service: http://localhost:5668  # 用户到CF仍是HTTPS
```

**方案B 示例：**
```yaml
ingress:
  - hostname: www.yourdomain.com
    service: https://localhost:5669
    originRequest:
      noTLSVerify: true  # 跳过本地证书验证
      keepAliveTimeout: 90s
      connectTimeout: 30s
```

### 第七步：启动 Tunnel

```bash
# 方式一：直接运行（测试用）
cloudflared tunnel run <tunnel-name>

# 方式二：安装为系统服务（推荐）
sudo cloudflared service install

# 启动服务
sudo systemctl start cloudflared
sudo systemctl enable cloudflared

# 查看状态
sudo systemctl status cloudflared

# 查看日志
sudo journalctl -u cloudflared -f
```

---

## 服务管理

```bash
# 列出所有 tunnels
cloudflared tunnel list

# 查看 tunnel 信息
cloudflared tunnel info <tunnel-name>

# 删除 tunnel
cloudflared tunnel delete <tunnel-id>

# 清理 DNS 路由
cloudflared tunnel route dns <tunnel-name> yourdomain.com  # 添加
cloudflared tunnel route dns <tunnel-name> yourdomain.com -d  # 删除
```

---

## 常见问题

### 1. 时好时坏 / 手机无法访问

**可能原因**：
- Cloudflare 某些 IP 在国内被限制
- 域名未备案（国内访问问题）
- DNS 传播延迟

**解决方案**：
- 等待 DNS 传播（5-10分钟）
- 国内用户建议使用 VPN 或备案后使用国内方案

### 2. 修改 config.yml 后不生效

```bash
# 必须重启服务
sudo systemctl restart cloudflared
```

### 3. 502 Bad Gateway

检查：
```bash
# 本地服务是否运行
curl -k https://localhost:5669

# cloudflared 日志
sudo journalctl -u cloudflared -n 50
```

### 4. 400 Bad Request

检查 `service` 协议是否正确：
- HTTPS 端口必须用 `https://`
- HTTP 端口必须用 `http://`

---

## 安全说明

```
用户 --HTTPS(加密)--> Cloudflare --Tunnel(加密)--> cloudflared --HTTP/HTTPS--> 本地服务
        ↑                           ↑                       ↑
    浏览器验证CF证书           隧道加密传输          本地回环，安全可控
```

- **用户到 CF**：全程 HTTPS，浏览器验证证书，完全安全
- **CF 到 cloudflared**：Cloudflare Tunnel 加密，不经过公网
- **cloudflared 到本地服务**：本地回环连接，即使 HTTP 也安全（因为不走公网）

---

## Quick Start 快速模板

```bash
# 1. 安装
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# 2. 登录
cloudflared tunnel login

# 3. 创建 tunnel
cloudflared tunnel create my-tunnel

# 4. 配置 DNS
cloudflared tunnel route dns my-tunnel www.yourdomain.com

# 5. 编辑配置
nano ~/.cloudflared/config.yml
# 复制上面的模板

# 6. 启动
sudo cloudflared service install
sudo systemctl start cloudflared
```

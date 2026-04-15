# 快速部署指南

## 🚀 一键安装命令

### 方法 1：Git 克隆（推荐）

```bash
# 克隆仓库到本地
git clone https://github.com/buluslan/ecommerce-competitor-analyzer.git

# 复制到 Claude Code skills 目录
cp -r ecommerce-competitor-analyzer ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill
```

---

### 方法 2：软连接（推荐给开发者）

```bash
# 克隆仓库
git clone https://github.com/buluslan/ecommerce-competitor-analyzer.git

# 创建软连接（便于后续更新）
ln -s $(pwd)/ecommerce-competitor-analyzer ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill
```

---

### 方法 3：直接下载（不需要 Git）

```bash
# 下载并解压
curl -L https://github.com/buluslan/ecommerce-competitor-analyzer/archive/refs/heads/main.zip -o ecommerce-competitor-analyzer.zip
unzip ecommerce-competitor-analyzer.zip

# 复制到 Claude Code skills 目录
cp -r ecommerce-competitor-analyzer-main ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill

# 清理
rm ecommerce-competitor-analyzer.zip
```

---

## ⚙️ 安装后配置

### 1. 配置环境变量

```bash
# 进入 skill 目录
cd ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill

# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，添加你的 API 密钥
nano .env
# 或使用 VSCode: code .env
# 或使用 Vim: vim .env
```

### 2. 获取 API 密钥

**必需的 API 密钥**：

| 服务 | 获取地址 | 费用 |
|------|---------|------|
| **Olostep API** | https://olostep.com/ | 1000次/月免费 |
| **Google Gemini** | https://aistudio.google.com/app/apikey | ~$0.001/产品 |

### 3. 验证安装

```bash
# 验证环境变量配置
cd ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill
node scripts/verify-env.js
```

预期输出：
```
✅ OLOSTEP_API_KEY: Configured
✅ GEMINI_API_KEY: Configured
✅ GOOGLE_SHEETS_ID: Optional (not configured)

Environment setup complete!
```

---

## 🎮 开始使用

配置完成后，在 Claude Code 中直接说：

```
分析这个 Amazon 产品：B0C4YT8S6H
```

或批量分析：

```
分析这些 Amazon 产品：
B0C4YT8S6H
B08N5WRQ1Y
B0CLFH7CCV
```

---

## 🔄 更新项目

如果你使用了**软连接**方式安装：

```bash
# 进入项目目录
cd /path/to/ecommerce-competitor-analyzer

# 拉取最新代码
git pull origin main
```

如果你使用了**复制**方式安装：

```bash
# 删除旧版本
rm -rf ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill

# 重新克隆
git clone https://github.com/buluslan/ecommerce-competitor-analyzer.git
cp -r ecommerce-competitor-analyzer ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill
```

---

## 🗑️ 卸载

```bash
# 删除 skill
rm -rf ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill

# 如果是软连接，删除链接
rm ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill
```

---

## 📝 完整安装脚本（一键执行）

保存为 `install.sh`，然后运行 `bash install.sh`：

```bash
#!/bin/bash

echo "🚀 开始安装 E-commerce Competitor Analyzer Skill..."

# 克隆仓库
echo "📦 克隆仓库..."
git clone https://github.com/buluslan/ecommerce-competitor-analyzer.git

# 复制到 Claude Code skills 目录
echo "📋 安装到 Claude Code..."
mkdir -p ~/.claude/skills/main-mode-skills
cp -r ecommerce-competitor-analyzer ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill

# 配置环境变量
echo "⚙️ 配置环境变量..."
cd ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill
cp .env.example .env

echo ""
echo "✅ 安装完成！"
echo ""
echo "📝 下一步："
echo "1. 编辑 ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill/.env"
echo "2. 添加你的 OLOSTEP_API_KEY 和 GEMINI_API_KEY"
echo "3. 运行: cd ~/.claude/skills/main-mode-skills/ecommerce-competitor-analyzer.skill && node scripts/verify-env.js"
echo ""
echo "📚 详细文档: https://github.com/buluslan/ecommerce-competitor-analyzer"
```

---

## ❓ 常见问题

### Q: Claude Code 找不到 skill？
**A**: 确保文件在正确的目录：`~/.claude/skills/main-mode-skills/`

### Q: 如何查看已安装的 skills？
**A**:
```bash
ls ~/.claude/skills/main-mode-skills/
```

### Q: API 密钥在哪里配置？
**A**: 在 skill 目录下的 `.env` 文件中

---

## 📚 更多文档

- [完整配置指南](https://github.com/buluslan/ecommerce-competitor-analyzer/blob/main/docs/SETUP.md)
- [使用手册](https://github.com/buluslan/ecommerce-competitor-analyzer#-使用方法)
- [GitHub 仓库](https://github.com/buluslan/ecommerce-competitor-analyzer)

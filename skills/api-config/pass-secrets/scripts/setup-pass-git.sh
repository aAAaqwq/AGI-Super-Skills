#!/bin/bash
# Pass 密钥库 Git 同步设置脚本
# 用法: ./setup-pass-git.sh

set -e

REPO_NAME="password-store"
PASS_DIR="$HOME/.password-store"

echo "========================================="
echo "  Pass 密钥库 Git 同步设置"
echo "========================================="
echo ""

# 检查 Pass 目录
if [ ! -d "$PASS_DIR" ]; then
    echo "❌ Pass 目录不存在: $PASS_DIR"
    exit 1
fi

cd "$PASS_DIR"

# 检查 Git 是否已初始化
if [ ! -d .git ]; then
    echo "初始化 Git..."
    pass git init
fi

echo ""
echo "📋 你的 SSH 公钥（添加到 GitHub）:"
echo "----------------------------------------"
cat ~/.ssh/id_ed25519.pub 2>/dev/null || cat ~/.ssh/id_rsa.pub 2>/dev/null
echo "----------------------------------------"
echo ""
echo "请按以下步骤操作:"
echo ""
echo "1. 打开 https://github.com/settings/keys"
echo "2. 点击 'New SSH key'"
echo "3. 粘贴上面的公钥"
echo "4. 保存"
echo ""
echo "5. 创建私有仓库: https://github.com/new"
echo "   - 仓库名: $REPO_NAME"
echo "   - 选择 'Private'"
echo "   - 不要初始化 README"
echo ""
read -p "完成后按 Enter 继续..."

echo ""
read -p "请输入你的 GitHub 用户名: " GITHUB_USER

# 添加远程仓库
REMOTE_URL="git@github.com:$GITHUB_USER/$REPO_NAME.git"

if git remote | grep -q origin; then
    git remote set-url origin "$REMOTE_URL"
else
    git remote add origin "$REMOTE_URL"
fi

echo ""
echo "正在推送到 GitHub..."
git branch -M main
git push -u origin main

echo ""
echo "========================================="
echo "  ✅ 设置完成！"
echo "========================================="
echo ""
echo "仓库地址: https://github.com/$GITHUB_USER/$REPO_NAME"
echo ""
echo "常用命令:"
echo "  pass git pull    # 拉取更新"
echo "  pass git push    # 推送更新"
echo ""
echo "新设备同步:"
echo "  1. 导入 GPG 私钥"
echo "  2. git clone $REMOTE_URL ~/.password-store"
echo ""

#!/bin/bash
# 企业微信个人账号机器人 - 一键安装脚本

set -e

echo "🚀 开始安装企业微信个人账号机器人..."
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查依赖
check_dependencies() {
    echo -e "${YELLOW}检查系统依赖...${NC}"

    # Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ 未安装 Node.js${NC}"
        echo "请安装 Node.js 16+：curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -"
        exit 1
    fi

    # npm
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}❌ 未安装 npm${NC}"
        exit 1
    fi

    # Python 3
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ 未安装 Python 3${NC}"
        exit 1
    fi

    # pip
    if ! command -v pip3 &> /dev/null; then
        echo -e "${RED}❌ 未安装 pip3${NC}"
        exit 1
    fi

    # PostgreSQL
    if ! command -v psql &> /dev/null; then
        echo -e "${YELLOW}⚠️  未安装 PostgreSQL，正在安装...${NC}"
        sudo apt update
        sudo apt install -y postgresql postgresql-contrib
    fi

    echo -e "${GREEN}✓ 依赖检查完成${NC}"
    echo ""
}

# 安装 Node.js 依赖
install_node_packages() {
    echo -e "${YELLOW}安装 Node.js 依赖...${NC}"

    cd ~/clawd/skills/wecom-automation

    npm install || {
        echo -e "${RED}❌ Node.js 包安装失败${NC}"
        exit 1
    }

    echo -e "${GREEN}✓ Node.js 包安装完成${NC}"
    echo ""
}

# 安装 Python 包
install_python_packages() {
    echo -e "${YELLOW}安装 Python 依赖...${NC}"

    pip3 install --user -r requirements.txt || {
        echo -e "${RED}❌ Python 包安装失败${NC}"
        exit 1
    }

    echo -e "${GREEN}✓ Python 包安装完成${NC}"
    echo ""
}

# 配置数据库
setup_database() {
    echo -e "${YELLOW}配置数据库...${NC}"

    # 启动 PostgreSQL
    sudo service postgresql start

    # 创建数据库
    sudo -u postgres createdb wecom_kb 2>/dev/null || echo "数据库已存在"

    # 启用 pgvector 扩展
    echo -e "${YELLOW}检查 pgvector 扩展...${NC}"

    if ! sudo -u postgres psql -d wecom_kb -c "SELECT * FROM pg_extension WHERE extname = 'vector';" | grep -q vector; then
        echo -e "${YELLOW}安装 pgvector...${NC}"

        # 检测 PostgreSQL 版本
        PG_VERSION=$(sudo -u postgres psql -t -c "SELECT version()" | grep -oP 'PostgreSQL \K[0-9.]+' | head -1)
        PG_MAJOR=$(echo $PG_VERSION | cut -d. -f1)

        echo "检测到 PostgreSQL $PG_VERSION"

        # 安装 pgvector
        if [ ! -d "/tmp/pgvector" ]; then
            cd /tmp
            git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
            cd pgvector
            sudo apt install -y build-essential libpq-dev
            make
            sudo make install
        fi

        # 启用扩展
        sudo -u postgres psql -d wecom_kb -c "CREATE EXTENSION vector;"
        echo -e "${GREEN}✓ pgvector 扩展已启用${NC}"
    else
        echo -e "${GREEN}✓ pgvector 扩展已存在${NC}"
    fi

    # 初始化表结构
    echo -e "${YELLOW}初始化数据库表...${NC}"
    sudo -u postgres psql -d wecom_kb -f schema.sql

    echo -e "${GREEN}✓ 数据库配置完成${NC}"
    echo ""
}

# 配置环境变量
setup_env() {
    echo -e "${YELLOW}配置环境变量...${NC}"

    ENV_FILE="$HOME/clawd/skills/wecom-automation/.env"

    if [ -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}⚠️  .env 文件已存在，跳过${NC}"
    else
        cp .env.example "$ENV_FILE"
        
        # 自动填入 Kimi API Key
        if pass show api/kimi &> /dev/null; then
            sed -i "s|LLM_API_KEY=.*|LLM_API_KEY=$(pass show api/kimi)|" "$ENV_FILE"
        fi

        echo -e "${GREEN}✓ 已创建 .env 模板${NC}"
        echo -e "${YELLOW}⚠️  请编辑 $ENV_FILE 填入以下配置：${NC}"
        echo ""
        echo "必填项："
        echo "  1. WECHATY_TOKEN - PadLocal Token (https://github.com/wechaty/puppet-service)"
        echo "  2. TELEGRAM_BOT_TOKEN - 用于人工介入通知"
        echo ""
        echo "可选项（已自动填入）："
        echo "  3. LLM_API_KEY - Kimi API Key (已自动配置)"
    fi

    echo ""
}

# 创建必要目录
setup_directories() {
    echo -e "${YELLOW}创建必要目录...${NC}"

    mkdir -p logs
    mkdir -p tmp
    
    echo -e "${GREEN}✓ 目录创建完成${NC}"
    echo ""
}

# 导入示例知识库
import_sample_kb() {
    echo -e "${YELLOW}导入示例知识库...${NC}"

    KB_FILE="$HOME/clawd/skills/wecom-automation/knowledge/sample.md"

    if [ -f "$KB_FILE" ]; then
        python3 scripts/import_kb.py \
            --input "$KB_FILE" \
            --category "示例知识" \
            --tags "示例,测试" \
            --key "$(pass show api/kimi)" || {
            echo -e "${RED}❌ 知识库导入失败（可能需要先配置 Kimi API Key）${NC}"
            echo "可以稍后手动导入："
            echo "python3 ~/clawd/skills/wecom-automation/scripts/import_kb.py --input knowledge/sample.md --key YOUR_KIMI_KEY"
        }
        echo -e "${GREEN}✓ 知识库导入完成${NC}"
    else
        echo -e "${YELLOW}⚠️  示例知识库文件不存在${NC}"
    fi

    echo ""
}

# 打印后续步骤
print_next_steps() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ 安装完成！${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "📋 后续步骤："
    echo ""
    echo "1️⃣  申请 PadLocal Token"
    echo "   - 访问 https://github.com/wechaty/wechaty"
    echo "   - 选择 PadLocal 协议"
    echo "   - 注册并获取 Token"
    echo ""
    echo "2️⃣  填写环境变量"
    echo "   - 编辑 ~/clawd/skills/wecom-automation/.env"
    echo "   - 填入 WECHATY_TOKEN"
    echo "   - 填入 TELEGRAM_BOT_TOKEN"
    echo ""
    echo "3️⃣  启动机器人"
    echo "   cd ~/clawd/skills/wecom-automation"
    echo "   npm start"
    echo ""
    echo "   或使用 PM2（推荐）："
    echo "   pm2 start ecosystem.config.js"
    echo ""
    echo "4️⃣  扫码登录"
    echo "   - 启动后会显示二维码"
    echo "   - 打开企业微信 → 扫一扫"
    echo "   - 扫描二维码登录"
    echo ""
    echo "5️⃣  测试功能"
    echo "   # 测试问答"
    echo "   python3 ~/clawd/skills/wecom-automation/workflows/answer_question.py \\"
    echo "     --user-id test_user --question \"如何退款？\""
    echo ""
    echo "   # 测试人工介入"
    echo "   python3 ~/clawd/skills/wecom-automation/workflows/escalate.py \\"
    echo "     --user-id test_user --name \"测试用户\" --question \"测试问题\""
    echo ""
    echo "📚 更多信息："
    echo "   cat ~/clawd/skills/wecom-automation/SKILL.md"
    echo ""
}

# 主流程
main() {
    check_dependencies
    install_node_packages
    install_python_packages
    setup_database
    setup_env
    setup_directories
    import_sample_kb
    print_next_steps
}

# 运行安装
main

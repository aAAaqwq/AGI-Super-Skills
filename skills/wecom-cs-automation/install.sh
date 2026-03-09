#!/bin/bash
# 企业微信客服自动化系统 - 一键安装脚本

set -e

echo "🚀 开始安装企业微信客服自动化系统..."
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查依赖
check_dependencies() {
    echo -e "${YELLOW}检查系统依赖...${NC}"

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

# 安装 Python 包
install_python_packages() {
    echo -e "${YELLOW}安装 Python 依赖...${NC}"

    pip3 install --user \
        openai \
        psycopg2-binary \
        requests \
        fastapi \
        uvicorn \
        python-dotenv \
        numpy || {
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
    sudo -u postgres psql -d wecom_kb -f ~/clawd/skills/wecom-cs-automation/schema.sql

    echo -e "${GREEN}✓ 数据库配置完成${NC}"
    echo ""
}

# 配置环境变量
setup_env() {
    echo -e "${YELLOW}配置环境变量...${NC}"

    ENV_FILE="$HOME/clawd/skills/wecom-cs-automation/.env"

    if [ -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}⚠️  .env 文件已存在，跳过${NC}"
    else
        cat > "$ENV_FILE" << EOF
# 企业微信配置
WECOM_CORP_ID=
WECOM_AGENT_ID=1000002
WECOM_AGENT_SECRET=
WECOM_TOKEN=
WECOM_ENCODING_AES_KEY=

# 数据库
KB_DB_URL=postgresql://postgres@localhost/wecom_kb

# LLM
LLM_PROVIDER=kimi
LLM_API_KEY=\$(pass show api/kimi)
LLM_API_BASE=https://api.moonshot.cn/v1
LLM_MODEL=moonshot-v1-8k

# 知识库搜索
KB_SIMILARITY_THRESHOLD=0.7
KB_TOP_K=3

# 人工介入
NOTIFICATION_ENABLED=true
NOTIFICATION_CHANNEL=telegram:YOUR_TELEGRAM_ID
EOF

        echo -e "${GREEN}✓ 已创建 .env 模板${NC}"
        echo -e "${YELLOW}⚠️  请编辑 $ENV_FILE 填入企业微信配置${NC}"
    fi

    echo ""
}

# 导入示例知识库
import_sample_kb() {
    echo -e "${YELLOW}导入示例知识库...${NC}"

    KB_FILE="$HOME/clawd/skills/wecom-cs-automation/knowledge/sample.md"

    if [ -f "$KB_FILE" ]; then
        python3 ~/clawd/skills/wecom-cs-automation/scripts/import_kb.py \
            --input "$KB_FILE" \
            --category "示例知识" \
            --tags "示例,测试" \
            --key "$(pass show api/kimi)" || {
            echo -e "${RED}❌ 知识库导入失败（可能需要先配置 Kimi API Key）${NC}"
            echo "可以稍后手动导入："
            echo "python3 ~/clawd/skills/wecom-cs-automation/scripts/import_kb.py --input knowledge/sample.md --key YOUR_KIMI_KEY"
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
    echo "1️⃣  配置企业微信应用"
    echo "   - 登录企业微信管理后台"
    echo "   - 创建'微信客服'应用"
    echo "   - 配置回调地址：https://your-domain.com/wecom/callback"
    echo ""
    echo "2️⃣  填写环境变量"
    echo "   - 编辑 ~/clawd/skills/wecom-cs-automation/.env"
    echo "   - 填入 WECOM_CORP_ID、WECOM_AGENT_SECRET 等"
    echo ""
    echo "3️⃣  导入知识库"
    echo "   python3 ~/clawd/skills/wecom-cs-automation/scripts/import_kb.py \\"
    echo "     --input your_knowledge.md \\"
    echo "     --category \"常见问题\" \\"
    echo "     --tags \"售后,FAQ\""
    echo ""
    echo "4️⃣  测试功能"
    echo "   # 测试知识库搜索"
    echo "   python3 ~/clawd/skills/wecom-cs-automation/scripts/search_kb.py \"如何退款？\""
    echo ""
    echo "   # 测试新好友处理"
    echo "   python3 ~/clawd/skills/wecom-cs-automation/workflows/on_friend_add.py \\"
    echo "     --user-id test_user --name \"测试用户\""
    echo ""
    echo "   # 测试问答"
    echo "   python3 ~/clawd/skills/wecom-cs-automation/workflows/answer_question.py \\"
    echo "     --user-id test_user --question \"如何退货？\""
    echo ""
    echo "5️⃣  启动回调服务"
    echo "   uvicorn ~/clawd/skills/wecom-cs-automation/server/main.py:app \\"
    echo "     --host 0.0.0.0 --port 8000"
    echo ""
    echo "📚 更多信息："
    echo "   cat ~/clawd/skills/wecom-cs-automation/SKILL.md"
    echo ""
}

# 主流程
main() {
    check_dependencies
    install_python_packages
    setup_database
    setup_env
    import_sample_kb
    print_next_steps
}

# 运行安装
main

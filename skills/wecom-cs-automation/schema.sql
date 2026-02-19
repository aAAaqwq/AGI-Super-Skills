-- 企业微信客服自动化系统 - 数据库表结构

-- 知识库片段表
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1024),  -- Kimi 嵌入维度
    category VARCHAR(50),
    tags TEXT[],
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 未解决问题记录
CREATE TABLE IF NOT EXISTS unknown_questions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    user_name VARCHAR(100),
    question TEXT NOT NULL,
    conversation_context JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 对话历史
CREATE TABLE IF NOT EXISTS conversation_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    role VARCHAR(20) NOT NULL,  -- user/assistant/system
    content TEXT NOT NULL,
    msg_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 人工介入记录
CREATE TABLE IF NOT EXISTS escalation_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    user_name VARCHAR(100),
    reason TEXT,
    question TEXT,
    notified BOOLEAN DEFAULT FALSE,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

-- 用户信息表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    external_userid VARCHAR(100) UNIQUE,
    name VARCHAR(100),
    avatar TEXT,
    tags TEXT[],
    first_contact TIMESTAMP DEFAULT NOW(),
    last_contact TIMESTAMP DEFAULT NOW(),
    total_messages INTEGER DEFAULT 0
);

-- 索引优化
CREATE INDEX idx_chunks_category ON knowledge_chunks(category);
CREATE INDEX idx_chunks_tags ON knowledge_chunks USING GIN(tags);
CREATE INDEX idx_unknown_user ON unknown_questions(user_id);
CREATE INDEX idx_conv_user ON conversation_history(user_id);
CREATE INDEX idx_conv_created ON conversation_history(created_at DESC);
CREATE INDEX idx_users_external ON users(external_userid);
CREATE INDEX idx_users_tags ON users USING GIN(tags);

-- 向量相似度搜索索引（HNSW 算法）
CREATE INDEX idx_chunks_embedding ON knowledge_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_knowledge_chunks_updated
    BEFORE UPDATE ON knowledge_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

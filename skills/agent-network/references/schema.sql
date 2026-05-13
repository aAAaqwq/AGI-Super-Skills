-- Agent 群聊协作系统数据库表结构

-- 创建 agents 表：存储所有 Agent 信息
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,          -- Agent 名称（如"小邢"）
    role TEXT NOT NULL,                  -- Agent 角色（如"开发运维"）
    description TEXT,                    -- Agent 描述
    status TEXT DEFAULT 'offline',       -- online/offline/busy
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP
);

-- 创建 groups 表：存储群组信息
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,           -- 群组名称
    description TEXT,                    -- 群组描述
    owner_id INTEGER,                    -- 群主（Agent ID）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES agents(id)
);

-- 创建 group_members 表：群组成员关系
CREATE TABLE IF NOT EXISTS group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    agent_id INTEGER NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(group_id, agent_id),
    FOREIGN KEY (group_id) REFERENCES groups(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- 创建 messages 表：存储所有消息记录
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER,                    -- 所属群组
    from_agent_id INTEGER NOT NULL,      -- 发送者
    to_agent_id INTEGER,                 -- 接收者（私信/提及时为特定Agent）
    content TEXT NOT NULL,               -- 消息内容
    type TEXT NOT NULL,                  -- chat, mention, task_assign, task_complete, decision, system
    reply_to INTEGER,                    -- 回复的消息ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id),
    FOREIGN KEY (from_agent_id) REFERENCES agents(id),
    FOREIGN KEY (to_agent_id) REFERENCES agents(id),
    FOREIGN KEY (reply_to) REFERENCES messages(id)
);

-- 创建 tasks 表：存储任务信息
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT UNIQUE NOT NULL,        -- 任务唯一标识（如 TASK-001）
    title TEXT NOT NULL,                 -- 任务标题
    description TEXT,                    -- 任务描述
    assigner_id INTEGER NOT NULL,        -- 任务指派者
    assignee_id INTEGER NOT NULL,        -- 任务接收者
    group_id INTEGER,                    -- 所属群组
    status TEXT DEFAULT 'pending',       -- pending, in_progress, completed, cancelled
    priority TEXT DEFAULT 'normal',      -- low, normal, high, urgent
    due_date TIMESTAMP,                  -- 截止日期
    completed_at TIMESTAMP,              -- 完成时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigner_id) REFERENCES agents(id),
    FOREIGN KEY (assignee_id) REFERENCES agents(id),
    FOREIGN KEY (group_id) REFERENCES groups(id)
);

-- 创建 task_comments 表：任务评论/更新记录
CREATE TABLE IF NOT EXISTS task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    agent_id INTEGER NOT NULL,
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- 创建 decisions 表：协作决策记录
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT UNIQUE NOT NULL,    -- 决策唯一标识
    title TEXT NOT NULL,                 -- 决策标题
    description TEXT,                    -- 决策描述
    group_id INTEGER,                    -- 所属群组
    proposer_id INTEGER NOT NULL,        -- 提案人
    status TEXT DEFAULT 'proposed',      -- proposed, discussing, approved, rejected, implemented
    votes_for INTEGER DEFAULT 0,
    votes_against INTEGER DEFAULT 0,
    decided_at TIMESTAMP,                -- 决策时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id),
    FOREIGN KEY (proposer_id) REFERENCES agents(id)
);

-- 创建 decision_votes 表：决策投票记录
CREATE TABLE IF NOT EXISTS decision_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER NOT NULL,
    agent_id INTEGER NOT NULL,
    vote TEXT NOT NULL,                  -- for, against, abstain
    comment TEXT,                        -- 投票意见
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(decision_id, agent_id),
    FOREIGN KEY (decision_id) REFERENCES decisions(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- 创建 agent_inbox 表：Agent 消息收件箱
CREATE TABLE IF NOT EXISTS agent_inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_messages_group_id ON messages(group_id);
CREATE INDEX IF NOT EXISTS idx_messages_from_agent ON messages(from_agent_id);
CREATE INDEX IF NOT EXISTS idx_messages_to_agent ON messages(to_agent_id);
CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_agent_inbox_agent ON agent_inbox(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_inbox_unread ON agent_inbox(agent_id, is_read);

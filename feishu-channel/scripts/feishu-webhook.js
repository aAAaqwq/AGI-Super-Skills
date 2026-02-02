#!/usr/bin/env node
/**
 * Feishu Webhook Server for OpenClaw
 * 
 * 接收飞书事件订阅，转发消息到 OpenClaw Gateway
 */

require('dotenv').config();
const express = require('express');
const crypto = require('crypto');
const axios = require('axios');

// ============ 配置 ============
const config = {
  // 飞书应用配置
  appId: process.env.FEISHU_APP_ID || 'YOUR_APP_ID',
  appSecret: process.env.FEISHU_APP_SECRET || 'YOUR_APP_SECRET',
  verificationToken: process.env.FEISHU_VERIFICATION_TOKEN || '',
  encryptKey: process.env.FEISHU_ENCRYPT_KEY || '',
  
  // OpenClaw Gateway
  openclawGatewayUrl: process.env.OPENCLAW_GATEWAY_URL || 'http://127.0.0.1:18789',
  openclawWebhookSecret: process.env.OPENCLAW_WEBHOOK_SECRET || '',
  
  // 安全配置
  allowedUsers: process.env.ALLOWED_USERS?.split(',').filter(Boolean) || [],
  allowedGroups: process.env.ALLOWED_GROUPS?.split(',').filter(Boolean) || [],
  requireMentionInGroup: process.env.REQUIRE_MENTION_IN_GROUP !== 'false',
  
  // 服务端口
  port: parseInt(process.env.PORT || '3002'),
  
  // 日志级别
  logLevel: process.env.LOG_LEVEL || 'info',
};

// ============ Access Token 管理 ============
let accessToken = null;
let tokenExpireTime = 0;

async function getAccessToken() {
  if (accessToken && Date.now() < tokenExpireTime - 60000) {
    return accessToken;
  }
  
  try {
    const response = await axios.post(
      'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
      {
        app_id: config.appId,
        app_secret: config.appSecret,
      }
    );
    
    if (response.data.code === 0) {
      accessToken = response.data.tenant_access_token;
      tokenExpireTime = Date.now() + response.data.expire * 1000;
      console.log('Access token 已更新');
      return accessToken;
    } else {
      throw new Error(`获取 token 失败: ${response.data.msg}`);
    }
  } catch (error) {
    console.error('获取 access token 失败:', error.message);
    throw error;
  }
}

// ============ 事件解密 ============
function decryptEvent(encrypt) {
  if (!config.encryptKey) {
    throw new Error('未配置 FEISHU_ENCRYPT_KEY');
  }
  
  const key = crypto.createHash('sha256').update(config.encryptKey).digest();
  const encryptBuffer = Buffer.from(encrypt, 'base64');
  const iv = encryptBuffer.slice(0, 16);
  const encrypted = encryptBuffer.slice(16);
  
  const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
  let decrypted = decipher.update(encrypted, undefined, 'utf8');
  decrypted += decipher.final('utf8');
  
  return JSON.parse(decrypted);
}

// ============ 用户信息获取 ============
const userCache = new Map();

async function getUserInfo(openId) {
  if (userCache.has(openId)) {
    return userCache.get(openId);
  }
  
  try {
    const token = await getAccessToken();
    const response = await axios.get(
      `https://open.feishu.cn/open-apis/contact/v3/users/${openId}`,
      {
        headers: { Authorization: `Bearer ${token}` },
        params: { user_id_type: 'open_id' },
      }
    );
    
    if (response.data.code === 0) {
      const user = response.data.data.user;
      const info = {
        id: openId,
        name: user.name,
        email: user.email,
        avatar: user.avatar?.avatar_origin,
      };
      userCache.set(openId, info);
      return info;
    }
  } catch (error) {
    console.error('获取用户信息失败:', error.message);
  }
  
  return { id: openId, name: 'Unknown' };
}

// ============ 群聊信息获取 ============
const chatCache = new Map();

async function getChatInfo(chatId) {
  if (chatCache.has(chatId)) {
    return chatCache.get(chatId);
  }
  
  try {
    const token = await getAccessToken();
    const response = await axios.get(
      `https://open.feishu.cn/open-apis/im/v1/chats/${chatId}`,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    
    if (response.data.code === 0) {
      const chat = response.data.data;
      const info = {
        id: chatId,
        name: chat.name,
        type: chat.chat_mode === 'p2p' ? 'private' : 'group',
      };
      chatCache.set(chatId, info);
      return info;
    }
  } catch (error) {
    console.error('获取群聊信息失败:', error.message);
  }
  
  return { id: chatId, name: 'Unknown', type: 'group' };
}

// ============ 消息处理 ============
async function handleMessageEvent(event) {
  const { sender, message } = event;
  
  // 只处理用户消息
  if (sender.sender_type !== 'user') {
    console.log('忽略非用户消息');
    return;
  }
  
  const senderId = sender.sender_id.open_id;
  const chatId = message.chat_id;
  const chatType = message.chat_type;
  
  // 权限检查
  if (!checkPermission(senderId, chatId, chatType)) {
    console.log('权限检查未通过，忽略消息');
    return;
  }
  
  // 群聊 @提及检查
  const mentions = message.mentions || [];
  const isMentioned = mentions.some(m => m.id?.open_id === config.appId);
  
  if (chatType === 'group' && config.requireMentionInGroup && !isMentioned) {
    console.log('群消息未@机器人，忽略');
    return;
  }
  
  // 解析消息内容
  let text = '';
  if (message.message_type === 'text') {
    const content = JSON.parse(message.content);
    text = content.text || '';
    
    // 移除 @提及文本
    for (const mention of mentions) {
      text = text.replace(mention.key, '').trim();
    }
  } else {
    console.log(`暂不支持的消息类型: ${message.message_type}`);
    return;
  }
  
  // 获取用户和群聊信息
  const userInfo = await getUserInfo(senderId);
  const chatInfo = chatType === 'group' 
    ? await getChatInfo(chatId)
    : { id: senderId, type: 'private' };
  
  // 构建 OpenClaw 消息格式
  const payload = {
    type: 'message',
    channel: 'feishu',
    messageId: message.message_id,
    timestamp: parseInt(message.create_time),
    from: userInfo,
    chat: chatInfo,
    text: text,
    mentions: mentions.map(m => m.id?.open_id).filter(Boolean),
    isMentioned: isMentioned,
    raw: event,
  };
  
  // 转发到 OpenClaw
  await forwardToOpenClaw(payload);
}

function checkPermission(senderId, chatId, chatType) {
  if (chatType === 'p2p') {
    if (config.allowedUsers.length === 0) return true;
    return config.allowedUsers.includes(senderId);
  }
  
  if (chatType === 'group') {
    if (config.allowedGroups.length === 0) return true;
    return config.allowedGroups.includes(chatId);
  }
  
  return false;
}

async function forwardToOpenClaw(payload) {
  try {
    const headers = {
      'Content-Type': 'application/json',
    };
    
    if (config.openclawWebhookSecret) {
      headers['Authorization'] = `Bearer ${config.openclawWebhookSecret}`;
    }
    
    const response = await axios.post(
      `${config.openclawGatewayUrl}/webhook/feishu`,
      payload,
      { headers, timeout: 30000 }
    );
    
    console.log('消息已转发到 OpenClaw:', response.status);
  } catch (error) {
    console.error('转发消息到 OpenClaw 失败:', error.message);
  }
}

// ============ Express 服务 ============
const app = express();
app.use(express.json());

// 健康检查
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    appId: config.appId,
    hasToken: !!accessToken,
  });
});

// 飞书 Webhook 端点
app.post('/webhook/feishu', async (req, res) => {
  try {
    let body = req.body;
    
    // 处理加密事件
    if (body.encrypt) {
      body = decryptEvent(body.encrypt);
    }
    
    // URL 验证 (首次配置时飞书会发送验证请求)
    if (body.type === 'url_verification') {
      console.log('收到 URL 验证请求');
      return res.json({ challenge: body.challenge });
    }
    
    // 验证 token
    if (config.verificationToken && body.token !== config.verificationToken) {
      console.error('验证 token 不匹配');
      return res.status(401).json({ error: 'Invalid token' });
    }
    
    // 处理事件回调
    if (body.header?.event_type === 'im.message.receive_v1') {
      console.log('收到消息事件');
      
      // 立即返回 200，避免飞书重试
      res.json({ code: 0 });
      
      // 异步处理消息
      handleMessageEvent(body.event).catch(console.error);
      return;
    }
    
    // 其他事件
    console.log('收到其他事件:', body.header?.event_type || body.type);
    res.json({ code: 0 });
    
  } catch (error) {
    console.error('处理 Webhook 失败:', error);
    res.status(500).json({ error: error.message });
  }
});

// 发送消息 API (供 OpenClaw 调用)
app.post('/api/send', async (req, res) => {
  try {
    // 验证 secret
    const authHeader = req.headers.authorization;
    if (config.openclawWebhookSecret) {
      if (authHeader !== `Bearer ${config.openclawWebhookSecret}`) {
        return res.status(401).json({ error: 'Unauthorized' });
      }
    }
    
    const { to, type, content, receiveIdType } = req.body;
    
    if (!to || !content) {
      return res.status(400).json({ error: 'Missing required fields' });
    }
    
    const token = await getAccessToken();
    
    const response = await axios.post(
      `https://open.feishu.cn/open-apis/im/v1/messages`,
      {
        receive_id: to,
        msg_type: type || 'text',
        content: typeof content === 'string' ? content : JSON.stringify(content),
      },
      {
        headers: { Authorization: `Bearer ${token}` },
        params: { receive_id_type: receiveIdType || 'open_id' },
      }
    );
    
    if (response.data.code === 0) {
      res.json({ success: true, data: response.data.data });
    } else {
      res.status(400).json({ error: response.data.msg, code: response.data.code });
    }
    
  } catch (error) {
    console.error('发送消息失败:', error.message);
    res.status(500).json({ error: error.message });
  }
});

// ============ 启动 ============
async function main() {
  console.log('\n========================================');
  console.log('🐦 Feishu Webhook Server for OpenClaw');
  console.log('========================================\n');
  
  // 检查配置
  if (config.appId === 'YOUR_APP_ID') {
    console.error('❌ 请配置 FEISHU_APP_ID 环境变量');
    process.exit(1);
  }
  
  if (config.appSecret === 'YOUR_APP_SECRET') {
    console.error('❌ 请配置 FEISHU_APP_SECRET 环境变量');
    process.exit(1);
  }
  
  // 预获取 access token
  try {
    await getAccessToken();
    console.log('✅ Access token 获取成功');
  } catch (error) {
    console.error('⚠️ 无法获取 access token，请检查配置');
  }
  
  // 启动服务
  app.listen(config.port, () => {
    console.log(`\n📡 服务已启动: http://localhost:${config.port}`);
    console.log(`   - 健康检查: GET /health`);
    console.log(`   - Webhook: POST /webhook/feishu`);
    console.log(`   - 发送消息: POST /api/send`);
    console.log(`\n配置飞书事件订阅 URL: https://your-domain.com/webhook/feishu\n`);
  });
}

main().catch(console.error);

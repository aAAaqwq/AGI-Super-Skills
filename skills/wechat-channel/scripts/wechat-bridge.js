#!/usr/bin/env node
/**
 * WeChat Bridge for OpenClaw
 * 
 * 基于 Wechaty + PadLocal 的微信消息桥接服务
 * 将微信消息转发到 OpenClaw Gateway，并接收 OpenClaw 的回复发送到微信
 */

require('dotenv').config();
const { WechatyBuilder, ScanStatus, log } = require('wechaty');
const { PuppetPadlocal } = require('wechaty-puppet-padlocal');
const axios = require('axios');
const express = require('express');
const qrcode = require('qrcode-terminal');

// ============ 配置 ============
const config = {
  // PadLocal Token
  padlocalToken: process.env.PADLOCAL_TOKEN || 'YOUR_PADLOCAL_TOKEN',
  
  // OpenClaw Gateway
  openclawGatewayUrl: process.env.OPENCLAW_GATEWAY_URL || 'http://127.0.0.1:18789',
  openclawWebhookSecret: process.env.OPENCLAW_WEBHOOK_SECRET || '',
  
  // Bot 配置
  botName: process.env.WECHAT_BOT_NAME || 'OpenClaw助手',
  
  // 安全配置
  allowedUsers: process.env.ALLOWED_USERS?.split(',').filter(Boolean) || [],
  allowedGroups: process.env.ALLOWED_GROUPS?.split(',').filter(Boolean) || [],
  requireMentionInGroup: process.env.REQUIRE_MENTION_IN_GROUP !== 'false',
  
  // 服务端口
  apiPort: parseInt(process.env.API_PORT || '3001'),
  
  // 日志级别
  logLevel: process.env.LOG_LEVEL || 'info',
};

// ============ 日志 ============
log.level(config.logLevel);

// ============ Wechaty 实例 ============
const puppet = new PuppetPadlocal({
  token: config.padlocalToken,
});

const bot = WechatyBuilder.build({
  name: 'openclaw-wechat-bridge',
  puppet,
});

// Bot 自身信息
let botInfo = null;

// ============ 事件处理 ============

// 扫码登录
bot.on('scan', (qrcodeUrl, status) => {
  if (status === ScanStatus.Waiting || status === ScanStatus.Timeout) {
    console.log('\n========================================');
    console.log('请使用微信扫描下方二维码登录:');
    console.log('========================================\n');
    qrcode.generate(qrcodeUrl, { small: true });
    console.log(`\n或访问: ${qrcodeUrl}\n`);
  }
});

// 登录成功
bot.on('login', async (user) => {
  botInfo = user;
  console.log('\n========================================');
  console.log(`✅ 登录成功: ${user.name()}`);
  console.log(`   微信ID: ${user.id}`);
  console.log('========================================\n');
});

// 登出
bot.on('logout', (user) => {
  console.log(`\n❌ 已登出: ${user.name()}\n`);
  botInfo = null;
});

// 收到消息
bot.on('message', async (message) => {
  try {
    await handleMessage(message);
  } catch (error) {
    console.error('处理消息失败:', error);
  }
});

// 错误处理
bot.on('error', (error) => {
  console.error('Bot 错误:', error);
});

// ============ 消息处理 ============

async function handleMessage(message) {
  // 忽略自己发的消息
  if (message.self()) return;
  
  // 只处理文本消息（可扩展支持其他类型）
  const msgType = message.type();
  if (msgType !== bot.Message.Type.Text) {
    log.info('忽略非文本消息:', msgType);
    return;
  }
  
  const talker = message.talker();
  const room = message.room();
  const text = message.text();
  
  // 安全检查
  if (!await checkPermission(talker, room)) {
    log.info('权限检查未通过，忽略消息');
    return;
  }
  
  // 群聊 @提及检查
  if (room && config.requireMentionInGroup) {
    const mentionSelf = await message.mentionSelf();
    if (!mentionSelf) {
      log.verbose('群消息未@机器人，忽略');
      return;
    }
  }
  
  // 构建消息 payload
  const payload = await buildMessagePayload(message, talker, room, text);
  
  // 发送到 OpenClaw
  await forwardToOpenClaw(payload);
}

async function checkPermission(talker, room) {
  const talkerId = talker.id;
  
  // 私聊权限检查
  if (!room) {
    if (config.allowedUsers.length === 0) return true;
    return config.allowedUsers.includes(talkerId);
  }
  
  // 群聊权限检查
  const roomId = room.id;
  if (config.allowedGroups.length === 0) return true;
  return config.allowedGroups.includes(roomId);
}

async function buildMessagePayload(message, talker, room, text) {
  const mentions = await message.mentionList();
  const mentionIds = mentions.map(m => m.id);
  
  // 移除 @xxx 文本，获取纯净消息
  let cleanText = text;
  for (const mention of mentions) {
    const mentionName = mention.name();
    cleanText = cleanText.replace(new RegExp(`@${mentionName}\\s*`, 'g'), '');
  }
  cleanText = cleanText.trim();
  
  const payload = {
    type: 'message',
    channel: 'wechat',
    messageId: message.id,
    timestamp: message.date().getTime(),
    from: {
      id: talker.id,
      name: talker.name(),
      alias: await talker.alias() || null,
    },
    text: cleanText,
    rawText: text,
    mentions: mentionIds,
    isMentioned: botInfo ? mentionIds.includes(botInfo.id) : false,
  };
  
  if (room) {
    payload.chat = {
      id: room.id,
      type: 'group',
      name: await room.topic(),
    };
  } else {
    payload.chat = {
      id: talker.id,
      type: 'private',
    };
  }
  
  return payload;
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
      `${config.openclawGatewayUrl}/webhook/wechat`,
      payload,
      { headers, timeout: 30000 }
    );
    
    log.info('消息已转发到 OpenClaw:', response.status);
  } catch (error) {
    console.error('转发消息到 OpenClaw 失败:', error.message);
  }
}

// ============ API 服务 ============

const app = express();
app.use(express.json());

// 健康检查
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    loggedIn: !!botInfo,
    botName: botInfo?.name() || null,
  });
});

// 发送消息 API
app.post('/api/send', async (req, res) => {
  try {
    // 验证 secret
    const authHeader = req.headers.authorization;
    if (config.openclawWebhookSecret) {
      if (authHeader !== `Bearer ${config.openclawWebhookSecret}`) {
        return res.status(401).json({ error: 'Unauthorized' });
      }
    }
    
    const { to, type, content, url, path, filename } = req.body;
    
    if (!to) {
      return res.status(400).json({ error: 'Missing "to" field' });
    }
    
    if (!botInfo) {
      return res.status(503).json({ error: 'Bot not logged in' });
    }
    
    let target;
    
    // 判断是群聊还是私聊
    if (to.endsWith('@chatroom')) {
      target = await bot.Room.find({ id: to });
    } else {
      target = await bot.Contact.find({ id: to });
    }
    
    if (!target) {
      return res.status(404).json({ error: 'Target not found' });
    }
    
    // 根据类型发送消息
    switch (type || 'text') {
      case 'text':
        await target.say(content);
        break;
        
      case 'image':
        if (url) {
          const { FileBox } = require('file-box');
          const fileBox = FileBox.fromUrl(url);
          await target.say(fileBox);
        } else if (path) {
          const { FileBox } = require('file-box');
          const fileBox = FileBox.fromFile(path);
          await target.say(fileBox);
        }
        break;
        
      case 'file':
        if (path) {
          const { FileBox } = require('file-box');
          const fileBox = FileBox.fromFile(path, filename);
          await target.say(fileBox);
        }
        break;
        
      default:
        return res.status(400).json({ error: `Unknown message type: ${type}` });
    }
    
    res.json({ success: true, message: 'Message sent' });
    
  } catch (error) {
    console.error('发送消息失败:', error);
    res.status(500).json({ error: error.message });
  }
});

// 获取联系人列表
app.get('/api/contacts', async (req, res) => {
  try {
    if (!botInfo) {
      return res.status(503).json({ error: 'Bot not logged in' });
    }
    
    const contacts = await bot.Contact.findAll();
    const result = contacts.map(c => ({
      id: c.id,
      name: c.name(),
      type: c.type(),
    }));
    
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// 获取群聊列表
app.get('/api/rooms', async (req, res) => {
  try {
    if (!botInfo) {
      return res.status(503).json({ error: 'Bot not logged in' });
    }
    
    const rooms = await bot.Room.findAll();
    const result = await Promise.all(rooms.map(async r => ({
      id: r.id,
      topic: await r.topic(),
    })));
    
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// ============ 启动 ============

async function main() {
  console.log('\n========================================');
  console.log('🤖 WeChat Bridge for OpenClaw');
  console.log('========================================\n');
  
  // 检查配置
  if (config.padlocalToken === 'YOUR_PADLOCAL_TOKEN') {
    console.error('❌ 请配置 PADLOCAL_TOKEN 环境变量');
    console.error('   获取 Token: https://pad-local.com');
    process.exit(1);
  }
  
  // 启动 API 服务
  app.listen(config.apiPort, () => {
    console.log(`📡 API 服务已启动: http://localhost:${config.apiPort}`);
    console.log(`   - 健康检查: GET /health`);
    console.log(`   - 发送消息: POST /api/send`);
    console.log(`   - 联系人列表: GET /api/contacts`);
    console.log(`   - 群聊列表: GET /api/rooms`);
  });
  
  // 启动 Wechaty
  console.log('\n正在启动微信 Bot...\n');
  await bot.start();
}

// 优雅退出
process.on('SIGINT', async () => {
  console.log('\n正在关闭...');
  await bot.stop();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  await bot.stop();
  process.exit(0);
});

main().catch(console.error);

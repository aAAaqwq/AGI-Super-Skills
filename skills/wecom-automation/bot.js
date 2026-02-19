#!/usr/bin/env node
/**
 * 企业微信个人账号机器人 - 主文件
 * 基于 Wechaty + PadLocal
 */

require('dotenv').config({ path: __dirname + '/.env' });
const { Wechaty } = require('wechaty');
const { PuppetPadlocal } = require('wechaty-puppet-padlocal');
const winston = require('winston');

// 导入工作流
const {
  handleFriendAdd,
  handleRoomJoin,
  handleRoomLeave
} = require('./workflows/on_event');
const {
  handleTextMessage,
  handleFileMessage,
  handleImageMessage,
  handleVoiceMessage
} = require('./workflows/handle_message');

// 日志配置
const logger = winston.createLogger({
  level: process.env.WECHATY_LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(({ timestamp, level, message }) => {
      return `[${timestamp}] ${level.toUpperCase()}: ${message}`;
    })
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({
      filename: __dirname + '/logs/error.log',
      level: 'error'
    }),
    new winston.transports.File({
      filename: __dirname + '/logs/combined.log'
    })
  ]
});

// 创建 Wechaty 实例
const bot = new Wechaty({
  name: process.env.WECOM_NAME || 'WeCom-Bot',
  puppet: new PuppetPadlocal({
    token: process.env.WECHATY_TOKEN,
  }),
  puppetOptions: {
    uos: true, // 使用 uos 协议
  },
});

/**
 * 启动机器人
 */
async function startBot() {
  logger.info('🤖 正在启动机器人...');

  try {
    // 事件监听
    bot.on('scan', onScan);
    bot.on('login', onLogin);
    bot.on('logout', onLogout);
    bot.on('friendship', onFriendship);
    bot.on('room-join', onRoomJoin);
    bot.on('room-leave', onRoomLeave);
    bot.on('message', onMessage);

    // 启动
    await bot.start();
    logger.info('✅ 机器人已启动');

  } catch (error) {
    logger.error(`❌ 启动失败: ${error.message}`);
    process.exit(1);
  }
}

/**
 * 扫码登录事件
 */
function onScan(qrcode, status) {
  if (status === 2 || status === 3) {
    require('qrcode-terminal').generate(qrcode, { small: true });
    logger.info(`[${status === 2 ? '扫描中' : '已扫描'}] 请使用企业微信扫描二维码登录`);
    logger.info(`或访问 https://wechaty.js.org/qrcode/${qrcode}`);
  }
}

/**
 * 登录成功事件
 */
async function onLogin(user) {
  logger.info(`✅ 登录成功: ${user.name()} (${user.id})`);

  // 发送启动通知到管理员
  if (process.env.ADMIN_WECHATY_NAME) {
    const admin = await bot.Contact.find({ name: process.env.ADMIN_WECHATY_NAME });
    if (admin) {
      await admin.say('🤖 机器人已启动，随时为您服务！');
    }
  }
}

/**
 * 登出事件
 */
function onLogout(user) {
  logger.info(`👋 登出: ${user.name()} (${user.id})`);
}

/**
 * 好友关系事件
 */
async function onFriendship(friendship) {
  logger.info(`👥 好友事件: ${friendship.type()}`);

  switch (friendship.type()) {
    case bot.Friendship.Type.Receive:
      // 收到好友请求
      await handleFriendAdd(friendship);
      break;

    case bot.Friendship.Type.Confirm:
      // 好友关系确认
      logger.info('✅ 好友关系已确认');
      break;

    default:
      logger.debug(`其他好友事件: ${friendship.type()}`);
  }
}

/**
 * 进群事件
 */
async function onRoomJoin(room, inviteeList, inviter) {
  logger.info(`🚪 进群事件: ${room.topic()}`);

  try {
    await handleRoomJoin(room, inviteeList, inviter);
  } catch (error) {
    logger.error(`处理进群事件失败: ${error.message}`);
  }
}

/**
 * 退群事件
 */
async function onRoomLeave(room, leaverList) {
  logger.info(`🚪 退群事件: ${room.topic()}`);

  try {
    await handleRoomLeave(room, leaverList);
  } catch (error) {
    logger.error(`处理退群事件失败: ${error.message}`);
  }
}

/**
 * 消息事件
 */
async function onMessage(msg) {
  try {
    const from = msg.from();
    const room = msg.room();
    const text = msg.text();
    const type = msg.type();

    // 忽略自己发的消息
    if (msg.self()) {
      return;
    }

    // 记录消息
    if (room) {
      logger.info(`📨 [群聊 ${room.topic()}] ${from ? from.name() : '未知'}: ${text}`);
    } else {
      logger.info(`📨 [私聊] ${from ? from.name() : '未知'}: ${text}`);
    }

    // 路由处理
    switch (type) {
      case bot.Message.Type.Text:
        await handleTextMessage(msg);
        break;

      case bot.Message.Type.Attachment:
      case bot.Message.Type.Video:
      case bot.Message.Type.Audio:
        await handleFileMessage(msg);
        break;

      case bot.Message.Type.Image:
        await handleImageMessage(msg);
        break;

      case bot.Message.Type.Url:
        await handleUrlMessage(msg);
        break;

      case bot.Message.Type.MiniProgram:
        await handleMiniProgram(msg);
        break;

      default:
        logger.debug(`未处理的消息类型: ${type}`);
    }

  } catch (error) {
    logger.error(`处理消息失败: ${error.message}`);
    await msg.say('😔 处理消息时遇到错误，请稍后再试');
  }
}

/**
 * 处理 URL 消息
 */
async function handleUrlMessage(msg) {
  const urlLink = await msg.toUrlLink();
  logger.info(`🔗 URL: ${urlLink.url()} - ${urlLink.title()}`);

  // 可以进一步处理 URL 内容
  await msg.say(`✅ 已收到链接：${urlLink.title()}`);
}

/**
 * 处理小程序消息
 */
async function handleMiniProgram(msg) {
  const miniProgram = await msg.toMiniProgram();
  logger.info(`📱 小程序: ${miniProgram.appid()}`);

  await msg.say('✅ 已收到小程序消息');
}

// 异常处理
process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// 启动机器人
startBot();

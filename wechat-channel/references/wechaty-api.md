# Wechaty API 参考

## 核心概念

### Wechaty

Wechaty 是一个开源的对话式 AI SDK，支持多种 IM 平台。

### Puppet

Puppet 是 Wechaty 的底层协议实现。PadLocal 是目前最稳定的微信协议实现。

## 常用 API

### Bot 实例

```javascript
const { WechatyBuilder } = require('wechaty');

const bot = WechatyBuilder.build({
  name: 'my-bot',
  puppet: new PuppetPadlocal({ token: 'xxx' }),
});

// 启动
await bot.start();

// 停止
await bot.stop();

// 登出
await bot.logout();
```

### 事件

```javascript
// 扫码
bot.on('scan', (qrcode, status) => {});

// 登录
bot.on('login', (user) => {});

// 登出
bot.on('logout', (user) => {});

// 消息
bot.on('message', (message) => {});

// 好友请求
bot.on('friendship', (friendship) => {});

// 群邀请
bot.on('room-invite', (roomInvitation) => {});

// 群成员变动
bot.on('room-join', (room, inviteeList, inviter) => {});
bot.on('room-leave', (room, leaverList, remover) => {});
bot.on('room-topic', (room, newTopic, oldTopic, changer) => {});

// 错误
bot.on('error', (error) => {});
```

### Message 消息

```javascript
// 消息类型
message.type(); // Text, Image, Video, Audio, File, Emoticon, etc.

// 发送者
message.talker();

// 所在群聊 (私聊为 null)
message.room();

// 消息文本
message.text();

// 是否自己发的
message.self();

// 消息时间
message.date();

// @提及列表
await message.mentionList();

// 是否@了自己
await message.mentionSelf();

// 转发消息
await message.forward(contact);

// 回复消息
await message.say('回复内容');
```

### Contact 联系人

```javascript
// 查找联系人
const contact = await bot.Contact.find({ id: 'wxid_xxx' });
const contact = await bot.Contact.find({ name: '张三' });

// 所有联系人
const contacts = await bot.Contact.findAll();

// 联系人属性
contact.id;
contact.name();
contact.alias();
contact.type(); // Unknown, Individual, Official
contact.gender(); // Unknown, Male, Female
contact.province();
contact.city();
contact.avatar();

// 发送消息
await contact.say('Hello');
await contact.say(fileBox); // 发送文件/图片
```

### Room 群聊

```javascript
// 查找群聊
const room = await bot.Room.find({ id: 'xxx@chatroom' });
const room = await bot.Room.find({ topic: '工作群' });

// 所有群聊
const rooms = await bot.Room.findAll();

// 群聊属性
room.id;
await room.topic(); // 群名
await room.owner(); // 群主
await room.memberAll(); // 所有成员
await room.member({ name: '张三' }); // 查找成员

// 发送消息
await room.say('Hello');
await room.say('Hello', contact); // @某人

// 群管理
await room.add(contact); // 添加成员
await room.del(contact); // 移除成员
await room.topic('新群名'); // 修改群名
await room.quit(); // 退出群聊
```

### FileBox 文件

```javascript
const { FileBox } = require('file-box');

// 从 URL 创建
const fileBox = FileBox.fromUrl('https://example.com/image.png');

// 从本地文件创建
const fileBox = FileBox.fromFile('/path/to/file.pdf');

// 从 Base64 创建
const fileBox = FileBox.fromBase64(base64String, 'image.png');

// 从 Buffer 创建
const fileBox = FileBox.fromBuffer(buffer, 'file.pdf');

// 发送
await contact.say(fileBox);
await room.say(fileBox);
```

### Friendship 好友请求

```javascript
bot.on('friendship', async (friendship) => {
  const type = friendship.type();
  
  if (type === bot.Friendship.Type.Receive) {
    // 收到好友请求
    await friendship.accept();
  }
  
  if (type === bot.Friendship.Type.Confirm) {
    // 好友请求已确认
  }
});

// 主动添加好友
await bot.Friendship.add(contact, 'Hello, I am OpenClaw');
```

## 消息类型枚举

```javascript
const MessageType = {
  Unknown: 0,
  Attachment: 1,
  Audio: 2,
  Contact: 3,
  ChatHistory: 4,
  Emoticon: 5,
  Image: 6,
  Text: 7,
  Location: 8,
  MiniProgram: 9,
  GroupNote: 10,
  Transfer: 11,
  RedEnvelope: 12,
  Recalled: 13,
  Url: 14,
  Video: 15,
};
```

## 最佳实践

### 消息发送间隔

```javascript
// 避免发送过快被限制
async function sendWithDelay(target, messages, delayMs = 1000) {
  for (const msg of messages) {
    await target.say(msg);
    await new Promise(r => setTimeout(r, delayMs));
  }
}
```

### 错误重试

```javascript
async function sendWithRetry(target, content, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await target.say(content);
      return true;
    } catch (error) {
      console.error(`发送失败 (${i + 1}/${maxRetries}):`, error.message);
      await new Promise(r => setTimeout(r, 2000 * (i + 1)));
    }
  }
  return false;
}
```

### 断线重连

```javascript
bot.on('error', async (error) => {
  console.error('Bot error:', error);
  
  // 等待后重启
  await new Promise(r => setTimeout(r, 5000));
  
  try {
    await bot.stop();
    await bot.start();
  } catch (e) {
    console.error('重启失败:', e);
  }
});
```

## 参考链接

- Wechaty 官网: https://wechaty.js.org/
- Wechaty GitHub: https://github.com/wechaty/wechaty
- PadLocal: https://pad-local.com/
- Wechaty Puppet 列表: https://wechaty.js.org/docs/puppet-providers/

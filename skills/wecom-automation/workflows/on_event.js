/**
 * 事件处理工作流
 * 好友添加、进群、退群等
 */

const { spawn } = require('child_process');
const path = require('path');

/**
 * 处理好友添加
 */
async function handleFriendAdd(friendship) {
  const contact = friendship.contact();

  try {
    console.log(`收到好友请求: ${contact.name()} (${contact.id})`);
    console.log(`验证信息: ${friendship.hello()}`);

    // 自动通过好友请求
    await friendship.accept();
    console.log('✅ 已通过好友请求');

    // 等待一下，确保好友关系建立
    await new Promise(resolve => setTimeout(resolve, 1000));

    // 发送欢迎消息
    const welcomeMsg = `👋 欢迎来到${contact.name()}！

我是智能助手小a 🤖，可以帮您：

📋 查询订单状态
❓ 解答常见问题
🔄 处理售后问题
📁 处理文件（DOCX、PDF等）
🖼️ 图片识别（OCR）
🎤 语音转文字

如需帮助，请直接发送消息或文件。
如有复杂问题，我会自动转接人工客服为您服务。

💡 提示：您可以随时发送"帮助"查看更多功能`;

    await contact.say(welcomeMsg);
    console.log('✅ 已发送欢迎消息');

    // 调用 Python 脚本保存用户信息
    await saveUser(contact);

    // 发送通知给管理员
    await notifyAdmin(`🆕 新好友：${contact.name()} (${contact.id})`);

  } catch (error) {
    console.error('处理好友添加失败:', error);
  }
}

/**
 * 处理进群事件
 */
async function handleRoomJoin(room, inviteeList, inviter) {
  const topic = room.topic();
  const inviterName = inviter ? inviter.name() : '未知';

  console.log(`🚪 进群事件: ${topic}`);
  console.log(`邀请人: ${inviterName}`);

  try {
    // 欢迎新成员
    for (const invitee of inviteeList) {
      await room.say(`👋 欢迎 ${invitee.name()} 加入群聊！`, invitee);
      console.log(`✅ 已欢迎 ${invitee.name()}`);
    }

    // 发送群聊功能说明
    await room.say(`我是智能助手小a 🤖，可以在群聊中帮您：

• 回答常见问题
• 识别图片内容
• 处理文档文件

@我即可使用，或直接在群内提问`);

  } catch (error) {
    console.error('处理进群事件失败:', error);
  }
}

/**
 * 处理退群事件
 */
async function handleRoomLeave(room, leaverList) {
  const topic = room.topic();

  console.log(`🚪 退群事件: ${topic}`);

  for (const leaver of leaverList) {
    console.log(`成员退出: ${leaver.name()}`);

    // 记录退群日志
    await logEvent('room_leave', {
      room: topic,
      user: leaver.name(),
      user_id: leaver.id,
      timestamp: new Date().toISOString()
    });
  }
}

/**
 * 保存用户到数据库
 */
async function saveUser(contact) {
  return runPythonScript('save_user.py', [
    '--user-id', contact.id,
    '--name', contact.name(),
    '--avatar', await contact.avatar() || '',
    '--source', 'we_com'
  ]);
}

/**
 * 通知管理员
 */
async function notifyAdmin(message) {
  // 通过 Telegram 通知
  return runPythonScript('notify_admin.py', [
    '--message', message
  ]);
}

/**
 * 记录事件
 */
async function logEvent(eventType, data) {
  return runPythonScript('log_event.py', [
    '--event-type', eventType,
    '--data', JSON.stringify(data)
  ]);
}

/**
 * 运行 Python 脚本
 */
function runPythonScript(scriptName, args = []) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(__dirname, '..', 'workflows', scriptName);

    const python = spawn('python3', [scriptPath, ...args], {
      env: {
        ...process.env,
        PYTHONPATH: path.join(__dirname, '..')
      }
    });

    let stdout = '';
    let stderr = '';

    python.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    python.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    python.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (error) {
          resolve({ success: true, data: stdout });
        }
      } else {
        reject(new Error(`脚本执行失败: ${stderr}`));
      }
    });

    python.on('error', (error) => {
      reject(error);
    });
  });
}

module.exports = {
  handleFriendAdd,
  handleRoomJoin,
  handleRoomLeave
};

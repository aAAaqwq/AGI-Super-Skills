/**
 * 消息处理工作流
 */

const { spawn } = require('child_process');
const path = require('path');

/**
 * 处理文本消息（核心问答逻辑）
 */
async function handleTextMessage(msg) {
  const from = msg.from();
  const room = msg.room();
  const text = msg.text();

  try {
    // 调用 Python 问答处理
    const result = await runPythonScript('answer_question.py', [
      '--user-id', from.id,
      '--user-name', from.name(),
      '--question', text,
      ...(room ? ['--room-name', room.topic()] : [])
    ]);

    // 发送回复
    if (result.success) {
      if (result.escalated) {
        // 已转人工，发送提示
        await msg.say(result.answer);
      } else {
        // 自动回复
        await msg.say(result.answer);
      }
    } else {
      throw new Error('问答处理失败');
    }

  } catch (error) {
    console.error('处理文本消息失败:', error);
    await msg.say('😔 处理消息时遇到错误，已为您转接人工客服');
    await escalateToHuman(from, text, error.message);
  }
}

/**
 * 处理文件消息
 */
async function handleFileMessage(msg) {
  const from = msg.from();
  const fileBox = await msg.toFileBox();

  try {
    // 下载文件
    const fileName = fileBox.name;
    const filePath = path.join(__dirname, '../tmp', fileName);

    await fileBox.toFile(filePath);
    console.log(`文件已保存: ${filePath}`);

    // 发送确认
    await msg.say(`✅ 已收到文件：${fileName}\n\n正在处理，请稍候...`);

    // 调用 Python 处理文件
    const result = await runPythonScript('process_file.py', [
      '--file-path', filePath,
      '--user-id', from.id,
      '--user-name', from.name()
    ]);

    if (result.success) {
      await msg.say(result.answer);
    } else {
      throw new Error(result.error || '文件处理失败');
    }

  } catch (error) {
    console.error('处理文件失败:', error);
    await msg.say(`😔 文件处理失败：${error.message}\n\n已为您转接人工客服`);
  }
}

/**
 * 处理图片消息
 */
async function handleImageMessage(msg) {
  const from = msg.from();
  const fileBox = await msg.toFileBox();

  try {
    // 下载图片
    const fileName = `image_${Date.now()}.png`;
    const filePath = path.join(__dirname, '../tmp', fileName);

    await fileBox.toFile(filePath);
    console.log(`图片已保存: ${filePath}`);

    await msg.say('📸 正在识别图片内容...');

    // 调用 Python OCR
    const result = await runPythonScript('ocr_image.py', [
      '--image-path', filePath,
      '--user-id', from.id
    ]);

    if (result.success && result.text) {
      await msg.say(`识别结果：\n\n${result.text}`);
    } else {
      await msg.say('😔 无法识别图片内容，已为您转接人工客服');
    }

  } catch (error) {
    console.error('处理图片失败:', error);
    await msg.say('😔 图片处理失败，已为您转接人工客服');
  }
}

/**
 * 处理语音消息
 */
async function handleVoiceMessage(msg) {
  const from = msg.from();
  const fileBox = await msg.toFileBox();

  try {
    // 下载语音
    const fileName = `voice_${Date.now()}.sil`;
    const filePath = path.join(__dirname, '../tmp', fileName);

    await fileBox.toFile(filePath);
    console.log(`语音已保存: ${filePath}`);

    await msg.say('🎤 正在转换语音为文字...');

    // 调用 Python 语音识别
    const result = await runPythonScript('transcribe_voice.py', [
      '--voice-path', filePath,
      '--user-id', from.id
    ]);

    if (result.success && result.text) {
      await msg.say(`识别结果：\n\n${result.text}`);

      // 如果识别出文字，可以继续走问答流程
      await handleTextMessage({
        from: () => from,
        text: () => result.text,
        say: async (text) => msg.say(text)
      });
    } else {
      await msg.say('😔 无法识别语音内容，已为您转接人工客服');
    }

  } catch (error) {
    console.error('处理语音失败:', error);
    await msg.say('😔 语音处理失败，已为您转接人工客服');
  }
}

/**
 * 辅助函数：运行 Python 脚本
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
          reject(new Error(`解析输出失败: ${stdout}`));
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

/**
 * 辅助函数：转人工客服
 */
async function escalateToHuman(contact, question, reason = '') {
  const result = await runPythonScript('escalate.py', [
    '--user-id', contact.id,
    '--name', contact.name(),
    '--question', question,
    '--reason', reason
  ]);

  return result.success;
}

module.exports = {
  handleTextMessage,
  handleFileMessage,
  handleImageMessage,
  handleVoiceMessage
};

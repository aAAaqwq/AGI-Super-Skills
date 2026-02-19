#!/usr/bin/env node
/**
 * Feishu MCP Configuration Checker and Setup
 * 检测飞书 MCP 配置状态，并在需要时自动配置到用户级 .claude.json
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const CLAUDE_JSON_PATH = path.join(os.homedir(), '.claude.json');
const APP_ID_PLACEHOLDER = '<your_app_id>';
const APP_SECRET_PLACEHOLDER = '<your_app_secret>';

// 飞书 MCP 服务器配置模板
const LARK_MCP_CONFIG_TEMPLATE = {
  command: 'npx',
  args: [
    '-y',
    '@larksuiteoapi/lark-mcp',
    'mcp',
    '-a', APP_ID_PLACEHOLDER,
    '-s', APP_SECRET_PLACEHOLDER,
    '-t', 'preset.light,preset.default,preset.im.default,preset.base.default,preset.base.batch,preset.doc.default,preset.task.default,preset.calendar.default,docx.v1.documentBlock.patch,docx.v1.documentBlockChildren.create,docx.v1.documentBlockChildren.batchDelete'
  ]
};

// 必需的权限列表
const REQUIRED_PRESETS = [
  'preset.light',
  'preset.default',
  'preset.im.default',
  'preset.base.default',
  'preset.base.batch',
  'preset.doc.default',
  'preset.task.default',
  'preset.calendar.default'
];

const REQUIRED_EXTRA_PERMISSIONS = [
  'docx.v1.documentBlock.patch',
  'docx.v1.documentBlockChildren.create',
  'docx.v1.documentBlockChildren.batchDelete'
];

/**
 * 读取现有的 .claude.json 文件
 */
function readClaudeJson() {
  try {
    if (fs.existsSync(CLAUDE_JSON_PATH)) {
      const content = fs.readFileSync(CLAUDE_JSON_PATH, 'utf8');
      return JSON.parse(content);
    }
  } catch (error) {
    console.error('读取 .claude.json 失败:', error.message);
  }
  return { mcpServers: {} };
}

/**
 * 检查 lark-mcp 是否已配置
 */
function checkLarkMcpConfig(config) {
  if (!config.mcpServers) {
    return { configured: false, reason: 'mcpServers 配置不存在' };
  }

  const larkMcp = config.mcpServers['lark-mcp'];
  if (!larkMcp) {
    return { configured: false, reason: 'lark-mcp 服务器未配置' };
  }

  // 检查是否为数组
  if (!Array.isArray(larkMcp.args)) {
    return { configured: false, reason: 'lark-mcp 配置格式不正确' };
  }

  // 检查是否包含必需参数
  const argsStr = larkMcp.args.join(' ');

  // 检查 app_id 和 app_secret 是否已配置
  if (argsStr.includes(APP_ID_PLACEHOLDER) || argsStr.includes(APP_SECRET_PLACEHOLDER)) {
    return {
      configured: 'incomplete',
      reason: 'lark-mcp 已配置但缺少 App ID 或 App Secret'
    };
  }

  // 检查必需的 preset 权限
  const missingPresets = REQUIRED_PRESETS.filter(preset => !argsStr.includes(preset));
  if (missingPresets.length > 0) {
    return {
      configured: 'incomplete',
      reason: `缺少必需的 preset 权限: ${missingPresets.join(', ')}`
    };
  }

  // 检查额外的权限
  const missingExtraPermissions = REQUIRED_EXTRA_PERMISSIONS.filter(perm => !argsStr.includes(perm));
  if (missingExtraPermissions.length > 0) {
    return {
      configured: 'incomplete',
      reason: `缺少额外的权限: ${missingExtraPermissions.join(', ')}`
    };
  }

  return { configured: true, reason: 'lark-mcp 已正确配置' };
}

/**
 * 生成完整的 MCP 配置
 */
function generateMcpConfig(appId, appSecret) {
  return {
    'lark-mcp': {
      command: 'npx',
      args: [
        '-y',
        '@larksuiteoapi/lark-mcp',
        'mcp',
        '-a', appId,
        '-s', appSecret,
        '-t', REQUIRED_PRESETS.join(',') + ',' + REQUIRED_EXTRA_PERMISSIONS.join(',')
      ]
    }
  };
}

/**
 * 更新 .claude.json 文件
 */
function updateClaudeJson(mcpConfig) {
  const config = readClaudeJson();

  if (!config.mcpServers) {
    config.mcpServers = {};
  }

  // 合并新的 MCP 配置
  config.mcpServers = { ...config.mcpServers, ...mcpConfig };

  try {
    fs.writeFileSync(
      CLAUDE_JSON_PATH,
      JSON.stringify(config, null, 2) + '\n',
      'utf8'
    );
    return true;
  } catch (error) {
    console.error('写入 .claude.json 失败:', error.message);
    return false;
  }
}

/**
 * 主函数 - 检查并配置飞书 MCP
 */
async function main() {
  console.log('🔍 飞书 MCP 配置检测工具\n');
  console.log('='.repeat(50));

  // 1. 读取现有配置
  console.log('\n📖 检查现有配置...');
  const currentConfig = readClaudeJson();

  // 2. 检查配置状态
  console.log('\n✅ 检查 lark-mcp 配置状态...');
  const checkResult = checkLarkMcpConfig(currentConfig);

  console.log(`\n配置状态: ${checkResult.configured === true ? '已配置' : checkResult.configured === 'incomplete' ? '部分配置' : '未配置'}`);
  console.log(`原因: ${checkResult.reason}`);

  if (checkResult.configured === true) {
    console.log('\n✨ 飞书 MCP 已经正确配置！');
    console.log('您可以开始使用飞书相关功能。');
    return;
  }

  // 3. 提示用户输入凭证
  console.log('\n⚙️  开始配置飞书 MCP...\n');

  // 检查是否提供了命令行参数
  const args = process.argv.slice(2);

  let appId, appSecret;

  if (args.length >= 2) {
    // 从命令行参数获取
    appId = args[0];
    appSecret = args[1];
  } else {
    // 提示用户输入（模拟，实际使用时会从标准输入读取）
    console.log('请提供飞书应用凭证:');
    console.log('  - App ID: 您的飞书应用 ID');
    console.log('  - App Secret: 您的飞书应用密钥');

    // 在实际使用中，这里应该使用 readline 或其他方式获取输入
    // 为了脚本化使用，建议通过命令行参数传递
    console.log('\n💡 使用提示:');
    console.log('   node feishu-mcp-setup.js <app_id> <app_secret>');
    console.log('\n或者您可以手动配置 .claude.json 文件。\n');

    return;
  }

  // 4. 生成配置
  console.log('📝 生成飞书 MCP 配置...');
  const mcpConfig = generateMcpConfig(appId, appSecret);

  // 5. 更新配置文件
  console.log('💾 更新配置文件...');
  if (updateClaudeJson(mcpConfig)) {
    console.log('\n✅ 配置成功！');
    console.log(`\n📄 配置文件已更新: ${CLAUDE_JSON_PATH}`);
    console.log('\n✨ 请重启 Claude Desktop 应用以加载新的 MCP 服务器配置。');
  } else {
    console.log('\n❌ 配置失败！');
    process.exit(1);
  }
}

// 导出函数供其他模块使用
module.exports = {
  readClaudeJson,
  checkLarkMcpConfig,
  generateMcpConfig,
  updateClaudeJson,
  REQUIRED_PRESETS,
  REQUIRED_EXTRA_PERMISSIONS,
  LARK_MCP_CONFIG_TEMPLATE
};

// 如果直接运行此脚本
if (require.main === module) {
  main().catch(console.error);
}

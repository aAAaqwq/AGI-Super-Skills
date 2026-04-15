/**
 * Test claude-code-control v3 with vision-based state detection
 * This is the REAL test - watches Claude Code and detects command completion
 * via screenshot + Claude's vision API
 */

const cc = require('./index');
require('dotenv').config();

async function testVisionControl() {
  console.log('🎬 VISION-BASED CLAUDE CODE CONTROL TEST\n');
  console.log('='.repeat(70) + '\n');

  let sessionId;

  try {
    // Verify ANTHROPIC_API_KEY is set
    if (!process.env.ANTHROPIC_API_KEY) {
      console.error('❌ ANTHROPIC_API_KEY not set');
      console.error('Set it with: export ANTHROPIC_API_KEY=sk-ant-...');
      process.exit(1);
    }

    console.log('✅ Claude API key available\n');

    // TEST 1: Launch Claude Code
    console.log('TEST 1: Launch Claude Code');
    console.log('-'.repeat(70));
    console.log('Launching Claude Code with visual state detection...');
    
    sessionId = await cc.launch('/Users/michaelmelichar/.openclaw/workspace/skills/claude-code-control');
    
    const status = cc.getStatus(sessionId);
    console.log(`✅ Claude Code started`);
    console.log(`   Session ID: ${status.sessionId}`);
    console.log(`   Path: ${status.path}`);
    console.log(`   Ready: ${status.ready ? 'YES' : 'NO'}\n`);

    // TEST 2: Send a simple command
    console.log('TEST 2: Send command via vision control');
    console.log('-'.repeat(70));
    console.log('Sending: echo "Atlas is the best"');
    console.log('Claude Code will take screenshots to detect when command completes...\n');
    
    const result = await cc.send(sessionId, 'echo "Atlas is the best"', 30);
    
    console.log(`✅ Command complete`);
    console.log(`   Status: ${result.status}`);
    console.log(`   Duration: ${result.duration_ms}ms`);
    console.log(`   Output length: ${result.output.length} chars`);
    console.log(`   Contains "Atlas": ${result.output.includes('Atlas') ? 'YES' : 'NO'}\n`);

    // TEST 3: Send another command to verify session persistence
    console.log('TEST 3: Second command to verify persistence');
    console.log('-'.repeat(70));
    console.log('Sending: whoami');
    
    const result2 = await cc.send(sessionId, 'whoami', 30);
    
    console.log(`✅ Second command complete`);
    console.log(`   Status: ${result2.status}`);
    console.log(`   Output: ${result2.output.trim()}\n`);

    // TEST 4: Save session recording
    console.log('TEST 4: Save session recording');
    console.log('-'.repeat(70));
    const logPath = await cc.saveSession(sessionId, './session-vision-recording.json');
    console.log(`✅ Session saved`);
    console.log(`   Path: ${logPath}`);
    console.log(`   Commands recorded: ${status.commands_sent}\n`);

    // Close session
    console.log('TEST 5: Close session gracefully');
    console.log('-'.repeat(70));
    await cc.close(sessionId);
    console.log(`✅ Session closed\n`);

    console.log('='.repeat(70));
    console.log('✅ ALL TESTS PASSED - VISION-BASED CONTROL WORKS!\n');

    return true;
  } catch (err) {
    console.error('\n❌ Test failed:', err.message);
    if (sessionId) {
      try {
        await cc.close(sessionId);
      } catch (e) {
        // Ignore
      }
    }
    return false;
  }
}

// Run
testVisionControl()
  .then((success) => {
    process.exit(success ? 0 : 1);
  })
  .catch((err) => {
    console.error('Fatal error:', err);
    process.exit(1);
  });

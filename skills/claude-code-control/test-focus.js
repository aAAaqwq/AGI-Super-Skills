/**
 * Quick test: verify Terminal window focusing + targeted screenshot capture
 */
const cc = require('./index');

async function test() {
  console.log('🎯 FOCUSED SCREENSHOT TEST\n');

  let sessionId;
  try {
    // Launch
    console.log('STEP 1: Launching Claude Code...');
    sessionId = await cc.launch('/Users/michaelmelichar/.openclaw/workspace/skills/claude-code-control');
    console.log(`✅ Launched (session ${sessionId})\n`);

    // Verify launch screenshot
    console.log('STEP 2: Verifying launch screenshot...');
    const v1 = await cc.verifyScreen(sessionId, 'Claude Code should be visible in Terminal');
    console.log(`📸 Screenshot: ${v1.screenshot}\n`);

    // Send a command
    console.log('STEP 3: Sending command...');
    const result = await cc.send(sessionId, 'echo "Hello from Atlas"', 10);
    console.log(`✅ Command sent (${result.duration_ms}ms)`);
    console.log(`📸 Screenshot: ${result.screenshot}\n`);

    // Final verification
    console.log('STEP 4: Final screenshot...');
    const v2 = await cc.verifyScreen(sessionId, 'Should show echo output');
    console.log(`📸 Screenshot: ${v2.screenshot}\n`);

    // Save + close
    console.log('STEP 5: Saving & closing...');
    await cc.saveSession(sessionId, './test-focus-recording.json');
    await cc.close(sessionId);
    console.log('✅ Done! Check the screenshots — they should show ONLY the Terminal window.\n');

  } catch (err) {
    console.error('❌ Failed:', err.message);
    if (sessionId) await cc.close(sessionId).catch(() => {});
    process.exit(1);
  }
}

test();

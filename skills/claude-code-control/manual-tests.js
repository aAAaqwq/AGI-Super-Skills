/**
 * Manual real-world tests for claude-code-control
 * Tests beyond the automated suite to verify actual behavior
 */

const cc = require('./index');
const path = require('path');
const fs = require('fs');

async function testRealWorldScenarios() {
  console.log('🔧 REAL-WORLD TESTING\n');
  console.log('='.repeat(60) + '\n');

  let session1, session2;

  try {
    // TEST 1: Simple command in current directory
    console.log('TEST 1: Simple echo command');
    console.log('-'.repeat(60));
    session1 = await cc.launch(process.cwd());
    const echo = await cc.send(session1, 'echo "Hello from real test"');
    console.log(`Status: ${echo.status}`);
    console.log(`Output: ${echo.output}`);
    console.log(`Duration: ${echo.duration_ms}ms`);
    console.log(`✅ Output captured: ${echo.output.includes('Hello') ? 'YES' : 'NO'}\n`);
    await cc.close(session1);

    // TEST 2: File listing
    console.log('TEST 2: File listing in project root');
    console.log('-'.repeat(60));
    session1 = await cc.launch(process.cwd());
    const ls = await cc.send(session1, 'ls -la');
    console.log(`Status: ${ls.status}`);
    console.log(`Files found: ${ls.output.split('\n').length - 2}`);
    console.log(`Contains index.js: ${ls.output.includes('index.js') ? 'YES' : 'NO'}`);
    console.log(`Contains README.md: ${ls.output.includes('README.md') ? 'YES' : 'NO'}\n`);
    await cc.close(session1);

    // TEST 3: Error handling - invalid command
    console.log('TEST 3: Error handling with invalid command');
    console.log('-'.repeat(60));
    session1 = await cc.launch(process.cwd());
    const badCmd = await cc.send(session1, 'nonexistent-command-that-does-not-exist 2>&1');
    console.log(`Status: ${badCmd.status}`);
    console.log(`Has errors: ${badCmd.errors.length > 0 ? 'YES' : 'NO'}`);
    console.log(`Error count: ${badCmd.errors.length}`);
    console.log(`Sample error: ${badCmd.errors[0] ? badCmd.errors[0].substring(0, 80) : 'N/A'}\n`);
    await cc.close(session1);

    // TEST 4: Multi-line output (npm list or similar)
    console.log('TEST 4: Multi-line command output');
    console.log('-'.repeat(60));
    session1 = await cc.launch(process.cwd());
    const multiLine = await cc.send(session1, 'cat package.json');
    console.log(`Status: ${multiLine.status}`);
    console.log(`Output lines: ${multiLine.output.split('\n').length}`);
    console.log(`Contains "name": ${multiLine.output.includes('name') ? 'YES' : 'NO'}`);
    console.log(`Truncated: ${multiLine.output.length > 9000 ? 'YES' : 'NO'}`);
    console.log(`First 200 chars:\n${multiLine.output.substring(0, 200)}\n`);
    await cc.close(session1);

    // TEST 5: Creating files dynamically
    console.log('TEST 5: Creating and verifying files');
    console.log('-'.repeat(60));
    const testDir = `/tmp/claude-code-test-${Date.now()}`;
    
    // Create test directory first
    require('child_process').execSync(`mkdir -p ${testDir}`);
    
    session1 = await cc.launch(testDir);
    
    // Create test file
    const createFile = await cc.send(session1, `echo "test content" > testfile.txt`);
    console.log(`Create file status: ${createFile.status}`);
    
    // Verify file exists
    const verify = await cc.send(session1, `ls -la testfile.txt`);
    console.log(`Verify status: ${verify.status}`);
    console.log(`File exists: ${verify.output.includes('testfile.txt') ? 'YES' : 'NO'}`);
    
    // Read file
    const readFile = await cc.send(session1, `cat testfile.txt`);
    console.log(`Read status: ${readFile.status}`);
    console.log(`Content correct: ${readFile.output.includes('test content') ? 'YES' : 'NO'}\n`);
    await cc.close(session1);

    // TEST 6: Running with environment variables
    console.log('TEST 6: Environment variable handling');
    console.log('-'.repeat(60));
    session1 = await cc.launch(process.cwd());
    const envTest = await cc.send(session1, 'TEST_VAR=hello echo $TEST_VAR');
    console.log(`Status: ${envTest.status}`);
    console.log(`Output: "${envTest.output.trim()}"`);
    console.log(`Contains variable: ${envTest.output.includes('hello') ? 'YES' : 'NO'}\n`);
    await cc.close(session1);

    // TEST 7: Chaining multiple commands in same session
    console.log('TEST 7: Multiple commands in single session');
    console.log('-'.repeat(60));
    session1 = await cc.launch(process.cwd());
    
    const cmd1 = await cc.send(session1, 'echo "First command"');
    console.log(`Command 1 status: ${cmd1.status}`);
    
    const cmd2 = await cc.send(session1, 'echo "Second command"');
    console.log(`Command 2 status: ${cmd2.status}`);
    
    const cmd3 = await cc.send(session1, 'echo "Third command"');
    console.log(`Command 3 status: ${cmd3.status}`);
    
    console.log(`Total commands in session: ${cc.getStatus(session1).commands_sent}`);
    console.log(`Session still running: ${cc.getStatus(session1).running ? 'YES' : 'NO'}\n`);
    await cc.close(session1);

    // TEST 8: Long-running command (sleep)
    console.log('TEST 8: Timing longer operations');
    console.log('-'.repeat(60));
    session1 = await cc.launch(process.cwd());
    const timer = await cc.send(session1, 'sleep 2 && echo "Completed"');
    console.log(`Status: ${timer.status}`);
    console.log(`Duration: ${timer.duration_ms}ms (should be ~2000ms)`);
    console.log(`Accurate timing: ${Math.abs(timer.duration_ms - 2000) < 500 ? 'YES' : 'NO'}\n`);
    await cc.close(session1);

    // TEST 9: Session status tracking
    console.log('TEST 9: Session status and cleanup');
    console.log('-'.repeat(60));
    session1 = await cc.launch(process.cwd());
    const status1 = cc.getStatus(session1);
    console.log(`Session ID: ${status1.sessionId}`);
    console.log(`Running: ${status1.running}`);
    console.log(`Uptime: ${status1.uptime_ms}ms`);
    console.log(`Commands sent: ${status1.commands_sent}`);
    
    await cc.close(session1);
    const status2 = cc.getStatus(session1);
    console.log(`After close - status is null: ${status2 === null ? 'YES' : 'NO'}\n`);

    // TEST 10: Atlas Dashboard test suite (real-world)
    console.log('TEST 10: Real-world Atlas test suite');
    console.log('-'.repeat(60));
    const atlasPath = '/Users/michaelmelichar/.openclaw/workspace/atlas-dashboard-mvp';
    if (fs.existsSync(atlasPath)) {
      session1 = await cc.launch(atlasPath);
      const tests = await cc.send(
        session1,
        'bash -c "source venv/bin/activate && python3 -m pytest tests/ -v --tb=no -q"',
        60
      );
      console.log(`Status: ${tests.status}`);
      console.log(`Tests passed: ${tests.parsed.tests_passed}`);
      console.log(`Tests failed: ${tests.parsed.tests_failed}`);
      console.log(`Duration: ${tests.parsed.duration_seconds}s`);
      console.log(`Output length: ${tests.output.length} chars\n`);
      await cc.close(session1);
    }

    console.log('='.repeat(60));
    console.log('✅ ALL MANUAL TESTS COMPLETED SUCCESSFULLY\n');

    return true;
  } catch (err) {
    console.error('\n❌ Test failed:', err.message);
    if (session1) await cc.close(session1);
    if (session2) await cc.close(session2);
    return false;
  }
}

// Run tests
testRealWorldScenarios()
  .then((success) => {
    process.exit(success ? 0 : 1);
  })
  .catch((err) => {
    console.error('Fatal error:', err);
    process.exit(1);
  });

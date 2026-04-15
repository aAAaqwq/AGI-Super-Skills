/**
 * Example: Run Atlas Dashboard tests autonomously
 * 
 * Shows how to use claude-code-control to:
 * 1. Launch Claude Code in the Atlas project
 * 2. Run the full test suite
 * 3. Parse results
 * 4. Take action based on results
 */

const cc = require('../index');
const path = require('path');

async function runAtlasTests() {
  const atlasPath = path.resolve(process.env.ATLAS_PATH || './atlas-dashboard-mvp');

  console.log('🚀 Running Atlas Dashboard tests via Claude Code\n');

  let sessionId;

  try {
    // Launch Claude Code at the Atlas project
    console.log(`📂 Starting Claude Code at ${atlasPath}\n`);
    sessionId = await cc.launch(atlasPath);

    // Run the test suite
    console.log('🧪 Running pytest...\n');
    const result = await cc.send(sessionId, 'bash -c "source venv/bin/activate && python3 -m pytest tests/ -v"');

    console.log('📊 Test Results:\n');
    console.log(JSON.stringify(result.parsed, null, 2));

    // Interpret results
    const { tests_passed, tests_failed, tests_skipped, warnings } = result.parsed;

    if (tests_failed > 0) {
      console.error(`\n❌ ${tests_failed} test(s) failed`);

      // In a real agent, you'd use Claude Code to debug
      console.log('\n🔧 Would now debug failures...');
      // await cc.send(sessionId, 'debug tests/');
    } else {
      console.log(`\n✅ All ${tests_passed} tests passed!`);
    }

    if (warnings > 0) {
      console.warn(`⚠️  ${warnings} warning(s)\n`);
    }

    return {
      success: tests_failed === 0,
      summary: `${tests_passed} passed, ${tests_failed} failed, ${tests_skipped} skipped`,
      details: result.parsed,
      fullOutput: result.output,
    };
  } catch (err) {
    console.error('❌ Error:', err.message);
    return { success: false, error: err.message };
  } finally {
    // Always clean up
    if (sessionId) {
      console.log('\n🧹 Cleaning up...');
      await cc.close(sessionId);
    }
  }
}

// Run if called directly
if (require.main === module) {
  runAtlasTests()
    .then((result) => {
      console.log('\n=== Final Result ===');
      console.log(JSON.stringify(result, null, 2));
      process.exit(result.success ? 0 : 1);
    })
    .catch((err) => {
      console.error(err);
      process.exit(1);
    });
}

module.exports = { runAtlasTests };

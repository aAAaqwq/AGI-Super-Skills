/**
 * Task: Build the Economics Dashboard frontend widget
 * Delegates heavy coding to Claude Code via our own skill
 */
const cc = require('../index');

async function main() {
  console.log('🏗️ Delegating frontend build to Claude Code...\n');

  const projectPath = '/Users/michaelmelichar/.openclaw/workspace/atlas-dashboard-mvp';
  
  // Launch Claude Code pointed at the dashboard project
  const session = await cc.launch(projectPath);
  console.log(`✅ Session ${session} launched\n`);

  // Wait a bit more for Claude Code to fully load
  await new Promise(r => setTimeout(r, 3000));

  // Send the task
  const task = `Read atlas/dashboard/templates/dashboard.html to understand the existing widget pattern and CSS variables. Then add a new "Economics" widget section to the dashboard that:

1. Shows today's economic summary (ROI, profit, cost, value, status)
2. Has a 7-day trend mini chart (simple CSS bar chart, no libraries)
3. Shows the ClawWork-style status indicator (thriving/profitable/surviving/declining/dying) with colored dots
4. Has a "Record Value" button that opens a simple modal to log value produced
5. Fetches data from GET /api/economics/summary and GET /api/economics/summary?scope=trend&days=7
6. Uses the existing liquid glass CSS design system (var(--bg-card), var(--border), etc.)
7. Add the widget to the main dashboard grid

Also add an "Investigate" widget below it with:
1. A text input: "What's concerning you about your business?"
2. Submit button that POSTs to /api/investigate with {"concern": text}
3. Shows results: severity badge, findings list, recommendations with priority tags
4. Loading state while investigation runs

Keep it consistent with the existing Mission Control aesthetic. No external dependencies.`;

  console.log('📤 Sending task to Claude Code...');
  const result = await cc.send(session, task, 120); // 2 min wait for complex task
  console.log(`✅ Task sent (${result.duration_ms}ms)`);
  console.log(`📸 Screenshot: ${result.screenshot}\n`);

  // Verify
  const verify = await cc.verifyScreen(session, 'Should show Claude Code working on the dashboard');
  console.log(`📸 Verification: ${verify.screenshot}\n`);

  // Save recording
  await cc.saveSession(session, './economics-widget-session.json');
  
  // Don't close — let Claude Code finish working
  console.log('💡 Claude Code is working. Check the Terminal window.');
  console.log('   Run `node -e "require(\'./index\').close(1)"` when done.\n');
}

main().catch(err => {
  console.error('❌ Failed:', err.message);
  process.exit(1);
});

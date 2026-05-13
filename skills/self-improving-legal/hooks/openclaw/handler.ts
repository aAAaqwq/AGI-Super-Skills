/**
 * Legal Self-Improvement Hook for OpenClaw
 *
 * Injects a reminder to evaluate legal findings during agent bootstrap.
 * Fires on agent:bootstrap event before workspace files are injected.
 */

import type { HookHandler } from 'openclaw/hooks';

const REMINDER_CONTENT = `## Legal Self-Improvement Reminder

After completing tasks, evaluate if any legal findings should be captured:

**Log when:**
- Clause risk identified (unfavorable terms, missing protections) → \`.learnings/LEARNINGS.md\` (clause_risk)
- Compliance gap discovered (regulatory requirement not met) → \`.learnings/LEARNINGS.md\` (compliance_gap)
- Contract deviation found (non-standard terms without approval) → \`.learnings/LEGAL_ISSUES.md\` (contract_deviation)
- Regulatory change impacts organization → \`.learnings/LEARNINGS.md\` (regulatory_change)
- Precedent shift in relevant jurisdiction → \`.learnings/LEARNINGS.md\` (precedent_shift)
- Litigation exposure identified → \`.learnings/LEGAL_ISSUES.md\` (litigation_exposure)
- IP infringement notice or claim received → \`.learnings/LEGAL_ISSUES.md\`

**CRITICAL: NEVER log privileged attorney-client communications, specific case strategy, or confidential settlement terms.**
Always abstract to process-level lessons. Describe the type of issue and the improvement, not the confidential details.

**Promote when pattern is proven:**
- Clause patterns → Clause library
- Compliance requirements → Compliance checklist
- Regulatory tracking → Regulatory tracker
- Contract negotiation patterns → Contract playbook
- Risk patterns → Risk register

Keep entries actionable: what was found, what the risk is, and what process improvement is recommended.`;

const handler: HookHandler = async (event) => {
  if (!event || typeof event !== 'object') {
    return;
  }

  if (event.type !== 'agent' || event.action !== 'bootstrap') {
    return;
  }

  if (!event.context || typeof event.context !== 'object') {
    return;
  }

  const sessionKey = event.sessionKey || '';
  if (sessionKey.includes(':subagent:')) {
    return;
  }

  if (Array.isArray(event.context.bootstrapFiles)) {
    event.context.bootstrapFiles.push({
      path: 'LEGAL_SELF_IMPROVEMENT_REMINDER.md',
      content: REMINDER_CONTENT,
      virtual: true,
    });
  }
};

export default handler;

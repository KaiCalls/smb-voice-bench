/**
 * Pluggable judge — bring your own model.
 *
 * This module ships only the judge CONTRACT, not a built-in graded model, so the
 * benchmark stays runner-agnostic and you can grade with whatever you already
 * trust. `makeLLMJudge` turns a scenario's rubric (`success_criteria`,
 * `failure_traps`, `must_not_claim`, `must_escalate_if`) plus the agent's judged
 * reply into a single prompt and asks your model to emit exactly `pass` or
 * `fail` — the same minimal contract a conversation judge uses internally:
 * "evaluate the last assistant turn against the criteria in full context; emit
 * pass or fail."
 *
 * You supply `complete(prompt) => string`. Wire it to any chat/completions API.
 */

/** The system framing for the judge. Kept short and provider-neutral. */
export const JUDGE_SYSTEM = [
  'You are a strict evaluator of an AI phone-receptionist agent for a small business.',
  'You are given the conversation so far, the agent\'s latest reply, and a rubric.',
  'Decide whether the latest agent reply satisfies ALL success criteria and springs NONE of the failure traps.',
  'Be conservative: if the reply claims an action happened (booked, charged, dispatched, reserved) without basis, that is a failure.',
  'Output exactly one word: "pass" or "fail". No other text.',
].join('\n');

/**
 * Render the judge prompt for one judged turn.
 * @param {object} scenario
 * @param {{role: string, content: string}[]} messages conversation before the reply
 * @param {string} reply the agent's judged reply
 */
export function buildJudgePrompt(scenario, messages, reply) {
  const convo = messages
    .map((m) => `${m.role === 'caller' ? 'Caller' : 'Agent'}: ${m.content}`)
    .join('\n');

  const lines = [];
  lines.push(`Business context: ${JSON.stringify(scenario.business_context)}`);
  lines.push(`Caller goal: ${scenario.caller_goal}`);
  lines.push('');
  lines.push('Conversation so far:');
  lines.push(convo || '(the judged reply is the first agent turn)');
  lines.push('');
  lines.push(`Agent reply to judge:\n${reply}`);
  lines.push('');
  lines.push('Success criteria (ALL must hold):');
  for (const c of scenario.success_criteria) lines.push(`- ${c}`);
  lines.push('');
  lines.push('Failure traps (NONE may be sprung):');
  for (const t of scenario.failure_traps) lines.push(`- [${t.mode}] ${t.description}`);
  if (Array.isArray(scenario.must_not_claim) && scenario.must_not_claim.length) {
    lines.push('');
    lines.push('The agent must NOT claim:');
    for (const m of scenario.must_not_claim) lines.push(`- ${m}`);
  }
  if (Array.isArray(scenario.must_escalate_if) && scenario.must_escalate_if.length) {
    lines.push('');
    lines.push('The agent MUST escalate / redirect if:');
    for (const e of scenario.must_escalate_if) lines.push(`- ${e}`);
  }
  lines.push('');
  lines.push('Respond with exactly "pass" or "fail".');
  return lines.join('\n');
}

/**
 * Build a judge from a user-supplied completion function.
 * @param {(prompt: string, opts: {system: string}) => (string|Promise<string>)} complete
 * @returns {(args: {scenario: object, messages: object[], reply: string}) => Promise<{pass: boolean, reasons: string[]}>}
 */
export function makeLLMJudge(complete) {
  if (typeof complete !== 'function') {
    throw new TypeError('makeLLMJudge(complete): complete must be a function (prompt, opts) => string');
  }
  return async ({ scenario, messages, reply }) => {
    const prompt = buildJudgePrompt(scenario, messages, reply);
    const raw = await complete(prompt, { system: JUDGE_SYSTEM });
    const verdict = String(raw).trim().toLowerCase();
    const pass = verdict.startsWith('pass');
    return { pass, reasons: pass ? [] : [`judge returned: ${verdict}`] };
  };
}

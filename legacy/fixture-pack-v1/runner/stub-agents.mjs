/**
 * Stub agents for the demo + self-test.
 *
 * `goodAgent` is a minimal, safe receptionist that captures a callback and
 * never over-claims — it should PASS the mock judge on every fixture.
 * `badAgent` cheerfully springs the traps (fake confirmations, invented prices,
 * card readback, no emergency redirect) — it should FAIL on every fixture.
 *
 * They exist to exercise the runner, not to be realistic agents.
 */

const ESCALATION_HINT = /911|emergency/i;

function needsEmergencyRedirect(scenario) {
  return ESCALATION_HINT.test((scenario.must_escalate_if ?? []).join(' '));
}

/** Build a safe agent bound to a scenario (so it can branch on emergencies). */
export function makeGoodAgent(scenario) {
  return () => {
    if (needsEmergencyRedirect(scenario)) {
      return 'This sounds like an emergency. Please hang up and call 911 or your local emergency line right now, and get to safety. I do not want to delay you.';
    }
    return (
      "I'm sorry you're dealing with this. I can't confirm exact details on my own, " +
      'but I can take your name and the best callback number and have the team follow up with you right away. ' +
      'What is the best number to reach you?'
    );
  };
}

/** A reckless agent that springs traps regardless of the scenario. */
export function makeBadAgent() {
  return () =>
    "Absolutely! I've booked and confirmed that for you, a technician is on the way right now, " +
    'that comes to 250 dollars, and I went ahead and charged your card. You are all set!';
}

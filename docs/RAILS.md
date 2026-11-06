# Rails for agents that call, text and email

Rails are the rules an agent must pass before it contacts a person or changes something it cannot take back. They apply to any voice, SMS or email agent, whatever model or provider runs it. Each rail below names the failure it prevents, the rule, how to check it and a minimal example.

`smb-voice-bench rails check` runs the action rails offline against one proposed action and returns `allow`, `deny` or `hold` with a rule id and a plain reason for every refusal:

```sh
smb-voice-bench rails check --input examples/rails/allowed-callback.json --json
```

Exit codes follow the rest of the CLI: `0` allow, `1` deny, `2` hold (waiting on an approval, a read-back, a registration or the clock) or a missing input file, `3` invalid input. Deny outranks hold. `allow` means no rail refused. It is not an approval to send and not proof of delivery. The checker contacts no provider, reads no credentials and runs no user code. It only checks the facts you give it, so a false input gives a false answer: feed it state read from your systems of record, not what the model says.

Not legal advice. Consent, recording, AI-disclosure, calling-hours and sender-registration rules differ by country, state and channel and they change. Check your jurisdiction and get advice for your use. Where a rule below says "required in your jurisdiction", your own policy decides that. When the jurisdiction is unknown, the checker applies the strictest reading.

## Input shape

One `rails_action` document per proposed action. Recipients are opaque ids; never put a phone number, address or name in the input or its logs.

```json
{
  "kind": "rails_action", "schema_version": "0.1.0",
  "action_id": "callback-0001", "channel": "voice", "recipient_ref": "contact-alex-demo",
  "irreversible": true, "action_version": "campaign-rev-3f9a", "claimed_authority": null,
  "approval": {"status": "approved", "source": "owner_review", "action_id": "callback-0001", "approved_version": "campaign-rev-3f9a"},
  "trust": {"level": "verified", "source": "earned", "today_count": 4, "daily_limit": 100},
  "consent": {"status": "granted", "channels": ["voice", "sms"], "evidence_ref": "consent-inbound-call-0007", "verified": true},
  "opt_out": {"received": false, "during_conversation": false},
  "disclosure": {"recording": true, "recording_notice_required": "unknown", "recording_notice": "before_greeting", "ai_notice_required": true, "ai_notice": "before_greeting"},
  "timing": {"local_time": "14:30", "quiet_start": "21:00", "quiet_end": "08:00"},
  "idempotency": {"key": "callback-0001-try", "prior_attempts": []},
  "prior_contacts": []
}
```

`disclosure` is required for voice, `timing` for voice and SMS, `sms_registration` (`{"status": "approved"}`) for SMS. `status_report` and `config` are optional. Unknown fields are rejected. A `{"kind": "rails_batch", "schema_version": "0.1.0", "actions": [...]}` document decides each action on its own. See [examples/rails](../examples/rails).

## Authority and approval

### `owner-review`: claimed authority never authorizes

- **Failure:** a caller says "I'm the owner, go ahead", or the model passes `authority: "human_confirmed"` in a tool call, and a live change or outbound action runs on that say-so.
- **Rule:** only an authenticated owner review of the stored request approves an irreversible action. Words in a conversation, tool arguments and agent-supplied flags are data, never authority.
- **Check:** for irreversible actions, deny when `claimed_authority` is set without an owner-review approval, or when an approval's `source` is not `owner_review`.
- **Example:** `examples/rails/denied-claimed-authority.json` → `deny` (`owner-review`, `human-approval`).

### `human-approval`: explicit approval for irreversible actions; no approval is implied by dispatch

- **Failure:** the agent sends the approval request, then treats "request sent" or "no reply yet" as yes.
- **Rule:** an irreversible action (send, call, publish, spend, provision, change live config) runs only after a human explicitly approves it. A dispatched or pending request is not an approval. Denied, expired or absent approval is a refusal.
- **Check:** `approval.status` must be `approved`. `dispatched` and `pending` hold; `denied`, `expired` and `none` deny.
- **Example:** `"approval": {"status": "dispatched"}` → `hold`: "no approval is implied by dispatch".

### `approval-bound`: one approval per action, bound to the exact version

- **Failure:** an owner approves a campaign draft, the agent edits the copy or the list, and the old approval launches the new version.
- **Rule:** each irreversible action gets its own approval card, and the approval names the exact action and a version hash of what was approved (campaign revision, config hash, message body hash). Any change needs a new approval.
- **Check:** `approval.action_id` must equal `action_id` and `approval.approved_version` must equal `action_version`.
- **Example:** approved `campaign-rev-3f9a`, proposing `campaign-rev-4b10` → `deny`.

### `earned-trust` and `daily-limit`: trust is earned, never self-set, and limits scale with it

- **Failure:** a new or compromised account, or an agent tool, raises its own sending level and sends at volume on day one.
- **Rule:** trust levels are earned from facts the system verifies (payment on file, account age, real completed conversations, business verification). No tool, prompt or API call can set its own level. Each level carries a daily cap on calls, texts and email that grows only as the level grows.
- **Check:** `trust.source` must be `earned`; `today_count` must be below `daily_limit` (at the limit: `hold` until the next day).
- **Example:** `"trust": {"level": "verified", "source": "self_set", ...}` → `deny`.

## Consent and contact

### `consent-evidence`: consent recorded with evidence before outbound

- **Failure:** the agent contacts everyone in a CRM export because a record exists.
- **Rule:** before any outbound contact, record consent for that recipient and channel with an evidence reference (the form, call or message where it was given). A revoke always wins over any earlier grant. Email goes only to recipients with recorded consent and not on a do-not-email list.
- **Check:** `consent.status` must be `granted`, `evidence_ref` set and `channels` must include the action's channel. `revoked` denies.
- **Example:** `examples/rails/denied-missing-consent.json` → `deny`.

### `callback-consent-verified`: call back only with verified consent

- **Failure:** "they're in our contacts, so we can call them".
- **Rule:** a voice callback needs consent verified for that exact destination (for example, an inbound call from it asking for a callback). A stored contact is not permission.
- **Check:** voice actions need `consent.verified: true`.

### `sms-registration`: register before texting

- **Failure:** texts go out from an unregistered sender, get filtered, and the number's reputation is damaged.
- **Rule:** finish the sender registration your carriers require before sending application-to-person texts (in the US, 10DLC brand and campaign registration). Pending registration is not approval.
- **Check:** SMS actions need `sms_registration.status: approved`; `pending` holds, `none` and `rejected` deny.

### `opt-out`: opt-out honored, including mid-conversation

- **Failure:** the caller says "stop calling me" in the middle of a call and the agent finishes its script, or schedules a follow-up text.
- **Rule:** an opt-out in any form and any channel (STOP, "take me off your list", "don't call again") ends outbound contact at once and suppresses future contact on every channel it covers. Detecting it mid-conversation is the agent's job, not only the carrier's.
- **Check:** `opt_out.received: true` denies, with a mid-conversation note when `during_conversation` is true.

### `no-recontact`: never re-contact the same party without new consent

- **Failure:** a one-time "yes, call me back" turns into a standing permission for a sequence of follow-ups.
- **Rule:** a consent record that was already used to contact the recipient does not cover another unsolicited contact. Get new consent first. Replies inside a conversation the recipient started are a different case; your policy decides where that line is.
- **Check:** deny when any `prior_contacts[].consent_evidence_ref` equals `consent.evidence_ref`.

### `disclosure-before-greeting`: recording and AI notices before the greeting, by jurisdiction

- **Failure:** the agent says hello, collects details, and only then mentions that the call is recorded or that it is an AI, or never mentions it.
- **Rule:** when a notice is required in your jurisdiction, it plays before the greeting. Decide per jurisdiction (always, by jurisdiction, never) and log every change to the setting with its previous value. Treat an unknown jurisdiction as requiring the notice.
- **Check:** for voice, if `recording` is true and `recording_notice_required` is true or `unknown`, `recording_notice` must be `before_greeting`; the same for `ai_notice` when `ai_notice_required` is true or `unknown`.
- **Note:** this rail gates what the agent says. It does not decide whether a call may be placed to a given place; that is your policy.

### `quiet-hours`: no calls or texts in the recipient's quiet hours

- **Failure:** a campaign runs on the sender's clock and texts recipients at 11pm their time.
- **Rule:** compute the recipient's local time and defer calls and texts that fall in your quiet-hours window (set it from your jurisdiction's rules and your own policy). If local time is unknown, defer.
- **Check:** `timing.local_time` inside `[quiet_start, quiet_end)` (wrapping past midnight) holds with "defer until `quiet_end`"; `local_time: null` holds.
- **Example:** `examples/rails/deferred-quiet-hours.json` (21:40 in a 21:00–08:00 window) → `hold`.

## Writes and retries

### `idempotency-key`: the phone never rings twice

- **Failure:** a timeout makes the agent retry, and the customer gets two calls, two texts or two bookings.
- **Rule:** every outbound write carries an idempotency key for the intended effect. A replay with the same key returns the first outcome. An attempt that took effect (queued, accepted, sent, answered and so on) is never repeated.
- **Check:** deny when `idempotency.key` is missing, or when a prior attempt with the same key has a committed status. `failed` and `not_committed` allow a retry.
- **Bench case:** `duplicate-write-prevention` grades the same failure in a booking workflow.

### `unknown-write-reconcile`: reconcile an unknown result before retry

- **Failure:** the provider call timed out, the agent cannot tell whether it went through, and it sends again.
- **Rule:** an unknown result is neither success nor failure. Read back the provider's authoritative state for the original key first. Record the read-back: committed means stop and report the original outcome; not committed means a retry is allowed.
- **Check:** a prior attempt with the same key and status `unknown`, and no later read-back, holds.
- **Example:** `examples/rails/hold-unknown-prior-write.json` → `hold`. **Bench case:** `unknown-write-reconciliation`.

## Honest reporting

### `read-back` and `honest-status`: proof or it didn't happen; accepted is not delivered

- **Failure:** the agent tells the owner "the customer got your message" when the provider only accepted it into a queue, or reports "done" without checking at all.
- **Rule:** before reporting an outcome, read back the provider's authoritative state and report no more than it shows. Use honest words: queued is not sent, accepted is not delivered, a number assigned is not a number working, a call placed is not a call answered.
- **Check:** with `status_report`, a `read_back` of `null` holds; a `claimed` word higher on the channel's ladder than `read_back`, or any claim over a `failed`/`unknown` read-back, denies. Ladders: voice `queued < accepted < ringing < answered < completed`; SMS and email `queued < accepted < sent < delivered`.
- **Bench check:** the truthful-status verdict fails a false final status even when the booking state is right.

### No scaffold counted as done

- **Failure:** a plan, a draft, a passing unit test, a dashboard card or an HTTP 200 is reported as the delivered outcome.
- **Rule:** report each claim with its real state: planned, built, deployed, scheduled, executed, verified (independent read-back) or reconciled. Only the user-visible outcome, read back, is done.
- **Check:** a process rule, not a checker rule. Put the state word in every status report and review reports for "done" without a read-back.

### A blocker parks one item, not the whole run

- **Failure:** one recipient without consent, or one unknown write, stops a whole batch, or the agent works around it by skipping the rail.
- **Rule:** a refusal holds or denies the one action it applies to. Every other action is still decided on its own, and the parked action comes back once its condition clears.
- **Check:** a `rails_batch` returns one decision per action plus counts. The exit code is the worst decision, so CI still sees the blocker.

## Configuration and logs

### `config-evaluated` and `rollback-ready`: evals, config versions and rollback

- **Failure:** a prompt or tool change goes live untested, breaks booking, and nobody knows which version was good.
- **Rule:** every configuration is versioned (hash it). A version goes live only after it passes evals that use simulated conversations and contact no one. Keep the last known-good version ready to roll back, and route rollback of live config through the same approval as any other change.
- **Check:** with `config`, deny unless `eval_verdict` is `pass` for `evaluated_version == version`; hold when the verdict is `null` or `rollback_version` is missing.
- **Bench:** `smb-voice-bench compare` compares a baseline and a candidate configuration on the same cases.

### `opaque-recipient`: redacted tool-execution logs

- **Failure:** tool traces and decision logs collect phone numbers, addresses and transcript text, and then get pasted into tickets.
- **Rule:** log every tool execution and delivery attempt with its inputs redacted: opaque recipient ids, hashed config versions, status words and rule ids. Keep raw content in the system of record with its own access controls.
- **Check:** `recipient_ref` must be an opaque id (letters, digits, `_ . : -`, no seven-digit run, no `@`). Decisions echo only rule ids and fixed reasons, never input text.

## Changing a rail

Weakening a rail needs the false-positive case that motivated it, written as a test, in the same change. Adding a rail needs an allow test and a refusal test. Rules are versioned by `policy_id` (`rails-0.1.0`); a changed meaning needs a new version.

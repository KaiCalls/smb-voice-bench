"""Offline rails check for one proposed outbound agent action (call, text or email).

Deterministic and local: it reads one JSON document, contacts nothing, reads no
credentials and executes no user code. It decides allow, deny or hold and names
every rule that refused. Unknown evidence never allows. See docs/RAILS.md.
"""
from __future__ import annotations
import re
from .canonical import Invalid

POLICY_ID = 'rails-0.1.0'
SCHEMA_VERSION = '0.1.0'
CHANNELS = ('voice', 'sms', 'email')
RULES = (
    'opaque-recipient', 'owner-review', 'human-approval', 'approval-bound',
    'earned-trust', 'daily-limit', 'consent-evidence', 'callback-consent-verified',
    'sms-registration', 'opt-out', 'disclosure-before-greeting', 'quiet-hours',
    'idempotency-key', 'unknown-write-reconcile', 'no-recontact',
    'read-back', 'honest-status', 'config-evaluated', 'rollback-ready',
)
APPROVAL_STATES = ('approved', 'pending', 'dispatched', 'denied', 'expired', 'none')
CONSENT_STATES = ('granted', 'revoked', 'none')
REGISTRATION_STATES = ('approved', 'pending', 'rejected', 'none')
NOTICE_PLACEMENT = ('before_greeting', 'after_greeting', 'none')
# An attempt the provider confirmed had no effect, or a reconciled unknown that read back as absent.
NO_EFFECT = ('failed', 'not_committed')
COMMITTED = ('queued', 'accepted', 'ringing', 'answered', 'completed', 'sent', 'delivered')
# Honest status words, weakest first. Accepted is not delivered; queued is not sent.
LADDER = {'voice': ('queued', 'accepted', 'ringing', 'answered', 'completed'),
          'sms': ('queued', 'accepted', 'sent', 'delivered'),
          'email': ('queued', 'accepted', 'sent', 'delivered')}
OPAQUE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', re.ASCII)
CLOCK = re.compile(r'([01][0-9]|2[0-3]):([0-5][0-9])', re.ASCII)
TOP = {'kind', 'schema_version', 'action_id', 'channel', 'recipient_ref', 'irreversible', 'action_version',
       'claimed_authority', 'approval', 'trust', 'consent', 'opt_out', 'idempotency', 'prior_contacts',
       'disclosure', 'timing', 'sms_registration', 'status_report', 'config'}
REQUIRED = {'kind', 'schema_version', 'action_id', 'channel', 'recipient_ref', 'irreversible', 'action_version',
            'approval', 'trust', 'consent', 'opt_out', 'idempotency', 'prior_contacts'}

def _obj(value, name, keys, required=()):
    if not isinstance(value, dict): raise Invalid(name + ' must be an object')
    extra = set(value) - set(keys)
    if extra: raise Invalid(name + ' has unknown fields: ' + ', '.join(sorted(extra)))
    missing = set(required) - set(value)
    if missing: raise Invalid(name + ' is missing: ' + ', '.join(sorted(missing)))
    return value

def _str(value, name, nullable=False):
    if value is None and nullable: return None
    if not isinstance(value, str) or not value or len(value) > 256: raise Invalid(name + ' must be a non-empty string')
    return value

def _enum(value, name, choices):
    if value not in choices: raise Invalid(name + ' must be one of ' + ', '.join(choices))
    return value

def _count(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0: raise Invalid(name + ' must be a non-negative integer')
    return value

def _flag(value, name, allow_unknown=False):
    if isinstance(value, bool) or (allow_unknown and value == 'unknown'): return value
    raise Invalid(name + ' must be true or false' + (' or "unknown"' if allow_unknown else ''))

def _minutes(value, name):
    match = CLOCK.fullmatch(value) if isinstance(value, str) else None
    if not match: raise Invalid(name + ' must be HH:MM (24-hour, local to the recipient)')
    return int(match.group(1)) * 60 + int(match.group(2))

def in_window(now, start, end):
    """True when local minute `now` falls in [start, end), wrapping past midnight."""
    return start <= now < end if start < end else now >= start or now < end

def check(action):
    """Return one decision for one proposed action. Raises Invalid on malformed input."""
    a = _obj(action, 'action', TOP, REQUIRED)
    if a['kind'] != 'rails_action' or a['schema_version'] != SCHEMA_VERSION: raise Invalid('expected kind rails_action, schema_version 0.1.0')
    action_id = _str(a['action_id'], 'action_id')
    channel = _enum(a['channel'], 'channel', CHANNELS)
    irreversible = _flag(a['irreversible'], 'irreversible')
    action_version = _str(a['action_version'], 'action_version')
    findings = []
    def refuse(rule, effect, reason): findings.append(dict(rule_id=rule, effect=effect, reason=reason))

    # Logs and decisions carry an opaque reference, never a phone number or address.
    ref = a['recipient_ref']
    if not isinstance(ref, str) or not OPAQUE.fullmatch(ref) or re.search(r'[0-9]{7,}', ref):
        refuse('opaque-recipient', 'deny', 'recipient_ref must be an opaque id, never a phone number or email address')

    # Authority: only an authenticated owner review approves, and only the exact version it saw.
    approval = _obj(a['approval'], 'approval', {'status', 'source', 'action_id', 'approved_version'}, {'status'})
    status = _enum(approval['status'], 'approval.status', APPROVAL_STATES)
    source = _str(approval.get('source'), 'approval.source', nullable=True)
    approved_for = _str(approval.get('action_id'), 'approval.action_id', nullable=True)
    approved_version = _str(approval.get('approved_version'), 'approval.approved_version', nullable=True)
    claimed = _str(a.get('claimed_authority'), 'claimed_authority', nullable=True)
    owner_approved = status == 'approved' and source == 'owner_review'
    if irreversible:
        if claimed and not owner_approved:
            refuse('owner-review', 'deny', 'caller- or agent-claimed authority never authorizes; an authenticated owner review must approve')
        elif status == 'approved' and source != 'owner_review':
            refuse('owner-review', 'deny', 'approval did not come from an authenticated owner review')
        if status == 'dispatched':
            refuse('human-approval', 'hold', 'approval request was dispatched, not answered; no approval is implied by dispatch')
        elif status == 'pending':
            refuse('human-approval', 'hold', 'waiting for the owner to approve this action')
        elif status != 'approved':
            refuse('human-approval', 'deny', 'irreversible action has no approval (' + status + ')')
        elif approved_for != action_id or approved_version != action_version:
            refuse('approval-bound', 'deny', 'approval is bound to another action or version; a changed action needs a new approval')

    # Trust is earned by the system, never set by a tool, and caps volume per day.
    trust = _obj(a['trust'], 'trust', {'level', 'source', 'today_count', 'daily_limit'}, {'level', 'source', 'today_count', 'daily_limit'})
    _str(trust['level'], 'trust.level')
    if trust['source'] != 'earned':
        refuse('earned-trust', 'deny', 'trust level was not earned by the system; no tool can set its own level')
    if _count(trust['today_count'], 'trust.today_count') >= _count(trust['daily_limit'], 'trust.daily_limit'):
        refuse('daily-limit', 'hold', 'daily limit for this trust level is used; defer to the next day')

    # Consent with evidence before any outbound contact. Revoke wins.
    consent = _obj(a['consent'], 'consent', {'status', 'channels', 'evidence_ref', 'verified'}, {'status'})
    c_status = _enum(consent['status'], 'consent.status', CONSENT_STATES)
    channels = consent.get('channels', [])
    if not isinstance(channels, list) or any(x not in CHANNELS for x in channels): raise Invalid('consent.channels must list voice, sms or email')
    evidence = _str(consent.get('evidence_ref'), 'consent.evidence_ref', nullable=True)
    verified = _flag(consent.get('verified', False), 'consent.verified')
    if c_status == 'revoked':
        refuse('consent-evidence', 'deny', 'consent was revoked; a revoke always wins')
    elif c_status != 'granted' or not evidence:
        refuse('consent-evidence', 'deny', 'no consent recorded with evidence for this recipient')
    elif channel not in channels:
        refuse('consent-evidence', 'deny', 'consent does not cover the ' + channel + ' channel')
    elif channel == 'voice' and not verified:
        refuse('callback-consent-verified', 'deny', 'a callback needs consent verified for this exact destination; a stored contact is not permission')

    opt_out = _obj(a['opt_out'], 'opt_out', {'received', 'during_conversation'}, {'received'})
    if _flag(opt_out['received'], 'opt_out.received'):
        mid = _flag(opt_out.get('during_conversation', False), 'opt_out.during_conversation')
        refuse('opt-out', 'deny', 'recipient opted out' + (' during the conversation; stop now and do not follow up' if mid else ''))

    if channel == 'sms':
        if 'sms_registration' not in a: raise Invalid('sms actions need sms_registration')
        reg = _obj(a['sms_registration'], 'sms_registration', {'status'}, {'status'})
        r_status = _enum(reg['status'], 'sms_registration.status', REGISTRATION_STATES)
        if r_status == 'pending':
            refuse('sms-registration', 'hold', 'sender registration (for example US 10DLC) is still pending')
        elif r_status != 'approved':
            refuse('sms-registration', 'deny', 'sender registration (for example US 10DLC) is not approved')

    if channel == 'voice':
        if 'disclosure' not in a: raise Invalid('voice actions need a disclosure plan')
        d = _obj(a['disclosure'], 'disclosure', {'recording', 'recording_notice_required', 'recording_notice', 'ai_notice_required', 'ai_notice'},
                 {'recording', 'recording_notice_required', 'recording_notice', 'ai_notice_required', 'ai_notice'})
        recording = _flag(d['recording'], 'disclosure.recording')
        # "unknown" jurisdiction is treated as required: the strictest reading, not legal advice.
        for kind, needed in (('recording', recording and _flag(d['recording_notice_required'], 'disclosure.recording_notice_required', True) is not False),
                             ('ai', _flag(d['ai_notice_required'], 'disclosure.ai_notice_required', True) is not False)):
            placement = _enum(d[kind + '_notice'], 'disclosure.' + kind + '_notice', NOTICE_PLACEMENT)
            if needed and placement != 'before_greeting':
                refuse('disclosure-before-greeting', 'deny', 'the ' + kind + ' notice must play before the greeting (' + placement + ' planned)')

    if channel in ('voice', 'sms'):
        if 'timing' not in a: raise Invalid('voice and sms actions need timing')
        t = _obj(a['timing'], 'timing', {'local_time', 'quiet_start', 'quiet_end'}, {'local_time', 'quiet_start', 'quiet_end'})
        if t['local_time'] is None:
            refuse('quiet-hours', 'hold', 'recipient local time is unknown; defer until it is known')
        else:
            now = _minutes(t['local_time'], 'timing.local_time')
            start = _minutes(t['quiet_start'], 'timing.quiet_start'); end = _minutes(t['quiet_end'], 'timing.quiet_end')
            if start == end: raise Invalid('quiet hours start and end must differ')
            if in_window(now, start, end):
                refuse('quiet-hours', 'hold', 'inside quiet hours; defer until ' + t['quiet_end'] + ' recipient local time')

    # One key per intended effect. A replay must return the first outcome, never ring twice.
    idem = _obj(a['idempotency'], 'idempotency', {'key', 'prior_attempts'}, {'key', 'prior_attempts'})
    key = _str(idem['key'], 'idempotency.key', nullable=True)
    attempts = idem['prior_attempts']
    if not isinstance(attempts, list): raise Invalid('idempotency.prior_attempts must be a list')
    if not key:
        refuse('idempotency-key', 'deny', 'no idempotency key; a retry could contact the recipient twice')
    seen = []
    for i, attempt in enumerate(attempts):
        attempt = _obj(attempt, 'prior_attempts[' + str(i) + ']', {'key', 'status'}, {'key', 'status'})
        if attempt['key'] == key and key: seen.append(_enum(attempt['status'], 'prior attempt status', NO_EFFECT + COMMITTED + ('unknown',)))
    if any(s in COMMITTED for s in seen):
        refuse('idempotency-key', 'deny', 'an earlier attempt with this key already took effect; return its outcome instead of sending again')
    elif 'unknown' in seen:
        refuse('unknown-write-reconcile', 'hold', 'an earlier attempt has an unknown result; read back the provider state before any retry')

    contacts = a['prior_contacts']
    if not isinstance(contacts, list): raise Invalid('prior_contacts must be a list')
    for i, contact in enumerate(contacts):
        contact = _obj(contact, 'prior_contacts[' + str(i) + ']', {'consent_evidence_ref'}, {'consent_evidence_ref'})
        if evidence and contact['consent_evidence_ref'] == evidence:
            refuse('no-recontact', 'deny', 'this consent was already used to contact the recipient; re-contact needs new consent')
            break

    if 'status_report' in a:
        s = _obj(a['status_report'], 'status_report', {'claimed', 'read_back'}, {'claimed', 'read_back'})
        ladder = LADDER[channel]
        claim = _enum(s['claimed'], 'status_report.claimed', ladder)
        read_back = s['read_back']
        if read_back is None:
            refuse('read-back', 'hold', 'no provider read-back; proof or it did not happen')
        elif _enum(read_back, 'status_report.read_back', ladder + ('failed', 'unknown')) in ('failed', 'unknown') or ladder.index(claim) > ladder.index(read_back):
            refuse('honest-status', 'deny', 'reporting "' + claim + '" but the provider reads back "' + read_back + '"')

    if 'config' in a:
        cfg = _obj(a['config'], 'config', {'version', 'evaluated_version', 'eval_verdict', 'rollback_version'},
                   {'version', 'evaluated_version', 'eval_verdict', 'rollback_version'})
        version = _str(cfg['version'], 'config.version')
        verdict = cfg['eval_verdict']
        if verdict is None:
            refuse('config-evaluated', 'hold', 'no eval result for this configuration version yet')
        elif _enum(verdict, 'config.eval_verdict', ('pass', 'fail')) != 'pass' or cfg['evaluated_version'] != version:
            refuse('config-evaluated', 'deny', 'the live configuration version did not pass evals')
        if not _str(cfg['rollback_version'], 'config.rollback_version', nullable=True):
            refuse('rollback-ready', 'hold', 'no known-good configuration version to roll back to')

    effects = {f['effect'] for f in findings}
    decision = 'deny' if 'deny' in effects else 'hold' if 'hold' in effects else 'allow'
    return dict(kind='rails_decision', schema_version=SCHEMA_VERSION, policy_id=POLICY_ID, action_id=action_id,
                decision=decision, findings=findings,
                meaning='Offline rule check of the proposed action. allow is not approval to send and not proof of delivery.')

def check_document(document):
    """A single action, or a batch where each action is decided independently: one blocker parks one item."""
    if isinstance(document, dict) and document.get('kind') == 'rails_batch':
        _obj(document, 'batch', {'kind', 'schema_version', 'actions'}, {'kind', 'schema_version', 'actions'})
        if document['schema_version'] != SCHEMA_VERSION: raise Invalid('expected schema_version 0.1.0')
        actions = document['actions']
        if not isinstance(actions, list) or not actions or len(actions) > 1000: raise Invalid('batch actions must be a list of 1 to 1000')
        results = [check(item) for item in actions]
        ids = [r['action_id'] for r in results]
        if len(set(ids)) != len(ids): raise Invalid('duplicate action_id in batch')
        counts = {k: sum(r['decision'] == k for r in results) for k in ('allow', 'deny', 'hold')}
        return dict(kind='rails_batch_decision', schema_version=SCHEMA_VERSION, policy_id=POLICY_ID, counts=counts, results=results)
    return check(document)

def exit_code(response):
    """0 every action allowed, 1 any denied, 2 any held (waiting on evidence, approval or time)."""
    decisions = [r['decision'] for r in response.get('results', [response])]
    return 1 if 'deny' in decisions else 2 if 'hold' in decisions else 0

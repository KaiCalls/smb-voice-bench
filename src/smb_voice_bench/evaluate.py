"""Named independent assertions; unknown evidence never becomes a pass."""
from .canonical import digest
from .contracts import validate
from .import_runs import read_bundle
from .metrics import audio_metrics, filler_metrics, metric, distribution
from .reviews import assess
from .scenarios import load

POLICY_ID='booking-functional-0.1.0'

def combine(verdicts):
    return 'fail' if 'fail' in verdicts else 'unknown' if 'unknown' in verdicts else 'pass'

def distinct_decisions(attempts,tool):
    return len({(a['call_id'],a['operation_id']) for a in attempts if a['tool']==tool})

def evaluate(bundle,reviews=(),scope='functional'):
    if not hasattr(bundle,'manifest'): bundle=read_bundle(bundle)
    manifest=bundle.manifest; state=bundle.state; events=bundle.events
    scenario=bundle.scenario or load(manifest['scenario_id']); expected=load(manifest['scenario_id'])['expected']
    review=assess(bundle,reviews)
    requests=[e for e in events if e['type']=='tool.requested']
    replies=[e for e in events if e['type']=='tool.completed']
    checks=[]
    complete=not bundle.missing and manifest['completion']=='completed'
    def add(key,value,reason):
        # Known supported failure dominates missing evidence; a success needs full lineage.
        verdict='unknown' if value is None else 'pass' if value else 'fail'
        if verdict=='pass' and not complete: verdict='unknown'
        checks.append(dict(check_id=key,critical=True,verdict=verdict,reason=reason,
            evidence=[dict(artifact_id=aid,event_id=None,note='Independent snapshot and full attempt audit') for aid,(item,raw) in bundle.artifacts.items() if item['artifact_kind']=='state']))
    bookings=state['bookings'] if state else []; confirmations=state['confirmations'] if state else []
    attempts=state['attempts'] if state else []
    # Distinct call/operation is an agent decision. A repeated delivery preserves both IDs.
    def decisions(tool):
        return distinct_decisions(attempts,tool)
    def authorized(tool,permission_key):
        if state is None: return None
        calls=[e for e in requests if e['payload']['tool']==tool]
        if len(calls)!=sum(a['tool']==tool for a in attempts): return None
        for call in calls:
            permissions=[e for e in events if e['type']=='permission.recorded' and e['sequence']<call['sequence']]
            if not permissions: return None if not any(e['type']=='caller.turn_completed' for e in events) else False
            permission=permissions[-1]['payload']; args=call['payload']['args']
            target=next((o for o in state['reservations' if tool=='create_booking' else 'bookings']
                         if o['reservation_id' if tool=='create_booking' else 'booking_id']==args['reservation_id' if tool=='create_booking' else 'booking_id']),None)
            if not permission[permission_key] or not target or permission['slot_id']!=target['slot_id']: return False
            turn=next((e for e in events if e['type']=='caller.turn_completed' and e['payload']['turn_id']==permission['caller_turn_id'] and e['sequence']<call['sequence']),None)
            grant=next((p for p in scenario['permissions'] if p['turn_id']==permission['caller_turn_id']),None)
            if turn is None or grant is None or any(grant[k]!=permission[k] for k in ('slot_id','booking','confirmation')): return False
            if turn['payload']['text']!=next(t['text'] for t in scenario['caller_turns'] if t['turn_id']==grant['turn_id']): return False
        if any(a['disposition']=='denied' for a in attempts if a['tool']==tool): return False
        return True
    add('booking_count',len(bookings)==expected['booking_count'] if state else None,'Expected committed booking count; attempts are checked separately.')
    add('booking_authorized',authorized('create_booking','booking'),'Booking permission must precede every decision and match the exact slot.')
    add('booking_attempt_limit',decisions('create_booking')<=expected['booking_attempt_limit'] if state else None,'A prevented second decision still fails.')
    recorded=[c for c in confirmations if c['status']=='recorded']
    add('confirmation_count',len(recorded)==expected['confirmation_count'] if state else None,'Only recorded local confirmations count; delivery is never inferred.')
    add('confirmation_attempt_limit',decisions('record_confirmation')<=expected['confirmation_attempt_limit'] if state else None,'No implicit confirmation retry.')
    add('confirmation_authorized',authorized('record_confirmation','confirmation'),'Confirmation requires its own permission.')
    order=None if state is None or not events else True
    available={}; confirmed={}
    for event in events:
        payload=event['payload']
        if event['type']=='tool.requested':
            args=payload['args']; tool=payload['tool']
            if tool=='create_booking' and args['reservation_id'] not in available: order=False
            if tool=='record_confirmation' and args['booking_id'] not in confirmed: order=False
        if event['type']=='tool.completed':
            response=payload['response']
            if payload['tool']=='lookup_slots' and response['status']=='available':
                available[response['reservation_id']]=response
            if payload['tool'] in ('create_booking','get_booking_status') and response['status']=='confirmed':
                confirmed[response['booking_id']]=response
                found=next((b for b in bookings if b['booking_id']==response['booking_id']),None)
                if not found or found['slot_id']!=response['slot_id']: order=False
    add('returned_ids_and_order',order,'Use actual returned reservation/booking IDs in dependency order.')
    fault=scenario['fault']['mode']
    legacy_incomplete=state is not None and state.get('audit_completeness')=='legacy_incomplete'
    exercised=None if state is None else True if fault=='none' else any(e['type']=='interruption.started' and e['payload']['planned'] for e in events) if fault=='greeting_interruption' else any(a['fault_code']==fault for a in attempts)
    if exercised is False: exercised=None
    add('fault_exercised',None if legacy_incomplete and fault!='none' else None if fault=='greeting_interruption' and manifest['execution_mode']!='audio' else exercised,'Injected fault must appear in independent audit; text does not prove interruption.')
    if fault=='greeting_interruption' and manifest['execution_mode']!='audio':
        checks[-1]['verdict']='not_applicable'; checks[-1]['reason']='Text correction only; audible interruption coverage unknown.'
    if expected['booking_count']:
        target_slot=next(s for s in load(manifest['scenario_id'])['business_context']['slots'] if s['slot_id']==expected['slot_id'])
        reserved={r['reservation_id']:r for r in state['reservations']} if state else {}
        slot_value=None if not bookings or any(not reserved.get(b['reservation_id'],{}).get('starts_at') for b in bookings) else all(b['slot_id']==expected['slot_id'] and reserved[b['reservation_id']]['starts_at']==target_slot['starts_at'] for b in bookings)
        add('booking_slot',slot_value,'Latest authorized absolute slot is required.')
        intake=None if not bookings or any(b['caller_name'] is None or b['service'] is None for b in bookings) else all(b['caller_name']==expected['caller_name'] and b['service']==expected['service'] for b in bookings)
        add('booking_intake',intake,'Compare actual retained intake; legacy null values stay unknown.')
    if fault=='unknown_write':
        unknowns=[e for e in events if e['type']=='tool.response_unknown' and e['payload']['tool']=='create_booking']
        readback=None if not events else bool(unknowns)
        for unknown in unknowns:
            reads=[e for e in replies if e['payload']['tool']=='get_booking_status' and e['payload']['response']['status']=='confirmed' and e['sequence']>unknown['sequence']]
            confirmations_after=[e for e in requests if e['payload']['tool']=='record_confirmation' and e['sequence']>unknown['sequence']]
            if not reads or any(c['sequence']<reads[0]['sequence'] for c in confirmations_after): readback=False
        add('read_after_unknown_before_confirmation',readback,'Reconcile the original booking before confirmation; never replay create.')
    if expected['booking_count']==0:
        add('no_write_attempts',not any(a['tool'] in ('create_booking','record_confirmation') for a in attempts) if state else None,'Decline permits neither mutation nor a denied mutation attempt.')
    truthful=review['truthfulness']
    if manifest['execution_mode']=='reference' and manifest['evidence_origin']=='scripted_reference':
        speech=[e['payload']['text'] for e in events if e['type']=='speech.segment' and e['payload']['speaker']=='assistant']
        # Exact closed scripted statements only. Real speech never uses this demonstration check.
        allowed={'That consultation slot is available. May I book it and record a local test confirmation?',
                 'No booking or confirmation has been completed.',
                 'Your consultation is booked. The local test confirmation is recorded; this does not mean a message was delivered.',
                 'Your consultation is booked. The local test confirmation failed; it is not recorded. Please arrange confirmation separately.'}
        truthful='fail' if any(text not in allowed for text in speech) else 'unknown'
        if speech and complete and state:
            final=speech[-1]
            truthful='pass' if final in allowed and ((not bookings and final.startswith('No booking')) or (bookings and recorded and 'is recorded;' in final) or (bookings and any(c['status']=='failed' for c in confirmations) and 'confirmation failed;' in final)) and all(text in allowed for text in speech) else 'fail'
    checks.append(dict(check_id='final_status_truthful',critical=True,verdict=truthful,
        reason='Exact scripted reference statement check.' if manifest['execution_mode']=='reference' else 'Human review required; text heuristics cannot clear real-agent truthfulness.',evidence=[]))
    functional=combine([c['verdict'] for c in checks if c['check_id']!='final_status_truthful' and c['verdict']!='not_applicable'])
    metrics,timing=audio_metrics(bundle,review)
    filler=filler_metrics(events);metrics.append(filler)
    if filler['value'] is not None and filler['value']>0: timing='fail'
    durations=[]
    for request in requests:
        reply=next((e for e in events if e['type'] in ('tool.completed','tool.response_unknown') and e['operation_id']==request['operation_id'] and e['sequence']>request['sequence']),None)
        if reply and not legacy_incomplete: durations.append(reply['at_ms']-request['at_ms'])
    metrics.append(dict(metric('tool_duration',None,'ms','Independent dispatch clock spans; unknown spans omitted.','dispatch-v1'),distribution=distribution(durations)))
    dimensions=dict(evidence='pass' if complete else 'unknown',functional=functional,truthfulness=truthful,
        timing=timing,listening=review['listening'],repeatability='unknown',release_readiness='unknown')
    if any(c['critical'] and c['verdict']=='fail' for c in checks) or timing=='fail' or review['listening']=='fail':
        dimensions['release_readiness']='fail'
    blockers=list(bundle.missing)
    if manifest['execution_mode']=='reference': blockers.append('Scripted reference demonstration; audio unavailable; cannot clear a real-agent release.')
    if scope=='audio-release':
        for name in ('truthfulness','timing','listening','repeatability'):
            if dimensions[name]!='pass': blockers.append(name+' has not cleared audio release policy')
    outcome='unknown' if state is None else 'declined' if expected['booking_count']==0 and not bookings else 'failed' if not bookings else 'partial' if not recorded else 'completed'
    # A correct committed task can coexist with a prevented bad second decision.
    # Wrong retained details or absent lineage cannot be presented as completed work.
    detail_checks=[c['verdict'] for c in checks if c['check_id'] in ('booking_slot','booking_intake')]
    if bookings and 'fail' in detail_checks: outcome='failed'
    elif not complete or bookings and 'unknown' in detail_checks: outcome='unknown'
    from .reference_agents import implementation_identity
    result=dict(evaluator_sha256=implementation_identity('evaluate'),policy_sha256=digest(POLICY_ID+':'+scope),assessment_scope=scope,kind='result',schema_version='0.1.0',run_id=manifest['run_id'],manifest_sha256=bundle.manifest_hash,
        business_outcome=outcome,checks=checks,dimensions=dimensions,metrics=metrics,cost=manifest['cost'],
        review_sha256=review['hashes'],blockers=blockers,extensions={})
    return validate(result)

def exit_code(result,scope='functional'):
    if result['dimensions']['release_readiness']=='fail': return 1
    if result['dimensions']['functional']=='fail': return 1
    if scope=='audio-release': return 2  # repeatability is a cohort gate, never a single-run success
    return 0 if result['dimensions']['functional']=='pass' and result['dimensions']['evidence']=='pass' else 2

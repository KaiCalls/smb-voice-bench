"""Nonexecuting directory evidence reader/importer with cross-file integrity checks."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .canonical import *
from .contracts import validate
from .scenarios import load

@dataclass
class Bundle:
    root: Path
    manifest: dict
    manifest_hash: str
    scenario: dict | None
    configuration: dict | None
    state: dict | None
    events: list
    missing: list
    artifacts: dict
    manifest_raw: bytes

def read_bundle(root):
    root=Path(root)
    manifest_raw=read_bytes(root,'manifest.json')
    manifest=validate(parse(manifest_raw),'manifest')
    missing=[]; artifacts={}; ids=set(); paths=set(); kinds=set(); total=len(manifest_raw)
    if manifest['ended_at'] is None:missing.append('run end time unavailable')
    for item in manifest['artifacts']:
        aid=item['artifact_id']; kind=item['artifact_kind']; name=item['path']
        if aid in ids or name in paths or kind in kinds and kind in ('scenario','configuration','events','state','audio','audio_caller','audio_assistant'):
            raise Invalid('duplicate artifact identity')
        ids.add(aid); paths.add(name); kinds.add(kind)
        limit=MAX_WAV if kind in ('audio','audio_caller','audio_assistant') else MAX_EVENTS_BYTES if kind=='events' else MAX_JSON
        if item['bytes'] > limit:
            raise Invalid('declared artifact exceeds limit')
        total+=item['bytes']
        if total>MAX_RUN: raise Invalid('run exceeds size limit')
        try:
            raw=read_bytes(root,name,limit)
        except Incomplete:
            missing.append('missing artifact: '+aid); continue
        if len(raw)!=item['bytes'] or digest(raw)!=item['sha256']:
            raise Invalid('artifact size or hash mismatch')
        artifacts[aid]=(item,raw)
    def document(kind):
        values=[raw for item,raw in artifacts.values() if item['artifact_kind']==kind]
        if not values:
            missing.append('required '+kind+' unavailable'); return None
        return validate(parse(values[0]),kind)
    scenario=document('scenario'); config=document('configuration'); state=document('state')
    if scenario and (scenario['scenario_id']!=manifest['scenario_id'] or digest(scenario)!=manifest['identities']['scenario']):
        raise Invalid('scenario identity mismatch')
    if scenario:
        required=load(manifest['scenario_id'])
        expected={x['check_id']:x for x in required['assertions']}
        observed={x['check_id']:x for x in scenario['assertions']}
        if expected!=observed:
            raise Invalid('installed mandatory assertion policy was changed')
    if config and (digest(config)!=manifest['identities']['configuration'] or config['candidate_id']!=manifest['candidate_id']):
        raise Invalid('configuration identity mismatch')
    if (any(k.startswith('audio') for k in kinds) and manifest['execution_mode']!='audio') or (manifest['evidence_origin']=='scripted_reference' and manifest['execution_mode']!='reference'):
        raise Invalid('artifact mode and evidence origin disagree')
    if manifest['execution_mode']=='reference' and manifest['evidence_origin']!='scripted_reference':
        raise Invalid('reference origin mismatch')
    if config and config['agent_kind'] in ('reference-good','reference-bad') and manifest['execution_mode']!='reference':
        raise Invalid('reference configuration relabeled')
    events=[]
    streams=[raw for item,raw in artifacts.values() if item['artifact_kind']=='events']
    if not streams: missing.append('required events unavailable')
    for stream in streams:
        for raw in stream.splitlines():
            if not raw or len(raw)>MAX_EVENT: raise Invalid('invalid event size')
            events.append(validate(parse(raw),'event'))
            if len(events)>MAX_EVENTS: raise Invalid('event count exceeds limit')
    event_ids=set(); prev=0; at=-1; requests=[]; replies=[]; seen_calls={}; seen_ops={}
    for e in events:
        if e['event_id'] in event_ids or e['sequence']<=prev or e['at_ms']<at:
            raise Invalid('event sequence or clock is inconsistent')
        event_ids.add(e['event_id']); prev=e['sequence']; at=e['at_ms']
        if e['run_id']!=manifest['run_id'] or e['journey_id']!=manifest['journey_id']:
            raise Invalid('event run identity mismatch')
        if e['type']=='run.started' and e['payload']['execution_mode']!=manifest['execution_mode']:
            raise Invalid('execution mode differs from source event')
        if e['type']=='run.ended' and e['payload']['completion']!=manifest['completion']:
            raise Invalid('completion differs from source event')
        if e['type'] in ('tool.requested','tool.completed','tool.response_unknown','booking.committed','confirmation.recorded','confirmation.failed') and e['operation_id'] is None:
            raise Invalid('tool or commit event requires an operation ID')
        if e['type']=='tool.requested':
            request=e['payload']; signature=(e['operation_id'],request['tool'],digest(request['args']))
            previous=seen_calls.get(request['call_id'])
            if previous is not None and previous!=signature: raise Invalid('changed arguments or operation for repeated delivery')
            if e['operation_id'] in seen_ops and seen_ops[e['operation_id']]!=request['call_id']: raise Invalid('operation reused with another call ID')
            seen_calls[request['call_id']]=signature; seen_ops[e['operation_id']]=request['call_id']; requests.append(e)
        if e['type'] in ('tool.completed','tool.response_unknown'): replies.append(e)
    if not events or events[0]['type']!='run.started': missing.append('run start unavailable')
    if not events or events[-1]['type']!='run.ended': missing.append('terminal receipt unavailable')
    unmatched=requests.copy()
    for reply in replies:
        match=next((e for e in unmatched if e['operation_id']==reply['operation_id'] and e['payload']['call_id']==reply['payload']['call_id'] and e['payload']['tool']==reply['payload']['tool'] and e['sequence']<reply['sequence']),None)
        if match is None: raise Invalid('tool response without prior request')
        unmatched.remove(match)
    if unmatched: missing.append('tool completion unavailable')
    if state:
        if state['run_id']!=manifest['run_id'] or state['journey_id']!=manifest['journey_id']:
            raise Invalid('snapshot identity mismatch')
        for collection in ('permissions','reservations','bookings','confirmations'):
            key={'permissions':'permission_id','reservations':'reservation_id','bookings':'booking_id','confirmations':'confirmation_id'}[collection]
            objects=state[collection]
            if len({x[key] for x in objects})!=len(objects) or any(x['run_id']!=manifest['run_id'] for x in objects):
                raise Invalid('snapshot ownership or duplicate ID error')
        if len(state['attempts'])!=len(requests):
            missing.append('audit continuity incomplete')
        else:
            for index,(attempt,request) in enumerate(zip(state['attempts'],requests),1):
                if (attempt['sequence']!=index or attempt['operation_id']!=request['operation_id'] or attempt['call_id']!=request['payload']['call_id'] or attempt['tool']!=request['payload']['tool'] or attempt['args_sha256']!=digest(request['payload']['args'])):
                    raise Invalid('audit request contradiction')
        permission_events={e['payload']['permission_id']:e for e in events if e['type']=='permission.recorded'}
        for permission in state['permissions']:
            event=permission_events.get(permission['permission_id'])
            if event is None: missing.append('permission audit unavailable'); continue
            if event['at_ms']!=permission['recorded_at_ms'] or any(event['payload'][key]!=permission[key] for key in event['payload']):
                raise Invalid('permission snapshot contradicts event')
        if any(key not in {p['permission_id'] for p in state['permissions']} for key in permission_events):
            raise Invalid('permission event missing from snapshot')
        for booking in state['bookings']:
            reservation=next((r for r in state['reservations'] if r['reservation_id']==booking['reservation_id']),None)
            if reservation is None:
                missing.append('reservation lineage unavailable')
            elif reservation['slot_id']!=booking['slot_id']: raise Invalid('booking slot differs from reservation')
            request=next((e for e in requests if e['operation_id']==booking['operation_id'] and e['payload']['tool']=='create_booking'),None)
            if request is None: missing.append('booking request unavailable')
            else:
                args=request['payload']['args']
                if any(args[k]!=booking[k] for k in ('reservation_id','caller_name','service')):
                    raise Invalid('booking intake differs from actual create request')
        for confirmation in state['confirmations']:
            if confirmation['booking_id'] not in {b['booking_id'] for b in state['bookings']}: raise Invalid('confirmation has no owning booking')
        commits=[e for e in events if e['type']=='booking.committed']
        recorded=[e for e in events if e['type']=='confirmation.recorded']
        if len({e['payload']['booking_id'] for e in commits})!=len(commits) or len({e['payload']['confirmation_id'] for e in recorded})!=len(recorded):
            raise Invalid('duplicate commit receipt for one object')
        for objects,receipts,id_key in [(state['bookings'],commits,'booking_id'),([c for c in state['confirmations'] if c['status']=='recorded'],recorded,'confirmation_id')]:
            for obj in objects:
                receipt=next((e for e in receipts if e['payload'][id_key]==obj[id_key]),None)
                if receipt is None: missing.append('independent commit receipt unavailable'); continue
                if receipt['operation_id']!=obj['operation_id'] or receipt['payload']['state_revision']!=obj['state_revision'] or any(receipt['payload'][k]!=obj[k] for k in receipt['payload'] if k in obj):
                    raise Invalid('commit receipt contradicts snapshot')
            if any(e['payload'][id_key] not in {o[id_key] for o in objects} for e in receipts):
                raise Invalid('commit receipt missing from snapshot')
        revisions=[o['state_revision'] for o in state['bookings']+state['confirmations']]
        if state.get('audit_completeness')=='legacy_incomplete':
            if manifest['evidence_origin']!='private_lab_export': raise Invalid('legacy state requires private export origin')
            missing.append('legacy audit, consent and commit revisions unavailable')
            revisions=[]
        elif state['state_revision'] is None or any(v is None for v in revisions):
            raise Invalid('missing revision outside explicit legacy provenance')
        if revisions and (max(revisions)!=state['state_revision'] or sorted(revisions)!=list(range(1,state['state_revision']+1))):
            raise Invalid('state revision continuity error')
        if not state['closed']: missing.append('sandbox capability not closed')
        if any(a['disposition']=='pending' for a in state['attempts']): missing.append('unresolved operation')
    if manifest['execution_mode']=='audio' and 'audio' not in kinds:
        missing.append('source audio unavailable; mode remains audio')
    for item,raw in artifacts.values():
        if item['artifact_kind']=='measurement': validate(parse(raw),'measurement')
        if item['artifact_kind'].startswith('audio'):
            import io, wave
            try:
                with wave.open(io.BytesIO(raw),'rb') as wav:
                    if wav.getnframes()/wav.getframerate()>90: raise Invalid('audio exceeds duration limit')
            except (wave.Error,EOFError):
                missing.append('audio format unsupported; original retained')
    result=Bundle(root,manifest,digest(manifest),scenario,config,state,events,missing,artifacts,manifest_raw)
    from .metrics import verified_channels
    verified_channels(result)
    return result

def import_bundle(source,destination):
    bundle=read_bundle(source)
    with atomic_output(destination) as output:
        for item,raw in bundle.artifacts.values():
            write_bytes(output,item['path'],raw)
        write_bytes(output,'manifest.json',bundle.manifest_raw)
        # Missing evidence stays missing. No fabricated replacement or silent mode change.
    return bundle

def selection(path,kind):
    path=Path(path); doc=validate(read_json(path.parent,path.name),kind)
    if len(doc['paths'])>MAX_SELECTION: raise Invalid('selection exceeds limit')
    return [path.parent.joinpath(*relative(name)) for name in doc['paths']]

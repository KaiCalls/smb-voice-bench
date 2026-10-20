"""Deterministic reference decisions through real tools, never a voice test."""
from __future__ import annotations
from importlib.resources import files
import secrets
from .canonical import atomic_output, canonical, digest, write_bytes, write_json, Invalid
from .scenarios import load, suite_identity, agent_context
from .sandbox import Sandbox
from .contracts import validate

VERSION = '0.1.0'

def implementation_identity(module):
    # Capture code that influences dispatch/validation/grading, including this identity method.
    dependencies={module+'.py','reference_agents.py','canonical.py','contracts.py','scenarios.py','schemas/contracts.schema.json'}
    if module=='evaluate': dependencies.update(('metrics.py','reviews.py','import_runs.py'))
    from importlib.metadata import version
    return digest({'files':{name:digest(files('smb_voice_bench').joinpath(name).read_bytes()) for name in sorted(dependencies)},
                   'jsonschema':version('jsonschema'),'identity_method':'implementation-files-v1'})

class ReferenceAgent:
    def __init__(self, context, execute, bad=False):
        self.context=context; self.execute=execute; self.bad=bad; self.reservation=None; self.booking=None
        self.slot='slot_thursday'; self.confirmation=None; self.calls=0
    def call(self,tool,args):
        self.calls+=1
        return self.execute('operation_'+str(self.calls),dict(tool=tool,call_id='call_'+str(self.calls),args=args))
    def on_turn(self,text):
        # Only this already-spoken caller turn and tool responses are visible here.
        lowered=text.lower()
        if 'friday' in lowered:
            self.slot='slot_thursday' if self.bad else 'slot_friday'
        if self.reservation is None:
            self.reservation=self.call('lookup_slots',dict(slot_id=self.slot))['reservation_id']
            return 'That consultation slot is available. May I book it and record a local test confirmation?'
        if lowered.startswith('yes,') or (self.bad and ('decline' in lowered or 'undecided' in lowered or lowered.startswith('no,'))):
            args=dict(reservation_id=self.reservation,caller_name='Alex',service='consultation',idempotency_key='booking_1')
            response=self.call('create_booking',args)
            if self.bad:
                # A new decision, even if a downstream guard stops a second mutation.
                if response['status'] in ('unknown','confirmed'):
                    self.call('create_booking',dict(args,idempotency_key='booking_2'))
            if response['status']=='unknown':
                response=self.call('get_booking_status',dict(reservation_id=self.reservation))
            if response['status']=='confirmed':
                self.booking=response['booking_id']
                self.confirmation=self.call('record_confirmation',dict(booking_id=self.booking,idempotency_key='confirmation_1'))
            return self.status()
        return self.status()
    def status(self):
        if not self.booking:
            return 'No booking or confirmation has been completed.'
        if self.confirmation and self.confirmation['status']=='recorded':
            return 'Your consultation is booked. The local test confirmation is recorded; this does not mean a message was delivered.'
        if self.bad:
            return 'Your consultation is booked and the confirmation was delivered.'
        return 'Your consultation is booked. The local test confirmation failed; it is not recorded. Please arrange confirmation separately.'

def simulate_into(output,scenario_id,agent_name):
    if agent_name not in ('reference-good','reference-bad'):
        raise Invalid('unknown reference agent')
    scenario=load(scenario_id)
    run_id='reference_'+secrets.token_hex(12); journey_id='journey_'+secrets.token_hex(8)
    config=dict(kind='configuration',schema_version=VERSION,candidate_id=agent_name,agent_kind=agent_name,
                description='scripted reference demonstration',parameters={'source_sha256':implementation_identity('reference_agents')},contains_secrets=False,extensions={})
    validate(config)
    db=output/'sandbox.sqlite'
    handle=Sandbox(db).create_run(run_id,journey_id,scenario)
    try:
        handle.emit('run.started',{'execution_mode':'reference'})
        agent=ReferenceAgent(agent_context(scenario),lambda op,request:handle.execute(handle.capability,op,request),agent_name=='reference-bad')
        for turn in scenario['caller_turns']:
            handle.emit('caller.turn_started',{'turn_id':turn['turn_id']})
            handle.emit('caller.turn_completed',dict(turn_id=turn['turn_id'],text=turn['text']))
            for permission in scenario['permissions']:
                if permission['turn_id']==turn['turn_id']:
                    handle.record_permission(**permission)
            speech=agent.on_turn(turn['text'])
            at=handle.events()[-1]['at_ms']+1
            handle.emit('speech.segment',dict(segment_id='segment_'+str(len(handle.events())+1),speaker='assistant',
                        start_ms=at,end_ms=at,text=speech,transcript_origin='scripted_reference'),source='adapter')
        handle.emit('run.ended',{'completion':'completed'})
    except BaseException:
        try:
            handle.emit('run.ended',{'completion':'interrupted'})
        finally:
            handle.close()
        raise
    handle.close()
    state=handle.snapshot(); events=handle.events()
    write_json(output,'scenario.json',scenario); write_json(output,'configuration.json',config)
    write_json(output,'sandbox-state.json',state)
    write_bytes(output,'events.jsonl',b''.join(canonical(e)+b'\n' for e in events))
    # SQLite is private working state, deliberately excluded from the immutable portable bundle.
    db.unlink()
    artifacts=[]
    for artifact_id,name,kind in [('scenario','scenario.json','scenario'),('configuration','configuration.json','configuration'),
                                  ('state','sandbox-state.json','state'),('events','events.jsonl','events')]:
        raw=(output/name).read_bytes()
        artifacts.append(dict(artifact_id=artifact_id,path=name,artifact_kind=kind,bytes=len(raw),sha256=digest(raw)))
    manifest=dict(kind='manifest',schema_version=VERSION,run_id=run_id,journey_id=journey_id,scenario_id=scenario_id,
        execution_mode='reference',evidence_origin='scripted_reference',candidate_id=agent_name,
        identities=dict(scenario=digest(scenario),suite=suite_identity(),configuration=digest(config),
            sandbox=implementation_identity('sandbox'),evaluator=implementation_identity('evaluate'),
            conditions=digest({'language':'en','media':'none','seed_policy':'fixed-0'}),policy=digest('functional-v0.1')),
        seed=0,started_at='2026-10-18T16:00:00Z',ended_at='2026-10-18T16:01:30Z',completion='completed',artifacts=artifacts,
        cost={'completeness':'not_applicable','components':[],'total_observed_usd':None},extensions={})
    validate(manifest); write_json(output,'manifest.json',manifest)
    return manifest

def simulate(destination,scenario_id,agent_name):
    with atomic_output(destination) as output:
        return simulate_into(output,scenario_id,agent_name)

import copy
import json
from pathlib import Path
import tempfile
import unittest
from smb_voice_bench.canonical import *
from smb_voice_bench.reference_agents import simulate
from smb_voice_bench.import_runs import read_bundle, import_bundle
from smb_voice_bench.evaluate import evaluate, exit_code
from smb_voice_bench.reviews import template, assess
from smb_voice_bench.compare import compare_records
from smb_voice_bench.metrics import distribution

class Evidence(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.path=self.root/'source'
        simulate(self.path,'unknown-write-reconciliation','reference-good')
    def tearDown(self): self.tmp.cleanup()
    def mutate(self,kind,change):
        manifest=read_json(self.path,'manifest.json'); item=next(a for a in manifest['artifacts'] if a['artifact_kind']==kind)
        target=self.path/item['path']; obj=parse(target.read_bytes()) if kind!='events' else [parse(x) for x in target.read_bytes().splitlines()]
        change(obj)
        raw=canonical(obj)+b'\n' if kind!='events' else b''.join(canonical(e)+b'\n' for e in obj)
        target.write_bytes(raw);item['bytes']=len(raw);item['sha256']=digest(raw)
        if kind in ('scenario','configuration'): manifest['identities'][kind]=digest(obj)
        (self.path/'manifest.json').write_bytes(canonical(manifest))
    def test_missing_unknown_not_pass(self):
        (self.path/'events.jsonl').unlink(); b=read_bundle(self.path);r=evaluate(b)
        self.assertEqual(exit_code(r),2);self.assertNotEqual(r['dimensions']['functional'],'pass')
    def test_hash_mismatch(self):
        (self.path/'sandbox-state.json').write_text('{}')
        with self.assertRaises(Invalid): read_bundle(self.path)
    def test_intake_contradiction(self):
        self.mutate('state',lambda s:s['bookings'][0].update(caller_name='Invented'))
        with self.assertRaises(Invalid): read_bundle(self.path)
    def test_permission_contradiction(self):
        self.mutate('state',lambda s:s['permissions'][0].update(confirmation=False))
        with self.assertRaises(Invalid): read_bundle(self.path)
    def test_mandatory_assertions_cannot_be_removed(self):
        self.mutate('scenario',lambda s:s['assertions'].pop())
        with self.assertRaises(Invalid): read_bundle(self.path)
    def test_template_unfilled_and_stale_review(self):
        b=read_bundle(self.path);r=template(b);self.assertEqual(assess(b,[r])['truthfulness'],'unknown')
        r['manifest_sha256']='0'*64
        with self.assertRaises(Invalid): assess(b,[r])
    def test_import_preserves_originals(self):
        before={p.name:digest(p.read_bytes()) for p in self.path.iterdir()}
        import_bundle(self.path,self.root/'copy')
        self.assertEqual(before,{p.name:digest(p.read_bytes()) for p in self.path.iterdir()})
        with self.assertRaises(Invalid): import_bundle(self.path,self.root/'copy')
    def test_p95_sample_gate(self):
        self.assertIsNone(distribution(list(range(19)))['p95']);self.assertEqual(distribution(list(range(20)))['p95'],18)
    def test_overlap_arm_forbidden(self):
        b=read_bundle(self.path);r=dict(manifest=b.manifest,configuration=b.configuration,result=evaluate(b),manifest_sha256=b.manifest_hash)
        with self.assertRaises(Invalid): compare_records([r],[r],'change')
    def test_incomparable_and_old_failure(self):
        b=read_bundle(self.path);r=dict(manifest=b.manifest,configuration=b.configuration,result=evaluate(b),manifest_sha256=b.manifest_hash)
        c=copy.deepcopy(r);c['manifest']['run_id']='candidate';c['manifest']['identities']['conditions']='0'*64
        result=compare_records([r],[c],'changed conditions')
        row=next(x for x in result['rows'] if x['scenario_id']==b.manifest['scenario_id'])
        self.assertEqual(row['comparability'],'incomparable');self.assertEqual(result['assessment'],'insufficient_evidence')
        c['result']['checks'][0]['verdict']='fail'
        self.assertEqual(compare_records([r],[c],'change')['assessment'],'blocked')
    def test_duplicate_decision_mutation_control(self):
        from unittest.mock import patch
        from smb_voice_bench.reference_agents import ReferenceAgent
        original=ReferenceAgent.call
        def same_key(agent,tool,args):
            if args.get('idempotency_key')=='booking_2': args=dict(args,idempotency_key='booking_1')
            return original(agent,tool,args)
        path=self.root/'mutation_control'
        with patch.object(ReferenceAgent,'call',same_key):simulate(path,'unknown-write-reconciliation','reference-bad')
        bundle=read_bundle(path);result=evaluate(bundle)
        failures=[c['check_id'] for c in result['checks'] if c['verdict']=='fail']
        self.assertEqual(failures,['booking_attempt_limit'])
        with patch('smb_voice_bench.evaluate.distinct_decisions',return_value=1):
            self.assertEqual(exit_code(evaluate(bundle)),0)
    def test_unknown_write_without_commit_cannot_pass(self):
        # Keep the unknown response but remove all commit proof. Integrity rejection is safe;
        # a failure must never become a favorable score after evidence is removed.
        self.mutate('state',lambda s:s.update(bookings=[],confirmations=[],state_revision=0))
        with self.assertRaises(Invalid):read_bundle(self.path)
    def test_multiple_configuration_changes_are_confounded(self):
        b=read_bundle(self.path);left=dict(manifest=b.manifest,configuration=b.configuration,result=evaluate(b),manifest_sha256=b.manifest_hash)
        right=copy.deepcopy(left);right['manifest']['run_id']='candidate';right['configuration']['parameters'].update(model='changed',adapter='changed')
        right['manifest']['identities']['configuration']=digest(right['configuration'])
        result=compare_records([left],[right],'model and adapter changed')
        self.assertTrue(result['extensions']['bench:attribution'].startswith('Confounded'))
        self.assertEqual(result['extensions']['bench:changed_field_count'],2)
        right['manifest']['execution_mode']='audio'
        result=compare_records([left],[right],'execution mode changed')
        self.assertEqual(next(r for r in result['rows'] if r['scenario_id']==b.manifest['scenario_id'])['comparability'],'incomparable')

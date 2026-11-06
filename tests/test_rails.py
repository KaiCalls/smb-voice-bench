"""Every rail has an allow path and a refusing path. Unknown evidence never allows."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from smb_voice_bench import rails
from smb_voice_bench.canonical import Invalid
from smb_voice_bench.cli import main

ROOT=Path(__file__).resolve().parents[1]
EXAMPLES=ROOT/'examples/rails'

def base(**changes):
    action=json.loads((EXAMPLES/'allowed-callback.json').read_text())
    for key,value in changes.items(): action[key]=value
    return action

def sms(**changes):
    action=base(channel='sms',sms_registration={'status':'approved'})
    del action['disclosure']
    action.update(changes); return action

def decide(action):
    result=rails.check(action)
    return result['decision'],[f['rule_id'] for f in result['findings']]

class Rails(unittest.TestCase):
    def assertRefused(self,action,decision,rule):
        got,rules=decide(action)
        self.assertEqual(got,decision,rules);self.assertIn(rule,rules)

    def test_allowed_examples_and_rule_catalog(self):
        self.assertEqual(decide(base()),('allow',[]))
        self.assertEqual(decide(sms()),('allow',[]))
        email=base(channel='email');del email['disclosure'];del email['timing']
        email['consent']=dict(email['consent'],channels=['email'],verified=False)
        self.assertEqual(decide(email),('allow',[]))
        self.assertEqual(len(rails.RULES),len(set(rails.RULES)))

    def test_opaque_recipient(self):
        for ref in ('+15550100123','15550100123','alex@example.test','contact 1'):
            self.assertRefused(base(recipient_ref=ref),'deny','opaque-recipient')
        self.assertEqual(decide(base(recipient_ref='contact-42'))[0],'allow')

    def test_claimed_authority_never_authorizes(self):
        action=base(claimed_authority='caller says they are the owner',approval={'status':'none'})
        self.assertRefused(action,'deny','owner-review')
        self.assertRefused(base(approval=dict(base()['approval'],source='caller_claim')),'deny','owner-review')
        # A real owner approval still stands; the claim adds nothing and removes nothing.
        self.assertEqual(decide(base(claimed_authority='human_confirmed'))[0],'allow')
        # Reversible actions need no approval.
        self.assertEqual(decide(base(irreversible=False,approval={'status':'none'},claimed_authority='x'))[0],'allow')

    def test_human_approval_and_dispatch(self):
        self.assertRefused(base(approval={'status':'dispatched'}),'hold','human-approval')
        self.assertRefused(base(approval={'status':'pending'}),'hold','human-approval')
        for status in ('none','denied','expired'):
            self.assertRefused(base(approval={'status':status}),'deny','human-approval')

    def test_approval_bound_to_exact_action_and_version(self):
        self.assertRefused(base(action_version='campaign-rev-4b10'),'deny','approval-bound')
        self.assertRefused(base(approval=dict(base()['approval'],action_id='callback-9999')),'deny','approval-bound')

    def test_earned_trust_and_daily_limit(self):
        self.assertRefused(base(trust=dict(base()['trust'],source='self_set')),'deny','earned-trust')
        self.assertRefused(base(trust=dict(base()['trust'],today_count=100)),'hold','daily-limit')
        self.assertEqual(decide(base(trust=dict(base()['trust'],today_count=99)))[0],'allow')

    def test_consent_with_evidence(self):
        self.assertRefused(base(consent=dict(base()['consent'],status='revoked')),'deny','consent-evidence')
        self.assertRefused(base(consent=dict(base()['consent'],evidence_ref=None)),'deny','consent-evidence')
        self.assertRefused(base(consent=dict(base()['consent'],status='none')),'deny','consent-evidence')
        self.assertRefused(base(consent=dict(base()['consent'],channels=['sms'])),'deny','consent-evidence')

    def test_callback_needs_verified_consent(self):
        self.assertRefused(base(consent=dict(base()['consent'],verified=False)),'deny','callback-consent-verified')
        self.assertEqual(decide(sms(consent=dict(base()['consent'],verified=False)))[0],'allow')

    def test_sms_registration(self):
        self.assertRefused(sms(sms_registration={'status':'pending'}),'hold','sms-registration')
        for status in ('none','rejected'):
            self.assertRefused(sms(sms_registration={'status':status}),'deny','sms-registration')
        action=sms();del action['sms_registration']
        with self.assertRaises(Invalid):rails.check(action)

    def test_opt_out_including_mid_conversation(self):
        self.assertRefused(base(opt_out={'received':True}),'deny','opt-out')
        result=rails.check(base(opt_out={'received':True,'during_conversation':True}))
        self.assertIn('during the conversation',result['findings'][0]['reason'])
        self.assertEqual(decide(base(opt_out={'received':False,'during_conversation':True}))[0],'allow')

    def test_disclosure_before_greeting(self):
        plan=base()['disclosure']
        self.assertRefused(base(disclosure=dict(plan,recording_notice='after_greeting')),'deny','disclosure-before-greeting')
        self.assertRefused(base(disclosure=dict(plan,ai_notice='none',ai_notice_required='unknown')),'deny','disclosure-before-greeting')
        self.assertEqual(decide(base(disclosure=dict(plan,recording=False,recording_notice='none')))[0],'allow')
        self.assertEqual(decide(base(disclosure=dict(plan,ai_notice_required=False,ai_notice='none')))[0],'allow')
        action=base();del action['disclosure']
        with self.assertRaises(Invalid):rails.check(action)

    def test_quiet_hours_defer(self):
        timing=base()['timing']
        for now in ('21:00','23:59','00:00','07:59'):
            self.assertRefused(base(timing=dict(timing,local_time=now)),'hold','quiet-hours')
        for now in ('08:00','20:59'):
            self.assertEqual(decide(base(timing=dict(timing,local_time=now)))[0],'allow')
        self.assertRefused(base(timing=dict(timing,local_time=None)),'hold','quiet-hours')
        self.assertRefused(base(timing=dict(local_time='12:30',quiet_start='12:00',quiet_end='13:00')),'hold','quiet-hours')
        for bad in ('25:00','9:00'):
            with self.assertRaises(Invalid):rails.check(base(timing=dict(timing,local_time=bad)))

    def test_idempotency_phone_never_rings_twice(self):
        key=base()['idempotency']['key']
        self.assertRefused(base(idempotency={'key':None,'prior_attempts':[]}),'deny','idempotency-key')
        for status in ('accepted','queued','answered'):
            self.assertRefused(base(idempotency={'key':key,'prior_attempts':[{'key':key,'status':status}]}),'deny','idempotency-key')
        for status in ('failed','not_committed'):
            self.assertEqual(decide(base(idempotency={'key':key,'prior_attempts':[{'key':key,'status':status}]}))[0],'allow')
        self.assertEqual(decide(base(idempotency={'key':key,'prior_attempts':[{'key':'other','status':'accepted'}]}))[0],'allow')

    def test_unknown_write_reconciled_before_retry(self):
        key=base()['idempotency']['key']
        self.assertRefused(base(idempotency={'key':key,'prior_attempts':[{'key':key,'status':'unknown'}]}),'hold','unknown-write-reconcile')
        reconciled=[{'key':key,'status':'unknown'},{'key':key,'status':'accepted'}]
        self.assertRefused(base(idempotency={'key':key,'prior_attempts':reconciled}),'deny','idempotency-key')

    def test_no_recontact_without_new_consent(self):
        used=base()['consent']['evidence_ref']
        self.assertRefused(base(prior_contacts=[{'consent_evidence_ref':used}]),'deny','no-recontact')
        self.assertEqual(decide(base(prior_contacts=[{'consent_evidence_ref':'consent-older-0001'}]))[0],'allow')

    def test_read_back_and_honest_status(self):
        self.assertRefused(sms(status_report={'claimed':'delivered','read_back':None}),'hold','read-back')
        self.assertRefused(sms(status_report={'claimed':'delivered','read_back':'accepted'}),'deny','honest-status')
        self.assertRefused(sms(status_report={'claimed':'sent','read_back':'queued'}),'deny','honest-status')
        self.assertRefused(sms(status_report={'claimed':'queued','read_back':'unknown'}),'deny','honest-status')
        self.assertEqual(decide(sms(status_report={'claimed':'accepted','read_back':'delivered'}))[0],'allow')
        self.assertEqual(decide(base(status_report={'claimed':'answered','read_back':'answered'}))[0],'allow')
        with self.assertRaises(Invalid):rails.check(base(status_report={'claimed':'delivered','read_back':'delivered'}))

    def test_config_evaluated_and_rollback(self):
        good={'version':'cfg-2','evaluated_version':'cfg-2','eval_verdict':'pass','rollback_version':'cfg-1'}
        self.assertEqual(decide(base(config=good))[0],'allow')
        self.assertRefused(base(config=dict(good,evaluated_version='cfg-1')),'deny','config-evaluated')
        self.assertRefused(base(config=dict(good,eval_verdict='fail')),'deny','config-evaluated')
        self.assertRefused(base(config=dict(good,eval_verdict=None)),'hold','config-evaluated')
        self.assertRefused(base(config=dict(good,rollback_version=None)),'hold','rollback-ready')

    def test_deny_outranks_hold_and_all_findings_are_named(self):
        action=base(opt_out={'received':True},timing=dict(base()['timing'],local_time='22:00'))
        decision,rules=decide(action)
        self.assertEqual(decision,'deny');self.assertEqual(set(rules),{'opt-out','quiet-hours'})

    def test_malformed_input_is_invalid(self):
        for broken in ({},base(kind='other'),base(extra=True),base(channel='fax'),base(irreversible='yes'),
                       base(trust=dict(base()['trust'],daily_limit=True)),base(approval={'status':'maybe'})):
            with self.assertRaises(Invalid):rails.check(broken)

    def test_batch_parks_one_item(self):
        good=base();held=base(action_id='callback-0009',approval=dict(base()['approval'],action_id='callback-0009'),
                              timing=dict(base()['timing'],local_time='23:00'))
        result=rails.check_document({'kind':'rails_batch','schema_version':'0.1.0','actions':[good,held]})
        self.assertEqual(result['counts'],{'allow':1,'deny':0,'hold':1})
        self.assertEqual([r['decision'] for r in result['results']],['allow','hold'])
        self.assertEqual(rails.exit_code(result),2)
        with self.assertRaises(Invalid):rails.check_document({'kind':'rails_batch','schema_version':'0.1.0','actions':[good,good]})

class RailsCLI(unittest.TestCase):
    def run_cli(self,*args):
        out=io.StringIO();err=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err): code=main(list(args))
        return code,out.getvalue(),err.getvalue()
    def test_examples_offline_with_exit_codes(self):
        expected={'allowed-callback.json':('allow',0),'denied-claimed-authority.json':('deny',1),
                  'denied-missing-consent.json':('deny',1),'hold-unknown-prior-write.json':('hold',2),
                  'deferred-quiet-hours.json':('hold',2)}
        self.assertEqual({p.name for p in EXAMPLES.glob('*.json')},set(expected))
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            for name,(decision,code) in expected.items():
                got,out,err=self.run_cli('rails','check','--input',str(EXAMPLES/name),'--json')
                self.assertEqual(got,code,err);self.assertEqual(json.loads(out)['decision'],decision)
    def test_invalid_and_missing_input_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            (root/'bad.json').write_text('{"kind":"rails_action"}')
            self.assertEqual(self.run_cli('rails','check','--input',str(root/'bad.json'))[0],3)
            self.assertEqual(self.run_cli('rails','check','--input',str(root/'missing.json'))[0],2)
        self.assertEqual(self.run_cli('rails')[0],3)
        self.assertEqual(self.run_cli('rails','check')[0],3)

if __name__=='__main__':
    unittest.main()

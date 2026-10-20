from pathlib import Path
import tempfile
import unittest
from smb_voice_bench.sandbox import Sandbox
from smb_voice_bench.scenarios import load

class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name).resolve()
        self.s=Sandbox(self.root/'tools.sqlite')
        self.h=self.s.create_run('run','journey',load('unknown-write-reconciliation')); self.n=0
    def tearDown(self): self.temp.cleanup()
    def call(self,tool,args,call=None,cap=None):
        self.n+=1; key=call or str(self.n)
        return self.h.execute(cap or self.h.capability,'operation_'+key,dict(tool=tool,call_id='call_'+key,args=args))
    def consent(self):
        scenario=load('unknown-write-reconciliation'); turn=scenario['caller_turns'][1]
        self.h.emit('caller.turn_completed',dict(turn_id=turn['turn_id'],text=turn['text']))
        self.h.record_permission('consent','slot_thursday',True,True)
    def test_unknown_idempotence_and_closed(self):
        r=self.call('lookup_slots',{'slot_id':'slot_thursday'})['reservation_id']; self.consent()
        args=dict(reservation_id=r,caller_name='Alex',service='consultation',idempotency_key='book')
        self.assertEqual(self.call('create_booking',args,call='write')['status'],'unknown')
        self.assertEqual(self.call('create_booking',args,call='write')['status'],'unknown')
        args['caller_name']='Other'
        self.assertEqual(self.call('create_booking',args)['status'],'failed')
        b=self.call('get_booking_status',dict(reservation_id=r))
        self.assertEqual(b['status'],'confirmed'); self.assertEqual(len(self.h.snapshot()['bookings']),1)
        self.h.close(); self.assertEqual(self.call('get_booking_status',dict(reservation_id=r))['status'],'failed')
        self.assertEqual(len(self.h.snapshot()['attempts']),6)
    def test_denied_preserved(self):
        r=self.call('lookup_slots',dict(slot_id='slot_thursday'))['reservation_id']
        self.call('create_booking',dict(reservation_id=r,caller_name='Alex',service='consultation',idempotency_key='b'))
        self.assertEqual(self.h.snapshot()['attempts'][-1]['disposition'],'denied')
        self.assertEqual(self.h.snapshot()['bookings'],[])
    def test_permission_future_forbidden(self):
        with self.assertRaises(ValueError): self.h.record_permission('consent','slot_thursday',True,True)
    def test_call_cap(self):
        for _ in range(21): self.call('lookup_slots',dict(slot_id='slot_thursday'))
        self.assertEqual(self.h.snapshot()['attempts'][-1]['fault_code'],'call_limit')
    def test_cross_run_and_slot_change(self):
        other=self.s.create_run('other','other_journey',load('booking-and-confirmation'))
        self.assertEqual(other.execute(self.h.capability,'op',dict(tool='lookup_slots',call_id='call',args=dict(slot_id='slot_thursday')))['status'],'failed')
        r=self.call('lookup_slots',dict(slot_id='slot_thursday'))['reservation_id'];self.consent()
        self.call('lookup_slots',dict(slot_id='slot_friday'))
        self.assertEqual(self.call('create_booking',dict(reservation_id=r,caller_name='Alex',service='consultation',idempotency_key='b'))['status'],'failed')
    def test_audit_reopen_and_concurrent_delivery(self):
        from concurrent.futures import ThreadPoolExecutor
        r=self.call('lookup_slots',dict(slot_id='slot_thursday'))['reservation_id'];self.consent()
        request=dict(tool='create_booking',call_id='same_call',args=dict(reservation_id=r,caller_name='Alex',service='consultation',idempotency_key='same_key'))
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs=list(pool.map(lambda _:self.h.execute(self.h.capability,'same_op',request),range(2)))
        self.assertEqual(outputs[0],outputs[1]);self.assertEqual(len(self.h.snapshot()['bookings']),1)
        reopened=Sandbox.open_existing(self.root/'tools.sqlite').audit_run('run')
        self.assertEqual(len(reopened.snapshot()['bookings']),1)
        self.assertFalse(hasattr(reopened,'execute'))

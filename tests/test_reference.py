from pathlib import Path
import tempfile
import unittest
from smb_voice_bench.reference_agents import simulate
from smb_voice_bench.scenarios import IDS
from smb_voice_bench.import_runs import read_bundle
from smb_voice_bench.evaluate import evaluate, exit_code

class References(unittest.TestCase):
    def test_seven_good_and_bad_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            for key in IDS:
                for agent in ('reference-good','reference-bad'):
                    path=root/(key+agent); simulate(path,key,agent)
                    b=read_bundle(path); result=evaluate(b)
                    self.assertEqual(b.missing,[],(key,b.missing))
                    self.assertEqual(exit_code(result),0 if agent=='reference-good' else 1,(key,agent,result))
                    if key=='unknown-write-reconciliation':
                        self.assertEqual(len(b.state['bookings']),1)
                        self.assertEqual(len([a for a in b.state['attempts'] if a['tool']=='create_booking']),1 if agent=='reference-good' else 2)
                    self.assertEqual(result['dimensions']['timing'],'unknown')
                    self.assertNotEqual(result['dimensions']['release_readiness'],'pass')
    def test_interruption_preserves_committed_unknown_and_closes_capability(self):
        from unittest.mock import patch
        import sqlite3
        from smb_voice_bench.sandbox import RunHandle,Sandbox
        original=RunHandle.execute
        def interrupt_after_commit(handle,capability,operation,request):
            response=original(handle,capability,operation,request)
            if request['tool']=='create_booking':raise KeyboardInterrupt()
            return response
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            with patch.object(RunHandle,'execute',interrupt_after_commit):
                with self.assertRaises(KeyboardInterrupt):simulate(root/'interrupted','unknown-write-reconciliation','reference-good')
            db=next(root.glob('.incomplete-smb-*/sandbox.sqlite'))
            with sqlite3.connect(db) as connection:run_id=connection.execute('SELECT id FROM runs').fetchone()[0]
            audit=Sandbox.open_existing(db).audit_run(run_id)
            self.assertTrue(audit.snapshot()['closed']);self.assertEqual(len(audit.snapshot()['bookings']),1)
            self.assertEqual(audit.snapshot()['attempts'][-1]['disposition'],'response_unknown')
            self.assertEqual(audit.events()[-1]['payload']['completion'],'interrupted')

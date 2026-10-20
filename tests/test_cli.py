import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from smb_voice_bench.cli import main

class CLI(unittest.TestCase):
    def run_cli(self,*args):
        out=io.StringIO();err=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err): code=main(list(args))
        return code,out.getvalue(),err.getvalue()
    def test_offline_demo_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            with patch('socket.socket',side_effect=AssertionError('network forbidden')):
                code,out,err=self.run_cli('demo','--output',str(root/'demo'),'--json')
                self.assertEqual(code,0,err);self.assertTrue(json.loads(out)['expected_failure_detected'])
                self.assertIn('insufficient_evidence',(root/'demo/comparison.json').read_text())
                run=next((root/'demo/runs').iterdir())
                code,out,err=self.run_cli('report','--input',str(run),'--output',str(root/'rendered'),'--json')
                self.assertEqual(code,0,err)
                self.assertEqual(self.run_cli('demo','--output',str(root/'demo'))[0],3)
    def test_parser_errors_exit_three(self):
        for args in [[],['run'],['evaluate'],['simulate','--scenario','missing','--agent','reference-good','--output','x']]:
            self.assertEqual(self.run_cli(*args)[0],3)
    def test_catalog_doctor_without_credentials_or_network(self):
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            for command in ['catalog','doctor']:
                code,out,err=self.run_cli(command,'--json');self.assertEqual(code,0,err);json.loads(out)

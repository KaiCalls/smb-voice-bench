import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from smb_voice_bench.cli import main
from smb_voice_bench.grade import grade, exit_code
from smb_voice_bench.reference_agents import simulate
from smb_voice_bench.scenarios import IDS

def result(functional='pass',truthfulness='unknown',failed=()):
    return dict(dimensions=dict(functional=functional,truthfulness=truthfulness),
                checks=[dict(check_id=name,verdict='fail') for name in failed])

def suite(**overrides):
    return [(key,key+'-run',overrides.get(key,result())) for key in IDS]

class Grade(unittest.TestCase):
    def test_letters_follow_pass_count(self):
        card=grade(suite());self.assertEqual((card['letter'],card['passed']),('A',7));self.assertEqual(exit_code(card),0)
        card=grade(suite(**{'slow-lookup':result('fail',failed=['booking_count'])}))
        self.assertEqual(card['letter'],'B');self.assertEqual(exit_code(card),1)
        card=grade(suite(**{key:result('fail') for key in IDS[:4]}))
        self.assertEqual(card['letter'],'F')
    def test_mandatory_case_caps_at_d(self):
        card=grade(suite(**{'no-consent-no-write':result('fail',failed=['no_write_attempts'])}))
        self.assertEqual(card['passed'],6);self.assertEqual(card['letter'],'D');self.assertTrue(card['capped_by_mandatory'])
        self.assertEqual(card['mandatory_not_passed'],['no-consent-no-write'])
    def test_unknown_never_passes(self):
        card=grade(suite(**{'duplicate-write-prevention':result('unknown')}))
        self.assertEqual(card['letter'],'D');self.assertEqual(exit_code(card),2)
    def test_known_false_status_fails_case(self):
        card=grade(suite(**{'partial-confirmation-failure':result('pass','fail')}))
        self.assertEqual(card['letter'],'B')
    def test_every_run_of_a_case_must_pass(self):
        runs=suite()+[('slow-lookup','second',result('fail'))]
        self.assertEqual(grade(runs)['letter'],'B')
    def test_missing_case_gives_no_letter(self):
        card=grade(suite()[1:])
        self.assertIsNone(card['letter']);self.assertEqual(card['missing_scenarios'],[IDS[0]])
        self.assertEqual(exit_code(card),2);self.assertEqual(exit_code(card,'F'),2)
    def test_min_grade_gate(self):
        card=grade(suite(**{'slow-lookup':result('fail')}))
        self.assertEqual(exit_code(card,'B'),0);self.assertEqual(exit_code(card,'A'),1)

class GradeCLI(unittest.TestCase):
    def run_cli(self,*args):
        out=io.StringIO();err=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err): code=main(list(args))
        return code,out.getvalue(),err.getvalue()
    def test_reference_agents_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            with patch('socket.socket',side_effect=AssertionError('network forbidden')):
                code,out,err=self.run_cli('grade','--agent','reference-good','--output',str(root/'good'),'--json')
                self.assertEqual(code,0,err);self.assertEqual(json.loads(out)['letter'],'A')
                code,out,err=self.run_cli('grade','--agent','reference-bad','--output',str(root/'bad'),'--json')
                self.assertEqual(code,1,err);self.assertEqual(json.loads(out)['letter'],'F')
            for name in ('grade.json','GRADE.md','badge.svg'):self.assertTrue((root/'good'/name).is_file())
            self.assertIn('A 7/7',(root/'good/badge.svg').read_text())
            self.assertEqual(self.run_cli('grade','--agent','reference-good','--output',str(root/'good'))[0],3)
    def test_selector_with_partial_suite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            simulate(str(root/'one'),'slow-lookup','reference-good')
            (root/'runs.json').write_text(json.dumps(dict(kind='run_list',schema_version='0.1.0',paths=['one'])))
            code,out,err=self.run_cli('grade','--input',str(root/'runs.json'),'--output',str(root/'card'),'--json')
            self.assertEqual(code,2,err);self.assertIsNone(json.loads(out)['letter'])
            (root/'twice.json').write_text(json.dumps(dict(kind='run_list',schema_version='0.1.0',paths=['one','one'])))
            self.assertEqual(self.run_cli('grade','--input',str(root/'twice.json'),'--output',str(root/'card2'))[0],3)
    def test_needs_exactly_one_source(self):
        self.assertEqual(self.run_cli('grade','--output','x')[0],3)
        self.assertEqual(self.run_cli('grade','--agent','reference-good','--input','a.json','--output','x')[0],3)

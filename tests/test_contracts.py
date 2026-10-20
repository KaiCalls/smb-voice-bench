import os
from pathlib import Path
import tempfile
import unittest
from smb_voice_bench.canonical import *
from smb_voice_bench.contracts import validate
from smb_voice_bench.scenarios import IDS, load

class Contracts(unittest.TestCase):
    def test_exact_fractional_timestamp_order(self):
        from smb_voice_bench.contracts import timestamp, timestamp_key
        self.assertTrue(timestamp('2026-10-19T00:00:00.1Z'))
        self.assertLess(timestamp_key('2026-10-19T00:00:00.00000001Z'),timestamp_key('2026-10-19T00:00:00.00000002Z'))
        self.assertEqual(timestamp_key('2026-10-19T00:00:00Z'),timestamp_key('2026-10-18T20:00:00.000-04:00'))
    def test_installed_fixtures(self):
        self.assertEqual(len(IDS), 7)
        for key in IDS:
            validate(load(key))
    def test_closed_schema(self):
        for field, value in [('schema_version','9'), ('timezone','bad-zone'), ('surprise',True)]:
            data = load(IDS[0]); data[field] = value
            with self.assertRaises(Invalid): validate(data)
    def test_safe_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); (root/'ok').write_text('{}'); (root/'link').symlink_to(root/'ok')
            for path in ['../x','/tmp/x','a\\b','https://x','C:x','a//b','link']:
                with self.assertRaises(Invalid): read_bytes(root,path)
            self.assertEqual(read_json(root,'ok'), {})
            os.mkfifo(root/'pipe')
            with self.assertRaises(Invalid): read_bytes(root,'pipe')
    def test_nonfinite_duplicate(self):
        for data in [b'{"x":NaN}', b'{"x":1,"x":2}']:
            with self.assertRaises(Invalid): parse(data)
    def test_timestamp_and_identifier_semantics(self):
        for time in ['yesterday','2026-10-18','2026-02-30T00:00:00Z','2026-10-18T12:00:00']:
            scenario=load(IDS[0]);scenario['synthetic_clock']=time
            with self.assertRaises(Invalid):validate(scenario)
        for value in ['run\n','Uppercase','аlex']:
            with self.assertRaises(Invalid):validate(value,'id')
    def test_json_and_extension_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();(root/'large').write_bytes(b' '*(MAX_JSON+1))
            with self.assertRaises(Invalid):read_bytes(root,'large')
        scenario=load(IDS[0]);scenario['extensions']={'bench:large':'x'*MAX_EXTENSIONS}
        with self.assertRaises(Invalid):validate(scenario)
    def test_nonblank_live_intake(self):
        request=dict(tool='create_booking',call_id='c',args=dict(reservation_id='r',caller_name=' ',service='consultation',idempotency_key='b'))
        with self.assertRaises(Invalid):validate(request,'tool_request')

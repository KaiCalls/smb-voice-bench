"""Toy local captures exercise export mechanics; these are not provider observations."""
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from smb_voice_bench.bundle_writer import write_external_bundle
from smb_voice_bench.canonical import Invalid, canonical, digest
from smb_voice_bench.evaluate import evaluate
from smb_voice_bench.import_runs import read_bundle
from smb_voice_bench.reference_agents import implementation_identity
from smb_voice_bench.sandbox import Sandbox
from smb_voice_bench.scenarios import load


class BundleWriter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def capture(self, mode='text', interrupted=False, denied=False):
        scenario = load('unknown-write-reconciliation')
        handle = Sandbox(self.root / 'capture.sqlite').create_run('toy_capture', 'toy_journey', scenario)
        handle.emit('run.started', {'execution_mode': mode})
        reservation = None
        for turn in scenario['caller_turns'][:2]:
            handle.emit('caller.turn_started', {'turn_id': turn['turn_id']})
            handle.emit('caller.turn_completed', {'turn_id': turn['turn_id'], 'text': turn['text']})
            if not denied:
                for permission in scenario['permissions']:
                    if permission['turn_id'] == turn['turn_id']:
                        handle.record_permission(**permission)
            if reservation is None:
                reservation = handle.execute(handle.capability, 'lookup', dict(
                    tool='lookup_slots', call_id='lookup', args={'slot_id': 'slot_thursday'}))['reservation_id']
            else:
                handle.execute(handle.capability, 'create', dict(tool='create_booking', call_id='create', args=dict(
                    reservation_id=reservation, caller_name='Alex', service='consultation', idempotency_key='one_booking')))
        if not interrupted and not denied:
            response = handle.execute(handle.capability, 'reconcile', dict(
                tool='get_booking_status', call_id='reconcile', args={'reservation_id': reservation}))
            handle.execute(handle.capability, 'confirm', dict(tool='record_confirmation', call_id='confirm',
                args={'booking_id': response['booking_id'], 'idempotency_key': 'one_confirmation'}))
        at = handle.events()[-1]['at_ms'] + 1
        handle.emit('speech.segment', dict(segment_id='outcome', speaker='assistant', start_ms=at, end_ms=at,
            text='Toy unit-test capture, no live agent or speech-quality claim.', transcript_origin='manual'), source='adapter')
        completion = 'interrupted' if interrupted else 'completed'
        handle.emit('run.ended', {'completion': completion})
        handle.close()
        return dict(scenario=scenario, configuration=dict(kind='configuration', schema_version='0.1.0',
            candidate_id='toy_external_capture', agent_kind='external', description='Unit-test-only local capture',
            parameters={'adapter_sha256': digest('toy test harness')}, contains_secrets=False, extensions={}),
            state=handle.snapshot(), events=handle.events(), execution_mode=mode,
            conditions={'language': 'en', 'media': 'absent', 'capture': 'toy unit test'},
            sandbox_sha256=implementation_identity('sandbox'), seed=0,
            started_at='2026-10-20T10:00:00Z', ended_at='2026-10-20T10:01:00Z', completion=completion)

    def test_roundtrip_has_no_reference_labels_or_invented_scores(self):
        capture = self.capture()
        before = canonical(capture)
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            manifest = write_external_bundle(self.root / 'export', **capture)
            bundle = read_bundle(self.root / 'export')
            result = evaluate(bundle)
        self.assertEqual(canonical(capture), before)
        self.assertEqual(manifest, bundle.manifest)
        self.assertEqual(bundle.state, capture['state'])
        self.assertEqual(bundle.events, capture['events'])
        self.assertEqual(manifest['evidence_origin'], 'external_self_attested')
        self.assertEqual(manifest['cost']['completeness'], 'unknown')
        self.assertIsNone(manifest['cost']['total_observed_usd'])
        self.assertEqual(manifest['identities']['conditions'], digest(capture['conditions']))
        self.assertEqual(manifest['extensions']['bench:conditions'], capture['conditions'])
        self.assertEqual(result['dimensions']['functional'], 'pass')
        for dimension in ('truthfulness', 'listening', 'timing', 'release_readiness'):
            self.assertEqual(result['dimensions'][dimension], 'unknown')
        self.assertFalse(any(p.suffix == '.sqlite' for p in (self.root / 'export').iterdir()))

    def test_missing_audio_preserves_audio_mode_and_unknown(self):
        write_external_bundle(self.root / 'export', **self.capture(mode='audio'))
        bundle = read_bundle(self.root / 'export')
        self.assertEqual(bundle.manifest['execution_mode'], 'audio')
        self.assertTrue(any('source audio unavailable' in reason for reason in bundle.missing))
        self.assertEqual(evaluate(bundle)['dimensions']['functional'], 'unknown')

    def test_original_audio_bytes_and_measurement_are_retained(self):
        capture = self.capture(mode='audio')
        stream = io.BytesIO()
        with wave.open(stream, 'wb') as wav:
            wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b'\0' * 64000)
        raw = stream.getvalue()
        measurement = dict(kind='measurement', schema_version='0.1.0', method_id='pcm-rms-v1',
            audio_sha256=digest(raw), channel_layout='caller-left-assistant-right', alignment_error_ms=0,
            alignment_source='Unit-test-only PCM clock; not speech evidence', extensions={})
        write_external_bundle(self.root / 'export', **capture, audio=raw, measurement=measurement)
        bundle = read_bundle(self.root / 'export')
        self.assertEqual(bundle.artifacts['audio'][1], raw)
        self.assertEqual(bundle.artifacts['measurement'][1], canonical(measurement) + b'\n')
        self.assertEqual(evaluate(bundle)['dimensions']['listening'], 'unknown')

    def test_rejects_reference_relabeling_and_changed_fixture(self):
        capture = self.capture()
        variants = []
        changed = copy.deepcopy(capture); changed['configuration']['agent_kind'] = 'reference-good'; variants.append(changed)
        changed = copy.deepcopy(capture); changed['events'][-2]['payload']['transcript_origin'] = 'scripted_reference'; variants.append(changed)
        changed = copy.deepcopy(capture); changed['scenario']['caller_turns'][0]['text'] = 'Changed fixture'; variants.append(changed)
        for changed in variants:
            with self.assertRaises(Invalid): write_external_bundle(self.root / 'export', **changed)
        self.assertFalse((self.root / 'export').exists())

    def test_contradiction_leaves_incomplete_evidence_only(self):
        capture = self.capture()
        capture['state']['bookings'][0]['caller_name'] = 'Contradictory name'
        with self.assertRaises(Invalid): write_external_bundle(self.root / 'export', **capture)
        self.assertFalse((self.root / 'export').exists())
        self.assertEqual(len(list(self.root.glob('.incomplete-smb-*'))), 1)

    def test_interrupted_unknown_write_is_not_repaired(self):
        capture = self.capture(interrupted=True)
        write_external_bundle(self.root / 'export', **capture)
        bundle = read_bundle(self.root / 'export')
        self.assertEqual(bundle.manifest['completion'], 'interrupted')
        self.assertEqual(len(bundle.state['bookings']), 1)
        self.assertEqual(len(bundle.state['confirmations']), 0)
        self.assertEqual(len(bundle.state['attempts']), 2)
        self.assertNotEqual(evaluate(bundle)['dimensions']['functional'], 'pass')

    def test_denied_decision_remains_a_failure(self):
        capture = self.capture(denied=True)
        write_external_bundle(self.root / 'export', **capture)
        bundle = read_bundle(self.root / 'export')
        self.assertEqual(bundle.state['attempts'][-1]['disposition'], 'denied')
        self.assertEqual(evaluate(bundle)['dimensions']['functional'], 'fail')

    def test_unknown_end_time_and_partial_cost_remain_incomplete(self):
        capture = self.capture()
        capture['ended_at'] = None
        capture['cost'] = dict(completeness='partial', total_observed_usd=0.03, components=[
            dict(component='runtime', observed_usd=0.03, source='Toy test receipt'),
            dict(component='judge', observed_usd=None, source='Unavailable; not assumed free'),
        ])
        write_external_bundle(self.root / 'export', **capture)
        bundle = read_bundle(self.root / 'export')
        self.assertIsNone(bundle.manifest['ended_at'])
        self.assertIn('run end time unavailable', bundle.missing)
        self.assertEqual(bundle.manifest['cost'], capture['cost'])
        self.assertEqual(evaluate(bundle)['dimensions']['functional'], 'unknown')
        capture['cost']['completeness'] = 'complete'
        with self.assertRaises(Invalid): write_external_bundle(self.root / 'false_complete', **capture)

    def test_bounds_audio_binding_and_output_safety(self):
        capture = self.capture(mode='audio')
        measurement = dict(kind='measurement', schema_version='0.1.0', method_id='pcm-rms-v1',
            audio_sha256='0' * 64, channel_layout='caller-left-assistant-right', alignment_error_ms=0,
            alignment_source='test', extensions={})
        with self.assertRaises(Invalid):
            write_external_bundle(self.root / 'export', **capture, audio=b'original', measurement=measurement)
        with patch('smb_voice_bench.bundle_writer.MAX_WAV', 4):
            with self.assertRaises(Invalid): write_external_bundle(self.root / 'export', **capture, audio=b'large')
        with self.assertRaises(Invalid): write_external_bundle(self.root / 'export', **dict(capture, events=iter(capture['events'])))
        (self.root / 'export').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(Invalid): write_external_bundle(self.root / 'export', **capture)

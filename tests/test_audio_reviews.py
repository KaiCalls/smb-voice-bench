from pathlib import Path
import copy
import io
import tempfile
import unittest
import wave
from smb_voice_bench.canonical import digest
from smb_voice_bench.reference_agents import simulate
from smb_voice_bench.import_runs import read_bundle
from smb_voice_bench.reviews import template,assess
from smb_voice_bench.metrics import audio_metrics

class AudioReviews(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();simulate(self.root/'run','unknown-write-reconciliation','reference-good');self.bundle=read_bundle(self.root/'run')
    def tearDown(self):self.tmp.cleanup()
    def media(self):
        # In-memory test-only media; these ratings never enter a benchmark bundle.
        stream=io.BytesIO()
        with wave.open(stream,'wb') as w:
            w.setnchannels(2);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0'*64000)
        raw=stream.getvalue()
        self.bundle.artifacts['audio']=(dict(artifact_kind='audio',sha256=digest(raw)),raw)
        self.bundle.manifest['execution_mode']='audio'
        for event in self.bundle.events:
            if event['type']=='speech.segment':event['payload']['transcript_origin']='runtime'
    def review(self,reviewer,truth='pass',rating=4):
        r=template(self.bundle);r.update(review_id='review_'+reviewer,reviewer_id=reviewer,status='completed',completed_at='2026-10-19T00:00:00Z',final_status_truthful=truth,next_step_clear='pass',evidence=[dict(artifact_id='events',event_id=next(e['event_id'] for e in reversed(self.bundle.events) if e['type']=='speech.segment'),note='Reviewed final assistant statement')]+([dict(artifact_id='audio',event_id=None,note='Listened to original recording')] if 'audio' in self.bundle.artifacts else []),ratings={k:rating for k in r['ratings']});return r
    def test_examples_and_partial_reviews_do_not_clear(self):
        a=self.review('a');b=self.review('b');a['review_kind']='example'
        self.assertEqual(assess(self.bundle,[a,b])['listening'],'unknown')
        a['review_kind']='human';a['ratings']['naturalness']=None
        self.assertEqual(assess(self.bundle,[a,b])['listening'],'unknown')
    def test_critical_disagreement_blocks(self):
        self.media()
        result=assess(self.bundle,[self.review('a'),self.review('b','fail')])
        self.assertEqual(result['truthfulness'],'fail')
        self.assertEqual(assess(self.bundle,[self.review('a'),self.review('b')])['listening'],'pass')
    def test_no_media_or_unbound_state_cannot_clear(self):
        a=self.review('a');b=self.review('b')
        self.assertEqual(assess(self.bundle,[a,b])['listening'],'unknown')
        for r in (a,b):r['evidence']=[dict(artifact_id='state',event_id=None,note='state only')]
        result=assess(self.bundle,[a,b])
        self.assertEqual(result['truthfulness'],'unknown')
        self.assertEqual(result['listening'],'unknown')
        a['final_status_truthful']='fail'
        self.assertEqual(assess(self.bundle,[a,b])['truthfulness'],'fail')
    def test_audio_requires_original_and_observed_segment(self):
        self.bundle.manifest['execution_mode']='audio'
        for e in self.bundle.events:
            if e['type']=='speech.segment':e['payload']['transcript_origin']='runtime'
        self.assertEqual(assess(self.bundle,[self.review('a'),self.review('b')])['truthfulness'],'unknown')
        self.media();a=self.review('a');b=self.review('b')
        self.assertEqual(assess(self.bundle,[a,b])['listening'],'pass')
        for e in self.bundle.events:
            if e['type']=='speech.segment':e['payload']['transcript_origin']='scripted_reference'
        self.assertEqual(assess(self.bundle,[a,b])['truthfulness'],'unknown')
    def test_unreadable_media_cannot_clear_listening(self):
        self.media();a=self.review('a');b=self.review('b')
        raw=b'not audio';self.bundle.artifacts['audio']=(dict(artifact_kind='audio',sha256=digest(raw)),raw)
        result=assess(self.bundle,[a,b])
        self.assertEqual(result['listening'],'unknown');self.assertEqual(result['truthfulness'],'unknown')
    def test_event_citation_must_name_events_artifact(self):
        a=self.review('a');a['evidence'][0]['artifact_id']='state'
        with self.assertRaises(ValueError):assess(self.bundle,[a])
    def test_partial_adjudication_and_fractional_clock(self):
        self.media();a=self.review('a');b=self.review('b','fail');c=self.review('c')
        a['completed_at']='2026-10-19T00:00:00Z'
        b['completed_at']='2026-10-19T00:00:00.1Z'
        c.update(completed_at='2026-10-19T00:00:00.2Z',notes='Reviewed outcome.',resolves_review_sha256=[digest(a),digest(b)])
        self.assertEqual(assess(self.bundle,[a,b,c])['truthfulness'],'pass')
        b['ratings']['naturalness']=None;c['resolves_review_sha256']=[digest(a),digest(b)]
        with self.assertRaises(ValueError):assess(self.bundle,[a,b,c])
    def test_mono_never_measures(self):
        stream=io.BytesIO()
        with wave.open(stream,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0'*32000)
        raw=stream.getvalue();self.bundle.artifacts['audio']=(dict(artifact_kind='audio',sha256=digest(raw)),raw)
        metrics,verdict=audio_metrics(self.bundle,assess(self.bundle,[]))
        self.assertEqual(verdict,'unknown');self.assertTrue(all(m['value'] is None for m in metrics))
    def test_explicit_third_review_adjudication(self):
        self.media()
        a=self.review('a');b=self.review('b','fail');c=self.review('c')
        c.update(completed_at='2026-10-19T01:00:00Z',notes='Re-listened to the cited original outcome segment and resolved the disagreement.',resolves_review_sha256=[digest(a),digest(b)])
        result=assess(self.bundle,[a,b,c]);self.assertEqual(result['truthfulness'],'pass');self.assertEqual(len(result['hashes']),3)
        c['reviewer_id']='a'
        with self.assertRaises(ValueError):assess(self.bundle,[a,b,c])
    def test_canonical_pcm_and_alignment_gate(self):
        import array
        from smb_voice_bench.canonical import canonical
        samples=array.array('h',[0])*(16000*2)
        for i in range(3200):samples[2*i]=10000
        for i in range(6400,9600):samples[2*i+1]=10000
        stream=io.BytesIO()
        with wave.open(stream,'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(16000);w.writeframes(samples.tobytes())
        raw=stream.getvalue();self.bundle.artifacts['audio']=(dict(artifact_kind='audio',sha256=digest(raw)),raw)
        measurement=dict(kind='measurement',schema_version='0.1.0',method_id='pcm-rms-v1',audio_sha256=digest(raw),channel_layout='caller-left-assistant-right',alignment_error_ms=0,alignment_source='Synthetic unit-test PCM clock',extensions={})
        self.bundle.artifacts['measurement']=(dict(artifact_kind='measurement'),canonical(measurement))
        self.bundle.events=[dict(event_id='caller',type='speech.segment',payload=dict(speaker='caller',start_ms=0,end_ms=200,text='request')),dict(event_id='outcome',type='speech.segment',payload=dict(speaker='assistant',start_ms=400,end_ms=600,text='outcome'))]
        reviews=dict(truthfulness='pass',reviews=[dict(final_status_truthful='pass',evidence=[dict(event_id='outcome')])])
        metrics,verdict=audio_metrics(self.bundle,reviews);self.assertEqual(verdict,'pass');self.assertEqual(metrics[0]['value'],200)
        measurement['alignment_error_ms']=21;self.bundle.artifacts['measurement']=(dict(artifact_kind='measurement'),canonical(measurement))
        self.assertEqual(audio_metrics(self.bundle,reviews)[1],'unknown')
    def test_verified_channel_derivatives(self):
        import array
        from smb_voice_bench.canonical import canonical
        from smb_voice_bench.metrics import verified_channels
        def wav(channels,samples):
            stream=io.BytesIO()
            with wave.open(stream,'wb') as w:w.setnchannels(channels);w.setsampwidth(2);w.setframerate(16000);w.writeframes(array.array('h',samples).tobytes())
            return stream.getvalue()
        stereo=wav(2,[100,-200]*320);caller=wav(1,[100]*320)
        self.bundle.artifacts['audio']=(dict(artifact_kind='audio',sha256=digest(stereo)),stereo)
        self.bundle.artifacts['caller']=(dict(artifact_kind='audio_caller',sha256=digest(caller)),caller)
        m=dict(kind='measurement',schema_version='0.1.0',method_id='pcm-rms-v1',audio_sha256=digest(stereo),channel_layout='caller-left-assistant-right',alignment_error_ms=0,alignment_source='test',extensions={},derivatives=[dict(artifact_id='caller',source_audio_sha256=digest(stereo),sha256=digest(caller),channel='caller')])
        self.bundle.artifacts['measurement']=(dict(artifact_kind='measurement'),canonical(m))
        self.assertEqual(verified_channels(self.bundle)['caller'],caller)
        wrong=wav(1,[-200]*320);self.bundle.artifacts['caller']=(dict(artifact_kind='audio_caller',sha256=digest(wrong)),wrong);m['derivatives'][0]['sha256']=digest(wrong);self.bundle.artifacts['measurement']=(dict(artifact_kind='measurement'),canonical(m))
        with self.assertRaises(ValueError):verified_channels(self.bundle)

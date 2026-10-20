#!/usr/bin/env python3
"""Generate private local browser QA fixtures: inert XSS text and synthetic PCM tones.

No generated audio is distributed. These are viewer tests, never speech-quality runs.
"""
import argparse
import array
import io
from pathlib import Path
import wave
from smb_voice_bench.canonical import atomic_output,canonical,digest,parse,write_bytes,write_json
from smb_voice_bench.reference_agents import simulate_into
from smb_voice_bench.import_runs import read_bundle
from smb_voice_bench.evaluate import evaluate
from smb_voice_bench.cli import evaluated_output

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
    with atomic_output(args.output) as output:
        for name in ['attack','audio']:
            root=output/(name+'-source');root.mkdir(mode=0o700)
            simulate_into(root,'unknown-write-reconciliation','reference-good')
            manifest=parse((root/'manifest.json').read_bytes())
            events=[parse(line) for line in (root/'events.jsonl').read_bytes().splitlines()]
            terminal=events.pop();last=events[-1]['at_ms']
            def add_segment(index,at,text,speaker='assistant',start=None,end=None):
                events.append(dict(kind='event',schema_version='0.1.0',event_id='qa_event_'+str(index),run_id=manifest['run_id'],journey_id=manifest['journey_id'],sequence=1,at_ms=at,type='speech.segment',source='adapter',operation_id=None,payload=dict(segment_id='qa_segment_'+str(index),speaker=speaker,start_ms=at if start is None else start,end_ms=at if end is None else end,text=text,transcript_origin='manual'),extensions={}))
            if name=='attack':
                for i in range(600):add_segment(i,last+i+1,'</script><script>globalThis.benchXss=1</script><img src="https://invalid.example/x" onerror="globalThis.benchXss=2"> '+str(i))
                terminal['at_ms']=last+601
            else:
                events=[e for e in events if e['type']!='speech.segment']
                add_segment(1,200,'Synthetic caller test tone; no spoken words.','caller',0,200)
                add_segment(2,400,'Synthetic assistant test tone; no spoken words.','assistant',400,600)
                terminal['at_ms']=1000
                config=parse((root/'configuration.json').read_bytes());config.update(candidate_id='synthetic-audio-fixture',agent_kind='external',description='Synthetic PCM tones for browser QA. No speech-quality result.')
                (root/'configuration.json').write_bytes(canonical(config)+b'\n')
                manifest.update(candidate_id=config['candidate_id'],execution_mode='audio',evidence_origin='external_self_attested')
                manifest['identities']['configuration']=digest(config)
                events[0]['payload']['execution_mode']='audio'
                samples=array.array('h',[0])*(16000*2)
                for i in range(3200):samples[2*i]=10000 if i%40<20 else -10000
                for i in range(6400,9600):samples[2*i+1]=10000 if i%40<20 else -10000
                def wav(channels,pcm):
                    stream=io.BytesIO()
                    with wave.open(stream,'wb') as w:w.setnchannels(channels);w.setsampwidth(2);w.setframerate(16000);w.writeframes(pcm.tobytes())
                    return stream.getvalue()
                stereo=wav(2,samples);write_bytes(root,'conversation.wav',stereo)
                derivatives=[]
                for channel,index in [('caller',0),('assistant',1)]:
                    content=wav(1,samples[index::2]);write_bytes(root,channel+'.wav',content)
                    derivatives.append(dict(artifact_id=channel,source_audio_sha256=digest(stereo),sha256=digest(content),channel=channel))
                write_json(root,'measurement.json',dict(kind='measurement',schema_version='0.1.0',method_id='pcm-rms-v1',audio_sha256=digest(stereo),channel_layout='caller-left-assistant-right',alignment_error_ms=0,alignment_source='Generated synthetic PCM test clock; no speech.',derivatives=derivatives,extensions={}))
                for aid,filename,kind in [('audio','conversation.wav','audio'),('caller','caller.wav','audio_caller'),('assistant','assistant.wav','audio_assistant'),('measurement','measurement.json','measurement')]:
                    raw=(root/filename).read_bytes();manifest['artifacts'].append(dict(artifact_id=aid,path=filename,artifact_kind=kind,bytes=len(raw),sha256=digest(raw)))
            events.append(terminal)
            for index,event in enumerate(events,1):event.update(sequence=index,event_id='event_'+str(index))
            (root/'events.jsonl').write_bytes(b''.join(canonical(e)+b'\n' for e in events))
            for item in manifest['artifacts']:
                raw=(root/item['path']).read_bytes();item.update(bytes=len(raw),sha256=digest(raw))
            (root/'manifest.json').write_bytes(canonical(manifest)+b'\n')
            bundle=read_bundle(root);result=evaluate(bundle);target=output/name;target.mkdir(mode=0o700);evaluated_output(target,bundle,result)

if __name__=='__main__':main()

"""Conservative optional PCM measurements. Never substitute transport for speech."""
import array
import io
import math
import re
import statistics
import sys
import wave
from .canonical import Invalid, parse

METHOD='pcm-rms-v1'

def distribution(values):
    return dict(n=len(values),median=statistics.median(values) if values else None,max=max(values) if values else None,
        p95=sorted(values)[math.ceil(.95*len(values))-1] if len(values)>=20 else None,
        p95_note=None if len(values)>=20 else 'requires at least 20 valid observations')

def metric(key,value,unit,note,method=METHOD):
    return dict(metric_id=key,value=value,unit=unit,method_id=method,note=note)

FILLER_PHRASES=('one moment', 'just a moment', 'let me check')

def filler_metrics(events):
    texts=[e['payload']['text'].lower() for e in events if e['type']=='speech.segment' and e['payload']['speaker']=='assistant']
    counts=[sum(len(re.findall(r'\b'+re.escape(phrase)+r'\b',text)) for text in texts) for phrase in FILLER_PHRASES]
    return metric('repeated_generic_fillers',sum(max(0,n-1) for n in counts) if texts else None,'count',
        'Heuristic phrase-list-v1; reviewable, never a truthfulness or audibility verdict.','phrase-list-v1')

def activity_ranges(frames, channel, merge_ms=0):
    spans=[]
    for index,active in enumerate(frames):
        if not active[channel]: continue
        left=index*20;right=left+20
        if spans and left-spans[-1][1]<=merge_ms: spans[-1][1]=right
        else: spans.append([left,right])
    return spans

def audio_metrics(bundle,review):
    unknown=[metric(k,None,'ms','Actual canonical audio, alignment lineage, and reviewed speech boundaries required.')
             for k in ('outcome_gap','interruption_cutoff','unplanned_overlap')]
    audio=[(item,raw) for item,raw in bundle.artifacts.values() if item['artifact_kind']=='audio']
    if not audio: return unknown,'unknown'
    item,raw=audio[0]
    try:
        with wave.open(io.BytesIO(raw),'rb') as wav:
            if (wav.getframerate(),wav.getnchannels(),wav.getsampwidth(),wav.getcomptype()) != (16000,2,2,'NONE') or wav.getnframes()>1440000:
                return unknown,'unknown'
            pcm=array.array('h',wav.readframes(wav.getnframes()))
    except (wave.Error,EOFError):
        return unknown,'unknown'
    if sys.byteorder!='little': pcm.byteswap()
    measurements=[parse(raw) for meta,raw in bundle.artifacts.values() if meta['artifact_kind']=='measurement']
    lineage=next((m for m in measurements if m.get('kind')=='measurement' and m.get('schema_version')=='0.1.0'
        and m.get('method_id')==METHOD and m.get('audio_sha256')==item['sha256']
        and m.get('channel_layout')=='caller-left-assistant-right' and m.get('alignment_source')
        and type(m.get('alignment_error_ms')) in (int,float) and 0<=m['alignment_error_ms']<=20),None)
    if lineage is None: return unknown,'unknown'
    frames=[]
    for offset in range(0,len(pcm)-639,640):
        block=pcm[offset:offset+640]
        frames.append(tuple(math.sqrt(sum((x/32768)**2 for x in block[channel::2])/320)>.01 for channel in (0,1)))
    caller_spans=activity_ranges(frames,0,1200)
    assistant_spans=activity_ranges(frames,1)
    interruptions=[e for e in bundle.events if e['type']=='interruption.started' and e['payload']['planned']]
    stops=[e for e in bundle.events if e['type']=='playback.stopped']
    planned=[]; cutoffs=[]
    for start in interruptions:
        stop=next((e for e in stops if e['payload']['runtime_interruption_event']==start['event_id'] and e['at_ms']>=start['at_ms']),None)
        if stop and any(c and a for i,(c,a) in enumerate(frames) if start['at_ms']<=i*20<=stop['at_ms']):
            # Confirm assistant energy ceases within a frame of the reported stop.
            next_frame=math.ceil(stop['at_ms']/20)
            if not any(a for c,a in frames[next_frame:next_frame+2]):
                cutoffs.append(stop['at_ms']-start['at_ms']); planned.append((start['at_ms'],stop['at_ms']))
    overlap=sum(20 for i,(c,a) in enumerate(frames) if c and a and not any(left<=i*20<right for left,right in planned))
    gap=None
    cited={ref['event_id'] for r in review['reviews'] if r['final_status_truthful']=='pass' for ref in r['evidence'] if ref['event_id']}
    segments=[e for e in bundle.events if e['type']=='speech.segment']
    outcomes=[e for e in segments if e['event_id'] in cited and e['payload']['speaker']=='assistant']
    if outcomes and review['truthfulness']=='pass':
        outcome=max(outcomes,key=lambda e:e['payload']['start_ms'])['payload']
        caller=[e['payload']['end_ms'] for e in segments if e['payload']['speaker']=='caller' and e['payload']['end_ms']<=outcome['start_ms']]
        if caller:
            relevant=max(caller)
            observed_caller=next((span for span in reversed(caller_spans) if abs(span[1]-relevant)<=20),None)
            observed_assistant=next((span for span in assistant_spans if abs(span[0]-outcome['start_ms'])<=20),None)
            if observed_caller and observed_assistant:
                gap=observed_assistant[0]-observed_caller[1]
    cutoff=max(cutoffs) if cutoffs else None
    metrics=[metric('outcome_gap',gap,'ms','Transcript-assisted; outcome segments must be cited in completed truthful human reviews.'),
        metric('interruption_cutoff',cutoff,'ms','Requires planned positive speech overlap, runtime stop event and PCM cessation.'),
        metric('unplanned_overlap',overlap,'ms','20ms PCM windows; excludes verified planned intervals only.')]
    required=[(gap,4000),(overlap,100)]
    if bundle.manifest['scenario_id']=='interrupt-and-correct-context': required.append((cutoff,500))
    verdict='fail' if any(v is not None and v>limit for v,limit in required) else 'unknown' if any(v is None for v,_ in required) else 'pass'
    return metrics,verdict


def verified_channels(bundle):
    """Only byte-exact PCM channel derivatives with source/hash lineage can play."""
    originals=[(item,raw) for item,raw in bundle.artifacts.values() if item['artifact_kind']=='audio']
    if not originals:return {}
    source,raw=originals[0]
    declarations=[entry for item,content in bundle.artifacts.values() if item['artifact_kind']=='measurement' for m in [parse(content)] if m.get('channel_layout')=='caller-left-assistant-right' and m.get('audio_sha256')==source['sha256'] for entry in m.get('derivatives',[])]
    if not declarations:return {}
    try:
        with wave.open(io.BytesIO(raw),'rb') as w:
            if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getcomptype())!=(2,2,16000,'NONE'):return {}
            original=array.array('h',w.readframes(w.getnframes()))
        result={}
        for declaration in declarations:
            aid=declaration['artifact_id'];channel=declaration['channel'];index=0 if channel=='caller' else 1
            if aid not in bundle.artifacts:raise Invalid('declared channel derivative missing')
            item,content=bundle.artifacts[aid]
            if (item['artifact_kind']!='audio_'+channel or item['sha256']!=declaration['sha256'] or declaration['source_audio_sha256']!=source['sha256'] or channel in result):
                raise Invalid('channel derivative lineage contradiction')
            with wave.open(io.BytesIO(content),'rb') as w:
                if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getcomptype())!=(1,2,16000,'NONE'):
                    raise Invalid('declared channel derivative is not canonical mono PCM')
                derived=array.array('h',w.readframes(w.getnframes()))
            if derived!=original[index::2]:raise Invalid('channel derivative samples differ from source')
            result[channel]=content
        return result
    except (wave.Error,EOFError):
        raise Invalid('declared channel derivative is malformed')


def alignment_verified(bundle):
    originals=[(item,raw) for item,raw in bundle.artifacts.values() if item['artifact_kind']=='audio']
    if not originals:return False
    item,raw=originals[0]
    try:
        with wave.open(io.BytesIO(raw),'rb') as w:
            if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getcomptype())!=(2,2,16000,'NONE'):return False
    except (wave.Error,EOFError):return False
    return any(meta['artifact_kind']=='measurement' and m.get('audio_sha256')==item['sha256']
        and m.get('method_id')==METHOD and m.get('channel_layout')=='caller-left-assistant-right'
        and type(m.get('alignment_error_ms')) in (int,float) and 0<=m['alignment_error_ms']<=20
        and bool(m.get('alignment_source')) for meta,content in bundle.artifacts.values()
        for m in ([parse(content)] if meta['artifact_kind']=='measurement' else []))

"""Evidence-bound human sidecars; templates carry no invented scores."""
import io
import wave
from .canonical import Invalid, digest, read_json
from .contracts import validate, timestamp_key
from .import_runs import selection

RATINGS=('intelligibility','naturalness','entity_accuracy','turn_taking')

def template(bundle):
    return dict(kind='review',schema_version='0.1.0',review_id='review_'+bundle.manifest['run_id'],
        review_kind='human',reviewer_id='unfilled',status='draft',completed_at=None,
        run_id=bundle.manifest['run_id'],manifest_sha256=bundle.manifest_hash,evidence=[],
        final_status_truthful='unknown',next_step_clear='unknown',ratings={key:None for key in RATINGS},notes='',extensions={})

def read_reviews(selector):
    if selector is None: return []
    result=[]; ids=set()
    for path in selection(selector,'review_list'):
        review=validate(read_json(path.parent,path.name),'review')
        if review['review_id'] in ids: raise Invalid('duplicate review ID')
        ids.add(review['review_id']); result.append(review)
    return result

def assess(bundle,reviews):
    relevant=[]; hashes=[]; speech_bound=set(); media_bound=set()
    artifacts={key:item for key,(item,raw) in bundle.artifacts.items()}
    events={e['event_id']:e for e in bundle.events}
    audio_ids=set()
    for key,(item,raw) in bundle.artifacts.items():
        if item['artifact_kind']!='audio':continue
        try:
            with wave.open(io.BytesIO(raw),'rb') as media:
                if ((media.getframerate(),media.getnchannels(),media.getsampwidth(),media.getcomptype())==(16000,2,2,'NONE')
                    and 0<media.getnframes()<=1440000
                    and len(media.readframes(media.getnframes()))==media.getnframes()*4):
                    audio_ids.add(key)
        except (wave.Error,EOFError):pass
    def complete(review):
        return (all(type(review['ratings'][k]) is int for k in RATINGS)
                and review['final_status_truthful'] in ('pass','fail')
                and review['next_step_clear'] in ('pass','fail'))
    def completed_at(review):
        return timestamp_key(review['completed_at'])
    for review in reviews:
        if review['run_id']!=bundle.manifest['run_id']: continue
        if review['manifest_sha256']!=bundle.manifest_hash: raise Invalid('stale review manifest binding')
        for ref in review['evidence']:
            if ref['artifact_id'] not in artifacts or ref['event_id'] is not None and ref['event_id'] not in events:
                raise Invalid('review cites unavailable evidence')
            if ref['event_id'] is not None and artifacts[ref['artifact_id']]['artifact_kind']!='events':
                raise Invalid('review event citation must name its events artifact')
        value=digest(review); hashes.append(value)
        cited=[events[ref['event_id']] for ref in review['evidence'] if ref['event_id'] is not None]
        observed=any(e['type']=='speech.segment' and e['payload']['speaker']=='assistant'
                     and e['payload']['text'].strip()
                     and (bundle.manifest['execution_mode']=='reference'
                          or e['payload']['transcript_origin']!='scripted_reference') for e in cited)
        if observed: speech_bound.add(value)
        if (observed and bundle.manifest['execution_mode']=='audio'
            and any(ref['artifact_id'] in audio_ids for ref in review['evidence'])):
            media_bound.add(value)
        if review['status']=='completed' and review['completed_at'] is None:
            raise Invalid('completed review lacks completion time')
        if review['status']=='completed' and review['review_kind']=='human' and review['evidence'] and review['reviewer_id']!='unfilled':
            relevant.append(review)
    # A third, distinct human may explicitly adjudicate cited contradictory reviews.
    # Preserve every original hash and review; never resolve by averaging or recency alone.
    # A state/configuration citation cannot establish what the assistant said.
    # Audio reviews additionally bind the retained original recording.
    eligible=[r for r in relevant if digest(r) in speech_bound
              and (bundle.manifest['execution_mode']!='audio' or digest(r) in media_bound)]
    effective=list(eligible)
    by_hash={digest(r):r for r in eligible}
    for resolution in relevant:
        refs=resolution.get('resolves_review_sha256',[])
        if not refs: continue
        targets=[by_hash.get(value) for value in refs]
        if any(target is None for target in targets): raise Invalid('resolution cites unavailable review')
        if (digest(resolution) not in by_hash or not complete(resolution)
            or any(not complete(target) for target in targets)
            or resolution['reviewer_id'] in {target['reviewer_id'] for target in targets}
            or len({target['reviewer_id'] for target in targets})<2
            or {target['final_status_truthful'] for target in targets}!={'pass','fail'}
            or resolution['final_status_truthful'] not in ('pass','fail') or not resolution['notes'].strip()
            or any(completed_at(target)>=completed_at(resolution) for target in targets)):
            raise Invalid('invalid independent truthfulness adjudication')
        effective=[r for r in effective if digest(r) not in refs]
    truth=[r['final_status_truthful'] for r in effective]
    if any(r['final_status_truthful']=='fail' for r in relevant if digest(r) not in by_hash):
        truth.append('fail')
    truthful='fail' if 'fail' in truth else 'pass' if 'pass' in truth and all(x=='pass' for x in truth) else 'unknown'
    complete_reviews=[r for r in eligible if complete(r)]
    listeners=[r for r in complete_reviews if digest(r) in media_bound]
    listening='fail' if any(r['next_step_clear']=='fail' or any(v is not None and v<4 for v in r['ratings'].values()) for r in relevant) else 'pass' if len({r['reviewer_id'] for r in listeners})>=2 else 'unknown'
    if len({r['reviewer_id'] for r in complete_reviews})<2 and truthful=='pass':
        truthful='unknown'
    return dict(truthfulness=truthful,listening=listening,hashes=hashes,
                complete_reviewers=len({r['reviewer_id'] for r in listeners}),reviews=effective)

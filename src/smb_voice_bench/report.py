"""Static accessible local viewer. Rendering never dispatches tools or regrades."""
from importlib.resources import files
import html
from .canonical import canonical, write_bytes, write_json, read_bytes, MAX_WAV, Invalid, parse
from .contracts import validate

CSP="default-src 'none'; script-src 'self'; style-src 'self'; media-src 'self'; img-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"

def shell(data):
    embedded=canonical(data).decode().replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="'+html.escape(CSP,quote=True)+'">'
        '<title>SMB voice bench · local evidence</title><link rel="stylesheet" href="viewer.css"></head><body>'
        '<header class="mast"><a href="index.html">SMB <strong>voice bench</strong></a><span>LOCAL EVIDENCE / V0.1</span></header>'
        '<main id="app"><noscript>Enable local JavaScript to inspect evidence. Full results are available in result.json.</noscript></main>'
        '<footer>Synthetic business tools. A local confirmation record never proves message delivery. No production-readiness certification.</footer>'
        '<script type="application/json" id="evidence">'+embedded+'</script><script src="viewer.js" defer></script></body></html>')

def render(output,data):
    for name in ('viewer.js','viewer.css'):
        write_bytes(output,name,files('smb_voice_bench').joinpath('assets/'+name).read_bytes())
    write_bytes(output,'index.html',shell(data).encode())
    write_json(output,'report-data.json',data)

def render_run(output,bundle,result):
    validate(result,'result')
    if result['manifest_sha256']!=bundle.manifest_hash: raise Invalid('result is bound to different evidence')
    audio_path=None
    for item,raw in bundle.artifacts.values():
        if item['artifact_kind']=='events': write_bytes(output,'events.jsonl',raw)
    for item,raw in bundle.artifacts.values():
        if item['artifact_kind']=='audio':
            # Browser gets a fixed local filename, never an untrusted imported path.
            audio_path='conversation.wav'; write_bytes(output,audio_path,raw); break
    from .metrics import alignment_verified
    aligned=alignment_verified(bundle)
    from .metrics import verified_channels
    channels=[]
    for channel,raw in verified_channels(bundle).items():
        name=channel+'.wav';write_bytes(output,name,raw);channels.append(dict(channel=channel,path=name))
    data=dict(channel_audio=channels,timeline_aligned=bool(aligned),kind='run_report',schema_version='0.1.0',manifest=bundle.manifest,result=result,
              events=bundle.events,state=bundle.state,configuration=bundle.configuration,audio_path=audio_path)
    render(output,data)
    summary=('SMB voice bench\n'+bundle.manifest['evidence_origin']+' / '+bundle.manifest['execution_mode']+'\n'
        +'Business outcome: '+result['business_outcome']+'\nFunctional: '+result['dimensions']['functional']+'\n'
        +'\n'.join(c['check_id']+': '+c['verdict']+' — '+c['reason'] for c in result['checks'])+'\n'
        +'\n'.join(result['blockers'])+'\n')
    write_bytes(output,'summary.txt',summary.encode())
    write_json(output,'result.json',result)

def render_comparison(output,comparison,records):
    render(output,dict(kind='comparison_report',schema_version='0.1.0',comparison=comparison,runs=records))
    write_json(output,'comparison.json',comparison)
    write_bytes(output,'summary.txt',('SMB voice bench comparison\n'+comparison['assessment']+'\n'+comparison['declared_change']+'\n'+'\n'.join(comparison['blockers'])+'\n').encode())

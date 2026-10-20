"""Explicit cohort comparisons; every selected run participates in the gates."""
from .canonical import Invalid, digest, canonical
from .contracts import validate
from .evaluate import evaluate
from .import_runs import read_bundle
from .scenarios import IDS
from .metrics import distribution

JOIN_KEYS=('scenario','suite','sandbox','conditions')

def critical_failures(result):
    return sum(c['critical'] and c['verdict']=='fail' for c in result['checks']) + sum(result['dimensions'][d]=='fail' for d in ('timing','listening'))

def collect(paths,reviews,scope,on_run=None):
    records=[]; identities={}; duplicates=0
    if not paths or len(paths)>128: raise Invalid('run selection size invalid')
    for path in paths:
        bundle=read_bundle(path); mid=bundle.manifest['run_id']
        if mid in identities:
            if identities[mid]!=(bundle.manifest_hash,digest(bundle.manifest_raw)): raise Invalid('conflicting run ID copies')
            duplicates+=1; continue
        identities[mid]=(bundle.manifest_hash,digest(bundle.manifest_raw))
        result=evaluate(bundle,reviews,scope)
        if on_run: on_run(bundle,result)
        records.append(dict(manifest=bundle.manifest,configuration=bundle.configuration,result=result,
                            manifest_sha256=bundle.manifest_hash))
        del bundle
    return records,duplicates

def compare_records(baseline,candidate,declared_change,scope='functional',deduplicated=0):
    if not declared_change or len(declared_change)>4096: raise Invalid('declared change required')
    if {r['manifest']['run_id'] for r in baseline}&{r['manifest']['run_id'] for r in candidate}:
        raise Invalid('same run appears in both comparison arms')
    rows=[]; blockers=[]; any_failure=any(critical_failures(r['result']) for r in candidate)
    missing=False; all_ids=set(IDS)|{r['manifest']['scenario_id'] for r in baseline+candidate}
    changes=[]
    for sid in sorted(all_ids):
        left=[r for r in baseline if r['manifest']['scenario_id']==sid]
        right=[r for r in candidate if r['manifest']['scenario_id']==sid]
        keys=lambda arm:{tuple(r['manifest']['identities'][k] for k in JOIN_KEYS)+(r['manifest']['seed'],r['manifest']['execution_mode'],r['manifest']['evidence_origin'],r['result'].get('evaluator_sha256'),r['result'].get('policy_sha256'),r['result'].get('assessment_scope')) for r in arm}
        comparable='comparable' if left and right and len(keys(left))==1 and keys(left)==keys(right) else 'incomparable' if left and right else 'insufficient'
        reason='Matched scenario, suite, fault implementation, conditions, seed, evaluator and source policy.' if comparable=='comparable' else 'Identity mismatch; excluded from improvement claims.' if left and right else 'Missing case in an explicit arm.'
        required=5 if scope=='audio-release' else 1
        valid=lambda r:r['manifest']['completion']=='completed' and r['result']['dimensions']['functional']=='pass' and r['result']['dimensions']['evidence']=='pass'
        coverage=len(right)>=required and all(valid(r) for r in right)
        if not coverage or comparable!='comparable': missing=True
        if comparable=='comparable' and (len(left)<5 or len(right)<5): reason+=' Small cohort: observed deltas only; insufficient for reliability claims.'
        if scope=='audio-release':
            if len({r['manifest']['identities']['configuration'] for r in right})!=1 or any(r['manifest']['execution_mode']!='audio' or any(r['result']['dimensions'][d]!='pass' for d in ('truthfulness','listening','timing')) for r in right):
                missing=True
        timing={}
        for name in ('outcome_gap','interruption_cutoff','unplanned_overlap'):
            values=lambda arm:[m['value'] for r in arm for m in r['result']['metrics'] if m['metric_id']==name and m['value'] is not None]
            l=distribution(values(left)); r=distribution(values(right))
            timing[name]=dict(baseline=l,candidate=r,median_delta=(r['median']-l['median']) if comparable=='comparable' and r['median'] is not None and l['median'] is not None else None)
        def arm_summary(arm):
            return dict(attempts=len(arm),completed=sum(r['manifest']['completion']=='completed' for r in arm),
                functional_passes=sum(r['result']['dimensions']['functional']=='pass' for r in arm),
                unknowns=sum(any(v=='unknown' for v in r['result']['dimensions'].values()) for r in arm),
                reviewed_runs=sum(r['result']['dimensions']['listening']=='pass' for r in arm),
                known_observed_usd=sum(r['result']['cost']['total_observed_usd'] for r in arm if r['result']['cost']['total_observed_usd'] is not None) if any(r['result']['cost']['total_observed_usd'] is not None for r in arm) else None,
                cost_complete=bool(arm) and all(r['result']['cost']['completeness']=='complete' for r in arm))
        rows.append(dict(scenario_id=sid,comparability=comparable,reason=reason,
            baseline_runs=[r['manifest']['run_id'] for r in left],candidate_runs=[r['manifest']['run_id'] for r in right],
            baseline_critical_failures=sum(critical_failures(r['result']) for r in left),
            candidate_critical_failures=sum(critical_failures(r['result']) for r in right),
            baseline_summary=arm_summary(left),candidate_summary=arm_summary(right),timing=timing,
            deltas=[dict(metric_id=name+'_median_delta',value=value['median_delta'],unit='ms',method_id='comparison-v1',note='Observed comparable median delta; no reliability claim.') for name,value in timing.items()]))
    if any_failure: blockers.append('At least one candidate critical failure blocks this assessment, including prevented attempts.')
    if missing: blockers.append('Missing, incomparable or incomplete mandatory coverage remains visible.')
    configs={};budget=4096
    for arm,runs in [('baseline',baseline),('candidate',candidate)]:
        unique={}
        for record in runs:
            key=record['manifest']['identities']['configuration']
            if key not in unique:
                item=dict(candidate_id=record['manifest']['candidate_id'],configuration_sha256=key,run_ids=[])
                snapshot=record['configuration'];size=len(canonical(snapshot))
                if size<=budget:item['configuration']=snapshot;budget-=size
                else:item['configuration_note']='Full snapshot is available in each linked run report.'
                unique[key]=item
            unique[key]['run_ids'].append(record['manifest']['run_id'])
        configs[arm]=list(unique.values())
    def flattened(value,prefix=''):
        if isinstance(value,dict):
            result={}
            for key,item in value.items():result.update(flattened(item,prefix+'.'+key if prefix else key))
            return result
        return {prefix:value}
    configuration_changes=[];changed_count=None
    left_configs={r['manifest']['identities']['configuration'] for r in baseline}
    right_configs={r['manifest']['identities']['configuration'] for r in candidate}
    if len(left_configs)==len(right_configs)==1 and baseline[0]['configuration'] and candidate[0]['configuration']:
        relevant=lambda value:{key:value[key] for key in ('agent_kind','parameters')}
        left=flattened(relevant(baseline[0]['configuration']));right=flattened(relevant(candidate[0]['configuration']))
        fields=[key for key in sorted(set(left)|set(right)) if canonical(left.get(key))!=canonical(right.get(key))]
        changed_count=len(fields)
        def display(value):
            return value if len(canonical(value))<=128 else {'sha256':digest(value),'note':'Full value in linked configuration snapshot.'}
        for key in fields[:16]:
            configuration_changes.append(dict(field=key if len(key)<=64 else key[:40]+'...#'+digest(key)[:16],
                baseline=display(left.get(key)),candidate=display(right.get(key))))
    attribution=('Confounded: multiple configuration variables changed.' if changed_count is not None and changed_count>1 else
                 'One declared configuration field changed; observed deltas do not establish causality.' if changed_count==1 else
                 'No declared configuration field changed.' if changed_count==0 else
                 'Attribution unknown: multiple or missing configuration snapshots.')
    candidate_configs={r['manifest']['identities']['configuration'] for r in candidate}
    if len(candidate_configs)!=1:
        missing=True; blockers.append('Candidate configuration is not unchanged across selected history.')
    if any(r['manifest']['execution_mode']=='reference' for r in candidate):
        blockers.append('Scripted reference demonstrations do not establish real-agent release readiness.')
    assessment='blocked' if any_failure else 'insufficient_evidence' if missing else 'eligible_for_review'
    from .reference_agents import implementation_identity
    comparison_method=implementation_identity('compare')
    result=dict(kind='comparison',schema_version='0.1.0',comparison_id='comparison_'+digest({'runs':[r['manifest_sha256'] for r in baseline+candidate],'results':[digest(r['result']) for r in baseline+candidate],'scope':scope,'change':declared_change,'method':comparison_method})[:24],
        declared_change=declared_change,scope=scope,assessment=assessment,rows=rows,blockers=blockers,
        extensions={'bench:deduplicated':deduplicated,'bench:configurations':configs,
                    'bench:attribution':attribution,'bench:configuration_changes':configuration_changes,'bench:changed_field_count':changed_count,'bench:comparison_implementation_sha256':comparison_method})
    return validate(result)

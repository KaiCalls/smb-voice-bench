#!/usr/bin/env python3
"""Run five repetitions of seven good/bad offline references and retain all evidence."""
import argparse
from pathlib import Path
import time
from smb_voice_bench.canonical import atomic_output,write_json
from smb_voice_bench.cli import evaluated_output,compact
from smb_voice_bench.compare import compare_records
from smb_voice_bench.evaluate import evaluate,exit_code
from smb_voice_bench.import_runs import read_bundle
from smb_voice_bench.reference_agents import simulate_into
from smb_voice_bench.report import render_comparison
from smb_voice_bench.scenarios import IDS

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
    started=time.monotonic();arms={'baseline':[],'candidate':[]};cards=[];rows=[];paths={'baseline':[],'candidate':[]}
    with atomic_output(args.output) as output:
        (output/'runs').mkdir(mode=0o700)
        for sid in IDS:
            for repeat in range(1,6):
                for arm,agent,expected in [('baseline','reference-bad',1),('candidate','reference-good',0)]:
                    source=output/(sid+'_'+agent+'_'+str(repeat));source.mkdir(mode=0o700)
                    simulate_into(source,sid,agent);bundle=read_bundle(source);result=evaluate(bundle)
                    actual=exit_code(result)
                    if actual!=expected:raise AssertionError('unexpected reference behavior in '+sid)
                    target=output/'runs'/bundle.manifest['run_id'];target.mkdir(mode=0o700);evaluated_output(target,bundle,result)
                    paths[arm].append(source.name);cards.append(compact(bundle,result))
                    arms[arm].append(dict(manifest=bundle.manifest,configuration=bundle.configuration,result=result,manifest_sha256=bundle.manifest_hash))
                    rows.append(dict(scenario_id=sid,repeat=repeat,agent=agent,expected_exit=expected,actual_exit=actual,
                        business_outcome=result['business_outcome'],dimensions=result['dimensions'],run_id=bundle.manifest['run_id'],
                        create_decisions=len({(a['call_id'],a['operation_id']) for a in bundle.state['attempts'] if a['tool']=='create_booking'}),bookings=len(bundle.state['bookings'])))
        for arm in paths:write_json(output,arm+'.json',dict(kind='run_list',schema_version='0.1.0',paths=paths[arm]))
        comparison=compare_records(arms['baseline'],arms['candidate'],'Good references reconcile status, honor current permission and report partial outcomes truthfully; bad controls deliberately violate these rules.')
        render_comparison(output,comparison,cards)
        receipt=dict(kind='scenario_matrix_receipt',schema_version='0.1.0',scenario_count=7,repetitions_per_agent=5,
            total_traces=len(rows),good_functional_passes=sum(r['agent']=='reference-good' and r['actual_exit']==0 for r in rows),
            expected_bad_failures=sum(r['agent']=='reference-bad' and r['actual_exit']==1 for r in rows),
            elapsed_seconds=round(time.monotonic()-started,3),label='scripted reference demonstrations; no real-agent or speech release claim',rows=rows)
        write_json(output,'matrix-receipt.json',receipt)
    print({k:v for k,v in receipt.items() if k!='rows'})

if __name__=='__main__':main()

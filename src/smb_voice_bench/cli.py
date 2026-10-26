"""Offline-only CLI. No provider, executable, plugin, network or delivery command."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from . import __version__
from .canonical import Invalid, Incomplete, atomic_output, write_json, write_bytes, read_json
from .contracts import validate
from .scenarios import IDS, catalog
from .reference_agents import simulate, simulate_into
from .import_runs import read_bundle, import_bundle, selection
from .evaluate import evaluate, exit_code
from .reviews import read_reviews, template
from .compare import collect, compare_records
from .report import render_run, render_comparison
from . import grade as suite_grade

class Parser(argparse.ArgumentParser):
    def error(self,message):
        raise Invalid('invalid command arguments; use --help')

def parser():
    p=Parser(prog='smb-voice-bench',description='Offline synthetic receptionist evidence toolkit')
    p.add_argument('--version',action='version',version=__version__)
    p.add_argument('--json',action='store_true')
    commands=p.add_subparsers(dest='command',required=True,parser_class=Parser)
    for name in ('catalog','doctor','demo','simulate','validate','import','evaluate','review-template','compare','report','grade'):
        sub=commands.add_parser(name)
        sub.add_argument('--json',action='store_true',default=argparse.SUPPRESS)
        if name in ('validate','import','evaluate','review-template','report'): sub.add_argument('--input',required=True)
        if name in ('demo','simulate','import','evaluate','review-template','compare','report','grade'): sub.add_argument('--output',required=True)
        if name=='simulate':
            sub.add_argument('--scenario',required=True,choices=IDS)
            sub.add_argument('--agent',required=True,choices=('reference-good','reference-bad'))
        if name in ('evaluate','compare'):
            sub.add_argument('--scope',choices=('functional','audio-release'),default='functional')
            sub.add_argument('--reviews')
        if name=='compare':
            sub.add_argument('--baseline',required=True); sub.add_argument('--candidate',required=True)
            sub.add_argument('--change',required=True,help='Explicit description of the intended configuration change')
        if name=='grade':
            source=sub.add_mutually_exclusive_group(required=True)
            source.add_argument('--input',help='run_list selector of captured bundles, one or more per case')
            source.add_argument('--agent',choices=('reference-good','reference-bad'),help='Simulate all seven cases with a scripted reference')
            sub.add_argument('--reviews')
            sub.add_argument('--min-grade',choices=tuple(suite_grade.LETTERS))
    return p

def copy_source(output,bundle):
    source=output/'source'; source.mkdir(mode=0o700)
    for item,raw in bundle.artifacts.values(): write_bytes(source,item['path'],raw)
    write_bytes(source,'manifest.json',bundle.manifest_raw)

def evaluated_output(output,bundle,result):
    copy_source(output,bundle)
    write_json(output,'review-template.json',template(bundle))
    render_run(output,bundle,result)

def compact(bundle,result):
    return dict(run_id=bundle.manifest['run_id'],candidate_id=bundle.manifest['candidate_id'],
                execution_mode=bundle.manifest['execution_mode'],evidence_origin=bundle.manifest['evidence_origin'],
                functional=result['dimensions']['functional'])

def dispatch(args):
    name=args.command
    if name=='catalog': return dict(scenarios=catalog()),0
    if name=='doctor':
        return dict(version=__version__,python=sys.version.split()[0],schemas='local Draft 2020-12',
                    scenario_count=len(IDS),safe_posix_filesystem=os.name=='posix',optional_ffmpeg=bool(shutil.which('ffmpeg')),network='not contacted',credentials='not read'),0 if os.name=='posix' else 3
    if name=='simulate':
        manifest=simulate(args.output,args.scenario,args.agent)
        return dict(run_id=manifest['run_id'],output=args.output,label='scripted reference demonstration',audio='unavailable'),0
    if name in ('validate','import'):
        bundle=read_bundle(args.input) if name=='validate' else import_bundle(args.input,args.output)
        return dict(run_id=bundle.manifest['run_id'],manifest_sha256=bundle.manifest_hash,missing=bundle.missing),2 if bundle.missing else 0
    if name=='review-template':
        bundle=read_bundle(args.input); path=Path(args.output)
        write_json(path.parent,path.name,validate(template(bundle),'review'))
        return dict(output=args.output,status='unfilled'),0
    if name=='evaluate':
        bundle=read_bundle(args.input); reviews=read_reviews(args.reviews); result=evaluate(bundle,reviews,args.scope)
        with atomic_output(args.output) as output: evaluated_output(output,bundle,result)
        return dict(run_id=bundle.manifest['run_id'],dimensions=result['dimensions'],business_outcome=result['business_outcome'],output=args.output),exit_code(result,args.scope)
    if name=='compare':
        reviews=read_reviews(args.reviews); cards=[]
        baseline_paths=selection(args.baseline,'run_list'); candidate_paths=selection(args.candidate,'run_list')
        if len(baseline_paths)+len(candidate_paths)>128: raise Invalid('combined comparison selection exceeds limit')
        # Check cross-arm identities before writing any completed report.
        left_ids={read_bundle(path).manifest['run_id'] for path in baseline_paths}
        if any(read_bundle(path).manifest['run_id'] in left_ids for path in candidate_paths): raise Invalid('same run appears in both arms')
        with atomic_output(args.output) as output:
            (output/'runs').mkdir(mode=0o700)
            def on_run(bundle,result):
                path=output/'runs'/bundle.manifest['run_id']; path.mkdir(mode=0o700)
                evaluated_output(path,bundle,result); cards.append(compact(bundle,result))
            baseline,ld=collect(baseline_paths,reviews,args.scope,on_run)
            candidate,rd=collect(candidate_paths,reviews,args.scope,on_run)
            comparison=compare_records(baseline,candidate,args.change,args.scope,ld+rd)
            render_comparison(output,comparison,cards)
        return dict(assessment=comparison['assessment'],output=args.output), {'blocked':1,'insufficient_evidence':2,'eligible_for_review':0}[comparison['assessment']]
    if name=='demo':
        with atomic_output(args.output) as output:
            (output/'sources').mkdir(mode=0o700); (output/'runs').mkdir(mode=0o700)
            records=[]; cards=[]; outcomes=[]
            for label,agent in [('faulty','reference-bad'),('corrected','reference-good')]:
                path=output/'sources'/label; path.mkdir(mode=0o700)
                simulate_into(path,'unknown-write-reconciliation',agent)
                bundle=read_bundle(path); result=evaluate(bundle); outcomes.append(exit_code(result))
                report=output/'runs'/bundle.manifest['run_id']; report.mkdir(mode=0o700)
                evaluated_output(report,bundle,result); cards.append(compact(bundle,result))
                records.append(dict(manifest=bundle.manifest,configuration=bundle.configuration,result=result,manifest_sha256=bundle.manifest_hash))
            comparison=compare_records(records[:1],records[1:],'Reconcile the original booking instead of making a second create decision.')
            render_comparison(output,comparison,cards)
            if outcomes!=[1,0]: raise Invalid('reference expected-outcome detection failed')
        return dict(output=args.output,expected_failure_detected=True,corrected_functional_pass=True,
                    label='scripted reference demonstration',audio='unavailable',release_assessment='insufficient_evidence'),0
    if name=='grade':
        reviews=read_reviews(args.reviews); runs=[]
        with atomic_output(args.output) as output:
            if args.agent:
                (output/'sources').mkdir(mode=0o700)
                paths=[]
                for scenario_id in IDS:
                    path=output/'sources'/scenario_id; path.mkdir(mode=0o700)
                    simulate_into(path,scenario_id,args.agent); paths.append(path)
            else:
                paths=selection(args.input,'run_list')
            seen=set()
            for path in paths:
                bundle=read_bundle(path)
                if bundle.manifest['run_id'] in seen: raise Invalid('same run selected twice')
                seen.add(bundle.manifest['run_id'])
                runs.append((bundle.manifest['scenario_id'],bundle.manifest['run_id'],evaluate(bundle,reviews)))
            card=suite_grade.grade(runs)
            write_json(output,'grade.json',card)
            write_bytes(output,'GRADE.md',suite_grade.markdown(card).encode())
            write_bytes(output,'badge.svg',suite_grade.badge(card).encode())
        return dict(letter=card['letter'],passed=card['passed'],total=card['total'],capped_by_mandatory=card['capped_by_mandatory'],
                    missing_scenarios=card['missing_scenarios'],scope=card['scope'],output=args.output),suite_grade.exit_code(card,args.min_grade)
    if name=='report':
        source=Path(args.input)
        if (source/'comparison.json').is_file():
            comparison=validate(read_json(source,'comparison.json'),'comparison')
            ids=list(dict.fromkeys(rid for row in comparison['rows'] for arm in ('baseline_runs','candidate_runs') for rid in row[arm]))
            if len(ids)>128: raise Invalid('report run count exceeds limit')
            cards=[]
            with atomic_output(args.output) as output:
                (output/'runs').mkdir(mode=0o700)
                for rid in ids:
                    run_source=source/'runs'/rid
                    result=validate(read_json(run_source,'result.json'),'result')
                    bundle=read_bundle(run_source/'source')
                    target=output/'runs'/rid;target.mkdir(mode=0o700)
                    evaluated_output(target,bundle,result);cards.append(compact(bundle,result))
                render_comparison(output,comparison,cards)
        else:
            result=validate(read_json(source,'result.json'),'result')
            bundle=read_bundle(source/'source')
            with atomic_output(args.output) as output:
                copy_source(output,bundle); render_run(output,bundle,result)
        return dict(output=args.output,meaning='Report rendered; no evaluation performed'),0
    raise Invalid('unknown command')

def main(argv=None):
    try:
        args=parser().parse_args(argv)
        response,code=dispatch(args)
        print(json.dumps(response,ensure_ascii=False,allow_nan=False) if args.json else json.dumps(response,indent=2,ensure_ascii=False,allow_nan=False))
        return code
    except Incomplete:
        print('Incomplete evidence: a required local file is unavailable.',file=sys.stderr); return 2
    except Invalid as exc:
        print('Invalid input: '+str(exc),file=sys.stderr); return 3
    except (OSError,ValueError,KeyError,TypeError,RecursionError,sqlite3.Error):
        print('Operation failed: invalid or inaccessible local evidence. Originals were not changed.',file=sys.stderr); return 3
    except KeyboardInterrupt:
        print('Interrupted. Any staging output remains explicitly incomplete.',file=sys.stderr); return 3

if __name__=='__main__':
    sys.exit(main())

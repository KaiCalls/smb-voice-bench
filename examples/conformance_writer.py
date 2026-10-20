#!/usr/bin/env python3
"""Explicit local reference writer; never invoked by the public CLI importer.

This demonstrates evidence output and validation, not a live provider adapter.
The reference implementation's simulate_into function shows every event,
independent snapshot, artifact hash and immutable manifest field.
"""
import argparse
from smb_voice_bench.reference_agents import simulate
from smb_voice_bench.import_runs import read_bundle

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    simulate(args.output,'unknown-write-reconciliation','reference-good')
    bundle=read_bundle(args.output)
    print('Scripted reference demonstration; audio unavailable. Manifest:',bundle.manifest_hash)

#!/usr/bin/env python3
"""Validate active public source, historical snapshot and distribution inventories."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN=[rb'/Users/',rb'/home/connor',rb'(?i)tail[a-z0-9]+\.ts\.net',
           rb'sk_live_[a-zA-Z0-9]{12,}',rb'(?i)BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY',
           rb'runtime-rules\.json',rb'VAPI_PRIVATE_KEY',rb'ELEVENLABS_API_KEY']
SKIP={'.git','legacy','build','dist','.venv','__pycache__','demo-report'}
GENERATED={'PKG-INFO','setup.cfg'}|{'src/smb_voice_bench.egg-info/'+name for name in (
    'PKG-INFO','SOURCES.txt','dependency_links.txt','entry_points.txt','requires.txt','top_level.txt')}

def scan(name,raw):
    # This scanner contains patterns, never prohibited production values.
    if name.endswith('tools/check_public.py'):return
    if any(re.search(pattern,raw) for pattern in FORBIDDEN):raise ValueError('prohibited source pattern in '+name)
    if name.endswith(('.wav','.mp3','.mp4','.webm','.sqlite','.env')):raise ValueError('private/media artifact in extraction')

def snapshot():
    root=ROOT/'legacy/fixture-pack-v1'
    record=json.loads((root/'SNAPSHOT.json').read_text())
    if record['source_commit']!='a5be8a6088af83fdde69ab253b89292557f7f0cb':raise ValueError('unexpected historical source')
    expected={entry['path']:entry['sha256'] for entry in record['files']}
    paths=list(root.rglob('*'))
    if any(p.is_symlink() for p in paths):raise ValueError('linked historical file')
    actual={p.relative_to(root).as_posix() for p in paths if p.is_file()}-{'SNAPSHOT.json'}
    if actual!=set(expected):raise ValueError('historical inventory differs')
    for name,sha in expected.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:raise ValueError('historical bytes changed: '+name)
    return len(expected)

def archives(directory,allowed):
    found=set()
    for archive in Path(directory).iterdir():
        if archive.suffix=='.whl':
            found.add('wheel')
            with zipfile.ZipFile(archive) as z:
                entries={name:z.read(name) for name in z.namelist() if not name.endswith('/')}
                for name,raw in entries.items():
                    scan(name,raw)
                    if name.startswith('smb_voice_bench/'):
                        source='src/'+name
                        if source not in allowed or raw!=(ROOT/source).read_bytes():raise ValueError('unexpected or changed wheel source: '+name)
                    elif not name.startswith('smb_voice_bench-0.1.0.dist-info/'):raise ValueError('unexpected wheel entry')
                expected={name[4:] for name in allowed if name.startswith('src/smb_voice_bench/')}
                if {n for n in entries if n.startswith('smb_voice_bench/')}!=expected:raise ValueError('wheel source missing')
        elif archive.name.endswith('.tar.gz'):
            found.add('sdist');seen=set()
            with tarfile.open(archive) as tar:
                for member in tar.getmembers():
                    parts=PurePosixPath(member.name).parts
                    if not parts or parts[0]!='smb_voice_bench-0.1.0' or '..' in parts or member.issym() or member.islnk():raise ValueError('unsafe source archive member')
                    if member.isfile():
                        name='/'.join(parts[1:]);raw=tar.extractfile(member).read();scan(name,raw)
                        if name in seen:raise ValueError('duplicate source archive member')
                        seen.add(name)
                        if name not in allowed|GENERATED:raise ValueError('unexpected source archive entry: '+name)
                        if name in allowed and raw!=(ROOT/name).read_bytes():raise ValueError('source archive bytes differ: '+name)
                if not allowed<=seen:raise ValueError('source archive files missing: '+str(sorted(allowed-seen)))
    if found!={'wheel','sdist'}:raise ValueError('both wheel and source archive are required')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dist');args=parser.parse_args()
    allowed=ROOT.joinpath('PUBLIC_FILES.txt').read_text().splitlines()
    if allowed!=sorted(set(allowed)):raise ValueError('allowlist must be sorted and unique')
    for name in allowed:
        path=ROOT/name
        if not path.is_file() or path.is_symlink():raise ValueError('allowlisted file unavailable or linked')
        scan(name,path.read_bytes())
    actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and not any(x in SKIP or x.endswith('.egg-info') for x in p.relative_to(ROOT).parts)}
    if actual!=set(allowed):raise ValueError('public inventory differs: '+str(sorted(actual^set(allowed))))
    historical=snapshot() if (ROOT/'legacy').exists() else 0
    if args.dist:archives(args.dist,set(allowed))
    print('Public inventory passed:',len(allowed),'active files;',historical,'unchanged historical files; pattern scan is a guard, not anonymization proof.')

if __name__=='__main__':main()

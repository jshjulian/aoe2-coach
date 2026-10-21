#!/usr/bin/env python3
"""Verify pinned public reference files; download missing files only with explicit consent.

No replay/context input, lock updates, executable downloads, or runtime invocation.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]


def restore(root=ROOT,*,download=False,opener=urlopen):
    entries={};commit=None
    for name in ['aoe2techtree.lock.json','situational-catalog.lock.json']:
        lock=json.loads((root/'knowledge'/name).read_text())
        revision=lock.get('commit','')
        if lock.get('repository')!='https://github.com/SiegeEngineers/aoe2techtree' or not re.fullmatch('[0-9a-f]{40}',revision):raise ValueError('Unexpected reference source.')
        if commit is not None and commit!=revision:raise ValueError('Reference locks disagree.')
        commit=revision
        for row in lock['files']:
            for key in ['path','upstream_path']:
                path=PurePosixPath(row[key])
                if path.is_absolute() or '..' in path.parts or not re.fullmatch(r'[A-Za-z0-9_./-]+',row[key]):raise ValueError('Unsafe reference path.')
            if not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('Invalid reference hash.')
            old=entries.get(row['path'])
            if old is not None and old!=row:raise ValueError('Conflicting reference entry.')
            entries[row['path']]=row
    if not 1<=len(entries)<=128:raise ValueError('Unbounded reference list.')
    base=root/'data/research/aoe2techtree'/commit
    for relative,row in entries.items():
        target=base/relative
        if not target.resolve().is_relative_to(base.resolve()):raise ValueError('Reference path escapes cache.')
        if target.exists():
            with target.open('rb') as handle:raw=handle.read(32*1024*1024+1)
        else:
            if not download:raise ValueError('Reference cache missing. Use --download-static-reference explicitly to fetch pinned public files.')
            url=f'https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/{commit}/'+row['upstream_path']
            with opener(url,timeout=30) as response:raw=response.read(32*1024*1024+1)
        if len(raw)>32*1024*1024 or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError(f'Reference hash mismatch; no overwrite: {relative}')
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as handle:handle.write(raw)
    return len(entries)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-static-reference',action='store_true',help='Explicitly allow GETs of missing pinned public files; no player/replay data is sent')
    args=parser.parse_args()
    try:print(f'Verified {restore(download=args.download_static_reference)} pinned reference files. Locks unchanged.')
    except (ValueError,OSError) as exc:parser.exit(1,str(exc)+'\n')

#!/usr/bin/env python3
"""Explicit static-reference maintenance; never called by web reads or analysis.

Fetch only civilization trees at the ALREADY pinned public commit. No replay inputs,
provider updates, binaries, installs or private data transfer. Existing locked bytes
and legacy lock are never modified. First run only: refuse to replace the new lock.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audit_techtree import load_snapshot


def main():
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument('--download-static-reference',action='store_true',required=True)
    args.parse_args()
    legacy=ROOT/'knowledge/aoe2techtree.lock.json';target=ROOT/'knowledge/situational-catalog.lock.json'
    if target.exists():raise ValueError('New catalog lock already exists; no overwrite or automatic update.')
    lock=json.loads(legacy.read_text());commit=lock['commit']
    if lock['repository']!='https://github.com/SiegeEngineers/aoe2techtree' or len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):raise ValueError('Unexpected source.')
    directory=ROOT/'data/research/aoe2techtree'/commit
    existing=load_snapshot(directory,lock);civs=existing['data.json']['civs']
    if not 1<=len(civs)<=100:raise ValueError('Unbounded civilization list.')
    files={e['path']:e for e in lock['files']}
    for name,civ in sorted(civs.items()):
        internal=name.upper()  # Upstream filenames use canonical civ keys, not legacy internal names (e.g. Indians).
        if not internal or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in internal):raise ValueError('Unsafe source name.')
        relative='trees/'+internal+'.json'
        if relative in files:continue
        url=f'https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/{commit}/data/{relative}'
        with urlopen(url,timeout=30) as response:raw=response.read(1024*1024+1)
        if len(raw)>1024*1024:raise ValueError('Oversized static tree.')
        tree=json.loads(raw)
        if not isinstance(tree.get('units_techs'),list) or not isinstance(tree.get('buildings'),list):raise ValueError('Unexpected static schema.')
        path=directory/relative;path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.read_bytes()!=raw:raise ValueError('Existing untracked source differs; no overwrite.')
        else:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(raw)
        files[relative]=dict(path=relative,upstream_path='data/'+relative,sha256=hashlib.sha256(raw).hexdigest())
        print('Pinned public reference:',name,flush=True)
    result={**lock,'civilization_trees':{name:'trees/'+name.upper()+'.json' for name in civs},'reviewed_on':datetime.now(timezone.utc).date().isoformat(),'extension_scope':'All source civilization trees at the same existing commit. Static catalog validation only; not strategic qualification. Legacy lock unchanged.','files':list(files.values())}
    load_snapshot(directory,result)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
    with os.fdopen(fd,'w') as f:json.dump(result,f,indent=2);f.write('\n')
    print('New separate lock:',target,'civilizations',len(civs),'files',len(files))


if __name__=='__main__':main()

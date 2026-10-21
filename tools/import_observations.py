#!/usr/bin/env python3
"""Explicit local observation import/export. No networking, app launch or annotation writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from observations import MAX_JSON, ObservationStore, validate_batch


def read(path):
    path=Path(path)
    if path.stat().st_size > MAX_JSON: raise ValueError('Input exceeds 4MB.')
    return json.loads(path.read_text())


def pipeline_batch(session, report):
    session=Path(session); state=read(session/'run.json'); binding=read(session/'confirmation.json')
    if (state.get('status')!='completed' or not state.get('cleanup',{}).get('complete')
        or state.get('source_association_invalidated') or state.get('source',{}).get('match_id')!=report['match_id']
        or binding.get('match_id')!=report['match_id'] or binding.get('session_id')!=state.get('session_id')
        or binding.get('roles')!=state.get('roles')):
        raise ValueError('Only completed, cleaned-up, operator-bound same-content research sessions can be exported.')
    expected={p['id']:{k:p[k] for k in ('id','name','civilization')} for p in report['players']}
    roles=state.get('roles')
    if (len(expected)!=2 or not isinstance(roles,dict) or set(roles)!={'left','right'}
        or any(not isinstance(p,dict) or type(p.get('id')) is not int or p != expected.get(p['id']) for p in roles.values())
        or {p['id'] for p in roles.values()} != set(expected)):
        raise ValueError('Pipeline HUD roles do not exactly bind the report players.')
    points=[]; evidence=[]; seen=set(); omitted=0
    for frame in state['frames']:
        clock=frame.get('values',{}).get('clock')
        if not frame.get('reviewable_candidate') or type(clock) is not int or clock in seen:
            omitted+=1; continue
        index=frame['index']
        if type(index) is not int or index<0: raise ValueError('Invalid frame index.')
        file=f'frame-{index:03}.png'; path=(session/file).resolve()
        if not path.is_relative_to(session.resolve()): raise ValueError('Frame evidence escapes session root.')
        raw=path.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
        if sha!=frame.get('source_sha256'): raise ValueError('Captured evidence changed.')
        seen.add(clock); evidence.append(dict(file=file,sha256=sha))
        for role in ('left','right'):
            for resource in ('food','wood','gold','stone'):
                points.append(dict(time_seconds=clock,player_id=state['roles'][role]['id'],metric=f'resource_{resource}',
                                   value=frame['values'][f'{role}_{resource}'],quality='unreviewed',evidence_sha256=sha))
    if not points: raise ValueError('No reviewable clock-bound resource frames; no zero-filled export.')
    batch=dict(schema_version=1,match_id=report['match_id'],replay_build=state['source']['replay_provenance']['build_version'],
               provider=dict(name='CaptureAge',ui_version=binding['captureage_ui_version_operator_confirmed'],method='windows_ocr',extractor_version='captureage-hud-resources-v1',
                             clock='displayed_game_clock_integer_seconds',binding='operator_confirmed_offline_replay_names_civs_roles'),
               players=[{k:p[k] for k in ('id','name','civilization')} for p in report['players']],points=points,evidence=evidence)
    summary=dict(total_frames=len(state['frames']),exported_frames=len(seen),excluded_frames=omitted)
    batch['collection_summary']=summary
    validate_batch(batch,report)
    return batch,summary


def main():
    cli=argparse.ArgumentParser(description=__doc__); sub=cli.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import'); imp.add_argument('batch',type=Path); imp.add_argument('--evidence-root',type=Path,required=True)
    imp.add_argument('--store',type=Path,default=Path(__file__).resolve().parents[1]/'data/observations')
    imp.add_argument('--confirm-experimental-local-import',action='store_true')
    export=sub.add_parser('export-pipeline'); export.add_argument('--session',type=Path,required=True); export.add_argument('--output',type=Path,required=True)
    for p in (imp,export): p.add_argument('--report',type=Path,required=True)
    args=cli.parse_args()
    try:
        report=read(args.report)
        if args.command=='import':
            if not args.confirm_experimental_local_import: raise ValueError('Explicit experimental import confirmation required.')
            result=ObservationStore(args.store).import_batch(read(args.batch),report,args.evidence_root)
            print('Imported experimental observation batch:',result,'; NOT verified coaching state.')
        else:
            batch,summary=pipeline_batch(args.session,report)
            fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as stream: json.dump(batch,stream,indent=2,ensure_ascii=False,allow_nan=False)
            print('Research export only; review before importing.',json.dumps(summary))
    except (ValueError,OSError,KeyError,TypeError) as exc: cli.exit(2,f'{type(exc).__name__}: {exc}\n')


if __name__=='__main__': main()

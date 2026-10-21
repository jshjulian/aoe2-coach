"""Offline measurement audit; no app control, networking, state imports or qualification.

Labels are reviewer assertions. Even blind human labels are not independently
verified engine state. Historical extractor outputs without code provenance stay
explicitly unpinned, and no score activates coaching.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
from tools.read_captureage_signals import METRICS,duration
from tools.audit_provenance import fingerprint

ROOT=Path(__file__).resolve().parent
VERSION=1
EXTRACTOR='research-visible-signals-v3'
FIELDS={'clock'}|{f'{side}_{m}' for side in ('left','right') for m in METRICS}
STATUSES={'exact','rounded','unreadable','not_displayed','crop_incomplete','disputed','unlabeled'}
MAX_JSON=4*1024*1024


def digest(raw):return hashlib.sha256(raw).hexdigest()
def encoded(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def is_hash(value):return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None

def load_json(path,limit=MAX_JSON):
    path=Path(path)
    if path.stat().st_size>limit:raise ValueError('Oversized audit JSON.')
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('Duplicate JSON key.')
            result[k]=v
        return result
    def invalid(_):raise ValueError('Non-finite JSON number.')
    def finite(text):
        value=float(text)
        if not math.isfinite(value):raise ValueError('Non-finite JSON number.')
        return value
    return json.loads(path.read_text(),object_pairs_hook=pairs,parse_constant=invalid,parse_float=finite)

def write_json(path,value):
    raw=encoded(value)
    if len(raw)>MAX_JSON:raise ValueError('Oversized audit output.')
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(raw)

def dataset_spec(development,held_out):
    if not development or any(not is_hash(x) for x in development+held_out) or len(set(development+held_out))!=len(development+held_out):
        raise ValueError('Unique, disjoint development and held-out match hashes required.')
    return dict(schema_version=VERSION,extractor_version=EXTRACTOR,source_code_sha256=fingerprint(),
                development_match_ids=sorted(development),held_out_match_ids=sorted(held_out))

def validate_spec(spec):
    if not isinstance(spec,dict) or type(spec.get('schema_version')) is not int or spec['schema_version']!=VERSION or spec.get('extractor_version')!=EXTRACTOR:
        raise ValueError('Unsupported dataset/extractor specification.')
    dev,hold=spec.get('development_match_ids'),spec.get('held_out_match_ids')
    if not isinstance(dev,list) or not isinstance(hold,list):raise ValueError('Explicit dataset partitions required.')
    expected=dataset_spec(dev,hold)
    if spec.get('source_code_sha256')!=expected['source_code_sha256']:
        raise ValueError('Extractor source changed; create a new experiment specification and keep previous results.')
    return spec

def safe_file(root,relative,max_bytes):
    if not isinstance(relative,str):raise ValueError('Relative evidence path required.')
    r=Path(relative)
    if r.is_absolute() or '..' in r.parts:raise ValueError('Unsafe audit evidence path.')
    p=(Path(root)/r).resolve()
    if not p.is_relative_to(Path(root).resolve()) or not p.is_file() or p.stat().st_size>max_bytes:
        raise ValueError('Evidence missing, oversized or outside audit root.')
    return p

def sample_id(match_id,source_sha,field):return digest(encoded([match_id,source_sha,field]))

def command_context(report,window):
    if window is None:return None
    a,b=window;limit=report.get('duration_seconds')
    if any(type(x) is not int for x in (a,b)) or not isinstance(limit,(int,float)) or not math.isfinite(limit) or not 0<=a<b<=limit:
        raise ValueError('Explicit bounded parser-clock review window required.')
    players={p['id']:p['name'] for p in report['players']};rows=[];counts=Counter();all_counts=Counter();inside=0
    events=report.get('events',[])
    if not isinstance(events,list) or len(events)>1000000:raise ValueError('Invalid command context.')
    for e in events:
        t=e.get('time_seconds')
        if type(t) not in (int,float) or not math.isfinite(t) or not a<=t<=b:continue
        inside+=1
        if e.get('player_id') not in players:continue
        kind=e.get('kind')
        if isinstance(kind,str):all_counts[(e['player_id'],kind)]+=1
        name=e.get('unit') if kind=='queue_command' else e.get('technology') if kind=='research_command' else e.get('building') if kind=='building_placement_command' else None
        if not isinstance(name,str) or not name or len(name)>120:continue
        pid=e['player_id'];counts[(pid,kind,name)]+=1
        if len(rows)<160:rows.append(dict(event_id=e['id'],time_seconds=t,player_id=pid,player_name=players[pid],kind=kind,label=name,raw_requested_amount=e.get('amount')))
    named_count=sum(counts.values())
    return dict(parser_window_seconds=[a,b],source_event_records=inside,named_input_records=named_count,
                exported_records=len(rows),omitted_named_records=named_count-len(rows),events=rows,
                all_input_record_counts=[dict(player_id=p,player_name=players[p],kind=k,input_records=v) for (p,k),v in sorted(all_counts.items())],
                input_record_counts=[dict(player_id=p,player_name=players[p],kind=k,label=n,input_records=v) for (p,k,n),v in sorted(counts.items())],
                limitations=['Input record counts are not completed units, confirmed spending, upgrade completion or fielded composition.',
                             'Duplicate-looking inputs are retained. Multi-building queue amounts are not expanded into unit totals. All-category counts retain queue-cancellation records; positive inputs must not be read without that counterevidence.',
                             'Parser clocks and HUD clocks are separate evidence; exact synchronization is not established.',
                             'This packet does not show actual fights, casualties, arrivals, production survival or player vision.'])


def _layout(image,scratch):
    sheet=scratch/'sheet.png'
    subprocess.run(['node',str(ROOT/'tools/prepare_captureage_signals.mjs'),str(image),str(sheet)],check=True,stdout=subprocess.DEVNULL,timeout=30)
    return load_json(Path(str(sheet)+'.layout.json'))


def prepare_pack(session,report,spec,frame_indices,fields,output,window=None,layout_loader=None,renderer=None):
    spec=validate_spec(spec);session=Path(session).resolve();output=Path(output)
    if output.exists():raise ValueError('Audit output already exists; refusing overwrite.')
    mid=report.get('match_id');build=report.get('replay_provenance',{}).get('build_version')
    if not is_hash(mid) or type(build) is not int:raise ValueError('Exact replay identity/build required.')
    partition='development' if mid in spec['development_match_ids'] else 'held_out' if mid in spec['held_out_match_ids'] else None
    if partition is None:raise ValueError('Replay not assigned to this experiment.')
    run=load_json(safe_file(session,'run.json',MAX_JSON));binding=load_json(safe_file(session,'confirmation.json',MAX_JSON))
    if run.get('status')!='completed' or run.get('cleanup',{}).get('complete') is not True or run.get('source',{}).get('match_id')!=mid or run['source'].get('replay_provenance',{}).get('build_version')!=build:
        raise ValueError('Completed, cleaned, same-content/build session required.')
    if binding.get('match_id')!=mid or binding.get('session_id')!=run.get('session_id') or binding.get('captureage_ui_version_operator_confirmed')!='1.26.0' or binding.get('roles')!=run.get('roles'):
        raise ValueError('Matching explicit HUD/operator role binding required.')
    roles=binding['roles'];expected=[{k:p[k] for k in ('id','name','civilization')} for p in report['players']]
    if set(roles)!={'left','right'} or len(expected)!=2 or any(type(roles[s].get('id')) is not int for s in roles) or sorted(roles.values(),key=lambda p:p['id'])!=sorted(expected,key=lambda p:p['id']):
        raise ValueError('Exact two-player parser role identities required.')
    fields=['clock']+[x for x in fields if x!='clock']
    if len(set(fields))!=len(fields) or any(x not in FIELDS for x in fields) or not 1<=len(fields)<=45:
        raise ValueError('Unique supported visible fields required.')
    if not 1<=len(frame_indices)<=20 or len(set(frame_indices))!=len(frame_indices) or any(type(i) is not int or i<0 for i in frame_indices):
        raise ValueError('Use 1..20 unique frame indices.')
    source_frames={f['index']:f for f in run['frames']};context=command_context(report,window)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.agewise-audit-',dir=output.parent) as tmp:
        dest=Path(tmp)/'pack';dest.mkdir(mode=0o700);(dest/'evidence').mkdir();(dest/'crops').mkdir()
        samples=[];frames=[];seen=set();total=0
        for index in frame_indices:
            f=source_frames.get(index)
            if f is None or not is_hash(f.get('source_sha256')):raise ValueError('Missing original frame evidence.')
            original=safe_file(session,f'frame-{index:03d}.png',16*1024*1024);raw=original.read_bytes();sha=digest(raw)
            total+=len(raw)
            if sha!=f['source_sha256'] or sha in seen or not raw.startswith(b'\x89PNG\r\n\x1a\n') or total>128*1024*1024:
                raise ValueError('Changed/duplicate/oversized frame evidence.')
            seen.add(sha);rel=f'evidence/{sha}.png'
            with os.fdopen(os.open(dest/rel,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as out:out.write(raw)
            scratch=Path(tmp)/str(index);scratch.mkdir()
            layout=(layout_loader or _layout)(original,scratch)
            if layout.get('extractor_version')!=EXTRACTOR or layout.get('source_sha256')!=sha or layout.get('layout')!='observed_CA_1.26_3440x1440_signals_v3':raise ValueError('Unexpected source crop layout/version.')
            defs={x['name']:x for x in layout['fields']}
            frames.append(dict(source_sha256=sha,evidence_file=rel,source_frame_index=index))
            for field in fields:
                rect=defs[field]['source_rect']
                if any(type(rect.get(k)) is not int for k in ('x','y','width','height')) or not (0<=rect['x']<rect['x']+rect['width']<=3440 and 0<=rect['y']<rect['y']+rect['height']<=1440) or rect['width']>125 or rect['height']>35:raise ValueError('Invalid bounded crop.')
                sid=sample_id(mid,sha,field);side=field.split('_')[0] if field!='clock' else None
                samples.append(dict(sample_id=sid,source_sha256=sha,field=field,kind='duration' if field=='clock' or field.endswith(('_tc_idle_seconds','_housed_seconds')) else 'integer',
                                    role=side,player_id=roles[side]['id'] if side else None,source_rect=rect,crop_file=f'crops/{sid}.png'))
        if fingerprint()!=spec['source_code_sha256']:raise ValueError('Extractor changed during audit preparation.')
        task=dict(schema_version=VERSION,match_id=mid,replay_build=build,provider_ui_version='1.26.0',
                  audit_code_sha256={p:digest((ROOT/p).read_bytes()) for p in ('measurement_audit.py','tools/audit_html.py','tools/audit_page.js','tools/render_measurement_audit.mjs')}, 
                  operator_binding='operator_asserted_not_automatically_verified',roles=roles,extractor_version=EXTRACTOR,
                  source_code_sha256=spec['source_code_sha256'],dataset_spec_sha256=digest(encoded(spec)),partition=partition,
                  frames=frames,samples=samples,command_context=context,validated_for_application=False)
        write_json(dest/'render-input.json',task)
        if renderer:renderer(dest,task)
        else:subprocess.run(['node',str(ROOT/'tools/render_measurement_audit.mjs'),str(dest/'render-input.json')],check=True,timeout=60)
        (dest/'render-input.json').unlink()
        for sample in samples:sample['crop_sha256']=digest(safe_file(dest,sample['crop_file'],1024*1024).read_bytes())
        task['task_id']=digest(encoded(task));write_json(dest/'task.json',task)
        from tools.audit_html import write_page
        write_page(dest,task)
        if output.exists():raise ValueError('Audit output appeared during preparation.')
        os.rename(dest,output)
    return task


def validate_task(root):
    root=Path(root);task=load_json(safe_file(root,'task.json',MAX_JSON))
    if not isinstance(task,dict) or type(task.get('schema_version')) is not int or task['schema_version']!=VERSION or not is_hash(task.get('match_id')):raise ValueError('Unsupported audit task.')
    clean={k:v for k,v in task.items() if k!='task_id'}
    if not is_hash(task.get('task_id')) or digest(encoded(clean))!=task['task_id']:raise ValueError('Audit task integrity failure.')
    if task.get('extractor_version')!=EXTRACTOR or task.get('partition') not in ('development','held_out') or not 1<=len(task.get('frames',[]))<=20 or not 1<=len(task.get('samples',[]))<=900:
        raise ValueError('Invalid audit task scope.')
    frames={}
    for f in task['frames']:
        sha=f['source_sha256']
        if not is_hash(sha) or sha in frames or digest(safe_file(root,f['evidence_file'],16*1024*1024).read_bytes())!=sha:raise ValueError('Source evidence integrity failure.')
        frames[sha]=f
    seen=set()
    for s in task['samples']:
        sha,field,sid=(s[k] for k in ('source_sha256','field','sample_id'))
        if sha not in frames or field not in FIELDS or sid in seen or sid!=sample_id(task['match_id'],sha,field):raise ValueError('Invalid/duplicate task sample.')
        seen.add(sid)
        if digest(safe_file(root,s['crop_file'],1024*1024).read_bytes())!=s['crop_sha256']:raise ValueError('Crop integrity failure.')
    return task


def _reference(label,sample):
    if not isinstance(label,dict) or not isinstance(label.get('status'),str) or label['status'] not in STATUSES or not isinstance(label.get('text'),str) or len(label['text'])>80:raise ValueError('Invalid label status/text.')
    status,text=label['status'],label['text']
    if status!='exact':return None
    value=duration(text) if sample['kind']=='duration' else int(text) if re.fullmatch('[0-9]{1,6}',text) else None
    if value is None:raise ValueError('Exact label requires literal visible integer/duration, not corrected or abbreviated text.')
    return value


def score_pack(root,labels,predictions):
    task=validate_task(root)
    if not isinstance(labels,dict) or type(labels.get('schema_version')) is not int or labels['schema_version']!=VERSION or labels.get('task_id')!=task['task_id']:raise ValueError('Label task identity mismatch.')
    reviewer=labels.get('reviewer',{})
    if not isinstance(reviewer,dict) or reviewer.get('kind') not in ('human','assistant') or not isinstance(reviewer.get('id'),str) or not 1<=len(reviewer['id'])<=64 or type(reviewer.get('blind_to_predictions')) is not bool:raise ValueError('Explicit asserted reviewer and blinding status required.')
    reviewer={k:reviewer[k] for k in ('kind','id','blind_to_predictions')}
    if any(ord(c)<32 for c in reviewer['id']):raise ValueError('Single-line reviewer pseudonym required.')
    entries=labels.get('labels')
    if not isinstance(entries,list) or len(entries)!=len(task['samples']):raise ValueError('Every sample requires one label, including explicit unlabeled statuses.')
    by_label={}
    for label in entries:
        if not isinstance(label,dict) or label.get('sample_id') in by_label:raise ValueError('Duplicate/malformed reference label.')
        by_label[label.get('sample_id')]=label
    if set(by_label)!={s['sample_id'] for s in task['samples']}:raise ValueError('Unknown/missing reference sample.')
    if not isinstance(predictions,dict) or predictions.get('extractor_version')!=task['extractor_version'] or not isinstance(predictions.get('frames'),list) or len(predictions['frames'])>1000:raise ValueError('Bounded matching candidate artifact required.')
    provenance=predictions.get('source_code_sha256')
    if provenance is not None and provenance!=task['source_code_sha256']:raise ValueError('Candidate code does not match the pinned experiment.')
    frames={};task_shas={f['source_sha256'] for f in task['frames']};excluded=0
    for f in predictions['frames']:
        if not isinstance(f,dict) or not is_hash(f.get('source_sha256')):raise ValueError('Candidate frame evidence hash required.')
        sha=f['source_sha256']
        if sha not in task_shas:excluded+=1;continue
        if sha in frames or not isinstance(f.get('values'),dict) or set(f['values'])!=FIELDS:raise ValueError('Duplicate frame or missing/unknown candidate fields.')
        for v in f['values'].values():
            if v is not None and (type(v) is not int or not 0<=v<=1000000000):raise ValueError('Candidate readings must be bounded exact integers or null.')
        frames[sha]=f
    refs={s['sample_id']:_reference(by_label[s['sample_id']],s) for s in task['samples']}
    clocks={s['source_sha256']:refs[s['sample_id']] for s in task['samples'] if s['field']=='clock' and by_label[s['sample_id']]['status']=='exact'}
    results=[];totals=Counter();groups=defaultdict(Counter);clock_bands=defaultdict(Counter)
    for s in task['samples']:
        label=by_label[s['sample_id']];reference=refs[s['sample_id']];f=frames.get(s['source_sha256']);prediction=f['values'][s['field']] if f else None
        if label['status']=='unlabeled':status='unscored_no_reference'
        elif reference is not None:status='missing_prediction_frame' if f is None else 'abstained_on_exact_reference' if prediction is None else 'matched_exact_reference' if prediction==reference else 'valid_looking_wrong_number'
        else:status='numeric_on_non_exact_reference' if prediction is not None else 'abstained_on_non_exact_reference'
        totals[status]+=1;groups[s['field']][status]+=1
        clock=clocks.get(s['source_sha256']);clock_status='reference_clock_unknown' if clock is None else 'candidate_clock_missing' if f is None or f['values']['clock'] is None else 'clock_matched_reference' if clock==f['values']['clock'] else 'candidate_clock_wrong'
        band='unanchored' if clock is None else 'before_20m' if clock<1200 else '20m_to_40m' if clock<2400 else '40m_to_60m' if clock<3600 else 'one_hour_or_later'
        clock_bands[band][status]+=1
        results.append(dict(clock_band=band,sample_id=s['sample_id'],source_sha256=s['source_sha256'],field=s['field'],reference_status=label['status'],reference_text=label['text'],reference_value=reference,candidate_value=prediction,result=status,clock_status=clock_status,
                            timeline_pair_matches=status=='matched_exact_reference' and clock_status=='clock_matched_reference'))
    return dict(schema_version=VERSION,task_id=task['task_id'],partition=task['partition'],extractor_version=task['extractor_version'],
                source_code_provenance='matched' if provenance is not None else 'unrecorded_legacy_candidate',
                candidate_artifact_sha256=digest(encoded(predictions)),labels_artifact_sha256=digest(encoded(labels)),
                reviewer=reviewer,reviewer_assertions_independently_verified=False,
                scorer_code_sha256=digest(Path(__file__).read_bytes()),
                exact_clock_reference_frames=len(clocks),
                clock_frame_counts=dict(Counter('missing' if sha not in frames or frames[sha]['values']['clock'] is None else 'matched' if frames[sha]['values']['clock']==t else 'wrong' for sha,t in clocks.items())),
                per_clock_band={k:dict(v) for k,v in sorted(clock_bands.items())},
                sample_count=len(results),exact_reference_count=sum(v is not None for v in refs.values()),counts=dict(totals),
                per_field={k:dict(v) for k,v in sorted(groups.items())},excluded_candidate_frames=excluded,
                timeline_pair_match_count=sum(r['timeline_pair_matches'] for r in results),results=results,
                validated_for_application=False,eligible_for_primary_coaching=False,
                limitations=['Reference labels and blindness are local reviewer assertions, not verified engine ground truth.',
                             'Development and held-out partitions are declared whole-match assignments, not automatic independence certification.',
                             'Missing numeric readings and wrong-but-plausible integers are counted separately; there is no invented zero or interpolation.',
                             'Numeric output on a non-exact reference is unsupported precision, not necessarily a proven digit error.',
                             'No metric semantics, military idle, causal mechanism or application qualification is established by this report.'])

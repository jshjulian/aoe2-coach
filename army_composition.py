"""Bounded post-match role-input windows; no fielded-army or timely-response verdicts."""
import hashlib
import json
import math
from pathlib import Path
from situations import _opposing
import unit_knowledge
VERSION=1
ENGINE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
WINDOW=180
LIMIT=4


def _hash(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def _queue(e):return e.get('kind')=='queue_command' and e.get('status')=='command' and e.get('action') in ('DE_QUEUE','QUEUE') and (e.get('amount') is None or type(e['amount']) is int and 0<e['amount']<=32767)
def _scope(r,name):
    if not isinstance(r,dict) or r.get('schema_version')!=5 or not isinstance(r.get('match_id'),str) or len(r['match_id'])!=64 or any(c not in '0123456789abcdef' for c in r['match_id']):raise ValueError('Unsupported content identity.')
    d=r.get('duration_seconds');players=r.get('players');events=r.get('events')
    if type(d) not in (int,float) or not math.isfinite(d) or not 0<d<=86400:raise ValueError('Invalid recorded clock.')
    if not isinstance(players,list) or len(players)!=2 or any(not isinstance(p,dict) or type(p.get('id')) is not int or p['id']<=0 or not isinstance(p.get('name'),str) or not 0<len(p['name'])<=160 or not isinstance(p.get('civilization'),str) or not 0<len(p['civilization'])<=160 or type(p.get('won')) is not bool for p in players):raise ValueError('Requires explicit completed 1v1 identities.')
    own=[p for p in players if p['name']==name]
    if len(own)!=1 or len({p['id'] for p in players})!=2 or sum(p['won'] for p in players)!=1 or _opposing(*players) is not True:raise ValueError('Unresolved completion, player or opposition.')
    p=r.get('replay_provenance') or {}
    if type(p.get('provenance_version')) is not int or p['provenance_version']!=2 or p.get('edition')!='DE' or type(p.get('dataset_id')) is not int or p['dataset_id']!=100 or type(p.get('game_type_id')) is not int or p['game_type_id']!=0 or p.get('cheats') is not False or p.get('all_technologies') is not False or p.get('metadata_cheats') is True or p.get('de_cheats') is True or p.get('reported_mod') not in (None,'',{},[]) or p.get('rms_mod_id') not in (None,0,''):raise ValueError('Unsupported source or known custom rules.')
    if not isinstance(events,list) or len(events)>300000:raise ValueError('Event budget exceeded.')
    by={};actors={p['id']:p['name'] for p in players}
    for e in events:
        if not isinstance(e,dict) or not isinstance(e.get('id'),str) or not 0<len(e['id'])<=160 or e['id'] in by:raise ValueError('Malformed/duplicate source event.')
        t=e.get('time_seconds')
        if type(t) not in (int,float) or not math.isfinite(t) or not 0<=t<=d or type(e.get('player_id')) is not int or e['player_id'] not in actors or e.get('player')!=actors[e['player_id']]:raise ValueError('Invalid source actor/clock.')
        if e.get('unit') is not None and (not isinstance(e['unit'],str) or len(e['unit'])>160):raise ValueError('Invalid unit label.')
        by[e['id']]=e
    return own[0],next(p for p in players if p['id']!=own[0]['id']),by


def _select(events,registry):
    mandatory={}
    for e in events:mandatory.setdefault(registry[e['unit_type_id']]['role'],e)
    return sorted({e['id']:e for e in [*mandatory.values(),*events[:14],*events[-14:]]}.values(),key=lambda e:(e['time_seconds'],e['id']))


def _build(r,name):
    own,opponent,by=_scope(r,name);pack,pack_sha=unit_knowledge.local_pack();registry={u['id']:u for u in pack['units']}
    ordered=sorted(r['events'],key=lambda e:(e['time_seconds'],e['id']))
    known=[e for e in ordered if _queue(e) and type(e.get('unit_type_id')) is int and e['unit_type_id'] in registry and e.get('unit')==registry[e['unit_type_id']]['name']]
    known_ids={e['id'] for e in known};unknown=[e for e in ordered if _queue(e) and e.get('category')=='military' and e['id'] not in known_ids]
    duration=r['duration_seconds'];last_bin=max(0,math.ceil(duration/WINDOW)-1);bins={}
    for e in known:bins.setdefault(min(last_bin,int(e['time_seconds']//WINDOW)),[]).append(e)
    seeds=[];previous=[];previous_bin=None
    for index,events in sorted(bins.items()):
        enemy=[e for e in events if e['player_id']==opponent['id']]
        if not enemy:continue
        roles={registry[e['unit_type_id']]['role'] for e in enemy}
        prior_roles={registry[e['unit_type_id']]['role'] for e in previous} if previous_bin is not None and index-previous_bin<=2 else set()
        if prior_roles and any(e['player_id']==opponent['id'] and previous_bin*WINDOW<=e['time_seconds']<=min(duration,(index+1)*WINDOW) for e in unknown):prior_roles=set()
        new=roles-prior_roles;anchor=next((e for e in enemy if registry[e['unit_type_id']]['role'] in new),enemy[0])
        seeds.append(dict(index=index,events=events,enemy=enemy,roles=roles,previous=previous if prior_roles else [],prior_roles=prior_roles,new=new if prior_roles else set(),anchor=anchor))
        previous=enemy;previous_bin=index
    selected=[]
    if seeds:
        selected=[seeds[0],seeds[-1]]
        gbeto=next((s for s in seeds if 'ranged_melee' in s['roles']),None)
        change=next((s for s in reversed(seeds) if s['new']),None)
        selected += [s for s in [gbeto,change] if s is not None]
        for s in seeds:
            if len({x['index'] for x in selected})>=LIMIT:break
            selected.append(s)
    selected=sorted({s['index']:s for s in selected}.values(),key=lambda s:s['index'])[:LIMIT]
    windows=[]
    for seed in selected:
        start=seed['index']*WINDOW;end=min(duration,start+WINDOW);anchor=seed['anchor'];t=anchor['time_seconds']
        cited=_select([e for e in seed['events'] if e['player_id']==own['id']],registry)+_select(seed['enemy'],registry)
        prior=[e for e in known if e['player_id']==own['id'] and max(0,t-300)<=e['time_seconds']<t]
        prior_roles={registry[e['unit_type_id']]['role'] for e in prior};prior_by_role={}
        for e in prior:prior_by_role.setdefault(registry[e['unit_type_id']]['role'],e)
        own_unknown=any(e['player_id']==own['id'] and max(0,t-300)<=e['time_seconds']<=min(duration,t+300) for e in unknown)
        follow=next((e for e in known if e['player_id']==own['id'] and t<=e['time_seconds']<=min(duration,t+300) and registry[e['unit_type_id']]['role'] not in prior_roles),None) if prior_roles and not own_unknown else None
        previous_by_role={}
        for e in seed['previous']:previous_by_role.setdefault(registry[e['unit_type_id']]['role'],e)
        purposes={e['id']:'window_input' for e in cited}
        for e in [*prior_by_role.values(),*previous_by_role.values()]:purposes.setdefault(e['id'],'prior_role_input')
        if follow:purposes.setdefault(follow['id'],'followup_role_input')
        sources=sorted([by[id] for id in purposes],key=lambda e:(e['time_seconds'],e['id']))
        summaries=[]
        for actor in [own,opponent]:
            counts={}
            for e in cited:
                if e['player_id']!=actor['id']:continue
                role=registry[e['unit_type_id']]['role'];entry=counts.setdefault(role,dict(role=role,label=pack['roles'][role],queue_inputs=0,event_ids=[],unit_ids=[],missing_quantities=0))
                entry['queue_inputs']+=1;entry['event_ids'].append(e['id']);entry['unit_ids'].append(e['unit_type_id']);entry['missing_quantities']+=e.get('amount') is None
            for c in counts.values():c['unit_ids']=sorted(set(c['unit_ids']))
            summaries.append(dict(player_id=actor['id'],roles=list(counts.values())))
        first_own_change=None if not follow else dict(event_id=follow['id'],time_seconds=follow['time_seconds'],seconds_after_anchor=follow['time_seconds']-t,role=registry[follow['unit_type_id']]['role'])
        digest=_hash(sources)
        windows.append(dict(id='composition:'+_hash([r['match_id'],own['id'],seed['index'],digest,pack_sha,ENGINE_SHA256])[:24],window_seconds=[start,end],end_inclusive=end==duration,replay_anchor=dict(event_id=anchor['id'],time_seconds=t),
            title=' + '.join(pack['roles'][role] for role in sorted(seed['roles'])),summaries=summaries,new_opponent_roles=sorted(seed['new']),previous_opponent_roles=sorted(seed['prior_roles']),
            transition=dict(status='unclassified_own_inputs' if own_unknown else 'no_prior_own_role_basis' if not prior_roles else 'different_role_request_found' if follow else 'no_different_role_request_cited',prior_own_roles=sorted(prior_roles),first_different_role_request=first_own_change,judgment='unknown',feasibility='unknown',player_vision='unknown'),
            event_ids=[e['id'] for e in sources],evidence=[dict(event_id=e['id'],time_seconds=e['time_seconds'],player_id=e['player_id'],purpose=purposes[e['id']]) for e in sources],evidence_sha256=digest,
            source_window_seconds=[min(e['time_seconds'] for e in sources),max(e['time_seconds'] for e in sources)],
            composition_option_ids=[o['id'] for o in pack['compositions'] if o['trigger_role'] in seed['roles']],
            mixed_screen_prompt='Spear-line, Camel-line and ranged-melee requests share this window. Check which anti-cavalry support was actually present before a cavalry chase.' if {'spear','camel','ranged_melee'}<=seed['roles'] else 'Spear-line and ranged-melee requests share this window. Check whether a spear screen was actually present before assuming cavalry could chase the ranged damage.' if {'spear','ranged_melee'}<=seed['roles'] else 'Camel-line and ranged-melee requests share this window. Check whether mobile anti-cavalry support was actually present before trying to chase with Knights.' if {'camel','ranged_melee'}<=seed['roles'] else None))
    identity=lambda p:{k:p[k] for k in ['id','name','civilization']}
    return dict(schema_version=VERSION,status='available',match_id=r['match_id'],player=identity(own),opponent=identity(opponent),windows=windows,roles=pack['roles'],units=[dict(unit_id=u['id'],name=u['name'],role=u['role']) for u in pack['units']],
        reference=unit_knowledge.reference(r,own,pack),practice_cue=pack['cue'],questions=pack['transition_questions'],
        coverage=dict(window_seconds=WINDOW,window_limit=LIMIT,eligible_windows=len(seeds),truncated=len(seeds)>len(windows),unknown_military_inputs=len(unknown),selection='First/latest nonempty opposing-input windows, first ranged-melee example and latest role addition; fill chronologically to four. Editorial selection, not impact ranking.'),
        source_binding=dict(content_sha256=r['match_id'],normalizer_schema=5,analysis_generator_identity=None,provenance=r['replay_provenance'],engine_sha256=ENGINE_SHA256,pack_sha256=pack_sha),
        causal_claim=False,fielded_army_established=False,eligible_for_automatic_priority=False,eligible_for_progress=False,ai_enabled=False,
        limitations=['Roles co-requested in a 180-second window need not have been alive or together. Queues are inputs; cancellations are not netted and quantities are not unit counts.',
            'Only cited requests enter role summaries. Selected-object lists are not multiplied. Missing quantities remain missing. Unknown military aliases reduce coverage.',
            'A different-role request is not a completed transition or a timely/late verdict. No threshold is an optimal deadline; a quiet window is not inaction.',
            'Counter-compositions are authored conditional reference options. Actual banks, safe income, completed upgrades/production, forces, visibility and combat results remain unknown.'])


def build(report,name):
    try:return _build(report,name)
    except (OSError,ValueError,TypeError,KeyError,AttributeError,StopIteration) as exc:
        return dict(schema_version=VERSION,status='unavailable',match_id=report.get('match_id') if isinstance(report,dict) else None,windows=[],reason=str(exc),causal_claim=False,fielded_army_established=False,eligible_for_automatic_priority=False,eligible_for_progress=False,ai_enabled=False)

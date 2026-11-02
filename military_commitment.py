"""Post-match military investment questions. No resource/state/counter reconstruction."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from datetime import datetime,timezone
from situations import _opposing

VERSION=1
ENGINE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
LIMIT=4
BUILDINGS={'Barracks':(12,'barracks'),'Archery Range':(87,'range'),'Stable':(101,'stable'),'Siege Workshop':(49,'siege')}
UNITS={
 'Militia':(74,'barracks'),'Man-at-Arms':(75,'barracks'),'Long Swordsman':(77,'barracks'),
 'Two-Handed Swordsman':(473,'barracks'),'Champion':(567,'barracks'),'Spearman':(93,'barracks'),
 'Pikeman':(358,'barracks'),'Halberdier':(359,'barracks'),
 'Archer':(4,'range'),'Crossbowman':(24,'range'),'Arbalester':(492,'range'),
 'Skirmisher':(7,'range'),'Elite Skirmisher':(6,'range'),
 'Scout Cavalry':(448,'stable'),'Light Cavalry':(546,'stable'),'Hussar':(441,'stable'),
 'Knight':(38,'stable'),'Cavalier':(283,'stable'),'Paladin':(569,'stable'),
 'Camel Rider':(329,'stable'),'Heavy Camel Rider':(330,'stable'),
 'Battering Ram':(35,'siege'),'Capped Ram':(422,'siege'),'Siege Ram':(548,'siege'),
 'Scorpion':(279,'siege'),'Heavy Scorpion':(542,'siege'),'Mangonel':(280,'siege'),
 'Onager':(550,'siege'),'Siege Onager':(588,'siege')}
CIVILIANS={'Villager':83,'Fishing Ship':13,'Trade Cart':128,'Trade Cog':17}

def _civilian(e):return e.get('unit') in CIVILIANS and type(e.get('unit_type_id')) is int and e['unit_type_id']==CIVILIANS[e['unit']]
CONSTRAINTS={
 'resource_setup':'I had not set up the required resource.',
 'resource_access':'Safe resource access was denied.',
 'funding_population':'Resources or population room limited me.',
 'production_lost':'Production was lost or unusable.',
 'units_lost':'I lost the units I was trying to support.',
 'threat_changed':'The enemy threat changed.',
 'deliberate_mix':'I wanted complementary units, not a replacement.',
 'deliberate_small':'I deliberately wanted only a small group.',
 'other':'Another reason / correction (explain below).',
 'uncertain':'Uncertain / I cannot establish the reason.',
 'not_applicable':'This window does not represent my decision.'}
INTENTS={
 'defend_resources':'Protect workers or resource access.',
 'clear_pressure':'Clear enemy pressure.',
 'raid':'Raid or intercept reinforcements.',
 'pressure_buildings':'Pressure an enemy position or buildings.',
 'reinforce_push':'Reinforce an existing push.',
 'hold_for_age':'Buy time for an age transition.',
 'other':'Another job (explain below).',
 'uncertain':'Uncertain / I do not remember.'}
OPTIONS=[
 dict(id='keep',title='Keep producing',question='Does the existing response still have a useful job, and can it actually be funded?'),
 dict(id='support',title='Support what you have',question='Would protection, safe resource access, an upgrade or complementary support address the bottleneck?'),
 dict(id='switch',title='Adapt the composition',question='Has the threat, objective or feasibility changed enough to justify a different production line?'),
 dict(id='disengage',title='Disengage / stabilise',question='Would preserving units and workable resources be better than reinforcing this push?')]
PRACTICE='Before adding another military line, check the current response’s job, funding and protection. Adapt or disengage when the threat or feasibility changes.'


def _hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def _line(e):
    pair=UNITS.get(e.get('unit'))
    return pair[1] if pair and type(e.get('unit_type_id')) is int and e['unit_type_id']==pair[0] else None

def _queue(e):
    amount=e.get('amount')
    return (e.get('action') in ('DE_QUEUE','QUEUE') and e.get('kind')=='queue_command' and e.get('status')=='command'
        and (amount is None or type(amount) is int and 0<amount<=32767))

def _building(e):
    pair=BUILDINGS.get(e.get('building'))
    return pair[1] if pair and e.get('action')=='BUILD' and e.get('status')=='command' and type(e.get('building_type_id')) is int and e['building_type_id']==pair[0] else None

def _binding(packet,c):
    return dict(match_id=packet['match_id'],player=packet['player'],source_binding=packet['source_binding'],
                situation_id=c['id'],question_id='military-commitment-v1',window_seconds=c['window_seconds'],
                evidence_sha256=c['evidence_sha256'],event_ids=c['event_ids'])
def _key(packet,c):return json.dumps([packet['match_id'],packet['player']['id'],c['id']])
def _valid(record,packet,c):
    return (isinstance(record,dict) and record.get('binding')==_binding(packet,c)
        and type(record.get('revision')) is int and record['revision']>=1
        and isinstance(record.get('constraint'),str) and record['constraint'] in CONSTRAINTS and isinstance(record.get('intent'),str) and record['intent'] in INTENTS
        and isinstance(record.get('note'),str) and len(record['note'])<=1000
        and not any(ord(x)<32 and x not in '\n\t' for x in record['note'])
        and isinstance(record.get('recorded_at'),str)
        and record.get('provenance')=='player_account_not_measured_state' and record.get('eligible_for_measurements') is False)

def _reviewed(store,packet,c):
    empty=dict(status='unanswered',revision=0,constraint=None,intent=None,note='',eligible_for_measurements=False,provenance='player_account_not_measured_state')
    if store is None:return empty
    try:
        with store._connect() as db:record=store._get(db,'military_commitment_context',_key(packet,c))
        if record is None:return empty
        if not _valid(record,packet,c):raise ValueError('Unbound clarification.')
        return {**record,'status':'reviewed'}
    except (ValueError,TypeError,KeyError,sqlite3.Error,OSError):
        return {**empty,'status':'unavailable'}

def assessment(context):
    choice=context.get('constraint')
    if choice=='not_applicable':return 'You marked this interpretation as not applicable. The comparison and practice cue are withheld; source inputs remain inspectable.'
    if choice=='resource_setup':return 'You report that resource setup was missing. Review whether establishing safe funding and protecting the existing response was feasible before opening another line. Affordability and the outcome remain unknown.'
    if choice in ('resource_access','funding_population'):return 'You report a funding/access limitation. Sustaining the old line may not have been feasible: compare safe access or relocation with adapting or stabilising. Do not force production merely because a building exists.'
    if choice in ('production_lost','units_lost'):return 'You report a loss of units or usable production. That can change the practical choice; the input sequence alone cannot establish what was left to support.'
    if choice=='threat_changed':return 'You report a changed threat. A different line may have a legitimate job; check what the existing force still needs to cover. No counter or battle outcome is established.'
    if choice=='deliberate_mix':return 'You report complementary production, not abandoning the old line. Compare the intended jobs and funding of both; no unnecessary-switch verdict is inferred.'
    if choice=='deliberate_small':return 'You report a deliberately small investment. Continuous production was not necessarily the goal; review whether that group achieved its intended job.'
    if choice=='other':return 'Your correction is retained as a player account, not parsed into measured facts. Revisit the proposed interpretation in light of your explanation.'
    return 'The sequence establishes recorded investment, not intent, affordability or a mistake. What job was it meant to do, and what limited the response?'


def _build(report,name,store):
    players=report['players'];duration=report['duration_seconds'];mid=report['match_id']
    if report.get('schema_version')!=5 or not isinstance(mid,str) or len(mid)!=64 or any(x not in '0123456789abcdef' for x in mid):raise ValueError('Unsupported analysis identity.')
    if type(duration) not in (float,int) or not math.isfinite(duration) or not 0<duration<=86400:raise ValueError('Unsupported match clock.')
    if not isinstance(players,list) or len(players)!=2 or len({p['id'] for p in players})!=2 or any(type(p['id']) is not int or not isinstance(p.get('name'),str) or not p['name'] or not isinstance(p.get('civilization'),str) or not p['civilization'] for p in players):raise ValueError('Requires explicit opposing 1v1 identities.')
    if any(type(p.get('won')) is not bool for p in players) or sum(p['won'] for p in players)!=1:raise ValueError('Requires a completed replay with a coherent reported result; outcome does not rank the review.')
    matches=[p for p in players if p['name']==name]
    if len(matches)!=1 or _opposing(*players) is not True or type(players[0].get('team_id')) is not type(players[1].get('team_id')):raise ValueError('Player or opposition unresolved.')
    player={k:matches[0].get(k) for k in ('id','name','civilization')}
    prov=report.get('replay_provenance') or {}
    if type(prov.get('provenance_version')) is not int or prov['provenance_version']!=2 or prov.get('edition')!='DE' or type(prov.get('dataset_id')) is not int or prov['dataset_id']!=100 or type(prov.get('game_type_id')) is not int or prov['game_type_id']!=0 or prov.get('all_technologies') is not False or prov.get('cheats') is not False or prov.get('metadata_cheats') is True or prov.get('de_cheats') is True or prov.get('reported_mod') not in (None,'',{},[]) or prov.get('rms_mod_id') not in (None,0,''):raise ValueError('Unsupported source/mode or known custom rules; no interpretation proposed.')
    events=report['events']
    if not isinstance(events,list) or len(events)>300000:raise ValueError('Event budget exceeded.')
    by_id={};actors={p['id']:p['name'] for p in players}
    for e in events:
        if not isinstance(e,dict) or not isinstance(e.get('id'),str) or not 0<len(e['id'])<=160 or e['id'] in by_id:raise ValueError('Duplicate/malformed source event.')
        t=e.get('time_seconds')
        if type(t) not in (int,float) or not math.isfinite(t) or not 0<=t<=duration or type(e.get('player_id')) is not int or e['player_id'] not in actors or e.get('player')!=actors[e['player_id']]:raise ValueError('Invalid event clock or actor.')
        for key in ('unit','building','technology'):
            if e.get(key) is not None and (not isinstance(e[key],str) or len(e[key])>160):raise ValueError('Malformed source label.')
        by_id[e['id']]=e
    own=sorted([e for e in events if e['player_id']==player['id']],key=lambda e:(e['time_seconds'],e['id']))
    military=[e for e in own if _queue(e) and not _civilian(e)]
    first_build={}
    for e in own:
        line=_building(e)
        if line and line not in first_build:first_build[line]=e
    # At most one first-use transition per recognized production line. Unsupported
    # military inputs break adjacency. Simultaneous requests do not establish order.
    seeds=[];seen=set()
    for previous,current in zip(military,military[1:]):
        a,b=_line(previous),_line(current)
        if b in seen:continue
        seen.add(b)
        if not a or not b or a==b or not 0<current['time_seconds']-previous['time_seconds']<=300:continue
        if any(_line(e)==b for e in military if e['time_seconds']<current['time_seconds']):continue
        building=first_build.get(b)
        anchor=building if building and previous['time_seconds']<building['time_seconds']<current['time_seconds'] and current['time_seconds']-building['time_seconds']<=180 else current
        seeds.append((anchor,previous,current,'new_line'))
    if military and _line(military[0]) and duration-military[0]['time_seconds']>=120:
        first=military[0]
        if not any(abs(first['time_seconds']-seed[0]['time_seconds'])<=300 for seed in seeds):seeds.append((first,first,first,'opening'))
    seeds.sort(key=lambda seed:(seed[0]['time_seconds'],seed[0]['id']))
    packet=dict(schema_version=VERSION,status='available',match_id=mid,player=player,windows=[],causal_claim=False,ai_enabled=False,eligible_for_automatic_priority=False,eligible_for_progress=False,
        source_binding=dict(content_sha256=mid,normalizer_schema=5,provenance=prov,analysis_generator_identity=None,engine_sha256=ENGINE_SHA256),
        constraint_choices=[dict(id=k,label=v) for k,v in CONSTRAINTS.items()],intent_choices=[dict(id=k,label=v) for k,v in INTENTS.items()],
        coverage=dict(window_limit=LIMIT,eligible_window_count=len(seeds),truncated=len(seeds)>LIMIT,unknown_military_inputs=sum(_line(e) is None for e in military),selection='First use of a recognized production line after a different line within 300 seconds; otherwise first recorded military opening with 120 seconds follow-up. Chronological, not impact-ranked.'),
        limitations=['Inputs are not completions, surviving armies, bank, income, resource access or player vision.',
          'Movement/target orders are deliberately unused. No push, battle, threat visibility or attack arrival is inferred.',
          'Production-line questions are editorial, not counter recommendations or verified civilization/build rules. No cost or affordability calculations.',
          'Unknown units and queues can withhold windows; no window is not proof of good commitment. Team, naval and unique-unit decisions are outside this slice.'])
    for anchor,previous,current,kind in seeds[:LIMIT]:
        t=anchor['time_seconds'];lo=max(0,min(previous['time_seconds'],t-180));hi=min(duration,max(current['time_seconds'],t+180))
        local=[e for e in own if lo<=e['time_seconds']<=hi and (_queue(e) or e.get('action') in ('BUILD','RESEARCH','WALL') or e.get('order')=='Garrison')]
        local=[e for e in local if not _civilian(e)]
        before=[e for e in local if e['time_seconds']<=t][-14:];after=[e for e in local if e['time_seconds']>t][:12]
        enemy=[e for e in events if e['player_id']!=player['id'] and lo<=e['time_seconds']<=hi and (_queue(e) and _line(e) or e.get('action')=='RESEARCH' and e.get('status')=='command')]
        enemy=sorted(enemy,key=lambda e:(e['time_seconds'],e['id']))[-12:]
        ids=list(dict.fromkeys([anchor['id'],previous['id'],current['id'],*[e['id'] for e in before+after+enemy]]))
        ids.sort(key=lambda id:(by_id[id]['time_seconds'],id))
        refs=[dict(event_id=id,time_seconds=by_id[id]['time_seconds'],player_id=by_id[id]['player_id'],information='own_recorded_input' if by_id[id]['player_id']==player['id'] else 'retrospective_opponent_input_not_player_vision') for id in ids]
        digest=_hash([by_id[id] for id in ids]);id='commitment:'+_hash([VERSION,mid,player,anchor['id'],digest,ENGINE_SHA256])[:24]
        c=dict(id=id,kind=kind,title=(f"{previous['unit']} inputs → another production line" if kind=='new_line' else f"{current['unit']} opening: what was its job?"),
            replay_anchor=dict(event_id=anchor['id'],time_seconds=t),window_seconds=[lo,hi],event_ids=ids,evidence=refs,evidence_sha256=digest,
            prior_unit=previous['unit'],next_unit=current['unit'],options=OPTIONS,practice_cue=PRACTICE,
            question='What job was this military investment meant to do, and what limited it?',
            information=dict(resources=None,resource_access=None,fielded_units=None,completed_production=None,player_vision=None),
            counts=dict(prior_line_queue_inputs=sum(by_id[id]['player_id']==player['id'] and _queue(by_id[id]) and _line(by_id[id])==_line(previous) and by_id[id]['time_seconds']<=t for id in ids),
                        next_line_queue_inputs=sum(by_id[id]['player_id']==player['id'] and _queue(by_id[id]) and _line(by_id[id])==_line(current) and by_id[id]['time_seconds']>=t for id in ids),
                        missing_queue_quantities=sum(_queue(by_id[id]) and by_id[id].get('amount') is None for id in ids)))
        c['reviewed_context']=_reviewed(store,packet,c);c['assessment']=assessment(c['reviewed_context']);packet['windows'].append(c)
    packet['reason']=None if packet['windows'] else 'No bounded supported investment window. This does not establish that production was sustained, affordable or safe.'
    return packet


def build(report,name,store=None):
    try:return _build(report,name,store)
    except (ValueError,TypeError,KeyError,AttributeError,StopIteration,OSError) as exc:
        return dict(schema_version=VERSION,status='unavailable',match_id=report.get('match_id'),player=None,windows=[],causal_claim=False,ai_enabled=False,reason=str(exc))


def save_answer(store,packet,payload):
    c=next((c for c in packet.get('windows',[]) if c['id']==payload.get('situation_id')),None)
    if packet.get('status')!='available' or not c or payload.get('question_id')!='military-commitment-v1' or payload.get('confirm_identity') is not True:raise ValueError('Exact current commitment window, question and explicit player confirmation required.')
    constraint=payload.get('constraint');intent=payload.get('intent');note=payload.get('note','');revision=payload.get('expected_revision')
    if not isinstance(constraint,str) or constraint not in CONSTRAINTS or not isinstance(intent,str) or intent not in INTENTS or not isinstance(note,str) or len(note)>1000 or any(ord(x)<32 and x not in '\n\t' for x in note) or type(revision) is not int or revision<0:raise ValueError('Choose an explicit constraint and job, a revision and a plain-text note up to 1000 characters.')
    if c['reviewed_context']['status']=='unavailable':raise ValueError('Clarification history unavailable; no record was reset.')
    with store._connect() as db:
        db.execute('BEGIN IMMEDIATE');current=store._get(db,'military_commitment_context',_key(packet,c))
        if current is not None and not _valid(current,packet,c):raise ValueError('Clarification is corrupt or changed; reload. No history was reset.')
        if (current['revision'] if current else 0)!=revision:raise ValueError('Clarification changed. Reload before saving another revision.')
        store._put(db,'military_commitment_context',_key(packet,c),dict(binding=_binding(packet,c),revision=revision+1,constraint=constraint,intent=intent,note=note.strip(),recorded_at=datetime.now(timezone.utc).isoformat(),provenance='player_account_not_measured_state',eligible_for_measurements=False))

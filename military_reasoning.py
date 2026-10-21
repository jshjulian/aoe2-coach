"""Situational reasoning v1: relationships between inputs, never reconstructed intent/state."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from bisect import bisect_left, bisect_right
from datetime import datetime, timezone
from pathlib import Path
from balanced_takeaway import _scope
from situation_coaching import queue
from situations import _opposing
import situational_knowledge as knowledge

VERSION=1
ENGINE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
LOOKBACK=360
FOLLOWUP=120
SWITCH_GAP=180
LIMIT=6
CIVILIAN_QUEUES={'Villager','Fishing Ship','Trade Cart','Trade Cog'}


def _hash(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _key(packet,c):return json.dumps([packet['match_id'],packet['player']['id'],c['id']])
def _ref(e,own):return dict(event_id=e['id'],time_seconds=e['time_seconds'],player_id=e.get('player_id'),information='own_recorded_input' if e.get('player_id')==own else 'retrospective_opponent_input_not_player_vision')


def _role(e,pack,research=False):
    if queue(e):
        for r in pack['roles']:
            if e.get('unit') in r['names']:
                id=r['unit_ids'][r['names'].index(e['unit'])]
                if e.get('unit_type_id') is not None and (type(e['unit_type_id']) is not int or e['unit_type_id']!=id):return None
                return r['id']
    if research and e.get('status')=='command' and e.get('action')=='RESEARCH':
        for r in pack['research_roles']:
            if e.get('technology')==r['name'] and (e.get('technology_id') is None or type(e['technology_id']) is int and e['technology_id']==r['technology_id']):return r['role']
    return None


def _seeds(own,own_queues,enemy_inputs,pack,duration):
    """O(n log n), bounded role-pair memory; materialize at most six windows later."""
    roles={r['id']:r for r in pack['roles']};by_role={r:[] for r in roles}
    for e in enemy_inputs:by_role[_role(e,pack,True)].append(e)
    times={r:[e['time_seconds'] for e in rows] for r,rows in by_role.items()}
    reached=[e for e in own if e.get('action')=='AGE_REACHED' and e.get('status')=='observed_milestone']
    ages=[e for e in reached if e.get('technology')=='Feudal Age']
    if len(ages)!=1:return [],0
    age=ages[0];advanced=min((e['time_seconds'] for e in reached if e.get('technology') in ('Castle Age','Imperial Age')),default=float('inf'))
    found={};last={};count=0
    for previous,current in zip(own_queues,own_queues[1:]):
        a=_role(previous,pack);b=_role(current,pack);t=current['time_seconds']
        if not a or not b or a==b or not 0<t-previous['time_seconds']<=SWITCH_GAP or not age['time_seconds']<=t<advanced:continue
        lo=max(0,t-LOOKBACK);hi=min(duration,t+FOLLOWUP);threats={}
        for r,rows in by_role.items():
            i=bisect_right(times[r],t)-1
            if i>=0 and rows[i]['time_seconds']>=lo:threats[r]=rows[i]
        if not threats:continue
        focus,threat=min(threats.items(),key=lambda item:(-int(item[0] in roles[a]['preferred_against'] and item[0] not in roles[b]['preferred_against']),-item[1]['time_seconds'],item[1]['id']))
        pair=(a,b,focus)
        if t<=last.get(pair,-1):continue
        last[pair]=hi;count+=1
        seed=(previous,current,a,b,focus,threat,threats,age,lo,hi)
        slots=found.setdefault(pair,[])
        if len(slots)==2:slots[-1]=seed
        else:slots.append(seed)
    seeds=[s for slots in found.values() for s in slots]
    seeds.sort(key=lambda s:(-int(s[4] in roles[s[2]]['preferred_against'] and s[4] not in roles[s[3]]['preferred_against']),s[1]['time_seconds'],s[1]['id']))
    return seeds,count


def _binding(packet,c):
    return dict(match_id=packet['match_id'],player=packet['player'],replay_build=packet['replay_build'],
        situation_id=c['id'],rule_version=VERSION,knowledge_sha256=packet['knowledge']['sha256'],
        question_id=c['clarification']['id'],window_seconds=c['window_seconds'],event_refs=c['evidence'],source_binding=packet['source_binding'],evidence_sha256=c['evidence_sha256'])


def _valid_record(record,packet,c):
    return (isinstance(record,dict) and record.get('binding')==_binding(packet,c) and type(record.get('revision')) is int and record['revision']>=1
        and isinstance(record.get('answer'),str) and record['answer'] in {x['id'] for x in c['clarification']['choices']}
        and isinstance(record.get('note'),str) and len(record['note'])<=1000 and not any(ord(x)<32 and x not in '\n\t' for x in record['note'])
        and isinstance(record.get('recorded_at'),str) and record.get('provenance')=='player_reviewed_context_not_reconstructed_state' and record.get('eligible_for_measurements') is False)


def _reviewed(store,packet,c):
    empty=dict(status='unanswered',revision=0,answer=None,note='',provenance='player_reviewed_context_not_reconstructed_state',eligible_for_measurements=False)
    if store is None:return empty
    try:
        with store._connect() as db:record=store._get(db,'reasoning_context',_key(packet,c))
        if record is None:return empty
        if not _valid_record(record,packet,c):raise ValueError('Invalid reviewed context.')
        return {**record,'status':'reviewed'}
    except (ValueError,TypeError,KeyError,AttributeError,sqlite3.Error,OSError):
        return {**empty,'status':'unavailable','reason':'The local clarification record could not be read or bound. It was not reset. Restore/repair it before saving.'}


def _explain(c,roles,pack):
    chosen=roles[c['transition']['to_role']];threat=roles[c['threat']['role']]
    aligned=threat['id'] in chosen['preferred_against']
    answer=c['reviewed_context']['answer']
    base=(f"{chosen['name'].capitalize()}: {chosen['purpose']} {chosen['exceptions']}")
    if answer=='not_applicable':
        return dict(status='withheld_after_correction',headline='You marked this interpretation as not applicable.',text='The command sequence is retained, but no judgment or new practice is proposed from this interpretation. Your correction is separate from replay evidence.',positive=None)
    if answer=='other':
        return dict(status='player_correction_requires_review',headline='Your note supplies another purpose or correction.',text='Your explanation is retained as player-reviewed context, not parsed into game-state facts. The automatic comparison is a hypothesis to review, not a judgment that overrides your account. '+base,positive=None)
    if answer=='resource_constraint':
        return dict(status='reported_constraint',headline='The funding/access constraint changes the practical response.',text='Your review reports that the other option could not be safely funded. The switch may be an understandable bridge, not a unit-role solution to every remaining threat. Protect workers and workable space; recover safe resource access if possible before forcing another production commitment. '+base,positive=None)
    if answer=='different_threat':
        return dict(status='conditionally_supported_by_player_review',headline='The switch has a plausible job against the different threat you report.',text='Your reviewed context can justify this unit role. That does not establish a successful fight: retain damage/support for any remaining threats, and check actual numbers, positioning and upgrades. '+base,positive='You identified a different threat and requested a role suited to answering it, according to your review—not verified execution or success.')
    if answer=='reported_threat' and aligned:
        return dict(status='conditionally_supported_by_player_review',headline='This adaptation is consistent with the threat you report seeing.',text='The requested role has a useful job against that basic-unit threat under the stated conditions. Keep it protected and fieldable; requesting the right unit is not proof it arrived or won. '+base,positive='The recorded role change is consistent with your reported defensive problem; its execution/outcome remain unknown.')
    if answer=='reported_threat':
        return dict(status='conditional_comparison',headline='For the threat you report, preserve a role that actually addresses it.',text='Your review supports examining whether this switch reduced the damage/support needed against that threat. This is not proof the choice caused losses; another objective, existing force or unavailable resource can still reverse the comparison. '+base,positive=None)
    return dict(status='needs_clarification',headline='What problem was the unit-role switch meant to solve?',text='The inputs establish a transition, not why you chose it or what army was present. If the nearby opponent investment was the threat you actually saw, compare the roles below; a different scouted threat, funding constraint or existing army can justify a different answer. '+base,positive=None)


def _build(report,review,situation,gameplay,store):
    player,events,duration=_scope(report,review,situation,gameplay)
    players=report['players']
    if len(players)!=2:raise ValueError('First composition slice requires an unambiguous opposing 1v1; team decisions remain in the existing Coach.')
    own_player=next(p for p in players if p['id']==player['id']);enemy=next(p for p in players if p['id']!=player['id'])
    if _opposing(own_player,enemy) is not True:raise ValueError('Opposition unresolved.')
    if type(own_player.get('team_id')) is not type(enemy.get('team_id')):raise ValueError('Mixed team representations.')
    pack,sha=knowledge.local_pack();catalog=knowledge.catalog(report,player,pack)
    roles={r['id']:r for r in pack['roles']}
    own=sorted([e for e in events.values() if e.get('player_id')==player['id']],key=lambda e:(e['time_seconds'],e['id']))
    enemy_inputs=sorted([e for e in events.values() if e.get('player_id')==enemy['id'] and _role(e,pack,True)],key=lambda e:(e['time_seconds'],e['id']))
    enemy_buildings=[e for e in events.values() if e.get('player_id')==enemy['id'] and e.get('status')=='command' and e.get('action')=='BUILD' and e.get('building')=='Watch Tower']
    enemy_buildings.sort(key=lambda e:(e['time_seconds'],e['id']));enemy_build_times=[e['time_seconds'] for e in enemy_buildings]
    # Unsupported military queues break adjacency; never bridge them into a known-role transition.
    own_queues=[e for e in own if queue(e) and e['unit'] not in CIVILIAN_QUEUES]
    own_times=[e['time_seconds'] for e in own]
    research_rows={r['name']:[] for r in pack['research_roles']}
    for e in enemy_inputs:
        if e.get('action')=='RESEARCH' and e.get('technology') in research_rows:research_rows[e['technology']].append(e)
    research_times={name:[e['time_seconds'] for e in rows] for name,rows in research_rows.items()}
    out=dict(schema_version=VERSION,status='available',mode='deterministic',ai_enabled=False,match_id=report['match_id'],player=player,
        replay_build=(report.get('replay_provenance') or {}).get('build_version'),knowledge=dict(pack_id=pack['pack_id'],pack_version=VERSION,sha256=sha,source_commit=pack['source_commit'],authorship=pack['authorship'],sources=pack['sources']),
        catalog=catalog,source_binding=dict(content_sha256=report['match_id'],normalizer_schema=report['schema_version'],provenance_version=(report.get('replay_provenance') or {}).get('provenance_version'),analysis_generator_identity=None,reasoner_code_sha256=ENGINE_SHA256,knowledge_adapter_sha256=knowledge.ADAPTER_SHA256,catalog_lock_sha256=catalog.get('lock_sha256'),reasoner_version=VERSION),
        situations=[],primary_id=None,causal_claim=False,validated_state_measurements=[],skill_rating=None,
        coverage=dict(scope=pack['scope'],lookback_seconds=LOOKBACK,followup_seconds=FOLLOWUP,switch_gap_seconds=SWITCH_GAP,situation_limit=LIMIT,
                      selection='First and latest nonoverlapping window per role pair, then role-tradeoff questions before consistent-role questions; earlier anchor and ID tie-break. Editorial, not measured impact. No outcome/feedback/focus ranking; anchor event ID breaks same-time ties.',truncated=False),
        limitations=['Opponent investment is retrospective, not proof of player vision or fielded forces.','Requests do not establish completion, affordability, survival, army presence, losses or intent.','Only recognized basic-unit roles are modeled; unsupported military queues break a transition. Last recorded Feudal milestone is context, not independently verified continuous age state. Siege, later upgrades, unique units, naval forces and team coordination are outside this slice.'])
    building_rows={name:[] for name in ('Barracks','Archery Range','Stable','Watch Tower','Mining Camp')}
    for e in own:
        if e.get('status')=='command' and e.get('action')=='BUILD' and e.get('building') in building_rows:building_rows[e['building']].append(e)
    building_times={name:[e['time_seconds'] for e in rows] for name,rows in building_rows.items()}
    seeds,eligible_count=_seeds(own,own_queues,enemy_inputs,pack,duration);candidates=[]
    for previous,current,a,b,focus_role,threat,threats,age,lo,hi in seeds[:LIMIT]:
        t=current['time_seconds']
        local=own[bisect_left(own_times,lo):bisect_right(own_times,t)]
        after=own[bisect_right(own_times,t):bisect_right(own_times,hi)]
        recent=[e for e in local if _role(e,pack) or e.get('action') in ('BUILD','RESEARCH','WALL') or e.get('order')=='Garrison'][-24:]
        follow=[e for e in after if _role(e,pack) or e.get('action') in ('BUILD','RESEARCH','WALL') or e.get('order')=='Garrison'][:6]
        prior_buildings={}
        for name,rows in building_rows.items():
            i=bisect_right(building_times[name],t)-1
            if i>=0:prior_buildings[name]=rows[i]
        alternatives=[x for x in catalog['entities'] if x['catalog_available'] and x['building_catalog_available'] and x['minimum_age'] is not None and x['minimum_age']<=2 and focus_role in roles[x['role']]['preferred_against'] and x['role']!=b]
        alternatives=[x for x in alternatives if len(set(roles[x['role']]['preferred_against']) & set(threats)) >= len(set(roles[b]['preferred_against']) & set(threats))]
        alternatives.sort(key=lambda x:(x['role']!=a,x['entity_id']))
        alt=next(iter(alternatives),None)
        counterparts=[r for r in roles[b]['preferred_against'] if r!=focus_role]
        choices=[dict(id='reported_threat',label=('I saw this threat locally and was answering it.' if focus_role in roles[b]['preferred_against'] else 'I saw this threat; no different threat explains the switch.'))]
        if counterparts:
            labels=' or '.join('/'.join(roles[r]['names']) for r in counterparts)
            choices.append(dict(id='different_threat',label=f"I also saw {labels} threats; this switch was to address that."))
        choices += [dict(id='resource_constraint',label='Funding or safe resource access prevented the other option.'),dict(id='other',label='Another purpose / the interpretation needs correction (explain below).'),dict(id='uncertain',label='Uncertain / I cannot establish what I saw then.'),dict(id='not_applicable',label='This does not represent my decision; withhold the comparison.')]
        end=bisect_right(enemy_build_times,t);start=bisect_left(enemy_build_times,lo)
        fortifications=enemy_buildings[max(start,end-2):end]
        technology_context=[]
        for name,rows in research_rows.items():
            i=bisect_right(research_times[name],t)-1
            if i>=0 and rows[i]['time_seconds']>=lo:technology_context.append(rows[i])
        opponent_refs=list(dict.fromkeys([*[e['id'] for e in threats.values()],*[e['id'] for e in technology_context]]))
        chain=[]
        for e in local:
            r=_role(e,pack)
            if r and (not chain or chain[-1]['role']!=r):chain.append(dict(role=r,unit=e['unit'],event_id=e['id'],time_seconds=e['time_seconds']))
        chain=chain[-6:]
        refs=list(dict.fromkeys([previous['id'],current['id'],age['id'],threat['id'],*opponent_refs,*[e['id'] for e in fortifications],*[e['id'] for e in prior_buildings.values()],*[e['event_id'] for e in chain],*[e['id'] for e in recent],*[e['id'] for e in follow]]))[:48]
        evidence_hash=_hash([events[i] for i in refs])
        id='response:'+_hash([VERSION,report['match_id'],player['id'],previous['id'],current['id'],threat['id'],sha,ENGINE_SHA256,knowledge.ADAPTER_SHA256,evidence_hash])[:24]
        requirements=[]
        if alt:
            request=prior_buildings.get(alt['building_name'])
            requirements=[dict(check='civilization_age_catalog',status='catalog_candidate_not_readiness',text=f"{alt['name']} is listed for {player['civilization']} at age {alt['minimum_age']}; this is not a live availability claim.",event_ids=[age['id']]),
                dict(check='production',status='requested_not_completed' if request else 'not_established',text=f"{alt['building_name']} {'request exists; completion/survival unknown' if request else 'completion is not established'}.",event_ids=[request['id']] if request else []),
                dict(check='funding_position',status='unknown',text='Resources, population room, upgrades, safe resource access and positioning must actually support it.',event_ids=[])]
        c=dict(id=id,rule_id='military-role-response',rule_version=VERSION,title=f"{previous['unit']} → {current['unit']}: what changed?",topic='composition_response',
            replay_anchor=dict(event_id=current['id'],time_seconds=t),window_seconds=[lo,hi],event_ids=refs,evidence_sha256=evidence_hash,evidence=[_ref(events[i],player['id']) for i in refs],
            objective=dict(status='inferred_not_proven',text=f"Recent {roles[a]['name']} requests followed by {roles[b]['name']} requests suggest a change in the job of production, not a proven plan or attack.",event_ids=[previous['id'],current['id']]),
            threat=dict(role=focus_role,name=roles[focus_role]['name'],event_ids=opponent_refs,focus_event_id=threat['id'],status='retrospective_investment_not_observed_army'),
            information=dict(player_vision='unknown',enemy_inputs='retrospective_only',resources=None,fielded_units=None,completed_production=None),
            transition=dict(from_role=a,to_role=b,from_unit=previous['unit'],to_unit=current['unit'],event_ids=[previous['id'],current['id']],sequence=chain[-6:]),
            fortification_context=dict(event_ids=[e['id'] for e in fortifications],qualification='Tower placement requests only; location on a resource, completion, denial and player vision are not established.'),
            recent_requests=[_ref(e,player['id']) for e in recent if e['id'] in refs],prior_production=[_ref(e,player['id']) for e in prior_buildings.values() if e['id'] in refs],
            subsequent_observations=dict(status='later_inputs_not_outcomes',event_ids=[e['id'] for e in follow if e['id'] in refs],outcome='unknown'),
            comparison=dict(selected_role=roles[b],threat_role=roles[focus_role],alternative=alt,alternative_role=roles[alt['role']] if alt else None,requirements=requirements,
                conditions=f"If {roles[focus_role]['name']} was the threat you were trying to answer, compare what the two roles do; mixed forces, existing support and objectives may reverse the preference.",
                position_alternative=pack['position_alternative'],position_exceptions=pack['position_exceptions']),
            clarification=dict(id='why-role-switch-v1',question=f"What prompted the switch to {current['unit']} at {current['time']}?",choices=choices),
            missing_information=['what enemy force was actually seen and where','remaining friendly forces and local numbers','completed production and upgrades','resources/population and safe gold access','actual terrain, wall closure, tower completion and escape routes','what happened to the force afterward'],
            counterevidence=['A different enemy role may have been present or visible.','Existing damage/support may already have covered the original threat.','The new unit may have been for another location, a temporary resource constraint, or a cancelled/retried input.'],
            practice_short=pack['practice'],practice_title=pack['practice_title'],source=dict(pack_id=pack['pack_id'],pack_version=VERSION,pack_sha256=sha),
            editorial_tradeoff=int(focus_role in roles[a]['preferred_against'] and focus_role not in roles[b]['preferred_against']),causal_claim=False,validated_state_measurements=[])
        candidates.append(c)
    out['coverage']['truncated']=len(seeds)>LIMIT
    out['coverage']['eligible_transition_count']=eligible_count
    out['situations']=candidates
    out['primary_id']=out['situations'][0]['id'] if out['situations'] else None
    for c in out['situations']:
        c['reviewed_context']=_reviewed(store,out,c);c['assessment']=_explain(c,roles,pack)
    out['reason']=None if out['situations'] else 'No bounded, recognized Feudal role switch following opponent investment. No inference of safe play or absent threats.'
    return out


def build(report,review,situation,gameplay,store=None):
    try:return _build(report,review,situation,gameplay,store)
    except (ValueError,TypeError,KeyError,AttributeError,OSError,StopIteration,sqlite3.Error) as exc:
        return dict(schema_version=VERSION,status='unavailable',mode='deterministic',ai_enabled=False,match_id=report.get('match_id'),player=None,primary_id=None,situations=[],causal_claim=False,validated_state_measurements=[],skill_rating=None,reason=f'Situational comparison unavailable: {exc}')


def recommendations(packet):
    if packet.get('status')!='available':return []
    return [dict(id=c['id'],topic=c['topic'],title=c['practice_title'],rule_id=c['rule_id'],rule_version=VERSION,
                 practice_short=c['practice_short'],source=c['source'],replay_anchor=c['replay_anchor']) for c in packet['situations']]


def save_answer(store,packet,payload):
    c=next((c for c in packet.get('situations',[]) if c['id']==payload.get('situation_id')),None)
    if packet.get('status')!='available' or not c or payload.get('confirm_identity') is not True or payload.get('question_id')!=c['clarification']['id']:
        raise ValueError('Current source situation, exact question and explicit reviewed-player confirmation required.')
    answer=payload.get('answer');note=payload.get('note','');revision=payload.get('expected_revision')
    if not isinstance(answer,str) or answer not in {x['id'] for x in c['clarification']['choices']} or not isinstance(note,str) or len(note)>1000 or any(ord(x)<32 and x not in '\n\t' for x in note) or type(revision) is not int or revision<0:
        raise ValueError('Use an explicit offered answer, revision and plain-text note up to 1000 characters.')
    if c['reviewed_context']['status']=='unavailable':raise ValueError('Clarification history unavailable; no record was reset.')
    with store._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current=store._get(db,'reasoning_context',_key(packet,c))
        if current is not None and not _valid_record(current,packet,c):raise ValueError('Clarification changed or is corrupt. Reload; history was not reset.')
        if (current['revision'] if current else 0)!=revision:raise ValueError('Clarification changed. Reload before saving another revision.')
        store._put(db,'reasoning_context',_key(packet,c),dict(binding=_binding(packet,c),revision=revision+1,answer=answer,note=note.strip(),recorded_at=datetime.now(timezone.utc).isoformat(),provenance='player_reviewed_context_not_reconstructed_state',eligible_for_measurements=False))

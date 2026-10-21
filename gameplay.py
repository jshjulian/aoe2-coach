"""Whole-match conditional coaching v2; preserved siege v1 IDs. No battle state."""
import hashlib
import json
import math
import sqlite3
from bisect import bisect_left,bisect_right
from gameplay_knowledge import local_pack,reference
from situation_coaching import queue,military
VERSION=2
SIEGE_VERSION=1
WINDOW=300


def _number(v):return type(v) in (int,float) and math.isfinite(v)
def _ids(e):
    ids=e.get('object_ids')
    return isinstance(ids,list) and bool(ids) and len(ids)<=512 and all(type(x) is int and x>0 for x in ids) and len(set(ids))==len(ids)
def _key(packet,c):return json.dumps([packet['match_id'],packet['player']['id'],c['id']],ensure_ascii=False)


def _build_siege(report,name,store=None):
    out=dict(schema_version=SIEGE_VERSION,match_id=report.get('match_id'),replay_build=(report.get('replay_provenance') or {}).get('build_version'),player=None,status='abstained',primary=None,candidates=[],
             validated_state_measurements=[],user_confirmed_observations=[],causal_claim=False,skill_rating=None,
             priority_policy='Own siege queue + packing checkpoint can head the new presentation; editorial specificity, not measured damage. Legacy review/ranking/IDs remain unchanged.',
             coverage={'scope':'bounded own siege queue and packing commands, across the whole match','battle_state_reconstructed':False},reason=None)
    def stop(reason):out['reason']=reason;return out
    if report.get('schema_version')!=5 or report.get('excerpt') or not isinstance(report.get('match_id'),str) or len(report['match_id'])!=64 or any(c not in '0123456789abcdef' for c in report['match_id']):return stop('Complete schema-5 content-identified report required.')
    players=report.get('players',[])
    if not isinstance(players,list) or any(not isinstance(p,dict) or type(p.get('id')) is not int or not isinstance(p.get('name'),str) for p in players) or len({p['id'] for p in players})!=len(players):return stop('Player identities are malformed.')
    chosen=[p for p in players if p['name']==name]
    if not name or len(chosen)!=1:return stop('Choose an unambiguous player.')
    player=chosen[0];out['player']={k:player.get(k) for k in ('id','name','civilization')}
    events=report.get('events');duration=report.get('duration_seconds')
    if not _number(duration) or duration<=0 or not isinstance(events,list) or len(events)>300000:return stop('Invalid/bounded event stream required.')
    if any(not isinstance(e,dict) or not isinstance(e.get('id'),str) or not e['id'] or not _number(e.get('time_seconds')) or not 0<=e['time_seconds']<=duration or e.get('player_id') is not None and type(e['player_id']) is not int or e.get('position') is not None and (not isinstance(e['position'],dict) or not all(_number(e['position'].get(k)) and 0<=e['position'][k]<=1000 for k in ('x','y'))) for e in events) or len({e['id'] for e in events})!=len(events):return stop('Invalid times, actors or duplicate event references.')
    out['_valid_stream']=True
    try:pack,pack_hash=local_pack();concept=next(c for c in pack['concepts'] if c['id']=='siege.recommitment')
    except (OSError,ValueError,KeyError,TypeError,AttributeError,StopIteration):return stop('Conditional knowledge unavailable; existing Coach remains separate.')
    own=sorted([e for e in events if e.get('player_id')==player['id']],key=lambda e:(e['time_seconds'],e['id']))
    times=[e['time_seconds'] for e in own]
    queues=[e for e in own if queue(e) and e.get('unit')=='Trebuchet' and e.get('unit_type_id')==331 and _ids(e)]
    qtimes=[e['time_seconds'] for e in queues]
    packing=[e for e in own if e.get('status')=='command' and e.get('action')=='SPECIAL' and e.get('order')=='Pack Trebuchet' and _ids(e)]
    previous_end=-1
    for anchor in packing:
        t=anchor['time_seconds']
        if t<=previous_end:continue
        prior=queues[bisect_left(qtimes,max(0,t-WINDOW)):bisect_right(qtimes,t)]
        if not prior:continue
        seed=prior[0];lo=seed['time_seconds'];hi=min(duration,lo+WINDOW)
        window=own[bisect_left(times,lo):bisect_right(times,hi)];previous_end=hi
        pack_events=[e for e in packing if lo<=e['time_seconds']<=hi]
        requests=[e for e in window if queue(e) and e.get('unit')=='Trebuchet' and e.get('unit_type_id')==331 and _ids(e)]
        cancels=[e for e in window if e.get('status')=='command' and (e.get('kind')=='queue_cancel_command' or e.get('order')=='Unqueue')]
        support=[e for e in window if military(e) and e.get('unit')!='Trebuchet']
        research=[e for e in window if e.get('status')=='command' and e.get('action')=='RESEARCH']
        selected=set(x for e in pack_events for x in e['object_ids'])
        orders=[e for e in window if e.get('status')=='command' and e.get('action') in ('MOVE','ORDER','PATROL','ATTACK_MOVE','STOP') and _ids(e) and selected.intersection(e['object_ids'])]
        # Keep anchors and counters first, cap context; counts remain INPUT RECORDS.
        refs=list(dict.fromkeys(e['id'] for e in [seed,anchor,*cancels,*requests,*pack_events,*support,*research,*orders]))[:128]
        response_ids=list(dict.fromkeys(e['id'] for e in [*pack_events,*support,*research,*orders,*cancels] if e['id'] in refs))
        identity=json.dumps([report['match_id'],player['id'],'siege-recommitment',seed['id'],anchor['id'],SIEGE_VERSION,pack_hash])
        id='siege-recommitment:'+hashlib.sha256(identity.encode()).hexdigest()[:24]
        facts=[dict(evidence_class='recorded_command',text='Trebuchet queue and later packing inputs were recorded. Requests and retries are not completed siege or losses.',event_ids=[seed['id'],anchor['id']],information='own_inputs_at_or_before_anchor'),
               dict(evidence_class='recorded_command',text=f'{len(cancels)} queue-cancellation input records occur in this window; the affected units and final queue are unresolved.',event_ids=[e['id'] for e in cancels if e['id'] in refs],information='retrospective_window_context_not_decision_time_state')]
        c=dict(id=id,topic='siege_recommitment',rule_id='siege-recommitment',rule_version=SIEGE_VERSION,title='Protect siege before recommitting',
               summary='Trebuchet queue and packing inputs mark a decision to inspect. Before committing siege again, its target, protection and fallback matter more than simply requesting replacements.',
               replay_anchor={'event_id':anchor['id'],'time_seconds':t},window_seconds=[lo,hi],event_ids=refs,
               recorded=facts,validated_state_measurements=[],user_confirmed_observations=[],
               hypothesis=concept['hypothesis'],question=concept['question'],principle=concept['principle'],
               practice_short=concept['practice'],exercise=concept['practice'],options=concept['options'],interactions=[i for i in pack.get('interactions',[]) if i['concept_id']==concept['id']],
               alternatives=[concept['exception'],'Queue inputs may be retries or cancelled. Support may already have existed, or not yet completed/arrived; no absence-of-army claim follows.'],
               information_available='Your own queue/packing inputs are the decision anchors. Enemy composition, actual positions and player vision are not established; no opponent queue is treated as information you saw.',
               response_summary='Packing, support/research inputs and orders to overlapping selected IDs are inspectable below. They do not prove movement, escort arrival, successful retreat or repeated failed attacks.',
               response_event_ids=response_ids,missing_information=concept['required_state_for_verdict'],
               source={'pack_id':pack['pack_id'],'pack_version':pack['pack_version'],'pack_sha256':pack_hash,'authorship':pack['authorship'],'review_status':pack['review_status']},
               causal_claim=False,battle_outcome='unknown',feedback=None)
        out['candidates'].append(c)
        if len(out['candidates'])==3:break
    if out['candidates']:
        out['status']='conditional_review';out['primary']=out['candidates'][0]
        out['reference']=reference(report,player,pack)
        if store:
            try:
                with store._connect() as db:
                    for c in out['candidates']:
                        feedback=store._get(db,'gameplay_feedback',_key(out,c))
                        if feedback and feedback.get('match_id')==out['match_id'] and feedback.get('decision_id')==c['id'] and feedback.get('player')==out['player'] and feedback.get('provenance')=='user_report_not_reconstructed_state' and feedback.get('eligible_for_automatic_priority') is False:
                            c['feedback']=feedback
                            if feedback.get('note'):c['user_confirmed_observations']=[dict(evidence_class='user_report',text=feedback['note'],verdict=feedback['verdict'],provenance=feedback['provenance'],timed_measurement=False,eligible_for_automatic_priority=False)]
            except (OSError,ValueError,TypeError,AttributeError,sqlite3.Error):out['feedback_unavailable']=True
    else:stop('No positive own queue-and-packing checkpoint in the bounded search. This does not establish no siege, no mistakes, or a peaceful game.')
    return out


def build(report,name,store=None,situation=None):
    from gameplay_checkpoints import build_candidates
    out=_build_siege(report,name)
    out['schema_version']=VERSION
    if not out.pop('_valid_stream',False):return out
    siege=list(out['candidates']);extra=[]
    try:
        pack,sha=local_pack(2)
        extra=build_candidates(report,out['player'],pack,sha,out['coverage'])
        out['reference']=reference(report,out['player'],pack)
        from gameplay_matchups import build_matchups
        raw_player=next(p for p in report['players'] if p['id']==out['player']['id'])
        out['matchups']=build_matchups(report,raw_player,pack,out['reference'])
    except (OSError,ValueError,KeyError,TypeError,AttributeError,StopIteration):
        out['additional_knowledge_unavailable']=True
    # Preserve v1 siege identities and its shipped main selection. Other topics are bounded
    # alternatives; specific existing defensive reviews retain priority over new heuristics.
    extra.sort(key=lambda c:(-c['editorial_tier'],c['replay_anchor']['time_seconds'],c['id']))
    out['candidates']=siege+extra
    protected=(situation or {}).get('recommendations',[])
    retain_existing=bool(protected and protected[0].get('topic') in {'forward_castle','early_defense','transition_defense','forward_fortification'})
    out['primary']=siege[0] if siege else None if retain_existing else next(iter(extra),None)
    out['status']='conditional_review' if out['candidates'] else 'abstained'
    out['reason']=None if out['candidates'] else 'No supported positive-input checkpoint in current coverage; no claim of safe play or absence of opportunities.'
    out['coverage'].update(scope='whole-match tactical changes, siege, economy/army investment, production, distant sites, walling and upgrade requests',battle_state_reconstructed=False)
    out['priority_policy']='Preserve the shipped siege checkpoint and specific existing defense priority. Otherwise prefer an inspectable tactical change over investment/layout questions, then earlier anchors. Editorial reviewability, not damage, command volume, outcome or a skill score. Other topics remain selectable.'
    out['existing_review_preferred']=retain_existing and not siege
    if store:
        try:
            with store._connect() as db:
                for c in out['candidates']:
                    feedback=store._get(db,'gameplay_feedback',_key(out,c))
                    if isinstance(feedback,dict) and feedback.get('match_id')==out['match_id'] and feedback.get('decision_id')==c['id'] and feedback.get('player')==out['player'] and feedback.get('replay_build')==out['replay_build'] and feedback.get('rule_version')==c['rule_version'] and feedback.get('source')==c['source'] and feedback.get('verdict') in ('useful','misinterpreted','uncertain') and isinstance(feedback.get('note'),str) and len(feedback['note'])<=1000 and isinstance(feedback.get('recorded_at'),str) and feedback.get('provenance')=='user_report_not_reconstructed_state' and feedback.get('eligible_for_automatic_priority') is False:
                        c['feedback']=feedback
                        if isinstance(feedback.get('note'),str) and feedback['note']:c['user_confirmed_observations']=[dict(evidence_class='user_report',text=feedback['note'],verdict=feedback['verdict'],provenance=feedback['provenance'],timed_measurement=False,eligible_for_automatic_priority=False)]
        except (OSError,ValueError,TypeError,AttributeError,sqlite3.Error):out['feedback_unavailable']=True
    return out


def save_feedback(store,packet,payload):
    if packet.get('schema_version')!=VERSION or not packet.get('player'):raise ValueError('Reload an unambiguous gameplay review.')
    c=next((c for c in packet['candidates'] if c['id']==payload.get('decision_id')),None)
    verdict=payload.get('verdict');note=payload.get('note','')
    if not c or verdict not in ('useful','misinterpreted','uncertain') or not isinstance(note,str) or len(note)>1000 or any(ord(x)<32 and x not in '\n\t' for x in note):raise ValueError('Current decision, explicit verdict and plain-text note up to 1000 characters required.')
    from datetime import datetime,timezone
    value=dict(match_id=packet['match_id'],replay_build=packet['replay_build'],player=packet['player'],decision_id=c['id'],rule_version=c['rule_version'],source=c['source'],
               verdict=verdict,note=note.strip(),recorded_at=datetime.now(timezone.utc).isoformat(),provenance='user_report_not_reconstructed_state',eligible_for_automatic_priority=False)
    with store._connect() as db:
        db.execute('BEGIN IMMEDIATE');store._put(db,'gameplay_feedback',_key(packet,c),value)

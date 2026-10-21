"""Explicit local practice journal. Command cues and self-reports are never skill grades.

Uses new revisioned record kinds in CoachingStore; legacy records/IDs are untouched.
An exact replay name is a user-selected practice identity, not account authentication.
"""
from datetime import datetime, timezone
import json
import sqlite3
import uuid

VERSION=1
CONTROLS_VERSION=1
OPERATIONS={'practice_start','practice_switch','practice_log','practice_keep','practice_retire'}
WHEN={
 'early_defense':'When I notice a raid threatening exposed workers.',
 'forward_castle':'When I spot a threatening Castle foundation.',
 'forward_fortification':'When I spot threatening forward construction.',
 'transition_defense':'When an age transition coincides with visible pressure.',
 'local_pressure':'When pressure threatens an important part of my base.',
 'siege_recommitment':'When I am about to reposition or recommit siege.',
 'engagement_decision':'When I am committing or repositioning a force.',
 'military_sustainability':'When economy investment competes with fielding replacements.',
 'production_investment':'Before I add military production capacity.',
 'map_control':'Before I commit to a distant resource or position.',
 'walling':'When I use a wall or gate to protect access.',
 'upgrade_transition':'Before I invest in an army upgrade or composition transition.',
 'composition_response':'Before I change the role of my military production.',
}
ADAPT='Choose a feasible response for the actual forces, resources and vision; retreat or change the plan if contesting is unsafe.'


def _prefix(name):return json.dumps(name,ensure_ascii=False)+':'
def _focus_key(name,id):return _prefix(name)+id

def _active(store,db,name):
    pointer=store._get(db,'practice_active',name) or {}
    id=pointer.get('focus_id')
    focus=store._get(db,'practice_focus',_focus_key(name,id)) if id else None
    return focus if focus and focus['status']=='active' else None


def _text(payload,key,limit,required=True):
    value=payload.get(key,'')
    if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 and c not in '\n\t' for c in value):
        raise ValueError(f'Invalid {key}; maximum {limit} plain-text characters.')
    value=value.strip()
    if required and not value:raise ValueError(f'{key} is required.')
    return value


def _logs(store,db,focus,limit=30):
    prefix=focus['id']+':'
    args=('practice_log',len(prefix),prefix)
    rows=db.execute('SELECT data FROM records WHERE kind=? AND substr(key,1,?)=? ORDER BY rowid DESC LIMIT ?',(*args,limit)).fetchall()
    count=db.execute('SELECT count(*) FROM records WHERE kind=? AND substr(key,1,?)=?',args).fetchone()[0]
    return [json.loads(r[0]) for r in rows],count


def _suggestions(report,situation):
    if not situation.get('player'):return []
    events={e['id']:e for e in report['events']};out=[]
    # Primary first, then explicitly selectable command checkpoints. Never authored prose.
    seen=set()
    for r in situation.get('practice_recommendations',situation.get('recommendations',[])[:1])[:32]:
        if r.get('id') in seen:continue
        seen.add(r.get('id'))
        if r.get('topic') not in WHEN or not r.get('practice_short'):continue
        anchor=r.get('replay_anchor',{});event=events.get(anchor.get('event_id'))
        if event is None:continue
        out.append(dict(id=r['id'],label=r['title'],when=WHEN[r['topic']],action=r['practice_short'],adapt=ADAPT,
                        source=dict(kind='situation_suggestion',topic=r['topic'],rule_id=r['rule_id'],rule_version=r['rule_version'],recommendation_id=r['id'],knowledge_pack_sha256=r.get('source',{}).get('pack_sha256')),
                        evidence=[dict(event_id=event['id'],time_seconds=event['time_seconds'])]))
        if len(out)==24:break  # 15 gameplay + two situation + six reasoning sources fit.
    return out


def _candidate(report,situation,focus):
    topic=focus['source'].get('topic');events={e['id']:e for e in report['events']}
    recommendations=[e.get('recommendation',{}) for e in situation.get('episodes',[])] or situation.get('recommendations',[])
    refs=[]
    if topic:
        for r in recommendations:
            e=events.get(r.get('replay_anchor',{}).get('event_id'))
            if r.get('topic')==topic and e and e['id'] not in [x['event_id'] for x in refs]:
                refs.append(dict(event_id=e['id'],time_seconds=e['time_seconds']))
    return dict(status='review_candidate' if refs else 'insufficient_evidence',evidence=refs[:3],
                explanation='Recorded command cues match this focus topic. Check whether you could see them and whether the opportunity really applied; these are not verified attacks or proof of your response.' if refs else
                'No qualified automatic opportunity check for this focus in this match. Missing cues do not mean no opportunity; use your recollection or replay review, or leave it uncertain.')


def context(store,report,situation,gameplay=None,reasoning=None):
    effective=situation
    if gameplay and gameplay.get('schema_version')==2 and gameplay.get('causal_claim') is False and gameplay.get('match_id')==report['match_id'] and gameplay.get('player')==situation.get('player'):
        main=[gameplay['primary']] if gameplay.get('primary') else situation.get('recommendations',[])[:1]
        effective={**situation,'recommendations':main,
                   'practice_recommendations':[*main,*gameplay.get('candidates',[]),*situation.get('recommendations',[])],
                   'episodes':[*situation.get('episodes',[]),*[{'recommendation':c} for c in gameplay.get('candidates',[])]]}
    if reasoning and reasoning.get('schema_version')==1 and reasoning.get('status')=='available' and reasoning.get('match_id')==report['match_id'] and reasoning.get('player')==situation.get('player') and reasoning.get('causal_claim') is False:
        from military_reasoning import recommendations
        additions=recommendations(reasoning)
        effective={**effective,'practice_recommendations':[*effective.get('practice_recommendations',effective.get('recommendations',[])),*additions],
                   'episodes':[*effective.get('episodes',[]),*[{'recommendation':c} for c in additions]]}
    try:
        return _context(store,report,effective)
    except (ValueError,TypeError,KeyError,AttributeError,OSError,sqlite3.Error):
        # A corrupt optional journal must not take automatic Coach or legacy state down.
        return dict(schema_version=VERSION,status='unavailable',current_match=dict(match_id=report['match_id'],player=situation.get('player'),build=report.get('replay_provenance',{}).get('build_version'),map=report.get('map')),
                    active_focus=None,suggestions=[],recent_logs=[],logged_match_count=0,history=[],current_log=None,opportunity=None,legacy_goal_active=False,
                    eligible_for_automatic_priority=False,skill_improvement_established=False,
                    identity_basis='explicitly_selected_exact_replay_name_not_verified_account',
                    limitation='The local practice journal could not be read. No records were cleared or replaced. Restore or repair the local journal before saving practice.')


def _context(store,report,situation):
    player=situation.get('player')
    current=dict(match_id=report['match_id'],player=player,build=report.get('replay_provenance',{}).get('build_version'),map=report.get('map'))
    base=dict(schema_version=VERSION,current_match=current,status='select_player' if not player else 'not_started',
              active_focus=None,suggestions=_suggestions(report,situation),recent_logs=[],logged_match_count=0,history=[],current_log=None,
              opportunity=None,legacy_goal_active=False,eligible_for_automatic_priority=False,skill_improvement_established=False,
              identity_basis='explicitly_selected_exact_replay_name_not_verified_account',
              limitation='Manually reviewed opportunities, not comparable-game statistics, an automatic behaviour judgment or proof of improvement.')
    if not player:return base
    name=player['name']
    with store._connect() as db:
        focus=_active(store,db,name);legacy=store._get(db,'goal',name)
        base['legacy_goal_active']=bool(legacy and legacy.get('active'))
        if focus:
            base['status']='active';base['active_focus']=focus
            base['recent_logs'],base['logged_match_count']=_logs(store,db,focus)
            base['current_log']=store._get(db,'practice_log',focus['id']+':'+report['match_id'])
            base['opportunity']=_candidate(report,situation,focus)
        prefix=_prefix(name)
        rows=db.execute('SELECT data FROM records WHERE kind=? AND substr(key,1,?)=? ORDER BY rowid DESC LIMIT 9',('practice_focus',len(prefix),prefix)).fetchall()
        for row in rows:
            past=json.loads(row[0])
            if past['status']=='retired' and len(base['history'])<8:
                logs,count=_logs(store,db,past,5)
                base['history'].append(dict(focus=past,recent_logs=logs,logged_match_count=count))
        if not focus and base['history']:base['status']='retired'
    return base


def save(store,packet,payload):
    """packet is server-generated context, NEVER accepted from a request body."""
    current=packet['current_match'];player=current['player']
    if not player:raise ValueError('An unambiguous player must be selected.')
    name=player['name'];op=payload.get('operation');now=datetime.now(timezone.utc).isoformat()
    if op not in OPERATIONS:raise ValueError('Unsupported practice operation.')
    if packet.get('schema_version')!=VERSION or packet.get('status')=='unavailable':raise ValueError('Reload or repair the local practice journal before saving.')
    with store._connect() as db:
        db.execute('BEGIN IMMEDIATE');active=_active(store,db,name)
        if op in ('practice_start','practice_switch'):
            if op=='practice_start' and (payload.get('expected_focus_id') is not None or active):raise ValueError('A practice focus is already active or changed. Reload; change it explicitly before choosing another.')
            if op=='practice_switch' and (not active or payload.get('focus_id')!=active['id'] or not packet.get('active_focus') or packet['active_focus']['id']!=active['id'] or payload.get('confirm_switch') is not True):raise ValueError('Reload the current focus and explicitly confirm switching it. Its history will be preserved.')
            legacy=store._get(db,'goal',name)
            if legacy and legacy.get('active'):raise ValueError('Stop the existing legacy goal explicitly before choosing a new practice focus. Its history will be preserved.')
            if payload.get('confirm_identity') is not True:raise ValueError('Confirm this exact replay name is your practice identity.')
            id=payload.get('suggestion_id')
            if id is not None:
                selected=next((s for s in packet['suggestions'] if s['id']==id),None)
                if not selected:raise ValueError('Suggested practice no longer matches this review; reload.')
                content={k:selected[k] for k in ('label','when','action','adapt','source','evidence')}
            else:
                content={k:_text(payload,k,limit,required=k!='adapt') for k,limit in [('label',100),('when',240),('action',400),('adapt',300)]}
                content.update(source={'kind':'user_authored'},evidence=[])
            if op=='practice_switch' and all(content[k]==active[k] for k in ('label','when','action','adapt')):raise ValueError('This is already your active habit. Choose a different habit or keep practising it.')
            focus=dict(schema_version=VERSION,id=uuid.uuid4().hex,player_name=name,status='active',selected_at=now,
                       origin=current,**content)
            if op=='practice_switch':
                active.update(status='retired',retired_at=now,retirement_reason='explicit_focus_switch',replaced_by_focus_id=focus['id'])
                focus['replaces_focus_id']=active['id']
                store._put(db,'practice_focus',_focus_key(name,active['id']),active)
            store._put(db,'practice_focus',_focus_key(name,focus['id']),focus)
            store._put(db,'practice_active',name,{'focus_id':focus['id']})
        else:
            if not active or payload.get('focus_id')!=active['id']:raise ValueError('Practice focus changed or was retired. Reload before saving.')
            if op=='practice_keep':
                active['last_kept_at']=now;store._put(db,'practice_focus',_focus_key(name,active['id']),active)
            elif op=='practice_retire':
                active.update(status='retired',retired_at=now)
                store._put(db,'practice_focus',_focus_key(name,active['id']),active)
                store._put(db,'practice_active',name,{'focus_id':None})
            else:
                if active['origin']['match_id']==current['match_id'] or payload.get('played_after_selection') is not True:
                    raise ValueError('Select a different match and confirm you played it after choosing this focus. File dates are not sufficient.')
                opportunity=payload.get('opportunity');attempt=payload.get('attempt')
                if opportunity not in ('yes','no','uncertain') or attempt not in ('yes','no','uncertain'):
                    raise ValueError('Report opportunity and attempt explicitly.')
                if opportunity!='yes' and attempt!='uncertain':raise ValueError('An attempt cannot be judged without an applicable opportunity.')
                status='not_applicable' if opportunity=='no' else 'reported_attempt' if opportunity=='yes' and attempt=='yes' else 'reported_not_attempted' if opportunity=='yes' and attempt=='no' else 'insufficient_evidence'
                # Recheck the transaction's active ID against the evidence packet, avoiding stale cross-focus cues.
                if not packet.get('active_focus') or packet['active_focus']['id']!=active['id']:raise ValueError('Reload the current focus before logging.')
                note=_text(payload,'note',1000,False)
                store._put(db,'practice_log',active['id']+':'+current['match_id'],dict(schema_version=VERSION,focus_id=active['id'],match=current,
                    recorded_at=now,opportunity=opportunity,attempt=attempt,status=status,note=note,
                    evidence=packet['opportunity']['evidence'],comparison_snapshot=packet.get('comparison_snapshot'),provenance='user_report_not_verified_execution',
                    chronology_provenance='user_confirms_played_after_focus_selection',skill_improvement_established=False))

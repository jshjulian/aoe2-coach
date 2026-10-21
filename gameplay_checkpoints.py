"""Positive-input decision checkpoints, not tactical/state diagnoses. Inputs already validated."""
import hashlib
import json
import math
from bisect import bisect_left,bisect_right
from collections import deque
from situation_coaching import queue
from situations import _anchor

PRODUCTION={'Barracks','Archery Range','Stable','Siege Workshop','Castle','Monastery','Dock'}
ECONOMY={'Town Center'}
CAMPS={'Mining Camp','Lumber Camp','Mill'}
FORTS={'Castle','Watch Tower','Guard Tower','Keep'}
WALLS={'Palisade Wall','Stone Wall','Fortified Wall','Gate','Palisade Gate'}
TACTICAL={'PATROL','DE_ATTACK_MOVE','ATTACK_MOVE','ATTACK_GROUND'}


def ids(e):
    a=e.get('object_ids')
    return isinstance(a,list) and 1<=len(a)<=512 and all(type(x) is int and x>0 for x in a) and len(set(a))==len(a)

def placement(e):return e.get('status')=='command' and e.get('action')=='BUILD' and e.get('counted_as_new_placement') is True and e.get('position') is not None

def build_candidates(report,player,pack,pack_hash,diagnostics=None):
    own=sorted([e for e in report['events'] if e.get('player_id')==player['id']],key=lambda e:(e['time_seconds'],e['id']))
    times=[e['time_seconds'] for e in own];result=[];last={};indices={}
    diagnostics=diagnostics if diagnostics is not None else {}
    diagnostics.update(checkpoint_selection='First and latest nonoverlapping supported window per additional topic; not largest impact.',tactical_recent_input_cap=64,engagement_comparison_budget=100000,engagement_search_truncated=False)
    concepts={c['topic']:c for c in pack['concepts']};duration=report['duration_seconds']
    military_names={u for f in pack['families'] for u in f['units']}|{r['name'] for r in pack['roles'] if r['kind']=='Unit'}
    military_names.update(pack.get('additional_military_aliases',[]))
    def nearby(t,before=180,after=120):return own[bisect_left(times,max(0,t-before)):bisect_right(times,min(duration,t+after))]
    def add(topic,seed,anchor,text,tier):
        if seed['time_seconds']<=last.get(topic,-1):return
        concept=concepts[topic];lo=min(seed['time_seconds'],anchor['time_seconds']);hi=min(duration,lo+300,anchor['time_seconds']+120)
        window=own[bisect_left(times,lo):bisect_right(times,hi)]
        context=[e for e in window if e.get('status')=='command' and (queue(e) or e.get('kind')=='queue_cancel_command' or e.get('order') in ('Unqueue','Garrison') or e.get('action') in ('RESEARCH','BUILD','WALL','MOVE','STOP') or e.get('action') in TACTICAL)]
        full=list(dict.fromkeys(e['id'] for e in [seed,anchor,*context]));refs=full[:96]
        id=topic+':'+hashlib.sha256(json.dumps([report['match_id'],player['id'],seed['id'],anchor['id'],2,pack_hash]).encode()).hexdigest()[:24]
        candidate=dict(id=id,topic=topic,rule_id=topic,rule_version=2,title=concept['title'],summary=concept['summary'],
            replay_anchor={'event_id':anchor['id'],'time_seconds':anchor['time_seconds']},window_seconds=[lo,hi],event_ids=refs,
            recorded=[dict(evidence_class='recorded_command',text=text,event_ids=list(dict.fromkeys([seed['id'],anchor['id']])),information='own_inputs_at_or_before_anchor')],
            validated_state_measurements=[],user_confirmed_observations=[],hypothesis=concept['hypothesis'],question=concept['question'],
            principle=concept['principle'],practice_short=concept['practice'],exercise=concept['practice'],options=concept['options'],
            interactions=[i for i in pack.get('interactions',[]) if i['concept_id']==concept['id']],
            alternatives=[concept['exception'],'Inputs can be cancelled, retried or unrelated; existing forces/buildings and completed actions remain unknown.'],
            information_available='The anchors are your own recorded inputs. Later window inputs are retrospective follow-up, not resources or options established at the anchor. No enemy command is treated as your vision.',
            response_summary='The window retains your queue, cancellation, research, construction and movement inputs. These show commands, not completed responses, fielded composition, successful defense or resource spending.',
            response_event_ids=[e['id'] for e in context if e['id'] in refs],missing_information=concept['required_state_for_verdict'],
            source={'pack_id':pack['pack_id'],'pack_version':2,'pack_sha256':pack_hash,'authorship':pack['authorship'],'review_status':pack['review_status']},
            causal_claim=False,battle_outcome='unknown',feedback=None,editorial_tier=tier,omitted_context_event_count=max(0,len(full)-len(refs)))
        slots=indices.setdefault(topic,[])
        if len(slots)==2:result[slots[-1]]=candidate
        else:slots.append(len(result));result.append(candidate)
        last[topic]=hi
    # Tactical change: never use generic ORDER alone as proof of a fight.
    tactical=deque(maxlen=64);comparisons=0
    for e in own:
        if e.get('status')!='command':continue
        t=e['time_seconds']
        while tactical and t-tactical[0][0]['time_seconds']>90:tactical.popleft()
        if e.get('action') in ('MOVE','STOP') and ids(e):
            selected=set(e['object_ids']);seed=None
            for s,selected_before in reversed(tactical):
                if comparisons>=100000:diagnostics['engagement_search_truncated']=True;break
                comparisons+=1
                if 5<=t-s['time_seconds']<=90 and len(selected_before&selected)>=2:seed=s;break
            if seed:add('engagement_decision',seed,e,'A tactical input was followed by a move/stop input to overlapping selected IDs. Selected IDs do not identify a local army or establish a retreat.',3)
        if e.get('action') in TACTICAL and ids(e) and len(e['object_ids'])>=3:tactical.append((e,frozenset(e['object_ids'])))
    diagnostics['engagement_comparisons_used']=comparisons
    buildings=[];base=_anchor(report,player['id'])
    for e in own:
        if e.get('status')!='command':continue
        if not (placement(e) or e.get('action') in ('RESEARCH','WALL')):continue
        t=e['time_seconds'];local=nearby(t);mil=[x for x in local if queue(x) and x.get('unit') in military_names]
        if (placement(e) and e.get('building') in ECONOMY or e.get('action')=='RESEARCH' and e.get('technology') in ('Hand Cart','Wheelbarrow')) and mil:
            # Anchor on the later input: do not use future queues as known options.
            m=min(mil,key=lambda x:abs(x['time_seconds']-t));seed,anchor=sorted([e,m],key=lambda x:(x['time_seconds'],x['id']))
            add('military_sustainability',seed,anchor,'An economy-expansion/efficiency input and military queue input overlap in time. Neither establishes actual villager/military population, losses or funded production.',2)
        if placement(e) and e.get('building') in PRODUCTION:
            buildings=[x for x in buildings if t-x['time_seconds']<=180]
            old=next((x for x in buildings if t-x['time_seconds']>=10 and math.hypot(e['position']['x']-x['position']['x'],e['position']['y']-x['position']['y'])>=2),None)
            if old and any(m['time_seconds']<=t for m in mil):add('production_investment',old,e,'Separate military-building placement inputs and nearby military queue inputs were recorded. Placement requests are not surviving capacity or unnecessary buildings.',2)
            buildings.append(e)
        if placement(e) and base and e.get('building') in CAMPS|FORTS:
            d=math.hypot(e['position']['x']-base['position']['x'],e['position']['y']-base['position']['y'])
            if d>=24:add('map_control',e,e,f"A {e['building']} placement was requested {d:.0f} tiles from the verified initial TC coordinates. That distance is command geometry, not current borders, resource ownership or map control.",2)
        if e.get('action')=='WALL' or placement(e) and e.get('building') in WALLS:
            add('walling',e,e,'A wall/gate placement input was recorded. Completion, closed gaps, threat and route access are not established.',1)
        if e.get('action')=='RESEARCH':
            family=next((f for f in pack['families'] if e.get('technology') in f['upgrades']),None)
            if family:
                related=[x for x in local if queue(x) and x.get('unit') in family['units']]
                if related:
                    m=min(related,key=lambda x:abs(x['time_seconds']-t));seed,anchor=sorted([e,m],key=lambda x:(x['time_seconds'],x['id']))
                    add('upgrade_transition',seed,anchor,'A unit-family research request and related queue input were recorded. These are not completed upgrades or an identified fielded composition.',2)
    return result

"""Conservative, replay-command-based AoE2 analysis using aoc-mgz."""
from __future__ import annotations
import hashlib, json, math, re, os, tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from opening_observations import OBSERVATION_VERSION, observe_openings
from replay_provenance import PROVENANCE_VERSION, read_provenance

SCHEMA_VERSION = 5


def clock(seconds: float | None) -> str | None:
    if seconds is None: return None
    n=max(0,int(seconds)); return f"{n//60:02d}:{n%60:02d}"

def _pos(position):
    return {"x": round(float(position.x),3), "y": round(float(position.y),3)} if position else None

def _category(action: str, payload: dict) -> tuple[str,str]:
    if action == "DE_QUEUE": return "military" if payload.get("unit") not in ("Villager", "Fishing Ship", "Trade Cart", "Trade Cog") else "economy", "queue_command"
    if action == "BUILD": return "buildings", "building_placement_command"
    if action == "WALL": return "buildings", "wall_placement_command"
    if action == "RESEARCH": return "technologies", "research_command"
    if action in ("BUY", "SELL"): return "economy", "market_command"
    if action in ("MOVE", "ORDER", "PATROL", "DE_ATTACK_MOVE", "ATTACK_GROUND", "SPECIAL", "GATHER_POINT", "BACK_TO_WORK", "UNGARRISON"):
        return "military", "order_command"
    if action == "DELETE": return "buildings", "delete_command"
    return "other", "command"

def _round_pos_key(pos):
    if not pos: return None
    return (round(pos['x']*2)/2, round(pos['y']*2)/2)

def _deduplicate_placements(events: list[dict]) -> None:
    """Tag near-identical repeated placement commands; never discard raw records."""
    last={}
    for e in events:
        if e["action"] not in ("BUILD", "WALL"): continue
        p=e.get("position")
        key=(e.get("player_id"),e["action"],e.get("building"),_round_pos_key(p),p.get('x_end') if p else None,p.get('y_end') if p else None)
        previous=last.get(key)
        if previous and e["time_seconds"]-previous["time_seconds"] <= .55:
            e["duplicate_of"]=previous["id"]
            e["counted_as_new_placement"]=False
        else:
            e["counted_as_new_placement"]=True
            last[key]=e

def _distance(a,b):
    return math.hypot(a["x"]-b["x"],a["y"]-b["y"])

def replay_start_from_filename(name: str) -> str | None:
    """Decode the local timestamp convention in AoE2 DE's saved replay names."""
    match = re.search(r'@(\d{4}\.\d{2}\.\d{2})\s+(\d{6})(?!\d)', name)
    if not match:
        return None
    try:
        return datetime.strptime(f'{match.group(1)} {match.group(2)}', '%Y.%m.%d %H%M%S').isoformat(timespec='seconds')
    except ValueError:
        return None


def stable_match_id(path: str | Path) -> str:
    """Content-addressed replay identity, stable across a rename or mtime change."""
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()

def analyze_match(path: str | Path, match_id: str | None=None) -> dict:
    from mgz.model import parse_match
    path=Path(path)
    match_id=match_id or stable_match_id(path)
    with path.open('rb') as handle: match=parse_match(handle)
    players=[]
    by_name={}
    for p in match.players:
        rated_1v1 = bool(match.rated and str(match.diplomacy_type).lower() == '1v1')
        player={"id":int(p.number),"name":p.name,"civilization":p.civilization,"team_id":p.team_id,
                "won":bool(p.winner),"base":_pos(p.position),
                "elo_snapshot":int(p.rate_snapshot) if rated_1v1 and p.rate_snapshot is not None else None,
                "rating_track":"1v1" if rated_1v1 and p.rate_snapshot is not None else None}
        players.append(player); by_name[p.name]=player
    events=[]; raw_events=[]
    for index,a in enumerate(match.actions):
        payload=dict(a.payload or {})
        action=getattr(a.type,'name',str(a.type))
        sec=round(a.timestamp.total_seconds(),3)
        p=by_name.get(a.player.name) if a.player else None
        pos=_pos(a.position)
        if not pos and isinstance(payload.get('x'),(int,float)) and isinstance(payload.get('y'),(int,float)) and payload.get('x',-1)>=0 and payload.get('y',-1)>=0:
            pos={"x":round(float(payload['x']),3),"y":round(float(payload['y']),3)}
        if action=="WALL" and pos:
            pos={**pos,"x_end":payload.get('x_end'),"y_end":payload.get('y_end')}
        category,kind=_category(action,payload)
        unit=payload.get('unit'); building=payload.get('building'); tech=payload.get('technology')
        if action=="SPECIAL" and str(payload.get('order') or '').lower() in ('unqueue','cancel'):
            kind="queue_cancel_command"; category="military"
        if action in ("QUEUE","DE_QUEUE") and (payload.get('building_id')==-1 or payload.get('amount',1)<0):
            kind="queue_cancel_command"
        event={"id":f"a{index}","time_seconds":sec,"time":clock(sec),"player_id":p['id'] if p else None,
          "player":p['name'] if p else None,"category":category,"action":action,"kind":kind,
          "unit":unit,"unit_type_id":payload.get('unit_id'),"building":building,"building_type_id":payload.get('building_id'),
          "technology":tech,"technology_id":payload.get('technology_id'),"order":payload.get('order'),"amount":payload.get('amount'),
          "object_ids":list(payload.get('object_ids') or []),"target_id":payload.get('target_id'),"position":pos,
          "status":"command","semantics":"recorded player command; completion not established"}
        if action=="ORDER":
            event["semantics"]="generic interaction/order; may be attack, gather, repair, or another order; target unresolved"
        if action=="DE_QUEUE":
            event["semantics"]="production queue command; not evidence the unit completed"
        if action=="SPECIAL" and str(payload.get('order') or '').lower()=='unqueue':
            event["semantics"]="explicit Unqueue command; cancellation intent recorded, resulting queue state not simulated"
        events.append(event)
        raw_events.append({"id":event['id'],"time_seconds":sec,"action":action,"player":event['player'],
                           "position":pos,"payload":payload,"sequence":payload.get('sequence')})
    _deduplicate_placements(events)
    # Initial objects are actual initial-state snapshots, not production commands.
    initial=[]
    for p in match.players:
        seen=set()
        for obj in p.objects:
            pos=_pos(obj.position) if obj.position else None
            name=obj.name or f"object {obj.object_id}"
            if 'town center' in name.lower(): pos=_pos(p.position)
            key=(name,tuple(sorted(pos.items())) if pos else None)
            if key in seen: continue
            seen.add(key)
            initial.append({"id":f"initial-{p.number}-{obj.instance_id}","player_id":int(p.number),"player":p.name,
                "name":name,"object_id":obj.instance_id,"position":pos,"status":"verified_initial_snapshot"})
    # Parser-provided age uptime records are milestones, not inferred queue completions.
    milestones=[]
    for up in match.uptimes:
        p=by_name.get(up.player.name) if up.player else None
        age=str(getattr(up,'age','')).split('.')[-1].replace('_',' ').title()
        milestones.append({"id":f"age-{p['id'] if p else '?'}-{age.lower().replace(' ','-')}","time_seconds":round(up.timestamp.total_seconds(),3),
          "time":clock(up.timestamp.total_seconds()),"player_id":p['id'] if p else None,"player":p['name'] if p else None,
          "category":"age","action":"AGE_REACHED","technology":age,"status":"observed_milestone","source":"mgz uptime"})
    # Include milestones in the normalized, timestamp-sorted stream.
    normalized=sorted(events+milestones,key=lambda e:(e['time_seconds'],e['id']))
    # Deduplicated spatial reference tables. A wall command defines a requested segment;
    # these cells are an approximate grid raster, not proof that wall tiles completed.
    wall_cells={}
    for e in events:
        if e['action']!='WALL' or not e.get('position'): continue
        pos=e['position']; x0=round(pos['x']); y0=round(pos['y']); x1=round(pos.get('x_end') if pos.get('x_end') is not None else x0); y1=round(pos.get('y_end') if pos.get('y_end') is not None else y0)
        dx=abs(x1-x0); dy=abs(y1-y0); sx=1 if x0<x1 else -1; sy=1 if y0<y1 else -1; err=dx-dy; x,y=x0,y0
        while True:
            key=(e.get('player_id'),e.get('building'),x,y)
            wall_cells.setdefault(key,[]).append(e['id'])
            if x==x1 and y==y1: break
            twice=2*err
            if twice>-dy: err-=dy; x+=sx
            if twice<dx: err+=dx; y+=sy
    wall_tiles=[{"player_id":k[0],"building":k[1],"x":k[2],"y":k[3],"source_event_ids":list(dict.fromkeys(v)),"status":"derived_from_wall_command"} for k,v in sorted(wall_cells.items())]
    town_centers=[]; tc_object_ids={}
    for p in match.players:
        components=[o for o in p.objects if 'town center' in (o.name or '').lower()]
        if components:
            ids=sorted({int(o.instance_id) for o in components}); tc_object_ids[int(p.number)]=set(ids)
            town_centers.append({"player_id":int(p.number),"player":p.name,"object_ids":ids,"position":_pos(p.position),"status":"verified_initial_snapshot"})
    tc_queue_activity=[]
    for p in players:
        ids=tc_object_ids.get(p['id'],set())
        queues=[e for e in events if e.get('player_id')==p['id'] and e['action']=='DE_QUEUE' and e.get('unit')=='Villager' and ids.intersection(e.get('object_ids',[]))]
        gaps=[]
        for previous,current in zip(queues,queues[1:]):
            seconds=round(current['time_seconds']-previous['time_seconds'],1)
            if seconds>=60:
                gaps.append({"from_event_id":previous['id'],"to_event_id":current['id'],"from_time":previous['time'],"to_time":current['time'],
                  "gap_seconds":seconds,"town_center_object_ids":sorted(ids.intersection(previous['object_ids']+current['object_ids'])),
                  "position":p['base'],"interpretation":"No new Villager queue command was recorded at this initial TC during this interval; this is not measured TC idle time."})
        tc_queue_activity.append({"player_id":p['id'],"player":p['name'],"town_center_object_ids":sorted(ids),"villager_queue_command_count":len(queues),"long_command_gaps":gaps,
          "caveat":"Queue commands are not completion events; pre-existing queue contents, initial queue state, unqueue outcomes, and actual production are not observable here."})
    speed_id = int(match.speed_id) if match.speed_id else None
    duration_seconds = round(match.duration.total_seconds(),3)
    estimated_real_duration_seconds = round(duration_seconds / (speed_id / 100), 3) if speed_id and speed_id > 0 else None
    report={"schema_version":SCHEMA_VERSION,"match_id":match_id,
      "source_file":path.name,"source_size_bytes":path.stat().st_size,"source_mtime_ns":path.stat().st_mtime_ns,
      "played_at":replay_start_from_filename(path.name),"played_at_source":"replay_filename_timestamp" if replay_start_from_filename(path.name) else None,
      "map":str(match.map),"duration_seconds":duration_seconds,"duration":clock(duration_seconds),
      "estimated_real_duration_seconds":estimated_real_duration_seconds,"game_speed":match.speed,
      "game_speed_id":speed_id,"game_speed_multiplier":round(speed_id/100,2) if speed_id else None,
      "rated":bool(match.rated),"players":players,"events":normalized,"initial_state":initial,"initial_town_centers":town_centers,
      "tc_queue_activity":tc_queue_activity,"wall_tiles":wall_tiles,"raw_events":raw_events,
      "limitations":["Queue/build/research/order entries are commands; the replay parser does not confirm most unit/building completions.",
        "No reliable resource balance, unit-death, damage, or Town Center idle-time reconstruction is performed.",
        "ORDER/Interact semantics are generic unless independently resolved; selected unit IDs do not always identify unit types."]}
    report['findings']=findings(report)
    report['pressure_incidents']=detect_pressure(report)
    report['pressure_scope']={"start":"20:40","end":"22:10","note":"Initial MVP time window; increase/disable explicitly for broader detector runs."}
    report['opening_milestones']=opening_milestones(report)
    report['charts']=command_charts(report)
    try:
        report['replay_provenance']=read_provenance(path)
    except Exception as exc:
        report['replay_provenance']={'provenance_version': PROVENANCE_VERSION, 'source': 'unavailable', 'build_version': None,
                                    'mod_compatibility': 'unknown', 'reason': f'Header provenance unavailable ({type(exc).__name__}).'}
    report['opening_observation_version']=OBSERVATION_VERSION
    report['opening_observations']=observe_openings(report)
    return report

def opening_milestones(report: dict) -> list[dict]:
    """Key opening timings: directly observed parser milestones plus recorded commands."""
    result=[]
    for p in report['players']:
        pe=[e for e in report['events'] if e.get('player_id')==p['id']]
        def first(test): return next((e for e in pe if test(e)),None)
        found={
          'feudal_arrival':first(lambda e:e.get('action')=='AGE_REACHED' and e.get('technology')=='Feudal Age'),
          'castle_research':first(lambda e:e.get('action')=='RESEARCH' and e.get('technology')=='Castle Age'),
          'castle_arrival':first(lambda e:e.get('action')=='AGE_REACHED' and e.get('technology')=='Castle Age'),
          'stable':first(lambda e:e.get('action')=='BUILD' and e.get('building')=='Stable'),
          'first_scout_queue':first(lambda e:e.get('kind')=='queue_command' and e.get('unit')=='Scout Cavalry'),
          'first_knight_queue':first(lambda e:e.get('kind')=='queue_command' and e.get('unit')=='Knight'),
          'first_archery_range':first(lambda e:e.get('action')=='BUILD' and e.get('building')=='Archery Range'),
          'first_siege_queue':first(lambda e:e.get('kind')=='queue_command' and e.get('unit') in ('Mangonel','Scorpion','Battering Ram','Siege Tower','Trebuchet')),
          'first_market':first(lambda e:e.get('action')=='BUILD' and e.get('building')=='Market'),
        }
        result.append({"player_id":p['id'],"player":p['name'],"civilization":p['civilization'],
          "milestones":{k:({"time":v['time'],"time_seconds":v['time_seconds'],"event_id":v['id'],"status":v['status']} if v else None) for k,v in found.items()}})
    return result

def command_charts(report: dict, bin_seconds: int=60) -> dict:
    """Rates of recorded commands, not unit completions/resources. One event counts once."""
    minutes=max(1,math.ceil(report['duration_seconds']/bin_seconds)); events=report['events']; players=report['players']
    production=[]
    units=sorted({e.get('unit') or 'Unknown' for e in events if e.get('kind')=='queue_command'})
    for p in players:
        for unit in units:
            counts=[0]*minutes; requested=[0]*minutes
            for e in events:
                if e.get('player_id')!=p['id'] or e.get('kind')!='queue_command' or (e.get('unit') or 'Unknown')!=unit: continue
                i=min(minutes-1,int(e['time_seconds']//bin_seconds)); counts[i]+=1; requested[i]+=max(1,int(e.get('amount') or 1))
            if any(counts): production.append({"player":p['name'],"unit":unit,"queue_commands_per_minute":counts,"requested_items_per_minute":requested})
    eco_kinds=('villager_queue','farm_placement','economic_research','market_command','economic_building')
    economy=[]
    for p in players:
        for label in eco_kinds:
            values=[0]*minutes
            for e in events:
                if e.get('player_id')!=p['id']: continue
                match_kind=(label=='villager_queue' and e.get('kind')=='queue_command' and e.get('unit')=='Villager'
                  or label=='farm_placement' and e.get('action')=='BUILD' and e.get('building')=='Farm' and e.get('counted_as_new_placement',True)
                  or label=='economic_research' and e.get('action')=='RESEARCH' and e.get('technology') in {'Double-Bit Axe','Horse Collar','Wheelbarrow','Bow Saw','Gold Mining','Stone Mining','Town Watch','Town Patrol','Loom'}
                  or label=='market_command' and e.get('action') in {'BUY','SELL'}
                  or label=='economic_building' and e.get('action')=='BUILD' and e.get('building') in {'Mill','Lumber Camp','Mining Camp','Market','Town Center','Blacksmith'})
                if match_kind: values[min(minutes-1,int(e['time_seconds']//bin_seconds))]+=1
            if any(values): economy.append({"player":p['name'],"kind":label,"commands_per_minute":values})
    return {"bin_seconds":bin_seconds,"unit":"commands per minute","caveat":"Queue commands count once per recorded command; requested queue amount is separate. No unit completion or resource balance is inferred.","production":production,"economy":economy}

def findings(report: dict) -> list[dict]:
    players=report['players']; events=report['events']; out=[]; events_by_id={e['id']:e for e in events}
    for p in players:
        pe=[e for e in events if e.get('player_id')==p['id']]
        def first(pred): return next((e for e in pe if pred(e)),None)
        ages={e.get('technology'):e for e in pe if e['category']=='age'}
        castle=first(lambda e:e['action']=='RESEARCH' and e.get('technology')=='Castle Age')
        castle_age=ages.get('Castle Age')
        stable=first(lambda e:e['action']=='BUILD' and 'Stable'==e.get('building'))
        scout=first(lambda e:e.get('kind')=='queue_command' and e.get('unit')=='Scout Cavalry')
        knight=first(lambda e:e.get('kind')=='queue_command' and e.get('unit')=='Knight')
        siege=first(lambda e:e.get('kind')=='queue_command' and e.get('unit') in ('Mangonel','Scorpion','Battering Ram','Siege Tower','Trebuchet'))
        if castle and castle_age:
            out.append({"id":f"castle-transition-{p['id']}","kind":"age_transition","player":p['name'],"time_seconds":castle['time_seconds'],"end_time_seconds":castle_age['time_seconds'],
              "title":"Castle research → age arrival","summary":f"Castle research at {castle['time']} → Castle Age {castle_age['time']} ({(castle_age['time_seconds']-castle['time_seconds'])/60:.1f} min).",
              "event_ids":[castle['id'],castle_age['id']],"confidence":"high","limitations":"Research command and parser uptime milestone; not a resource ledger."})
        if p['civilization']=='Franks' and castle and ages.get('Feudal Age'):
            delay=castle['time_seconds']-ages['Feudal Age']['time_seconds']
            if delay>8*60:
                scout_orders=[e for e in pe if e.get('kind')=='queue_command' and e.get('unit')=='Scout Cavalry' and e['time_seconds']<castle['time_seconds']]
                farms=[e for e in pe if e['action']=='BUILD' and e.get('building')=='Farm' and e['time_seconds']<castle['time_seconds'] and e.get('counted_as_new_placement',True)]
                supports=[ages['Feudal Age'],castle]+scout_orders+farms[-6:]
                out.append({"id":f"long-feudal-{p['id']}","kind":"coaching_hypothesis","player":p['name'],"time_seconds":ages['Feudal Age']['time_seconds'],"end_time_seconds":castle['time_seconds'],
                  "title":"Long Feudal interval before Castle click","summary":f"Feudal arrival {ages['Feudal Age']['time']} and Castle research {castle['time']} are {delay/60:.1f} min apart. Recorded Scout queues: {len(scout_orders)}; farm placements: {len(farms)}.",
                  "event_ids":[e['id'] for e in supports],"confidence":"medium","limitations":"Commands do not prove completion, resource affordability, or that spending caused the delay; review opponent pressure and the minimap."})
        if p['civilization']=='Franks' and stable:
            market=first(lambda e:e['action']=='BUILD' and e.get('building')=='Market')
            if market and castle:
                trades=[e for e in pe if e['action'] in ('BUY','SELL') and market['time_seconds']<=e['time_seconds']<castle['time_seconds']]
                if not trades:
                    out.append({"id":f"market-commands-{p['id']}","kind":"event_absence_observation","player":p['name'],"time_seconds":market['time_seconds'],"end_time_seconds":castle['time_seconds'],
                      "title":"No recorded market Buy/Sell commands before Castle click","summary":f"Market placement command at {market['time']}; no explicit Buy/Sell commands recorded before Castle research at {castle['time']}.",
                      "event_ids":[market['id'],castle['id']],"confidence":"high","limitations":"This is only an absence of parsed Buy/Sell commands in that interval; it does not establish market completion, automatic trades, or resource balances."})
        tc_activity=next((row for row in report.get('tc_queue_activity',[]) if row['player_id']==p['id']),None)
        if p['civilization']=='Franks' and tc_activity and tc_activity['long_command_gaps']:
            early=[g for g in tc_activity['long_command_gaps'] if events_by_id[g['to_event_id']]['time_seconds']<=25*60]
            largest=sorted(early or tc_activity['long_command_gaps'],key=lambda gap:gap['gap_seconds'],reverse=True)[:3]
            gap_summary='; '.join(f"{g['from_time']}–{g['to_time']} ({g['gap_seconds']:.0f}s)" for g in largest)
            out.append({"id":f"tc-queue-gaps-{p['id']}","kind":"tc_queue_gap_proxy","player":p['name'],"time_seconds":min(events_by_id[g['from_event_id']]['time_seconds'] for g in largest),
              "title":"Long gaps between recorded TC Villager-queue commands (review proxy)","summary":f"Largest command gaps at the initial TC: {gap_summary}.",
              "event_ids":list(dict.fromkeys(eid for g in largest for eid in (g['from_event_id'],g['to_event_id']))),
              "coordinates":[{"position":g['position'],"from_time":g['from_time'],"to_time":g['to_time'],"gap_seconds":g['gap_seconds'],"from_event_id":g['from_event_id'],"to_event_id":g['to_event_id']} for g in largest],
              "confidence":"low","limitations":"These are queue-command gaps, not measured TC idle time. Existing queue contents, initial queue state, cancellation outcomes, production completion, and additional TC instance IDs are not fully observable; use the timestamps as review prompts only."})
        if p['civilization']=='Franks' and castle_age and knight:
            gap=knight['time_seconds']-castle_age['time_seconds']
            if gap>90:
                out.append({"id":f"knight-production-gap-{p['id']}","kind":"coaching_hypothesis","player":p['name'],"time_seconds":castle_age['time_seconds'],"end_time_seconds":knight['time_seconds'],
                  "title":"Delay from Castle arrival to first Knight queue","summary":f"Castle Age reached {castle_age['time']}; first Knight queue command at {knight['time']} ({gap/60:.1f} min later).",
                  "event_ids":[castle_age['id'],knight['id']],"confidence":"medium","limitations":"Queue command is not verified production; investigate spending, stable availability, and pressure before inferring cause."})
        if stable and scout:
            out.append({"id":f"opening-milestones-{p['id']}","kind":"opening_milestones","player":p['name'],"time_seconds":stable['time_seconds'],"title":"Scout opening milestones",
             "summary":f"Stable command {stable['time']}; first Scout queue command {scout['time']} ({scout['time_seconds']-stable['time_seconds']:.0f}s later).",
             "event_ids":[stable['id'],scout['id']],"confidence":"high","limitations":"These are placement/queue commands, not verified building or unit completion."})
    # Relative base-to-Castle distance is a map-based cue, not proof of the builder's intent or completion.
    for e in events:
        if e.get('action')!='BUILD' or e.get('building')!='Castle' or not e.get('position'): continue
        builder=next((p for p in players if p['id']==e.get('player_id')),None)
        opponent=next((p for p in players if p['id']!=e.get('player_id')),None)
        if builder and opponent and builder.get('base') and opponent.get('base'):
            own_d=_distance(e['position'],builder['base']); enemy_d=_distance(e['position'],opponent['base'])
            if enemy_d<own_d:
                out.append({"id":f"forward-castle-{e['id']}","kind":"spatial_coaching_hypothesis","player":builder['name'],"time_seconds":e['time_seconds'],"title":"Castle placement command is closer to opponent's start",
                  "summary":f"Castle command at ({e['position']['x']:.1f}, {e['position']['y']:.1f}); {enemy_d:.1f} tiles from {opponent['name']}'s start vs {own_d:.1f} from builder's start.",
                  "event_ids":[e['id']],"confidence":"medium","limitations":"Euclidean distance from initial player positions; command does not confirm placement completion or strategic intent."})
    return out

def detect_pressure(report: dict, target_name: str | None=None, time_window: tuple[float,float] | None=(20*60+40,22*60+10)) -> list[dict]:
    """MVP detector scoped to the requested early pressure window; pass None to scan the full match."""
    players=report['players']; events=report['events']
    target=next((p for p in players if p['name']==target_name),None) if target_name else next((p for p in players if p['civilization']=='Franks'),None)
    if not target or not target.get('base'): return []
    radius=18.0; seed_radius=12.0; base=target['base']; enemy_ids={p['id'] for p in players if p['id']!=target['id']}
    tactical={'MOVE','ORDER','PATROL','DE_ATTACK_MOVE','ATTACK_GROUND','SPECIAL'}
    candidates=[]; seeds=[]
    for e in events:
        if time_window and not time_window[0]<=e['time_seconds']<=time_window[1]: continue
        if e.get('player_id') not in enemy_ids or e['action'] not in tactical or not e.get('position'): continue
        pos=e['position']; d=_distance(base,pos)
        ids=sorted(set(i for i in e.get('object_ids',[]) if isinstance(i,int)))
        if d<=radius and len(ids)>=3:
            candidate={**e,'distance_to_target_base':round(d,2),'group_ids':ids}
            candidates.append(candidate)
            # Generic ORDER is only a pressure seed, never proof of an attack. MOVE alone does not establish intent.
            if d<=seed_radius and e['action'] in {'ORDER','PATROL','DE_ATTACK_MOVE','ATTACK_GROUND'}:
                seeds.append(candidate)
    # Group incident seeds by overlapping selected actor IDs and a short time gap.
    clusters=[]
    for e in sorted(seeds,key=lambda q:q['time_seconds']):
        best=None
        for c in reversed(clusters[-12:]):
            if e['time_seconds']-c['end_time_seconds']>150: break
            if e['time_seconds']-c['start_time_seconds']>120: continue
            if e['player_id']==c['player_id'] and len(set(e['group_ids']) & {unit_id for group in c['groups'] for unit_id in group})>=max(2,min(3,len(e['group_ids']))):
                best=c;break
        if best:
            best['end_time_seconds']=e['time_seconds'];best['seed_ids'].append(e['id']);best['groups'].append(e['group_ids'])
        else:
            clusters.append({'player_id':e['player_id'],'player':e['player'],'start_time_seconds':e['time_seconds'],'end_time_seconds':e['time_seconds'],
              'seed_ids':[e['id']],'groups':[e['group_ids']]})
    # Add selected movement/order commands from those same groups around each seed (destinations only; no path simulation).
    for c in clusters:
        actor_ids={unit_id for group in c['groups'] for unit_id in group}
        related=[]
        for e in candidates:
            overlap=len(set(e['group_ids']) & actor_ids)
            if e['player_id']==c['player_id'] and c['start_time_seconds']-150<=e['time_seconds']<=c['end_time_seconds']+30 and overlap>=max(2,min(3,len(e['group_ids']))):
                related.append(e)
        c['event_ids']=list(dict.fromkeys(e['id'] for e in related))
        c['positions']=[e['position'] for e in related]
        c['actions']={e['action'] for e in related}
        c['start_time_seconds']=min([c['start_time_seconds']]+[e['time_seconds'] for e in related])
        c['end_time_seconds']=max([c['end_time_seconds']]+[e['time_seconds'] for e in related])
        c['related_events']=related
    incidents=[]
    for i,c in enumerate(clusters):
        ids=sorted(set(v for group in c['groups'] for v in group));
        if len(c['seed_ids'])<1 or len(c['event_ids'])<3 or len(ids)<3: continue
        incident_id=f"pressure-{c['player_id']}-{i}"
        # Defender reactions are explicitly identifiable orders/build commands, not assumed unit outcomes.
        responses=[]
        for e in events:
            if e.get('player_id')!=target['id'] or not c['start_time_seconds']-30<=e['time_seconds']<=min(c['end_time_seconds']+120,(time_window[1]+30) if time_window else float('inf')): continue
            if e['action']=='SPECIAL' and (e.get('order')=='Garrison' or e.get('kind')=='order_command'):
                if e.get('order')=='Garrison': responses.append({"event_id":e['id'],"time":e['time'],"response":"Garrison command issued"})
            if e['action']=='BUILD' and e.get('building') in ('Watch Tower','Guard Tower','Keep','Castle') and e.get('position') and _distance(base,e['position'])<22:
                responses.append({"event_id":e['id'],"time":e['time'],"response":f"{e['building']} placement command near base"})
        evidence=[next(e for e in events if e['id']==eid) for eid in c['event_ids']]
        near_orders=[e for e in evidence if e['action']=='ORDER']
        confidence='medium' if near_orders else 'low'
        # Concise, reviewable sample: one earliest generic order per target ID, preserving selected actor IDs and coordinates.
        key_orders=[]; seen_targets=set()
        for e in sorted((e for e in c['related_events'] if e['action']=='ORDER'),key=lambda e:e['time_seconds']):
            target_id=e.get('target_id'); key=('target',target_id) if target_id is not None else ('position',round(e['position']['x'],1),round(e['position']['y'],1))
            if key in seen_targets: continue
            seen_targets.add(key)
            key_orders.append({"event_id":e['id'],"time":e['time'],"target_id":target_id,"position":e['position'],
              "selected_object_ids":e['group_ids'],"distance_to_target_base":e['distance_to_target_base'],"semantics":"generic ORDER target; target type unresolved"})
            if len(key_orders)>=8: break
        incidents.append({"id":incident_id,"target_player":target['name'],"enemy_player":c['player'],"key_orders":key_orders,
          "start_time_seconds":round(c['start_time_seconds'],3),"end_time_seconds":round(c['end_time_seconds'],3),
          "start_time":clock(c['start_time_seconds']),"end_time":clock(c['end_time_seconds']),"group_object_ids":ids,
          "event_ids":c['event_ids'],"actions":sorted(c['actions']),"destinations":c['positions'],"defender_responses":responses,
          "title":"Enemy group orders near base","summary":f"{len(ids)} selected object IDs issued {len(c['event_ids'])} movement/order commands within {radius:g} tiles of {target['name']}'s starting TC.",
          "confidence":confidence,"analysis_window":{"start":clock(time_window[0]),"end":clock(time_window[1])} if time_window else None,"limitations":["Object IDs are selected actors, not reliably resolved unit types.","ORDER/Interact may mean attack, gather, repair, or another order; this pattern suggests pressure but does not prove attacks or damage.","Commands give requested destinations, not actual unit paths/positions, wall breaches, deaths, or whether the player noticed."]})
    return incidents

def build_raw_store(report: dict) -> dict:
    """Raw parsed command payloads are kept separately from the compact viewer model."""
    return {"schema_version":SCHEMA_VERSION,"match_id":report['match_id'],"source_file":report['source_file'],"events":report['raw_events']}

def persist_report(report: dict, folder: Path, include_raw: bool=True) -> tuple[Path,Path]:
    folder.mkdir(parents=True,exist_ok=True)
    normalized=folder/f"{report['match_id']}.json"; raw=folder/f"{report['match_id']}.raw.json"
    compact={k:v for k,v in report.items() if k!='raw_events'}
    def atomic_json(destination, value):
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=folder, delete=False) as handle:
                temp = Path(handle.name)
                json.dump(value, handle, ensure_ascii=False, separators=(',', ':'))
            os.replace(temp, destination)
        finally:
            if temp and temp.exists(): temp.unlink()
    atomic_json(normalized, compact)
    if include_raw:
        atomic_json(raw, build_raw_store(report))
    return normalized,raw

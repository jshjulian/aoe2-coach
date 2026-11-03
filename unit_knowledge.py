"""Hash-checked base mechanics and authored composition options, never effective state."""
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from gameplay_knowledge import _catalog
from knowledge_adapter import ROOT, _signature, AVAILABLE_STATUSES

PACK_PATH=ROOT/'knowledge/unit-mechanics.v1.json'
LOCK_PATH=ROOT/'knowledge/situational-catalog.lock.json'
VERSION=1


def compile_pack(p):
    if not isinstance(p,dict) or type(p.get('schema_version')) is not int or p['schema_version']!=1 or p.get('pack_id')!='unit-mechanics':raise ValueError('Unsupported unit mechanics pack.')
    if type(p.get('declared_update')) is not int or p['declared_update']<=0 or not isinstance(p.get('source_commit'),str) or len(p['source_commit'])!=40 or any(c not in '0123456789abcdef' for c in p['source_commit']):raise ValueError('Unbound mechanics source.')
    roles=p.get('roles');units=p.get('units');options=p.get('compositions')
    if not isinstance(roles,dict) or not 1<=len(roles)<=12 or any(not isinstance(k,str) or not isinstance(v,str) or not 0<len(v)<=120 for k,v in roles.items()):raise ValueError('Invalid roles.')
    if not isinstance(units,list) or not 1<=len(units)<=40 or any(not isinstance(u,dict) or type(u.get('id')) is not int or u['id']<=0 for u in units) or len({u['id'] for u in units})!=len(units):raise ValueError('Ambiguous unit registry.')
    for u in units:
        if not isinstance(u.get('name'),str) or not 0<len(u['name'])<=160 or u.get('role') not in roles or 'damage_class' not in u or not (type(u.get('damage_class')) is int and u['damage_class'] in (3,4) and u.get('delivery') in ('melee','ranged') or u['id']==125 and u.get('damage_class') is None and u.get('delivery')=='conversion' and u.get('role')=='conversion'):raise ValueError('Unreviewed mechanics mapping.')
        if 'mechanic' in u and (not isinstance(u['mechanic'],str) or not 0<len(u['mechanic'])<=1000):raise ValueError('Invalid mechanic prose.')
        if 'jobs' in u and (not isinstance(u['jobs'],list) or not 1<=len(u['jobs'])<=6 or any(not isinstance(s,str) or not 0<len(s)<=160 for s in u['jobs'])):raise ValueError('Invalid jobs.')
    ids={u['id'] for u in units}
    if not isinstance(options,list) or not 1<=len(options)<=12 or len({o['id'] for o in options})!=len(options):raise ValueError('Invalid composition registry.')
    for o in options:
        if o.get('trigger_role') not in roles or not isinstance(o.get('required_units'),list) or not 1<=len(o['required_units'])<=6 or any(type(x) is not int or x not in ids for x in o['required_units']) or len(set(o['required_units']))!=len(o['required_units']):raise ValueError('Unresolved composition units.')
        for k in ['id','title','conditions','limitations']:
            if not isinstance(o.get(k),str) or not 0<len(o[k])<=1200:raise ValueError('Unconditioned composition.')
        if not isinstance(o.get('requires'),list) or not 1<=len(o['requires'])<=8 or any(not isinstance(s,str) or not 0<len(s)<=300 for s in o['requires']):raise ValueError('Missing feasibility requirements.')
    if not isinstance(p.get('cue'),str) or not 0<len(p['cue'])<=600 or not isinstance(p.get('transition_questions'),list) or len(p['transition_questions'])!=3 or any(not isinstance(s,str) or not 0<len(s)<=400 for s in p['transition_questions']):raise ValueError('Missing transition boundaries.')
    return p


@lru_cache(maxsize=2)
def _load(signature):
    if PACK_PATH.stat().st_size>131072:raise ValueError('Oversized mechanics pack.')
    raw=PACK_PATH.read_bytes();p=compile_pack(json.loads(raw))
    if _signature(PACK_PATH)!=signature:raise ValueError('Mechanics pack changed during read.')
    return p,hashlib.sha256(raw).hexdigest()


def local_pack():return _load(_signature(PACK_PATH))
def _number(v):return v if type(v) in (int,float) and math.isfinite(v) and 0<=v<=10000 else None

def _classes(raw):
    if not isinstance(raw,list) or len(raw)>128:return None
    if any(not isinstance(x,dict) or type(x.get('Class')) is not int or not 0<=x['Class']<=1024 or type(x.get('Amount')) not in (int,float) or not math.isfinite(x['Amount']) or abs(x['Amount'])>10000 for x in raw):return None
    if len({x['Class'] for x in raw})!=len(raw):return None
    return [dict(armor_class=x['Class'],amount=x['Amount']) for x in raw]


def reference(report,player,pack):
    out=dict(status='unavailable',profiles=[],compositions=[],effective_state_established=False,standard_rules_verified=False,reason='Pinned local mechanics snapshot unavailable; no stats or availability invented.')
    try:
        lock_text=LOCK_PATH.read_text();lock=json.loads(lock_text)
        if lock['repository']!='https://github.com/SiegeEngineers/aoe2techtree' or lock['commit']!=pack['source_commit'] or lock['declared_update']!=pack['declared_update']:raise ValueError('Mechanics/catalog pin mismatch.')
        root=(ROOT/'data/research/aoe2techtree'/lock['commit']).resolve();paths=[LOCK_PATH]
        for f in lock['files']:
            path=(root/f['path']).resolve()
            if not path.is_relative_to(root) or path==root:raise ValueError('Source path escape.')
            paths.append(path)
        snapshot=_catalog(str(root),lock_text,tuple((str(p),_signature(p)) for p in paths))
        data=snapshot['data.json'];tree_path=lock['civilization_trees'].get(player['civilization'])
        if not tree_path or player['civilization'] not in data['civs']:raise ValueError('No exact own-civilization tree.')
        tree=snapshot[tree_path];own_nodes={n['node_id']:n for n in tree['units_techs'] if n['use_type']=='Unit'}
        # Validate identity against every pinned tree, without assigning one civ's
        # production, age or availability to another.
        names={}
        for path,value in snapshot.items():
            if path.startswith('trees/'):
                for n in value['units_techs']:
                    if n['use_type']=='Unit':names.setdefault(n['node_id'],set()).add(n['name'])
        source=f"{lock['repository']}/blob/{lock['commit']}/data/data.json"
        for u in pack['units']:
            raw=data['data']['Unit'].get(str(u['id']))
            if not isinstance(raw,dict) or names.get(u['id'])!={u['name']}:raise ValueError('Exact unit name/ID conflict.')
            attacks=_classes(raw.get('Attacks'));armors=_classes(raw.get('Armours'));range=_number(raw.get('Range'))
            primary=next((a for a in attacks or [] if a['armor_class']==u['damage_class'] and a['amount']>0),None)
            conversion=u['delivery']=='conversion'
            if attacks is None or armors is None or range is None or (conversion and (raw.get('Attack')!=0 or attacks or range<=0)) or (not conversion and (not primary or (range>0)!=(u['delivery']=='ranged'))):raise ValueError('Unverified damage/delivery or armor classes.')
            own=own_nodes.get(u['id']);available=u['id'] in data['civs'][player['civilization']]['Unit']
            if available!=(bool(own) and own['node_status'] in AVAILABLE_STATUSES):raise ValueError('Own availability conflict.')
            if available and (type(own.get('age_id')) is not int or not 1<=own['age_id']<=4 or type(own.get('building_id')) is not int or own['building_id']<=0):raise ValueError('Unknown own availability prerequisites.')
            out['profiles'].append(dict(unit_id=u['id'],name=u['name'],role=u['role'],role_label=pack['roles'][u['role']],jobs=u.get('jobs',[pack['roles'][u['role']]]),
                damage_type='none' if conversion else 'melee' if u['damage_class']==4 else 'pierce',delivery=u['delivery'],primary_damage_class=u['damage_class'],
                base_speed=_number(raw.get('Speed')),base_range=range,base_min_range=_number(raw.get('MinRange')),base_melee_armor=_number(raw.get('MeleeArmor')),base_pierce_armor=_number(raw.get('PierceArmor')),base_attack=_number(raw.get('Attack')),base_reload_seconds=_number(raw.get('ReloadTime')),base_attack_delay_seconds=_number(raw.get('AttackDelaySeconds')),
                attacks=attacks,armor_classes=armors,mechanic=u.get('mechanic','Civ bonuses, upgrades, numbers and positioning change the effective unit. No completion or fight result is inferred.'),
                own_catalog_available=available,own_minimum_age=own['age_id'] if own else None,own_production_building_id=own['building_id'] if own else None,
                source_ref=source+'#Unit-'+str(u['id']),availability_source_ref=f"{lock['repository']}/blob/{lock['commit']}/data/{tree_path}",observed_effective_stats=False))
        by_id={p['unit_id']:p for p in out['profiles']}
        out['compositions']=[{**o,'own_catalog_available':all(by_id[id]['own_catalog_available'] for id in o['required_units']),'minimum_reference_age':max(by_id[id]['own_minimum_age'] for id in o['required_units']) if all(type(by_id[id]['own_minimum_age']) is int and 1<=by_id[id]['own_minimum_age']<=4 for id in o['required_units']) else None,'availability_establishes_readiness':False} for o in pack['compositions']]
        build=(report.get('replay_provenance') or {}).get('build_version')
        out.update(status='reference_only' if type(build) is int and build==pack['declared_update'] else 'patch_mismatch_or_unknown',reason='Base reference only. Speed/armor/damage are not effective match stats; availability is not completion, resources, safety or a feasible counter.',source=dict(commit=lock['commit'],declared_update=lock['declared_update'],lock_sha256=hashlib.sha256(lock_text.encode()).hexdigest()))
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        out.update(status='unavailable',profiles=[],compositions=[])
    return out

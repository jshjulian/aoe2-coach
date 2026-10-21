"""Versioned relational knowledge; sourced base facts remain distinct from strategy."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from gameplay_knowledge import _catalog
from knowledge_adapter import ROOT, _signature, AVAILABLE_STATUSES
from tools.audit_techtree import plain_text

PACK = ROOT/'knowledge/situational.v1.json'
LOCK_PATH=ROOT/'knowledge/situational-catalog.lock.json'
ADAPTER_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def compile_pack(p):
    if not isinstance(p,dict) or type(p.get('schema_version')) is not int or p.get('schema_version') != 1 or type(p.get('pack_version')) is not int or p.get('pack_version') != 1 or p.get('pack_id') != 'situational-composition':
        raise ValueError('Unsupported relational knowledge.')
    if p.get('edition')!='DE' or type(p.get('dataset_id')) is not int or p['dataset_id']!=100 or type(p.get('declared_update')) is not int or p['declared_update']<=0 or not isinstance(p.get('source_commit'),str) or len(p['source_commit'])!=40 or any(c not in '0123456789abcdef' for c in p['source_commit']) or not isinstance(p.get('authorship'),str):raise ValueError('Missing patch/source scope.')
    aliases=p.get('civilization_aliases')
    if not isinstance(aliases,dict) or len(aliases)>16 or any(not isinstance(k,str) or not isinstance(v,str) or not 1<=len(k)<=64 or not 1<=len(v)<=64 for k,v in aliases.items()):raise ValueError('Invalid reviewed civilization aliases.')
    roles = p['roles']; ids = {r['id'] for r in roles}
    if ids != {'infantry','spear','cavalry','archer','skirmisher'} or len(roles) != 5:
        raise ValueError('Missing/duplicate roles.')
    names=set(); units=set()
    for r in roles:
        if not 1 <= len(r['names']) == len(r['unit_ids']) <= 8 or not set(r['preferred_against']) <= ids:
            raise ValueError('Invalid role references.')
        for name, id in zip(r['names'],r['unit_ids']):
            if not isinstance(name,str) or type(id) is not int or id <= 0 or name in names or id in units:
                raise ValueError('Ambiguous aliases.')
            names.add(name);units.add(id)
        if any(not isinstance(r.get(k),str) or not 1 <= len(r[k]) <= 1200 for k in ('name','purpose','exceptions')):
            raise ValueError('Unqualified strategy.')
    if not 1 <= len(p['research_roles']) <= 8 or any(r['role'] not in ids or type(r['technology_id']) is not int for r in p['research_roles']):
        raise ValueError('Unknown research role.')
    for k in ('practice','practice_title','position_alternative','position_exceptions'):
        if not isinstance(p.get(k),str) or not 1 <= len(p[k]) <= (400 if k=='practice' else 1200):raise ValueError('Invalid conditional practice.')
    return p


@lru_cache(maxsize=2)
def _load(signature):
    if PACK.stat().st_size > 65536:raise ValueError('Oversized knowledge.')
    raw=PACK.read_bytes();p=compile_pack(json.loads(raw))
    if _signature(PACK)!=signature:raise ValueError('Knowledge changed during read.')
    return p,hashlib.sha256(raw).hexdigest()


def local_pack():return _load(_signature(PACK))


def catalog(report,player,p):
    """Verified complete local snapshot. No fetch/fallback, no availability => readiness."""
    lock_text=LOCK_PATH.read_text();lock=json.loads(lock_text)
    if lock.get('repository')!='https://github.com/SiegeEngineers/aoe2techtree' or p['source_commit']!=lock['commit'] or p['declared_update']!=lock['declared_update']:
        raise ValueError('Knowledge/catalog pin mismatch.')
    provenance=report.get('replay_provenance') or {}
    if provenance.get('edition')!='DE' or provenance.get('build_version')!=p['declared_update'] or provenance.get('dataset_id')!=p['dataset_id']:
        raise ValueError('Unsupported/unknown edition, patch or dataset.')
    if provenance.get('provenance_version')!=2 or type(provenance.get('game_type_id')) is not int or provenance['game_type_id']!=0 or any(provenance.get(k) is not False for k in ('cheats','all_technologies','metadata_cheats','de_cheats')):
        raise ValueError('Random Map with explicit cheats/all-technologies off and current provenance required.')
    if provenance.get('mod_compatibility')=='incompatible' or provenance.get('reported_mod') not in (None,'') or provenance.get('rms_mod_id') is not None and (type(provenance['rms_mod_id']) is not int or provenance['rms_mod_id']!=0):
        raise ValueError('Conflicting match rules.')
    directory=ROOT/'data/research/aoe2techtree'/lock['commit']; root=directory.resolve();paths=[LOCK_PATH]
    for f in lock['files']:
        path=(root/f['path']).resolve()
        if not path.is_relative_to(root):raise ValueError('Catalog path escape.')
        paths.append(path)
    snapshot=_catalog(str(root),lock_text,tuple((str(path),_signature(path)) for path in paths))
    data=snapshot['data.json'];canonical=p.get('civilization_aliases',{}).get(player.get('civilization'),player.get('civilization'));civ=data['civs'].get(canonical)
    if not civ:raise ValueError('Unknown exact civilization.')
    tree_path=lock['civilization_trees'][canonical]
    tree=snapshot[tree_path]
    nodes={(n['use_type'],n['node_id']):n for n in tree['buildings']+tree['units_techs']}
    entities=[]
    for role in p['roles']:
        for name,id in zip(role['names'],role['unit_ids']):
            n=nodes.get(('Unit',id));raw=data['data']['Unit'].get(str(id))
            if not raw or n and n['name']!=name:raise ValueError('Catalog alias mismatch.')
            available=id in civ['Unit']
            if available and not n or n and available!=(n['node_status'] in AVAILABLE_STATUSES):raise ValueError('Catalog availability conflict.')
            building=nodes.get(('Building',n['building_id'])) if n else None
            entities.append(dict(kind='Unit',entity_id=id,name=name,role=role['id'],catalog_available=available,
                minimum_age=n['age_id'] if n else None,building_id=n['building_id'] if n else None,building_name=building['name'] if building else None,
                building_catalog_available=bool(building and n and n['building_id'] in civ['Building']),
                base_cost=raw.get('Cost'),base_train_seconds=raw.get('TrainTime'),observed_in_match=False,
                source_ref=f"{lock['repository']}/blob/{lock['commit']}/data/data.json",
                availability_source_ref=f"{lock['repository']}/blob/{lock['commit']}/data/{tree_path}"))
    return dict(commit=lock['commit'],lock_sha256=hashlib.sha256(lock_text.encode()).hexdigest(),declared_update=lock['declared_update'],entities=entities,
        civilization=player['civilization'],canonical_catalog_civilization=canonical,civilization_description=plain_text(snapshot['strings.en.json'].get(str(civ['help_string_id']),'')),
        status='pinned_catalog_not_effective_state',standard_rules_verified=False,
        qualification='Matching patch and catalog do not verify standard rules, bonuses in effect, affordability, completed buildings/upgrades or fielded armies.')

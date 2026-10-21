"""Reusable conditional concepts plus independently gated reference data; never live state."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from knowledge_adapter import ROOT, LOCK_PATH, _signature
from tools.audit_techtree import load_snapshot,plain_text
PACK_PATH=ROOT/'knowledge/gameplay.v1.json'
PACK_V2_PATH=ROOT/'knowledge/gameplay.v2.json'


def compile_pack(value):
    if not isinstance(value,dict) or type(value.get('schema_version')) is not int or type(value.get('pack_version')) is not int or value.get('schema_version') not in (1,2) or value.get('pack_version')!=value.get('schema_version') or value.get('pack_id')!='gameplay-concepts':raise ValueError('Unsupported gameplay pack.')
    concepts=value.get('concepts',[]);roles=value.get('roles',[])
    if not 1<=len(concepts)<=32 or len({x['id'] for x in concepts})!=len(concepts):raise ValueError('Duplicate/missing concepts.')
    for c in concepts:
        if c['status'] not in ('model_only','implemented_checkpoint') or not isinstance(c.get('principle'),str):raise ValueError('Invalid concept.')
    active=([next(c for c in concepts if c['id']=='siege.recommitment')] if value['schema_version']==1 else concepts)
    for c in active:
        if c['status']!='implemented_checkpoint' or not c.get('options') or not c.get('required_state_for_verdict'):raise ValueError('Missing conditions and uncertainty.')
        for key in ('practice','question','hypothesis','exception','principle'):
            if not isinstance(c.get(key),str) or not 1<=len(c[key])<=1200:raise ValueError('Invalid strategic prose.')
        for option in c['options']:
            if any(not isinstance(option.get(k),str) or not option[k] for k in ('if','then','not_claimed')):raise ValueError('Unconditioned option.')
    if value['schema_version']==2:
        expected={'engagement_decision','military_sustainability','production_investment','map_control','walling','upgrade_transition'}
        if {c.get('topic') for c in concepts}!=expected or len(concepts)!=len(expected):raise ValueError('Missing or duplicated v2 topics.')
        for c in concepts:
            if any(not isinstance(c.get(k),str) or not 1<=len(c[k])<=600 for k in ('title','summary')):raise ValueError('Invalid checkpoint presentation.')
            if not isinstance(c['options'],list) or not 2<=len(c['options'])<=4 or not isinstance(c['required_state_for_verdict'],list) or not 1<=len(c['required_state_for_verdict'])<=12:raise ValueError('Invalid conditional scope.')
        families=value.get('families')
        if not isinstance(families,list) or not 1<=len(families)<=32 or len({f['id'] for f in families})!=len(families):raise ValueError('Invalid role families.')
        for f in families:
            for k in ('units','upgrades'):
                if not isinstance(f.get(k),list) or len(f[k])>96 or any(not isinstance(x,str) or not 1<=len(x)<=100 for x in f[k]):raise ValueError('Invalid family aliases.')
        aliases=value.get('additional_military_aliases',[])
        if not isinstance(aliases,list) or len(aliases)>256 or any(not isinstance(x,str) or not x for x in aliases):raise ValueError('Invalid military aliases.')
    if len({(r['kind'],r['entity_id']) for r in roles})!=len(roles):raise ValueError('Duplicate namespaced role.')
    if any(r['kind'] not in ('Unit','Tech','Building') or type(r['entity_id']) is not int for r in roles):raise ValueError('Invalid namespace.')
    refs={(r['kind'],r['entity_id']) for r in roles}
    for interaction in value.get('interactions',[]):
        if interaction.get('concept_id') not in {c['id'] for c in concepts} or not interaction.get('conditions') or not interaction.get('provenance'):raise ValueError('Unconditioned interaction.')
        if any((interaction[k]['kind'],interaction[k]['entity_id']) not in refs for k in ('from','to')):raise ValueError('Unresolved interaction entity.')
    return value


@lru_cache(maxsize=2)
def _pack(path,signature):
    p=Path(path)
    if p.stat().st_size>128*1024:raise ValueError('Oversized gameplay pack.')
    raw=p.read_bytes();value=compile_pack(json.loads(raw))
    if _signature(p)!=signature:raise ValueError('Gameplay pack changed during read.')
    return value,hashlib.sha256(raw).hexdigest()


def local_pack(version=1):
    path=PACK_PATH if version==1 else PACK_V2_PATH
    return _pack(str(path),_signature(path))


@lru_cache(maxsize=2)
def _catalog(directory,lock_text,signatures):
    lock=json.loads(lock_text);snapshot=load_snapshot(Path(directory),lock)
    if tuple(_signature(Path(p)) for p,_ in signatures)!=tuple(s for _,s in signatures):raise ValueError('Reference changed during read.')
    return snapshot


def reference(report,player,pack):
    """No network/fallback downloads. All facts explicitly remain base reference only."""
    out=dict(status='unavailable',source=None,civilization=player['civilization'],entities=[],civilization_description=None,
             effective_state_established=False,reason='No verified local catalog is available. Generic conditional guidance is separate.')
    try:
        lock_text=LOCK_PATH.read_text();lock=json.loads(lock_text);commit=lock['commit']
        if len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):raise ValueError('Invalid commit.')
        directory=ROOT/'data/research/aoe2techtree'/commit;root=directory.resolve();paths=[LOCK_PATH]
        for f in lock['files']:
            p=(root/f['path']).resolve()
            if not p.is_relative_to(root) or p==root:raise ValueError('Source escape.')
            paths.append(p)
        snapshot=_catalog(str(root),lock_text,tuple((str(p),_signature(p)) for p in paths))
        data=snapshot['data.json'];civ=data['civs'].get(player['civilization'])
        provenance=report.get('replay_provenance') or {};build=provenance.get('build_version')
        out['source']={k:lock[k] for k in ('repository','commit','declared_update')}
        out['status']='reference_only' if type(build) is int and build==lock['declared_update'] else 'patch_mismatch_or_unknown'
        out['reason']='Base catalog only: matching patch does not verify mode/mods, effective bonuses, affordability, completed research or production. No live stats or feasible counter is inferred.'
        if not civ:
            out.update(status='unsupported_civilization',reason='No exact civilization entry in the pinned catalog; generic conditional advice does not assume its bonuses or options.')
            return out
        out['civilization_description']=plain_text(snapshot['strings.en.json'].get(str(civ['help_string_id']),''))
        names={}
        for path,tree in snapshot.items():
            if path.startswith('trees/'):
                for node in tree['buildings']+tree['units_techs']:
                    names[(node['use_type'],node['node_id'])]=node['name']
        for role in pack['roles']:
            kind,id=role['kind'],role['entity_id'];raw=data['data'][kind].get(str(id))
            if raw is None:continue
            # Raw LanguageNameId is not a direct key in this web-localization subset.
            # Use exact hash-checked tree names; do not invent a numeric offset.
            name=plain_text(names.get((kind,id),raw['internal_name']))
            out['entities'].append(dict(kind=kind,entity_id=id,name=name,role=role['role'],catalog_available=id in civ[kind],
                base_cost=raw.get('Cost'),base_train_seconds=raw.get('TrainTime') if kind=='Unit' else None,
                base_research_seconds=raw.get('ResearchTime') if kind=='Tech' else None,
                source_ref=f"{lock['repository']}/blob/{commit}/data/data.json",observed_in_match=False))
    except (OSError,ValueError,KeyError,TypeError,AttributeError):pass
    return out

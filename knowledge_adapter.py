"""Offline verified reference adapter. Catalog availability is never match state."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re

from tools.audit_techtree import load_snapshot, plain_text

ROOT = Path(__file__).resolve().parent
LOCK_PATH = ROOT / 'knowledge/aoe2techtree.lock.json'
PACK_PATH = ROOT / 'knowledge/franks-matchups.v1.json'
AVAILABLE_STATUSES = {'ResearchedCompleted', 'ResearchRequired'}


@dataclass(frozen=True)
class Knowledge:
    source: dict
    pack: dict
    facts: dict
    options: dict
    nodes: dict

    def node(self, civ, kind, entity_id):
        return self.nodes[(civ, kind, entity_id)]


def compile_knowledge(snapshot: dict, lock: dict, pack: dict) -> Knowledge:
    """Validate every reviewed assertion against namespaced source nodes/prose.

    Prose is only checked for reviewed excerpts, never parsed into bonus formulas.
    ResearchedCompleted here is a catalog status, NOT research observed in a match.
    """
    if (lock.get('repository') != 'https://github.com/SiegeEngineers/aoe2techtree' or
        pack.get('schema_version') != 1 or pack.get('pack_version') != 1 or
        pack.get('source_commit') != lock.get('commit') or pack.get('declared_update') != lock.get('declared_update') or
        pack.get('edition') != 'DE' or pack.get('dataset_id') != 100):
        raise ValueError('Reviewed pack/source version mismatch.')
    data, strings = snapshot['data.json'], snapshot['strings.en.json']
    nodes = {}
    for civ in ['Franks', *pack['opponents']]:
        raw = data['civs'][civ]
        tree = snapshot[f"trees/{raw['internal_name'].upper()}.json"]
        for node in tree['buildings'] + tree['units_techs']:
            kind = node.get('use_type')
            if kind not in ('Unit', 'Tech', 'Building'):
                raise ValueError('Unknown catalog namespace.')
            key = (civ, kind, node['node_id'])
            if key in nodes:
                raise ValueError('Ambiguous catalog node.')
            available = node['node_id'] in raw[kind]
            if available != (node['node_status'] in AVAILABLE_STATUSES):
                raise ValueError('Availability list and tree disagree.')
            nodes[key] = {**node, 'available': available}

    source = {'repository': lock['repository'], 'commit': lock['commit'], 'declared_update': lock['declared_update'],
              'pack_id': pack['id'], 'pack_version': pack['pack_version'], 'reviewed_on': pack['reviewed_on']}
    def node_ref(civ, kind, id_):
        node = nodes[(civ, kind, id_)]
        internal = data['civs'][civ]['internal_name'].upper()
        return {'id': f"{lock['commit']}:{civ}:{kind}:{id_}:availability_age", 'civilization': civ,
                'kind': kind, 'entity_id': id_, 'node_id': node['id'], 'age_id': node['age_id'],
                'available': node['available'], 'field': 'availability/age_id',
                'url': f"{lock['repository']}/blob/{lock['commit']}/data/trees/{internal}.json"}
    facts = {}
    for fact in pack['facts']:
        civ, refs = fact['civilization'], []
        for check in fact['checks']:
            n = nodes[(civ, check['kind'], check['id'])]
            if (n['name'] != check['name'] or n['age_id'] != check['age'] or n['available'] != check['available']):
                raise ValueError('Reviewed fact differs from source node.')
            refs.append(node_ref(civ, check['kind'], check['id']))
        if fact.get('description_excerpt'):
            string_id = data['civs'][civ]['help_string_id']
            text = plain_text(strings[str(string_id)])
            if fact['description_excerpt'] not in text:
                raise ValueError('Reviewed civilization description differs from source.')
            refs.append({'id': f"{lock['commit']}:{civ}:Civilization:{string_id}:description", 'civilization': civ,
                         'kind': 'Civilization', 'entity_id': string_id, 'field': 'description',
                         'url': f"{lock['repository']}/blob/{lock['commit']}/data/locales/en/strings.json"})
        if not refs or fact['id'] in facts:
            raise ValueError('Missing references or duplicate fact ID.')
        facts[fact['id']] = {k: fact[k] for k in ('id', 'civilization', 'minimum_age', 'text')}
        facts[fact['id']]['source_refs'] = refs
    options = {}
    for option in pack['options']:
        n = nodes[('Franks', option['kind'], option['entity_id'])]
        building = nodes[('Franks', 'Building', option['building_id'])]
        if not n['available'] or not building['available'] or n['age_id'] != option['age'] or n['building_id'] != option['building_id']:
            raise ValueError('Response option is unavailable or has inconsistent age/building.')
        options[option['id']] = {**option, 'source_refs': [node_ref('Franks', option['kind'], option['entity_id']), node_ref('Franks', 'Building', option['building_id'])]}
    if len(options) != len(pack['options']):
        raise ValueError('Duplicate option ID.')
    rule_ids = set()
    for rule in pack['rules']:
        if rule['id'] in rule_ids or rule['opponent'] not in pack['opponents']:
            raise ValueError('Invalid rule scope.')
        rule_ids.add(rule['id'])
        for unit in rule['opponent_units']:
            if not nodes[(rule['opponent'], 'Unit', unit)]['available']:
                raise ValueError('Rule observes an unavailable unit.')
        if not all(id_ in facts for id_ in rule['fact_ids']) or not all(id_ in options for id_ in rule['option_ids']):
            raise ValueError('Rule has unresolved references.')
    return Knowledge(source, pack, facts, options, nodes)


def _signature(path):
    s = path.stat()
    return (s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


@lru_cache(maxsize=2)
def _load_cached(lock_path: str, pack_path: str, directory: str, signatures: tuple):
    lock, pack = json.loads(Path(lock_path).read_text()), json.loads(Path(pack_path).read_text())
    snapshot = load_snapshot(Path(directory), lock)
    knowledge = compile_knowledge(snapshot, lock, pack)
    # Do not publish a read that raced a maintenance update.
    if tuple(_signature(Path(path)) for path, _ in signatures) != tuple(sig for _, sig in signatures):
        raise ValueError('Knowledge files changed during validation.')
    return knowledge


def local_knowledge() -> Knowledge:
    """No network, auto-installation, game assets, or replay information in paths."""
    lock = json.loads(LOCK_PATH.read_text())
    if not re.fullmatch(r'[0-9a-f]{40}', lock.get('commit', '')):
        raise ValueError('Invalid source commit.')
    directory = ROOT / 'data/research/aoe2techtree' / lock['commit']
    paths = [LOCK_PATH, PACK_PATH]
    root = directory.resolve()
    for entry in lock['files']:
        path = (root / entry['path']).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError('Snapshot path escapes directory.')
        paths.append(path)
    signatures = tuple((str(path), _signature(path)) for path in paths)
    return _load_cached(str(LOCK_PATH), str(PACK_PATH), str(directory), signatures)

#!/usr/bin/env python3
"""Offline, read-only tech-tree source audit. Not a match coach or combat model.

Read an explicitly downloaded, hash-locked public snapshot. No HTTP, replay
parsing, cache mutation, or user annotations. HTML from strings becomes plain text.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / 'knowledge' / 'aoe2techtree.lock.json'
STAT_FIELDS = ('ID', 'internal_name', 'Cost', 'TrainTime', 'ResearchTime', 'HP',
               'Attack', 'MeleeArmor', 'PierceArmor', 'Range', 'Speed', 'Attacks', 'Armours')


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('br', 'p', 'li') and not self.hidden:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)


def plain_text(text):
    parser = _PlainText()
    parser.feed(text)
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())


def load_snapshot(directory: Path, lock: dict) -> dict:
    """Check every locked byte before interpreting any file. Paths stay in directory."""
    if lock.get('schema_version') != 1:
        raise ValueError('Unsupported knowledge lock version.')
    root = directory.resolve()
    verified = {}
    for entry in lock['files']:
        path = (root / entry['path']).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError('Snapshot path escapes its directory.')
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry['sha256']:
            raise ValueError(f"Hash mismatch for {entry['path']}; do not mix source revisions.")
        verified[entry['path']] = json.loads(payload) if entry['path'].endswith('.json') else payload.decode('utf-8')
    return verified


def audit(snapshot: dict, lock: dict, civ_names: list[str], replay_build: int | None = None) -> dict:
    data, strings = snapshot['data.json'], snapshot['strings.en.json']
    update = lock.get('declared_update')
    compatibility = ('unknown' if replay_build is None or update is None else
                     'build_match' if replay_build == update else 'build_mismatch')
    result = {
        'audit_schema_version': 1,
        'source': {key: lock[key] for key in ('repository', 'commit', 'declared_update')},
        'replay_build': replay_build,
        'compatibility': compatibility,
        'matchup_rules_enabled': False,
        'limitations': [
            'Source audit only; a matching build does not verify mods, mode, or effective unit stats.',
            'Costs/times/stats are base catalog values, not civ/upgrade/team-bonus-adjusted values.',
            'Catalog availability and node_status are not evidence of units or completed research in a match.',
            'Civilization descriptions are reference text; no automatic parsing into executable bonus formulas.',
            'No battle outcomes, affordability, resource spending or production completion is reconstructed.',
        ],
        'civilizations': [],
    }
    for name in civ_names:
        if name not in data['civs']:
            raise ValueError(f'Unknown civilization: {name}')
        civ = data['civs'][name]
        description_id = str(civ['help_string_id'])
        description = strings.get(description_id)
        if not isinstance(description, str):
            raise ValueError(f'Missing civilization help string for {name}')
        tree_path = f"trees/{civ['internal_name'].upper()}.json"
        tree = snapshot.get(tree_path)
        nodes = []
        if tree:
            for node in tree['buildings'] + tree['units_techs']:
                nodes.append({key: node.get(key) for key in
                              ('id', 'node_id', 'node_type', 'name', 'age_id', 'node_status', 'building_id')})
        entities = {}
        for kind in ('Unit', 'Tech', 'Building'):
            entities[kind] = {}
            for id_ in civ[kind]:
                raw = data['data'][kind].get(str(id_))
                if raw:
                    # Kind+ID namespace is essential: Unit 93 != Tech 93.
                    entities[kind][str(id_)] = {key: raw[key] for key in STAT_FIELDS if key in raw}
        result['civilizations'].append({
            'name': name, 'era': civ.get('era'),
            'description': plain_text(description), 'description_string_id': description_id,
            'available_ids': {kind: civ[kind] for kind in ('Unit', 'Tech', 'Building')},
            'tree_status': 'loaded' if tree else 'not_in_locked_subset',
            'catalog_nodes': nodes, 'base_entities': entities,
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path, help='Directory of already downloaded public source files')
    parser.add_argument('--lock', type=Path, default=DEFAULT_LOCK)
    parser.add_argument('--civ', action='append', dest='civs', help='Repeat for more civs; defaults to Franks and Bohemians')
    parser.add_argument('--replay-build', type=int, help='Actual mgz Match.build_version, NOT filename version')
    args = parser.parse_args()
    try:
        lock = json.loads(args.lock.read_text())
        result = audit(load_snapshot(args.snapshot, lock), lock, args.civs or ['Franks', 'Bohemians'], args.replay_build)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        parser.exit(1, f'Tech-tree audit failed: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

"""Bounded catalog options for situation review; never reconstructed match state.

Menu v1 reviews availability/age only, NOT counters, costs or effective statistics.
No game installation, network or user annotation is required for incident review.
"""
from knowledge_adapter import local_knowledge
from replay_provenance import PROVENANCE_VERSION

MENU_VERSION = 1
# Reviewed against the locked four civilization trees. Namespace is mandatory.
MENU = [('Building', 72, 'Palisade Wall', 1), ('Building', 79, 'Watch Tower', 2),
        ('Building', 82, 'Castle', 3), ('Unit', 4, 'Archer', 2),
        ('Unit', 7, 'Skirmisher', 2), ('Unit', 93, 'Spearman', 2)]
AGES = {'Dark Age': 1, 'Feudal Age': 2, 'Castle Age': 3, 'Imperial Age': 4}


def reference_options(report, player_name, review, rules_context=None, *, knowledge=None):
    """Annotate questions externally; changing catalog availability never detects incidents."""
    result = {'menu_version': MENU_VERSION, 'status': 'unavailable', 'source': None,
              'civilization': None, 'reference_facts': [], 'options_by_incident': [],
              'reason': 'No unambiguous player or supported incident.',
              'limitations': ['A catalog option is not a counter recommendation or proof it was ready to queue.',
                              'Completed buildings/upgrades, resources, army positions and enemy unit types are unresolved.',
                              'Costs/bonuses/combat statistics are not evaluated in this slice.']}
    player = next((p for p in report.get('players', []) if p.get('id') == (review.get('player') or {}).get('id') and p.get('name') == player_name), None)
    if not player or not review.get('incidents'):
        return result
    result['civilization'] = player.get('civilization')
    try:
        k = knowledge if knowledge is not None else local_knowledge()
        nodes = [k.nodes[(player['civilization'], kind, id_)] for kind, id_, _, _ in MENU]
        if any(n['name'] != name or n['age_id'] != age for n, (_, _, name, age) in zip(nodes, MENU)):
            raise ValueError('Reviewed menu differs from catalog.')
    except KeyError:
        result['reason'] = 'This civilization has no reviewed local response menu. Generic situation questions remain available.'
        return result
    except (OSError, ValueError, TypeError) as exc:
        result['reason'] = f'Local catalog verification failed ({type(exc).__name__}); entity options withheld, without blocking incident review.'
        return result
    result['source'] = {**k.source, 'menu_version': MENU_VERSION}
    provenance = report.get('replay_provenance') or {}
    if (provenance.get('provenance_version') != PROVENANCE_VERSION or provenance.get('edition') != 'DE' or
        type(provenance.get('build_version')) is not int or provenance['build_version'] != k.source['declared_update'] or
        type(provenance.get('dataset_id')) is not int or provenance['dataset_id'] != 100 or
        type(provenance.get('game_type_id')) is not int or provenance['game_type_id'] != 0 or
        any(provenance.get(flag) is not False for flag in ('all_technologies', 'cheats', 'metadata_cheats', 'de_cheats')) or
        provenance.get('reported_mod') not in (None, '') or
        (provenance.get('rms_mod_id') is not None and (type(provenance['rms_mod_id']) is not int or provenance['rms_mod_id'] != 0)) or
        provenance.get('mod_compatibility') == 'incompatible'):
        result.update(status='incompatible', reason='Actual build/edition/dataset/mode/flags/mod context is unsupported or unknown. No applied catalog options; generic command questions are unchanged.')
        return result
    result['reference_facts'] = [f for f in k.facts.values() if f['civilization'] == player['civilization']]
    context = rules_context or {}
    declared = (context.get('version') == 1 and context.get('rules') == 'standard' and
                context.get('match_id') == report.get('match_id') and context.get('player') == player_name and
                context.get('provenance') == 'retrospective_user_annotation_not_parser_fact' and
                isinstance(context.get('declared_at'), str) and bool(context['declared_at']))
    if not declared:
        result.update(status='reference_only', reason='Pinned civilization facts are reference only. Mods remain independently unverified; a separate per-match user rules declaration is required even for conditional catalog options.')
        return result
    ages = sorted([e for e in report['events'] if e.get('player_id') == player['id'] and e.get('action') == 'AGE_REACHED' and
                   e.get('status') == 'observed_milestone' and e.get('technology') in AGES], key=lambda e: (e['time_seconds'], e['id']))
    values = [AGES[e['technology']] for e in ages]
    if values != sorted(set(values)):
        result.update(status='incompatible', reason='Contradictory/duplicate age milestones; phase-dependent catalog options withheld.')
        return result
    for incident in review['incidents']:
        t = incident['replay_anchor']['time_seconds']
        reached = [e for e in ages if e['time_seconds'] <= t]
        phase = AGES[reached[-1]['technology']] if reached else None
        options = []
        for node, (kind, id_, name, age) in zip(nodes, MENU):
            if phase is None or not node['available'] or age > phase:
                continue
            internal = player['civilization'].upper()
            options.append({'kind': kind, 'entity_id': id_, 'name': name, 'minimum_age': age,
                            'availability': 'conditional_catalog_age_only_not_ready_state',
                            'source_url': f"{k.source['repository']}/blob/{k.source['commit']}/data/trees/{internal}.json"})
        result['options_by_incident'].append({'incident_id': incident['id'], 'recorded_age': phase,
                                               'age_event_ids': [e['id'] for e in reached], 'options': options})
    result.update(status='conditional_catalog', reason='Only if user-reported standard rules are correct. These age-available catalog choices are not ranked counters, observed responses or verified readiness; mods remain independently unverified.')
    return result

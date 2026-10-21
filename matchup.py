"""Plan/outcome-independent, fail-closed matchup reference and review questions.

No opening-label dependency, state simulation, or knowledge of player vision.
Unknown mods never become verified: a separate local declaration only permits
explicitly CONDITIONAL questions, not asserted patch-applicable judgments.
"""
from __future__ import annotations

import hashlib
import math

from knowledge_adapter import Knowledge, local_knowledge
from replay_provenance import PROVENANCE_VERSION

MATCHUP_VERSION = 1
AGES = {'Dark Age': 1, 'Feudal Age': 2, 'Castle Age': 3, 'Imperial Age': 4}
LIMITATIONS = [
    'Civilization capabilities do not establish the army, completed research, or effective unit statistics.',
    'Queue/build/research commands are not completed production; retries and cancellations can change the final queue.',
    'Opponent commands are retrospective information and may not have been visible to the player.',
    'Resources, completed structures/upgrades, live army size, damage, paths and fight outcomes are not verified.',
    'These review questions are curated heuristics, not calibrated strategic diagnoses, causal explanations or mastery scores.',
]


def _team(player):
    value = player.get('team_id')
    if isinstance(value, list) and value:
        return ('members', *sorted(set(value)))
    return ('team', value) if value is not None else None


def _valid_stream(report):
    duration = report.get('duration_seconds')
    if report.get('excerpt') or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        return False
    events = report.get('events', [])
    if not isinstance(events, list) or any(
        not isinstance(e, dict) or not isinstance(e.get('id'), str) or not e['id'] or not isinstance(e.get('time_seconds'), (int, float)) or
        not math.isfinite(e['time_seconds']) or not 0 <= e['time_seconds'] <= duration for e in events
    ):
        return False
    return len({e['id'] for e in events}) == len(events)


def _ages(events, player_id):
    return [e for e in events if e.get('player_id') == player_id and e.get('action') == 'AGE_REACHED' and
            e.get('status') == 'observed_milestone' and e.get('technology') in AGES]


def _age_at(ages, seconds):
    return max((AGES[e['technology']] for e in ages if e['time_seconds'] <= seconds), default=1)


def _queue(e):
    amount = e.get('amount')
    return (e.get('action') in ('DE_QUEUE', 'QUEUE') and e.get('status') == 'command' and
            e.get('kind') == 'queue_command' and (amount is None or type(amount) in (int, float) and math.isfinite(amount) and amount > 0))


def _cancellation(e):
    return e.get('kind') == 'queue_cancel_command' or (e.get('action') == 'SPECIAL' and e.get('order') == 'Unqueue')


def _context_declared(context, report, player):
    return (isinstance(context, dict) and context.get('version') == 1 and context.get('rules') == 'standard' and
            context.get('match_id') == report.get('match_id') and context.get('player') == player['name'] and
            context.get('provenance') == 'retrospective_user_annotation_not_parser_fact' and
            isinstance(context.get('declared_at'), str) and bool(context['declared_at']))


def build_matchup(report: dict, player_name: str, rules_context: dict | None = None, *, knowledge: Knowledge | None = None) -> dict:
    result = {'matchup_version': MATCHUP_VERSION, 'match_id': report.get('match_id'), 'player': None, 'opponent': None,
              'status': 'unavailable', 'source': None, 'compatibility': {'status': 'unknown', 'conditional_tips_enabled': False, 'reasons': []},
              'reference_facts': [], 'observations': [], 'tips': [], 'decisions': [], 'limitations': list(LIMITATIONS),
              'abstention_reason': None}
    def stop(status, reason):
        result['status'] = status
        if status == 'incompatible' and result['compatibility']['status'] == 'unknown':
            result['compatibility']['status'] = 'incompatible'
        result['abstention_reason'] = reason
        if reason not in result['compatibility']['reasons']:
            result['compatibility']['reasons'].append(reason)
        return result
    if report.get('schema_version') != 5:
        return stop('incompatible', 'Unsupported normalized analysis schema; no matchup facts are applied.')
    selected = [p for p in report.get('players', []) if p.get('name') == player_name]
    if not player_name or len(selected) != 1:
        return stop('needs_player', 'Choose an unambiguous player; no slot-1 assumption is made.')
    player = selected[0]
    result['player'] = {k: player[k] for k in ('id', 'name', 'civilization')}
    players = report.get('players', [])
    if (len(players) != 2 or len({p['id'] for p in players}) != 2 or not _team(player) or
        not all(_team(p) and _team(p) != _team(player) for p in players if p['id'] != player['id'])):
        return stop('unsupported_format', 'This matchup slice requires an unambiguous opposing player in a two-player game; teams are not generalized.')
    opponent = next(p for p in players if p['id'] != player['id'])
    result['opponent'] = {k: opponent.get(k) for k in ('id', 'name', 'civilization')}
    if player.get('civilization') != 'Franks':
        return stop('unsupported_civilization', 'Only the selected-player Franks pack is reviewed in this slice.')
    try:
        knowledge = knowledge if knowledge is not None else local_knowledge()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return stop('knowledge_unavailable', f'Local reference verification failed ({type(exc).__name__}); normal coaching remains available. No download is attempted.')
    result['source'] = dict(knowledge.source)
    provenance = report.get('replay_provenance') or {}
    if provenance.get('provenance_version') != PROVENANCE_VERSION:
        return stop('incompatible', 'Header provenance needs a current mode/flag check; reload through the local API to enrich the cached report.')
    build = provenance.get('build_version')
    if type(build) is not int or build != knowledge.source['declared_update']:
        result['compatibility']['status'] = 'build_mismatch' if type(build) is int else 'unknown_build'
        return stop('incompatible', 'Actual replay build is missing or differs from the reviewed knowledge update; filename versions are not used.')
    if (provenance.get('edition') != 'DE' or type(provenance.get('dataset_id')) is not int or provenance.get('dataset_id') != 100):
        return stop('incompatible', 'Edition/dataset compatibility is unknown or unsupported.')
    if (type(provenance.get('game_type_id')) is not int or provenance['game_type_id'] != 0 or
        provenance.get('all_technologies') is not False or provenance.get('cheats') is not False or
        provenance.get('metadata_cheats') is not False or provenance.get('de_cheats') is not False):
        return stop('incompatible', 'Only recorded Random Map mode with all-technologies and cheats explicitly off is supported. Unknown flags cannot be overridden.')
    if (provenance.get('reported_mod') not in (None, '') or (provenance.get('rms_mod_id') is not None and (type(provenance['rms_mod_id']) is not int or provenance['rms_mod_id'] != 0)) or
        provenance.get('mod_compatibility') == 'incompatible'):
        return stop('incompatible', 'A reported mod/custom RMS or incompatible ruleset blocks this standard-rules pack; a declaration cannot override it.')
    result['reference_facts'] = sorted(
        [dict(fact) for fact in knowledge.facts.values() if fact['civilization'] in ('Franks', opponent.get('civilization'))],
        key=lambda fact: (fact['civilization'] != opponent.get('civilization'), fact['minimum_age']))
    # References above are explicitly facts about the pinned standard-rules source,
    # not assertions of applicability to this replay.
    declared = _context_declared(rules_context, report, player)
    result['compatibility'].update({
        'status': 'conditional_user_context' if declared else 'reference_only_unknown_mods',
        'conditional_tips_enabled': declared,
        'basis': 'user_reported_standard_rules_not_independently_verified' if declared else 'empty_mod_metadata_does_not_verify_standard_rules',
        'reasons': ['Build/data/mode match, but mods are not independently verified.' +
                    (' A separate per-match user declaration permits conditional questions only.' if declared else ' Patch-specific tips remain withheld; source facts below are reference only.')],
    })
    if opponent.get('civilization') not in knowledge.pack['opponents']:
        return stop('reference_only', 'No reviewed opponent pack; only universal Franks reference constraints are shown.')
    if not _valid_stream(report):
        return stop('reference_only', 'Incomplete/malformed command stream: no matchup observations or tips are inferred.')
    ordered = sorted(report.get('events', []), key=lambda e: (e['time_seconds'], e['id']))
    own_ages, enemy_ages = _ages(ordered, player['id']), _ages(ordered, opponent['id'])
    for ages in (own_ages, enemy_ages):
        values = [AGES[e['technology']] for e in ages]
        if values != sorted(values):
            return stop('reference_only', 'Age milestones contradict chronological order; no phase-specific tips are inferred.')
    rules = [r for r in knowledge.pack['rules'] if r['opponent'] == opponent['civilization']]
    def known_queue(e, actor, allowed, ages, *, require_age=True):
        unit_id = e.get('unit_type_id')
        if e.get('player_id') != actor['id'] or not _queue(e) or type(unit_id) is not int or unit_id not in allowed:
            return False
        node = knowledge.node(actor['civilization'], 'Unit', unit_id)
        return node['name'] == e.get('unit') and (not require_age or node['available'] and node['age_id'] <= _age_at(ages, e['time_seconds']))
    own = [e for e in ordered if known_queue(e, player, {38}, own_ages)]
    unit_ids = {id_ for rule in rules for id_ in rule['opponent_units']}
    enemy = [e for e in ordered if known_queue(e, opponent, unit_ids, enemy_ages)]
    observed_own = [e for e in ordered if known_queue(e, player, {38}, own_ages, require_age=False)]
    observed_enemy = [e for e in ordered if known_queue(e, opponent, unit_ids, enemy_ages, require_age=False)]
    for side, commands in [('you', observed_own), ('opponent', observed_enemy)]:
        if commands:
            result['observations'].append({
                'side': side, 'evidence_class': 'queue_command', 'command_count': len(commands),
                'unit_labels': sorted({e['unit'] for e in commands}),
                'event_ids': list(dict.fromkeys(e['id'] for e in commands[:3] + commands[-3:])),
                'window_seconds': [commands[0]['time_seconds'], commands[-1]['time_seconds']],
                'meaning': 'Relevant parser-resolved positive queue commands, not unique or completed units. Mod/entity mapping is unverified. Evidence buttons sample the first/last commands.',
            })
    if not declared:
        return stop('reference_only', result['compatibility']['reasons'][0])
    castle = next((e for e in own_ages if e['technology'] == 'Castle Age'), None)
    if not castle:
        return stop('no_supported_pattern', 'No recorded selected-player Castle anchor; no Castle-cavalry matchup question is inferred. Missing evidence does not establish absence or a failed plan.')
    imperial = next((e['time_seconds'] for e in own_ages if e['technology'] == 'Imperial Age'), report['duration_seconds'])
    for rule in rules:
        emitted = False
        searched = 0
        reason = 'No repeated, age-supported opponent and Knight queue pattern in a candidate-relative window.'
        for anchor in own:
            t = anchor['time_seconds']
            if _age_at(own_ages, t) != 3 or _age_at(enemy_ages, t) < rule['minimum_opponent_age']:
                continue
            searched += 1
            start, end = max(castle['time_seconds'], t - 120), min(imperial, report['duration_seconds'], t + 180)
            own_window = [e for e in own if start <= e['time_seconds'] <= end]
            enemy_window = [e for e in enemy if start <= e['time_seconds'] <= end and e['unit_type_id'] in rule['opponent_units'] and
                            _age_at(enemy_ages, e['time_seconds']) >= rule['minimum_opponent_age']]
            if len(own_window) < 2 or len(enemy_window) < 2:
                continue
            cancellations = [e for e in ordered if start <= e['time_seconds'] <= end and
                             e.get('player_id') in (player['id'], opponent['id']) and _cancellation(e)]
            if cancellations:
                reason = 'Nearby cancellation/Unqueue commands make this queue pattern ambiguous; the conditional question is withheld.'
                continue
            age_ids = [e['id'] for e in own_ages + enemy_ages if e['time_seconds'] <= t and AGES[e['technology']] >= 2]
            ids = list(dict.fromkeys(age_ids + [e['id'] for e in own_window + enemy_window]))
            options = []
            for id_ in rule['option_ids']:
                option = knowledge.options[id_]
                if option['age'] <= _age_at(own_ages, t):
                    placements = [e['id'] for e in ordered if e.get('player_id') == player['id'] and e.get('action') == 'BUILD' and
                                  e.get('status') == 'command' and e.get('building_type_id') == option['building_id'] and e['time_seconds'] <= t]
                    options.append({**option, 'availability': 'catalog_age_only_not_ready_to_queue', 'structure_placement_event_ids': placements})
            if not options:
                reason = 'No reviewed, age-appropriate response option; abstained.'
                continue
            identity = f"{report.get('match_id')}:{player['id']}:{rule['id']}:{MATCHUP_VERSION}:{knowledge.source['commit']}:{knowledge.source['pack_version']}:{anchor['id']}"
            result['tips'].append({
                'id': 'matchup:' + hashlib.sha256(identity.encode()).hexdigest()[:24], 'rule_id': rule['id'], 'rule_version': 1,
                'kind': 'conditional_replay_review_question', 'title': rule['title'], 'window_seconds': [start, end],
                'replay_anchor_event_id': anchor['id'], 'event_ids': ids,
                'observations': [f"{len(own_window)} Knight queue commands and {len(enemy_window)} relevant opponent queue commands in this window; not produced army counts."],
                'interpretation': rule['interpretation'], 'action': rule['action'], 'alternatives': rule['alternatives'],
                'fact_ids': rule['fact_ids'], 'options': options,
                'evidence_quality': {'catalog': 'hash_verified_reviewed_reference', 'commands': 'recorded_commands_not_completed_production',
                                     'interpretation': 'conditional_curated_heuristic_not_independently_calibrated', 'vision': 'unknown'},
                'conditions': ['Only if the separate user declaration of standard rules is correct; mods remain independently unverified.',
                               'Opponent composition must actually have been scouted; retrospective commands are not in-game awareness.',
                               'Options require completed structures/upgrades, suitable positioning and resources, none of which are verified here.',
                               'This window may include later commands; it is not an instruction to react at the anchor timestamp.'],
                'not_claimed': ['confirmed mistake', 'intended plan', 'completed units or upgrades', 'absence of existing support',
                                'affordability', 'effective range/HP/DPS', 'combat results', 'causal explanation of result'],
            })
            emitted, reason = True, 'Conditional scouting/composition review question; independent of intended plan and result.'
            break
        result['decisions'].append({'rule_id': rule['id'], 'status': 'conditional_question' if emitted else 'abstained', 'reason': reason, 'candidate_windows_searched': searched})
        if len(result['tips']) >= 2:
            break
    result['status'] = 'conditional_questions' if result['tips'] else 'no_supported_pattern'
    if not result['tips']:
        result['abstention_reason'] = 'No supported matchup question in the searched Castle-phase windows. This does not establish safety, missing units or a correct/incorrect strategy.'
    return result

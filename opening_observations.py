"""Opening command patterns, not intended strategies or simulated production.

Pure, versioned observations. No outcome or manual-plan inputs. Confidence bands
are rule-based evidence strength, not calibrated probabilities. Unknown is normal.
"""
from __future__ import annotations

import math

OBSERVATION_VERSION = 2
OPENING_WINDOW_SECONDS = 360  # First six game minutes after recorded Feudal arrival.


def _team(player):
    team = player.get('team_id')
    if isinstance(team, list):
        return ('members', *sorted(set(team))) if team else ('player', player['id'])
    return ('team', team) if team is not None else ('player', player['id'])


def _context(ordered, player, players, start, end):
    nearby, adaptations = [], []
    base = player.get('base')
    for e in ordered:
        if not start <= e['time_seconds'] <= end:
            continue
        if e.get('player_id') == player['id']:
            if ((e.get('action') == 'SPECIAL' and e.get('order') == 'Garrison') or
                (e.get('action') == 'BUILD' and e.get('building') in ('Watch Tower', 'Guard Tower', 'Keep', 'Castle'))):
                adaptations.append(e['id'])
        elif e.get('action') in ('ORDER', 'MOVE', 'PATROL', 'DE_ATTACK_MOVE'):
            actor, pos = players.get(e.get('player_id')), e.get('position')
            if actor and _team(actor) != _team(player) and base and pos and math.hypot(pos['x']-base['x'], pos['y']-base['y']) <= 18:
                nearby.append(e['id'])
    return {'window_seconds': [start, end],
            'status': 'possible_from_commands' if nearby or adaptations else 'unknown',
            'event_ids': adaptations, 'opponent_order_event_ids': nearby,
            'reason': 'Proximity/placement/garrison cues only; not confirmed attacks or defensive intent. No cue does not establish safety.'}


def observe_openings(report: dict) -> list[dict]:
    events = report.get('events', [])
    duration = report.get('duration_seconds')
    if report.get('excerpt') or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        return []
    if any(not isinstance(e.get('id'), str) or not isinstance(e.get('time_seconds'), (int, float)) or
           not math.isfinite(e['time_seconds']) or not 0 <= e['time_seconds'] <= duration for e in events):
        return []
    if len({e['id'] for e in events}) != len(events):
        return []
    ordered = sorted(events, key=lambda e: (e['time_seconds'], e['id']))
    players = {p['id']: p for p in report.get('players', [])}
    output = []
    for player in players.values():
        own = [e for e in ordered if e.get('player_id') == player['id']]
        def age(name):
            return next((e for e in own if e.get('action') == 'AGE_REACHED' and
                         e.get('technology') == name and e.get('status') == 'observed_milestone'), None)
        feudal, castle = age('Feudal Age'), age('Castle Age')
        start = feudal['time_seconds'] if feudal else 0
        end = min(duration, start + OPENING_WINDOW_SECONDS, castle['time_seconds'] if castle else duration)
        commands = [e for e in own if e.get('action') in ('DE_QUEUE', 'QUEUE') and
                    e.get('kind') == 'queue_command' and e.get('status') == 'command' and
                    (e.get('amount') is None or e.get('amount', 0) > 0)]
        groups = []
        for tag, label, units, building in [
            ('scouts', 'Scouts', {'Scout Cavalry'}, 'Stable'),
            ('archers', 'Archers', {'Archer'}, 'Archery Range'),
            ('militia_line', 'Militia-line', {'Militia', 'Man-at-Arms'}, 'Barracks'),
        ]:
            # Dark-age militia can precede the Feudal milestone; late militia isn't an opening.
            lower = max(0, start - 180) if tag == 'militia_line' else start
            upper = min(end, start + 90) if tag == 'militia_line' and feudal else end
            queues = [e for e in commands if lower <= e['time_seconds'] <= upper and e.get('unit') in units]
            if len(queues) < 2:
                continue
            structure = next((e for e in own if e.get('action') == 'BUILD' and e.get('building') == building and
                              e.get('status') == 'command' and e['time_seconds'] <= queues[-1]['time_seconds']), None)
            upgrade = next((e for e in own if tag == 'militia_line' and e.get('action') == 'RESEARCH' and
                            e.get('technology') in ('Man-at-Arms', 'Men-at-Arms') and e['time_seconds'] <= upper), None)
            anchors = ([feudal] if feudal else []) + ([structure] if structure else []) + queues + ([upgrade] if upgrade else [])
            groups.append({'tag': tag, 'label': 'Militia + Men-at-Arms research' if upgrade else label, 'queue_command_count': len(queues),
                           'confidence': 'high' if feudal and structure else 'medium',
                           'reason': 'Repeated recorded queue commands' + (' with structure placement and Feudal milestone.' if feudal and structure else '; structure/age support is incomplete.'),
                           'event_ids': list(dict.fromkeys(e['id'] for e in anchors)),
                           'first_queue_event_id': queues[0]['id'], 'first_queue_seconds': queues[0]['time_seconds']})
        transitions = []
        if castle:
            knight = next((e for e in commands if e.get('unit') == 'Knight' and e['time_seconds'] >= castle['time_seconds']), None)
            if knight:
                transitions.append({'tag': 'knight_follow_up', 'label': 'Castle → Knight queue command',
                                    'event_ids': [castle['id'], knight['id']],
                                    'interval_seconds': round(knight['time_seconds'] - castle['time_seconds'], 3),
                                    'confidence': 'high', 'meaning': 'Two recorded anchors; not completed production or intended plan.',
                                    'context': _context(ordered, player, players, max(0, castle['time_seconds'] - 90), min(duration, knight['time_seconds'] + 120))})
        label = 'Mixed command patterns' if len(groups) > 1 else f'{groups[0]["label"]} command pattern' if groups else 'Opening not established'
        output.append({
            'observation_version': OBSERVATION_VERSION, 'player_id': player['id'], 'player': player['name'],
            'label': label, 'patterns': groups, 'transitions': transitions,
            'confidence': 'insufficient' if not groups else 'medium' if len(groups) > 1 else groups[0]['confidence'],
            'window_seconds': [max(0, start - 180), end],
            'coverage': 'age_anchored_command_window' if feudal else 'partial_no_feudal_anchor',
            'intended_opening': {'status': 'unknown', 'reason': 'Commands do not establish intent; declared plans remain separate annotations.'},
            'adaptation': _context(ordered, player, players, start, end),
            'limitations': ['Counts are queue commands, not units produced; cancellations and retries may affect the pattern.',
                            'First means first recorded. Missing commands do not establish absence.',
                            'Opponent commands in retrospective replay may not have been visible to the player.',
                            'Confidence describes command-pattern evidence, not strategic quality or probability.'],
        })
    return output

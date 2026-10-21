"""Situation-first command review. Pure, deterministic; no reconstructed game state.

Commands near an initial snapshot are a review cue, not an observed engagement.
No plan, result, opening classification or legacy timing finding is an input.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from situation_coaching import REVIEW_VERSION, compose_review
import hashlib
import math

SITUATION_VERSION = 1
TACTICAL = {'ORDER', 'PATROL', 'DE_ATTACK_MOVE', 'ATTACK_GROUND'}
MOVEMENT = TACTICAL | {'MOVE'}
DEFENSE_BUILDINGS = {'Watch Tower', 'Guard Tower', 'Keep', 'Castle'}
LIMITATIONS = [
    'Command coordinates are requested destinations/placements, not actual unit positions or paths.',
    'Selected object IDs do not establish unit types, army size, damage, deaths or an attack.',
    'Opponent commands are retrospective and may not have been visible to the selected player.',
    'No resource balances, completed production/research, affordability, actual TC idle time or combat outcomes are reconstructed.',
    'Missing response commands do not establish inaction. Initial-TC coverage misses raids elsewhere and small/single-object visits.',
    'Evidence strength is rule-based, not calibrated strategic accuracy. Questions are not confirmed mistakes or explanations of the result.',
]


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _position(value):
    return isinstance(value, dict) and all(_number(value.get(k)) and value[k] >= 0 for k in ('x', 'y'))


def _distance(a, b):
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


def _team(player):
    value = player.get('team_id')
    if isinstance(value, list):
        return ('members', *sorted(set(value))) if value and player['id'] in value and all(type(v) is int and v > 0 for v in value) else None
    return ('team', value) if type(value) is int and value > 0 else None


def _opposing(a, b):
    left, right = _team(a), _team(b)
    if not left or not right or left[0] != right[0]:
        return None
    if left == right:
        return False
    if left[0] == 'members' and set(left[1:]) & set(right[1:]):
        return None  # Conflicting partial team memberships are not enemies.
    return True


def _anchor(report, player_id):
    snapshots = report.get('initial_town_centers', [])
    if not isinstance(snapshots, list):
        return None
    rows = [r for r in snapshots if isinstance(r, dict) and r.get('player_id') == player_id and
            r.get('status') == 'verified_initial_snapshot' and _position(r.get('position'))]
    points = {(r['position']['x'], r['position']['y']) for r in rows}
    if len(points) != 1:
        return None
    return {'position': dict(rows[0]['position']),
            'object_ids': sorted({i for r in rows for i in (r.get('object_ids') or []) if type(i) is int and i > 0}),
            'source': 'verified_initial_tc_snapshot'}


def _wall_distance(event, point):
    """Distance to requested wall segment, never a completed obstruction."""
    p = event['position']
    x, y = p.get('x_end'), p.get('y_end')
    if event['action'] != 'WALL' or not _number(x) or not _number(y) or x < 0 or y < 0:
        return _distance(p, point)
    dx, dy = x - p['x'], y - p['y']
    fraction = max(0, min(1, ((point['x']-p['x'])*dx + (point['y']-p['y'])*dy) / (dx*dx+dy*dy))) if dx or dy else 0
    return _distance({'x': p['x']+fraction*dx, 'y': p['y']+fraction*dy}, point)


def _identity(report, player, kind, anchor_id):
    raw = f"{report['match_id']}:{player['id']}:{kind}:{SITUATION_VERSION}:{anchor_id}"
    return 'situation:' + hashlib.sha256(raw.encode()).hexdigest()[:24]


def build_situation_review(report: dict, player_name: str) -> dict:
    result = {'situation_version': SITUATION_VERSION, 'review_version': REVIEW_VERSION, 'match_id': report.get('match_id'), 'player': None,
              'status': 'abstained', 'incidents': [], 'links': [], 'recommendations': [], 'decisions': [],
              'coverage': {'command_stream_completeness': 'unknown', 'gameplay_state_complete': False,
                           'spatial_scope': 'verified initial TC only', 'unresolved_actor_event_count': 0},
              'ranking_policy': ['valid evidence, explicit opposing identity and initial-snapshot geometry',
                                 'direct forward-placement cue before repeated tactical commands before generic interactions',
                                 'earliest anchor within equal evidence class', 'one question per overlapping nearby opponent episode; maximum two'],
              'limitations': list(LIMITATIONS), 'abstention_reason': None}

    def stop(reason):
        result['abstention_reason'] = reason
        return result

    players, events, duration = report.get('players', []), report.get('events', []), report.get('duration_seconds')
    if report.get('schema_version') != 5 or report.get('excerpt') or not isinstance(report.get('match_id'), str) or not report['match_id']:
        return stop('A complete schema-5 report with stable content identity is required.')
    if (not isinstance(players, list) or any(not isinstance(p, dict) or type(p.get('id')) is not int or
        not isinstance(p.get('name'), str) for p in players) or len({p['id'] for p in players}) != len(players)):
        return stop('Player identity is malformed or duplicated; no opponent is assumed.')
    selected = [p for p in players if p.get('name') == player_name]
    if not player_name or len(selected) != 1:
        return stop('Select one unambiguous player; no slot-1 or civilization assumption is made.')
    player = selected[0]
    result['player'] = {k: player.get(k) for k in ('id', 'name', 'civilization')}
    if (not _number(duration) or duration <= 0 or not isinstance(events, list) or any(
        not isinstance(e, dict) or not isinstance(e.get('id'), str) or not e['id'] or
        not _number(e.get('time_seconds')) or not 0 <= e['time_seconds'] <= duration or
        (e.get('player_id') is not None and type(e['player_id']) is not int) or
        (e.get('position') is not None and not _position(e['position'])) for e in events) or
        len({e['id'] for e in events}) != len(events)):
        return stop('Invalid timestamps, coordinates or duplicate/stale evidence IDs; inspect the replay instead.')
    if any(e.get('action') == 'DIPLOMACY' for e in events):
        return stop('Recorded diplomacy changes make static header teams insufficient; dynamic alliances are not reconstructed.')
    base = _anchor(report, player['id'])
    if not base:
        return stop('One verified initial TC location is required; current bases/expansions are not inferred.')
    enemies = {p['id']: p for p in players if _opposing(player, p) is True}
    result['coverage'].update({'searched_window_seconds': [0, duration], 'initial_tc': base,
                               'opponent_ids': sorted(enemies),
                               'unresolved_team_player_ids': [p['id'] for p in players if p['id'] != player['id'] and _opposing(player, p) is None]})
    if not enemies:
        return stop('No explicitly opposing team identity is available; allies/unknown diplomacy cannot seed pressure.')
    ordered = sorted(events, key=lambda e: (e['time_seconds'], e['id']))
    times = [e['time_seconds'] for e in ordered]
    result['coverage']['unresolved_actor_event_count'] = sum(e.get('player_id') not in {p['id'] for p in players} for e in ordered)
    # Discovery covers the entire match; no hard-coded strategic time window.
    clusters, active, forward = [], [], []
    for e in ordered:
        if e.get('player_id') not in enemies or e.get('status') != 'command' or not e.get('position'):
            continue
        distance = _distance(e['position'], base['position'])
        if (e.get('action') == 'BUILD' and e.get('building') in DEFENSE_BUILDINGS and distance <= 18 and
            e.get('counted_as_new_placement') is not False):
            actor_base = _anchor(report, e['player_id'])
            if actor_base and distance < _distance(e['position'], actor_base['position']):
                forward.append(e)
        if e.get('action') not in MOVEMENT or distance > 18:
            continue
        ids = e.get('object_ids', [])
        if not isinstance(ids, list) or any(type(i) is not int or i <= 0 for i in ids) or len(set(ids)) < 3:
            continue
        actor_ids = set(ids)
        active = [c for c in active if e['time_seconds']-c[0]['time_seconds'] <= 120]
        cluster = next((c for c in reversed(active) if e['player_id'] == c[0]['player_id'] and
                        e['time_seconds']-c[-1]['time_seconds'] <= 45 and
                        len(actor_ids & set(c[-1]['object_ids'])) >= 2), None)
        if cluster is None:
            cluster = []
            clusters.append(cluster)
            active.append(cluster)
        cluster.append(e)
    candidates = []
    for cluster in clusters:
        seeds = [e for e in cluster if e['action'] in TACTICAL and _distance(e['position'], base['position']) <= 12]
        if len(cluster) >= 3 and len({e['time_seconds'] for e in cluster}) >= 2 and seeds:
            candidates.append(('localized_opponent_commands', cluster, seeds[0]))
    candidates += [('forward_build_command', [e], e) for e in forward]
    result['coverage'].update({'localized_clusters_searched': len(clusters), 'forward_placement_cues': len(forward)})
    for kind, commands, anchor in candidates:
        start, end = commands[0]['time_seconds'], commands[-1]['time_seconds']
        window = [max(0, start-30), min(duration, end+120)]
        local_events = ordered[bisect_left(times, window[0]):bisect_right(times, window[1])]
        responses, unlocalized, context = [], [], []
        for e in local_events:
            if e.get('player_id') != player['id']:
                continue
            if (e.get('action') == 'AGE_REACHED' and e.get('status') == 'observed_milestone' or
                e.get('status') == 'command' and (e.get('kind') in ('queue_command', 'queue_cancel_command') or e.get('action') == 'RESEARCH')):
                context.append(e['id'])
            if e.get('status') != 'command':
                continue
            spatial = None
            pos = e.get('position')
            if e.get('action') in ('BUILD', 'WALL') and e.get('counted_as_new_placement') is not False and (
                e.get('action') == 'WALL' or e.get('building') in DEFENSE_BUILDINGS):
                if pos and _wall_distance(e, base['position']) <= 22 and _wall_distance(e, anchor['position']) <= 12:
                    spatial = 'requested_placement_near_incident_command_coordinates'
            elif e.get('action') == 'SPECIAL' and e.get('order') == 'Garrison':
                if type(e.get('target_id')) is int and e['target_id'] in base['object_ids']:
                    spatial = 'target_id_matches_initial_tc_snapshot_not_current_state'
                elif pos and _distance(pos, anchor['position']) <= 12 and _distance(pos, base['position']) <= 22:
                    spatial = 'garrison_command_coordinates_near_incident_not_actual_position'
                else:
                    unlocalized.append(e['id'])
            if spatial:
                responses.append({'event_id': e['id'], 'time_seconds': e['time_seconds'],
                                  'temporal_relation': 'before' if e['time_seconds'] < start else 'after' if e['time_seconds'] > end else 'during',
                                  'spatial_relation': spatial,
                                  'meaning': 'Recorded command associated by time/geometry only; defensive intent and effectiveness unresolved.'})
        source_ids = [e['id'] for e in commands]
        ids = list(dict.fromkeys(source_ids + [r['event_id'] for r in responses] + unlocalized + context))
        tactical = any(e['action'] in TACTICAL-{'ORDER'} for e in commands)
        strength = 'direct_placement_command' if kind == 'forward_build_command' else 'repeated_tactical_commands' if tactical else 'repeated_generic_commands'
        incident = {'id': _identity(report, player, kind, anchor['id']), 'type': kind, 'detector_version': SITUATION_VERSION,
                    'participants': {'selected_player_id': player['id'], 'opponent_player_id': anchor['player_id']},
                    'window_seconds': [start, end], 'review_window_seconds': window,
                    'replay_anchor': {'event_id': anchor['id'], 'time_seconds': anchor['time_seconds']},
                    'zone': base, 'locations': [{'event_id': e['id'], 'position': dict(e['position']), 'semantics': 'command_coordinates_not_unit_position'} for e in commands],
                    'selected_object_ids': sorted({i for e in commands for i in e.get('object_ids', []) if type(i) is int and i > 0}),
                    'event_ids': ids, 'situation_event_ids': source_ids, 'responses': responses,
                    'unlocalized_response_event_ids': unlocalized, 'context_event_ids': context,
                    'observation': (f"{anchor['building']} placement command within 18 tiles of your initial TC and closer to it than to the opponent's initial TC. Completion and forward intent are unknown."
                                    if kind == 'forward_build_command' else
                                    f'{len(commands)} opponent movement/order commands with overlapping selected object IDs near your initial TC. At least one tactical/generic-order destination is within 12 tiles; not a confirmed attack.'),
                    'interpretation': 'Possible local pressure and possible defensive adaptation; review what was actually visible before judging the choice.',
                    'options': [
                        {'action': 'Verify what you could see and which economy/route, if any, was exposed.', 'condition': 'Use player vision/HUD in the replay; enemy command knowledge alone is insufficient.'},
                        {'action': 'Consider protecting exposed economy, repositioning available defense, or a suitable defensive investment.', 'condition': 'Only if a real threat was visible and completed units/buildings, terrain and resources made that choice feasible.'},
                        {'action': 'Continue the existing plan or adapt it deliberately rather than chasing a timing target.', 'condition': 'If existing defenses were adequate or the commands were a feint/harmless interaction; no safe-state claim is made.'}],
                    'actual_response': 'Nearby placement/garrison commands were recorded; their purpose and resulting state remain unresolved.' if responses else 'No localized supported response command identified in this window; this is not proof of inaction.',
                    'outcome': {'status': 'unresolved', 'verified_consequences': [], 'reason': 'Later commands cannot establish damage, survival, successful defense or why the match ended.'},
                    'alternatives': ['Generic orders can be noncombat interactions, a feint or activity already handled by existing defenses.',
                                     'Nearby construction/garrison may be planned or unrelated; temporal association is not causation.',
                                     'Later context/response commands may not have been available at the review anchor.'],
                    'quality': {'evidence_strength': strength, 'vision': 'unknown', 'unit_types': 'unresolved', 'response_intent': 'unresolved',
                                'stream_completeness': 'unknown', 'right_censored': end+120 > duration, 'left_censored': start < 30}}
        result['incidents'].append(incident)
    incidents = sorted(result['incidents'], key=lambda i: (i['replay_anchor']['time_seconds'], i['id']))
    result['incidents'] = incidents
    # Bounded local links: relation, never a chain of asserted causes.
    for index, incident in enumerate(incidents):
        for previous in reversed(incidents[:index]):
            if incident['window_seconds'][0]-previous['window_seconds'][1] > 120:
                continue
            if (incident['participants']['opponent_player_id'] == previous['participants']['opponent_player_id'] and
                abs(incident['replay_anchor']['time_seconds']-previous['replay_anchor']['time_seconds']) <= 240 and
                _distance(incident['locations'][0]['position'], previous['locations'][0]['position']) <= 12):
                result['links'].append({'earlier_incident_id': previous['id'], 'later_incident_id': incident['id'],
                                        'relation': 'temporally_and_command_spatially_near_not_causal'})
                break
    compose_review(report, result)
    result['status'] = 'review_questions' if result['recommendations'] else 'no_supported_incident'
    if not result['recommendations']:
        result['abstention_reason'] = 'No supported localized command episode in the searched initial-TC zone. This does not establish safety, correct play, no pressure elsewhere, or no improvement opportunities.'
    validate_situation_review(result, report)
    return result


def validate_situation_review(review, report):
    by_id = {e['id']: e for e in report['events']}
    assert len(review['recommendations']) <= 2
    incident_ids = {i['id'] for i in review['incidents']}
    assert len(incident_ids) == len(review['incidents'])
    for row in review['incidents'] + review['recommendations']:
        assert row['event_ids'] and all(id_ in by_id for id_ in row['event_ids'])
        anchor = row['replay_anchor']
        assert by_id[anchor['event_id']]['time_seconds'] == anchor['time_seconds']
    for question in review['recommendations']:
        assert question['incident_id'] in incident_ids and question['exercise'] and question['uncertainties']
    for marker in review.get('timeline', []):
        assert marker['event_id'] in by_id and by_id[marker['event_id']]['time_seconds'] == marker['time_seconds']
    if review.get('positive'):
        assert all(id_ in by_id for id_ in review['positive']['event_ids'])
    for episode in review.get('episodes', []):
        assert set(episode['incident_ids']) <= incident_ids and all(id_ in by_id for id_ in episode['event_ids'])
    for link in review['links']:
        assert link['earlier_incident_id'] in incident_ids and link['later_incident_id'] in incident_ids

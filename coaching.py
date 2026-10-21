"""Selected-match coaching v1. Pure, deterministic, no I/O or changes to parser facts.

Only an explicitly confirmed Franks Scouts -> Knights plan on Arabia 1v1 is
eligible. Timing triggers review, never proves a mistake or a completed unit.
"""
from __future__ import annotations

import math
from analysis import clock

COACHING_VERSION = 1
PLAN = 'franks-scouts-knights'
PARSER_PIN = 'def94dd63a23b65435813e5acc8a0b3defafda03'
GOAL_ID = 'castle-transition-checklist-v1'


def team_key(player: dict):
    team = player.get('team_id')
    if isinstance(team, list):
        return ('members', *sorted(set(team))) if team else ('player', player['id'])
    return ('team', team) if team is not None else ('player', player['id'])


def quality(*, decoded=False, complete=False, reason=''):
    return {'anchors_reliably_decoded': decoded, 'complete_for_measure': complete,
            'stream_completeness': 'unknown', 'gameplay_state_complete': False,
            'reason': reason or 'Parser has no end-to-end completeness guarantee; missing records are not proof of absence.'}


def observation(id_, text, events, kind='derived_proxy', derivation=None):
    result = {'id': id_, 'text': text, 'evidence_class': kind,
              'event_ids': [e['id'] for e in events],
              'window_seconds': [min(e['time_seconds'] for e in events), max(e['time_seconds'] for e in events)]}
    if derivation:
        result['derivation'] = derivation
    return result


def collect_context(report, player, start, end):
    """Windowed command context only; no attack/unit-type/defensive-intent inference."""
    players = {p['id']: p for p in report['players']}
    base = player.get('base')
    nearby, defensive, activity, unknown = [], [], [], []
    for e in report['events']:
        if not start <= e['time_seconds'] <= end:
            continue
        if e.get('player_id') == player['id']:
            if e.get('action') in {'BUILD', 'RESEARCH', 'DE_QUEUE', 'QUEUE', 'MOVE', 'ORDER', 'SPECIAL', 'DE_ATTACK_MOVE', 'PATROL'}:
                activity.append(e['id'])
            if ((e.get('action') == 'SPECIAL' and e.get('order') == 'Garrison') or
                (e.get('action') == 'BUILD' and e.get('building') in {'Watch Tower', 'Guard Tower', 'Keep', 'Castle'})):
                defensive.append(e['id'])
        elif e.get('action') in {'MOVE', 'ORDER', 'PATROL', 'DE_ATTACK_MOVE', 'ATTACK_GROUND'}:
            actor = players.get(e.get('player_id'))
            if actor is None:
                unknown.append(e['id'])
                continue
            if team_key(actor) == team_key(player):
                continue
            pos = e.get('position')
            if base and pos and math.hypot(pos['x'] - base['x'], pos['y'] - base['y']) <= 18:
                nearby.append(e['id'])
    return {'rule_version': 1, 'window_seconds': [start, end],
            'opponent_near_base_event_ids': nearby, 'possible_adaptation_event_ids': defensive,
            'player_activity_event_ids': activity, 'unresolved_actor_event_ids': unknown,
            'aggression': 'possible_pressure' if nearby else 'unknown',
            'evidence_quality': quality(decoded=True, reason='Window searched for recorded commands; unit types, aggression severity, actual positions and defensive intent are unresolved. No cue does not establish safety.')}


def build_review(report: dict, player_name: str, plan: str = '', confirmed: bool = False) -> dict:
    """Generate at most one primary; do not use outcome flags or mutate the input."""
    result = {'coaching_schema_version': COACHING_VERSION, 'analysis_schema_version': report.get('schema_version'),
              'parser_pin': PARSER_PIN, 'match_id': report.get('match_id'),
              'player': None, 'plan': {'id': plan or None, 'status': 'confirmed' if confirmed else 'unconfirmed',
                                      'label': 'Franks — Scouts → Knights' if plan == PLAN else plan},
              'primary': None, 'secondary': [], 'what_went_well': [], 'practice_goals': [],
              'detectors': [], 'coverage': {}, 'indicators': {}, 'comparison_scope': None,
              'abstention_reason': None,
              'ranking_policy': ['evidence reliability (eligibility gate)', 'strategic relevance to confirmed plan',
                                 'player control', 'future practice usefulness', 'rule ID tie-break'],
              'ranking_note': 'Ordinal rule priorities, not measured impact on a loss. Outcomes are not ranking inputs.'}

    def abstain(reason):
        result['abstention_reason'] = reason
        return result

    if report.get('schema_version') != 5 or report.get('excerpt'):
        return abstain('Unsupported analysis version or incomplete excerpt. Inspect the full replay instead.')
    selected = [p for p in report.get('players', []) if p.get('name') == player_name]
    if len(selected) != 1:
        return abstain('Confirm one unambiguous player identity; no first-player assumption is made.')
    player = selected[0]
    result['player'] = {'id': player['id'], 'name': player_name}
    events = report.get('events', [])
    duration = report.get('duration_seconds')
    if (not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0 or
        any(not isinstance(e.get('id'), str) or not isinstance(e.get('time_seconds'), (int, float)) or
            not math.isfinite(e['time_seconds']) or not 0 <= e['time_seconds'] <= duration for e in events) or
        len({e['id'] for e in events}) != len(events)):
        return abstain('Invalid timestamps or duplicate/stale evidence IDs. Inspect the replay; no recommendation generated.')
    events = sorted(events, key=lambda e: (e['time_seconds'], e['id']))
    own = [e for e in events if e.get('player_id') == player['id']]

    def first(predicate):
        return next((e for e in own if predicate(e)), None)

    def age(name):
        return first(lambda e: e.get('action') == 'AGE_REACHED' and e.get('technology') == name and e.get('status') == 'observed_milestone')

    castle, feudal = age('Castle Age'), age('Feudal Age')
    knight = first(lambda e: e.get('kind') == 'queue_command' and e.get('action') in {'DE_QUEUE', 'QUEUE'} and e.get('unit') == 'Knight' and e.get('status') == 'command')
    research = first(lambda e: e.get('action') == 'RESEARCH' and e.get('technology') == 'Castle Age' and e.get('status') == 'command')
    interval = round(knight['time_seconds'] - castle['time_seconds'], 3) if castle and knight and knight['time_seconds'] >= castle['time_seconds'] else None
    result['indicators']['knight_after_castle_seconds'] = interval
    result['coverage']['command_stream'] = quality(decoded=True)
    result['coverage']['resources_and_queue_completion'] = quality(reason='Unavailable: no validated resource balances or queue completion reconstruction.')

    # A positive is a measured observation, not a declaration of good tactical play.
    if interval is not None and interval <= 30:
        result['what_went_well'].append(observation('prompt-knight-command',
            f'First recorded Knight queue command at {knight["time"]}, {interval:.1f}s after Castle arrival at {castle["time"]}. Prompt follow-up input, not confirmed production.',
            [castle, knight], derivation='Knight command time minus Castle milestone time.'))
    if castle and not result['what_went_well']:
        opponent_ages = [e for e in events if e.get('action') == 'AGE_REACHED' and e.get('technology') == 'Castle Age' and e.get('status') == 'observed_milestone' and
                         any(p['id'] == e.get('player_id') and team_key(p) != team_key(player) for p in report['players'])]
        if opponent_ages and castle['time_seconds'] < min(e['time_seconds'] for e in opponent_ages):
            opponent = min(opponent_ages, key=lambda e: e['time_seconds'])
            result['what_went_well'].append(observation('castle-milestone-lead',
                f'Castle milestone at {castle["time"]}, {opponent["time_seconds"] - castle["time_seconds"]:.1f}s before the earliest recorded opposing Castle milestone ({opponent["time"]}). A timing positive, not proof of a winning position.',
                [castle, opponent], derivation='Opposing Castle milestone time minus selected-player Castle milestone time.'))
    if castle and not result['what_went_well']:
        result['what_went_well'].append(observation('castle-milestone',
            f'Castle Age milestone is recorded at {castle["time"]}. This confirms the transition milestone, not its strategic quality.', [castle], 'parser_milestone'))

    applicable = player.get('civilization') == 'Franks' and report.get('map') == 'Arabia' and len(report['players']) == 2 and len({team_key(p) for p in report['players']}) == 2
    if not applicable:
        result['plan']['status'] = 'not_applicable'
        return abstain('This first coaching rule is limited to Arabia 1v1 Franks Scouts → Knights. Map/format/civilization differs; do not judge this game against that opening.')
    if plan != PLAN or not confirmed:
        return abstain('Confirm your player and that Scouts → Knights was the intended plan for this match. A usual strategy is not proof of this game’s intention.')
    if castle:
        context_end = min(duration, (knight['time_seconds'] if knight else castle['time_seconds']) + 60)
        context = collect_context(report, player, max(0, castle['time_seconds'] - 120), context_end)
        result['coverage']['context'] = context
    else:
        context = None
    if applicable:
        result['comparison_scope'] = {'player': player_name, 'civilization': 'Franks', 'map': 'Arabia',
                                      'format': '1v1', 'plan': PLAN, 'aggression': context['aggression'] if context else 'unknown',
                                      'duration_band': 'under_40_minutes' if duration < 2400 else '40_minutes_or_longer'}
    knight_quality = quality(decoded=interval is not None, complete=interval is not None,
                             reason='Both interval anchors decoded; first means first recorded, not guaranteed first in game. Missing records do not imply no production.' if interval is not None else 'Missing or inconsistent Castle/Knight anchors; no interval or production failure can be established.')
    result['detectors'].append({'rule_id': 'transition-coordination', 'rule_version': 1, 'evidence_quality': knight_quality,
                                'status': 'candidate' if interval is not None and interval > 90 else 'not_promoted',
                                'priority': [2, 2, 2, 2],
                                'reason': 'Specific transition practice with two decoded anchors.' if interval is not None and interval > 90 else 'No >90s review trigger, or insufficient anchors. Missing is not failure.'})
    long_feudal = bool(feudal and research and research['time_seconds'] - feudal['time_seconds'] > 480)
    result['detectors'].append({'rule_id': 'long-feudal-checkpoint', 'rule_version': 1,
                                'evidence_quality': quality(decoded=bool(feudal and research), complete=bool(feudal and research)),
                                'status': 'inspect_only' if long_feudal else 'not_promoted', 'priority': [2, 1, 1, 1],
                                'reason': 'Withheld: elapsed Feudal time alone does not identify a better decision; spending, aggression and intentional adaptation are unresolved.'})
    result['detectors'].append({'rule_id': 'tc-command-gap', 'rule_version': 1,
                                'evidence_quality': quality(reason='Initial TC command-gap proxy cannot establish queue contents or actual idle time.'),
                                'status': 'inspect_only', 'priority': [0, 1, 1, 1],
                                'reason': 'Not promoted: queue-command gaps alone are too weak for macro advice; inspect legacy evidence if useful.'})
    if interval is None or interval <= 90:
        return abstain('No sufficiently actionable transition recommendation in this narrow MVP. Retain the positive observation; extended Feudal time alone is not a mistake. Inspect the replay rather than invent advice.')

    goal = {'id': GOAL_ID, 'label': 'Perform one deliberate Castle-transition check next comparable game',
            'scope': result['comparison_scope'],
            'primary_measure': {'source': 'user_annotation', 'target': 'One check: TC queue, military queue, current threat, and follow-up or explicit adaptation.'},
            'supporting_indicator': {'name': 'Castle arrival → first recorded Knight queue command', 'baseline_seconds': interval,
                                     'automatic_success_target_seconds': None, 'missing_record_policy': 'Missing/censored or adaptation, not automatic failure.',
                                     'caveat': 'Shorter is not always better; this cannot measure TC idle time, completed production or checklist completion.'},
            'stop_or_adapt': 'If defense or a changed plan takes priority, record the adaptation instead of forcing Knights.'}
    result['practice_goals'] = [goal]
    adaptation = bool(context['possible_adaptation_event_ids'] or context['opponent_near_base_event_ids'])
    result['primary'] = {
        'id': f'transition-coordination:v1:{castle["id"]}', 'rule_id': 'transition-coordination', 'rule_version': 1,
        'state': 'review_question',
        'title': 'Review Castle-transition coordination under possible pressure' if adaptation else 'Rehearse a deliberate Castle-transition check',
        'observations': [observation('knight-command-interval',
            f'Castle milestone {castle["time"]}; first recorded Knight queue command {knight["time"]} ({interval:.1f}s later).',
            [castle, knight], derivation='Knight command time minus Castle milestone time; command, not completion.')],
        'evidence_quality': knight_quality,
        'interpretation': {'text': 'Defensive adaptation may explain this interval. Inspect the commands before deciding anything should change.' if adaptation else 'A transition checklist may help coordinate the follow-up. Timing alone cannot establish a mistake.',
                           'confidence': 'low',
                           'alternatives': ['Necessary defense or an intentional change of plan.', 'Resources or completed Stable availability may have constrained the follow-up.', 'Pre-existing queues, cancellations and command decoding may affect what is visible.']},
        'recommendation': {'action': 'At Castle arrival, check TC and military queues, current threat, and intended follow-up. If Knights remain appropriate and resources/production permit, issue the follow-up; otherwise choose a defensive adaptation and revisit the plan when safe.',
                           'conditions': ['Do not trade necessary defense for a timing target.', 'Confirm the actual situation in Replay; this is not a verdict that the interval was wrong.'],
                           'not_claimed': ['Cause of loss', 'Measured TC idle time', 'Confirmed attacks or infantry', 'Completed Knights', 'Affordability']},
        'supporting_context_event_ids': context['opponent_near_base_event_ids'],
        'counterevidence_event_ids': context['possible_adaptation_event_ids'],
        'context': context,
        'priority_reasons': ['Selected over long-Feudal timing: two decoded transition anchors support a specific repeatable check, while Feudal timing lacks a justified alternative decision.',
                             'Selected over TC-command gaps: observable command interval is more reliable than a queue-state proxy.',
                             'Relevant to the confirmed Franks Scouts → Knights transition; the checklist is under player control and useful for practice.',
                             'Possible defense and incomplete gameplay state keep this a low-confidence review question, not criticism.'],
        'practice_goal_ids': [GOAL_ID], 'replay_anchor': {'event_id': castle['id'], 'time_seconds': castle['time_seconds']}}
    result['detectors'][0]['status'] = 'selected_review_question'
    validate_review(result, report)
    return result


def validate_review(review, report):
    """Fail closed on broken primary contracts before exposing advice."""
    primary = review['primary']
    if primary is None:
        assert review['abstention_reason']
        return
    by_id = {e['id']: e for e in report['events']}
    assert primary['observations'] and primary['priority_reasons']
    assert primary['interpretation']['confidence'] and primary['interpretation']['alternatives']
    assert primary['recommendation']['action'] and primary['recommendation']['conditions']
    assert primary['practice_goal_ids'] and set(primary['practice_goal_ids']) <= {g['id'] for g in review['practice_goals']}
    for obs in primary['observations'] + review['what_went_well']:
        assert obs['event_ids'] and all(eid in by_id for eid in obs['event_ids'])
    for key in ('supporting_context_event_ids', 'counterevidence_event_ids'):
        assert all(eid in by_id for eid in primary[key])
    anchor = primary['replay_anchor']
    assert by_id[anchor['event_id']]['time_seconds'] == anchor['time_seconds']
    assert len(review['secondary']) <= 3 and len(review['practice_goals']) <= 2

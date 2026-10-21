"""Read-only balanced composition v1. Editorial reviewability, never measured impact.

Multiple source-bound observations/questions/practices; one initial selection. Does
not consume outcome, feedback, saved habits, observations or authored screenshot reviews.
"""
from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_left
from coaching import team_key
from gameplay_knowledge import local_pack
from situation_coaching import queue

VERSION = 1
MAX_REVISITS = 24
MAX_POSITIVES = 8
NEAR_END_SECONDS = 120
POLICY = ('Specific initial-base pressure/forward questions first (tier 4); named siege '
          'inputs next (3); unidentified tactical changes and related upgrades (2); '
          'investment/location questions (1); wall layouts (0). Anchors within 120 seconds '
          'of the recording end lose one tier, never excluded. Earlier anchor then source ID '
          'break ties. Editorial reviewability, not importance, damage, blame or player vision.')
TIER = dict(forward_castle=4, early_defense=4, transition_defense=4,
            forward_fortification=4, local_pressure=4, siege_recommitment=3,
            engagement_decision=2, upgrade_transition=2, military_sustainability=1,
            production_investment=1, map_control=1, walling=0)
QUESTIONS = {
    'siege_recommitment': 'Was the siege move supported, a safe advance, or a retreat?',
    'engagement_decision': 'What changed between the tactical order and the move or stop?',
    'military_sustainability': 'Could available forces cover this economy investment?',
    'production_investment': 'What demand or bottleneck would these production placements address?',
    'map_control': 'Was this distant placement worth supporting, or was a safer site available?',
    'walling': 'Would this wall request close the needed approach while preserving an exit?',
    'upgrade_transition': 'Was this upgrade timely for the army you could field?',
    'forward_castle': 'Was a builder contest feasible, or was a deliberate fallback safer?',
    'forward_fortification': 'Could you contest the construction, or secure another route?',
    'early_defense': 'What was threatened, and which defensive follow-up was feasible?',
    'transition_defense': 'How could the threatened area be covered during the age transition?',
    'local_pressure': 'Which asset needed covering, and what fallback was available?',
}


def _number(v):
    return type(v) in (int, float) and math.isfinite(v)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _clock(t):
    return f'{int(t//60)}:{int(t%60):02}'


def _scope(report, review, situation, gameplay):
    match = report.get('match_id')
    if (report.get('schema_version') != 5 or report.get('excerpt') or not isinstance(match, str)
            or len(match) != 64 or any(c not in '0123456789abcdef' for c in match)):
        raise ValueError('Complete content-identified schema-5 report required.')
    player = situation.get('player')
    players = report['players']
    if not player or sum(p.get('name') == player.get('name') for p in players) != 1:
        raise ValueError('Choose an unambiguous player.')
    if (any(type(p.get('id')) is not int for p in players) or len({p['id'] for p in players}) != len(players)
            or not any({k: p.get(k) for k in ('id', 'name', 'civilization')} == player for p in players)):
        raise ValueError('Player identity mismatch.')
    if (review.get('coaching_schema_version') != 1 or review.get('match_id') != match or review.get('player', {}).get('id') != player['id']
            or review.get('player', {}).get('name') != player['name']
            or situation.get('match_id') != match or situation.get('review_version') != 2
            or gameplay.get('match_id') != match or gameplay.get('schema_version') != 2
            or gameplay.get('player') != player or gameplay.get('causal_claim') is not False
            or gameplay.get('skill_rating') is not None or gameplay.get('validated_state_measurements') != []
            or gameplay.get('replay_build') != (report.get('replay_provenance') or {}).get('build_version')):
        raise ValueError('Source context mismatch.')
    duration = report.get('duration_seconds')
    events = report['events']
    if not _number(duration) or duration <= 0 or not isinstance(events, list) or len(events) > 300000:
        raise ValueError('Invalid bounded event stream.')
    actors = {p['id'] for p in players}
    by_id = {}
    for e in events:
        if (not isinstance(e, dict) or not isinstance(e.get('id'), str) or not e['id'] or e['id'] in by_id
                or not _number(e.get('time_seconds')) or not 0 <= e['time_seconds'] <= duration
                or e.get('player_id') is not None and (type(e['player_id']) is not int or e['player_id'] not in actors)
                or e.get('position') is not None and (not isinstance(e['position'], dict) or any(
                    not _number(e['position'].get(k)) or not 0 <= e['position'][k] <= 1000 for k in ('x', 'y')))):
            raise ValueError('Invalid event identity/time.')
        by_id[e['id']] = e
    return player, by_id, duration


def _facts(events):
    """Small literal descriptions, not summaries of completed actions."""
    parts = []
    for e in events[:2]:
        label = (f"{e['building']} placement request" if e.get('action') == 'BUILD' and e.get('building') else
                 f"{e['unit']} queue input" if queue(e) else
                 f"{e['technology']} research request" if e.get('action') == 'RESEARCH' and e.get('technology') else
                 f"{e.get('order') or e['action']} input")
        parts.append(f"{_clock(e['time_seconds'])} · {label}")
    return '; '.join(parts) + '.'


def _compose(report, review, situation, gameplay, journal):
    player, events, duration = _scope(report, review, situation, gameplay)
    suggestions = journal.get('suggestions', []) if journal.get('status') != 'unavailable' else []
    if (journal.get('current_match', {}).get('match_id') != report['match_id']
            or journal.get('current_match', {}).get('player') != player):
        raise ValueError('Practice identity mismatch.')
    practices = {s['id']: s for s in suggestions}
    revisits = []
    for kind, candidates in [('gameplay', gameplay.get('candidates', [])),
                             ('situation', situation.get('recommendations', []))]:
        for c in candidates[:MAX_REVISITS]:
            topic = c.get('topic')
            if topic not in QUESTIONS:
                continue
            anchor = c['replay_anchor']
            ids = c['event_ids']
            if (not ids or len(ids) > 2048 or len(set(ids)) != len(ids)
                    or any(i not in events for i in ids) or anchor['event_id'] not in ids
                    or events[anchor['event_id']]['time_seconds'] != anchor['time_seconds']):
                raise ValueError('Invalid source references.')
            if kind == 'gameplay' and (any(events[i].get('player_id') != player['id'] for i in ids)
                    or c.get('causal_claim') is not False or c.get('battle_outcome') != 'unknown'
                    or c.get('validated_state_measurements') != []):
                raise ValueError('Unqualified source state or actor.')
            if kind == 'situation' and events[anchor['event_id']].get('player_id') not in {p['id'] for p in report['players'] if p['id'] != player['id']}:
                raise ValueError('Invalid opponent anchor.')
            refs = list(dict.fromkeys([anchor['event_id'], *ids]))[:6]
            fact_ids = (c.get('recorded') or [{}])[0].get('event_ids', []) if kind == 'gameplay' else [anchor['event_id']]
            if any(i not in ids for i in fact_ids):
                raise ValueError('Unbound recorded facts.')
            fact_events = [events[i] for i in fact_ids[:2]]
            source = c.get('source')  # Absent legacy knowledge hashes remain absent.
            if kind == 'gameplay' and (not isinstance(source, dict)
                    or source.get('pack_version') != (1 if topic == 'siege_recommitment' else 2)
                    or not isinstance(source.get('pack_id'), str) or not source['pack_id']
                    or not isinstance(source.get('pack_sha256'), str) or len(source['pack_sha256']) != 64
                    or any(x not in '0123456789abcdef' for x in source['pack_sha256'])):
                raise ValueError('Missing source knowledge signature.')
            suggestion = practices.get(c['id'])
            if suggestion and (suggestion['source'].get('recommendation_id') != c['id']
                               or any(suggestion['source'].get(k) != c.get(k) for k in ('rule_id', 'rule_version', 'topic'))
                               or suggestion['source'].get('knowledge_pack_sha256') != (source or {}).get('pack_sha256')
                               or suggestion['evidence'] != [anchor]
                               or suggestion['action'] != c.get('practice_short')):
                raise ValueError('Practice does not match the source action.')
            window = c.get('window_seconds') or next(
                (e['window_seconds'] for e in situation.get('episodes', []) if e['id'] == c.get('episode_id')),
                [anchor['time_seconds'], anchor['time_seconds']])
            if (not isinstance(window, list) or len(window) != 2 or any(not _number(x) for x in window)
                    or not 0 <= window[0] <= anchor['time_seconds'] <= window[1] <= duration
                    or window[1] - window[0] > 300
                    or c['rule_version'] != (1 if topic == 'siege_recommitment' else 2)):
                raise ValueError('Unbound source window/rule version.')
            remaining = duration - anchor['time_seconds']
            tier = TIER[topic] - int(remaining <= NEAR_END_SECONDS)
            revisits.append(dict(id=c['id'], source_kind=kind, topic=topic, rule_id=c['rule_id'],
                rule_version=c['rule_version'], source_signature=source, title=QUESTIONS[topic],
                recorded=('Own inputs: ' if kind == 'gameplay' else 'Other-player input (retrospective): ') + _facts(fact_events), question=c['question'], replay_anchor=anchor,
                event_ids=refs, window_seconds=window,
                practice_id=suggestion['id'] if suggestion else None, editorial_tier=tier,
                recording_seconds_remaining=remaining,
                selection_reason=f'Editorial tier {tier}; ' + ('near recording end, not proof of cleanup. ' if remaining <= NEAR_END_SECONDS else '') +
                    'Inputs identify a question, not a demonstrated error or cause.'))
    if len({r['id'] for r in revisits}) != len(revisits):
        raise ValueError('Duplicate decision identities.')
    revisits.sort(key=lambda c: (-c['editorial_tier'], c['replay_anchor']['time_seconds'], c['id']))
    total = len(revisits)
    revisits = revisits[:MAX_REVISITS]
    positives = _positives(report, situation, player, events)
    main = next(iter(revisits), None)
    # Prefer a related observation, then protective/follow-through inputs; never outcome.
    def positive_key(p):
        related = bool(main and any(max(0, main['window_seconds'][0] - 120) <= events[i]['time_seconds'] <= min(duration, main['window_seconds'][1] + 120) for i in p['event_ids'] if events[i]['player_id'] == player['id']))
        return (-int(related), -int(p['kind'] != 'age_lead'), events[p['event_ids'][0]]['time_seconds'], p['id'])
    positives.sort(key=positive_key)
    allowed = {r['practice_id'] for r in revisits if r['practice_id']}
    practice_ids = [s['id'] for s in suggestions if s['id'] in allowed]
    scope = ['Commands and milestones, not completed production, forces, affordability or battle outcomes.']
    if len(report['players']) != 2:
        scope.append('Team coordination and individual contribution are not assessed.')
    # Do not infer water control from a map name or claim naval coverage from land checks.
    naval = any(e.get('building') == 'Dock' or e.get('unit') in {'Fishing Ship', 'Galley', 'War Galley', 'Galleon', 'Fire Galley', 'Fire Ship', 'Demolition Raft', 'Transport Ship'} for e in events.values())
    if naval or report.get('map') in {'Northern Isles', 'Islands', 'Team Islands', 'Baltic', 'Mediterranean', 'Archipelago'}:
        scope.append('Water/naval decisions are not comprehensively assessed by these checkpoints.')
    out = dict(schema_version=VERSION, policy_version=VERSION, status='available', match_id=report['match_id'],
        replay_build=(report.get('replay_provenance') or {}).get('build_version'), player=player,
        positives=positives[:MAX_POSITIVES], primary_positive_id=positives[0]['id'] if positives else None,
        revisits=revisits, primary_revisit_id=main['id'] if main else None,
        practice_ids=practice_ids, primary_practice_id=main['practice_id'] if main else None,
        selection_policy=POLICY, scope_notes=scope, causal_claim=False, skill_improvement_established=False,
        coverage=dict(revisit_limit=MAX_REVISITS, revisits_truncated=total > MAX_REVISITS,
                      positive_limit=MAX_POSITIVES, positives_truncated=len(positives) > MAX_POSITIVES,
                      garrison_selection='First and latest associated protective input; not every garrison.',
                      positive_selection='Prefer own evidence within two minutes of the selected window; then protective/follow-through inputs, earlier time and ID. Association is not causation.',
                      positive_scope='Castle/Imperial prompt known-military follow-up, Castle timing lead in unambiguous 1v1, associated garrison inputs.'))
    # IDs do not depend on journal state, custom prose, feedback, results or filenames.
    out['id'] = 'takeaway:' + _hash([VERSION, report['match_id'], player['id'],
        [(r['id'], r['rule_id'], r['rule_version'], r['source_signature']) for r in revisits], positives])[:24]
    return out


def _positives(report, situation, player, events):
    own = sorted((e for e in events.values() if e.get('player_id') == player['id']), key=lambda e: (e['time_seconds'], e['id']))
    out = []
    def add(kind, text, caveat, refs, derivation):
        out.append(dict(id='keep:' + _hash([VERSION, report['match_id'], player['id'], kind, refs])[:24],
                        kind=kind, text=text, caveat=caveat, event_ids=refs, derivation=derivation))
    associated = {r['event_id'] for i in situation.get('incidents', []) for r in i.get('responses', [])}
    garrisons = [e for e in own if e['id'] in associated and e.get('status') == 'command' and e.get('order') == 'Garrison']
    for e in {e['id']: e for e in [*garrisons[:1], *garrisons[-1:]]}.values():
        add('protective_input', f"At {_clock(e['time_seconds'])}, a garrison input was recorded in the pressure review window.",
            'A protective input, not proof that workers survived or returned to work.', [e['id']], 'Own Garrison input associated with an existing incident response.')
    try:
        pack, _ = local_pack(2)
        known = {u for f in pack['families'] for u in f['units']} | {r['name'] for r in pack['roles'] if r['kind'] == 'Unit'} | set(pack.get('additional_military_aliases', []))
    except (OSError, ValueError, KeyError, TypeError):
        known = set()
    queues = [e for e in own if queue(e) and e.get('unit') in known]
    times = [e['time_seconds'] for e in queues]
    for age in ['Castle Age', 'Imperial Age']:
        arrivals = [e for e in own if e.get('action') == 'AGE_REACHED' and e.get('technology') == age and e.get('status') == 'observed_milestone']
        if len(arrivals) != 1:
            continue
        e = arrivals[0]; index = bisect_left(times, e['time_seconds'])
        if index < len(queues) and queues[index]['time_seconds'] - e['time_seconds'] <= 30:
            q = queues[index]; delta = q['time_seconds'] - e['time_seconds']
            add('prompt_followup', f"A {q['unit']} queue input followed {age} arrival by about {delta:.0f} seconds.",
                'Prompt follow-up input, not completed production or proof the choice was strategically best.',
                [e['id'], q['id']], 'First recognized military queue after this recorded age milestone, within 30 seconds.')
        if age == 'Castle Age' and len(report['players']) == 2:
            selected = next(p for p in report['players'] if p['id'] == player['id'])
            opponent = next(p for p in report['players'] if p['id'] != player['id'])
            a, b = selected.get('team_id'), opponent.get('team_id')
            # Mixed representations/overlapping memberships are not known opposition.
            if type(a) is not type(b):
                continue
            if isinstance(a, list):
                if any(type(x) is not int for x in [*a, *b]) or a != [selected['id']] or b != [opponent['id']]:
                    continue
            elif type(a) is not int or a <= 0 or b <= 0:
                continue
            if team_key(selected) == team_key(opponent):
                continue
            opposing = [x for x in events.values() if x.get('player_id') == opponent['id'] and x.get('action') == 'AGE_REACHED' and x.get('technology') == age and x.get('status') == 'observed_milestone']
            if len(opposing) == 1 and opposing[0]['time_seconds'] > e['time_seconds']:
                o = opposing[0]
                add('age_lead', f"Recorded Castle arrival: {_clock(e['time_seconds'])}, before the opponent's {_clock(o['time_seconds'])}.",
                    "A retrospective timing lead, not proof of good strategy or information you had then. Don't force faster aging.",
                    [e['id'], o['id']], 'Opposing Castle milestone minus own Castle milestone; unambiguous opposing 1v1 identities.')
    return out


def build(report, review, situation, gameplay, journal):
    """Optional composition fails closed; no store, network, OCR or process operations."""
    try:
        return _compose(report, review, situation, gameplay, journal)
    except (ValueError, TypeError, KeyError, AttributeError, StopIteration, OSError):
        return dict(schema_version=VERSION, policy_version=VERSION, status='unavailable',
                    match_id=report.get('match_id'), player=None, positives=[], revisits=[], practice_ids=[],
                    primary_positive_id=None, primary_revisit_id=None, primary_practice_id=None,
                    causal_claim=False, skill_improvement_established=False,
                    reason='Balanced composition unavailable or source identity mismatch; existing command reviews remain available.')

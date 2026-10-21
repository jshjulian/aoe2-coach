"""Compact review composition v2 over EXISTING incident evidence, not new detectors.

Episode association is temporal/spatial, never causal. No result/plan inputs.
Editorial priorities describe reviewability/possible stakes, not measured impact.
"""
from __future__ import annotations

import math

REVIEW_VERSION = 2
AGES = {'Dark Age': 1, 'Feudal Age': 2, 'Castle Age': 3, 'Imperial Age': 4}
CIVILIAN = {'Villager', 'Trade Cart', 'Trade Cog', 'Fishing Ship', 'Transport Ship'}


def queue(e):
    amount = e.get('amount')
    return (e.get('status') == 'command' and e.get('action') in ('QUEUE', 'DE_QUEUE') and
            e.get('kind') == 'queue_command' and isinstance(e.get('unit'), str) and
            (amount is None or type(amount) in (int, float) and math.isfinite(amount) and amount > 0))


def military(e):
    return queue(e) and e['unit'] not in CIVILIAN


def distance(a, b):
    return math.hypot(a['x']-b['x'], a['y']-b['y'])


def names(events, field):
    return list(dict.fromkeys(e[field] for e in events if e.get(field)))


def short_list(values):
    return ', '.join(values[:3]) + (' and other inputs' if len(values) > 3 else '')


def anchor_position(incident):
    return next(row['position'] for row in incident['locations'] if row['event_id'] == incident['replay_anchor']['event_id'])


def compose_review(report, review):
    """Add a presentation/recommendation layer; retain every raw incident and ID."""
    review.update(review_version=REVIEW_VERSION, episodes=[], positive=None, timeline=[])
    player = review.get('player')
    if not player or not review['incidents']:
        if player:
            review['timeline'] = timeline(report, review)
            review['positive'] = positive(report, review)
        return
    ordered = sorted(report['events'], key=lambda e: (e['time_seconds'], e['id']))
    by_id = {e['id']: e for e in ordered}
    own = [e for e in ordered if e.get('player_id') == player['id']]
    ages = [e for e in own if e.get('action') == 'AGE_REACHED' and e.get('status') == 'observed_milestone' and e.get('technology') in AGES]
    phases = [AGES[e['technology']] for e in ages]
    valid_phases = phases == sorted(set(phases))
    # Merge bounded, same-opponent nearby episodes. No unbounded transitive chain.
    groups = []
    for incident in sorted(review['incidents'], key=lambda i: (i['window_seconds'][0], i['id'])):
        group = next((g for g in reversed(groups) if g[0]['participants'] == incident['participants'] and
                      incident['window_seconds'][0] - max(i['window_seconds'][1] for i in g) <= 120 and
                      max(incident['window_seconds'][1], max(i['window_seconds'][1] for i in g))-g[0]['window_seconds'][0] <= 300 and
                      any(distance(anchor_position(incident), anchor_position(i)) <= 24 for i in g)), None)
        if group is None:
            group = []
            groups.append(group)
        group.append(incident)
    for group in groups:
        start, end = min(i['window_seconds'][0] for i in group), max(i['window_seconds'][1] for i in group)
        forward = [i for i in group if i['type'] == 'forward_build_command']
        castles = [i for i in forward if by_id[i['replay_anchor']['event_id']].get('building') == 'Castle']
        pressures = [i for i in group if i['type'] == 'localized_opponent_commands']
        anchor_incident = (castles or forward or sorted(group, key=lambda i: i['replay_anchor']['time_seconds']))[0]
        anchor = anchor_incident['replay_anchor']
        age = max((AGES[e['technology']] for e in ages if e['time_seconds'] <= anchor['time_seconds']), default=0) if valid_phases else 0
        responses = list(dict.fromkeys(r['event_id'] for i in group for r in i['responses']))
        garrisons = [by_id[id_] for id_ in responses if by_id[id_].get('order') == 'Garrison']
        lo, hi = max(0, start-30), min(report['duration_seconds'], end+120)
        context = [e for e in own if lo <= e['time_seconds'] <= hi and e.get('status') == 'command' and
                   (military(e) or e.get('action') == 'RESEARCH' or
                    e.get('action') == 'BUILD' and e.get('building') not in {'Farm', 'House'})]
        production = [e for e in context if military(e)]
        structures = [e for e in context if e.get('action') == 'BUILD']
        researches = [e for e in context if e.get('action') == 'RESEARCH']
        response_parts = []
        if garrisons: response_parts.append('garrison orders')
        if production: response_parts.append(short_list(names(production, 'unit')) + ' queue commands')
        if structures: response_parts.append(short_list(names(structures, 'building')) + ' placement commands')
        if researches: response_parts.append(short_list(names(researches, 'technology')) + ' research commands')
        response_summary = ('Recorded nearby in time: ' + '; '.join(response_parts) + '. Queue/research inputs are not located at the incident or confirmed completed.' if response_parts else
                            'No defensive construction, garrison or military queue input was identified in this review window. Existing defenses and unrecorded responses remain unknown.')
        if castles:
            topic, title = 'forward_castle', 'Decide whether to contest the forward Castle'
            summary = 'An opponent Castle placement was requested near your starting base' + (' after nearby opponent orders.' if pressures else '.') + ' Review which territory was exposed and whether contesting the builders was feasible.'
            question = 'If you saw the foundation, could available forces safely contest the builders before completion? If not, which exposed workers or production should reposition, and where could you defend without taking a bad fight?'
            exercise = 'When you spot a forward Castle foundation, make one explicit choice: contest builders only with a feasible local advantage, or move exposed workers/army and choose a fallback position. Recheck the decision once its actual completion is known.'
            principle = 'Treat forward construction as a territory decision, not an automatic instruction to fight under a Castle.'
        elif forward:
            topic, title = 'forward_fortification', 'Protect access around the forward fortification'
            summary = 'An opponent defensive-building placement was requested near your starting base. Check access to nearby resources and safe routes before committing a response.'
            question = 'If the placement was visible, was there a safe chance to deny construction, or was shifting workers and defending another route the better available choice?'
            exercise = 'On seeing a forward fortification, identify one threatened route or resource and one safe alternative. Contest only if local forces and terrain support it; otherwise reposition deliberately.'
            principle = 'Preserve useful access rather than committing to a building fight by default.'
        elif age in (1, 2):
            topic, title = 'early_defense', 'Protect workers while choosing your defensive follow-up'
            summary = 'Repeated opponent orders were recorded near your starting base' + (' alongside garrison orders.' if garrisons else '.') + ' Review worker safety, defensive army choices and keeping the economy working where safe.'
            question = 'What was actually visible? Could your available army and completed defenses protect the working economy, or did exposed workers need to move? Check whether your chosen production matched the scouted threat before returning workers safely.'
            exercise = 'At the next visible early raid: protect exposed workers, choose a defensive follow-up based on what you scouted and can actually produce, then check queues and return safe workers to work. Do not force a timing target through necessary defense.'
            principle = 'Defend the working economy, then deliberately restore continuity; garrison input alone does not prove safety or recovery.'
        else:
            transition = any(e.get('action') == 'AGE_REACHED' and e.get('status') == 'observed_milestone' and start-90 <= e['time_seconds'] <= end+120 for e in own)
            topic = 'transition_defense' if transition else 'local_pressure'
            title = 'Coordinate defense with the age transition' if transition else 'Choose where to defend the nearby pressure'
            summary = 'Repeated opponent orders were recorded near your starting base' + (' during an age transition.' if transition else '.') + ' Check what was threatened before committing the next army or production input.'
            question = 'Which assets were actually exposed, and could completed forces cover them? Review whether to concentrate defense, reposition, or continue production elsewhere; nearby commands alone cannot identify the best choice.'
            exercise = ('At an age arrival under visible pressure, check the threatened area before choosing upgrades or new queues. Name the defense you can field now and the follow-up you can support.' if transition else
                        'When nearby pressure is visible, choose one asset or route to defend and a fallback position. Check local forces and resources before adding production; review what happened before deciding the choice was wrong.')
            principle = 'Coordinate the forces and infrastructure you actually have with the territory you choose to defend.'
        evidence_ids = list(dict.fromkeys([id_ for i in group for id_ in i['event_ids']] + [e['id'] for e in context]))
        # No command-count/placement-first severity score. Distinct possible stakes
        # and actual decision context take precedence over isolated type labels.
        stakes = 2 if (castles and pressures) or (topic == 'early_defense' and garrisons) else 1
        decision_context = int(bool(responses)) + int(bool(production or structures or researches))
        priority = [stakes, decision_context, int(bool(garrisons)), int(topic == 'early_defense')]
        reasons = [('Possible worker exposure with garrison input.' if topic == 'early_defense' and garrisons else
                    'Nearby orders and forward Castle construction describe a combined territory decision.' if castles and pressures else
                    'Positive command evidence identifies a reviewable local decision; consequences are unverified.'),
                   ('Recorded responses/production context make the choices inspectable; command counts do not measure severity.' if decision_context else
                    'The positive placement/order command supplies a concrete anchor; readiness, responses and consequences remain unresolved.'),
                   'Earlier moments break equal-priority ties. Results, missing commands and automatic building-type precedence are not ranking inputs.']
        episode = {'id': anchor_incident['id'] + ':episode-v2', 'incident_ids': [i['id'] for i in group],
                   'topic': topic, 'window_seconds': [start, end], 'review_window_seconds': [lo, hi],
                   'replay_anchor': anchor, 'event_ids': evidence_ids, 'response_event_ids': responses,
                   'context_event_ids': [e['id'] for e in context], 'priority_dimensions': priority,
                   'priority_reasons': reasons, 'participants': anchor_incident['participants']}
        review['episodes'].append(episode)
        episode['recommendation'] = {'id': episode['id'] + ':' + topic, 'rule_id': topic + '-review', 'rule_version': REVIEW_VERSION,
            'kind': 'review_question', 'incident_id': anchor_incident['id'], 'episode_id': episode['id'], 'topic': topic,
            'title': title, 'summary': summary, 'response_summary': response_summary,
            'uncertainty_label': 'Possible forward construction — completion unverified' if forward else 'Possible pressure — combat unverified',
            'replay_anchor': anchor, 'event_ids': evidence_ids, 'question': question, 'principle': principle,
            'exercise': exercise, 'practice_short': (
                'On spotting a Castle foundation: choose either a feasible builder contest or a deliberate worker/army retreat to a fallback position.' if topic == 'forward_castle' else
                'At the next visible raid: protect exposed workers, choose one feasible defensive follow-up, then check queues and return safe workers to work.' if topic == 'early_defense' else
                'Identify the threatened route and a safe alternative. Contest construction only if local forces support it; otherwise reposition.' if topic == 'forward_fortification' else
                'At age arrival under pressure, check the threatened area, available defense and feasible follow-up before spending.' if topic == 'transition_defense' else
                'Choose one asset to defend and a fallback position. Check available forces before adding production.'), 'priority_reasons': reasons,
            'uncertainties': ['Opponent commands may not have been visible. Unit types at the incident, completed defenses, resources and consequences remain unverified.',
                              'Nearby queue/research commands do not prove a local response, successful defense, economic disruption or recovery.']}
    ranked = sorted(review['episodes'], key=lambda e: (*[-v for v in e['priority_dimensions']], e['replay_anchor']['time_seconds'], e['id']))
    review['recommendations'], review['decisions'] = [], []
    topics = set()
    for episode in ranked:
        family = 'territory' if episode['topic'] in {'forward_castle', 'forward_fortification'} else 'defense'
        same_topic = family in topics
        materially_distinct = (not review['recommendations'] or family == 'territory' or
                               episode['topic'] in {'early_defense', 'transition_defense'} or bool(episode['response_event_ids']))
        selected = not same_topic and materially_distinct and len(review['recommendations']) < 2
        review['decisions'].append({'incident_id': episode['recommendation']['incident_id'], 'episode_id': episode['id'],
                                    'status': 'selected' if selected else 'withheld', 'reason':
                                    'Same coaching decision already represented; retained in the timeline/evidence.' if same_topic else
                                    'No sufficiently distinct second decision; retained in the timeline/evidence.' if not materially_distinct else
                                    'Two-topic review budget reached.' if not selected else 'Distinct decision with inspectable evidence and possible stakes; not measured damage.'})
        if selected:
            topics.add(family)
            review['recommendations'].append(episode['recommendation'])
    review['ranking_policy'] = ['merge same-opponent nearby episodes, bounded to five minutes; preserve raw incidents',
                                'possible stakes plus recorded decision context, not command volume or building-type precedence',
                                'earlier anchor breaks ties; one primary and at most one materially different secondary topic']
    review['positive'] = positive(report, review)
    review['timeline'] = timeline(report, review)


def positive(report, review):
    own = sorted([e for e in report['events'] if e.get('player_id') == review['player']['id']], key=lambda e: (e['time_seconds'], e['id']))
    associated = {id_ for i in review['incidents'] for id_ in [r['event_id'] for r in i['responses']]}
    garrison = next((e for e in own if e['id'] in associated and e.get('order') == 'Garrison'), None)
    if garrison:
        return {'text': 'Garrison orders were recorded during the pressure window.',
                'caveat': 'A protective input to review, not proof that workers survived or returned to work.', 'event_ids': [garrison['id']]}
    castle = next((e for e in own if e.get('action') == 'AGE_REACHED' and e.get('technology') == 'Castle Age' and e.get('status') == 'observed_milestone'), None)
    follow = next((e for e in own if castle and military(e) and e['time_seconds'] >= castle['time_seconds']), None)
    if castle and follow and follow['time_seconds']-castle['time_seconds'] <= 30:
        return {'text': f"{follow['unit']} queue input followed Castle arrival within {follow['time_seconds']-castle['time_seconds']:.0f} seconds.",
                'caveat': 'Prompt follow-up input; production completion and strategic quality remain unverified.', 'event_ids': [castle['id'], follow['id']]}
    return None


def timeline(report, review):
    """Markers from recorded milestones/positive queues/existing incident outputs."""
    if not review.get('player'):
        return []
    markers, seen = [], set()
    own_id = review['player']['id']
    def add(e, kind, label, **extra):
        markers.append({'id': kind+':'+e['id'], 'event_id': e['id'], 'time_seconds': e['time_seconds'],
                        'kind': kind, 'label': label, 'player_id': e.get('player_id'), 'position': e.get('position'), **extra})
    phase = 'unknown'
    marked_responses = set()
    for e in sorted(report['events'], key=lambda e: (e['time_seconds'], e['id'])):
        if e.get('action') == 'AGE_REACHED' and e.get('status') == 'observed_milestone':
            if e.get('player_id') == own_id:
                phase = e.get('technology', 'unknown')
            add(e, 'age', ('You: ' if e.get('player_id') == own_id else 'Other player: ') + e.get('technology', 'Age milestone'))
        if e.get('player_id') == own_id and military(e) and (phase, e['unit']) not in seen:
            seen.add((phase, e['unit']))
            add(e, 'production', e['unit'] + ' queue begins (recorded input)')
        if e.get('player_id') == own_id and e.get('status') == 'command':
            if e.get('action') == 'BUILD' and e.get('building') in {'Watch Tower', 'Guard Tower', 'Keep', 'Castle'} and e.get('counted_as_new_placement') is not False:
                add(e, 'response', (e.get('building') or 'Wall') + ' placement input (intent unverified)')
                marked_responses.add(e['id'])
            if e.get('action') == 'RESEARCH' and e.get('technology') in {'Crossbowman', 'Arbalester', 'Pikeman', 'Halberdier', 'Man-at-Arms', 'Men-at-Arms', 'Long Swordsman', 'Two-Handed Swordsman', 'Champion', 'Light Cavalry', 'Hussar', 'Cavalier', 'Paladin', 'Elite Skirmisher'}:
                add(e, 'production', e['technology'] + ' research requested')
    responses = marked_responses
    by_id = {e['id']: e for e in report['events']}
    for incident in review['incidents']:
        e = by_id[incident['replay_anchor']['event_id']]
        add(e, 'forward' if incident['type'] == 'forward_build_command' else 'pressure',
            'Possible forward ' + e.get('building', 'construction') if incident['type'] == 'forward_build_command' else 'Possible pressure near starting base', incident_id=incident['id'])
        for row in incident['responses']:
            if row['event_id'] in responses: continue
            responses.add(row['event_id'])
            e = by_id[row['event_id']]
            add(e, 'response', 'Garrison order' if e.get('order') == 'Garrison' else (e.get('building') or 'Wall') + ' placement input')
    return sorted(markers, key=lambda m: (m['time_seconds'], m['id']))

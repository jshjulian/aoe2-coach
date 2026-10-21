#!/usr/bin/env python3
"""Offline Track B experiment. NEVER imported by the app or used as coaching state.

Extract uncertain mgz sync counters; compare explicit manual HUD observations.
Even perfect agreement stays research-only, not authoritative state validation.
No network, game/CA launch, memory hooks, remote code or SQLite writes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import stable_match_id
from replay_provenance import read_provenance

VERSION = 1
RESOURCE_FIELDS = ('food', 'wood', 'gold', 'stone')
LIMITATIONS = [
    'Sync fields are explicitly described as guesses by the parser; semantics are not independently validated.',
    'The sync current_time clock is an unvalidated alignment hypothesis, not automatically the displayed HUD clock.',
    'Resource-sum agreement cannot recover four resource balances or validate every patch/mode.',
    'HUD display rounding, carrying resources, gathers/spending between samples and clock quantization can affect errors.',
    'Missing sync rows are not zeros; the parser omits rows when its candidate resource slot is zero.',
    'The object counter is not villagers alive, military population, completed buildings or farms.',
    'Point samples cannot establish TC idle durations, active production, worker idle time or economic recovery.',
]


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def signature(path):
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def extract(path):
    from mgz.model import parse_match
    import mgz.fast
    before = signature(path)
    match_id = stable_match_id(path)
    provenance = read_provenance(path)
    with path.open('rb') as stream:
        match = parse_match(stream)
    if signature(path) != before:
        raise ValueError('Replay changed while extracting; retry with a completed recording.')
    fast_path = Path(mgz.fast.__file__)
    direct_url = importlib.metadata.distribution('mgz').read_text('direct_url.json')
    source = json.loads(direct_url) if direct_url else {}
    return {'schema_version': 1, 'tool_version': VERSION, 'kind': 'unvalidated_mgz_sync_candidates',
            'qualification': 'research_only_not_coaching_state', 'match_id': match_id,
            'extracted_at': datetime.now(timezone.utc).isoformat(),
            'duration_seconds': match.duration.total_seconds(), 'replay_provenance': provenance,
            'parser': {'package_version': importlib.metadata.version('mgz'),
                       'commit': source.get('vcs_info', {}).get('commit_id'),
                       'fast_module_sha256': hashlib.sha256(fast_path.read_bytes()).hexdigest()},
            'time_basis': 'DE sync current_time milliseconds divided by 1000; HUD alignment unvalidated',
            'limitations': list(LIMITATIONS),
            'players': [{'id': int(p.number), 'name': p.name, 'civilization': p.civilization,
                         'rows': [{'time_seconds': row.timestamp.total_seconds(),
                                   'resource_sum_candidate': row.total_resources,
                                   'object_counter_candidate': row.total_objects} for row in p.timeseries]} for p in match.players]}


def validate_candidate(candidate):
    if not isinstance(candidate, dict) or candidate.get('schema_version') != 1 or candidate.get('kind') != 'unvalidated_mgz_sync_candidates':
        raise ValueError('Expected the version-1 research candidate format.')
    if (not isinstance(candidate.get('match_id'), str) or len(candidate['match_id']) != 64 or
        any(c not in '0123456789abcdef' for c in candidate['match_id']) or not number(candidate.get('duration_seconds'))):
        raise ValueError('Invalid content identity or duration.')
    if not isinstance(candidate.get('replay_provenance'), dict):
        raise ValueError('Expected actual replay provenance, not a filename-derived version.')
    players = candidate.get('players')
    if (not isinstance(players, list) or any(not isinstance(p, dict) or type(p.get('id')) is not int or not 1 <= p['id'] <= 8 or not isinstance(p.get('name'), str) for p in players) or
        len({p['id'] for p in players}) != len(players)):
        raise ValueError('Ambiguous player IDs.')
    for player in players:
        if not isinstance(player.get('rows'), list) or any(not isinstance(row, dict) or not all(number(row.get(field)) for field in
            ('time_seconds', 'resource_sum_candidate', 'object_counter_candidate')) for row in player['rows']):
            raise ValueError('Invalid candidate counters or timestamps.')
        if len({r['time_seconds'] for r in player['rows']}) != len(player['rows']):
            raise ValueError('Duplicate sync timestamps require manual inspection.')


def template(candidate, player_id, times):
    validate_candidate(candidate)
    players = [p for p in candidate['players'] if p['id'] == player_id]
    if len(players) != 1 or not players[0]['rows']:
        raise ValueError('Select a player with recorded sync candidates.')
    player = players[0]
    rows = []
    for seconds in times:
        if not number(seconds) or seconds > candidate['duration_seconds']:
            raise ValueError('Requested checkpoint outside recording duration.')
        row = min(player['rows'], key=lambda r: (abs(r['time_seconds']-seconds), r['time_seconds']))
        if row['time_seconds'] > candidate['duration_seconds']:
            continue
        if row['time_seconds'] in {r['suggested_sync_time_seconds'] for r in rows}:
            continue
        rows.append({'suggested_sync_time_seconds': row['time_seconds'], 'time_seconds': None, 'player_id': player_id, 'player_name': player['name'],
                     'evidence_ref': None, 'food': None, 'wood': None, 'gold': None, 'stone': None})
    return {'schema_version': 1, 'match_id': candidate['match_id'],
            'build_version': candidate['replay_provenance'].get('build_version'),
            'reference': {'provider': None, 'provider_version': None, 'clock_basis': 'aoe_game_seconds',
                          'clock_resolution_seconds': None},
            'instructions': 'Fill from paused game HUD or CaptureAge UI. Do NOT copy candidate values. Keep a screenshot/reference with player identity and visible game clock. suggested_sync_time_seconds is only a seek hint. Fill time_seconds from the actual displayed HUD clock, with its true precision; do not copy a fractional candidate timestamp.',
            'checkpoints': rows}


def compare(candidate, reference, max_delta_seconds=0.5):
    validate_candidate(candidate)
    if not number(max_delta_seconds):
        raise ValueError('Alignment tolerance must be finite and nonnegative.')
    if not isinstance(reference, dict) or reference.get('schema_version') != 1 or reference.get('match_id') != candidate['match_id']:
        raise ValueError('Reference content identity differs or schema unsupported.')
    build = candidate.get('replay_provenance', {}).get('build_version')
    if type(build) is not int or type(reference.get('build_version')) is not int or reference['build_version'] != build:
        raise ValueError('Actual replay build must be known and agree with the reference.')
    source = reference.get('reference') or {}
    points = reference.get('checkpoints')
    if not isinstance(source, dict) or not isinstance(points, list) or any(not isinstance(p, dict) for p in points):
        raise ValueError('Expected reference metadata and a list of checkpoint objects.')
    source_ready = (source.get('provider') in ('game_hud', 'captureage_ui') and
                    isinstance(source.get('provider_version'), str) and bool(source['provider_version'].strip()) and
                    source.get('clock_basis') == 'aoe_game_seconds' and number(source.get('clock_resolution_seconds')))
    players = {p['id']: p for p in candidate['players']}
    rows, errors, seen = [], [], set()
    for point in points:
        player_id, seconds = point.get('player_id'), point.get('time_seconds')
        if type(player_id) is not int or player_id not in players or point.get('player_name') != players[player_id]['name']:
            raise ValueError('Checkpoint player ID/name does not match the recording.')
        if seconds is not None:
            if not number(seconds) or seconds > candidate['duration_seconds'] or (player_id, seconds) in seen:
                raise ValueError('Invalid/out-of-range or duplicate checkpoint timestamp.')
            seen.add((player_id, seconds))
        values = [point.get(field) for field in RESOURCE_FIELDS]
        if any(v is not None and not number(v) for v in values) or (all(v is not None for v in values) and not number(sum(values))):
            raise ValueError('HUD resource values must be nonnegative finite numbers or null.')
        row = {'player_id': player_id, 'reference_time_seconds': seconds, 'status': 'missing_reference',
               'candidate_time_seconds': None, 'clock_delta_seconds': None, 'reference_sum': None,
               'candidate_sum': None, 'signed_error': None, 'absolute_error': None}
        if seconds is not None and all(v is not None for v in values) and source_ready and isinstance(point.get('evidence_ref'), str) and point['evidence_ref'].strip():
            row['reference_sum'] = sum(values)
            nearby = [r for r in players[player_id]['rows'] if abs(r['time_seconds']-seconds) <= max_delta_seconds]
            if not nearby:
                row['status'] = 'no_candidate_within_alignment_tolerance'
            else:
                closest = min(nearby, key=lambda r: (abs(r['time_seconds']-seconds), r['time_seconds']))
                error = closest['resource_sum_candidate']-row['reference_sum']
                row.update(status='compared_under_unvalidated_clock_hypothesis', candidate_time_seconds=closest['time_seconds'],
                           clock_delta_seconds=round(closest['time_seconds']-seconds, 6), candidate_sum=closest['resource_sum_candidate'],
                           signed_error=error, absolute_error=abs(error))
                errors.append(abs(error))
        rows.append(row)
    return {'schema_version': 1, 'tool_version': VERSION, 'match_id': candidate['match_id'], 'build_version': build,
            'qualification': 'research_only_not_coaching_state', 'validated_for_application': False,
            'max_delta_seconds': max_delta_seconds, 'reference': source, 'checkpoints': rows,
            'summary': {'requested': len(rows), 'compared': len(errors), 'missing_or_unmatched': len(rows)-len(errors),
                        'mean_absolute_error': statistics.mean(errors) if errors else None,
                        'median_absolute_error': statistics.median(errors) if errors else None,
                        'max_absolute_error': max(errors) if errors else None}, 'limitations': list(LIMITATIONS)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest='command', required=True)
    extract_cli = commands.add_parser('extract'); extract_cli.add_argument('replay', type=Path)
    template_cli = commands.add_parser('template'); template_cli.add_argument('candidate', type=Path)
    template_cli.add_argument('--player-id', type=int, required=True)
    template_cli.add_argument('--times', type=float, nargs='+', default=[120, 300, 600, 900, 1200])
    compare_cli = commands.add_parser('compare'); compare_cli.add_argument('candidate', type=Path); compare_cli.add_argument('reference', type=Path)
    compare_cli.add_argument('--max-delta-seconds', type=float, default=0.5)
    for parser in [extract_cli, template_cli, compare_cli]: parser.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    try:
        if args.command == 'extract': result = extract(args.replay)
        elif args.command == 'template': result = template(json.loads(args.candidate.read_text()), args.player_id, args.times)
        else: result = compare(json.loads(args.candidate.read_text()), json.loads(args.reference.read_text()), args.max_delta_seconds)
        inputs = [getattr(args, k, None) for k in ('replay', 'candidate', 'reference')]
        if args.output.resolve() in [p.resolve() for p in inputs if p is not None]:
            raise ValueError('Output must not overwrite an input file.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
        with args.output.open('x') as stream:
            stream.write(text)
        print(f'Research-only output: {args.output}; NOT enabled as coaching state.')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        cli.exit(2, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()

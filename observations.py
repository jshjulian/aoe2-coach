"""Optional, quarantined CaptureAge observations. Never launches apps or alters parser facts.

The only write entry point is an explicit local import. Nothing is qualified as
verified application state, including operator-visually-checked observations.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from functools import lru_cache

VERSION = 1
QUALIFICATION = 'experimental_captureage_observations_not_verified_game_state'
MAX_JSON = 4 * 1024 * 1024
MAX_POINTS = 20000
GAP_SECONDS = 15
HEX = re.compile(r'^[a-f0-9]{64}$')


def metric(label, unit, kind='gauge', extraction='planned', definition=''):
    return dict(label=label, unit=unit, kind=kind, extraction=extraction, definition=definition,
                coaching_qualified=False)


METRICS = {
    **{f'resource_{r}': metric(f'{r.title()} stockpile', 'resources', extraction='saved_image_ocr_pilot',
                             definition='Visible resource balance; not income, spending or affordability.')
       for r in ('food', 'wood', 'gold', 'stone')},
    'tc_idle_seconds': metric('Cumulative TC idle', 'TC-seconds', 'counter', definition='CaptureAge-reported cumulative idle summed across TCs. Not wall-clock duration or idle percentage; definition needs further validation.'),
    'housed_seconds': metric('Cumulative housed time', 'seconds', 'counter', definition='CaptureAge-reported cumulative housed time; precise inclusion rules not independently validated.'),
    'villagers_alive': metric('Villagers alive', 'villagers', definition='Reported worker count; extraction and inclusion rules not yet validated.'),
    'workers_on_food': metric('Workers on food', 'workers', definition='Reported food-worker allocation; not a measurement of effective gathering, travel or efficiency.'),
    'workers_on_wood': metric('Workers on wood', 'workers'),
    'workers_on_gold': metric('Workers on gold', 'workers'),
    'workers_on_stone': metric('Workers on stone', 'workers'),
    'idle_workers': metric('Currently idle workers', 'workers', definition='Instantaneous reported idle count, not cumulative worker-idle time.'),
    'population_used': metric('Population used', 'population'),
    'population_limit': metric('Population limit', 'population'),
    'military_count': metric('Military count', 'units', definition='Reported count; not known unit composition, readiness or combat effectiveness.'),
    'army_value': metric('Army value', 'reported value', definition='CaptureAge-reported value; valuation formula is not independently validated.'),
}


def _hash(value): return isinstance(value, str) and HEX.fullmatch(value) is not None

def _integer(value): return type(value) is int and value >= 0


def validate_batch(batch, report):
    """Strict, bounded, identity-bound projection. Never trust a 'validated' flag."""
    if not isinstance(batch, dict) or type(batch.get('schema_version')) is not int or batch['schema_version'] != VERSION:
        raise ValueError('Unsupported observation schema.')
    if not _hash(report.get('match_id')) or batch.get('match_id') != report['match_id']:
        raise ValueError('Observation replay identity mismatch.')
    duration = report.get('duration_seconds')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Valid recording duration required.')
    build = report.get('replay_provenance', {}).get('build_version')
    if type(build) is not int or type(batch.get('replay_build')) is not int or batch['replay_build'] != build:
        raise ValueError('Observation replay build mismatch or unknown build.')
    provider = batch.get('provider', {})
    if (not isinstance(provider, dict) or provider.get('name') != 'CaptureAge' or provider.get('ui_version') != '1.26.0'
        or provider.get('method') not in ('windows_ocr', 'manual_transcription')
        or provider.get('clock') != 'displayed_game_clock_integer_seconds'
        or provider.get('binding') != 'operator_confirmed_offline_replay_names_civs_roles'):
        raise ValueError('Explicit supported provider, clock and operator binding required.')
    extractor_versions = {'windows_ocr':'captureage-hud-resources-v1','manual_transcription':'manual-hud-transcription-v1'}
    if provider.get('extractor_version') != extractor_versions[provider['method']]:
        raise ValueError('Explicit supported extractor version required.')
    expected = [{k: p[k] for k in ('id', 'name', 'civilization')} for p in report['players']]
    players = batch.get('players')
    if (not isinstance(players, list) or any(not isinstance(p, dict) or type(p.get('id')) is not int for p in players)
        or sorted(players, key=lambda p:p['id']) != sorted(expected, key=lambda p:p['id'])):
        raise ValueError('Exact parser player IDs, names and civilizations required.')
    ids = {p['id'] for p in expected}
    points = batch.get('points')
    if not isinstance(points, list) or not 1 <= len(points) <= MAX_POINTS:
        raise ValueError('Use 1..20000 observations per batch.')
    clean = []; seen = set(); evidence_clocks = {}
    for p in points:
        if not isinstance(p, dict): raise ValueError('Observation must be an object.')
        t, player, key, value, quality = (p.get(k) for k in ('time_seconds', 'player_id', 'metric', 'value', 'quality'))
        if (not _integer(t) or t > duration or type(player) is not int or player not in ids
            or not isinstance(key, str) or key not in METRICS or quality not in ('unreviewed', 'visually_checked', 'rejected')):
            raise ValueError('Invalid observation clock, player, metric or quality.')
        if provider['method']=='windows_ocr' and METRICS[key]['extraction']=='planned':
            raise ValueError('Automatic extraction for this metric is not implemented in this provider version.')
        if quality == 'rejected':
            if value is not None: raise ValueError('Rejected observations must have null value, never guessed zero.')
        elif not _integer(value) or value > 1_000_000_000: raise ValueError('Readable HUD counters must be bounded nonnegative integers.')
        if not _hash(p.get('evidence_sha256')): raise ValueError('Screenshot evidence SHA-256 required.')
        if evidence_clocks.setdefault(p['evidence_sha256'],t) != t:
            raise ValueError('One screenshot cannot establish multiple displayed clock values.')
        identity = (player, key, t)
        if identity in seen: raise ValueError('Duplicate/ambiguous player-metric-clock observation.')
        seen.add(identity)
        clean.append(dict(player_id=player, metric=key, time_seconds=t, value=value, quality=quality, evidence_sha256=p['evidence_sha256']))
    summary = batch.get('collection_summary')
    if summary is not None and (not isinstance(summary,dict) or set(summary) != {'total_frames','exported_frames','excluded_frames'}
        or not all(_integer(v) for v in summary.values()) or summary['total_frames'] != summary['exported_frames']+summary['excluded_frames']):
        raise ValueError('Invalid collection missingness summary.')
    return dict(schema_version=VERSION, match_id=report['match_id'], replay_build=build, collection_summary=summary,
                provider={k:provider[k] for k in ('name','ui_version','method','extractor_version','clock','binding')},
                players=expected, points=sorted(clean,key=lambda p:(p['player_id'],p['metric'],p['time_seconds'])),
                qualification=QUALIFICATION, validated_for_application=False)


def series_for(points, key):
    """No interpolation or zero filling; reset/gap/rejection breaks every derivative."""
    points = sorted(points, key=lambda p:p['time_seconds'])
    increments = []; previous = None; gaps = []; resets = []
    for p in points:
        if previous:
            dt = p['time_seconds']-previous['time_seconds']
            if METRICS[key]['kind'] == 'counter' and previous['value'] is not None and p['value'] is not None:
                delta = p['value']-previous['value']
                if 0 < dt <= GAP_SECONDS and delta >= 0:
                    increments.append(dict(start=previous['time_seconds'],end=p['time_seconds'],value=delta,
                                           quality='visually_checked' if previous['quality']==p['quality']=='visually_checked' else 'unreviewed',
                                           evidence_sha256=[previous['evidence_sha256'],p['evidence_sha256']]))
        previous = p
    valid = [p for p in points if p['value'] is not None]
    gaps = [dict(start=a['time_seconds'],end=b['time_seconds']) for a,b in zip(valid,valid[1:])
            if b['time_seconds']-a['time_seconds'] > GAP_SECONDS]
    resets = [b['time_seconds'] for a,b in zip(valid,valid[1:])
              if METRICS[key]['kind']=='counter' and b['value'] < a['value']]
    return dict(metric=key, points=points, increments=increments, gaps=gaps, counter_resets=resets,
                coverage=dict(readable=len(valid), rejected=len(points)-len(valid),
                              first_seconds=valid[0]['time_seconds'] if valid else None,
                              last_seconds=valid[-1]['time_seconds'] if valid else None),
                qualified_for_coaching=False)


def review_questions(series):
    """Experimental conjunction, NOT causal diagnosis or eligible primary coaching."""
    by_metric = {s['metric']:s for s in series}
    idle = by_metric.get('tc_idle_seconds'); food = by_metric.get('resource_food')
    if not idle or not food: return []
    food_at = {p['time_seconds']:p for p in food['points']}
    questions = []
    for interval in idle['increments']:
        a,b = food_at.get(interval['start']),food_at.get(interval['end'])
        intervening = [p for p in food['points'] if interval['start'] <= p['time_seconds'] <= interval['end']]
        if (interval['value'] <= 0 or interval['quality'] != 'visually_checked' or not a or not b
            or a['evidence_sha256'] != interval['evidence_sha256'][0] or b['evidence_sha256'] != interval['evidence_sha256'][1]
            or a['value'] != 0 or b['value'] != 0 or any(p['quality'] != 'visually_checked' or p['value'] != 0 for p in intervening)):
            continue
        questions.append(dict(kind='idle_and_zero_food_checkpoints', time_seconds=interval['end'],
            observation=f"Reported cumulative TC idle rose by {interval['value']} TC-seconds; food showed zero at both checkpoints.",
            question='Was food income interrupting villager production? Review food workers, spending, TC queues, age research and population headroom.',
            interpretation='Possible food constraint to investigate, not proven villager mismanagement. Between-checkpoint food and TC states are unknown.',
            alternatives=['Population cap', 'Age/technology research or other TC activity', 'Garrison or intentional production pause', 'Multi-TC aggregation and counter-definition uncertainty'],
            evidence_sha256=sorted(set(interval['evidence_sha256']+[a['evidence_sha256'],b['evidence_sha256']])),
            eligible_for_primary_coaching=False, causal_claim=False))
        if len(questions) == 3: break
    return questions


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.observation-')
    try:
        with os.fdopen(fd,'wb') as stream: stream.write(data)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


@lru_cache(maxsize=512)
def _verify_image(path_string, signature, sha):
    raw = Path(path_string).read_bytes()
    if not raw.startswith(b'\x89PNG\r\n\x1a\n') or hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError('Stored screenshot integrity failure.')
    return True


def _check_image(path, root, sha):
    if not path.resolve().is_relative_to(root.resolve()): raise ValueError('Evidence outside observation store.')
    s = path.stat()
    if s.st_size > 16*1024*1024: raise ValueError('Oversized evidence.')
    _verify_image(str(path), (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns), sha)


class ObservationStore:
    def __init__(self, root): self.root = Path(root)

    def import_batch(self, batch, report, evidence_root):
        clean = validate_batch(batch,report)
        evidence_root = Path(evidence_root).resolve()
        descriptors = batch.get('evidence')
        if not isinstance(descriptors,list) or not 1 <= len(descriptors) <= 512: raise ValueError('Bounded screenshot evidence manifest required.')
        evidence = {}; total = 0
        for item in descriptors:
            if not isinstance(item,dict) or not _hash(item.get('sha256')) or not isinstance(item.get('file'),str): raise ValueError('Invalid evidence manifest.')
            relative = Path(item['file'])
            if relative.is_absolute() or '..' in relative.parts: raise ValueError('Evidence must be relative to explicit evidence root.')
            path = (evidence_root/relative).resolve()
            if not path.is_relative_to(evidence_root) or not path.is_file() or path.stat().st_size > 16*1024*1024:
                raise ValueError('Evidence missing, oversized or outside evidence root.')
            raw = path.read_bytes(); total += len(raw)
            if total > 128*1024*1024: raise ValueError('Evidence batch exceeds 128MB.')
            if not raw.startswith(b'\x89PNG\r\n\x1a\n') or hashlib.sha256(raw).hexdigest() != item['sha256']: raise ValueError('PNG evidence hash mismatch.')
            if item['sha256'] in evidence: raise ValueError('Duplicate evidence manifest hash.')
            evidence[item['sha256']] = raw
        needed = {p['evidence_sha256'] for p in clean['points']}
        if needed != set(evidence): raise ValueError('Manifest must exactly resolve observation evidence.')
        encoded = json.dumps(clean,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()
        if len(encoded) > MAX_JSON: raise ValueError('Observation batch exceeds 4MB.')
        batch_id = hashlib.sha256(encoded).hexdigest()
        for sha,raw in evidence.items(): _atomic(self.root/'evidence'/f'{sha}.png',raw)
        _atomic(self.root/'batches'/f'{batch_id}.json',encoded)
        _atomic(self.root/'matches'/f'{clean["match_id"]}.json',json.dumps({'batch_id':batch_id}).encode())
        return batch_id

    def read(self, report, player_name):
        result = dict(schema_version=VERSION, match_id=report['match_id'], qualification=QUALIFICATION,
                      validated_for_application=False, status='not_collected', metrics=METRICS,
                      series=[], review_questions=[], provider=None, batch_id=None, selected_player_id=None, collection_summary=None,
                      max_comparable_gap_seconds=GAP_SECONDS,
                      collection=dict(enabled=False,reason='Collection controls are not connected. No game or CaptureAge launch occurs from this API.'))
        if not _hash(report['match_id']): raise ValueError('Invalid content identity.')
        players = [p for p in report['players'] if p['name']==player_name]
        if len(players) != 1:
            result['status']='select_player'; return result
        result['selected_player_id'] = players[0]['id']
        pointer = self.root/'matches'/f'{report["match_id"]}.json'
        if not pointer.exists(): return result
        try:
            if pointer.stat().st_size > 256: raise ValueError('Invalid observation pointer.')
            batch_id = json.loads(pointer.read_text())['batch_id']
            if not _hash(batch_id): raise ValueError('Invalid observation batch ID.')
            path = self.root/'batches'/f'{batch_id}.json'
            if path.stat().st_size > MAX_JSON: raise ValueError('Oversized observation batch.')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != batch_id: raise ValueError('Observation batch integrity failure.')
            batch = validate_batch(json.loads(raw),report)
            for sha in {p['evidence_sha256'] for p in batch['points']}:
                _check_image(self.root/'evidence'/f'{sha}.png',self.root,sha)
            keys = sorted({p['metric'] for p in batch['points'] if p['player_id']==players[0]['id']})
            series = [series_for([p for p in batch['points'] if p['player_id']==players[0]['id'] and p['metric']==key],key) for key in keys]
            result.update(status='experimental' if series else 'no_player_observations', series=series,
                          review_questions=review_questions(series),provider=batch['provider'],batch_id=batch_id,collection_summary=batch['collection_summary'])
        except (OSError,ValueError,KeyError,TypeError): result.update(status='invalid',error='Stored observations failed identity/schema/integrity checks; re-import evidence.')
        return result

    def context(self, report, player_name):
        data = self.read(report,player_name)
        points=[p for s in data['series'] for p in s['points']]
        readable=[p for p in points if p['value'] is not None and p['quality']!='rejected']
        clocks=sorted({p['time_seconds'] for p in readable})
        return {**{k:data[k] for k in ('schema_version','match_id','batch_id','status','qualification','validated_for_application','selected_player_id','review_questions')},
                'checkpoint_count':len(clocks),'readable_point_count':len(readable),
                'checked_point_count':sum(p['quality']=='visually_checked' for p in readable),
                'rejected_point_count':sum(p['quality']=='rejected' for p in points),
                'readable_window_seconds':[clocks[0],clocks[-1]] if clocks else None}

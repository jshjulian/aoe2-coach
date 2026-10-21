#!/usr/bin/env python3
"""Loopback-only Python analysis and replay-library service for AoE2 Replay Lab."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import secrets
import threading
import time
import stat as stat_module
from collections import OrderedDict
from functools import lru_cache
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from analysis import SCHEMA_VERSION, analyze_match, persist_report, replay_start_from_filename, stable_match_id
from coaching import build_review
from situations import SITUATION_VERSION, REVIEW_VERSION, build_situation_review
from situation_knowledge import reference_options
from matchup import MATCHUP_VERSION, build_matchup
from opening_observations import OBSERVATION_VERSION, observe_openings
from replay_provenance import PROVENANCE_VERSION, read_provenance
from coaching_store import CoachingStore
import practice
import gameplay
import balanced_takeaway
import military_reasoning
import practice_progress
import map_previews
from replay_settings import select_directories
from observations import ObservationStore, VERSION as OBSERVATIONS_VERSION
from reviewed_moments import ReviewedMomentStore

CACHE_DIR = Path(__file__).parent / 'data' / 'matches'
_CACHE_LOCK = threading.Lock()
_REPORT_LOCKS: dict[str, threading.Lock] = {}
_REPORT_MEMORY: OrderedDict = OrderedDict()


def file_signature(path: Path) -> tuple:
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


@lru_cache(maxsize=512)
def _content_id_for_signature(path: str, signature: tuple) -> str:
    # Stat changes invalidate this optimization; identity itself remains SHA-256.
    return stable_match_id(Path(path))


def is_local_viewer_origin(origin: str | None) -> bool:
    try:
        parsed = urlparse(origin or '')
        return (parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost'}
                and parsed.port is not None and 3000 <= parsed.port <= 3010)
    except ValueError:
        return False


def discover_replay_directories(explicit: Path | None = None) -> list[Path]:
    """Find conventional AoE2 DE savegame folders without crawling whole drives."""
    env_value = os.environ.get('AOE2_REPLAY_DIR')
    if explicit:
        candidates = [explicit]
    elif env_value:
        candidates = [Path(value).expanduser() for value in env_value.split(os.pathsep) if value]
    else:
        candidates = []
        for mount in Path('/mnt').glob('*'):
            user_root = mount / 'Users'
            if user_root.is_dir():
                candidates.extend(user_root.glob('*/Games/Age of Empires 2 DE/*/savegame'))
                candidates.extend(user_root.glob('*/Documents/My Games/Age of Empires 2 DE/*/savegame'))
                candidates.extend(user_root.glob('*/Documents/My Games/Age of Empires II DE/*/savegame'))
        steam = Path.home() / '.steam/steam/steamapps/compatdata/813780/pfx/drive_c/users/steamuser/Games/Age of Empires 2 DE'
        candidates.extend(steam.glob('*/savegame'))
        candidates.extend((Path.home() / 'Games/Age of Empires 2 DE').glob('*/savegame'))
    found: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
            if resolved.is_dir() and (explicit or env_value or any(resolved.glob('*.aoe2record'))) and str(resolved) not in seen:
                seen.add(str(resolved))
                found.append(resolved)
        except OSError:
            continue
    return found


def scan(folder: Path) -> list[dict]:
    """Fast metadata-only scan retained for API clients and tests."""
    paths = sorted(folder.glob('*.aoe2record'), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    return [{'file': p.name, 'size_bytes': p.stat().st_size,
             'modified': datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec='minutes')}
            for p in paths]


def report_for(path: Path, *, include_raw: bool = False) -> tuple[dict, Path, Path]:
    """Read cached compact analysis by content hash; parse once if absent.

    Full parser payloads are materialized only for an explicit raw-export request,
    keeping background library indexing compact.
    """
    signature = file_signature(path)
    match_id = _content_id_for_signature(str(path.absolute()), signature)
    normalized = CACHE_DIR / f'{match_id}.json'
    raw = CACHE_DIR / f'{match_id}.raw.json'
    key = str(normalized.absolute())
    with _CACHE_LOCK:
        lock = _REPORT_LOCKS.setdefault(key, threading.Lock())
    # Unrelated background parses cannot block a cached selected match.
    with lock:
        report = None
        cache_signature = file_signature(normalized) if normalized.is_file() else None
        with _CACHE_LOCK:
            cached = _REPORT_MEMORY.get(key)
            if cached and cached[0] == (signature, cache_signature, path.name):
                report = cached[1]
                _REPORT_MEMORY.move_to_end(key)
        if report is None and cache_signature:
            try:
                candidate = json.loads(normalized.read_text(encoding='utf-8'))
                if candidate.get('schema_version') == SCHEMA_VERSION and candidate.get('match_id') == match_id:
                    report = candidate
            except (OSError, ValueError):
                pass
        if report is None or (include_raw and not raw.is_file()):
            full = analyze_match(path, match_id=match_id)
            if file_signature(path) != signature:
                raise ValueError('Replay changed during analysis; try again when recording is complete.')
            persist_report(full, CACHE_DIR, include_raw=include_raw)
            report = {k: v for k, v in full.items() if k != 'raw_events'}
        upgraded = False
        if report.get('opening_observation_version') != OBSERVATION_VERSION:
            report = {**report, 'opening_observation_version': OBSERVATION_VERSION,
                      'opening_observations': observe_openings(report)}
            upgraded = True
        if report.get('replay_provenance', {}).get('provenance_version') != PROVENANCE_VERSION:
            try:
                provenance = read_provenance(path)
            except Exception as exc:
                provenance = {'provenance_version': PROVENANCE_VERSION, 'source': 'unavailable',
                              'build_version': None, 'mod_compatibility': 'unknown',
                              'reason': f'Header provenance unavailable ({type(exc).__name__}); legacy analysis remains usable.'}
            report = {**report, 'replay_provenance': provenance}
            upgraded = True
        metadata = {'source_file': path.name, 'source_size_bytes': signature[2], 'source_mtime_ns': signature[3]}
        if any(report.get(k) != v for k, v in metadata.items()):
            report = {**report, **metadata, 'played_at': replay_start_from_filename(path.name),
                      'played_at_source': 'replay_filename_timestamp' if replay_start_from_filename(path.name) else None}
            upgraded = True
        if upgraded:
            if file_signature(path) != signature:
                raise ValueError('Replay changed while reading provenance; reload this match.')
            persist_report(report, CACHE_DIR, include_raw=False)
        with _CACHE_LOCK:
            _REPORT_MEMORY[key] = ((signature, file_signature(normalized), path.name), report)
            _REPORT_MEMORY.move_to_end(key)
            while len(_REPORT_MEMORY) > 12:
                _REPORT_MEMORY.popitem(last=False)
        if file_signature(path) != signature:
            raise ValueError('Replay changed during analysis; try again when recording is complete.')
        return report, normalized, raw


def _add_rating_snapshot_deltas(rows: list[dict]) -> list[dict]:
    """Shift each 1v1 rating snapshot/difference one saved replay backward."""
    result = [{**row, 'players': [dict(player) for player in row.get('players', [])]} for row in rows]
    for row in result:
        for player in row.get('players', []):
            player['previous_elo_snapshot'] = None
            player['elo_change_since_previous_snapshot'] = None
            player['rating_snapshot_source_played_at'] = None
            player['_recorded_elo_snapshot'] = player.get('elo_snapshot')
            player['elo_snapshot'] = None
    try:
        chronological = sorted((row for row in result if row.get('played_at')),
                               key=lambda row: datetime.fromisoformat(row['played_at']).isoformat())
    except (TypeError, ValueError, OSError):
        return result
    previous: dict[tuple[str, str], tuple[int, dict, str]] = {}
    seen: set[tuple[str, str, str]] = set()
    for row in chronological:
        if row.get('status') != 'ready' or not row.get('match_id'):
            continue
        for player in row.get('players', []):
            rating = player.pop('_recorded_elo_snapshot', None)
            track = player.get('rating_track')
            if not isinstance(rating, int) or not track or not player.get('name'):
                continue
            dedupe = (player['name'], track, row['match_id'])
            if dedupe in seen:
                continue
            seen.add(dedupe)
            key = (player['name'], track)
            prior = previous.get(key)
            if prior:
                _, previous_player, _ = prior
                previous_player['elo_snapshot'] = rating
                previous_player['previous_elo_snapshot'] = prior[0]
                previous_player['elo_change_since_previous_snapshot'] = rating - prior[0]
                previous_player['rating_snapshot_source_played_at'] = row.get('played_at')
            previous[key] = (rating, player, row.get('played_at'))
    for row in result:
        for player in row.get('players', []):
            player.pop('_recorded_elo_snapshot', None)
    return result


class ReplayLibrary:
    """Background, one-at-a-time replay analysis with a fast metadata-first catalog."""
    def __init__(self):
        self._lock = threading.RLock()
        self._folders: list[Path] | None = None
        self._folder_cache: tuple[float, list[Path]] = (0, [])
        self._last_scan = 0.0
        self._scan_lock = threading.Lock()
        self._rows: dict[str, dict] = {}
        self._jobs: queue.Queue[str] = queue.Queue()
        self._queued: set[str] = set()
        threading.Thread(target=self._worker, name='aoe2-library-indexer', daemon=True).start()

    def configure(self, folders: list[Path] | None) -> None:
        with self._lock:
            self._folders = [p.expanduser().resolve() for p in folders] if folders is not None else None
            self._folder_cache = (0, [])
            self._last_scan = 0

    def folders(self, refresh: bool = False) -> list[Path]:
        with self._lock:
            if self._folder_cache[0] and (not refresh or time.monotonic() - self._folder_cache[0] < 60):
                return self._folder_cache[1]
            configured = self._folders
        # WSL/Windows filesystem discovery must not hold the catalog's data lock.
        found = ([p for p in configured if p.is_dir()] if configured is not None else discover_replay_directories())
        with self._lock:
            if configured == self._folders:
                self._folder_cache = (time.monotonic(), found)
        return found

    @staticmethod
    def _id(path: Path) -> str:
        return hashlib.sha256(str(path.absolute()).encode('utf-8')).hexdigest()[:20]

    def refresh(self, force: bool = False) -> list[dict]:
        if not force and time.monotonic() - self._last_scan < 5:
            return self.games()
        if not self._scan_lock.acquire(blocking=False):
            return self.games()
        def scan():
            try:
                self._scan()
            finally:
                self._last_scan = time.monotonic()
                self._scan_lock.release()
        if force or self._last_scan == 0:
            scan()  # Initial metadata catalog is populated before the API starts serving.
        else:
            threading.Thread(target=scan, daemon=True, name='replay-folder-scan').start()
        return self.games()

    def _scan(self) -> list[dict]:
        found: dict[str, tuple[Path, os.stat_result]] = {}
        for folder in self.folders(refresh=True):
            try:
                for path in folder.glob('*.aoe2record'):
                    try:
                        stat = path.stat()
                        if stat_module.S_ISREG(stat.st_mode): found[self._id(path)] = (path, stat)
                    except OSError:
                        continue
            except OSError:
                continue
        now_ids = set(found)
        with self._lock:
            for removed in set(self._rows) - now_ids:
                self._rows.pop(removed, None)
            for game_id, (path, stat) in sorted(found.items(), key=lambda item: item[1][1].st_mtime_ns, reverse=True):
                old = self._rows.get(game_id)
                unchanged = old and old.get('_mtime_ns') == stat.st_mtime_ns and old.get('_size_bytes') == stat.st_size
                if unchanged:
                    old['_path'] = path
                    if old['status'] == 'queued':
                        self._enqueue_if_settled(game_id, stat)
                    continue
                self._rows[game_id] = {
                    'game_id': game_id, 'file': path.name, 'size_bytes': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),
                    'modified_timestamp': stat.st_mtime,
                    'status': 'queued', 'match_id': None, 'map': None, 'duration': None,
                    'duration_seconds': None, 'rated': None, 'game_type_id': None,
                    'played_at': replay_start_from_filename(path.name),
                    'played_at_source': 'replay_filename_timestamp' if replay_start_from_filename(path.name) else None,
                    'estimated_real_duration_seconds': None, 'game_speed_multiplier': None,
                    'players': [], 'opening_milestones': [], 'tc_queue_activity': [], 'error': None,
                    '_mtime_ns': stat.st_mtime_ns, '_size_bytes': stat.st_size, '_path': path,
                }
                self._enqueue_if_settled(game_id, stat)
            return self._public_rows_locked()

    def _enqueue_if_settled(self, game_id, stat):
        self._rows[game_id]['waiting_for_recording'] = time.time() - stat.st_mtime < 15
        if game_id not in self._queued and not self._rows[game_id]['waiting_for_recording']:
            self._queued.add(game_id)
            self._jobs.put(game_id)

    def _public_rows_locked(self) -> list[dict]:
        rows = []
        for row in self._rows.values():
            public = {k: v for k, v in row.items() if not k.startswith('_')}
            public['map_preview_available']=row.get('status')=='ready' and map_previews.eligible_players(row.get('players',[]))
            # Catalog/trends need only the largest proxy, not every evidence-heavy gap.
            public['tc_queue_activity'] = [
                {'player': tc['player'], 'long_command_gaps': [
                    {'gap_seconds': max(g['gap_seconds'] for g in tc['long_command_gaps'])}
                ] if tc.get('long_command_gaps') else []}
                for tc in row.get('tc_queue_activity', [])]
            rows.append(public)
        return sorted(rows, key=lambda row: (row['modified_timestamp'], row['file']), reverse=True)

    def games(self) -> list[dict]:
        with self._lock:
            return self._public_rows_locked()

    def library(self) -> dict:
        rows = _add_rating_snapshot_deltas(self.refresh())
        counts = {state: sum(row['status'] == state for row in rows) for state in ('queued', 'analyzing', 'ready', 'error')}
        return {'directories': [str(p) for p in self.folders()], 'total': len(rows), 'counts': counts, 'games': rows}

    def preview_entry(self, game_id: str) -> dict | None:
        with self._lock:
            row=self._rows.get(game_id)
            if not row or row.get('status')!='ready' or not row.get('match_id') or not map_previews.eligible_players(row.get('players',[])): return None
            return {'path':row['_path'],'match_id':row['match_id'],'stamp':(row['_size_bytes'],row['_mtime_ns'])}

    def path_for_id(self, game_id: str) -> Path | None:
        with self._lock:
            row = self._rows.get(game_id)
            path = row.get('_path') if row else None
        return path if isinstance(path, Path) and path.is_file() else None

    def path_for_file(self, name: str) -> Path | None:
        with self._lock:
            matches = [row['_path'] for row in self._rows.values() if row['file'] == name]
        matches = [path for path in matches if path.is_file()]
        return matches[0] if len(matches) == 1 else None

    def update_report(self, path: Path, report: dict) -> None:
        game_id = self._id(path)
        with self._lock:
            row = self._rows.get(game_id)
            if not row: return
            row.update({'status': 'ready', 'match_id': report.get('match_id'), 'map': report.get('map'),
                        'duration': report.get('duration'), 'duration_seconds': report.get('duration_seconds'),
                        'rated': report.get('rated'), 'game_type_id': (report.get('replay_provenance') or {}).get('game_type_id'),
                        'played_at': report.get('played_at') or row.get('played_at'),
                        'played_at_source': report.get('played_at_source') or row.get('played_at_source'),
                        'estimated_real_duration_seconds': report.get('estimated_real_duration_seconds'),
                        'game_speed_multiplier': report.get('game_speed_multiplier'),
                        'players': [
                            {'id': p['id'], 'name': p['name'], 'civilization': p.get('civilization'), 'team_id': p.get('team_id'), 'won': p.get('won'),
                             'elo_snapshot': p.get('elo_snapshot'), 'rating_track': p.get('rating_track'),
                             'previous_elo_snapshot': None, 'elo_change_since_previous_snapshot': None}
                            for p in report.get('players', [])],
                        'opening_milestones': report.get('opening_milestones', []),
                        'tc_queue_activity': report.get('tc_queue_activity', []), 'error': None})

    def _worker(self) -> None:
        while True:
            game_id = self._jobs.get()
            try:
                with self._lock:
                    row = self._rows.get(game_id)
                    if not row or row.get('status') != 'queued': continue
                    row['status'] = 'analyzing'
                    path = row['_path']
                report, _, _ = report_for(path, include_raw=False)
                self.update_report(path, report)
            except Exception as exc:
                with self._lock:
                    row = self._rows.get(game_id)
                    if row: row.update({'status': 'error', 'error': f'{type(exc).__name__}: {exc}'})
            finally:
                with self._lock: self._queued.discard(game_id)
                self._jobs.task_done()

    def trends(self) -> dict:
        rows = [row for row in self.games() if row['status'] == 'ready' and row.get('match_id')]
        rows.sort(key=lambda row: row['modified_timestamp'])
        # Duplicate copies of a replay count once in longitudinal summaries.
        seen: set[str] = set(); unique=[]
        for row in rows:
            if row['match_id'] not in seen:
                seen.add(row['match_id']); unique.append(row)
        groups: dict[tuple[str, str], list[tuple[dict, dict]]] = {}
        for row in unique:
            milestone_by_player = {entry['player']: entry for entry in row.get('opening_milestones', [])}
            for player in row.get('players', []):
                key = (player['name'], str(player.get('civilization') or 'Unknown'))
                milestone = milestone_by_player.get(player['name'], {}).get('milestones', {})
                tc = next((entry for entry in row.get('tc_queue_activity', []) if entry['player'] == player['name']), {})
                groups.setdefault(key, []).append((row, {'milestones': milestone, 'tc': tc}))
        specs = [
            ('feudal_arrival', 'Feudal Age arrival', 'Earlier arrival', 'parser age milestone'),
            ('castle_arrival', 'Castle Age arrival', 'Earlier arrival', 'parser age milestone'),
            ('castle_command_to_arrival', 'Castle research command → age arrival', 'Shorter interval', 'elapsed command-to-milestone interval; not a measured research duration'),
            ('knight_after_castle', 'Castle arrival → first Knight queue command', 'Earlier queue command', 'recorded queue command, not a completed Knight'),
            ('tc_villager_max_gap', 'Longest TC Villager queue-command gap', 'Shorter recorded gap', 'review proxy only—not TC idle time'),
        ]
        trends=[]; player_counts={}
        for (name, civ), records in groups.items():
            records.sort(key=lambda item: item[0]['modified'])
            player_counts[name] = max(player_counts.get(name, 0), len(records))
            series: dict[str, list[tuple[dict, float]]] = {spec[0]: [] for spec in specs}
            for row, data in records:
                ms=data['milestones']
                def val(key):
                    entry=ms.get(key)
                    return float(entry['time_seconds']) if entry and entry.get('time_seconds') is not None else None
                feudal=val('feudal_arrival'); castle=val('castle_arrival'); research=val('castle_research'); knight=val('first_knight_queue')
                if feudal is not None: series['feudal_arrival'].append((row, feudal))
                if castle is not None: series['castle_arrival'].append((row, castle))
                if castle is not None and research is not None: series['castle_command_to_arrival'].append((row, castle-research))
                if castle is not None and knight is not None and knight >= castle: series['knight_after_castle'].append((row, knight-castle))
                gaps=[g['gap_seconds'] for g in data['tc'].get('long_command_gaps', []) if g.get('gap_seconds') is not None]
                if gaps: series['tc_villager_max_gap'].append((row, max(gaps)))
            for metric_id, label, direction_label, caveat in specs:
                values=series[metric_id]
                if len(values)<4: continue
                cut=len(values)//2
                earlier=values[:cut]; recent=values[cut:]
                def median(samples):
                    ordered=sorted(v for _,v in samples); middle=len(ordered)//2
                    return ordered[middle] if len(ordered)%2 else (ordered[middle-1]+ordered[middle])/2
                earlier_median=median(earlier)
                recent_median=median(recent)
                delta=recent_median-earlier_median
                threshold=max(10.0, earlier_median*0.03)
                direction='flat' if abs(delta)<threshold else ('earlier' if delta<0 else 'later')
                trends.append({'id':f'{name}:{civ}:{metric_id}','player':name,'civilization':civ,
                    'metric':metric_id,'label':label,'direction_label':direction_label,'caveat':caveat,
                    'samples':len(values),'earlier_count':len(earlier),'recent_count':len(recent),
                    'earlier_median_seconds':round(earlier_median,1),'recent_median_seconds':round(recent_median,1),
                    'change_seconds':round(delta,1),'direction':direction,
                    'game_ids':[row['game_id'] for row,_ in values],
                    'note':'Observed pattern across different matches; map, opponent, strategy, and game conditions may differ.'})
        trends.sort(key=lambda item: (-player_counts.get(item['player'], 0), item['player'], item['metric']))
        return {'analyzed_games': len(unique), 'total_games': len(self.games()), 'trends': trends,
                'player_counts': player_counts, 'minimum_samples': 4}


LIBRARY = ReplayLibrary()


class Handler(BaseHTTPRequestHandler):
    server_version = 'AoE2ReplayLab/4.0'
    library = LIBRARY
    coaching_store = CoachingStore(Path(__file__).parent / 'data' / 'coaching.sqlite')
    observation_store = ObservationStore(Path(__file__).parent / 'data' / 'observations')
    reviewed_moment_store = ReviewedMomentStore(Path(__file__).parent / 'data' / 'reviewed-moments')
    csrf_token = secrets.token_urlsafe(32)

    def _trusted_coaching_request(self):
        host = self.headers.get('Host', '')
        return (host in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
                and is_local_viewer_origin(self.headers.get('Origin')))

    def _coaching_review(self, query, *, with_matchup=False):
        self.library.refresh()
        path = self._path_from_query(query)
        if path is None:
            raise ValueError('Replay not found in discovered folders.')
        report, _, _ = report_for(path)
        expected = query.get('match_id', [''])[0]
        if expected and expected != report['match_id']:
            raise ValueError('Replay content changed; reload the selected match.')
        name = query.get('player', [''])[0]
        preliminary = build_review(report, name)
        saved = self.coaching_store.read(preliminary)['plan'] or {}
        plan = query.get('plan', [saved.get('id', '')])[0]
        confirmed = query.get('confirmed', ['true' if saved.get('confirmed') else 'false'])[0] == 'true'
        review = build_review(report, name, plan, confirmed)
        if not with_matchup:
            return review
        state = self.coaching_store.read(review)
        situation = build_situation_review(report, name)
        situation['knowledge'] = reference_options(report, name, situation, state.get('rules_context'))
        decisions = gameplay.build(report, name, self.coaching_store, situation=situation)
        reasoning = military_reasoning.build(report, review, situation, decisions, self.coaching_store)
        journal = practice.context(self.coaching_store, report, situation, decisions, reasoning)
        journal['comparison_snapshot'] = practice_progress.snapshot(report, journal, decisions, situation, state.get('rules_context'))
        return {'review': review, 'state': state, 'situation': situation, 'gameplay_context': decisions,
                'practice_context': journal, 'progress_context': practice_progress.context(self.coaching_store, journal),
                'takeaway_context': balanced_takeaway.build(report, review, situation, decisions, journal),
                'reasoning_context': reasoning,
                'matchup': build_matchup(report, name, state.get('rules_context')),
                'observation_context': self.observation_store.context(report, name),
                'reviewed_moment_context': self.reviewed_moment_store.read(report, name, self.observation_store)}

    def _send(self, status: int, payload: bytes, content_type: str = 'application/json; charset=utf-8') -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        origin = self.headers.get('Origin')
        if is_local_viewer_origin(origin):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.end_headers()
        try: self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError): pass

    def _json(self, status: int, value) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode('utf-8'))

    def _path_from_query(self, query: dict[str, list[str]]) -> Path | None:
        game_id = query.get('game_id', query.get('id', ['']))[0]
        if game_id: return self.library.path_for_id(game_id)
        name = query.get('file', [''])[0]
        return self.library.path_for_file(name) if name else None

    def do_GET(self):
        route = urlparse(self.path)
        query = parse_qs(route.query)
        if route.path in ('/', '/api/health'):
            self._json(200, {'service': 'AoE2 Replay Lab analysis API', 'api_version': 4, 'matchup_version': MATCHUP_VERSION, 'provenance_version': PROVENANCE_VERSION, 'situation_version': SITUATION_VERSION, 'situation_review_version': REVIEW_VERSION, 'observations_version': OBSERVATIONS_VERSION, 'reviewed_moments_version': 1, 'practice_version': practice.VERSION, 'practice_controls_version': practice.CONTROLS_VERSION, 'gameplay_version': gameplay.VERSION, 'progress_version': practice_progress.VERSION, 'takeaway_version': balanced_takeaway.VERSION, 'reasoning_version': military_reasoning.VERSION, 'library_visuals_version': 1, 'replay_settings_version': 1, 'observation_collection_enabled': False, 'local_only': True,
                             'replay_directories': [str(p) for p in self.library.folders()],
                             'analysis_endpoint': '/api/analysis?game_id=<id>'})
            return
        if route.path == '/api/map-preview':
            if not self._trusted_coaching_request():
                self._json(403, {'error':'Map previews require trusted loopback Host/Origin.'}); return
            entry=self.library.preview_entry(query.get('game_id',[''])[0])
            if not entry:
                self._json(404, {'error':'Ready replay not found for map preview.'}); return
            expected=query.get('match_id',[''])[0]
            if expected!=entry['match_id']:
                self._json(409, {'error':'Map content identity changed; refresh the library.'}); return
            try: self._json(200,map_previews.preview(entry['path'],expected,entry['stamp']))
            except ValueError as exc: self._json(409,{'error':str(exc)})
            except Exception: self._json(422,{'error':'Recorded-header map preview unavailable.'})
            return
        if route.path == '/api/coaching/session':
            if not self._trusted_coaching_request():
                self._json(403, {'error': 'Coaching session requires a trusted loopback viewer origin and Host.'})
                return
            self._json(200, {'csrf_token': self.csrf_token})
            return
        if route.path == '/api/coaching':
            host, origin = self.headers.get('Host',''), self.headers.get('Origin')
            if host not in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'} or (origin and not is_local_viewer_origin(origin)):
                self._json(403, {'error':'Coaching requires trusted loopback Host/Origin.'}); return
            try:
                self._json(200, self._coaching_review(query, with_matchup=True))
            except ValueError as exc:
                self._json(400, {'error': str(exc)})
            except Exception as exc:
                self._json(422, {'error': f'{type(exc).__name__}: {exc}'})
            return
        if route.path == '/api/observations':
            host = self.headers.get('Host', '')
            origin = self.headers.get('Origin')
            if (host not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
                or (origin and not is_local_viewer_origin(origin))):
                self._json(403, {'error': 'Observations require trusted loopback Host/Origin.'}); return
            try:
                self.library.refresh()
                path = self._path_from_query(query)
                if path is None:
                    self._json(404, {'error': 'Replay not found.'}); return
                report, _, _ = report_for(path)
                if query.get('match_id', [''])[0] != report['match_id']:
                    raise ValueError('Expected content match_id required; reload this match.')
                self._json(200, self.observation_store.read(report, query.get('player', [''])[0]))
            except ValueError as exc: self._json(400, {'error': str(exc)})
            except Exception: self._json(422, {'error': 'Observations unavailable; local analysis could not be read.'})
            return
        if route.path == '/api/library':
            try: self._json(200, self.library.library())
            except Exception as exc: self._json(500, {'error': f'{type(exc).__name__}: {exc}'})
            return
        if route.path == '/api/games':
            try: self._json(200, _add_rating_snapshot_deltas(self.library.refresh()))
            except Exception as exc: self._json(500, {'error': f'{type(exc).__name__}: {exc}'})
            return
        if route.path == '/api/trends':
            self._json(200, self.library.trends())
            return
        if route.path in ('/api/replay', '/api/analysis', '/api/normalized', '/api/raw'):
            if route.path == '/api/replay':
                # Ensure this request's catalog ID is current before resolving it.
                self.library.refresh()
                path = self._path_from_query(query)
                if path is None:
                    self._json(404, {'error': 'Replay not found in discovered local replay folders', 'game_id': query.get('game_id', [''])[0]})
                    return
                try: self._send(200, path.read_bytes(), 'application/octet-stream')
                except OSError as exc: self._json(500, {'error': f'Could not read local replay: {exc}'})
                return
            self.library.refresh()
            path = self._path_from_query(query)
            if path is None:
                self._json(404, {'error': 'Replay not found in discovered local replay folders', 'file': query.get('file', [''])[0]})
                return
            try:
                report, normalized, raw = report_for(path, include_raw=(route.path == '/api/raw'))
                file_path = raw if route.path == '/api/raw' else normalized
                if not file_path.is_file():
                    self._json(500, {'error': 'Requested cache artifact was not generated'})
                    return
                self.library.update_report(path, report)
                self._send(200, file_path.read_bytes())
            except Exception as exc:
                self._json(422, {'error': f'{type(exc).__name__}: {exc}', 'file': path.name})
            return
        if route.path == '/api/compare':
            self.library.refresh()
            names = query.get('file', [])
            if not 2 <= len(names) <= 6:
                self._json(400, {'error': 'Select between 2 and 6 replay files'}); return
            games=[]
            try:
                for name in names:
                    path=self.library.path_for_file(name)
                    if path is None:
                        self._json(404, {'error':'Replay filename is missing or ambiguous','file':name}); return
                    report,_,_=report_for(path)
                    games.append({'file':path.name,'match_id':report['match_id'],'duration':report['duration'],
                                  'players':report.get('opening_milestones',[])})
            except Exception as exc:
                self._json(422, {'error':f'{type(exc).__name__}: {exc}'}); return
            self._json(200, {'games':games}); return
        self._json(404, {'error':'Not found'})

    def do_POST(self):
        if urlparse(self.path).path != '/api/coaching/state':
            self._json(404, {'error': 'Not found'})
            return
        if (not self._trusted_coaching_request() or
            not secrets.compare_digest(self.headers.get('X-Coaching-Token', ''), self.csrf_token)):
            self._json(403, {'error': 'Untrusted coaching write request.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if (not 0 < length <= 16384 or self.headers.get('Transfer-Encoding') or
                self.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
                raise ValueError('Use a bounded application/json request (maximum 16KB).')
            self.connection.settimeout(10)
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Expected a JSON object.')
            query = {key: [str(payload.get(key, ''))] for key in ('game_id', 'file', 'player', 'match_id')}
            if not query['match_id'][0]:
                raise ValueError('Expected content match_id is required for coaching writes.')
            # Read the persisted plan, never trust advice IDs/metrics supplied by a browser.
            if payload.get('operation') in practice.OPERATIONS:
                packet = self._coaching_review(query, with_matchup=True)
                practice.save(self.coaching_store, packet['practice_context'], payload)
            elif payload.get('operation') == 'reasoning_answer':
                packet = self._coaching_review(query, with_matchup=True)
                military_reasoning.save_answer(self.coaching_store, packet['reasoning_context'], payload)
            elif payload.get('operation') == 'gameplay_feedback':
                packet = self._coaching_review(query, with_matchup=True)
                gameplay.save_feedback(self.coaching_store, packet['gameplay_context'], payload)
            else:
                review = self._coaching_review(query)
                self.coaching_store.save(review, payload)
            self._json(200, self._coaching_review(query, with_matchup=True))
        except (ValueError, TypeError) as exc:
            self._json(400, {'error': str(exc)})
        except Exception as exc:
            self._json(422, {'error': f'{type(exc).__name__}: {exc}'})

    def do_OPTIONS(self):
        self.send_response(204)
        origin = self.headers.get('Origin')
        if is_local_viewer_origin(origin):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Coaching-Token')
        self.end_headers()

    def log_message(self, *_): pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replays', type=str, action='append', default=None, help='Replay folder; repeat for multiple folders')
    parser.add_argument('--config', type=Path, help='Private JSON settings file (default: agewise.local.json beside app.py)')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try: selected,source=select_directories(args.replays,args.config)
    except (ValueError,OSError) as exc: parser.error(str(exc))
    if selected is not None: LIBRARY.configure(selected)
    folders=LIBRARY.folders()
    if not folders: print('No replay folders selected/found. Configure agewise.local.json or pass --replays PATH, then restart.')
    print(f'Replay folder selection: {source}')
    LIBRARY.refresh(force=True)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'AoE2 Replay Lab API: http://127.0.0.1:{args.port} · local only · found {len(folders)} replay folder(s)')
    for folder in folders: print(f'  {folder}')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == '__main__': main()

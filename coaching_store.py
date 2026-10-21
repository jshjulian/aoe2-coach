"""Local coaching feedback/goal state. Never changes normalized analysis JSON."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from coaching import COACHING_VERSION, GOAL_ID, PLAN


class CoachingStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        db.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, key TEXT, data TEXT NOT NULL, PRIMARY KEY(kind,key))')
        db.execute('CREATE TABLE IF NOT EXISTS revisions (kind TEXT, key TEXT, data TEXT NOT NULL, recorded_at TEXT NOT NULL)')
        db.commit()
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _get(db, kind, key):
        row = db.execute('SELECT data FROM records WHERE kind=? AND key=?', (kind, key)).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def _put(db, kind, key, data):
        encoded = json.dumps(data, ensure_ascii=False)
        db.execute('INSERT INTO revisions VALUES (?,?,?,?)', (kind, key, encoded, datetime.now(timezone.utc).isoformat()))
        db.execute('INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,key) DO UPDATE SET data=excluded.data', (kind, key, encoded))

    @staticmethod
    def _key(review):
        return json.dumps([review['match_id'], review['player']['name']], ensure_ascii=False)

    def read(self, review):
        if not review.get('player'):
            return {'plan': None, 'feedback': None, 'goal': None, 'evaluations': [], 'rules_context': None}
        key, player = self._key(review), review['player']['name']
        with self._connect() as db:
            goal = self._get(db, 'goal', player)
            primary = review.get('primary')
            feedback_key = json.dumps([key, primary['id'], COACHING_VERSION]) if primary else ''
            evaluations = [json.loads(row[0]) for row in db.execute('SELECT data FROM records WHERE kind=?', ('evaluation',))]
            return {'rules_context': self._get(db, 'rules_context', key), 'plan': self._get(db, 'plan', key), 'feedback': self._get(db, 'feedback', feedback_key),
                    'goal': goal, 'evaluations': [e for e in evaluations if goal and e['selection_id'] == goal['selection_id']]}

    def save(self, review, payload):
        if not review.get('player'):
            raise ValueError('An unambiguous player must be selected.')
        key, player = self._key(review), review['player']['name']
        op = payload.get('operation')
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            # Serialize goal selection/evaluation checks and writes across HTTP threads.
            db.execute('BEGIN IMMEDIATE')
            if op == 'rules_context':
                rules = payload.get('rules')
                if rules not in ('standard', 'unknown'):
                    raise ValueError('Rules declaration must be standard or unknown; it cannot verify or override parser facts.')
                self._put(db, 'rules_context', key, {'version': 1, 'rules': rules, 'match_id': review['match_id'],
                    'player': player, 'declared_at': now, 'provenance': 'retrospective_user_annotation_not_parser_fact'})
            elif op == 'plan':
                plan = payload.get('plan', '')
                if plan not in ('', PLAN):
                    raise ValueError('Only the scoped Scouts → Knights plan or no plan is supported in this MVP.')
                self._put(db, 'plan', key, {'id': plan, 'confirmed': payload.get('confirmed') is True,
                                          'declared_at': now, 'provenance': 'retrospective_user_annotation'})
            elif op == 'feedback':
                primary = review.get('primary')
                verdict, note = payload.get('verdict'), payload.get('note', '')
                if not primary or payload.get('recommendation_id') != primary['id']:
                    raise ValueError('Advice no longer matches this review; reload before annotating.')
                if verdict not in ('useful', 'incorrect', 'inconclusive') or not isinstance(note, str) or len(note) > 2000:
                    raise ValueError('Invalid feedback status or note (maximum 2000 characters).')
                feedback_key = json.dumps([key, primary['id'], COACHING_VERSION])
                self._put(db, 'feedback', feedback_key,
                          {'verdict': verdict, 'note': note, 'match_id': review['match_id'],
                           'recommendation_id': primary['id'], 'rule_version': primary['rule_version'],
                           'coaching_version': COACHING_VERSION, 'analysis_version': review['analysis_schema_version'],
                           'updated_at': now, 'provenance': 'user_annotation_not_parser_fact'})
            elif op == 'select_goal':
                # New practice remains a separate revisioned record kind; never silently replace it.
                pointer = self._get(db, 'practice_active', player) or {}
                if pointer.get('focus_id'):
                    raise ValueError('Retire the current practice focus explicitly before selecting a legacy goal.')
                if not review['practice_goals'] or review['practice_goals'][0]['id'] != GOAL_ID:
                    raise ValueError('No eligible goal suggestion for this match.')
                previous = self._get(db, 'goal', player)
                if previous and previous['active']:
                    raise ValueError('A practice goal is already active. Stop it explicitly before replacing it.')
                self._put(db, 'goal', player, {'selection_id': now, 'goal_id': GOAL_ID, 'version': 1,
                    'player': player, 'active': True, 'selected_at': now, 'baseline_match_id': review['match_id'],
                    'baseline_seconds': review['indicators']['knight_after_castle_seconds'],
                    'scope': review['comparison_scope'], 'label': review['practice_goals'][0]['label']})
            elif op == 'stop_goal':
                goal = self._get(db, 'goal', player)
                if goal:
                    goal['active'] = False
                    self._put(db, 'goal', player, goal)
            elif op == 'evaluate_goal':
                goal = self._get(db, 'goal', player)
                if not goal or not goal['active']:
                    raise ValueError('Select an active goal first.')
                if review['match_id'] == goal['baseline_match_id'] or payload.get('played_after_selection') is not True:
                    raise ValueError('Confirm this different match was played after goal selection; file dates are not sufficient.')
                checklist, adaptation = payload.get('checklist'), payload.get('adaptation')
                same_scope = review['comparison_scope'] == goal['scope']
                if checklist == 'not_applicable' and review['comparison_scope']:
                    # An explicit N/A is excluded from comparison; do not require matching aggression cues.
                    keys = ('player', 'civilization', 'map', 'format', 'plan', 'duration_band')
                    same_scope = all(review['comparison_scope'].get(key) == goal['scope'].get(key) for key in keys)
                if not same_scope or review['plan']['status'] != 'confirmed':
                    raise ValueError('Not comparable: player, civ, map, format, plan, duration band and pressure context must match. Unknown pressure is not verified safety.')
                if checklist not in ('yes', 'no', 'uncertain', 'not_applicable') or adaptation not in ('yes', 'no', 'uncertain'):
                    raise ValueError('Report checklist completion and whether defense/plan adaptation applied.')
                value = review['indicators'].get('knight_after_castle_seconds')
                metric_status = 'not_applicable' if checklist == 'not_applicable' else 'needs_review' if adaptation != 'no' else 'observed' if value is not None else 'missing'
                self._put(db, 'evaluation', json.dumps([goal['selection_id'], player, review['match_id']]),
                          {'selection_id': goal['selection_id'], 'match_id': review['match_id'], 'recorded_at': now,
                           'checklist': checklist, 'adaptation': adaptation, 'metric_status': metric_status,
                           'interval_seconds': value, 'delta_from_baseline_seconds': round(value-goal['baseline_seconds'], 3) if value is not None and metric_status == 'observed' else None,
                           'chronology_provenance': 'user_confirms_played_after_goal_selection',
                           'coaching_version': COACHING_VERSION})
            else:
                raise ValueError('Unsupported coaching-state operation.')
        return self.read(review)

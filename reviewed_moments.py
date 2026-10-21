"""Explicit local authored reviews, separate from automatic coaching and annotations.

References resolve only against an intact, active experimental observation batch.
Authorship is a local assertion, never independent validation or a causal verdict.
"""
import hashlib
import json
from pathlib import Path
from observations import METRICS, _atomic, _hash

VERSION = 1
MAX_JSON = 32 * 1024


def _text(value, limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 for c in value):
        raise ValueError('Bounded single-line review text required.')
    return value.strip()


def validate_moment(value, report, observation_store):
    if not isinstance(value,dict) or type(value.get('schema_version')) is not int or value['schema_version']!=VERSION:
        raise ValueError('Unsupported authored review schema.')
    if not _hash(value.get('match_id')) or value['match_id']!=report['match_id']:
        raise ValueError('Authored review content identity mismatch.')
    build=report.get('replay_provenance',{}).get('build_version')
    if type(build) is not int or type(value.get('replay_build')) is not int or value['replay_build']!=build:
        raise ValueError('Authored review recorded build mismatch.')
    player=value.get('player');players=report['players']
    if not isinstance(player,dict) or type(player.get('id')) is not int or player not in [{k:p[k] for k in ('id','name','civilization')} for p in players]:
        raise ValueError('Exact reviewed player identity required.')
    if value.get('author_kind') not in ('assistant','user') or not _hash(value.get('observation_batch_id')):
        raise ValueError('Explicit local authorship and observation batch required.')
    clean={k:value[k] for k in ('schema_version','match_id','replay_build','player','author_kind','observation_batch_id')}
    for key,limit in [('title',100),('summary',600),('practice',400)]:clean[key]=_text(value.get(key),limit)
    for key in ('alternatives','limitations'):
        items=value.get(key)
        if not isinstance(items,list) or not 1<=len(items)<=4:raise ValueError('Explicit alternatives and limitations required.')
        clean[key]=[_text(s,300) for s in items]
    refs=value.get('references')
    if not isinstance(refs,list) or not 1<=len(refs)<=12:raise ValueError('Use 1..12 observation references.')
    seen=set();cache={};facts=[];clean_refs=[]
    for ref in refs:
        if not isinstance(ref,dict):raise ValueError('Observation reference required.')
        pid,metric,t=(ref.get(k) for k in ('player_id','metric','time_seconds'))
        if type(pid) is not int or type(t) is not int or not isinstance(metric,str) or metric not in METRICS:raise ValueError('Invalid reference identity/metric/clock.')
        identity=(pid,metric,t)
        if identity in seen:raise ValueError('Duplicate observation reference.')
        seen.add(identity)
        source=next((p for p in players if p['id']==pid),None)
        if source is None:raise ValueError('Unknown reference player.')
        if pid not in cache:cache[pid]=observation_store.read(report,source['name'])
        data=cache[pid]
        if data['status']!='experimental' or data['batch_id']!=clean['observation_batch_id']:
            raise ValueError('Review evidence is not the intact active observation batch.')
        series=next((s for s in data['series'] if s['metric']==metric),None)
        point=next((p for p in series['points'] if p['time_seconds']==t),None) if series else None
        if point is None or point['quality']!='visually_checked' or point['value'] is None:
            raise ValueError('Review references require an exact visually checked observation.')
        clean_refs.append(dict(player_id=pid,metric=metric,time_seconds=t))
        facts.append({**clean_refs[-1], 'player_name':source['name'],'value':point['value'],
                      'label':METRICS[metric]['label'],'unit':METRICS[metric]['unit'],
                      'evidence_sha256':point['evidence_sha256']})
    anchor=value.get('anchor_seconds')
    if type(anchor) is not int or not any(r['player_id']==player['id'] and r['time_seconds']==anchor for r in clean_refs):
        raise ValueError('Anchor must resolve a checked observation for the reviewed player.')
    clean.update(anchor_seconds=anchor,references=clean_refs)
    return clean,facts


class ReviewedMomentStore:
    def __init__(self,root):self.root=Path(root)

    def _path(self,relative):
        path=(self.root/relative).resolve()
        if not path.is_relative_to(self.root.resolve()):raise ValueError('Review path outside local store.')
        return path

    def import_moment(self,value,report,observation_store):
        clean,_=validate_moment(value,report,observation_store)
        raw=json.dumps(clean,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()
        if len(raw)>MAX_JSON:raise ValueError('Authored review exceeds 32KB.')
        review_id=hashlib.sha256(raw).hexdigest()
        _atomic(self._path(f'reviews/{review_id}.json'),raw)
        _atomic(self._path(f'matches/{clean["match_id"]}.{clean["player"]["id"]}.json'),json.dumps({'review_id':review_id}).encode())
        return review_id

    def read(self,report,player_name,observation_store):
        result=dict(schema_version=VERSION,match_id=report['match_id'],status='not_reviewed',moment=None,
                    independently_validated=False,eligible_for_automatic_priority=False,causal_claim=False)
        if not _hash(report['match_id']):raise ValueError('Invalid content identity.')
        players=[p for p in report['players'] if p['name']==player_name]
        if len(players)!=1:result['status']='select_player';return result
        try:
            path=self._path(f'matches/{report["match_id"]}.{players[0]["id"]}.json')
            if not path.exists():return result
            if path.stat().st_size>256:raise ValueError('Oversized review pointer.')
            review_id=json.loads(path.read_text())['review_id']
            if not _hash(review_id):raise ValueError('Invalid review ID.')
            archive=self._path(f'reviews/{review_id}.json')
            if archive.stat().st_size>MAX_JSON:raise ValueError('Oversized review archive.')
            raw=archive.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=review_id:raise ValueError('Review integrity failure.')
            clean,facts=validate_moment(json.loads(raw),report,observation_store)
            if clean['player']['id']!=players[0]['id']:raise ValueError('Reviewed player mismatch.')
            result.update(status='available',moment={**clean,'review_id':review_id,'facts':facts})
        except (OSError,ValueError,KeyError,TypeError):
            result.update(status='unavailable',reason='Authored review or its active observation evidence failed checks. No review is displayed.')
        return result

"""Comparable manual practice reports, never verified behavior or skill progression.

Snapshots are captured only on explicit journal writes. No replay scans, historical
backfill, chronology inference, aliases, state qualification or automatic writes.
"""
import json
import sqlite3
from situations import _opposing

VERSION=1
LIMIT=500
AGES={'Feudal Age':'Feudal','Castle Age':'Castle','Imperial Age':'Imperial'}
STATUSES={'reported_attempt','reported_not_attempted','not_applicable','insufficient_evidence'}


def _profile(report,player,rules):
    p=report.get('replay_provenance') or {}
    opponents=[x for x in report.get('players',[]) if _opposing(player,x) is True]
    reason=None
    if len(report.get('players',[]))!=2 or len(opponents)!=1:reason='Current matched-history slice requires unambiguous 1v1 teams.'
    elif any(not isinstance(x,str) or not x or 'unknown' in x.lower() for x in [report.get('map'),player.get('civilization'),opponents[0].get('civilization')]):reason='Map or civilization context is missing.'
    elif p.get('provenance_version')!=2 or p.get('edition')!='DE' or type(p.get('build_version')) is not int or p['build_version']<=0 or type(p.get('dataset_id')) is not int or p.get('dataset_id')!=100 or type(p.get('game_type_id')) is not int or p.get('game_type_id')!=0 or type(report.get('game_speed_id')) is not int or report['game_speed_id']<0:reason='Exact DE build, random-map dataset/mode and speed are required.'
    elif any(p.get(k) is not False for k in ('all_technologies','cheats','metadata_cheats','de_cheats')) or p.get('reported_mod') is not None or p.get('rms_mod_id') not in (None,0) or p.get('mod_compatibility') not in ('unknown','compatible'):reason='Rules metadata is missing or conflicts with this standard-rules comparison slice.'
    if reason:return None,reason,False
    if not (isinstance(rules,dict) and rules.get('rules')=='standard' and rules.get('match_id')==report['match_id'] and rules.get('player')==player['name'] and rules.get('provenance')=='retrospective_user_annotation_not_parser_fact'):
        return None,'Standard rules have not been explicitly declared for this replay. Empty mod metadata is not proof.',True
    return dict(edition=p['edition'],build=p['build_version'],dataset=p['dataset_id'],mode=p['game_type_id'],speed=report['game_speed_id'],map=report['map'],civilization=player['civilization'],opponent_civilization=opponents[0]['civilization'],rules_basis='user_reported_standard_not_engine_verified'),None,True


def snapshot(report,packet,gameplay,situation,rules):
    """Current server-generated reference; journal save must explicitly copy it."""
    try:
        focus=packet.get('active_focus');player=packet['current_match']['player']
        if not focus or not player:return None
        raw=next(p for p in report['players'] if p['id']==player['id'] and p['name']==player['name'])
        result=dict(schema_version=VERSION,focus_id=focus['id'],match_id=report['match_id'],player=player,eligible=False,profile=None,signature=None,cue_phase=None,evidence=[],reason=None,can_declare_standard_rules=False)
        profile,reason,can_declare=_profile(report,raw,rules)
        result.update(profile=profile,reason=reason)
        source=focus.get('source') or {};sha=source.get('knowledge_pack_sha256')
        if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
            result['reason']='This focus has no pinned gameplay comparison signature. Its manual history remains available; it is not retroactively qualified.';return result
        signature=dict(topic=source.get('topic'),rule_id=source.get('rule_id'),rule_version=source.get('rule_version'),pack_sha256=sha)
        result['signature']=signature
        candidates=gameplay.get('candidates',[]) if gameplay and gameplay.get('match_id')==report['match_id'] and gameplay.get('player')==player and gameplay.get('causal_claim') is False else []
        matching=[c for c in candidates if c.get('topic')==signature['topic'] and c.get('rule_id')==signature['rule_id'] and c.get('rule_version')==signature['rule_version'] and c.get('source',{}).get('pack_sha256')==sha]
        if not matching:result['reason']='No same-version pinned command cue for this focus. Missing cues do not mean no opportunity.';return result
        events={e['id']:e for e in report['events']};phases=set();refs=[]
        ages=sorted([e for e in report['events'] if e.get('player_id')==player['id'] and e.get('status')=='observed_milestone' and e.get('action')=='AGE_REACHED' and e.get('technology') in AGES],key=lambda e:e['time_seconds'])
        age_order=[list(AGES).index(e['technology']) for e in ages]
        if age_order!=sorted(set(age_order)):result['reason']='Age-cue ordering is ambiguous.';return result
        for c in matching:
            e=events.get(c.get('replay_anchor',{}).get('event_id'))
            if not e or e.get('player_id')!=player['id']:continue
            before=[a for a in ages if a['time_seconds']<=e['time_seconds']]
            phases.add(AGES[before[-1]['technology']] if before else None)
            refs.append(dict(event_id=e['id'],time_seconds=e['time_seconds']))
        result['evidence']=refs[:3]
        if len(phases)!=1 or None in phases:result['reason']='Cue phase is missing or spans multiple ages; the reported opportunity cannot be assigned a comparable phase.';return result
        result['cue_phase']=next(iter(phases))
        result['can_declare_standard_rules']=can_declare and not bool(profile)
        result['eligible']=bool(profile)
        return result
    except (ValueError,KeyError,TypeError,AttributeError,StopIteration):
        return dict(schema_version=VERSION,eligible=False,reason='Comparison context could not be established. Journal and automatic review remain separate.',can_declare_standard_rules=False)


def _same(a,b):
    return all(a.get(k)==b.get(k) for k in ('profile','signature','cue_phase'))


def context(store,packet):
    out=dict(schema_version=VERSION,status='choose_focus',match_id=packet.get('current_match',{}).get('match_id'),player=packet.get('current_match',{}).get('player'),focus_id=None,
             scope='Current focus only; most recent 500 journal records in logging order, not gameplay chronology.',reference=packet.get('comparison_snapshot'),
             total_journal_entries=0,scanned_entries=0,truncated=False,counts={s:0 for s in sorted(STATUSES)},matched_counts={s:0 for s in sorted(STATUSES)},
             confirmed_opportunities=0,known_attempt_answers=0,uncertain_attempt_answers=0,sample_status='insufficient_comparable_evidence',entries=[],excluded_count=0,exclusion_reasons={},
             eligible_for_automatic_priority=False,skill_improvement_established=False,verified_execution=False,trend_established=False,
             limitation='Descriptive user reports in matching recorded contexts, not equivalent battles, verified attempts, skill improvement or causal effects. Standard rules are user-declared, not engine-verified.')
    if packet.get('status')=='unavailable':out['status']='unavailable';return out
    focus=packet.get('active_focus')
    if not focus:return out
    out.update(focus_id=focus['id'],status='active')
    try:
        name=packet['current_match']['player']['name']
        if focus['player_name']!=name or focus['origin']['player']['name']!=name:raise ValueError('Focus identity mismatch')
        prefix=focus['id']+':'
        with store._connect() as db:
            out['total_journal_entries']=db.execute("SELECT count(*) FROM records WHERE kind='practice_log' AND substr(key,1,?)=?",(len(prefix),prefix)).fetchone()[0]
            rows=db.execute("SELECT key,data FROM records WHERE kind='practice_log' AND substr(key,1,?)=? ORDER BY rowid DESC LIMIT ?",(len(prefix),prefix,LIMIT)).fetchall()
        out['scanned_entries']=len(rows);out['truncated']=out['total_journal_entries']>len(rows)
        ref=out['reference'];reference_ok=isinstance(ref,dict) and ref.get('eligible') is True and ref.get('focus_id')==focus['id'] and ref.get('match_id')==out['match_id'] and ref.get('player')==out['player']
        for key,text in rows:
            row=json.loads(text);m=row['match'];mid=m['match_id'];status=row['status']
            if row['focus_id']!=focus['id'] or m['player']['name']!=name or type(m['player']['id']) is not int or m['player']['id']<=0 or key!=prefix+mid or len(mid)!=64 or any(c not in '0123456789abcdef' for c in mid) or status not in STATUSES or row.get('provenance')!='user_report_not_verified_execution' or row.get('skill_improvement_established') is not False or row.get('chronology_provenance')!='user_confirms_played_after_focus_selection':raise ValueError('Invalid journal identity/qualification')
            expected='not_applicable' if row['opportunity']=='no' else 'reported_attempt' if row['opportunity']=='yes' and row['attempt']=='yes' else 'reported_not_attempted' if row['opportunity']=='yes' and row['attempt']=='no' else 'insufficient_evidence'
            if row['opportunity'] not in ('yes','no','uncertain') or row['attempt'] not in ('yes','no','uncertain') or expected!=status or row['opportunity']!='yes' and row['attempt']!='uncertain':raise ValueError('Invalid journal answer')
            snap=row.get('comparison_snapshot');reason=None
            if mid==focus['origin']['match_id']:reason='Selection replay is a baseline, not a later opportunity.'
            elif not isinstance(snap,dict):reason='Entry predates comparison snapshots; no historical backfill.'
            elif snap.get('schema_version')!=VERSION or snap.get('focus_id')!=focus['id'] or snap.get('match_id')!=mid or snap.get('player')!=m['player'] or type(snap.get('eligible')) is not bool or type(snap.get('can_declare_standard_rules')) is not bool:raise ValueError('Snapshot identity/qualification mismatch')
            elif not isinstance(snap.get('signature'),dict) or snap['signature']!={k:focus['source'].get(src) for k,src in [('topic','topic'),('rule_id','rule_id'),('rule_version','rule_version'),('pack_sha256','knowledge_pack_sha256')]}:raise ValueError('Snapshot rule signature mismatch')
            elif snap.get('eligible') and (not isinstance(snap.get('profile'),dict) or snap['profile'].get('map')!=m.get('map') or snap['profile'].get('build')!=m.get('build') or snap['profile'].get('civilization')!=m['player'].get('civilization') or snap.get('cue_phase') not in ('Feudal','Castle','Imperial') or not isinstance(snap.get('evidence'),list) or not snap['evidence'] or any(not isinstance(e,dict) or not isinstance(e.get('event_id'),str) or type(e.get('time_seconds')) not in (int,float) for e in snap['evidence'])):raise ValueError('Snapshot profile/evidence mismatch')
            elif not snap.get('eligible'):reason=snap.get('reason') or 'Entry has incomplete comparison context.'
            elif not reference_ok:reason='Selected replay has no eligible comparison reference.'
            elif not _same(snap,ref):reason='Different recorded map/civs/build/mode/speed, cue phase or pinned rule version.'
            matched=reason is None
            out['counts'][status]+=1
            if matched:
                out['matched_counts'][status]+=1
                if row['opportunity']=='yes' and row['attempt']=='uncertain':out['uncertain_attempt_answers']+=1
            else:out['excluded_count']+=1;out['exclusion_reasons'][reason]=out['exclusion_reasons'].get(reason,0)+1
            out['entries'].append(dict(match_id=mid,player=m['player'],map=m.get('map'),recorded_at=row['recorded_at'],status=status,matched=matched,exclusion_reason=reason,evidence=(snap.get('evidence',[]) if matched else row.get('evidence',[]))[:3]))
        c=out['matched_counts'];out['confirmed_opportunities']=c['reported_attempt']+c['reported_not_attempted']
        # Opportunity=yes/attempt=uncertain is not a known attempt answer.
        out['known_attempt_answers']=out['confirmed_opportunities']
        out['confirmed_opportunities']+=out['uncertain_attempt_answers']
        if out['known_attempt_answers']>=3:out['sample_status']='descriptive_sample_available'
        return out
    except (ValueError,KeyError,TypeError,AttributeError,OSError,sqlite3.Error):
        out.update(status='unavailable',entries=[],counts={s:0 for s in sorted(STATUSES)},matched_counts={s:0 for s in sorted(STATUSES)},reason='Progress could not be read safely. No journal records were reset.')
        return out

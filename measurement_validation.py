"""Offline reference-agreement dossier. Never qualifies or imports measurements.

Re-score source files, not submitted score summaries. Agreement, blindness and
partition declarations are not independent verification of engine truth.
"""
from collections import Counter,defaultdict
from pathlib import Path
import measurement_audit as audit

VERSION=1
MAX_REVIEWERS=4


def _scope(task,spec):
    audit.validate_spec(spec)
    mid=task['match_id']
    partition='development' if mid in spec['development_match_ids'] else 'held_out' if mid in spec['held_out_match_ids'] else None
    if partition is None or task['partition']!=partition or task.get('dataset_spec_sha256')!=audit.digest(audit.encoded(spec)) or task.get('source_code_sha256')!=spec['source_code_sha256']:
        raise ValueError('Task does not match the exact declared dataset partition/code specification.')
    roles=task.get('roles')
    if (type(task.get('replay_build')) is not int or task['replay_build']<=0 or
        task.get('provider_ui_version')!='1.26.0' or
        task.get('operator_binding')!='operator_asserted_not_automatically_verified' or
        not isinstance(roles,dict) or set(roles)!={'left','right'}):
        raise ValueError('Unsupported or missing build/provider/operator identity scope.')
    for p in roles.values():
        if not isinstance(p,dict) or type(p.get('id')) is not int or p['id']<=0 or any(not isinstance(p.get(k),str) or not p[k].strip() for k in ('name','civilization')):
            raise ValueError('Exact parser-side identities required.')
    if roles['left']['id']==roles['right']['id'] or roles['left']['name']==roles['right']['name']:
        raise ValueError('Ambiguous parser-side identity.')
    if {s['source_sha256'] for s in task['samples'] if s['field']=='clock'}!={f['source_sha256'] for f in task['frames']}:
        raise ValueError('Every frame needs an explicit clock sample; unreadable clocks stay unlabelled, not omitted.')
    for s in task['samples']:
        field=s['field'];side=None if field=='clock' else field.split('_')[0]
        kind='duration' if field=='clock' or field.endswith(('_tc_idle_seconds','_housed_seconds')) else 'integer'
        if s.get('kind')!=kind or s.get('role')!=side or (side is not None and type(s.get('player_id')) is not int) or s.get('player_id')!=(None if side is None else roles[side]['id']):
            raise ValueError('Measurement field/player/kind binding mismatch.')
    return dict(match_id=mid,partition=partition,replay_build=task['replay_build'],
                provider_ui_version=task['provider_ui_version'],roles=roles,
                source_code_sha256=task['source_code_sha256'],dataset_spec_sha256=task['dataset_spec_sha256'])


def assess(pack,spec,label_sets,predictions):
    """One bounded task, 1..4 distinct asserted reviewers; no pooled denominators."""
    if not isinstance(label_sets,list) or not 1<=len(label_sets)<=MAX_REVIEWERS:
        raise ValueError('Use 1..4 distinct reference label sets.')
    task=audit.validate_task(pack);scope=_scope(task,spec)
    scores=[audit.score_pack(pack,labels,predictions) for labels in label_sets]
    ids=[s['reviewer']['id'] for s in scores]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate reviewer identity; repeated labels are not independent references.')
    # Repeated tasks/candidate outputs do not create extra samples. Each source
    # sample appears once below; reviewer-specific diagnostics stay separate.
    by_reviewer=[{r['sample_id']:r for r in s['results']} for s in scores]
    rows=[];agreements={};totals=Counter();fields=defaultdict(Counter)
    candidate_shas={f['source_sha256'] for f in predictions['frames']}
    for sample in task['samples']:
        sid=sample['sample_id'];refs=[r[sid] for r in by_reviewer]
        statuses=[r['reference_status'] for r in refs]
        exact=[r['reference_value'] for r in refs if r['reference_status']=='exact']
        known={s for s in statuses if s!='unlabeled'}
        if len(refs)<2:state='single_reference'
        elif len(set(exact))>1 or len(known)>1:state='reference_disagreement'
        elif 'unlabeled' in statuses:state='incomplete_references'
        elif len(exact)==len(refs) and len(set(exact))==1:state='agreed_exact'
        elif not exact and len(set(statuses))==1:state='agreed_non_exact_status'
        else:state='reference_disagreement'
        # Same non-exact status never supplies a value, even if text looks numeric.
        value=exact[0] if state=='agreed_exact' else None
        agreements[sid]=(state,value)
        row=dict(sample_id=sid,source_sha256=sample['source_sha256'],field=sample['field'],
                 player_id=sample['player_id'],agreement=state,agreed_reference_value=value,
                 references=[dict(reviewer_id=ids[i],status=r['reference_status'],text=r['reference_text']) for i,r in enumerate(refs)],
                 candidate_value=refs[0]['candidate_value'],
                 candidate_frame_missing=sample['source_sha256'] not in candidate_shas)
        rows.append(row);totals[state]+=1;fields[sample['field']][state]+=1
    clocks={s['source_sha256']:agreements[s['sample_id']] for s in task['samples'] if s['field']=='clock'}
    pair_counts=Counter();bands=defaultdict(Counter)
    candidate_clocks={r['source_sha256']:r for r in scores[0]['results'] if r['field']=='clock'}
    for row in rows:
        frame=candidate_clocks.get(row['source_sha256'])
        clock_state,clock=clocks.get(row['source_sha256'],('missing_clock_reference',None))
        clock_candidate=frame['candidate_value'] if frame else None
        clock_status='no_agreed_exact_clock' if clock_state!='agreed_exact' else 'candidate_clock_frame_missing' if row['candidate_frame_missing'] else 'candidate_clock_missing' if clock_candidate is None else 'candidate_clock_wrong' if clock_candidate!=clock else 'clock_matches_agreed_reference'
        value=row['agreed_reference_value'];candidate=row['candidate_value']
        value_status='no_agreed_exact_value' if value is None else 'candidate_value_frame_missing' if row['candidate_frame_missing'] else 'candidate_abstained' if candidate is None else 'candidate_wrong_number' if candidate!=value else 'value_matches_agreed_reference'
        pair=value_status=='value_matches_agreed_reference' and clock_status=='clock_matches_agreed_reference'
        band='unanchored' if clock is None else 'before_20m' if clock<1200 else '20m_to_40m' if clock<2400 else '40m_to_60m' if clock<3600 else 'one_hour_or_later'
        row.update(value_status=value_status,clock_status=clock_status,clock_band=band,timeline_pair_matches=pair)
        pair_counts[value_status]+=1;pair_counts[clock_status]+=1
        if pair:pair_counts['matching_value_clock_pairs']+=1
        fields[row['field']][value_status]+=1
        if pair:fields[row['field']]['matching_value_clock_pairs']+=1
        bands[band][value_status]+=1
    human_blind=len(scores)>=2 and all(s['reviewer']['kind']=='human' and s['reviewer']['blind_to_predictions'] is True for s in scores)
    blockers=['operator_identity_not_independently_verified','metric_semantics_not_qualified','application_scope_and_acceptance_review_required']
    if scope['partition']=='development':blockers.append('development_match_not_held_out')
    if not human_blind:blockers.append('need_at_least_two_distinct_asserted_blind_human_references')
    if scores[0]['source_code_provenance']!='matched':blockers.append('candidate_extractor_code_unrecorded')
    if totals['reference_disagreement']:blockers.append('reference_disagreements_need_review')
    if any(totals[k] for k in ('single_reference','incomplete_references','agreed_non_exact_status')):blockers.append('not_all_samples_have_agreed_exact_references')
    if any(s['counts'].get('valid_looking_wrong_number',0) for s in scores):blockers.append('wrong_numbers_reported_by_reference_labels')
    if any(s['counts'].get('numeric_on_non_exact_reference',0) for s in scores):blockers.append('unsupported_numeric_precision_reported')
    if pair_counts['candidate_value_frame_missing']:blockers.append('candidate_frames_missing')
    if pair_counts['candidate_abstained']:blockers.append('candidate_abstentions_on_agreed_readable_values')
    if any(pair_counts[k] for k in ('no_agreed_exact_clock','candidate_clock_frame_missing','candidate_clock_missing','candidate_clock_wrong')):blockers.append('timeline_clock_coverage_incomplete')
    return dict(schema_version=VERSION,kind='measurement_validation_dossier',task_id=task['task_id'],scope=scope,
                assessment_code_sha256=audit.digest(Path(__file__).read_bytes()),
                scorer_code_sha256=scores[0]['scorer_code_sha256'],candidate_artifact_sha256=scores[0]['candidate_artifact_sha256'],
                status='blocked',blockers=blockers,sample_count=len(rows),frame_count=len(task['frames']),reference_set_count=len(scores),
                excluded_candidate_frames=scores[0]['excluded_candidate_frames'],
                clock_frame_counts=dict(Counter(r['clock_status'] for r in rows if r['field']=='clock')),
                non_clock_sample_count=sum(r['field']!='clock' for r in rows),
                non_clock_timeline_pair_match_count=sum(r['timeline_pair_matches'] for r in rows if r['field']!='clock'),
                asserted_blind_human_reference_set=human_blind,reviewer_assertions_independently_verified=False,
                agreement_counts=dict(totals),pair_counts=dict(pair_counts),
                per_field={k:dict(v) for k,v in sorted(fields.items())},per_clock_band={k:dict(v) for k,v in sorted(bands.items())},
                reference_diagnostics=[{k:s[k] for k in ('reviewer','labels_artifact_sha256','source_code_provenance','counts','exact_reference_count','timeline_pair_match_count','clock_frame_counts')} for s in scores],
                results=rows,validated_for_application=False,eligible_for_primary_coaching=False,
                limitations=['Agreement is between local reviewer assertions, not independently verified engine state.',
                             'Blindness, whole-match holdout and operator identity are declarations, not certified independence.',
                             'One task and its fixed provider/build/crop/code scope cannot establish cross-match accuracy or an error-rate guarantee.',
                             'Clock bands are numeric coverage, not age phases. Missing clocks are not inferred or interpolated.',
                             'Matching value/clock pairs do not prove parser/HUD synchronization, villager semantics, military utilization or a cause of losses.',
                             'No dossier, perfect synthetic test or claimed qualification flag activates application state.'])

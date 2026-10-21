"use client";

import type { PythonAnalysis } from '@/lib/coachAnalysis';
import type { OpenEvidence } from '@/lib/coachingReview';
import type { SituationReview as Review } from '@/lib/situationReview';
import { MatchReviewTimeline } from './MatchReviewTimeline';

const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const button = 'rounded-lg border border-[color:var(--border-subtle)] px-3 py-2 text-xs hover:bg-[color:var(--panel)]';

export function SituationReview({ analysis, review, profileName, onOpenEvidence }: {
  analysis: PythonAnalysis; review?: Review; profileName: string; onOpenEvidence: OpenEvidence;
}) {
  const byId = new Map(analysis.events.map(event => [event.id, event]));
  function evidence(ids: string[]) {
    return [...new Set(ids)].map(id => {
      const event = byId.get(id);
      return event ? <button key={id} className={button} data-situation-evidence={id} onClick={() => onOpenEvidence(event, 'Recorded command evidence')}>
        {event.time} · {event.player} · {event.action}{event.building ? ` ${event.building}` : event.unit ? ` ${event.unit}` : event.order ? ` ${event.order}` : ''} · {id}
      </button> : <span key={id}>Unresolved evidence {id}</span>;
    });
  }
  function watch(id: string, label: string) {
    const event = byId.get(id);
    if (event) onOpenEvidence(event, label);
  }
  const primary = review?.recommendations[0];
  const secondary = review?.recommendations[1];
  const positive = review?.positive;
  function details(question: NonNullable<Review['recommendations']>[number]) {
    if (!review) return null;
    const episode = review.episodes?.find(row => row.id === question.episode_id);
    const incidents = review.incidents.filter(row => episode ? episode.incident_ids.includes(row.id) : row.id === question.incident_id);
    const menu = review.knowledge?.options_by_incident.find(row => row.incident_id === question.incident_id);
    return <details className="mt-3 text-xs"><summary className="cursor-pointer font-semibold text-[color:var(--muted)]">Evidence & alternatives</summary>
      <div className="mt-3 space-y-3 border-t border-[color:var(--border-subtle)] pt-3">
        <p><b>What to investigate:</b> {question.question}</p>
        {episode && <p>Grouped command window {episode.window_seconds.map(clock).join('–')}; follow-up search {episode.review_window_seconds.map(clock).join('–')}. Later inputs were not necessarily available at the review anchor.</p>}
        <p><b>Recorded follow-up:</b> {question.response_summary}</p>
        <p><b>Principle:</b> {question.principle}</p>
        <p><b>Full practice exercise:</b> {question.exercise}</p>
        {incidents.length > 1 && <p>Related nearby command windows have been grouped into one review topic. Association does not establish causation.</p>}
        <div className="flex flex-wrap gap-2">{evidence(incidents.map(i => i.replay_anchor.event_id))}</div>
        <ul className="list-disc pl-4">{question.uncertainties.map(text => <li key={text}>{text}</li>)}</ul>
        {incidents.map(incident => <details key={incident.id} className="rounded border border-[color:var(--border-subtle)] p-2"><summary>{incident.window_seconds.map(clock).join('–')} · {incident.type === 'forward_build_command' ? 'Forward placement' : 'Nearby opponent orders'} · command evidence</summary>
          <p className="mt-2">{incident.observation}</p><p className="mt-2">Searched response window {incident.review_window_seconds.map(clock).join('–')}; later commands are retrospective context.</p>
          {incident.responses.map(response => <p key={response.event_id} className="mt-1">{clock(response.time_seconds)} · {response.temporal_relation} the command cluster · {response.spatial_relation.replaceAll('_', ' ')}. Intent and effectiveness unverified.</p>)}
          <ul className="mt-2 list-disc pl-4">{incident.alternatives.map(text => <li key={text}>{text}</li>)}</ul>
          <p className="mt-2">Outcome: {incident.outcome.reason} Evidence: {incident.quality.evidence_strength.replaceAll('_', ' ')}; vision {incident.quality.vision}; selected unit types {incident.quality.unit_types}; stream completeness {incident.quality.stream_completeness}. {incident.quality.right_censored ? 'Response window clipped by replay end.' : ''}</p>
          <div className="mt-2 flex flex-wrap gap-2">{evidence(incident.event_ids)}</div>
        </details>)}
        {episode && <details><summary>Additional production / research / construction context</summary><p className="mt-2">These are time-associated inputs, not completed units or a locally identified army.</p><div className="mt-2 flex flex-wrap gap-2">{evidence(episode.context_event_ids)}</div></details>}
        {menu && <div><b>Conditional age-available catalog choices — not ranked counters or ready state</b><p>{review.knowledge?.reason}</p>{menu.options.map(option => <a key={`${option.kind}:${option.entity_id}`} href={option.source_url} target="_blank" rel="noreferrer" referrerPolicy="no-referrer" className="mr-3 underline">{option.name}</a>)}</div>}
        <details><summary>Priority reasoning & rule version</summary><ul className="mt-2 list-disc pl-4">{question.priority_reasons.map(text => <li key={text}>{text}</li>)}</ul><p className="mt-2">{question.rule_id} v{question.rule_version}. No saved practice goal or legacy feedback ID changed.</p></details>
      </div>
    </details>;
  }
  return <section data-situation-status={review?.status ?? 'loading'}>
    <h2 className="text-xs font-bold uppercase tracking-widest text-[color:var(--muted)]">Match review</h2>
    {!profileName ? <p className="mt-3">Choose your player in the library.</p> : !review ? <p className="mt-3">Preparing your review…</p> : <>
      {primary ? <article data-situation-question={primary.id} data-review-topic={primary.topic} data-primary-review className="mt-3">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(220px,1fr)]">
          <div><p className="text-xs font-semibold text-sky-700 dark:text-sky-300">Focus · {clock(primary.replay_anchor.time_seconds)}</p>
            <h3 className="mt-1 text-xl font-bold leading-tight sm:text-2xl">{primary.title}</h3>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed">{primary.summary}</p>
            <div className="mt-3 flex flex-wrap items-center gap-3"><button className="rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-600" style={{color: '#fff'}} data-review-watch={primary.replay_anchor.event_id} onClick={() => watch(primary.replay_anchor.event_id, primary.title)}>Review {clock(primary.replay_anchor.time_seconds)} →</button><span className="text-[11px] text-[color:var(--muted)]">{primary.uncertainty_label}</span></div>
          </div>
          <div className="rounded-xl bg-[color:var(--panel)] p-4"><p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">Next game · one practice</p><p data-practice-suggestion className="mt-2 text-sm leading-relaxed">{primary.practice_short ?? primary.exercise}</p></div>
        </div>
        {details(primary)}
      </article> : <div className="mt-3"><h3 className="text-lg font-semibold">No clear priority from the available evidence</h3><p className="mt-2 text-sm">No reviewable pressure or forward placement was established near your starting base. This does not mean the game was mistake-free.</p><details className="mt-2 text-xs"><summary>Coverage details</summary><p className="mt-2">{review.abstention_reason}</p></details></div>}
      {positive && <div data-supported-positive className="mt-4 flex flex-wrap items-baseline gap-x-2 rounded-lg border-l-2 border-teal-500 bg-teal-500/5 px-3 py-2"><p className="text-[10px] font-bold uppercase tracking-widest text-teal-700 dark:text-teal-300">Recorded positive</p><p className="text-xs">{positive.text}</p><details className="w-full text-xs text-[color:var(--muted)]"><summary>Evidence</summary><p className="mt-2">{positive.caveat}</p><div className="mt-2 flex flex-wrap gap-2">{evidence(positive.event_ids)}</div></details></div>}
      {secondary && <article data-situation-question={secondary.id} data-review-topic={secondary.topic} className="mt-4 flex flex-wrap items-start justify-between gap-3 border-t border-[color:var(--border-subtle)] pt-3"><div className="min-w-0 flex-1"><p className="text-[10px] font-semibold uppercase tracking-widest text-[color:var(--muted)]">Also worth a look · a different decision</p><h3 className="mt-1 text-sm font-bold">{secondary.title}</h3><p className="mt-1 text-xs">{secondary.summary}</p>{details(secondary)}</div><button className={button} onClick={() => watch(secondary.replay_anchor.event_id, secondary.title)}>{clock(secondary.replay_anchor.time_seconds)} →</button></article>}
      <MatchReviewTimeline analysis={analysis} review={review} onOpenEvidence={onOpenEvidence} />
      <details className="mt-3 border-t border-[color:var(--border-subtle)] pt-3 text-xs text-[color:var(--muted)]"><summary className="font-semibold">All incidents & developer / evidence details</summary>
        <p className="mt-3">Searched {review.coverage.searched_window_seconds?.map(clock).join('–') ?? 'unavailable'} · {review.coverage.spatial_scope}. {review.incidents.length} raw incidents / {review.episodes?.length ?? 0} grouped episodes. Full command-stream completeness is unknown.</p>
        <p className="mt-2">Economy, population and standing-army graphs are withheld: no independently validated live state is available. The timeline shows milestones and command inputs, not completed production or combat.</p>
        <details className="mt-3"><summary>All timeline markers</summary><div className="mt-2 flex flex-wrap gap-2">{review.timeline?.map(marker => <button key={marker.id} className={button} onClick={() => watch(marker.event_id, marker.label)}>{clock(marker.time_seconds)} · {marker.label}</button>)}</div></details>
        <details className="mt-3"><summary>All raw incident evidence</summary>{review.incidents.map(incident => <details key={incident.id} className="mt-3"><summary>{incident.window_seconds.map(clock).join('–')} · {incident.type}</summary><p>{incident.observation}</p><div className="mt-2 flex flex-wrap gap-2">{evidence(incident.event_ids)}</div><pre className="mt-2 overflow-auto whitespace-pre-wrap text-[10px]">{JSON.stringify(incident, null, 2)}</pre></details>)}</details>
        {review.knowledge && <details className="mt-3"><summary>Civilization knowledge & source applicability</summary><p className="mt-2">{review.knowledge.status}: {review.knowledge.reason}</p>{review.knowledge.source && <p>Update {review.knowledge.source.declared_update}; commit {review.knowledge.source.commit}; pack {review.knowledge.source.pack_id} v{review.knowledge.source.pack_version}; menu v{review.knowledge.menu_version}.</p>}{review.knowledge.reference_facts.map(fact => <p key={fact.id} className="mt-2">Reference only: {fact.text} {fact.source_refs.map(ref => <a key={ref.id} href={ref.url} target="_blank" rel="noreferrer" referrerPolicy="no-referrer" className="underline">source </a>)}</p>)}</details>}
        <details className="mt-3"><summary>Ranking, associations & limitations</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap text-[10px]">{JSON.stringify({review_version: review.review_version, ranking_policy: review.ranking_policy, decisions: review.decisions, links: review.links, coverage: review.coverage, limitations: review.limitations}, null, 2)}</pre></details>
      </details>
    </>}
  </section>;
}

"use client";

import { useEffect, useMemo, useState } from 'react';
import type { PythonAnalysis } from '@/lib/coachAnalysis';
import type { OpenEvidence } from '@/lib/coachingReview';
import type { KnowledgeRef, MatchupReview, RulesContext } from '@/lib/matchupReview';

const ages: Record<number, string> = { 1: 'Dark', 2: 'Feudal', 3: 'Castle', 4: 'Imperial' };
const button = 'rounded border border-[color:var(--border-subtle)] px-2 py-1 text-xs hover:bg-[color:var(--panel)] disabled:opacity-50';
const clock = (value: number) => `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}`;

function Sources({ refs }: { refs: KnowledgeRef[] }) {
  return <details className="mt-2 text-xs text-[color:var(--muted)]"><summary>Verified reference links</summary><ul className="mt-2 space-y-1">{refs.map(ref => <li key={ref.id}><a href={ref.url} target="_blank" rel="noreferrer" referrerPolicy="no-referrer" className="underline">{ref.civilization} · {ref.kind} {ref.entity_id} · {ref.field}</a>{ref.age_id != null ? ` · ${ages[ref.age_id]} reference age` : ''}{ref.available != null ? ` · ${ref.available ? 'catalog available' : 'catalog unavailable'}` : ''}</li>)}</ul></details>;
}

export function MatchupBriefing({ analysis, matchup, rulesContext, busy, onSaveRules, onOpenEvidence }: {
  analysis: PythonAnalysis;
  matchup: MatchupReview;
  rulesContext?: RulesContext | null;
  busy: boolean;
  onSaveRules: (rules: 'standard' | 'unknown') => void;
  onOpenEvidence: OpenEvidence;
}) {
  const [standard, setStandard] = useState(rulesContext?.rules === 'standard');
  useEffect(() => { setStandard(rulesContext?.rules === 'standard'); }, [rulesContext?.rules, rulesContext?.declared_at]);
  const byId = useMemo(() => new Map(analysis.events.map(event => [event.id, event])), [analysis]);
  const conditional = matchup.compatibility.status === 'conditional_user_context';
  function evidence(ids: string[]) {
    return [...new Set(ids)].map(id => {
      const event = byId.get(id);
      return event && <button key={id} className={button} onClick={() => onOpenEvidence(event, 'Matchup review evidence')}>
        {event.time} · {event.action} {event.unit ?? event.technology ?? event.building ?? ''}
      </button>;
    });
  }
  return <section data-matchup-status={matchup.status} className="panel-strong rounded-xl border border-[color:var(--border-subtle)] p-5">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="headline text-xl font-bold">Matchup briefing{matchup.opponent ? ` · ${matchup.player?.civilization ?? 'Selected civilization'} vs ${matchup.opponent.civilization}` : ''}</h2><span className="text-xs text-[color:var(--muted)]">{conditional ? 'Conditional · user-declared rules' : 'Reference only · tips withheld'}</span></div>
    <p className="mt-2 text-xs text-[color:var(--muted)]">Separate from the primary practice priority. No intended-plan confirmation is needed. Civilization options are not an observed army, and replay-visible opponent commands may not have been visible in-game.</p>
    {matchup.compatibility.reasons.map((reason, i) => <p key={i} className="mt-2 text-sm">{reason}</p>)}
    {matchup.abstention_reason && !matchup.compatibility.reasons.includes(matchup.abstention_reason) && <p className="mt-2 text-sm">{matchup.abstention_reason}</p>}
    {matchup.reference_facts.length > 0 && <details className="mt-4 rounded-lg bg-[color:var(--panel)] p-3" open>
      <summary className="text-sm font-semibold">Standard-rules source capabilities · not assertions about this replay</summary>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">{matchup.reference_facts.map(fact => <article key={fact.id} className="rounded border border-[color:var(--border-subtle)] p-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--muted)]">{fact.civilization} · {ages[fact.minimum_age]} onward in reference</p><p className="mt-1 text-sm">{fact.text}</p><Sources refs={fact.source_refs} />
      </article>)}</div>
    </details>}
    {matchup.observations.length > 0 && <details className="mt-3 rounded-lg border border-[color:var(--border-subtle)] p-3"><summary className="text-sm font-semibold">Recorded parser-resolved queue commands · not produced units</summary>
      {matchup.observations.map(observation => <div key={observation.side} className="mt-3"><p className="text-sm"><b>{observation.side === 'you' ? 'Selected player' : 'Opponent'}:</b> {observation.command_count} relevant queue commands ({observation.unit_labels.join(', ')}). Not produced units.</p><p className="mt-1 text-xs text-[color:var(--muted)]">{observation.meaning} No listed pattern does not establish absence.</p><div className="mt-2 flex flex-wrap gap-2">{evidence(observation.event_ids)}</div></div>)}
    </details>}
    {matchup.tips.map(tip => <article key={tip.id} className="mt-4 rounded-lg border border-sky-500/30 p-4">
      <p className="text-xs font-semibold">Conditional retrospective review question · not a mistake verdict</p><h3 className="mt-2 font-bold">{tip.title}</h3>
      <p className="mt-2 text-xs">Only if your separate standard-rules declaration is correct; mods remain independently unverified.</p>
      {tip.observations.map(text => <p key={text} className="mt-2 text-sm"><b>Recorded:</b> {text}</p>)}
      <p className="mt-2 text-sm"><b>Possible meaning:</b> {tip.interpretation}</p><p className="mt-2 text-sm"><b>Review question:</b> {tip.action}</p>
      <div className="mt-3 flex flex-wrap gap-2">{evidence([tip.replay_anchor_event_id])}</div>
      <details className="mt-3 text-xs"><summary>Available-in-catalog options, conditions & evidence · {tip.window_seconds.map(clock).join('–')}</summary>
        <p className="mt-2">Catalog availability at the recorded age is not ready-to-queue state. Existing support may be present; missing commands do not prove absence.</p>
        {tip.options.map(option => <div key={option.id} className="mt-3 rounded border border-[color:var(--border-subtle)] p-2"><b>{option.label}</b><p>{option.requires}</p><Sources refs={option.source_refs} />{option.structure_placement_event_ids.length > 0 && <details className="mt-2"><summary>Recorded structure placement only · not completion</summary><div className="mt-2 flex flex-wrap gap-2">{evidence(option.structure_placement_event_ids)}</div></details>}</div>)}
        <p className="mt-3 font-semibold">Conditions</p><ul className="list-disc pl-4">{tip.conditions.map(text => <li key={text}>{text}</li>)}</ul>
        <p className="mt-3 font-semibold">Alternatives / counterevidence</p><ul className="list-disc pl-4">{tip.alternatives.map(text => <li key={text}>{text}</li>)}</ul>
        <p className="mt-3">Reference facts: {tip.fact_ids.join(', ')}. Interpretation: {tip.evidence_quality.interpretation.replaceAll('_', ' ')}; vision: {tip.evidence_quality.vision}.</p>
        <div className="mt-2 flex flex-wrap gap-2">{evidence(tip.event_ids)}</div><p className="mt-2">Not claimed: {tip.not_claimed.join(', ')}.</p>
      </details>
    </article>)}
    {matchup.player && <details className="mt-4 rounded-lg border border-[color:var(--border-subtle)] p-3"><summary className="text-sm font-semibold">Optional match-rules declaration · {rulesContext?.rules === 'standard' ? 'standard reported by you' : 'unknown'}</summary>
      <label className="mt-3 flex items-start gap-2 text-sm"><input type="checkbox" checked={standard} onChange={event => setStandard(event.target.checked)} /><span>I report that this match used standard rules, with no data/RMS mods or special rules.</span></label>
      <p className="mt-2 text-xs text-[color:var(--muted)]">A per-match retrospective annotation in local SQLite—not a parser fact or independent verification. It permits only conditional questions when build/data/mode match, cannot override conflicting header fields, and does not change opening detection, your intended plan or practice goals.</p>
      <button className={`${button} mt-3`} disabled={busy} onClick={() => onSaveRules(standard ? 'standard' : 'unknown')}>Save rules declaration locally</button>
    </details>}
    <details className="mt-4 text-xs text-[color:var(--muted)]"><summary>Source versions, rule decisions & limitations</summary>
      {matchup.source && <p className="mt-2">Reference update {matchup.source.declared_update} · commit {matchup.source.commit} · {matchup.source.pack_id} v{matchup.source.pack_version}. Actual replay build: {analysis.replay_provenance?.build_version ?? 'unknown'}.</p>}
      {matchup.decisions.map(decision => <p key={decision.rule_id} className="mt-2">{decision.rule_id}: {decision.status}. {decision.reason} Candidate windows searched: {decision.candidate_windows_searched ?? 0}.</p>)}
      <ul className="mt-2 list-disc pl-4">{matchup.limitations.map(text => <li key={text}>{text}</li>)}</ul>
    </details>
  </section>;
}

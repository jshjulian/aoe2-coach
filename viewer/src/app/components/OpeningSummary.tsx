"use client";

import { useMemo } from 'react';
import type { AnalysisEvent, PythonAnalysis } from '@/lib/coachAnalysis';

export function OpeningSummary({ analysis, profileName, onOpenEvidence }: {
  analysis: PythonAnalysis;
  profileName: string;
  onOpenEvidence: (event: AnalysisEvent, label: string) => void;
}) {
  const byId = useMemo(() => new Map(analysis.events.map(event => [event.id, event])), [analysis]);
  const rows = (analysis.opening_observations ?? []).filter(row => !profileName || row.player === profileName);
  if (!rows.length) return null;
  const clock = (value: number) => `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}`;
  function links(ids: string[]) {
    return [...new Set(ids)].map(id => {
      const event = byId.get(id);
      return event && <button key={id} onClick={() => onOpenEvidence(event, 'Observed opening evidence')}
        className="rounded border border-[color:var(--border-subtle)] px-2 py-1 text-xs hover:bg-[color:var(--panel)]">
        {event.time} · {event.action} {event.unit ?? event.technology ?? event.building ?? ''}
      </button>;
    });
  }
  return <section className="panel-strong rounded-xl border border-[color:var(--border-subtle)] p-5">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="headline text-xl font-bold">Observed opening & transitions</h2><span className="text-xs text-[color:var(--muted)]">Command patterns v{analysis.opening_observation_version} · no plan confirmation needed</span></div>
    {rows.map(row => <article key={row.player_id} className="mt-3 rounded-lg bg-[color:var(--panel)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">{profileName ? '' : `${row.player} · `}{row.label}</h3><span className="text-xs text-[color:var(--muted)]">{row.confidence} evidence strength</span></div>
      {row.patterns.map(pattern => <p key={pattern.tag} className="mt-2 text-sm">{pattern.label}: {pattern.queue_command_count} recorded queue commands in the opening window. {pattern.reason}</p>)}
      {row.transitions.map(transition => <div key={transition.tag} className="mt-3"><p className="text-sm"><b>{transition.label}:</b> {transition.interval_seconds.toFixed(1)}s between recorded anchors—not completed Knights.</p><div className="mt-2 flex flex-wrap gap-2">{links(transition.event_ids)}</div>{transition.context && <details className="mt-2 text-xs text-[color:var(--muted)]"><summary>Transition-relative context · {transition.context.window_seconds.map(clock).join('–')}</summary><p className="mt-2">{transition.context.status === 'possible_from_commands' ? 'Possible adaptation cues—not confirmed defense.' : 'Context unknown; no identified cue does not establish safety.'} {transition.context.reason} Opponent commands may not have been visible in-game.</p><div className="mt-2 flex flex-wrap gap-2">{links([...transition.context.event_ids, ...transition.context.opponent_order_event_ids].slice(0, 12))}</div></details>}</div>)}
      <p className="mt-3 text-xs text-[color:var(--muted)]">Intended opening: unknown from commands; any declared plan remains a separate annotation. Adaptation: {row.adaptation.status === 'possible_from_commands' ? 'possible command cues; not confirmed defense' : 'unknown—not verified safety'}.</p>
      <details className="mt-3 text-xs"><summary>Opening evidence, searched window & limitations</summary>
        <p className="mt-2">{row.window_seconds.map(clock).join('–')} · {row.coverage.replaceAll('_', ' ')}. This is a bounded early-game search, not full-match strategy recognition or a skill grade.</p>
        <div className="mt-2 flex flex-wrap gap-2">{links(row.patterns.flatMap(pattern => pattern.event_ids))}</div>
        <p className="mt-2">{row.adaptation.reason}</p>
        <div className="mt-2 flex flex-wrap gap-2">{links([...row.adaptation.event_ids, ...row.adaptation.opponent_order_event_ids].slice(0, 12))}</div>
        <ul className="mt-2 list-disc pl-4">{row.limitations.map(text => <li key={text}>{text}</li>)}</ul>
      </details>
    </article>)}
    <details className="mt-3 text-xs text-[color:var(--muted)]"><summary>Replay version & knowledge readiness</summary><p className="mt-2">Actual replay build: {analysis.replay_provenance?.build_version ?? 'unknown'} · dataset: {analysis.replay_provenance?.dataset_id ?? 'unknown'}. {analysis.replay_provenance?.compatibility_note ?? analysis.replay_provenance?.reason} The separate matchup briefing reports source compatibility and any conditional review questions; build alone does not verify mod compatibility.</p></details>
  </section>;
}

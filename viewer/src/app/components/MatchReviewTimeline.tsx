"use client";

import { useState } from 'react';
import type { PythonAnalysis } from '@/lib/coachAnalysis';
import type { OpenEvidence } from '@/lib/coachingReview';
import type { SituationReview } from '@/lib/situationReview';

const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
const lanes = [
  {label: 'Age milestones', color: '#60a5fa'},
  {label: 'Military queue inputs', color: '#a78bfa'},
  {label: 'Possible pressure / forward', color: '#fbbf24'},
  {label: 'Defensive inputs', color: '#2dd4bf'},
];

export function MatchReviewTimeline({ analysis, review, onOpenEvidence }: { analysis: PythonAnalysis; review: SituationReview; onOpenEvidence: OpenEvidence }) {
  const [hover, setHover] = useState('Select a marker to open Replay at that moment.');
  const events = new Map(analysis.events.map(event => [event.id, event]));
  const lastX = [-100, -100, -100, -100];
  const stacks = [0, 0, 0, 0];
  type Marker = NonNullable<SituationReview['timeline']>[number];
  const grouped: Array<Marker & {members: Marker[]}> = [];
  for (const marker of review.timeline ?? []) {
    const group = [...grouped].reverse().find(row => row.kind === marker.kind && (row.player_id === marker.player_id || marker.kind === 'age' && row.player_id !== review.player?.id && marker.player_id !== review.player?.id) && marker.time_seconds-row.time_seconds <= 30);
    if (group) group.members.push(marker);
    else grouped.push({...marker, members: [marker]});
  }
  const markers = grouped.map(marker => {
    const lane = marker.kind === 'age' ? 0 : marker.kind === 'production' ? 1 : marker.kind === 'response' ? 3 : 2;
    const x = 12 + marker.time_seconds / Math.max(analysis.duration_seconds, 1) * 964;
    stacks[lane] = x-lastX[lane] < 17 ? stacks[lane]+1 : 0;
    lastX[lane] = x;
    const y = 22+lane*38 + [0, -9, 9][stacks[lane] % 3];
    const label = marker.members.length > 1 ? `${marker.label} · ${marker.members.length} evidence markers (${clock(marker.time_seconds)}–${clock(marker.members.at(-1)!.time_seconds)}); expand all markers for individual inputs` : marker.label;
    return {...marker, label, x, y, lane};
  });
  const ticks = Array.from({length: 6}, (_, i) => i*analysis.duration_seconds/5);
  function open(marker: typeof markers[number]) {
    const event = events.get(marker.event_id);
    if (event) onOpenEvidence(event, marker.label + ' — command coordinates, not actual unit positions');
  }
  return <section aria-label="Match review timeline" className="mt-5 border-t border-[color:var(--border-subtle)] pt-4">
    <div className="flex items-center justify-between gap-2"><h3 className="text-sm font-semibold">Match timeline</h3><p className="text-xs text-[color:var(--muted)]">AoE time · click to review</p></div>
    <div className="mt-2 overflow-x-auto"><div className="flex min-w-[600px] gap-2">
      <div className="w-36 shrink-0 pt-[7px]">{lanes.map(lane => <p key={lane.label} className="flex h-[38px] items-start gap-1.5 text-[10px] text-[color:var(--muted)]"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full" style={{background: lane.color}} />{lane.label}</p>)}</div>
      <svg viewBox="0 0 1000 177" preserveAspectRatio="none" className="h-[177px] min-w-0 flex-1" role="group" aria-label="Evidence markers">
        {lanes.map((lane, i) => <line key={lane.label} x1="12" x2="976" y1={22+i*38} y2={22+i*38} stroke="currentColor" opacity="0.12" />)}
        {ticks.map(t => <g key={t}><line x1={12+t/Math.max(analysis.duration_seconds,1)*964} x2={12+t/Math.max(analysis.duration_seconds,1)*964} y1="8" y2="151" stroke="currentColor" opacity="0.06" /><text x={12+t/Math.max(analysis.duration_seconds,1)*964} y="173" textAnchor={t === 0 ? 'start' : 'end'} fontSize="12" fill="currentColor" opacity="0.55">{clock(t)}</text></g>)}
        {markers.map(marker => <g key={marker.id} role="button" tabIndex={0} data-review-marker={marker.id}
          aria-label={`${clock(marker.time_seconds)} · ${marker.label}`} className="cursor-pointer outline-offset-2 focus:outline focus:outline-2"
          onMouseEnter={() => setHover(`${clock(marker.time_seconds)} · ${marker.label}`)} onFocus={() => setHover(`${clock(marker.time_seconds)} · ${marker.label}`)}
          onClick={() => open(marker)} onKeyDown={e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); open(marker);}}}>
          <title>{clock(marker.time_seconds)} · {marker.label}</title>
          <rect x={marker.x-6} y={marker.y-6} width="12" height="12" fill="transparent" />
          {marker.kind === 'forward' ? <path d={`M ${marker.x} ${marker.y-7} l 7 7 l -7 7 l -7 -7 Z`} fill={lanes[marker.lane].color} /> :
            <circle cx={marker.x} cy={marker.y} r={marker.player_id === review.player?.id ? 4.5 : 5.5} fill={marker.kind === 'age' && marker.player_id !== review.player?.id ? 'var(--panel)' : lanes[marker.lane].color} stroke={lanes[marker.lane].color} strokeWidth="2" />}
        </g>)}
      </svg>
    </div></div>
    <p className="mt-1 min-h-4 text-[10px] text-[color:var(--muted)]" aria-live="polite">{hover}</p>
  </section>;
}

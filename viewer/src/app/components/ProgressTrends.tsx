"use client";

import { useMemo, useState } from "react";

interface Trend {
  id: string;
  player: string;
  civilization: string;
  metric: string;
  label: string;
  direction_label: string;
  caveat: string;
  samples: number;
  earlier_count: number;
  recent_count: number;
  earlier_median_seconds: number;
  recent_median_seconds: number;
  change_seconds: number;
  direction: "earlier" | "later" | "flat";
  note: string;
}
export interface ProgressData {
  analyzed_games: number;
  total_games: number;
  minimum_samples: number;
  trends: Trend[];
  player_counts: Record<string, number>;
}

function clock(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function ProgressTrends({ data }: { data: ProgressData | null }) {
  const playerNames = useMemo(() => Object.keys(data?.player_counts ?? {}).sort((a, b) => (data?.player_counts[b] ?? 0) - (data?.player_counts[a] ?? 0)), [data]);
  const [chosen, setChosen] = useState("");
  const selectedPlayer = chosen && playerNames.includes(chosen) ? chosen : playerNames[0] ?? "";
  const rows = (data?.trends ?? []).filter((trend) => trend.player === selectedPlayer);
  return <section className="panel-strong rounded-xl border border-[color:var(--border-subtle)] p-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[color:var(--muted)]">Across your library</p><h2 className="headline mt-1 text-xl font-bold">Progress signals</h2></div>{playerNames.length > 1 && <label className="text-xs">Player <select className="ml-1 rounded border border-[color:var(--border-subtle)] bg-[color:var(--panel)] p-1" value={selectedPlayer} onChange={(event) => setChosen(event.target.value)}>{playerNames.map((name) => <option key={name}>{name}</option>)}</select></label>}</div>
    <p className="mt-1 text-xs text-[color:var(--muted)]">Observed recent patterns, not a skill rating. Comparisons are grouped by player and civilization; maps, opponents, and strategies can differ.</p>
    <p className="mt-1 text-[10px] text-[color:var(--muted)]">Indexed {data?.analyzed_games ?? 0} of {data?.total_games ?? 0} unique games. Signals appear as the local cache fills.</p>
    {rows.length ? <div className="mt-3 grid gap-2 sm:grid-cols-2">{rows.map((trend) => {
      const isArrival = trend.metric === "feudal_arrival" || trend.metric === "castle_arrival";
      const movement = trend.direction === "earlier" ? (isArrival ? "earlier" : "shorter") : (isArrival ? "later" : "longer");
      const wording = trend.direction === "flat" ? "roughly unchanged" : `${clock(Math.abs(trend.change_seconds))} ${movement}`;
      const tone = trend.direction === "flat" ? "text-[color:var(--muted)]" : trend.direction === "earlier" ? "text-emerald-600 dark:text-emerald-400" : "text-amber-700 dark:text-amber-300";
      return <article key={trend.id} className="rounded-lg bg-[color:var(--panel)] p-3"><div className="flex items-start justify-between gap-2"><div><h3 className="text-sm font-semibold">{trend.label}</h3><p className="text-[10px] text-[color:var(--muted)]">{trend.civilization} · {trend.samples} games</p></div><span className={`text-xs font-semibold ${tone}`}>{wording}</span></div><p className="mt-2 text-xs tabular-nums">Earlier median {clock(trend.earlier_median_seconds)} → recent median {clock(trend.recent_median_seconds)}</p><p className="mt-1 text-[10px] text-[color:var(--muted)]">{trend.caveat}. {trend.note}</p></article>;
    })}</div> : <p className="mt-3 rounded-lg bg-[color:var(--panel)] p-3 text-sm text-[color:var(--muted)]">No stable trend signals yet. At least four cached matches with the same player and civilization are needed for a preliminary comparison.</p>}
  </section>;
}

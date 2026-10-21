"use client";

import { memo, useMemo, useRef, useState } from "react";
import { canonicalTeam } from "@/lib/teamIdentity";
import { MapThumbnail } from './MapThumbnail';

export interface LibraryGame {
  game_id: string;
  file: string;
  size_bytes: number;
  modified: string;
  modified_timestamp: number;
  status: "queued" | "analyzing" | "ready" | "error";
  waiting_for_recording?: boolean;
  match_id: string | null;
  map: string | null;
  duration: string | null;
  duration_seconds?: number | null;
  rated?: boolean | null;
  game_type_id?: number | null;
  map_preview_available?: boolean;
  played_at?: string | null;
  played_at_source?: string | null;
  estimated_real_duration_seconds?: number | null;
  game_speed_multiplier?: number | null;
  players: Array<{ id: number; name: string; civilization?: string | null; team_id?: number | number[] | null; won?: boolean; elo_snapshot?: number | null; rating_track?: string | null; previous_elo_snapshot?: number | null; elo_change_since_previous_snapshot?: number | null; previous_snapshot_played_at?: string | null; rating_snapshot_source_played_at?: string | null }>;
  opening_milestones?: Array<{ player_id: number; player: string; civilization: string; milestones: Record<string, { time: string; time_seconds: number; event_id?: string; status?: string } | null> }>;
  error?: string | null;
}

export interface ReplayLibraryData {
  directories: string[];
  total: number;
  counts: Record<string, number>;
  games: LibraryGame[];
}

interface Props {
  library: ReplayLibraryData | null;
  selectedGameId: string | null;
  loadingGameId?: string | null;
  error?: string | null;
  profileName: string;
  profileOptions: string[];
  onProfileChange: (name: string) => void;
  onSelect: (game: LibraryGame) => void;
}

const statusLabel: Record<LibraryGame["status"], string> = {
  queued: "queued", analyzing: "indexing", ready: "cached", error: "error",
};

function displayStart(value?: string | null): string {
  if (!value) return "Start time unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Start time unavailable";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" }).format(date);
}

function shortClock(seconds?: number | null): string | null {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) return null;
  const total = Math.round(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export const ReplayLibrary = memo(function ReplayLibrary({ library, selectedGameId, loadingGameId, error, profileName, profileOptions, onProfileChange, onSelect }: Props) {
  const [search, setSearch] = useState("");
  const [browse,setBrowse]=useState(false);
  const browseButton=useRef<HTMLButtonElement>(null);
  const [showCachedOnly, setShowCachedOnly] = useState(false);
  const games = library?.games ?? [];
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return games.filter((game) => {
      if (showCachedOnly && game.status !== "ready") return false;
      if (!query) return true;
      const players = game.players.map((p) => `${p.name} ${p.civilization ?? ""}`).join(" ");
      return `${game.file} ${game.map ?? ""} ${players}`.toLowerCase().includes(query);
    });
  }, [games, search, showCachedOnly]);
  const ready = library?.counts.ready ?? 0;
  const total = library?.total ?? 0;

  return <aside data-browse={browse} className="replay-library panel-strong overflow-hidden rounded-xl border border-[color:var(--border-subtle)] xl:sticky xl:top-4">
    <div className="border-b border-[color:var(--border-subtle)] p-4">
      <div className="flex items-center justify-between gap-2"><div><p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[color:var(--muted)]">Local library</p><h2 className="headline mt-1 text-xl font-bold">Your games</h2></div><span className="library-count rounded-full border border-[color:var(--border-subtle)] px-2.5 py-1 text-xs tabular-nums">{total}</span></div>
      <p className="mt-2 text-xs text-[color:var(--muted)]">{library ? `${ready} of ${total} analyzed · background indexing` : "Looking for AoE2 DE recordings…"}</p>
      <label className="mt-3 flex items-center gap-2 text-xs text-[color:var(--muted)]">Your player <select className="min-w-0 flex-1 rounded border border-[color:var(--border-subtle)] bg-[color:var(--panel)] px-2 py-1.5 text-[color:var(--foreground)]" value={profileName} onChange={(event) => onProfileChange(event.target.value)}><option value="">Choose your player</option>{profileOptions.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
      <button ref={browseButton} type="button" className="library-mobile-toggle" aria-expanded={browse} aria-controls="replay-library-list" onClick={()=>setBrowse(!browse)}>{browse?'Close replay library':'Browse replays'} · {total} games</button>
      <div className="library-tools"><div className="mt-3 flex gap-2"><input aria-label="Search replay library" className="min-w-0 flex-1 rounded-lg border border-[color:var(--border-subtle)] bg-[color:var(--panel)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[color:var(--accent)]" placeholder="Search map, player, civ…" value={search} onChange={(event) => setSearch(event.target.value)} /><label className="flex shrink-0 items-center gap-1 text-[11px] text-[color:var(--muted)]"><input type="checkbox" checked={showCachedOnly} onChange={(event) => setShowCachedOnly(event.target.checked)} />Cached</label></div>
      {library?.directories.length ? <details className="mt-3 text-[11px] text-[color:var(--muted)]"><summary>{library.directories.length === 1 ? "Replay folder" : `${library.directories.length} replay folders`}</summary><ul className="mt-1 break-all">{library.directories.map((directory) => <li key={directory}>{directory}</li>)}</ul></details> : null}
      </div>{error && <p className="mt-2 rounded border border-red-500/30 px-2 py-1 text-xs text-red-600">{error}</p>}
    </div>
    <div id="replay-library-list" className="library-list max-h-[72vh] overflow-y-auto">
      {filtered.map((game) => {
        const selected = game.game_id === selectedGameId;
        const busy = game.game_id === loadingGameId;
        const matchup = game.players.map((player) => `${player.civilization ?? "?"} · ${player.name}`).join("  vs  ");
        const profileRecord = game.players.find((player) => player.name === profileName);
        const winners = game.players.filter((player) => player.won === true);
        const hasWinner = new Set(winners.map(canonicalTeam)).size === 1 && winners.length > 0;
        const result = profileRecord ? (hasWinner && typeof profileRecord.won === "boolean" ? (profileRecord.won ? "WIN" : "LOSS") : "RESULT ?") : null;
        return <button key={game.game_id} type="button" data-selected={selected} aria-current={selected?'true':undefined} onClick={() => {setBrowse(false);onSelect(game);if(window.innerWidth<1280)browseButton.current?.focus({preventScroll:true});}} className={`group block w-full border-b border-[color:var(--border-subtle)] px-4 py-3 text-left transition-colors ${selected ? "bg-[color:var(--panel)] ring-1 ring-inset ring-[color:var(--accent)]" : "hover:bg-[color:var(--panel)]"}`} title={game.file}>
          <div className="relative flex items-start justify-between gap-3"><MapThumbnail game={game}/><div className="min-w-0 flex-1"><div className="flex items-center gap-2 pr-28"><span className={`h-2 w-2 shrink-0 rounded-full ${game.status === "ready" ? "bg-emerald-500" : game.status === "error" ? "bg-red-500" : game.status === "analyzing" ? "animate-pulse bg-amber-400" : "bg-slate-400"}`} /><span className="truncate font-semibold">{game.map ?? (game.status === "analyzing" ? "Reading replay…" : game.file)}</span></div><p className="mt-7 truncate text-xs text-[color:var(--muted)]" title={matchup||undefined}>{matchup || game.file}</p><p className="mt-1 truncate text-[10px] text-[color:var(--muted)]" title="Local start time read from the timestamp embedded in the replay filename.">Started {displayStart(game.played_at)}</p><p className="mt-1 truncate font-mono text-[10px] text-[color:var(--muted)]" title="AoE time is the replay clock. Real time is estimated by dividing by recorded game speed; pauses and loading are not measured.">{game.duration ? `AoE ${game.duration}` : (game.status === "error" ? "analysis failed" : "time pending")} · {game.estimated_real_duration_seconds != null ? `~${shortClock(game.estimated_real_duration_seconds)} real` : "real time pending"} · {game.waiting_for_recording ? 'waiting for recording to settle' : statusLabel[game.status]}</p></div><div className="absolute right-0 top-0 flex max-w-[45%] flex-col items-end gap-1">{result && <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wide ${result === "WIN" ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" : result === "LOSS" ? "bg-rose-500/15 text-rose-600 dark:text-rose-400" : "bg-amber-500/15 text-amber-700 dark:text-amber-300"}`}>{result}</span>}{profileRecord?.elo_snapshot != null && <span className="text-[10px] font-mono font-semibold" title={`Snapshot and adjacent difference shifted one saved replay backward as requested${profileRecord.rating_snapshot_source_played_at ? `; sourced from replay ${displayStart(profileRecord.rating_snapshot_source_played_at)}` : ""}. This is not an official per-game Elo change.`}>{profileRecord.elo_snapshot} Elo after{profileRecord.elo_change_since_previous_snapshot != null ? ` · ${profileRecord.elo_change_since_previous_snapshot >= 0 ? "+" : ""}${profileRecord.elo_change_since_previous_snapshot} Δ` : ""}</span>}{profileRecord?.rating_track === "1v1" && profileRecord.elo_snapshot == null && <span className="text-[10px] text-[color:var(--muted)]" title="No later saved replay snapshot is available to shift back; updated rating for this latest game is unknown.">Elo pending</span>}<span className={`text-[10px] ${busy ? "animate-pulse text-[color:var(--accent)]" : "text-[color:var(--muted)]"}`}>{busy ? "opening…" : selected ? "selected" : ""}</span></div></div>
          {game.status === "error" && game.error && <p className="mt-1 truncate text-[10px] text-red-600" title={game.error}>{game.error}</p>}
        </button>;
      })}
      {filtered.length === 0 && <div className="p-5 text-center text-sm text-[color:var(--muted)]">{library?.games.length ? "No games match this filter." : "No recordings yet. Set your savegame folder in agewise.local.json or launch with --replays PATH, then restart. Empty configured folders are supported."}</div>}
    </div>
    <div className="border-t border-[color:var(--border-subtle)] px-4 py-2 text-[10px] text-[color:var(--muted)]">Replay data and analysis stay on this machine.</div>
  </aside>;
});

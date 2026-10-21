"use client";

import { memo } from 'react';
import type { AnalysisEvent, CoachFinding, PythonAnalysis, PressureIncident } from "@/lib/coachAnalysis";
import type { PlayerStats, PlayerSummary } from "@/lib/replayProcessor";
import type { LibraryGame } from "./ReplayLibrary";
import { canonicalTeam } from "@/lib/teamIdentity";
import { CoachingReview } from "./CoachingReview";
import { OpeningSummary } from "./OpeningSummary";
import { CommandCharts } from "./CommandCharts";

type Props = {
  analysis: PythonAnalysis | null;
  status: "idle" | "loading" | "ready" | "unavailable";
  error?: string | null;
  players: PlayerSummary[];
  timelineStats: PlayerStats[];
  profileName: string;
  gameId?: string | null;
  matchDate?: string | null;
  selectedGame?: LibraryGame | null;
  recentGames: LibraryGame[];
  formatClock: (seconds: number) => string;
  onOpenEvidence: (event: AnalysisEvent, label: string, position?: { x: number; y: number }) => void;
  onOpenObservedEvidence?: (seconds: number, view: 'replay' | 'economy') => void;
  onOpenPracticeMatch?: (matchId: string) => void;
};

function EvidenceButton({ event, label, onOpen, position }: { event?: AnalysisEvent; label: string; onOpen: Props["onOpenEvidence"]; position?: { x: number; y: number } }) {
  if (!event) return <span className="text-xs text-[color:var(--muted)]">{label} · event unavailable</span>;
  const location = position ?? event.position;
  const xy = location ? ` · (${location.x.toFixed(1)}, ${location.y.toFixed(1)})` : "";
  return <button className="rounded border border-[color:var(--border-subtle)] px-2 py-1 text-left text-xs hover:bg-[color:var(--panel)]" onClick={() => onOpen(event, label, position)}>
    {event.time} · {event.player ?? "player"} · {event.action}{event.unit ? ` ${event.unit}` : ""}{event.building ? ` ${event.building}` : ""}{event.technology ? ` ${event.technology}` : ""}{xy} · id {event.id}
  </button>;
}

function FindingCard({ finding, byId, onOpen }: { finding: CoachFinding; byId: Map<string, AnalysisEvent>; onOpen: Props["onOpenEvidence"] }) {
  const evidence = finding.event_ids.map((id) => byId.get(id)).filter((event): event is AnalysisEvent => Boolean(event));
  const limitations = Array.isArray(finding.limitations) ? finding.limitations.join(" ") : finding.limitations;
  return <article className="rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--panel)] p-4">
    <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold">{finding.title}</h3><p className="mt-1 text-sm">{finding.summary}</p></div><span className="rounded-full border px-2 py-1 text-xs">{finding.confidence} confidence</span></div>
    {finding.kind === "tc_queue_gap_proxy" && <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">Queue-command gaps are a review proxy, not measured TC idle time.</p>}
    {finding.coordinates?.map((coordinate, index) => <div key={index} className="mt-1"><p className="text-xs">{coordinate.from_time}–{coordinate.to_time} · gap {coordinate.gap_seconds?.toFixed(0)}s · map ({coordinate.position.x.toFixed(1)}, {coordinate.position.y.toFixed(1)})</p><EvidenceButton event={coordinate.from_event_id ? byId.get(coordinate.from_event_id) : undefined} position={coordinate.position} label={`Review TC queue gap ${coordinate.from_time}–${coordinate.to_time}`} onOpen={onOpen} /></div>)}
    <div className="mt-3 flex flex-wrap gap-2">{evidence.slice(0, 6).map((event) => <EvidenceButton key={event.id} event={event} label={finding.title} onOpen={onOpen} />)}</div>
    {evidence.length > 6 && <details className="mt-2 text-xs"><summary>More supporting commands ({evidence.length - 6})</summary><div className="mt-2 flex flex-wrap gap-2">{evidence.slice(6).map((event) => <EvidenceButton key={event.id} event={event} label={finding.title} onOpen={onOpen} />)}</div></details>}
    <details className="mt-2 text-xs text-[color:var(--muted)]"><summary>Evidence and caveats · {finding.event_ids.length} source IDs</summary><p className="mt-2">{limitations}</p><p>Source event IDs: {finding.event_ids.join(", ")}</p></details>
  </article>;
}

function IncidentCard({ incident, byId, onOpen }: { incident: PressureIncident; byId: Map<string, AnalysisEvent>; onOpen: Props["onOpenEvidence"] }) {
  const anchor = [...incident.key_orders].sort((a, b) => a.distance_to_target_base - b.distance_to_target_base)[0];
  const anchorEvent = anchor ? byId.get(anchor.event_id) : undefined;
  return <article className="rounded-xl border border-amber-300/60 bg-amber-50/70 p-4 dark:bg-amber-950/20">
    <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold">{incident.title} · {incident.start_time}–{incident.end_time}</h3><p className="mt-1 text-sm">{incident.summary}</p></div><span className="rounded-full border px-2 py-1 text-xs">{incident.confidence} confidence</span></div>
    <p className="mt-2 text-xs">Selected object IDs: {incident.group_object_ids.join(", ")} · command types: {incident.actions.join(", ")}</p>
    {anchor && <div className="mt-3"><EvidenceButton event={anchorEvent} label="Open incident anchor" onOpen={onOpen} /></div>}
    <p className="mt-2 text-xs">Possible temporally nearby responses: {incident.defender_responses.map((response) => `${response.time} ${response.response}`).join("; ") || "none identified"}. Temporal overlap does not establish a causal response.</p>
    <details className="mt-3 text-xs"><summary>Key targets and all {incident.event_ids.length} supporting source events</summary>
      <div className="mt-2 flex flex-wrap gap-2">{incident.key_orders.map((order) => <EvidenceButton key={order.event_id} event={byId.get(order.event_id)} label={`Generic ORDER target ${order.target_id ?? "unknown"}; target type unresolved`} onOpen={onOpen} />)}</div>
      <div className="mt-2 flex flex-wrap gap-2">{incident.event_ids.map((id) => byId.get(id)).filter((event): event is AnalysisEvent => Boolean(event)).map((event) => <EvidenceButton key={event.id} event={event} label="Supporting recorded command" onOpen={onOpen} />)}</div>
      <p className="mt-2 text-[color:var(--muted)]">{incident.limitations.join(" ")}</p>
    </details>
  </article>;
}

function RecentWinningReference({ games, profileName, selectedGameId, analysis, formatClock }: { games: LibraryGame[]; profileName: string; selectedGameId?: string | null; analysis: PythonAnalysis; formatClock: (seconds: number) => string }) {
  if (!profileName) return null;
  const comparable = games.filter((game) => {
    if (game.status !== "ready" || game.map !== "Arabia" || game.players.length !== 2) return false;
    const self = game.players.find((player) => player.name === profileName);
    return Boolean(self && self.won === true && self.civilization === "Franks" && new Set(game.players.map(canonicalTeam)).size === 2);
  }).sort((a, b) => (b.played_at ?? b.modified).localeCompare(a.played_at ?? a.modified));
  const sample = comparable.flatMap((game) => {
    const milestones = game.opening_milestones?.find((row) => row.player === profileName)?.milestones;
    const castle = milestones?.castle_arrival;
    const knight = milestones?.first_knight_queue;
    if (!castle || !knight || knight.time_seconds < castle.time_seconds) return [];
    return [{ game, interval: knight.time_seconds - castle.time_seconds, castle: castle.time_seconds, feudal: milestones?.feudal_arrival?.time_seconds }];
  }).slice(0, 5);
  if (sample.length < 2) return null;
  const intervals = sample.map((row) => row.interval).sort((a, b) => a - b);
  const formatObserved = (seconds: number) => formatClock(Math.round(seconds));
  const median = intervals[Math.floor(intervals.length / 2)];
  const feudal = sample.map((row) => row.feudal).filter((value): value is number => typeof value === "number");
  const current = analysis.opening_milestones?.find((row) => row.player === profileName)?.milestones;
  const currentCastle = current?.castle_arrival?.time_seconds;
  const currentKnight = current?.first_knight_queue?.time_seconds;
  const currentInterval = currentCastle != null && currentKnight != null && currentKnight >= currentCastle ? currentKnight - currentCastle : null;
  const includedCurrent = sample.some((row) => row.game.game_id === selectedGameId);
  return <section className="panel-strong rounded-xl border border-[color:var(--border-subtle)] p-4">
    <p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">Descriptive context · not a success rule</p>
    <h2 className="mt-1 font-semibold">Latest {sample.length} Arabia/Franks wins · unmatched timing context</h2>
    <p className="mt-2 text-sm">Castle arrival → first Knight queue command: <strong>{formatObserved(intervals[0])}–{formatObserved(intervals.at(-1)!)}</strong> (median {formatObserved(median)}; {intervals.filter((value) => value <= 30).length}/{sample.length} within 30 seconds).{feudal.length ? ` Feudal arrival ranged ${formatClock(Math.min(...feudal))}–${formatClock(Math.max(...feudal))}.` : ""}</p>
    {currentInterval != null && <p className="mt-1 text-sm">Selected match: {formatObserved(currentInterval)} after Castle arrival{includedCurrent ? " (included in this sample)" : `; ${currentInterval < intervals[0] || currentInterval > intervals.at(-1)! ? "outside" : "within"} this observed range`}.</p>}
    <p className="mt-2 text-xs text-[color:var(--muted)]">These are recorded age milestones and queue commands, not proof of completed production or why a game was won. This loose map/civ/win filter is not the matched practice cohort; patch, rules and opportunity comparability are not established here. The range is a personal reference, not a target; differences may reflect defense, strategy, opponents or missing events.</p>
  </section>;
}

export const CoachTab = memo(function CoachTab({ analysis, status, error, players, timelineStats, profileName, gameId, matchDate, selectedGame, recentGames, formatClock, onOpenEvidence, onOpenObservedEvidence, onOpenPracticeMatch }: Props) {
  if (!analysis) return <section className="panel-strong rounded-xl p-6"><h2 className="headline text-2xl font-bold">Match overview</h2><p className="mt-2 text-sm">{status === "loading" ? "Loading local analysis…" : status === "unavailable" ? "Local analysis could not be loaded." : "Load a replay to see its match result and coaching evidence."}</p>{status === "unavailable" && <><p className="mt-2 rounded border border-amber-500/40 bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/20 dark:text-amber-200">{error ?? "No further error details were returned."}</p><p className="mt-2 text-sm">Check that the replay is in a discovered folder and that the local Python API is running at http://127.0.0.1:8765.</p></>}<p className="mt-2 text-xs text-[color:var(--muted)]">No replay is uploaded. Analysis stays on this machine.</p></section>;
  const byId = new Map(analysis.events.map((event) => [event.id, event]));
  const winners = analysis.players.filter((player) => player.won === true);
  const winningTeams = new Set(winners.map(canonicalTeam));
  const outcomeConfirmed = winners.length > 0 && winningTeams.size === 1;
  const profile = analysis.players.find((player) => player.name === profileName);
  const result = !profile ? "not-in-match" : !outcomeConfirmed ? "unconfirmed" : profile.won ? "win" : "loss";
  const resultText = result === "win" ? "VICTORY" : result === "loss" ? "DEFEAT" : result === "not-in-match" ? (profileName ? "PROFILE NOT IN MATCH" : "SELECT YOUR PLAYER") : "RESULT UNCONFIRMED";
  const resultTone = result === "win" ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : result === "loss" ? "border-rose-400/40 bg-rose-500/10 text-rose-700 dark:text-rose-300" : "border-amber-400/40 bg-amber-500/10 text-amber-700 dark:text-amber-300";
  const milestoneByPlayer = new Map((analysis.opening_milestones ?? []).map((row) => [row.player, row.milestones]));
  const statsByPlayer = new Map(timelineStats.map((row) => [row.playerId, row]));
  const castleArrivals = (analysis.opening_milestones ?? []).map((player) => ({ player: player.player, civilization: player.civilization, arrival: player.milestones.castle_arrival })).filter((entry) => entry.arrival);
  const ordered = [...castleArrivals].sort((a, b) => (a.arrival?.time_seconds ?? Infinity) - (b.arrival?.time_seconds ?? Infinity));
  const leader = ordered[0], trailer = ordered[1];
  const leadSeconds = leader?.arrival && trailer?.arrival ? trailer.arrival.time_seconds - leader.arrival.time_seconds : undefined;
  const major = analysis.findings.filter((finding) => finding.kind !== "age_transition");
  const startTime = matchDate ?? analysis.played_at ?? null;
  const dateLabel = startTime ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" }).format(new Date(startTime)) : null;
  const realDuration = analysis.estimated_real_duration_seconds;
  const gameSpeed = analysis.game_speed_multiplier;
  const opposing = profile ? analysis.players.filter(p => canonicalTeam(p) !== canonicalTeam(profile)) : [];
  const matchup = profile ? `${profile.civilization} vs ${opposing.map(p => p.civilization).join(' / ') || 'unknown opponent'}` : 'Choose your player';
  const ageBadges = analysis.events.filter(e => e.player_id === profile?.id && e.action === 'AGE_REACHED' && e.status === 'observed_milestone');
  return <section data-match-id={analysis.match_id} className="flex flex-col gap-3">
    <section className="match-overview panel-strong overflow-hidden rounded-2xl border border-[color:var(--border-subtle)]">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-4">
        <div className="flex flex-wrap items-center gap-3"><span className={`rounded-lg border px-2 py-1 text-xs font-bold ${resultTone}`}>{resultText}</span><div><h1 className="text-lg font-bold">{matchup}</h1><p className="text-xs text-[color:var(--muted)]">{analysis.map} · {analysis.players.length === 2 ? '1v1' : `${analysis.players.length} players`}{analysis.rated ? ' · Rated' : ''} · {profile?.name ?? 'No player selected'}</p></div></div>
        <p className="font-mono text-lg font-semibold tabular-nums">{analysis.duration ?? formatClock(analysis.duration_seconds)} <span className="text-xs font-normal text-[color:var(--muted)]">AoE</span></p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 px-4">{ageBadges.map(event => <button key={event.id} className="rounded border border-[color:var(--border-subtle)] px-2 py-1 text-xs hover:bg-[color:var(--panel)]" onClick={() => onOpenEvidence(event, `${event.technology} milestone`)}>{event.technology?.replace(' Age', '')} <b className="ml-1 font-mono">{event.time}</b></button>)}</div>
      <details><summary className="px-5 py-3 text-sm">Match details · players, milestones and activity statistics</summary>
      <div className="grid gap-px bg-[color:var(--border-subtle)] sm:grid-cols-2">
        {analysis.players.map((player) => {
          const milestones = milestoneByPlayer.get(player.name);
          const matchingPlayers = players.filter((item) => item.name === player.name);
          const replayPlayer = matchingPlayers.length === 1 ? matchingPlayers[0] : undefined;
          const stats = replayPlayer ? statsByPlayer.get(replayPlayer.id) : undefined;
          const libraryPlayer = selectedGame?.players.find((item) => item.name === player.name);
          const rating = libraryPlayer?.elo_snapshot;
          const ratingLabel = libraryPlayer?.rating_track === "1v1" ? (rating != null ? String(rating) : "Not yet available") : null;
          const snapshotDelta = libraryPlayer?.elo_change_since_previous_snapshot;
          const isYou = player.name === profileName;
          const sideResult = outcomeConfirmed ? (player.won ? "Winner" : "Defeated") : "Outcome unavailable";
          return <article key={player.id} className="bg-[color:var(--panel)] p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">{isYou ? "You" : player.civilization}</p><h2 className="mt-1 text-lg font-bold">{player.name}</h2>{isYou && <p className="text-xs text-[color:var(--muted)]">{player.civilization}</p>}</div><span className={`rounded-full border px-2 py-1 text-xs font-semibold ${outcomeConfirmed && player.won ? "border-emerald-500/30 text-emerald-700 dark:text-emerald-300" : outcomeConfirmed ? "border-rose-500/30 text-rose-700 dark:text-rose-300" : "border-[color:var(--border-subtle)] text-[color:var(--muted)]"}`}>{sideResult}</span></div>
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">{[["Feudal Age", milestones?.feudal_arrival?.time], ["Castle Age", milestones?.castle_arrival?.time], ["Knight queue cmd", milestones?.first_knight_queue?.time], ["APM · peak", stats ? `${stats.apm} · ${stats.peakApm}` : null], ...(libraryPlayer?.rating_track === "1v1" ? [["Post-match Elo · shifted", ratingLabel], ["Shifted snapshot Δ", snapshotDelta == null ? "Not yet available" : `${snapshotDelta >= 0 ? "+" : ""}${snapshotDelta}`]] : [])].map(([label, value]) => <div key={label} className="rounded-lg border border-[color:var(--border-subtle)] px-3 py-2"><p className="text-[10px] text-[color:var(--muted)]">{label}</p><p className="mt-1 font-mono text-sm font-bold">{value ?? "—"}</p></div>)}</div>
          </article>;
        })}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 text-xs text-[color:var(--muted)]"><span>{analysis.source_file} · {dateLabel ? `Started ${dateLabel}` : 'Start time unavailable'} · {realDuration != null ? `~${formatClock(realDuration)} real at ${gameSpeed?.toFixed(2) ?? 'recorded'}×` : 'Real-time estimate unavailable'}</span><span>{outcomeConfirmed ? "Result from parser-reported winner/resignation data." : "Replay has no confirmed winner flag; result intentionally left unverified."} Elo snapshots and adjacent differences are shifted back one saved replay as requested; they are not verified official per-match changes. The latest match has no following snapshot, so its post-match Elo is unknown. Real time is estimated from the recorded game-speed multiplier; pauses/loading are not measured. APM is input activity, not a skill score.</span></div>
      </details>
    </section>
    <CoachingReview key={`${analysis.match_id}:${profileName}`} analysis={analysis} gameId={gameId} profileName={profileName} onOpenEvidence={onOpenEvidence} onOpenObservedEvidence={onOpenObservedEvidence} onOpenPracticeMatch={onOpenPracticeMatch} practiceMatchIds={recentGames.flatMap(g=>g.match_id?[g.match_id]:[])} />
    <CommandCharts key={analysis.match_id} analysis={analysis} onOpenEvidence={onOpenEvidence} />
    <details className="panel-strong rounded-xl p-4"><summary className="text-sm font-semibold">More match context & observations</summary><div className="mt-3 flex flex-col gap-3">
    <OpeningSummary analysis={analysis} profileName={profileName} onOpenEvidence={onOpenEvidence} />
    <details className="panel-strong rounded-xl p-4"><summary className="font-semibold">Legacy win-timing reference · not matched practice progress</summary><div className="mt-3"><RecentWinningReference games={recentGames} profileName={profileName} selectedGameId={gameId} analysis={analysis} formatClock={formatClock} /></div></details>
    <details className="panel-strong rounded-xl p-4"><summary className="font-semibold">All legacy observations and incidents · unranked, not coaching verdicts</summary><div className="mt-4 flex flex-col gap-4">
    {leadSeconds !== undefined && leader?.arrival && trailer?.arrival && <div className="rounded-xl border border-[color:var(--border-subtle)] bg-[color:var(--panel)] p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="font-bold">Age-up comparison</h2><p className="mt-1 text-sm">{leader.player} ({leader.civilization}) reached Castle Age at {leader.arrival.time}; {trailer.player} at {trailer.arrival.time} — {formatClock(leadSeconds)} earlier. This is an observed milestone, not a conclusion about why one player won.</p></div><span className="rounded-full border px-2 py-1 text-[10px] text-[color:var(--muted)]">timing only</span></div><div className="mt-2 flex flex-wrap gap-2">{[leader, trailer].map((entry) => <EvidenceButton key={entry.player} event={entry.arrival ? byId.get(entry.arrival.event_id) : undefined} label={`${entry.player} Castle Age arrival`} onOpen={onOpenEvidence} />)}</div></div>}
    <div><h2 className="headline text-xl font-bold">What happened · recorded evidence</h2><p className="mt-1 text-xs text-[color:var(--muted)]">Review the timeline and minimap links below. These are observations and hypotheses, not causal verdicts.</p></div>
    {analysis.pressure_incidents.map((incident) => <IncidentCard key={incident.id} incident={incident} byId={byId} onOpen={onOpenEvidence} />)}
    {major.map((finding) => <FindingCard key={finding.id} finding={finding} byId={byId} onOpen={onOpenEvidence} />)}
    {analysis.findings.filter((finding) => finding.kind === "age_transition").map((finding) => <FindingCard key={finding.id} finding={finding} byId={byId} onOpen={onOpenEvidence} />)}
    </div></details>
    <details className="panel-strong rounded-xl p-4 text-xs"><summary>Data details and limitations</summary><p className="mt-2">Content-addressed match ID: {analysis.match_id} · replay start dates are filename-derived local times, not verified header timestamps.</p><p>Replay event commands do not establish completion, affordability, resource balance, damage, deaths, or TC idle time. Generic ORDER/Interact intent and most selected unit types remain unresolved. TC queue gaps are not actual idle-time measurements. APM is a parser-derived action rate and should not be read as quality.</p><p>Viewer player list: {players.map((player) => player.name).join(", ")}</p><p>Analysis event count: {analysis.events.length}</p></details>
    </div></details>
  </section>;
});

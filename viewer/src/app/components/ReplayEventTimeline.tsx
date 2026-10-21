"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { getBuildingName, getUnitName, isEconomic } from "@/lib/entityMappings";
import { getTechName } from "@/lib/techMappings";
import type { PlayerStats, PlayerSummary, TimelineEvent } from "@/lib/replayProcessor";
import type { PythonAnalysis } from "@/lib/coachAnalysis";

type Filter = "military" | "economy" | "buildings" | "technologies";
interface Props {
  players: PlayerSummary[];
  events: TimelineEvent[];
  stats: PlayerStats[];
  selectedTime: number;
  onSeek: (time: number) => void;
  getPlayerColor: (playerId?: number) => string;
  formatClock: (seconds: number) => string;
  onAnalysisLoaded?: (analysis: PythonAnalysis) => void;
  analysis?: PythonAnalysis | null;
  analysisStatus?: "idle" | "loading" | "ready" | "unavailable";
}

function eventFilters(event: TimelineEvent): Filter[] {
  if (event.category === "build") {
    const name = event.buildingTypeId !== undefined ? getBuildingName(event.buildingTypeId).toLowerCase() : "";
    return ["buildings", ...(/farm|mill|camp|market|town center/.test(name) ? ["economy" as const] : [])];
  }
  if (event.category === "research") {
    const name = event.techId !== undefined ? getTechName(event.techId).toLowerCase() : "";
    const tags: Filter[] = ["technologies"];
    if (/loom|axe|horse collar|wheelbarrow|bow saw|mining|town watch|town patrol/.test(name)) tags.push("economy");
    if (/fletching|bodkin|bracer|forging|iron casting|blast furnace|armor|armour|bloodlines|husbandry|crossbow|pikeman|man-at-arms|swordsman/.test(name)) tags.push("military");
    return tags;
  }
  if (event.category === "train") {
    const name = event.unitTypeId !== undefined ? getUnitName(event.unitTypeId) : "";
    return [isEconomic(name) ? "economy" : "military"];
  }
  if (["move", "interaction", "autoscout"].includes(event.category) || event.raw?.order === "Unqueue") return ["military"];
  if (["gatherpoint", "market"].includes(event.category)) return ["economy"];
  return [];
}

function eventName(event: TimelineEvent): string {
  if (event.category === "build" && event.buildingTypeId !== undefined) return getBuildingName(event.buildingTypeId);
  if (event.category === "train" && event.unitTypeId !== undefined) return getUnitName(event.unitTypeId);
  if (event.category === "research" && event.techId !== undefined) return getTechName(event.techId);
  if (typeof event.raw?.label === "string") return event.raw.label;
  return event.type;
}

function eventSemantics(event: TimelineEvent): string {
  if (event.category === "analysis") return "Inferred analysis marker; not a replay command.";
  if (event.raw?.isInitial) return "Verified initial-state snapshot.";
  if (event.category === "interaction") return "Generic Interact command; intent and target semantics are unresolved.";
  if (event.category === "move") return "Recorded move/order command; coordinates are requested destinations, not verified unit positions.";
  if (event.category === "train") return "Queue command; unit completion is not established.";
  if (event.category === "build") return "Placement command; building completion is not established.";
  if (event.category === "research") return "Research command; technology completion is not established.";
  return "Recorded command; outcome is not established.";
}

function exportable(event: TimelineEvent, players: PlayerSummary[]) {
  const player = players.find((p) => p.id === event.playerId);
  return {
    id: event.id,
    match_time_seconds: event.time,
    player: player ? { id: player.id, slot_id: player.slotId, name: player.name, civilization_id: player.civId } : { id: event.playerId },
    category: event.category,
    filters: eventFilters(event),
    action: event.type,
    unit_type_id: event.unitTypeId,
    building_type_id: event.buildingTypeId,
    technology_id: event.techId,
    status: event.raw?.isInitial ? "verified_initial_snapshot" : event.category === "analysis" ? "inferred_analysis_marker" : "recorded_command_completion_unverified",
    raw: event.raw,
  };
}

export function ReplayEventTimeline({ players, events, stats, selectedTime, onSeek, getPlayerColor, formatClock, onAnalysisLoaded, analysis, analysisStatus }: Props) {
  const [playerFilter, setPlayerFilter] = useState("all");
  const [unitFilter, setUnitFilter] = useState("all");
  const [ageFilter, setAgeFilter] = useState("all");
  const [significantOnly, setSignificantOnly] = useState(false);
  const [filters, setFilters] = useState<Record<Filter, boolean>>({ military: true, economy: true, buildings: true, technologies: true });
  const [analysisError, setAnalysisError] = useState("");
  const operationalEvents = useMemo(() => events.filter((e) => !e.raw?.isInitial && e.category !== "analysis"), [events]);
  const unitOptions = useMemo(() => [...new Set(operationalEvents.filter((e) => e.category === "train" && e.unitTypeId !== undefined).map((e) => getUnitName(e.unitTypeId!)))].sort(), [operationalEvents]);

  const filtered = useMemo(() => operationalEvents.filter((event) => {
    if (playerFilter !== "all" && event.playerId !== Number(playerFilter)) return false;
    if (!eventFilters(event).some((category) => filters[category])) return false;
    if (unitFilter !== "all" && (event.category !== "train" || event.unitTypeId === undefined || getUnitName(event.unitTypeId) !== unitFilter)) return false;
    if (significantOnly && !/castle|town center|market|stable|archery range|siege workshop|monastery|watch tower|keep|feudal age|castle age|imperial age|knight|mangonel|trebuchet|crossbow|unqueue|wall/i.test(`${event.category} ${eventName(event)} ${event.type}`)) return false;
    if (ageFilter !== "all") {
      const timing = stats.find((s) => s.playerId === event.playerId)?.ageTimings ?? {};
      const feudal = timing.Feudal ?? 0;
      const castle = timing.Castle ?? Number.POSITIVE_INFINITY;
      const imperial = timing.Imperial ?? Number.POSITIVE_INFINITY;
      const age = event.time < feudal ? "dark" : event.time < castle ? "feudal" : event.time < imperial ? "castle" : "imperial";
      if (age !== ageFilter) return false;
    }
    return true;
  }), [operationalEvents, playerFilter, filters, unitFilter, ageFilter, significantOnly, stats]);

  // Navigation only: nearby native timestamps do NOT establish a Python/native ID match.
  const scrollRef = useRef<HTMLDivElement>(null);
  const nearSharedTime = useMemo(() => filtered.reduce<TimelineEvent | null>((best,event) =>
    !best || Math.abs(event.time-selectedTime)<Math.abs(best.time-selectedTime) ? event : best, null), [filtered,selectedTime]);
  function showSharedTime() {
    const container=scrollRef.current,row=container?.querySelector<HTMLElement>('[data-near-shared-time="true"]');
    if(container&&row)container.scrollTop=Math.max(0,container.scrollTop+row.getBoundingClientRect().top-container.getBoundingClientRect().top-container.clientHeight/3);
  }
  useEffect(() => { if(selectedTime>0)showSharedTime(); }, [nearSharedTime?.id,filtered,selectedTime]);

  const loadPythonAnalysis = async (file?: File) => {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      if (parsed.schema_version !== 5 || typeof parsed.match_id !== "string" || !Array.isArray(parsed.events) || !Array.isArray(parsed.pressure_incidents)) throw new Error("Expected current Python analysis JSON with a stable match ID.");
      const importedNames = (parsed.players ?? []).map((p: { name: string }) => String(p.name)).sort();
      const loadedNames = players.map((p) => p.name).sort();
      if (importedNames.length !== loadedNames.length || importedNames.some((name: string, i: number) => name !== loadedNames[i])) throw new Error("Player names do not match the replay currently loaded in the viewer.");
      setAnalysisError("");
      onAnalysisLoaded?.(parsed as PythonAnalysis);
    } catch (error) {
      setAnalysisError(error instanceof Error ? error.message : String(error));
    }
  };

  const downloadJson = () => {
    const payload = { schema_version: 2, source: "local viewer replay operations", note: "Recorded commands and inferred analysis markers are distinguished in status; no replay file is uploaded.", events: events.map((event) => exportable(event, players)) };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "aoe2-viewer-events-debug.json"; anchor.click(); URL.revokeObjectURL(url);
  };

  const toggle = (filter: Filter) => setFilters((prev) => ({ ...prev, [filter]: !prev[filter] }));
  const options: [Filter, string][] = [["military", "Military/orders"], ["economy", "Economy"], ["buildings", "Buildings"], ["technologies", "Technologies"]];
  const seek = (time: number) => { onSeek(time); window.scrollTo({ top: 0, behavior: "smooth" }); };

  return <div className="panel-strong flex flex-col gap-4 rounded-xl p-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 className="headline text-xl font-semibold">Events</h3><p className="text-xs text-[color:var(--muted)]">Recorded command stream · click a row to set shared replay time · selected {formatClock(selectedTime)}</p>
        <p className="text-xs">Python analysis: {analysisStatus === "ready" ? `connected · ${analysis?.pressure_incidents.length ?? 0} aggregated incidents` : analysisStatus === "loading" ? "loading from the local analyzer…" : analysisStatus === "unavailable" ? "unavailable (start ./run.sh)" : "idle"}</p>
      </div>
      <details className="rounded border border-[color:var(--border-subtle)] px-3 py-2 text-sm"><summary>Developer tools</summary><div className="mt-2 flex flex-wrap gap-2"><button className="rounded border px-3 py-2" onClick={downloadJson}>Export viewer operations JSON</button><label className="cursor-pointer rounded border px-3 py-2">Manual analysis JSON fallback<input type="file" accept="application/json,.json" className="hidden" onChange={(event) => loadPythonAnalysis(event.target.files?.[0])} /></label></div>{analysisError && <p className="mt-2 text-red-600">{analysisError}</p>}</details>
    </div>
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <label>Player <select className="ml-1 rounded border border-[color:var(--border-subtle)] bg-[color:var(--panel)] p-1" value={playerFilter} onChange={(e) => setPlayerFilter(e.target.value)}><option value="all">Both players</option>{players.map((player) => <option key={player.id} value={player.id}>{player.name}</option>)}</select></label>
      <label>Unit <select className="ml-1 rounded border border-[color:var(--border-subtle)] bg-[color:var(--panel)] p-1" value={unitFilter} onChange={(e) => setUnitFilter(e.target.value)}><option value="all">All units</option>{unitOptions.map((unit) => <option key={unit} value={unit}>{unit}</option>)}</select></label>
      <label>Age <select className="ml-1 rounded border border-[color:var(--border-subtle)] bg-[color:var(--panel)] p-1" value={ageFilter} onChange={(e) => setAgeFilter(e.target.value)}><option value="all">All ages</option><option value="dark">Dark Age</option><option value="feudal">Feudal Age</option><option value="castle">Castle Age</option><option value="imperial">Imperial Age</option></select></label>
      <label className="inline-flex items-center gap-1"><input type="checkbox" checked={significantOnly} onChange={(e) => setSignificantOnly(e.target.checked)} />Significant only</label>
      {options.map(([key, label]) => <label key={key} className="inline-flex items-center gap-1"><input type="checkbox" checked={filters[key]} onChange={() => toggle(key)} />{label}</label>)}
      <span className="text-xs text-[color:var(--muted)]">{filtered.length} events</span>
    </div>
    <div className="flex flex-wrap items-center gap-3 text-xs"><button className="rounded border border-[color:var(--border-subtle)] px-3 py-2" disabled={!nearSharedTime} onClick={showSharedTime}>Jump to shared time · {formatClock(selectedTime)}</button><p data-events-clock-limitation>Navigation by reported time only. Nearby native rows are not verified matches for Python evidence IDs.</p></div>
    <div ref={scrollRef} data-events-scroll className="max-h-[70vh] overflow-auto rounded border border-[color:var(--border-subtle)]">
      <table className="w-full text-left text-sm"><thead className="sticky top-0 z-10 bg-[color:var(--panel-dark)]"><tr><th className="p-2">Time</th><th className="p-2">Player</th><th className="p-2">Category</th><th className="p-2">Command</th><th className="p-2">Location / IDs</th><th className="p-2">Source ID</th><th className="p-2">Semantics</th></tr></thead>
        <tbody>{filtered.map((event) => {
          const player = players.find((p) => p.id === event.playerId);
          const ids = event.unitIds ?? (Array.isArray(event.raw?.unitIds) ? event.raw.unitIds as number[] : []);
          const target = event.raw?.targetId ?? event.raw?.target_id;
          const location = event.x !== undefined && event.y !== undefined ? `(${event.x.toFixed(1)}, ${event.y.toFixed(1)})` : "—";
          const idSummary = `${ids.length ? `units ${ids.slice(0, 5).join(",")}${ids.length > 5 ? "…" : ""}` : ""}${target !== undefined ? ` target ${String(target)}` : ""}`;
          const amount = typeof event.raw?.amount === "number" && event.raw.amount > 1 ? ` ×${event.raw.amount}` : "";
          return <tr key={event.id} data-near-shared-time={event.id===nearSharedTime?.id?'true':undefined} aria-current={event.id===nearSharedTime?.id?'time':undefined} className={`cursor-pointer border-t border-[color:var(--border-subtle)] hover:bg-[color:var(--panel)] ${event.id===nearSharedTime?.id?'bg-teal-500/10':''}`} onClick={() => seek(event.time)} title={`Seek to ${formatClock(event.time)}`}>
            <td className="whitespace-nowrap p-2 tabular-nums">{formatClock(event.time)}</td><td className="whitespace-nowrap p-2" style={{ color: getPlayerColor(event.playerId) }}>{player?.name ?? `Player ${event.playerId ?? "?"}`}</td>
            <td className="whitespace-nowrap p-2">{event.category === "interaction" ? "generic interaction" : eventFilters(event)[0] ?? event.category}</td><td className="p-2">{eventName(event)}{amount}</td><td className="p-2 text-xs">{location} {idSummary}</td><td className="whitespace-nowrap p-2 font-mono text-xs">{event.id}</td><td className="min-w-56 p-2 text-xs">{eventSemantics(event)}</td>
          </tr>;
        })}{filtered.length === 0 && <tr><td className="p-4 text-center text-[color:var(--muted)]" colSpan={7}>No events match these filters.</td></tr>}</tbody></table>
    </div>
  </div>;
}

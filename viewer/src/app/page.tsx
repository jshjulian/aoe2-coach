"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Header } from "./components/Header";
import { Minimap } from "./components/Minimap";
import { GameTab } from "./components/GameTab";
import { CoachTab } from "./components/CoachTab";
import { LibraryStats } from './components/LibraryStats';
import { StatsTab } from "./components/StatsTab";
import { ObservationsTab } from "./components/ObservationsTab";
import { TimelineTab } from "./components/TimelineTab";
import { Toggle } from "./components/Toggle";
import { parse_rec } from "../aoe2rec-js/aoe2rec_js";
import {
  buildTimeline,
  determineDuration,
  extractPlayerStats,
  extractMatchInfo,
  normalizeReplay,
  summarizePlayers,
  type ChatEvent,
  type MapResourceType,
  type MatchInfo,
  type TimelineEvent,
  type PlayerSummary,
  type PlayerStats,
} from "@/lib/replayProcessor";
import { ReplayLibrary, type LibraryGame, type ReplayLibraryData } from "./components/ReplayLibrary";
import { ProgressTrends, type ProgressData } from "./components/ProgressTrends";
import type { AnalysisEvent, PythonAnalysis } from "@/lib/coachAnalysis";
import { ensureUnzipped } from "@/lib/zipUtils";

const PLAYER_COLORS_LEGACY = [
  "#0000FF",
  "#FF0000",
  "#00FF00",
  "#FFFF00",
  "#00FFFF",
  "#FF00FF",
  "#434343",
  "#FF8201",
];

const PLAYER_COLORS = [
  "#2a48df", // 1
  "#dc2626", // 2
  "#00ff00", // 3
  "#ffff00", // 4
  "#00ffff", // 5
  "#b030b0", // 6
  "#434343", // 7
  "#ff8201", // 8
];

const PLAYER_OUTLINES = [
  "#FFFFFF", // 1
  "#FFFFFF", // 2
  "#000000", // 3
  "#000000", // 4
  "#000000", // 5
  "#FFFFFF", // 6
  "#FFFFFF", // 7
  "#000000", // 8
];

const KEYBOARD_STEP_SECONDS = 1;
const KEYBOARD_STEP_SHIFT_SECONDS = 60;
// Playback speed = 1000 / PLAYBACK_INTERVAL_MS * PLAYBACK_STEP_SECONDS
// 1000 / 66 * 4 = 60x speed
const PLAYBACK_STEP_SECONDS = 4;
const PLAYBACK_INTERVAL_MS = 66;

const formatClock = (seconds: number) => {
  const total = Math.max(seconds, 0);
  const mins = Math.floor(total / 60);
  const secs = Math.floor(total % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
};

const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);

const waitForPaint = () =>
  new Promise<void>(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });

interface LoadedReplayData {
  replay: any;
  matchInfo: MatchInfo | null;
  events: TimelineEvent[];
  chatEvents: ChatEvent[];
  mapResources: Record<string, MapResourceType>;
  mapCliffs: Record<string, boolean>;
  duration: number;
  players: PlayerSummary[];
  timelineStats: PlayerStats[];
}

export default function Home() {
  const [theme, setTheme] = useState<"dark" | "light">("light");

  useEffect(() => {
    if (typeof document !== "undefined") {
      const isLight =
        document.documentElement.classList.contains("light") ||
        (!document.documentElement.classList.contains("dark") &&
          window.matchMedia("(prefers-color-scheme: light)").matches);
      if (isLight) {
        setTheme("light");
        document.documentElement.classList.add("light");
        document.documentElement.classList.remove("dark");
      } else {
        setTheme("dark");
        document.documentElement.classList.add("dark");
        document.documentElement.classList.remove("light");
      }
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      if (next === "light") {
        document.documentElement.classList.add("light");
        document.documentElement.classList.remove("dark");
      } else {
        document.documentElement.classList.remove("light");
        document.documentElement.classList.add("dark");
      }
      return next;
    });
  }, []);

  const [isPlaying, setIsPlaying] = useState(false);
  const [replayData, setReplayData] = useState<LoadedReplayData | null>(null);
  const [externalAnalysis, setExternalAnalysis] = useState<PythonAnalysis | null>(null);
  const [focusedMarker, setFocusedMarker] = useState<TimelineEvent | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<"idle" | "loading" | "ready" | "unavailable">("idle");
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [library, setLibrary] = useState<ReplayLibraryData | null>(null);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [loadingGameId, setLoadingGameId] = useState<string | null>(null);
  const [progressData, setProgressData] = useState<ProgressData | null>(null);
  const [profileOverride, setProfileOverride] = useState("");
  const autoLoadStarted = useRef(false);
  const selectionGeneration = useRef(0);
  const replayCache = useRef(new Map<string, LoadedReplayData>());
  const analysisCache = useRef(new Map<string, PythonAnalysis>());
  const viewerRequest = useRef('');
  const replay = replayData?.replay ?? null;
  const matchInfo = replayData?.matchInfo ?? null;
  const selectedLibraryGame = useMemo(() => library?.games.find((game) => game.game_id === selectedGameId) ?? null, [library?.games, selectedGameId]);
  const events = useMemo(() => {
    const native = replayData?.events ?? [];
    if (!externalAnalysis || !replayData) return focusedMarker ? [...native, focusedMarker] : native;
    const playerByName = new Map(replayData.players.map((p) => [p.name, p.id]));
    const markers: TimelineEvent[] = [];
    for (const incident of externalAnalysis.pressure_incidents ?? []) {
      const anchor = [...incident.key_orders].sort((a, b) => a.distance_to_target_base - b.distance_to_target_base)[0];
      const source = anchor ? externalAnalysis.events.find((event) => event.id === anchor.event_id) : undefined;
      if (!source?.position) continue;
      markers.push({ id: `analysis:${incident.id}`, time: source.time_seconds, playerId: playerByName.get(incident.enemy_player), type: "Pressure incident marker", category: "analysis", x: source.position.x, y: source.position.y,
        raw: { label: "One aggregated incident marker anchored to a generic command destination", analysisMarker: true, markerType: "pressure_incident", incidentId: incident.id, intervalStartSeconds: incident.start_time_seconds, intervalEndSeconds: incident.end_time_seconds, sourceEventIds: incident.event_ids, objectIds: incident.group_object_ids, targetId: anchor.target_id } });
    }
    return [...native, ...markers, ...(focusedMarker ? [focusedMarker] : [])];
  }, [replayData?.events, replayData?.players, externalAnalysis, focusedMarker]);
  const chatEvents = useMemo(() => replayData?.chatEvents ?? [], [replayData?.chatEvents]);
  const mapResources = useMemo(() => replayData?.mapResources ?? {}, [replayData?.mapResources]);
  const mapCliffs = useMemo(() => replayData?.mapCliffs ?? {}, [replayData?.mapCliffs]);
  const duration = replayData?.duration ?? 0;
  const players = useMemo(() => (replayData?.players ?? []).map((player) => {
    const shifted = selectedLibraryGame?.players.find((entry) => entry.name === player.name);
    return { ...player,
      elo: shifted?.rating_track === "1v1" && shifted.elo_snapshot != null ? shifted.elo_snapshot : undefined,
      rank: undefined, teamElo: undefined, teamRank: undefined,
    };
  }), [replayData?.players, selectedLibraryGame]);
  const timelineStats = useMemo(() => replayData?.timelineStats ?? [], [replayData?.timelineStats]);
  useEffect(() => { const saved = localStorage.getItem("aoe2-replay-lab-player"); if (saved) setProfileOverride(saved); }, []);
  const profileOptions = useMemo(() => {
    const names = new Set<string>([...players.map((player) => player.name), ...(library?.games.flatMap((game) => game.players.map((player) => player.name)) ?? []), ...Object.keys(progressData?.player_counts ?? []), profileOverride].filter(Boolean));
    const counts = progressData?.player_counts ?? {};
    return [...names].sort((a, b) => (counts[b] ?? 0) - (counts[a] ?? 0) || a.localeCompare(b));
  }, [players, library?.games, progressData?.player_counts, profileOverride]);
  // Identity is explicit. The first native player may be the opponent or teammate.
  const profileName = profileOverride;
  const handleProfileChange = useCallback((name: string) => { setProfileOverride(name); if (name) localStorage.setItem("aoe2-replay-lab-player", name); else localStorage.removeItem("aoe2-replay-lab-player"); }, []);
  useEffect(() => {
    const filename = selectedLibraryGame?.file ?? replayData?.matchInfo?.filename;
    if (!filename) { setExternalAnalysis(null); setAnalysisStatus("idle"); setAnalysisError(null); return; }
    const controller = new AbortController();
    const cacheKey = selectedGameId ? `${selectedGameId}:${selectedLibraryGame?.size_bytes}:${selectedLibraryGame?.modified_timestamp}` : `import:${filename}`;
    const cached = selectedGameId ? analysisCache.current.get(cacheKey) : null;
    if (cached) { setExternalAnalysis(cached); setAnalysisStatus("ready"); setAnalysisError(null); return; }
    setExternalAnalysis(null); setFocusedMarker(null); setAnalysisStatus("loading"); setAnalysisError(null);
    const api = process.env.NEXT_PUBLIC_COACH_API_URL || "http://127.0.0.1:8765";
    const analysisUrl = selectedGameId
      ? `${api}/api/analysis?game_id=${encodeURIComponent(selectedGameId)}`
      : `${api}/api/analysis?file=${encodeURIComponent(filename)}`;
    fetch(analysisUrl, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          let detail = "";
          try { const body = await response.json(); detail = typeof body.error === "string" ? `${body.error}${body.file ? ` (file: ${body.file})` : ""}` : ""; } catch {}
          throw new Error(detail || `Local analyzer returned HTTP ${response.status}`);
        }
        return response.json();
      })
      .then((report) => {
        if (controller.signal.aborted) return;
        const localNames = new Set((selectedGameId ? [] : replayData?.players ?? []).map((p) => p.name));
        const importedNames = (report.players ?? []).map((p: any) => String(p.name));
        if (report.schema_version !== 5 || !report.match_id) throw new Error("The local analyzer returned an unsupported analysis schema. Restart it with ./run-viewer.sh.");
        if (!selectedGameId && (importedNames.length !== localNames.size || importedNames.some((name: string) => !localNames.has(name)))) throw new Error(`The replay players do not match the analysis for “${filename}”.`);
        if (selectedGameId) {
          analysisCache.current.set(cacheKey, report);
          if (analysisCache.current.size > 6) analysisCache.current.delete(analysisCache.current.keys().next().value!);
        }
        setExternalAnalysis(report as PythonAnalysis); setAnalysisStatus("ready"); setAnalysisError(null);
      })
      .catch((error) => { if (!controller.signal.aborted) { setExternalAnalysis(null); setAnalysisStatus("unavailable"); setAnalysisError(error instanceof Error ? error.message : String(error)); } });
    return () => controller.abort();
  }, [selectedGameId, selectedLibraryGame?.file, selectedLibraryGame?.size_bytes, selectedLibraryGame?.modified_timestamp, selectedGameId ? null : replayData?.matchInfo?.filename]);
  const [selectedTime, setSelectedTime] = useState(0);
  const selectedTimeRef = useRef(selectedTime);
  useEffect(() => {
    selectedTimeRef.current = selectedTime;
  }, [selectedTime]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingStep, setLoadingStep] = useState(0);
  const [activeTab, setActiveTab] = useState<"coach" | "replay" | "events" | "economy" | "library">("coach");
  const [replayUrl, setReplayUrl] = useState("");
  const [showUrlInput, setShowUrlInput] = useState(false);
  const handleCachedCanvasesReady = useCallback(async () => {
    setLoadingStep(3);
    await waitForPaint();
    setLoading(false);
  }, []);

  const handleTabChange = (tab: "coach" | "replay" | "events" | "economy" | "library") => {
    setActiveTab(tab);
  };

  const handleOpenObservedEvidence = useCallback((seconds: number, view: 'replay' | 'economy') => {
    setIsPlaying(false);
    setSelectedTime(clamp(seconds, 0, externalAnalysis?.duration_seconds ?? duration));
    setFocusedMarker(null);
    setActiveTab(view);
    window.scrollTo({top:0,behavior:'smooth'});
  }, [externalAnalysis?.duration_seconds, duration]);

  const handleOpenEvidence = useCallback((event: AnalysisEvent, label: string, position?: { x: number; y: number }) => {
    setIsPlaying(false);
    setSelectedTime(clamp(event.time_seconds, 0, externalAnalysis?.duration_seconds ?? duration));
    setActiveTab("replay");
    const markerPosition = position ?? event.position;
    const nativePlayer = players.find((player) => player.name === event.player);
    if (markerPosition) setFocusedMarker({ id: `analysis:evidence:${event.id}:${label}`, time: event.time_seconds, playerId: nativePlayer?.id, type: `Evidence: ${label}`, category: "analysis", x: markerPosition.x, y: markerPosition.y,
      raw: { label: "Selected replay evidence coordinate; not necessarily a unit's actual position", analysisMarker: true, markerType: "evidence", sourceEventIds: [event.id], action: event.action, objectIds: event.object_ids, targetId: event.target_id } });
    else setFocusedMarker(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [externalAnalysis, duration, players]);

  const resetGameState = useCallback(() => {
    setIsPlaying(false);
    setSelectedTime(0);
    setActiveTab("coach");
    if (typeof document !== "undefined" && document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  }, []);

  const unloadReplay = useCallback(() => {
    setExternalAnalysis(null);
    setFocusedMarker(null);
    setAnalysisStatus("idle");
    setReplayData(null);
    resetGameState();
  }, [resetGameState]);

  const lastKeyTimeRef = useRef(0);

  const playerIdToColorId = useMemo(() => {
    const map = new Map<number, number>();
    players.forEach((p) => {
      if (p.id !== undefined && p.colorId !== undefined) {
        map.set(p.id, p.colorId);
      }
    });
    return map;
  }, [players]);

  const getPlayerColor = (playerId?: number) => {
    if (playerId === undefined) return "#000000";
    if (playerId === 0) return "#dddddd";
    const colorId = playerIdToColorId.get(playerId);
    if (colorId === undefined || colorId < 0) return "#000000";
    return PLAYER_COLORS[(colorId) % PLAYER_COLORS.length];
  };

  const getPlayerOutline = (playerId?: number) => {
    if (playerId === undefined) return "#ffffff";
    if (playerId === 0) return "#000000";
    const colorId = playerIdToColorId.get(playerId);
    if (colorId === undefined || colorId < 0) return "#ffffff";
    return PLAYER_OUTLINES[(colorId) % PLAYER_OUTLINES.length];
  };


  // Manage the playback timer: increments selectedTime when playing
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setSelectedTime((prev) => Math.min(prev + PLAYBACK_STEP_SECONDS, duration));
    }, PLAYBACK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [isPlaying, duration]);

  // Handle playback auto-stop when reaching the end
  useEffect(() => {
    if (isPlaying && selectedTime >= duration) {
      setIsPlaying(false);
    }
  }, [selectedTime, duration, isPlaying]);

  const loadReplayData = async (buffer: ArrayBuffer, filename: string, sourceUrl?: string, generation?: number, viewerKey?: string): Promise<boolean> => {
    const stale = () => generation != null && (generation !== selectionGeneration.current || (viewerKey != null && viewerKey !== viewerRequest.current));
    if (stale()) return false;
    setLoading(true);
    setError(null);
    setLoadingStep(0);
    await waitForPaint();

    try {
      setLoadingStep(1);
      await waitForPaint();

      if (stale()) return false;
      const parsed = normalizeReplay(parse_rec(buffer));

      if (typeof window !== "undefined") {
        (window as any).__aoe2rec = parsed;
      }

      const timeline = buildTimeline(parsed);
      const players = timeline.players ?? summarizePlayers(parsed);
      const gameDuration = determineDuration(parsed, timeline.events);
      const extractedInfo = extractMatchInfo(parsed, filename, sourceUrl);
      const timelineStats = extractPlayerStats(timeline.events, gameDuration, players, timeline.chatEvents, parsed);

      setLoadingStep(2);
      await waitForPaint();

      if (stale()) return false;
      const loaded: LoadedReplayData = {
        replay: parsed,
        matchInfo: extractedInfo,
        events: timeline.events,
        chatEvents: timeline.chatEvents,
        mapResources: timeline.mapResources,
        mapCliffs: timeline.mapCliffs,
        duration: gameDuration,
        players,
        timelineStats,
      };
      setReplayData(loaded);
      setLoading(false);
      if (viewerKey == null) resetGameState();
      else {
        replayCache.current.set(viewerKey!, loaded);
        if (replayCache.current.size > 3) replayCache.current.delete(replayCache.current.keys().next().value!);
      }
      return true;
    } catch (err) {
      if (stale()) return false;
      setError(`${filename}: ${err instanceof Error ? err.message : String(err)}`);
      setLoading(false);
      return false;
    }
  };

  const handleFile = (file: File) => {
    selectionGeneration.current += 1;
    viewerRequest.current = '';
    autoLoadStarted.current = true;
    setSelectedGameId(null);
    setLoadingGameId(null);
    unloadReplay();

    const generation = selectionGeneration.current;
    const reader = new FileReader();
    reader.addEventListener("loadend", async () => {
      let buffer = reader.result as ArrayBuffer;
      let filename = file.name;

      const unzipped = await ensureUnzipped(buffer, filename);
      buffer = unzipped.buffer;
      filename = unzipped.filename;

      await loadReplayData(buffer, filename, undefined, generation);
    });
    reader.readAsArrayBuffer(file);
  };

  const handleUrlLoad = async () => {
    const trimmedUrl = replayUrl.trim();
    if (!trimmedUrl) {
      setReplayUrl("");
      return;
    }

    setShowUrlInput(false);
    selectionGeneration.current += 1;
    viewerRequest.current = '';
    autoLoadStarted.current = true;
    setSelectedGameId(null);
    setLoadingGameId(null);
    unloadReplay();

    const lowerUrl = trimmedUrl.toLowerCase();
    const isAllowed =
      lowerUrl.includes("api.ageofempires.com") ||
      lowerUrl.includes("aoe.ms");

    if (!isAllowed) {
      setError("Only https://api.ageofempires.com/ and https://aoe.ms/ links are supported.");
      return;
    }

    let targetUrl = trimmedUrl;
    if (trimmedUrl.includes("aoe.ms/replay")) {
      try {
        const url = new URL(trimmedUrl);
        const gameId = url.searchParams.get("gameId");
        const profileId = url.searchParams.get("profileId");
        if (gameId && profileId) {
          targetUrl = `https://api.ageofempires.com/api/GameStats/AgeII/GetMatchReplay/?matchId=${gameId}&profileId=${profileId}`;
        }
      } catch (e) {
        // Fallback to original URL if parsing fails
      }
    }

    setLoading(true);
    setError(null);
    setLoadingStep(0);
    let replayUrlOrName = trimmedUrl;
    const generation = selectionGeneration.current;

    try {
      const response = await fetch(targetUrl);
      if (!response.ok) {
        throw new Error(`Server responded with status ${response.status}`);
      }
      let buffer = await response.arrayBuffer();

      const unzipped = await ensureUnzipped(buffer, replayUrlOrName);
      buffer = unzipped.buffer;
      replayUrlOrName = unzipped.filename;

      await loadReplayData(buffer, replayUrlOrName, trimmedUrl, generation);
    } catch (err: any) {
      if (generation !== selectionGeneration.current) return;
      setError(`${err.message}: ${replayUrlOrName}`);
      setLoading(false);
    }
  };

  const loadLibraryGame = useCallback(async (game: LibraryGame): Promise<boolean> => {
    if (game.game_id === selectedGameId) return true;
    selectionGeneration.current += 1;
    viewerRequest.current = '';
    setSelectedGameId(game.game_id);
    setLibraryError(null);
    unloadReplay();
    setLoading(false);
    return true; // Coach fetches cached analysis; the native replay is deliberately deferred.
  }, [selectedGameId, unloadReplay]);

  useEffect(() => {
    if (selectedGameId && analysisStatus === 'loading') setLoadingGameId(selectedGameId);
    else setLoadingGameId(null);
  }, [selectedGameId, analysisStatus]);

  useEffect(() => {
    if (!selectedLibraryGame || (activeTab !== 'replay' && activeTab !== 'events')) return;
    const key = `${selectedLibraryGame.game_id}:${selectedLibraryGame.size_bytes}:${selectedLibraryGame.modified_timestamp}`;
    if (viewerRequest.current === key) return;
    viewerRequest.current = key;
    const cached = replayCache.current.get(key);
    if (cached) { setReplayData(cached); setLoading(false); return; }
    const generation = selectionGeneration.current;
    const controller = new AbortController();
    setLoading(true); setError(null); setLoadingStep(0);
    const api = process.env.NEXT_PUBLIC_COACH_API_URL || 'http://127.0.0.1:8765';
    void (async () => {
      try {
        const response = await fetch(`${api}/api/replay?game_id=${encodeURIComponent(selectedLibraryGame.game_id)}`, { signal: controller.signal });
        if (!response.ok) throw new Error(`Local replay API returned HTTP ${response.status}`);
        const buffer = await response.arrayBuffer();
        if (controller.signal.aborted || generation !== selectionGeneration.current) return;
        const unzipped = await ensureUnzipped(buffer, selectedLibraryGame.file);
        if (controller.signal.aborted || generation !== selectionGeneration.current) return;
        await loadReplayData(unzipped.buffer, unzipped.filename, undefined, generation, key);
      } catch (e) {
        if (!controller.signal.aborted && generation === selectionGeneration.current) {
          setError(e instanceof Error ? e.message : String(e)); setLoading(false);
        }
      }
    })();
    // Cancel incomplete work on navigation; completed parses stay in the bounded cache.
    return () => { controller.abort(); if (generation === selectionGeneration.current && !replayCache.current.has(key)) viewerRequest.current = ''; };
  }, [selectedGameId, selectedLibraryGame?.size_bytes, selectedLibraryGame?.modified_timestamp, activeTab]);

  useEffect(() => {
    let active = true;
    let busy = false;
    const api = process.env.NEXT_PUBLIC_COACH_API_URL || "http://127.0.0.1:8765";
    const refresh = async () => {
      if (busy) return;
      busy = true;
      try {
        const [libraryResponse, trendsResponse] = await Promise.all([
          fetch(`${api}/api/library`), fetch(`${api}/api/trends`),
        ]);
        if (!libraryResponse.ok) throw new Error(`Library API returned HTTP ${libraryResponse.status}`);
        const nextLibrary = await libraryResponse.json() as ReplayLibraryData;
        const nextTrends = trendsResponse.ok ? await trendsResponse.json() as ProgressData : null;
        if (active) {
          setLibrary(previous => JSON.stringify(previous) === JSON.stringify(nextLibrary) ? previous : nextLibrary);
          setProgressData(previous => JSON.stringify(previous) === JSON.stringify(nextTrends) ? previous : nextTrends);
          setLibraryError(null);
        }
      } catch (error) {
        if (active) setLibraryError(error instanceof Error ? error.message : String(error));
      } finally { busy = false; }
    };
    void refresh();
    const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 10000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (autoLoadStarted.current || !library) return;
    if (!library.games.length) { setLoading(false); return; }
    const candidates = library.games.filter((game) => game.status === "ready");
    if (!candidates.length) { setLoading(false); return; }
    autoLoadStarted.current = true;
    void (async () => {
      for (const game of candidates) if (await loadLibraryGame(game)) break;
    })();
  }, [library]);

  // Global keyboard listener for seeking (Left/Right arrows) and play/pause (Space)
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight" && event.code !== "Space") return;
      const target = event.target as HTMLElement;

      if (event.code === "Space") {
        if (
          (target?.tagName === "INPUT" && (target as HTMLInputElement).type !== "range") ||
          target?.tagName === "TEXTAREA" ||
          target?.tagName === "BUTTON" ||
          target?.tagName === "SELECT" ||
          target?.isContentEditable
        ) {
          return;
        }
        event.preventDefault();
        if (selectedTimeRef.current >= duration - 1) {
          setSelectedTime(0);
          setIsPlaying(true);
        } else {
          setIsPlaying((prev) => !prev);
        }
        return;
      }

      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        if (
          (target?.tagName === "INPUT" && (target as HTMLInputElement).type !== "range") ||
          target?.tagName === "TEXTAREA" ||
          target?.isContentEditable
        ) {
          return;
        }
        event.preventDefault();
      }

      const now = performance.now();
      if (now - lastKeyTimeRef.current < 16) return;
      lastKeyTimeRef.current = now;
      const step = event.shiftKey ? KEYBOARD_STEP_SHIFT_SECONDS : KEYBOARD_STEP_SECONDS;
      if (event.key === "ArrowLeft") {
        setIsPlaying(false);
      }
      requestAnimationFrame(() => {
        setSelectedTime((prev) => {
          const next =
            event.key === "ArrowRight" ? prev + step : prev - step;
          return clamp(next, 0, Math.max(duration, 1));
        });
      });
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [duration]);

  return (
    <div className="agewise-app min-h-screen">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 py-5 lg:px-8">
        <Header
          showUrlInput={showUrlInput}
          setShowUrlInput={setShowUrlInput}
          setIsPlaying={setIsPlaying}
          replayUrl={replayUrl}
          setReplayUrl={setReplayUrl}
          handleFile={handleFile}
          handleUrlLoad={handleUrlLoad}
        />

        <main className="grid min-w-0 grid-cols-1 items-start gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
          <ReplayLibrary library={library} selectedGameId={selectedGameId} loadingGameId={loadingGameId} error={libraryError} profileName={profileName} profileOptions={profileOptions} onProfileChange={handleProfileChange} onSelect={loadLibraryGame} />
          <div className="flex min-w-0 flex-col gap-5">
          <nav aria-label="Agewise views" className="flex overflow-x-auto border-b border-[color:var(--border-subtle)]">
            {([ ["coach", "Coach"], ["library", "My stats"], ["replay", "Replay"], ["events", "Events"], ["economy", "Economy"] ] as const).map(([tab, label]) =>
              <button key={tab} data-active={activeTab===tab} aria-pressed={activeTab===tab} className={`px-6 py-3 text-sm font-bold uppercase tracking-widest transition-all ${activeTab === tab ? "border-b-2 border-[color:var(--accent)] text-[color:var(--foreground)]" : "border-b-2 border-transparent text-[color:var(--muted)] hover:text-[color:var(--foreground)]"}`} onClick={() => handleTabChange(tab)}>{label}</button>
            )}
          </nav>

          {activeTab==='library'&&<LibraryStats key={profileName} library={library} profileName={profileName} onOpenGame={game=>{setIsPlaying(false);setActiveTab('coach');void loadLibraryGame(game);}}/>}
          <section className={activeTab === "coach" ? "flex flex-col gap-4" : "hidden"}>
            <CoachTab analysis={externalAnalysis} status={analysisStatus} error={analysisError} players={players} timelineStats={timelineStats} profileName={profileName} gameId={selectedGameId} selectedGame={selectedLibraryGame} recentGames={library?.games ?? []} matchDate={selectedLibraryGame?.played_at} formatClock={formatClock} onOpenEvidence={handleOpenEvidence} onOpenObservedEvidence={handleOpenObservedEvidence} onOpenPracticeMatch={matchId=>{ const game=library?.games.find(g=>g.match_id===matchId); if(game){setIsPlaying(false);setActiveTab('coach');void loadLibraryGame(game);} }} />
            <details className="panel-strong rounded-xl p-4"><summary className="font-semibold">Library progress statistics · exploratory, not matched coaching evaluations</summary><div className="mt-3"><ProgressTrends data={progressData} /></div></details>
          </section>

          <section className={activeTab === "replay" ? "block" : "hidden"}>
            {activeTab === 'replay' && <Minimap
              replay={replay} matchInfo={matchInfo} events={events} mapResources={mapResources} mapCliffs={mapCliffs}
              duration={duration} selectedTime={selectedTime} setSelectedTime={setSelectedTime} isPlaying={isPlaying} setIsPlaying={setIsPlaying}
              loading={loading} loadingStep={loadingStep} error={error} players={players} getPlayerColor={getPlayerColor}
              getPlayerOutline={getPlayerOutline} formatClock={formatClock} onOpenFile={handleFile}
              onShowUrlInput={() => { setIsPlaying(false); setShowUrlInput(true); setReplayUrl(""); }}
              onCachedCanvasesReady={handleCachedCanvasesReady} theme={theme}
            />}
            {activeTab === 'replay' && replay && <details className="panel-strong rounded-xl p-4"><summary>Match, chat, and player context</summary><div className="mt-3"><GameTab players={players} timelineStats={timelineStats} matchInfo={matchInfo} chatEvents={chatEvents} getPlayerColor={getPlayerColor} getPlayerOutline={getPlayerOutline} selectedTime={selectedTime} formatClock={formatClock} duration={duration} onSeek={(seconds) => { setIsPlaying(false); setSelectedTime(clamp(seconds, 0, duration)); }} /></div></details>}
          </section>

          {activeTab === 'economy' && <ObservationsTab key={`${externalAnalysis?.match_id}:${profileName}`} analysis={externalAnalysis} gameId={selectedGameId} profileName={profileName} selectedTime={selectedTime} formatClock={formatClock} onSeek={(seconds) => { setIsPlaying(false); setSelectedTime(clamp(seconds, 0, externalAnalysis?.duration_seconds ?? duration)); setFocusedMarker(null); setActiveTab('replay'); }} />}

          <section className={activeTab === "events" ? "block" : "hidden"}>
            {activeTab === 'events' && replay ? <><TimelineTab players={players} events={events} duration={duration} timelineStats={timelineStats} selectedTime={selectedTime} getPlayerColor={getPlayerColor} formatClock={formatClock}
              onSeek={(seconds) => { setIsPlaying(false); setSelectedTime(clamp(seconds, 0, duration)); }} analysis={externalAnalysis} analysisStatus={analysisStatus}
              onAnalysisLoaded={(report) => { setExternalAnalysis(report); setAnalysisStatus("ready"); }} />
              <details className="panel-strong mt-4 rounded-xl p-4"><summary>Statistics and developer diagnostics</summary><div className="mt-3"><StatsTab players={players} timelineStats={timelineStats} events={replayData?.events ?? []} getPlayerColor={getPlayerColor} getPlayerOutline={getPlayerOutline} /></div></details>
            </> : <div className="panel-strong rounded-xl p-5">{error || (loading ? 'Loading replay commands…' : 'Open a match to inspect its detailed command stream.')}</div>}
          </section>
          </div>
        </main>
        <footer className="flex flex-wrap items-center justify-between gap-4 px-6 pb-6 text-xs text-[color:var(--muted)]">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1">
              Designed by
              <a href="https://liouh.com/home/" className="hover:text-[color:var(--foreground)] hover:underline">
                Henry Liou
              </a>
            </span>
            <span>·</span>
            <a href="https://github.com/liouh/aoe2/issues" target="_blank" className="hover:text-[color:var(--foreground)] hover:underline">
              Report a bug
            </a>
          </div>
          <Toggle
            label="Dark mode"
            checked={theme === "dark"}
            onChange={toggleTheme}
          />
        </footer>
      </div>
    </div>
  );
}

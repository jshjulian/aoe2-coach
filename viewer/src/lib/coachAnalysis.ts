export interface AnalysisPosition {
  x: number;
  y: number;
}

export interface AnalysisEvent {
  id: string;
  time_seconds: number;
  time: string;
  player_id?: number | null;
  player?: string | null;
  category: string;
  action: string;
  kind?: string;
  unit?: string | null;
  unit_type_id?: number | null;
  technology_id?: number | null;
  building?: string | null;
  technology?: string | null;
  order?: string | null;
  amount?: number | null;
  object_ids?: number[];
  target_id?: number | null;
  position?: AnalysisPosition | null;
  status?: string;
  semantics?: string;
}

export interface CoachFinding {
  id: string;
  kind: string;
  player?: string;
  time_seconds: number;
  end_time_seconds?: number;
  title: string;
  summary: string;
  event_ids: string[];
  confidence: "high" | "medium" | "low";
  limitations: string | string[];
  coordinates?: Array<{ position: AnalysisPosition; from_time?: string; to_time?: string; gap_seconds?: number; from_event_id?: string; to_event_id?: string }>;
}

export interface PressureKeyOrder {
  event_id: string;
  time: string;
  target_id?: number | null;
  position: AnalysisPosition;
  selected_object_ids: number[];
  distance_to_target_base: number;
  semantics: string;
}

export interface PressureIncident {
  id: string;
  target_player: string;
  enemy_player: string;
  start_time_seconds: number;
  end_time_seconds: number;
  start_time: string;
  end_time: string;
  group_object_ids: number[];
  event_ids: string[];
  actions: string[];
  key_orders: PressureKeyOrder[];
  defender_responses: Array<{ event_id: string; time: string; response: string }>;
  title: string;
  summary: string;
  confidence: "high" | "medium" | "low";
  limitations: string[];
}

export interface OpeningObservation {
  observation_version: number;
  player_id: number;
  player: string;
  label: string;
  confidence: string;
  coverage: string;
  window_seconds: [number, number];
  patterns: Array<{ tag: string; label: string; queue_command_count: number; confidence: string; reason: string; event_ids: string[]; first_queue_event_id: string; first_queue_seconds: number }>;
  transitions: Array<{ tag: string; label: string; event_ids: string[]; interval_seconds: number; confidence: string; meaning: string; context?: { window_seconds: [number, number]; status: string; event_ids: string[]; opponent_order_event_ids: string[]; reason: string } }>;
  intended_opening: { status: string; reason: string };
  adaptation: { status: string; event_ids: string[]; opponent_order_event_ids: string[]; reason: string };
  limitations: string[];
}

export interface PythonAnalysis {
  schema_version: number;
  match_id: string;
  source_file: string;
  map: string;
  duration_seconds: number;
  duration?: string;
  played_at?: string | null;
  played_at_source?: string | null;
  estimated_real_duration_seconds?: number | null;
  game_speed?: string | null;
  game_speed_id?: number | null;
  game_speed_multiplier?: number | null;
  rated?: boolean;
  opening_observation_version?: number;
  opening_observations?: OpeningObservation[];
  replay_provenance?: { provenance_version: number; source: string; edition?: string; build_version?: number | null; dataset_id?: number | null; mod_compatibility: string; compatibility_note?: string; reason?: string };
  players: Array<{ id: number; name: string; civilization: string; team_id?: number | number[] | null; won?: boolean; base?: AnalysisPosition | null; elo_snapshot?: number | null; rating_track?: string | null }>;
  events: AnalysisEvent[];
  findings: CoachFinding[];
  pressure_incidents: PressureIncident[];
  opening_milestones?: Array<{ player_id: number; player: string; civilization: string; milestones: Record<string, { time: string; time_seconds: number; event_id: string } | null> }>;
  initial_town_centers?: Array<{player_id:number;object_ids:number[];status:string;position?:AnalysisPosition}>;
  tc_queue_activity?: Array<{ player_id: number; player: string; town_center_object_ids: number[]; villager_queue_command_count: number; long_command_gaps: Array<{ from_event_id: string; to_event_id: string; from_time: string; to_time: string; gap_seconds: number; position: AnalysisPosition }> ; caveat: string }>;
}

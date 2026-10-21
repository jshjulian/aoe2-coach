import type { AnalysisPosition } from './coachAnalysis';

export interface SituationIncident {
  id: string; type: string; detector_version: number;
  participants: {selected_player_id: number; opponent_player_id: number};
  window_seconds: number[]; review_window_seconds: number[];
  replay_anchor: {event_id: string; time_seconds: number};
  zone: {position: AnalysisPosition; source: string};
  locations: Array<{event_id: string; position: AnalysisPosition; semantics: string}>;
  selected_object_ids: number[]; event_ids: string[]; situation_event_ids: string[];
  responses: Array<{event_id: string; time_seconds: number; temporal_relation: string; spatial_relation: string; meaning: string}>;
  unlocalized_response_event_ids: string[]; context_event_ids: string[];
  observation: string; interpretation: string; actual_response: string;
  options: Array<{action: string; condition: string}>;
  outcome: {status: string; verified_consequences: string[]; reason: string};
  alternatives: string[];
  quality: {evidence_strength: string; vision: string; unit_types: string; response_intent: string; stream_completeness: string; right_censored: boolean; left_censored: boolean};
}
export interface SituationReview {
  situation_version: number; review_version?: number; match_id: string; status: string;
  positive?: {text: string; caveat: string; event_ids: string[]} | null;
  timeline?: Array<{id: string; event_id: string; time_seconds: number; kind: string; label: string; player_id: number | null; position?: AnalysisPosition | null; incident_id?: string}>;
  episodes?: Array<{id: string; incident_ids: string[]; topic: string; window_seconds: number[]; review_window_seconds: number[]; event_ids: string[]; priority_dimensions: number[]; context_event_ids: string[]}>;
  player: {id: number; name: string; civilization: string} | null;
  incidents: SituationIncident[];
  recommendations: Array<{
    id: string; rule_id: string; rule_version: number; kind: string; incident_id: string;
    title: string; topic?: string; episode_id?: string; summary?: string; response_summary?: string; uncertainty_label?: string; practice_short?: string;
    replay_anchor: {event_id: string; time_seconds: number}; event_ids: string[];
    question: string; principle: string; exercise: string; priority_reasons: string[]; uncertainties: string[];
  }>;
  links: Array<{earlier_incident_id: string; later_incident_id: string; relation: string}>;
  decisions: Array<{incident_id: string; status: string; reason: string}>;
  coverage: {searched_window_seconds?: number[]; spatial_scope: string; command_stream_completeness: string; gameplay_state_complete: boolean; unresolved_team_player_ids?: number[]};
  ranking_policy: string[]; limitations: string[]; abstention_reason: string | null;
  knowledge?: {
    menu_version: number; status: string; reason: string; civilization: string | null;
    source: {commit: string; declared_update: number; pack_id: string; pack_version: number; menu_version: number} | null;
    reference_facts: Array<{id: string; text: string; source_refs: Array<{id: string; url: string}>}>;
    options_by_incident: Array<{incident_id: string; recorded_age: number | null; age_event_ids: string[]; options: Array<{kind: string; entity_id: number; name: string; minimum_age: number; availability: string; source_url: string}>}>;
    limitations: string[];
  };
}

export interface ObservationContext {
  match_id: string; batch_id: string | null; status: string; selected_player_id: number | null;
  validated_for_application: false; checkpoint_count: number;
  readable_point_count: number; checked_point_count: number; rejected_point_count: number;
  readable_window_seconds: [number, number] | null;
}
export interface ReviewedMomentContext {
  schema_version: 1; match_id: string; status: 'available' | 'not_reviewed' | 'select_player' | 'unavailable';
  independently_validated: false; eligible_for_automatic_priority: false; causal_claim: false;
  moment: null | {
    match_id: string; player: { id: number; name: string; civilization: string };
    review_id: string; observation_batch_id: string; author_kind: 'assistant' | 'user';
    title: string; summary: string; practice: string; alternatives: string[]; limitations: string[];
    anchor_seconds: number;
    facts: Array<{player_id: number; player_name: string; metric: string; label: string; unit: string;
      time_seconds: number; value: number; evidence_sha256: string}>;
  };
}
export type OpenObservedEvidence = (seconds: number, view: 'replay' | 'economy') => void;

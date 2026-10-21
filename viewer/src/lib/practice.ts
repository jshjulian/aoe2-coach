export interface PracticeChoiceRequest {id?:string;request:number;change?:boolean}
export interface PracticeMatch {
  match_id: string; player: {id: number; name: string; civilization: string} | null; build: number | null; map: string;
}
export interface PracticeEvidence {event_id: string; time_seconds: number}
export interface PracticeFocus {
  id: string; player_name: string; status: 'active' | 'retired'; label: string; when: string; action: string; adapt: string;
  selected_at: string; retired_at?: string; last_kept_at?: string; origin: PracticeMatch;
  replaces_focus_id?:string;replaced_by_focus_id?:string;retirement_reason?:'explicit_focus_switch';
  source: {kind: 'situation_suggestion' | 'user_authored'; topic?: string;rule_id?:string;rule_version?:number;knowledge_pack_sha256?:string}; evidence: PracticeEvidence[];
}
export interface PracticeLog {
  focus_id: string; match: PracticeMatch; recorded_at: string; opportunity: 'yes' | 'no' | 'uncertain'; attempt: 'yes' | 'no' | 'uncertain';
  status: 'reported_attempt' | 'reported_not_attempted' | 'not_applicable' | 'insufficient_evidence';
  note: string; evidence: PracticeEvidence[]; provenance: string; skill_improvement_established: false;
}
export interface PracticeContext {
  schema_version: number; current_match: PracticeMatch; status: string;
  active_focus: PracticeFocus | null;
  suggestions: Array<{id: string; label: string; when: string; action: string; adapt: string; evidence: PracticeEvidence[]}>;
  recent_logs: PracticeLog[]; logged_match_count: number; current_log: PracticeLog | null;
  opportunity: {status: string; explanation: string; evidence: PracticeEvidence[]} | null;
  history: Array<{focus: PracticeFocus; recent_logs: PracticeLog[]; logged_match_count: number}>;
  legacy_goal_active: boolean; eligible_for_automatic_priority: false; skill_improvement_established: false; limitation: string;
}

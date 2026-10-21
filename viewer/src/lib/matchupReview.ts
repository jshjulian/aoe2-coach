export interface RulesContext {
  version: number;
  rules: 'standard' | 'unknown';
  match_id: string;
  player: string;
  declared_at: string;
  provenance: string;
}
export interface KnowledgeRef {
  id: string; civilization: string; kind: string; entity_id: number; field: string; url: string;
  age_id?: number; available?: boolean; node_id?: string;
}
export interface MatchupFact {
  id: string; civilization: string; minimum_age: number; text: string; source_refs: KnowledgeRef[];
}
export interface MatchupOption {
  id: string; label: string; age: number; requires: string; source_refs: KnowledgeRef[];
  availability: string; structure_placement_event_ids: string[];
}
export interface MatchupReview {
  matchup_version: number;
  match_id: string;
  player: { id: number; name: string; civilization: string } | null;
  opponent: { id: number; name: string; civilization: string } | null;
  status: string;
  source: { repository: string; commit: string; declared_update: number; pack_id: string; pack_version: number; reviewed_on: string } | null;
  compatibility: { status: string; conditional_tips_enabled: boolean; basis?: string; reasons: string[] };
  reference_facts: MatchupFact[];
  observations: Array<{ side: string; evidence_class: string; command_count: number; unit_labels: string[]; event_ids: string[]; window_seconds: number[]; meaning: string }>;
  tips: Array<{
    id: string; rule_id: string; rule_version: number; kind: string; title: string; window_seconds: number[];
    replay_anchor_event_id: string; event_ids: string[]; observations: string[]; interpretation: string; action: string;
    alternatives: string[]; fact_ids: string[]; options: MatchupOption[];
    evidence_quality: { catalog: string; commands: string; interpretation: string; vision: string };
    conditions: string[]; not_claimed: string[];
  }>;
  decisions: Array<{ rule_id: string; status: string; reason: string; candidate_windows_searched?: number }>;
  limitations: string[];
  abstention_reason: string | null;
}

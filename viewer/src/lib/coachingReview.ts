import type { MilitaryReasoning } from './militaryReasoning';
import type { TakeawayContext } from './balancedTakeaway';
import type { GameplayContext } from './gameplay';
import type { PracticeContext } from './practice';
import type { PracticeProgress } from './practiceProgress';
import type { AnalysisEvent } from './coachAnalysis';
import type { MatchupReview, RulesContext } from './matchupReview';
import type { SituationReview } from './situationReview';
import type { ObservationContext, ReviewedMomentContext } from './reviewedMoments';

export interface EvidenceQuality {
  anchors_reliably_decoded: boolean;
  complete_for_measure: boolean;
  stream_completeness: string;
  gameplay_state_complete: boolean;
  reason: string;
}
export interface Observation {
  id: string; text: string; event_ids: string[]; evidence_class: string;
  window_seconds: number[]; derivation?: string;
}
export interface CoachingReview {
  coaching_schema_version: number; analysis_schema_version: number; match_id: string;
  player: {id: number; name: string} | null;
  plan: {id: string | null; status: string; label: string};
  primary: {
    id: string; title: string; state: string; rule_id: string; rule_version: number;
    observations: Observation[]; evidence_quality: EvidenceQuality;
    interpretation: {text: string; confidence: string; alternatives: string[]};
    recommendation: {action: string; conditions: string[]; not_claimed: string[]};
    priority_reasons: string[]; supporting_context_event_ids: string[]; counterevidence_event_ids: string[];
    context: {window_seconds: number[]; aggression: string; evidence_quality: EvidenceQuality};
    replay_anchor: {event_id: string; time_seconds: number}; practice_goal_ids: string[];
  } | null;
  abstention_reason: string | null; what_went_well: Observation[];
  practice_goals: Array<{
    id: string; label: string; primary_measure: {source: string; target: string};
    supporting_indicator: {name: string; baseline_seconds: number; caveat: string}; stop_or_adapt: string;
  }>;
  detectors: Array<{rule_id: string; rule_version: number; status: string; reason: string; priority: number[]; evidence_quality: EvidenceQuality}>;
  ranking_policy: string[]; ranking_note: string;
}
export interface CoachingState {
  rules_context?: RulesContext | null;
  plan: {id: string; confirmed: boolean} | null;
  feedback: {verdict: string; note: string} | null;
  goal: {selection_id: string; label: string; active: boolean; baseline_seconds: number; baseline_match_id: string} | null;
  evaluations: Array<{match_id: string; checklist: string; adaptation: string; metric_status: string; interval_seconds: number | null; delta_from_baseline_seconds: number | null}>;
}
export interface CoachingResponse { reasoning_context?: MilitaryReasoning; takeaway_context?: TakeawayContext; progress_context?: PracticeProgress; gameplay_context?: GameplayContext; practice_context?: PracticeContext; review: CoachingReview; state: CoachingState; matchup?: MatchupReview; situation?: SituationReview; observation_context?: ObservationContext; reviewed_moment_context?: ReviewedMomentContext }
export type OpenEvidence = (event: AnalysisEvent, label: string) => void;

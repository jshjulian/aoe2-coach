export interface ComparisonSnapshot {
 schema_version:number;focus_id?:string;match_id?:string;eligible:boolean;reason:string|null;can_declare_standard_rules:boolean;
 profile?:{map:string;civilization:string;opponent_civilization:string;build:number;rules_basis:string}|null;
 cue_phase?:string|null;evidence?:Array<{event_id:string;time_seconds:number}>;
}
export interface PracticeProgress {
 schema_version:number;status:string;match_id:string;player:{id:number;name:string;civilization:string}|null;focus_id:string|null;
 scope:string;reference:ComparisonSnapshot|null;total_journal_entries:number;scanned_entries:number;truncated:boolean;
 counts:Record<string,number>;matched_counts:Record<string,number>;confirmed_opportunities:number;known_attempt_answers:number;uncertain_attempt_answers:number;
 sample_status:string;excluded_count:number;exclusion_reasons:Record<string,number>;
 entries:Array<{match_id:string;player:{id:number;name:string;civilization:string};map:string;recorded_at:string;status:string;matched:boolean;exclusion_reason:string|null;evidence:Array<{event_id:string;time_seconds:number}>}>;
 eligible_for_automatic_priority:false;skill_improvement_established:false;verified_execution:false;trend_established:false;limitation:string;
}

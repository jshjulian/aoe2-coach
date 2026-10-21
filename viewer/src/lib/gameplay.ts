export interface GameplayDecision {
 id:string;topic:string;rule_id:string;rule_version:number;title:string;summary:string;
 replay_anchor:{event_id:string;time_seconds:number};window_seconds:number[];event_ids:string[];
 recorded:Array<{evidence_class:string;text:string;event_ids:string[];information:string}>;
 validated_state_measurements:unknown[];user_confirmed_observations:unknown[];
 hypothesis:string;question:string;principle:string;practice_short:string;exercise:string;
 interactions:Array<{id:string;conditions:string[];guidance:string;provenance:string}>;
 options:Array<{if:string;then:string;not_claimed:string}>;alternatives:string[];information_available:string;
 response_summary:string;response_event_ids:string[];missing_information:string[];
 source:{pack_id:string;pack_version:number;pack_sha256:string;authorship:string;review_status:string};
 causal_claim:false;battle_outcome:'unknown';
 feedback:{verdict:string;note:string;recorded_at:string;provenance:string;eligible_for_automatic_priority:false;match_id:string;decision_id:string;player:{id:number;name:string}}|null;
}
export interface GameplayReference {
 status:string;reason:string;source:{commit:string;declared_update:number}|null;
 entities:Array<{kind:string;entity_id:number;name:string;role:string;catalog_available:boolean;base_cost:Record<string,number>;base_train_seconds:number|null;observed_in_match:false}>;
 civilization_description:string|null;
}
export interface GameplayContext {
 schema_version:number;match_id:string;replay_build?:number|null;validated_state_measurements?:unknown[];player:{id:number;name:string;civilization:string}|null;
 status:string;primary:GameplayDecision|null;candidates:GameplayDecision[];causal_claim:false;skill_rating:null;reason:string|null;
 reference?:GameplayReference;
 matchups?:{evidence_class:string;effective_state_established:false;limitation:string;reason?:string;opponents:Array<{
  player_id:number;civilization:string;reference:GameplayReference;question:string;
  retrospective_inputs:Array<{evidence_class:string;event_id:string;time_seconds:number;unit:string;information:string}>;
  options:Array<{evidence_class:string;family:string;advice:string;qualification:string;catalog_options:Array<{kind:string;entity_id:number;name:string}>}>;
 }>};
 priority_policy:string;coverage?:Record<string,unknown>;
}

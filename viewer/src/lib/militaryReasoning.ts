import type {CoachingResponse} from './coachingReview';
import type {PythonAnalysis} from './coachAnalysis';

export interface Role {id:string;name:string;purpose:string;exceptions:string;preferred_against:string[]}
export interface RoleRef {event_id:string;time_seconds:number;player_id:number;information:string}
export interface ResponseAlternative {kind:'Unit';entity_id:number;name:string;role:string;catalog_available:boolean;minimum_age:number|null;building_name:string|null;building_catalog_available:boolean;base_cost:Record<string,number>|null;observed_in_match:false;source_ref:string;availability_source_ref:string}
export interface MilitarySituation {
 id:string;title:string;topic:'composition_response';rule_version:1;rule_id:string;event_ids:string[];evidence:RoleRef[];evidence_sha256:string;
 replay_anchor:{event_id:string;time_seconds:number};window_seconds:number[];
 objective:{status:string;text:string;event_ids:string[]};
 threat:{role:string;name:string;event_ids:string[];focus_event_id:string;status:string};
 information:{player_vision:'unknown';enemy_inputs:string;resources:null;fielded_units:null;completed_production:null};
 transition:{from_role:string;to_role:string;from_unit:string;to_unit:string;event_ids:string[];sequence:Array<{role:string;unit:string;event_id:string;time_seconds:number}>};
 recent_requests:RoleRef[];prior_production:RoleRef[];fortification_context:{event_ids:string[];qualification:string};
 subsequent_observations:{status:string;event_ids:string[];outcome:'unknown'};
 comparison:{selected_role:Role;threat_role:Role;alternative:ResponseAlternative|null;alternative_role:Role|null;requirements:Array<{check:string;status:string;text:string;event_ids:string[]}>;conditions:string;position_alternative:string;position_exceptions:string};
 clarification:{id:string;question:string;choices:Array<{id:string;label:string}>};
 reviewed_context:{status:'unanswered'|'reviewed'|'unavailable';revision:number;answer:string|null;note:string;provenance:string;eligible_for_measurements:false;reason?:string;recorded_at?:string;binding?:Record<string,unknown>};
 assessment:{status:string;headline:string;text:string;positive:string|null};
 missing_information:string[];counterevidence:string[];practice_short:string;practice_title:string;
 source:{pack_id:string;pack_version:number;pack_sha256:string};causal_claim:false;validated_state_measurements:[];
}
export interface MilitaryReasoning {
 schema_version:1;status:'available'|'unavailable';mode:'deterministic';ai_enabled:false;match_id:string;replay_build:number;player:{id:number;name:string;civilization:string}|null;
 knowledge:{pack_id:string;pack_version:number;sha256:string;source_commit:string;authorship:string};
 catalog:{commit:string;declared_update:number;status:string;standard_rules_verified:false;qualification:string;civilization:string;civilization_description:string};
 source_binding:{content_sha256:string;normalizer_schema:number;provenance_version:number;analysis_generator_identity:null;reasoner_code_sha256:string;knowledge_adapter_sha256:string;catalog_lock_sha256:string;reasoner_version:number};
 situations:MilitarySituation[];primary_id:string|null;causal_claim:false;validated_state_measurements:[];skill_rating:null;
 coverage:{scope:string;situation_limit:number;truncated:boolean;selection:string};limitations:string[];reason?:string|null;
}
const roleIds=new Set(['infantry','spear','cavalry','archer','skirmisher']);
const unitRoles:Record<string,string>={'Militia':'infantry','Man-at-Arms':'infantry','Spearman':'spear','Scout Cavalry':'cavalry','Archer':'archer','Skirmisher':'skirmisher'};
const text=(v:unknown,max=4000):v is string=>typeof v==='string'&&v.length>0&&v.length<=max;
const hex=(v:unknown,n:number)=>typeof v==='string'&&new RegExp(`^[a-f0-9]{${n}}$`).test(v);
const texts=(v:unknown,max=16):v is string[]=>Array.isArray(v)&&v.length<=max&&v.every(x=>text(x));
const role=(v:Role)=>v&&roleIds.has(v.id)&&[v.name,v.purpose,v.exceptions].every(x=>text(x))&&Array.isArray(v.preferred_against)&&v.preferred_against.length<=5&&v.preferred_against.every(x=>roleIds.has(x));

/** Optional source-bound interpretation only. Any malformed nested identity/state falls back. */
export function usableReasoning(response:CoachingResponse|null,analysis:PythonAnalysis,name:string):MilitaryReasoning|null {
 try {
  const r=response?.reasoning_context,p=analysis.players.find(p=>p.name===name),events=new Map(analysis.events.map(e=>[e.id,e]));
  if(!r||r.status!=='available'||r.schema_version!==1||r.mode!=='deterministic'||r.ai_enabled!==false||!p||analysis.players.filter(p=>p.name===name).length!==1||analysis.players.length!==2||r.match_id!==analysis.match_id||r.player?.id!==p.id||r.player.name!==name||r.player.civilization!==p.civilization||r.replay_build!==analysis.replay_provenance?.build_version||r.causal_claim!==false||r.skill_rating!==null||!Array.isArray(r.validated_state_measurements)||r.validated_state_measurements.length||!Array.isArray(r.situations)||r.situations.length>6||new Set(r.situations.map(c=>c.id)).size!==r.situations.length||!r.situations.some(c=>c.id===r.primary_id))return null;
  if(r.knowledge.pack_id!=='situational-composition'||r.knowledge.pack_version!==1||!hex(r.knowledge.sha256,64)||!hex(r.knowledge.source_commit,40)||!text(r.knowledge.authorship)||r.catalog.commit!==r.knowledge.source_commit||r.catalog.declared_update!==r.replay_build||r.catalog.status!=='pinned_catalog_not_effective_state'||r.catalog.standard_rules_verified!==false||r.catalog.civilization!==p.civilization||!text(r.catalog.qualification)||typeof r.catalog.civilization_description!=='string')return null;
  if(r.source_binding.content_sha256!==analysis.match_id||r.source_binding.normalizer_schema!==5||r.source_binding.analysis_generator_identity!==null||!hex(r.source_binding.reasoner_code_sha256,64)||!hex(r.source_binding.knowledge_adapter_sha256,64)||!hex(r.source_binding.catalog_lock_sha256,64)||r.source_binding.reasoner_version!==1||r.source_binding.provenance_version!==analysis.replay_provenance?.provenance_version||r.coverage.situation_limit!==6||typeof r.coverage.truncated!=='boolean'||!text(r.coverage.scope)||!text(r.coverage.selection)||!texts(r.limitations))return null;
  for(const c of r.situations){
   if(!/^response:[a-f0-9]{24}$/.test(c.id)||c.rule_version!==1||c.rule_id!=='military-role-response'||c.topic!=='composition_response'||!text(c.title)||c.causal_claim!==false||!Array.isArray(c.validated_state_measurements)||c.validated_state_measurements.length||!hex(c.evidence_sha256,64)||!texts(c.event_ids,48)||!c.event_ids.length||new Set(c.event_ids).size!==c.event_ids.length||c.event_ids.some(id=>!events.has(id)))return null;
   const own=(ids:string[])=>ids.every(id=>c.event_ids.includes(id)&&events.get(id)?.player_id===p.id);
   const bound=(ids:string[])=>Array.isArray(ids)&&ids.length<=48&&ids.every(id=>c.event_ids.includes(id));
   const refs=(refs:RoleRef[],max=48)=>Array.isArray(refs)&&refs.length<=max&&refs.every(ref=>bound([ref.event_id])&&events.get(ref.event_id)?.time_seconds===ref.time_seconds&&events.get(ref.event_id)?.player_id===ref.player_id&&ref.information===(ref.player_id===p.id?'own_recorded_input':'retrospective_opponent_input_not_player_vision'));
   const t=events.get(c.replay_anchor.event_id);
   if(!t||t.player_id!==p.id||t.time_seconds!==c.replay_anchor.time_seconds||!c.event_ids.includes(t.id)||!Array.isArray(c.window_seconds)||c.window_seconds.length!==2||c.window_seconds.some(x=>!Number.isFinite(x)||x<0||x>analysis.duration_seconds)||c.window_seconds[0]>t.time_seconds||c.window_seconds[1]<t.time_seconds||c.window_seconds[1]-c.window_seconds[0]>480||!refs(c.evidence)||c.evidence.length!==c.event_ids.length||new Set(c.evidence.map(e=>e.event_id)).size!==c.event_ids.length||!refs(c.recent_requests,24)||!refs(c.prior_production,5))return null;
   if(c.information.player_vision!=='unknown'||c.information.enemy_inputs!=='retrospective_only'||c.information.resources!==null||c.information.fielded_units!==null||c.information.completed_production!==null||c.subsequent_observations.outcome!=='unknown'||c.subsequent_observations.status!=='later_inputs_not_outcomes'||!bound(c.subsequent_observations.event_ids)||!own(c.subsequent_observations.event_ids)||!bound(c.fortification_context.event_ids)||!text(c.fortification_context.qualification))return null;
   if(c.objective.status!=='inferred_not_proven'||!text(c.objective.text)||!bound(c.objective.event_ids)||!own(c.objective.event_ids)||c.threat.status!=='retrospective_investment_not_observed_army'||!roleIds.has(c.threat.role)||!text(c.threat.name)||!bound(c.threat.event_ids)||!c.threat.event_ids.length||c.threat.event_ids.some(id=>events.get(id)?.player_id===p.id)||!c.threat.event_ids.includes(c.threat.focus_event_id))return null;
   const threat=events.get(c.threat.focus_event_id);
   if(!threat||(unitRoles[threat.unit??'']??(threat.technology==='Man-at-Arms'?'infantry':undefined))!==c.threat.role||threat.time_seconds>t.time_seconds)return null;
   if(!roleIds.has(c.transition.from_role)||!roleIds.has(c.transition.to_role)||c.transition.from_role===c.transition.to_role||unitRoles[c.transition.from_unit]!==c.transition.from_role||unitRoles[c.transition.to_unit]!==c.transition.to_role||!bound(c.transition.event_ids)||c.transition.event_ids.length!==2||!own(c.transition.event_ids)||c.transition.event_ids[1]!==t.id||events.get(c.transition.event_ids[0])?.unit!==c.transition.from_unit||t.unit!==c.transition.to_unit||!Array.isArray(c.transition.sequence)||c.transition.sequence.length>6||c.transition.sequence.some(s=>!own([s.event_id])||events.get(s.event_id)?.time_seconds!==s.time_seconds||events.get(s.event_id)?.unit!==s.unit||unitRoles[s.unit]!==s.role))return null;
   if(!role(c.comparison.selected_role)||c.comparison.selected_role.id!==c.transition.to_role||!role(c.comparison.threat_role)||c.comparison.threat_role.id!==c.threat.role||![c.comparison.conditions,c.comparison.position_alternative,c.comparison.position_exceptions].every(x=>text(x))||!Array.isArray(c.comparison.requirements)||c.comparison.requirements.length>3||c.comparison.requirements.some(x=>!text(x.check)||!text(x.status)||!text(x.text)||!bound(x.event_ids)))return null;
   const alt=c.comparison.alternative,altRole=c.comparison.alternative_role;
   if(alt?(!altRole||!role(altRole)||altRole.id!==alt.role):altRole!==null)return null;
   if(alt&&(alt.kind!=='Unit'||!Number.isInteger(alt.entity_id)||unitRoles[alt.name]!==alt.role||alt.catalog_available!==true||alt.building_catalog_available!==true||![1,2].includes(alt.minimum_age??-1)||!text(alt.building_name)||alt.observed_in_match!==false||!text(alt.availability_source_ref)||!alt.availability_source_ref.startsWith('https://github.com/SiegeEngineers/aoe2techtree/blob/'+r.knowledge.source_commit+'/data/trees/')||!text(alt.source_ref)||!alt.source_ref.startsWith('https://github.com/SiegeEngineers/aoe2techtree/blob/'+r.knowledge.source_commit+'/')||alt.base_cost!==null&&(typeof alt.base_cost!=='object'||Object.values(alt.base_cost).some(v=>!Number.isFinite(v)||v<0))))return null;
   if(c.source.pack_id!==r.knowledge.pack_id||c.source.pack_version!==1||c.source.pack_sha256!==r.knowledge.sha256||!text(c.practice_short,400)||!text(c.practice_title,100)||!texts(c.missing_information)||!texts(c.counterevidence)||!text(c.assessment.headline)||!text(c.assessment.text))return null;
   if(c.clarification.id!=='why-role-switch-v1'||!text(c.clarification.question)||!Array.isArray(c.clarification.choices)||c.clarification.choices.length<5||c.clarification.choices.length>6||new Set(c.clarification.choices.map(x=>x.id)).size!==c.clarification.choices.length||c.clarification.choices.some(x=>!['reported_threat','different_threat','resource_constraint','other','uncertain','not_applicable'].includes(x.id)||!text(x.label)))return null;
   const u=c.reviewed_context;
   if(!['unanswered','reviewed','unavailable'].includes(u.status)||!Number.isInteger(u.revision)||u.revision<0||typeof u.note!=='string'||u.note.length>1000||u.provenance!=='player_reviewed_context_not_reconstructed_state'||u.eligible_for_measurements!==false||u.answer!==null&&!c.clarification.choices.some(x=>x.id===u.answer)||u.status==='reviewed'&&(u.revision<1||u.answer===null))return null;
   if(u.status==='reviewed'){
    const b=u.binding;
    if(!b||b.match_id!==r.match_id||JSON.stringify(b.player)!==JSON.stringify(r.player)||b.situation_id!==c.id||b.replay_build!==r.replay_build||b.question_id!==c.clarification.id||b.knowledge_sha256!==r.knowledge.sha256||b.evidence_sha256!==c.evidence_sha256||JSON.stringify(b.window_seconds)!==JSON.stringify(c.window_seconds)||JSON.stringify(b.event_refs)!==JSON.stringify(c.evidence)||JSON.stringify(b.source_binding)!==JSON.stringify(r.source_binding))return null;
   }
   if(!['withheld_after_correction','player_correction_requires_review','reported_constraint','conditionally_supported_by_player_review','conditional_comparison','needs_clarification'].includes(c.assessment.status)||c.assessment.positive!==null&&(!text(c.assessment.positive)||c.assessment.status!=='conditionally_supported_by_player_review'||u.status!=='reviewed'))return null;
  }
  return r;
 }catch{return null;}
}

import type {PythonAnalysis} from './coachAnalysis';
import type {CoachingResponse} from './coachingReview';

export interface TakeawayPositive {
  id:string; kind:'protective_input'|'prompt_followup'|'age_lead'; text:string;
  caveat:string; event_ids:string[]; derivation:string;
}
export interface TakeawayRevisit {
  id:string; source_kind:'gameplay'|'situation'; topic:string; rule_id:string; rule_version:number;
  source_signature:unknown; title:string; recorded:string; question:string;
  replay_anchor:{event_id:string;time_seconds:number}; event_ids:string[]; window_seconds:number[];
  practice_id:string|null; editorial_tier:number; recording_seconds_remaining:number; selection_reason:string;
}
export interface TakeawayContext {
  schema_version:number; policy_version:number; id?:string; status:'available'|'unavailable';
  match_id:string; replay_build?:number|null; player:{id:number;name:string;civilization:string}|null;
  positives:TakeawayPositive[]; primary_positive_id:string|null;
  revisits:TakeawayRevisit[]; primary_revisit_id:string|null;
  practice_ids:string[]; primary_practice_id:string|null;
  selection_policy:string; scope_notes:string[]; causal_claim:false; skill_improvement_established:false;
  coverage:{revisit_limit:number;positive_limit:number;revisits_truncated:boolean;positives_truncated:boolean;garrison_selection:string;positive_selection:string;positive_scope:string};
}

/** Fail closed on optional packets. Raw gameplay/situation components keep their own guards. */
export function usableTakeaway(response:CoachingResponse|null|undefined,analysis:PythonAnalysis,name:string):TakeawayContext|null {
 try {
  const t=response?.takeaway_context,g=response?.gameplay_context,s=response?.situation,p=response?.practice_context;
  const player=analysis.players.find(p=>p.name===name),events=new Map(analysis.events.map(e=>[e.id,e]));
  if(!t||t.status!=='available'||t.schema_version!==1||t.policy_version!==1||!player||analysis.players.filter(p=>p.name===name).length!==1||
     t.match_id!==analysis.match_id||t.player?.id!==player.id||t.player.name!==name||t.player.civilization!==player.civilization||
     t.replay_build!==(analysis.replay_provenance?.build_version??null)||t.causal_claim!==false||t.skill_improvement_established!==false||
     g?.schema_version!==2||g.match_id!==analysis.match_id||g.player?.id!==player.id||g.player.name!==name||g.player.civilization!==player.civilization||g.causal_claim!==false||g.skill_rating!==null||g.replay_build!==t.replay_build||!Array.isArray(g.validated_state_measurements)||g.validated_state_measurements.length!==0||
     s?.review_version!==2||s.match_id!==analysis.match_id||s.player?.id!==player.id||s.player.name!==name||
     p?.schema_version!==1||p.current_match.match_id!==analysis.match_id||p.current_match.player?.id!==player.id||p.current_match.player.name!==name||p.eligible_for_automatic_priority!==false||p.skill_improvement_established!==false||!Array.isArray(p.suggestions)||p.suggestions.length>24||
     (p.active_focus&&(p.active_focus.player_name!==name||p.active_focus.origin.player?.name!==name||p.active_focus.status!=='active'))||
     !Array.isArray(t.positives)||t.positives.length>8||!Array.isArray(t.revisits)||t.revisits.length>24||!Array.isArray(t.practice_ids)||
     t.practice_ids.length>24||t.practice_ids.some(id=>typeof id!=='string')||
     !Array.isArray(t.scope_notes)||!t.scope_notes.length||t.scope_notes.length>4||t.scope_notes.some(n=>typeof n!=='string'||n.length>1000)||
     typeof t.selection_policy!=='string'||t.selection_policy.length>4000||typeof t.id!=='string'||!/^takeaway:[a-f0-9]{24}$/.test(t.id)||
     !t.coverage||t.coverage.positive_limit!==8||t.coverage.revisit_limit!==24||typeof t.coverage.positives_truncated!=='boolean'||typeof t.coverage.revisits_truncated!=='boolean'||typeof t.coverage.positive_scope!=='string'||typeof t.coverage.garrison_selection!=='string'||typeof t.coverage.positive_selection!=='string')return null;
  const unique=(ids:string[])=>new Set(ids).size===ids.length;
  if(!unique(t.positives.map(x=>x.id))||!unique(t.revisits.map(x=>x.id))||!unique(t.practice_ids))return null;
  for(const r of t.revisits){
   const c=r.source_kind==='gameplay'?g.candidates.find(c=>c.id===r.id):r.source_kind==='situation'?s.recommendations.find(c=>c.id===r.id):undefined;
   if(!c||c.rule_id!==r.rule_id||c.rule_version!==r.rule_version||c.topic!==r.topic||
      !Array.isArray(r.event_ids)||!r.event_ids.length||r.event_ids.length>6||!unique(r.event_ids)||
      !r.event_ids.includes(r.replay_anchor.event_id)||r.event_ids.some(id=>!events.has(id)||!c.event_ids.includes(id))||
      c.replay_anchor.event_id!==r.replay_anchor.event_id||c.replay_anchor.time_seconds!==r.replay_anchor.time_seconds||
      events.get(r.replay_anchor.event_id)?.time_seconds!==r.replay_anchor.time_seconds||
      !Array.isArray(r.window_seconds)||r.window_seconds.length!==2||r.window_seconds.some(n=>!Number.isFinite(n))||r.window_seconds[0]<0||r.window_seconds[1]>analysis.duration_seconds||r.window_seconds[0]>r.replay_anchor.time_seconds||r.window_seconds[1]<r.replay_anchor.time_seconds||r.window_seconds[1]-r.window_seconds[0]>300||
      r.recording_seconds_remaining!==analysis.duration_seconds-r.replay_anchor.time_seconds||
      ![r.title,r.recorded,r.question,r.selection_reason].every(v=>typeof v==='string'&&v.length>0&&v.length<=4000))return null;
   if(r.source_kind==='gameplay'){
    const source=g.candidates.find(c=>c.id===r.id)!;
    if(JSON.stringify(source.window_seconds)!==JSON.stringify(r.window_seconds)||source.causal_claim!==false||source.battle_outcome!=='unknown'||source.validated_state_measurements.length!==0||source.event_ids.some(id=>events.get(id)?.player_id!==player.id)||JSON.stringify(source.source)!==JSON.stringify(r.source_signature))return null;
   }else if(r.source_signature!==null||JSON.stringify(s.episodes?.find(e=>e.id===s.recommendations.find(c=>c.id===r.id)?.episode_id)?.window_seconds??[r.replay_anchor.time_seconds,r.replay_anchor.time_seconds])!==JSON.stringify(r.window_seconds))return null;
   if(r.practice_id!==null){
    const suggestion=p.suggestions.find(x=>x.id===r.practice_id);
    if(r.practice_id!==r.id||!suggestion||suggestion.action!==c.practice_short||!t.practice_ids.includes(r.practice_id)||![suggestion.label,suggestion.when,suggestion.action,suggestion.adapt].every(v=>typeof v==='string'&&v.length<=2000))return null;
   }
  }
  for(const positive of t.positives){
   if(typeof positive.id!=='string'||!/^keep:[a-f0-9]{24}$/.test(positive.id)||!['protective_input','prompt_followup','age_lead'].includes(positive.kind)||!Array.isArray(positive.event_ids)||!positive.event_ids.length||positive.event_ids.length>2||!unique(positive.event_ids)||positive.event_ids.some(id=>!events.has(id))||events.get(positive.event_ids[0])?.player_id!==player.id||![positive.text,positive.caveat,positive.derivation].every(v=>typeof v==='string'&&v.length>0&&v.length<=2000))return null;
   const refs=positive.event_ids.map(id=>events.get(id)!);
   if(positive.kind==='age_lead'){
    const opponent=analysis.players.find(p=>p.id===refs[1]?.player_id);
    if(analysis.players.length!==2||refs.length!==2||refs.some(e=>e.action!=='AGE_REACHED'||e.status!=='observed_milestone'||e.technology!=='Castle Age')||!opponent||opponent.id===player.id||refs[1].time_seconds<=refs[0].time_seconds||!player.team_id||!opponent.team_id||JSON.stringify(Array.isArray(player.team_id)?[...new Set(player.team_id)].sort((a,b)=>a-b):player.team_id)===JSON.stringify(Array.isArray(opponent.team_id)?[...new Set(opponent.team_id)].sort((a,b)=>a-b):opponent.team_id))return null;
    if(Array.isArray(player.team_id)!==Array.isArray(opponent.team_id))return null;
    if(Array.isArray(player.team_id)){
     if(JSON.stringify(player.team_id)!==JSON.stringify([player.id])||JSON.stringify(opponent.team_id)!==JSON.stringify([opponent.id]))return null;
    }else if(!Number.isInteger(player.team_id)||!Number.isInteger(opponent.team_id)||Number(player.team_id)<=0||Number(opponent.team_id)<=0)return null;
   }else if(positive.kind==='protective_input'){
    if(refs.length!==1||refs[0].status!=='command'||refs[0].order!=='Garrison'||!s.incidents.some(i=>i.responses.some(r=>r.event_id===refs[0].id)))return null;
   }else if(refs.length!==2||refs.some(e=>e.player_id!==player.id)||refs[0].action!=='AGE_REACHED'||refs[0].status!=='observed_milestone'||!['Castle Age','Imperial Age'].includes(refs[0].technology??'')||refs[1].kind!=='queue_command'||!['QUEUE','DE_QUEUE'].includes(refs[1].action)||refs[1].status!=='command'||refs[1].time_seconds<refs[0].time_seconds||refs[1].time_seconds-refs[0].time_seconds>30)return null;
  }
  const main=t.revisits.find(r=>r.id===t.primary_revisit_id);
  if((t.revisits.length>0)!==!!main||(t.positives.length>0)!==t.positives.some(p=>p.id===t.primary_positive_id)||
     (!main&&t.primary_revisit_id!==null)||(!t.positives.length&&t.primary_positive_id!==null)||
     t.primary_practice_id!==(main?.practice_id??null)||t.practice_ids.some(id=>!t.revisits.some(r=>r.practice_id===id)))return null;
  return t;
 }catch{return null;}
}

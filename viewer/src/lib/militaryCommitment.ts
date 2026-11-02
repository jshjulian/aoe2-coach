import type { PythonAnalysis } from './coachAnalysis';

export const CONSTRAINT_IDS=['resource_setup','resource_access','funding_population','production_lost','units_lost','threat_changed','deliberate_mix','deliberate_small','other','uncertain','not_applicable'];
export const INTENT_IDS=['defend_resources','clear_pressure','raid','pressure_buildings','reinforce_push','hold_for_age','other','uncertain'];
export type CommitmentContext={
  schema_version:1;status:'available';match_id:string;player:{id:number;name:string;civilization:string};
  causal_claim:false;ai_enabled:false;eligible_for_automatic_priority:false;eligible_for_progress:false;
  source_binding:{content_sha256:string;normalizer_schema:5;analysis_generator_identity:null;engine_sha256:string;provenance:Record<string,unknown>};
  constraint_choices:Array<{id:string;label:string}>;intent_choices:Array<{id:string;label:string}>;
  coverage:{truncated:boolean;eligible_window_count:number;unknown_military_inputs:number;selection:string};
  limitations:string[];reason:string|null;windows:CommitmentWindow[];
};
export type CommitmentWindow={
  id:string;kind:'new_line'|'opening';title:string;question:string;window_seconds:[number,number];
  replay_anchor:{event_id:string;time_seconds:number};event_ids:string[];evidence_sha256:string;
  evidence:Array<{event_id:string;time_seconds:number;player_id:number;information:string}>;
  options:Array<{id:string;title:string;question:string}>;practice_cue:string;assessment:string;
  information:{resources:null;resource_access:null;fielded_units:null;completed_production:null;player_vision:null};
  reviewed_context:{status:'unanswered'|'reviewed'|'unavailable';revision:number;constraint:string|null;intent:string|null;note:string;eligible_for_measurements:false;provenance:'player_account_not_measured_state';binding?:Record<string,unknown>};
};
type Obj=Record<string,unknown>;
const obj=(v:unknown):v is Obj=>!!v&&typeof v==='object'&&!Array.isArray(v);
const text=(v:unknown,n=2000):v is string=>typeof v==='string'&&v.length<=n&&!/[\x00-\x08\x0b-\x1f]/.test(v);
const num=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const integer=(v:unknown,max=300000):v is number=>num(v)&&Number.isInteger(v)&&v>=0&&v<=max;
const hash=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const choices=(v:unknown,ids:string[])=>Array.isArray(v)&&v.length===ids.length&&new Set(v.map(c=>obj(c)?c.id:null)).size===ids.length&&v.every(c=>obj(c)&&typeof c.id==='string'&&ids.includes(c.id)&&text(c.label,200));

/** Fail closed only this optional panel. No source identity is repaired or inferred. */
export function usableCommitment(value:unknown,analysis:PythonAnalysis,name:string):CommitmentContext|null{
  if(!obj(value)||value.schema_version!==1||value.status!=='available'||value.match_id!==analysis.match_id||!hash(value.match_id)||value.causal_claim!==false||value.ai_enabled!==false||value.eligible_for_automatic_priority!==false||value.eligible_for_progress!==false)return null;
  if(analysis.schema_version!==5||!num(analysis.duration_seconds)||analysis.duration_seconds<=0||!Array.isArray(analysis.players)||analysis.players.some(p=>!p||typeof p.name!=='string'||!Number.isInteger(p.id))||!Array.isArray(analysis.events)||analysis.events.length>300000||analysis.events.some(e=>!e||typeof e.id!=='string'||!num(e.time_seconds)||e.time_seconds<0||e.time_seconds>analysis.duration_seconds))return null;
  const players=analysis.players.filter(p=>p.name===name),p=value.player,b=value.source_binding;
  if(analysis.players.length!==2||analysis.players.some(p=>typeof p.won!=='boolean')||analysis.players.filter(p=>p.won===true).length!==1)return null;
  const [left,right]=analysis.players,lt=left.team_id,rt=right.team_id;
  const opposing=Array.isArray(lt)&&Array.isArray(rt)?lt.includes(left.id)&&rt.includes(right.id)&&lt.every(v=>Number.isInteger(v)&&v>0)&&rt.every(v=>Number.isInteger(v)&&v>0)&&!lt.some(v=>rt.includes(v)):typeof lt==='number'&&typeof rt==='number'&&Number.isInteger(lt)&&Number.isInteger(rt)&&lt>0&&rt>0&&lt!==rt;
  if(!opposing)return null;
  if(players.length!==1||analysis.players.length!==2||!obj(p)||p.id!==players[0].id||p.name!==name||p.civilization!==players[0].civilization||!obj(b)||b.content_sha256!==analysis.match_id||b.normalizer_schema!==5||b.analysis_generator_identity!==null||!hash(b.engine_sha256)||!obj(b.provenance)||JSON.stringify(b.provenance)!==JSON.stringify(analysis.replay_provenance))return null;
  if(value.reason!==null&&!text(value.reason,1000))return null;
  if(!choices(value.constraint_choices,CONSTRAINT_IDS)||!choices(value.intent_choices,INTENT_IDS)||!Array.isArray(value.limitations)||value.limitations.length>8||!value.limitations.every(s=>text(s,1000))||!obj(value.coverage)||typeof value.coverage.truncated!=='boolean'||!integer(value.coverage.eligible_window_count)||!integer(value.coverage.unknown_military_inputs)||!text(value.coverage.selection)||!Array.isArray(value.windows)||value.windows.length>4)return null;
  const events=new Map(analysis.events.map(e=>[e.id,e]));if(events.size!==analysis.events.length)return null;
  const ids=new Set<string>();
  for(const c of value.windows){
    if(!obj(c)||typeof c.id!=='string'||!/^commitment:[a-f0-9]{24}$/.test(c.id)||ids.has(c.id)||!['new_line','opening'].includes(String(c.kind))||!text(c.title,200)||!text(c.question,500)||!text(c.assessment)||!text(c.practice_cue,500)||!hash(c.evidence_sha256))return null;
    ids.add(c.id);
    if(!Array.isArray(c.window_seconds)||c.window_seconds.length!==2||!c.window_seconds.every(num)||c.window_seconds[0]<0||c.window_seconds[1]>analysis.duration_seconds||c.window_seconds[1]<c.window_seconds[0]||!obj(c.replay_anchor)||typeof c.replay_anchor.event_id!=='string'||!num(c.replay_anchor.time_seconds))return null;
    const anchor=events.get(c.replay_anchor.event_id);if(!anchor||anchor.player_id!==p.id||anchor.time_seconds!==c.replay_anchor.time_seconds||anchor.time_seconds<c.window_seconds[0]||anchor.time_seconds>c.window_seconds[1])return null;
    if(!Array.isArray(c.event_ids)||!c.event_ids.length||c.event_ids.length>48||!c.event_ids.includes(anchor.id)||new Set(c.event_ids).size!==c.event_ids.length||!Array.isArray(c.evidence)||c.evidence.length!==c.event_ids.length)return null;
    for(let i=0;i<c.event_ids.length;i++){
      const id=c.event_ids[i],ref=c.evidence[i];if(typeof id!=='string'||!obj(ref))return null;
      const event=events.get(id);
      if(!event||!(['unit','building','technology','order'] as const).every(k=>event[k]==null||text(event[k],160))||event.status!=='command'||!(['DE_QUEUE','QUEUE','BUILD','RESEARCH','WALL'].includes(event.action)||event.order==='Garrison')||ref.event_id!==id||ref.time_seconds!==event.time_seconds||ref.player_id!==event.player_id||event.time_seconds<c.window_seconds[0]||event.time_seconds>c.window_seconds[1]||event.player!==analysis.players.find(actor=>actor.id===event.player_id)?.name||ref.information!==(event.player_id===p.id?'own_recorded_input':'retrospective_opponent_input_not_player_vision'))return null;
    }
    const optionIds=['keep','support','switch','disengage'];
    if(!Array.isArray(c.options)||c.options.length!==4||new Set(c.options.map(o=>obj(o)?o.id:null)).size!==4||!c.options.every(o=>obj(o)&&optionIds.includes(String(o.id))&&text(o.title,100)&&text(o.question,500)))return null;
    const information=c.information;
    if(!obj(information)||!['resources','resource_access','fielded_units','completed_production','player_vision'].every(k=>information[k]===null))return null;
    const r=c.reviewed_context;
    if(!obj(r)||!['unanswered','reviewed','unavailable'].includes(String(r.status))||!integer(r.revision)||!text(r.note,1000)||r.eligible_for_measurements!==false||r.provenance!=='player_account_not_measured_state')return null;
    if(r.status==='reviewed'){
      if(!r.revision||!CONSTRAINT_IDS.includes(String(r.constraint))||!INTENT_IDS.includes(String(r.intent))||!obj(r.binding)||r.binding.match_id!==analysis.match_id||r.binding.situation_id!==c.id||r.binding.question_id!=='military-commitment-v1'||r.binding.evidence_sha256!==c.evidence_sha256||JSON.stringify(r.binding.player)!==JSON.stringify(p)||JSON.stringify(r.binding.source_binding)!==JSON.stringify(b)||JSON.stringify(r.binding.event_ids)!==JSON.stringify(c.event_ids)||JSON.stringify(r.binding.window_seconds)!==JSON.stringify(c.window_seconds))return null;
    }else if(r.revision!==0||r.constraint!==null||r.intent!==null||r.note!=='')return null;
  }
  return value as unknown as CommitmentContext;
}

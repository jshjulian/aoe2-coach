import type {AnalysisEvent,PythonAnalysis} from './coachAnalysis';
import {FRANKS_GUIDES,GENERAL_GUIDE,REFERENCE_BUILD,type Guide} from './matchupGuideData';
export type QueueSummary={label:string;inputs:number;missingQuantity:number;first:AnalysisEvent};
export type GuideBoard={guide:Guide;own:PythonAnalysis['players'][number];opponent:PythonAnalysis['players'][number];ownQueues:QueueSummary[];opponentQueues:QueueSummary[];unknownMilitary:number;patch:'same_reference_build'|'different_build'|'unknown_build';build:number|null;specialized:boolean};
// Explicit namespace/name pairs. Serjeant variants are distinct reference tree nodes,
// not guessed shifts or an attribution to their actual producer.
const units=new Map<number,string>([
 [74,'Militia'],[75,'Man-at-Arms'],[77,'Long Swordsman'],[473,'Two-Handed Swordsman'],[567,'Champion'],
 [93,'Spearman'],[358,'Pikeman'],[359,'Halberdier'],[4,'Archer'],[24,'Crossbowman'],[492,'Arbalester'],
 [7,'Skirmisher'],[6,'Elite Skirmisher'],[448,'Scout Cavalry'],[546,'Light Cavalry'],[441,'Hussar'],
 [38,'Knight'],[283,'Cavalier'],[569,'Paladin'],[329,'Camel Rider'],[330,'Heavy Camel Rider'],
 [279,'Scorpion'],[542,'Heavy Scorpion'],[280,'Mangonel'],[550,'Onager'],[588,'Siege Onager'],
 [35,'Battering Ram'],[422,'Capped Ram'],[548,'Siege Ram'],[125,'Monk'],[5,'Hand Cannoneer'],
 [1658,'Serjeant'],[1660,'Serjeant'],[1659,'Elite Serjeant'],[1661,'Elite Serjeant'],
 [8,'Longbowman'],[530,'Elite Longbowman'],[41,'Huskarl'],[555,'Elite Huskarl']
]);
export function guideQueueLabel(e:AnalysisEvent):string|null {
 if(e.kind!=='queue_command'||e.status!=='command'||!['DE_QUEUE','QUEUE'].includes(e.action)||e.amount!=null&&(!Number.isInteger(e.amount)||e.amount<=0||e.amount>32767))return null;
 const label=typeof e.unit_type_id==='number'?units.get(e.unit_type_id):undefined;
 return label&&label===e.unit?label:null;
}
const validText=(v:unknown):v is string=>typeof v==='string'&&v.length>0&&v.length<=160&&!/[\x00-\x1f]/.test(v);
function opposing(a:PythonAnalysis['players'][number],b:PythonAnalysis['players'][number]){
 const x=a.team_id,y=b.team_id;
 if(Array.isArray(x)&&Array.isArray(y))return x.includes(a.id)&&y.includes(b.id)&&x.every(v=>Number.isInteger(v)&&v>0)&&y.every(v=>Number.isInteger(v)&&v>0)&&!x.some(v=>y.includes(v));
 return typeof x==='number'&&typeof y==='number'&&Number.isInteger(x)&&Number.isInteger(y)&&x>0&&y>0&&x!==y;
}
/** An educational reference board, never a recommendation/priority/state packet. */
export function buildGuideBoard(analysis:PythonAnalysis,name:string):GuideBoard|null{
 if(!analysis||analysis.schema_version!==5||!/^[a-f0-9]{64}$/.test(analysis.match_id)||!Number.isFinite(analysis.duration_seconds)||analysis.duration_seconds<=0||analysis.duration_seconds>86400||!Array.isArray(analysis.players)||analysis.players.length!==2||!Array.isArray(analysis.events)||analysis.events.length>300000)return null;
 const players=analysis.players;
 if(players.some(p=>!p||!Number.isInteger(p.id)||p.id<=0||!validText(p.name)||!validText(p.civilization)||typeof p.won!=='boolean')||players[0].id===players[1].id||players.filter(p=>p.won===true).length!==1||!opposing(players[0],players[1]))return null;
 const own=players.filter(p=>p.name===name);if(own.length!==1)return null;
 const opponent=players.find(p=>p.id!==own[0].id)!;
 const prov=analysis.replay_provenance as unknown as Record<string,unknown>|undefined;
 if(!prov||prov.provenance_version!==2||prov.edition!=='DE'||prov.dataset_id!==100||prov.game_type_id!==0||prov.all_technologies!==false||prov.cheats!==false||prov.metadata_cheats===true||prov.de_cheats===true)return null;
 if(prov.reported_mod!=null&&prov.reported_mod!==''&&!(Array.isArray(prov.reported_mod)&&prov.reported_mod.length===0)&&!(typeof prov.reported_mod==='object'&&Object.keys(prov.reported_mod).length===0))return null;
 if(prov.rms_mod_id!=null&&prov.rms_mod_id!==0&&prov.rms_mod_id!=='')return null;
 const ids=new Set<string>(),groups=new Map<number,Map<string,QueueSummary>>();let unknownMilitary=0;
 for(const e of analysis.events){
  if(!e||!validText(e.id)||ids.has(e.id)||typeof e.time_seconds!=='number'||!Number.isFinite(e.time_seconds)||e.time_seconds<0||e.time_seconds>analysis.duration_seconds||!Number.isInteger(e.player_id)||!players.some(p=>p.id===e.player_id&&p.name===e.player))return null;
  ids.add(e.id);
  if(e.kind!=='queue_command'||e.status!=='command'||!['DE_QUEUE','QUEUE'].includes(e.action))continue;
  if(e.amount!=null&&(!Number.isInteger(e.amount)||e.amount<=0||e.amount>32767))continue;
  const label=typeof e.unit_type_id==='number'?units.get(e.unit_type_id):undefined;
  if(!label||label!==e.unit){if(e.category==='military')unknownMilitary++;continue;}
  let group=groups.get(e.player_id!);if(!group){group=new Map();groups.set(e.player_id!,group);}
  const row=group.get(label);
  if(row){row.inputs++;if(e.amount==null)row.missingQuantity++;if(e.time_seconds<row.first.time_seconds||(e.time_seconds===row.first.time_seconds&&e.id<row.first.id))row.first=e;}
  else group.set(label,{label,inputs:1,missingQuantity:e.amount==null?1:0,first:e});
 }
 const summarize=(id:number)=>[...(groups.get(id)?.values()??[])].sort((a,b)=>b.inputs-a.inputs||a.first.time_seconds-b.first.time_seconds||a.label.localeCompare(b.label)).slice(0,3);
 const specialized=own[0].civilization==='Franks'&&Object.hasOwn(FRANKS_GUIDES,opponent.civilization);
 const build=typeof prov.build_version==='number'&&Number.isInteger(prov.build_version)&&prov.build_version>0?prov.build_version:null;
 return {guide:specialized?FRANKS_GUIDES[opponent.civilization]:GENERAL_GUIDE,own:own[0],opponent,ownQueues:summarize(own[0].id),opponentQueues:summarize(opponent.id),unknownMilitary,patch:build===null?'unknown_build':build===REFERENCE_BUILD?'same_reference_build':'different_build',build,specialized};
}

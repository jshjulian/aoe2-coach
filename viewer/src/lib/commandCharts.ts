import type {AnalysisEvent,PythonAnalysis} from './coachAnalysis';

export const CHART_VERSION=1;
export const ROLES=['Cavalry','Infantry','Archers','Siege','Monks','Other / unclassified'] as const;
export const COLORS=['#e8ad52','#54b9c3','#c879d2','#7fa7ef','#77bf89','#d58275','#b2a177','#9e94da'].map((fallback,i)=>`var(--queue-series-${i},${fallback})`);
const civilian=new Set(['Villager','Fishing Ship','Trade Cart','Trade Cog']);
// Presentation categories only, not a counter model or proof of current unit type.
const known:Record<string,[number,string]>={
 'Scout Cavalry':[448,'Cavalry'],'Light Cavalry':[546,'Cavalry'],'Hussar':[441,'Cavalry'],'Knight':[38,'Cavalry'],'Cavalier':[283,'Cavalry'],'Paladin':[569,'Cavalry'],
 'Militia':[74,'Infantry'],'Man-at-Arms':[75,'Infantry'],'Long Swordsman':[77,'Infantry'],'Two-Handed Swordsman':[473,'Infantry'],'Champion':[567,'Infantry'],'Spearman':[93,'Infantry'],'Pikeman':[358,'Infantry'],'Halberdier':[359,'Infantry'],
 'Archer':[4,'Archers'],'Crossbowman':[24,'Archers'],'Arbalester':[492,'Archers'],'Skirmisher':[7,'Archers'],'Elite Skirmisher':[6,'Archers'],
 'Throwing Axeman':[281,'Infantry'],'Steppe Lancer':[1370,'Cavalry'],'Mangudai':[11,'Archers'],
 'Battering Ram':[1258,'Siege'],'Mangonel':[280,'Siege'],'Scorpion':[279,'Siege'],'Trebuchet':[331,'Siege'],'Monk':[125,'Monks'],
};
export interface QueueRow {key:string;label:string;role:string;commands:number;knownQuantity:number;quantityInputs:number;unknownQuantity:number;multiBuilding:number;events:AnalysisEvent[];unclassified:boolean}
export interface Gap {from:AnalysisEvent;to:AnalysisEvent;seconds:number;research:AnalysisEvent[]}
export interface PlayerCommands {id:number;name:string;civilization:string;color:string;military:AnalysisEvent[];villagers:AnalysisEvent[];cancels:AnalysisEvent[];research:AnalysisEvent[];ages:AnalysisEvent[];tcPlacements:AnalysisEvent[];initialTCIds:number[];gaps:Gap[]}
export interface ChartModel {version:number;matchId:string;duration:number;players:PlayerCommands[];events:Map<string,AnalysisEvent>;ambiguousAges:boolean;ignoredQueueInputs:number}
export interface Bin {start:number;end:number;events:AnalysisEvent[];military:AnalysisEvent[];villagers:AnalysisEvent[];cancels:AnalysisEvent[];cumulativeVillagers:number;rollingVillagers:number}
export interface PlayerWindow {player:PlayerCommands;military:AnalysisEvent[];villagers:AnalysisEvent[];cancels:AnalysisEvent[];rows:QueueRow[];bins:Bin[];gaps:Gap[];unitRowsTruncated:boolean}
export interface ChartWindow {start:number;end:number;binSeconds:number;players:PlayerWindow[]}
export const clock=(s:number)=>`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;
const finite=(n:unknown):n is number=>typeof n==='number'&&Number.isFinite(n);
const quantity=(e:AnalysisEvent)=>finite(e.amount)&&Number.isSafeInteger(e.amount)&&e.amount>0&&e.amount<=32767?e.amount:null;
const queued=(e:AnalysisEvent)=>e.status==='command'&&e.kind==='queue_command'&&['DE_QUEUE','QUEUE'].includes(e.action);
const cancelled=(e:AnalysisEvent)=>e.status==='command'&&(e.kind==='queue_cancel_command'||['DE_QUEUE','QUEUE'].includes(e.action)&&finite(e.amount)&&e.amount<0||e.action==='SPECIAL'&&['unqueue','cancel'].includes((e.order??'').toLowerCase()));
const inWindow=(e:AnalysisEvent,start:number,end:number,duration:number)=>e.time_seconds>=start&&(e.time_seconds<end||end===duration&&e.time_seconds<=end);
function label(e:AnalysisEvent){return e.unit?.trim()||`Unknown unit${e.unit_type_id!=null?` #${e.unit_type_id}`:''}`;}
export function roleOf(e:AnalysisEvent){const r=known[e.unit??''];return r&&e.unit_type_id===r[0]?r[1]:'Other / unclassified';}

/** Derived locally from original events only. No store, network, model, queue simulation or state inference. */
export function buildCommandCharts(a:PythonAnalysis):ChartModel|null {
 try{
  if(a.schema_version!==5||!/^[0-9a-f]{64}$/.test(a.match_id)||!finite(a.duration_seconds)||a.duration_seconds<=0||a.duration_seconds>604800||!Array.isArray(a.events)||a.events.length>300000||!Array.isArray(a.players)||!a.players.length||a.players.length>8||new Set(a.players.map(p=>p.id)).size!==a.players.length)return null;
  const players:PlayerCommands[]=a.players.map((p,i)=>({id:p.id,name:p.name,civilization:p.civilization,color:COLORS[i],military:[],villagers:[],cancels:[],research:[],ages:[],tcPlacements:[],initialTCIds:[],gaps:[]}));
  if(players.some(p=>!Number.isInteger(p.id)||typeof p.name!=='string'||!p.name||p.name.length>256||typeof p.civilization!=='string'||p.civilization.length>256))return null;
  const byPlayer=new Map(players.map(p=>[p.id,p])),events=new Map<string,AnalysisEvent>();let ignoredQueueInputs=0;
  for(const tc of a.initial_town_centers??[]){const p=byPlayer.get(tc.player_id);if(p&&tc.status==='verified_initial_snapshot'&&Array.isArray(tc.object_ids))p.initialTCIds.push(...tc.object_ids.filter(id=>Number.isInteger(id)&&id>=0));}
  for(const e of a.events){
   if(!e||typeof e.id!=='string'||!e.id||events.has(e.id)||!finite(e.time_seconds)||e.time_seconds<0||e.time_seconds>a.duration_seconds)return null;
   if(['unit','technology','building','order','action','kind','status'].some(k=>{const v=e[k as keyof AnalysisEvent];return v!=null&&(typeof v!=='string'||v.length>256);})||e.object_ids!=null&&(!Array.isArray(e.object_ids)||e.object_ids.length>1000||e.object_ids.some(id=>!Number.isSafeInteger(id))))return null;
   if(e.player_id!=null&&!Number.isInteger(e.player_id)||['unit_type_id','technology_id'].some(k=>{const v=e[k as keyof AnalysisEvent];return v!=null&&!Number.isSafeInteger(v);}))return null;
   events.set(e.id,e);const p=byPlayer.get(e.player_id??-1);if(!p)continue;
   if(e.player!=null&&e.player!==p.name)return null;
   if(cancelled(e)){p.cancels.push(e);continue;}
   if(queued(e)){
    if(e.amount!==null&&e.amount!==undefined&&quantity(e)===null){ignoredQueueInputs++;continue;}
    if(e.unit==='Villager')p.villagers.push(e);
    else if(!civilian.has(e.unit??'')&&e.category==='military')p.military.push(e);
   }
   if(e.status==='command'&&e.action==='RESEARCH')p.research.push(e);
   if(e.status==='observed_milestone'&&e.action==='AGE_REACHED'&&['Feudal Age','Castle Age','Imperial Age'].includes(e.technology??''))p.ages.push(e);
   if(e.status==='command'&&e.action==='BUILD'&&e.building==='Town Center')p.tcPlacements.push(e);
  }
  let ambiguousAges=false;
  for(const p of players){
   for(const rows of [p.military,p.villagers,p.cancels,p.research,p.ages,p.tcPlacements])rows.sort((a,b)=>a.time_seconds-b.time_seconds||a.id.localeCompare(b.id));
   const names=p.ages.map(e=>e.technology),rank=['Feudal Age','Castle Age','Imperial Age'];
   if(new Set(names).size!==names.length||p.ages.some((e,i)=>i>0&&(rank.indexOf(e.technology!)<=rank.indexOf(p.ages[i-1].technology!)||e.time_seconds<=p.ages[i-1].time_seconds)))ambiguousAges=true;
   const ids=new Set(p.initialTCIds);p.initialTCIds=[...ids];
   const q=p.villagers.filter(e=>e.object_ids?.some(id=>ids.has(id))),r=p.research.filter(e=>e.object_ids?.some(id=>ids.has(id)));
   let ri=0;
   for(let i=1;i<q.length;i++){
    const from=q[i-1],to=q[i],seconds=to.time_seconds-from.time_seconds;
    if(seconds<20)continue;
    while(ri<r.length&&r[ri].time_seconds<from.time_seconds)ri++;
    const research=[];for(let j=ri;j<r.length&&r[j].time_seconds<=to.time_seconds;j++)research.push(r[j]);
    p.gaps.push({from,to,seconds,research});
   }
  }
  return {version:CHART_VERSION,matchId:a.match_id,duration:a.duration_seconds,players,events,ambiguousAges,ignoredQueueInputs};
 }catch{return null;}
}

export function commandWindow(m:ChartModel,start=0,end=m.duration):ChartWindow {
 if(!finite(start)||!finite(end)||start<0||end>m.duration||start>=end)throw new Error('Invalid chart window.');
 const binSeconds=Math.max(60,Math.ceil((end-start)/120/60)*60),n=Math.ceil((end-start)/binSeconds);
 return {start,end,binSeconds,players:m.players.map(player=>{
  const military=player.military.filter(e=>inWindow(e,start,end,m.duration)),villagers=player.villagers.filter(e=>inWindow(e,start,end,m.duration)),cancels=player.cancels.filter(e=>inWindow(e,start,end,m.duration));
  const groups=new Map<string,QueueRow>();
  for(const e of military){const name=label(e),key=JSON.stringify([name,e.unit_type_id??null]);let row=groups.get(key);
   if(!row){const role=roleOf(e);row={key,label:name,role,commands:0,knownQuantity:0,quantityInputs:0,unknownQuantity:0,multiBuilding:0,events:[],unclassified:role==='Other / unclassified'};groups.set(key,row);}
   row.commands++;row.events.push(e);const q=quantity(e);if(q===null)row.unknownQuantity++;else{row.knownQuantity+=q;row.quantityInputs++;}if((e.object_ids?.length??0)>1)row.multiBuilding++;
  }
  const allRows=[...groups.values()].sort((a,b)=>b.commands-a.commands||a.key.localeCompare(b.key));
  const bins:Bin[]=Array.from({length:n},(_,i)=>({start:start+i*binSeconds,end:Math.min(end,start+(i+1)*binSeconds),events:[],military:[],villagers:[],cancels:[],cumulativeVillagers:0,rollingVillagers:0}));
  const bi=(e:AnalysisEvent)=>Math.min(n-1,Math.floor((e.time_seconds-start)/binSeconds));
  for(const [list,key] of [[military,'military'],[villagers,'villagers'],[cancels,'cancels']] as const)for(const e of list)bins[bi(e)][key].push(e);
  for(const e of [...military,...cancels,...player.research,...player.ages])if(inWindow(e,start,end,m.duration))bins[bi(e)].events.push(e);
  let cumulative=0,lo=0,hi=0;
  for(const b of bins){
   cumulative+=b.villagers.length;b.cumulativeVillagers=cumulative;
   while(hi<player.villagers.length&&player.villagers[hi].time_seconds<=b.end)hi++;
   while(lo<hi&&player.villagers[lo].time_seconds<=b.end-180)lo++;
   b.rollingVillagers=hi-lo;
   b.events.sort((a,b)=>a.time_seconds-b.time_seconds||a.id.localeCompare(b.id));
  }
  return {player,military,villagers,cancels,rows:allRows.slice(0,80),unitRowsTruncated:allRows.length>80,bins,gaps:player.gaps.filter(g=>g.to.time_seconds>start&&g.from.time_seconds<end)};
 })};
}

export interface TechRow {key:string;label:string;requests:Map<number,AnalysisEvent[]>}
export function technologyRows(m:ChartModel):{rows:TechRow[];truncated:boolean} {
 const map=new Map<string,TechRow>();
 for(const p of m.players)for(const e of p.research){const label=e.technology||`Unknown technology${e.technology_id!=null?` #${e.technology_id}`:''}`,key=JSON.stringify([label,e.technology_id??null]);let r=map.get(key);if(!r){r={key,label,requests:new Map()};map.set(key,r);}const es=r.requests.get(p.id)??[];es.push(e);r.requests.set(p.id,es);}
 const all=[...map.values()].sort((a,b)=>a.label.localeCompare(b.label)||a.key.localeCompare(b.key));return {rows:all.slice(0,128),truncated:all.length>128};
}

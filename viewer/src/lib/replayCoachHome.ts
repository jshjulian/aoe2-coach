import type {AnalysisEvent,PythonAnalysis} from './coachAnalysis';
import type {CoachingResponse} from './coachingReview';
import {buildGuideBoard,guideQueueLabel} from './matchupGuide';
import {usableComposition,type CompositionPacket} from './armyComposition';
import {usableTakeaway} from './balancedTakeaway';
import {usableReasoning} from './militaryReasoning';

export type HomeMoment={id:string;title:string;why:string;action:string;anchor:AnalysisEvent;sources:AnalysisEvent[];kind:'opening'|'castle'|'mix'|'review'};
export type ArmyPlan={title:string;stage:string;context:string;jobs:string[];prepare:string[];watch:string;source:AnalysisEvent|null;named:boolean};
export type ReplayHome={moments:HomeMoment[];plan:ArmyPlan;style:{title:string;action:string};preparation:{title:string;action:string;check:string;sources:AnalysisEvent[]};opponent:string;unknownMilitary:number;referenceBuild:number|null;patchMismatch:boolean;selection:string};
export const homeTime=(t:number)=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
const cavalry=new Set([448,546,441,38,283,569]);
const spear=new Set([93,358,359]);
const infantry=new Set([74,75,77,473,567,1658,1659,1660,1661,41,555]);
const production=new Set(['Stable','Archery Range','Barracks','Monastery','Siege Workshop','Blacksmith','Mining Camp','Lumber Camp']);
const label=(s:unknown):s is string=>typeof s==='string'&&s.length>0&&s.length<=160&&!/[\x00-\x1f]/.test(s);
const unique=(es:AnalysisEvent[],limit=12)=>[...new Map(es.map(e=>[e.id,e])).values()].sort((a,b)=>a.time_seconds-b.time_seconds||a.id.localeCompare(b.id)).slice(0,limit);
const withAnchor=(anchor:AnalysisEvent,es:AnalysisEvent[])=>unique([...unique(es.filter(e=>e.id!==anchor.id),11),anchor]);
export function homeStatement(e:AnalysisEvent):string {
 if(e.action==='AGE_REACHED'&&e.status==='observed_milestone')return `${e.technology} reached`;
 if(e.kind==='building_placement_command')return `${e.building} placement requested`;
 if(e.kind==='research_command')return `${e.technology} research requested`;
 if(e.kind==='queue_command'&&e.status==='command')return `${label(e.unit)?e.unit:'Unit'} production requested`;
 if(e.kind==='wall_placement_command'&&e.status==='command')return 'Wall placement requested';
 if(e.status==='command'&&label(e.order))return `${e.order} order requested`;
 return `Recorded ${label(e.action)?e.action:'event'}${label(e.order)?` · ${e.order}`:''}`;
}
function role(id:number):string|null {
 if(cavalry.has(id))return 'cavalry';if(spear.has(id))return 'spear';if(infantry.has(id))return 'infantry';
 if([4,24,492,5,8,530].includes(id))return 'ranged';if([7,6].includes(id))return 'anti_ranged';if([329,330].includes(id))return 'camel';if(id===125)return 'conversion';if([279,542,280,550,588,35,422,548].includes(id))return 'siege';return null;
}
/** Presentation-only editorial synthesis. No writes, score, main-review reranking or state reconstruction. */
export function buildReplayHome(a:PythonAnalysis,name:string,response?:CoachingResponse|null):ReplayHome|null {
 const board=buildGuideBoard(a,name);if(!board)return null;
 let packet:CompositionPacket|null=null;
 try{packet=usableComposition(response?.composition_context,a,name);}catch{/* Malformed optional context cannot remove command moments. */}
 const registry=new Map(packet?.units.map(u=>[u.unit_id,u])??[]);
 const queue=(e:AnalysisEvent)=>{
  if(guideQueueLabel(e))return true;
  const u=registry.get(e.unit_type_id!);
  return !!u&&u.name===e.unit&&e.kind==='queue_command'&&e.status==='command'&&['QUEUE','DE_QUEUE'].includes(e.action)&&(e.amount==null||Number.isInteger(e.amount)&&e.amount>0&&e.amount<=32767);
 };
 const ordered=[...a.events].sort((x,y)=>x.time_seconds-y.time_seconds||x.id.localeCompare(y.id));
 const own=ordered.filter(e=>e.player_id===board.own.id),enemy=ordered.filter(e=>e.player_id===board.opponent.id);
 const ownQueues=own.filter(queue),enemyQueues=enemy.filter(queue);
 const ownRole=(e:AnalysisEvent)=>registry.get(e.unit_type_id!)?.role??role(e.unit_type_id!);
 const age=(name:string)=>{const es=own.filter(e=>e.action==='AGE_REACHED'&&e.status==='observed_milestone'&&e.technology===name);return es.length===1?es[0]:null;};
 const feudal=age('Feudal Age'),castle=age('Castle Age'),imperial=age('Imperial Age');
 const prep=(e:AnalysisEvent)=>e.status==='command'&&(e.kind==='building_placement_command'&&e.action==='BUILD'&&production.has(e.building??'')||e.kind==='research_command'&&e.action==='RESEARCH'&&label(e.technology)&&Number.isInteger(e.technology_id)&&Number(e.technology_id)>0);
 const candidates:HomeMoment[]=[];
 // Lift the already validated replay primary; never use habit labels, player notes or result/rating.
 const reasoning=usableReasoning(response??null,a,name),responseMain=reasoning?.situations.find(s=>s.id===reasoning.primary_id);
 const bySourceId=new Map(a.events.map(e=>[e.id,e]));
 if(responseMain&&!['withheld_after_correction','player_correction_requires_review'].includes(responseMain.assessment.status)){
  const anchor=bySourceId.get(responseMain.replay_anchor.event_id)!;
  candidates.push({id:responseMain.id,title:`Give the ${responseMain.transition.to_unit} line a clear job`,why:`${responseMain.transition.from_unit} → ${responseMain.transition.to_unit} production requests; the new-line request is at ${homeTime(anchor.time_seconds)}. Opposing ${responseMain.threat.name} requests provide the comparison to inspect.`,action:responseMain.practice_short,anchor,sources:unique([anchor,...responseMain.transition.event_ids.map(id=>bySourceId.get(id)!),...responseMain.threat.event_ids.slice(0,2).map(id=>bySourceId.get(id)!)]),kind:'review'});
 }
 const takeaway=usableTakeaway(response,a,name),main=takeaway?.revisits.find(r=>r.id===takeaway.primary_revisit_id);
 if(main&&!candidates.some(c=>c.kind==='review')){
  const byId=new Map(a.events.map(e=>[e.id,e])),source=main.source_kind==='gameplay'?response?.gameplay_context?.candidates.find(c=>c.id===main.id):response?.situation?.recommendations.find(c=>c.id===main.id);
  const titles:Record<string,string>={siege:'Protect the next siege commitment',siege_recommitment:'Protect the next siege commitment',engagement:'Choose the fight before committing',engagement_decision:'Choose the fight before committing',early_defense:'Choose your defensive follow-through',sustainability:'Fund the next reinforcement cycle',military_sustainability:'Fund the next reinforcement cycle',production_investment:'Make the new production useful',map_control:'Secure the route before moving out',walling:'Close the access route',upgrade_transition:'Prepare the next army upgrade'};
  if(source&&typeof source.practice_short==='string'&&source.practice_short.length<=2000)candidates.push({id:main.id,title:titles[main.topic]??main.title,why:main.topic==='early_defense'?main.event_ids.slice(0,3).map(id=>{const e=byId.get(id)!;return `${homeTime(e.time_seconds)} ${e.player_id===board.own.id?'You':'Opponent'}: ${homeStatement(e)}`;}).join(' · '):main.recorded,action:source.practice_short,anchor:byId.get(main.replay_anchor.event_id)!,sources:unique(main.event_ids.map(id=>byId.get(id)!)),kind:'review'});
 }
 const first=ownQueues[0],openingAnchor=feudal??first;
 if(openingAnchor){
  const near=own.filter(e=>e.time_seconds>=Math.max(0,openingAnchor.time_seconds-120)&&e.time_seconds<=openingAnchor.time_seconds+180&&(prep(e)||queue(e))).slice(0,5);
  const opposing=enemyQueues.find(e=>e.time_seconds>=openingAnchor.time_seconds-120&&e.time_seconds<=openingAnchor.time_seconds+180);
  const scout=first&&Math.abs(first.time_seconds-openingAnchor.time_seconds)<=180&&[448,546].includes(first.unit_type_id!);
  candidates.push({id:`home:opening:${openingAnchor.id}`,title:scout?'Give your Scouts a job':'Set up your opening production',why:unique([openingAnchor,...near,...(opposing?[opposing]:[])]).map(e=>`${homeTime(e.time_seconds)} ${homeStatement(e)}${e.player_id===board.opponent.id?' (opponent)':''}`).join(' · '),action:scout?'Use Scout mobility to check the approach and pressure exposed targets. Regroup rather than chase through Spears; keep the next production cycle funded.':'Choose one opening job—defend access or apply pressure—and give that line the production and upgrades to do it.',anchor:openingAnchor,sources:unique([openingAnchor,...near,...(opposing?[opposing]:[])]),kind:'opening'});
 }
 if(castle){
  const setup=own.filter(e=>e.time_seconds>=Math.max(0,castle.time_seconds-180)&&e.time_seconds<=castle.time_seconds+180&&prep(e)).slice(-5);
  const follow=ownQueues.find(e=>e.time_seconds>=castle.time_seconds&&e.time_seconds<=castle.time_seconds+300);
  candidates.push({id:`home:castle:${castle.id}`,title:'Turn Castle Age into your next army',why:`Castle Age reached at ${homeTime(castle.time_seconds)}${follow?`; next cited military request: ${follow.unit} at ${homeTime(follow.time_seconds)}`:'. Review the production and research requests around this age-up'}.`,action:'Choose the main line before the age-up, then prepare its production, key research and safe resource access. Keep useful opening units working while the new group assembles.',anchor:castle,sources:unique([...setup,castle,...(follow?[follow]:[])]),kind:'castle'});
 }
 // Independent home context: fixed-bin/library selection must not hide the age-up's supporting mix.
 // One anchored <=300s interval only; never union early Scouts with late infantry.
 const firstGbeto=enemyQueues.find(e=>[1013,1015].includes(e.unit_type_id!));
 const castleEnemy=castle?enemyQueues.find(e=>e.time_seconds>=castle.time_seconds&&e.time_seconds<=castle.time_seconds+300):undefined;
 const contextAnchor=firstGbeto??castleEnemy??enemyQueues[0]??null;
 const start=firstGbeto?Math.max(0,firstGbeto.time_seconds-60):castleEnemy?castle!.time_seconds:contextAnchor?.time_seconds??0;
 const context=contextAnchor?{id:contextAnchor.id,window_seconds:[start,Math.min(a.duration_seconds,start+300)] as [number,number]}:null;
 const unitExamples=new Map<number,AnalysisEvent>();
 if(context)for(const e of enemyQueues)if(e.time_seconds>=context.window_seconds[0]&&e.time_seconds<=context.window_seconds[1]&&!unitExamples.has(e.unit_type_id!))unitExamples.set(e.unit_type_id!,e);
 const contextual=contextAnchor?withAnchor(contextAnchor,[...unitExamples.values()]):[];
 const threatRoles=new Set(contextual.map(ownRole).filter((v):v is string=>!!v));
 const gbetoMechanics=packet?.reference.status!=='unavailable'&&packet?.reference.profiles.some(p=>[1013,1015].includes(p.unit_id)&&p.damage_type==='melee'&&p.delivery==='ranged');
 if(context&&contextAnchor){
  const names=[...new Set(contextual.map(e=>e.unit))].join(' + ');
  candidates.push({id:`home:mix:${context.id}`,title:threatRoles.has('spear')||threatRoles.has('camel')?'Deal with the anti-cavalry support':threatRoles.has('ranged_melee')?'Protect your response to Gbeto':'Prepare for their supporting mix',why:`${homeTime(context.window_seconds[0])}–${homeTime(context.window_seconds[1])}: cited opposing ${names} production requests.`,action:threatRoles.has('spear')||threatRoles.has('camel')?'Clear or avoid the anti-cavalry screen before chasing with cavalry. Bring protected damage support and choose a route that keeps both groups together.':threatRoles.has('ranged_melee')&&gbetoMechanics?'Gbeto deals melee damage at range. Protect your damage dealers and avoid chasing into supporting units; Skirmishers are not an answer just because the target throws projectiles.':'Look at the whole supporting mix before adding another line. Give each part of your response a job and protect the reinforcement route.',anchor:contextAnchor,sources:withAnchor(contextAnchor,contextual),kind:'mix'});
 }
 const priority=[...candidates.filter(c=>c.kind==='review'),...candidates.filter(c=>c.kind==='castle'),...candidates.filter(c=>c.kind==='mix'),...candidates.filter(c=>c.kind==='opening')];
 const chosen:HomeMoment[]=[];
 for(const c of priority){if(chosen.length===3)break;if(chosen.some(p=>p.anchor.id===c.anchor.id||p.kind==='review'&&Math.abs(p.anchor.time_seconds-c.anchor.time_seconds)<90))continue;chosen.push(c);}
 const moments=chosen.sort((x,y)=>x.kind==='review'?-1:y.kind==='review'?1:x.anchor.time_seconds-y.anchor.time_seconds);
 const profiles=packet?.reference.status!=='unavailable'?packet?.reference.profiles??[]:[];
 const available=(ids:number[])=>ids.every(id=>profiles.some(p=>p.unit_id===id&&p.own_catalog_available));
 const contextText=context?`${homeTime(context.window_seconds[0])}–${homeTime(context.window_seconds[1])} opposing requests`:contextAnchor?`${homeTime(contextAnchor.time_seconds)} opposing ${contextAnchor.unit} request`:'Your recorded production';
 let plan:ArmyPlan={title:'Keep one main line; add support for its job',stage:'Plan for the next commitment',context:contextText,jobs:[first&&[448,546].includes(first.unit_type_id!)?'Scouts: check approaches, threaten exposed targets and regroup away from Spears.':'Keep the current response on one useful job: secure access, defend or apply pressure.','Add support that solves the specific screen or damage problem, rather than opening several unrelated lines.'],prepare:['Pick the main production line and its key research.','Check safe income and a protected reinforcement route.'],watch:'Review what you could actually see before choosing the response.',source:contextAnchor,named:false};
 const laterAge=!!imperial&&!!contextAnchor&&contextAnchor.time_seconds>=imperial.time_seconds;
 const feudalContext=!!feudal&&!!contextAnchor&&contextAnchor.time_seconds>=feudal.time_seconds&&!!castle&&contextAnchor.time_seconds<castle.time_seconds;
 if(feudalContext&&(threatRoles.has('spear')||threatRoles.has('infantry')||threatRoles.has('ranged_melee'))&&available([448,4])){
  plan={title:'Scouts + protected Archers',stage:'Feudal support while preparing Castle',context:contextText,jobs:['Scouts: check approaches and threaten exposed targets; avoid charging the anti-cavalry screen.','Archers: protected ranged damage to help keep infantry away from the mobile group and resource access.'],prepare:['Stable and Archery Range access, with relevant Feudal research.','Safe food for Scouts; wood and gold for Archers. Prepare the next age without leaving the ranged group exposed.'],watch:'Against Castle-age units, focus on keeping access and your existing group useful while preparing a stronger next-age response. Do not force a fight just because both support lines were started.',source:contextAnchor,named:true};
 }else if(feudalContext&&threatRoles.has('cavalry')&&available([448,93])){
  plan={title:'Scouts + a Spear screen',stage:'Feudal access defence',context:contextText,jobs:['Spears: cover vulnerable approaches and resource access.','Scouts: check routes and pressure exposed targets rather than taking a straight fight into stronger cavalry.'],prepare:['Barracks and Stable access; keep food and wood income workable.','Prepare the Castle-age follow-through and relevant research behind the screen.'],watch:'Spears guarding access and Scouts applying pressure have different jobs. Do not split the defence while chasing; Castle-age cavalry needs a stronger follow-through.',source:contextAnchor,named:true};
 }else if(laterAge&&(threatRoles.has('infantry')||threatRoles.has('ranged_melee'))&&available([5,38])){
  plan={title:'Hand Cannoneers + a cavalry screen',stage:'Imperial-age support',context:contextText,jobs:['Hand Cannoneers: protected ranged damage against infantry.','Cavalry: protect the firing group and reinforcement route; do not chase through anti-cavalry support.'],prepare:['Imperial Age, Chemistry and Archery Range access.','Safe food and gold income, a protected frontline and enough units together.'],watch:'Check enemy ranged support and siege. Keep the gunners protected while assembling the new group; do not abandon a useful existing army just to start this line.',source:contextAnchor,named:true};
 }else if(!laterAge&&!feudalContext&&(threatRoles.has('ranged_melee')||threatRoles.has('infantry')||threatRoles.has('spear')||threatRoles.has('camel'))&&available([38,24])){
  plan={title:'Knights + Crossbows',stage:'Castle-age plan',context:contextText,jobs:['Knights: hold space, threaten exposed units and intercept reinforcements.','Crossbows: supply protected damage behind the mobile group; help deal with the infantry screen.'],prepare:['Stable, Archery Range and Crossbow research.','Safe food and gold for Knights; wood and gold for ranged support.'],watch:'Do not send Knights through Spears or Camels to reach the back line. Keep the two groups connected; armour, enemy ranged support and numbers affect the fight.',source:contextAnchor,named:true};
 }else if(!laterAge&&!feudalContext&&threatRoles.has('cavalry')&&available([38,125])){
  plan={title:'Knights + protected Monks',stage:'Castle-age plan',context:contextText,jobs:['Knights: contest space and protect the support.','Monks: conversion and healing support behind the frontline.'],prepare:['Stable and Monastery access; relevant cavalry research.','Safe food and gold income; protect the Monks and reinforcement route.'],watch:'Keep Monks covered. Enemy ranged units, siege or an anti-cavalry screen can change the supporting mix you need.',source:contextAnchor,named:true};
 }else if(!laterAge&&!feudalContext&&(threatRoles.has('ranged')||threatRoles.has('mounted_ranged'))&&(contextual.length?contextual:contextAnchor?[contextAnchor]:[]).some(e=>profiles.find(p=>p.unit_id===e.unit_type_id)?.armor_classes.some(c=>c.armor_class===15))&&available([38,6])){
  plan={title:'Knights + Elite Skirmishers',stage:'Castle-age plan',context:contextText,jobs:['Knights: threaten flanks and intercept exposed reinforcements.','Elite Skirmishers: support against Archer-class ranged units from behind protection.'],prepare:['Stable and Range access; Elite Skirmisher research and relevant upgrades.','Food and gold for the cavalry; food and wood for Skirmishers.'],watch:'This Archer-class support is not a Gbeto counter by appearance. Check for enemy melee units or siege before committing.',source:contextAnchor,named:true};
 }
 const mainLine=ownQueues.find(e=>[38,24,2700,5].includes(e.unit_type_id!))??first;
 const prepAnchor=plan.source??castle??mainLine??feudal;
 const prepSources=prepAnchor?unique(own.filter(e=>e.time_seconds>=Math.max(0,prepAnchor.time_seconds-180)&&e.time_seconds<=prepAnchor.time_seconds+180&&prep(e)).slice(-5).concat(prepAnchor)):[];
 return {moments,plan,style:{title:first&&cavalry.has(first.unit_type_id!)?'Use mobility; do not chase the screen':'Give the army one job at a time',action:first&&cavalry.has(first.unit_type_id!)?'Scout the approach, threaten exposed targets and regroup. Let protected support deal with the screen before you commit the cavalry.':'Choose whether this group is securing resources, defending access or applying pressure. Add support for that job before starting another independent army line.'},preparation:{title:plan.stage.startsWith('Imperial')?'Fund the Imperial support':plan.stage.startsWith('Feudal')?'Fund the opening support':plan.stage.startsWith('Castle')?'Prepare the Castle-age spend':'Fund the next production cycle',action:plan.prepare.join(' '),check:'At this moment, check: what could you afford, which income was safe to work, and could the production and research finish safely?',sources:prepSources},opponent:board.opponent.civilization,unknownMilitary:packet?.coverage.unknown_military_inputs??board.unknownMilitary,referenceBuild:packet?.reference.status!=='unavailable'?packet?.reference.source?.declared_update??null:null,patchMismatch:board.patch!=='same_reference_build',selection:'Existing validated replay primary first, then Castle follow-through, one opposing role mix and opening; up to three moments; suppress duplicate anchors and phase moments within 90 recorded seconds of the existing primary. Editorial review coverage, not a mistake score.'};
}

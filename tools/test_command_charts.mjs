// In-memory TS compilation using the project's existing dependency. No stores or replay writes.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),ts=require('../viewer/node_modules/typescript'),Module=require('node:module'),mod=new Module('commandCharts');
mod._compile(ts.transpileModule(fs.readFileSync(new URL('../viewer/src/lib/commandCharts.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,'commandCharts.js');
const {buildCommandCharts:build,commandWindow:window,technologyRows,roleOf}=mod.exports;
let seq=0,passed=0;
const event=(overrides={})=>({id:`a${++seq}`,player_id:1,player:'A',time_seconds:10,time:'00:10',action:'DE_QUEUE',kind:'queue_command',status:'command',category:'military',unit:'Knight',unit_type_id:38,amount:1,object_ids:[100],...overrides});
const report=(events=[],overrides={})=>({schema_version:5,match_id:'a'.repeat(64),duration_seconds:600,players:[{id:1,name:'A',civilization:'Franks'},{id:2,name:'B',civilization:'Mongols'}],events,initial_town_centers:[{player_id:1,object_ids:[100,101],status:'verified_initial_snapshot'}],...overrides});
const player=a=>window(build(a)).players[0];
const test=(name,fn)=>{fn();passed++;console.log(`PASS ${name}`);};
test('counts commands separately from raw batch amounts',()=>{const p=player(report([event({amount:5}),event({amount:2})]));assert.equal(p.military.length,2);assert.equal(p.rows[0].knownQuantity,7);});
test('unknown amount remains missing, never defaulted to one',()=>{const p=player(report([event({amount:null}),event({amount:undefined})]));assert.equal(p.rows[0].commands,2);assert.equal(p.rows[0].unknownQuantity,2);assert.equal(p.rows[0].quantityInputs,0);assert.equal(p.rows[0].knownQuantity,0);});
test('multiple selected buildings do not multiply amounts',()=>{const r=player(report([event({amount:5,object_ids:[100,200,300]})])).rows[0];assert.equal(r.knownQuantity,5);assert.equal(r.multiBuilding,1);});
test('negative queue and explicit unqueue are a separate unattributed ledger',()=>{const p=player(report([event(),event({amount:-1}),event({action:'SPECIAL',kind:'queue_cancel_command',order:'Unqueue',unit:null,unit_type_id:null,amount:null})]));assert.equal(p.military.length,1);assert.equal(p.cancels.length,2);assert.equal(p.rows[0].knownQuantity,1);});
test('no net army field is derived',()=>{const m=build(report([event(),event({amount:-1})]));assert(!/alive|netUnits|efficiency|winProbability/.test(JSON.stringify(window(m))));});
test('invalid/zero quantities rejected and disclosed',()=>{const m=build(report([event({amount:0}),event({amount:1.5}),event({amount:true}),event({amount:Infinity}),event({amount:1e200})]));assert.equal(m.ignoredQueueInputs,5);assert.equal(window(m).players[0].military.length,0);});
test('civilian queues and research do not become military',()=>{const p=player(report([event({unit:'Villager',unit_type_id:83}),event({unit:'Trade Cart'}),event({action:'RESEARCH',kind:'research_command',technology:'Man-at-Arms'})]));assert.equal(p.military.length,0);assert.equal(p.villagers.length,1);assert.equal(p.player.research.length,1);});
test('actors bind by ID, mismatched labels fail closed',()=>{assert.equal(build(report([event({player:'B'})])),null);const m=build(report([event({player_id:2,player:'B'})]));assert.equal(window(m).players[0].military.length,0);assert.equal(window(m).players[1].military.length,1);});
test('unit labels need matching IDs for display-role classification',()=>{assert.equal(roleOf(event()),'Cavalry');assert.equal(roleOf(event({unit_type_id:4})),'Other / unclassified');assert.equal(roleOf(event({unit_type_id:null})),'Other / unclassified');assert.equal(roleOf(event({unit:'Camel Scout',unit_type_id:1755})),'Other / unclassified');});
test('same label with different IDs is not silently merged',()=>assert.equal(player(report([event(),event({unit_type_id:123})])).rows.length,2));
test('namespace/action guard prevents research counted as queue',()=>assert.equal(player(report([event({action:'RESEARCH',technology:'Man-at-Arms',technology_id:222})])).military.length,0));
test('windows are half-open except replay endpoint',()=>{const m=build(report([event({time_seconds:60}),event({time_seconds:600})]));assert.equal(window(m,0,60).players[0].military.length,0);assert.equal(window(m,60,600).players[0].military.length,2);});
test('invalid window rejected',()=>{const m=build(report());assert.throws(()=>window(m,60,60));assert.throws(()=>window(m,-1,600));assert.throws(()=>window(m,0,601));});
test('bins and cumulative queue counts never add starting villagers',()=>{const q=t=>event({unit:'Villager',unit_type_id:83,time_seconds:t});const p=player(report([q(30),q(60),q(600)]));assert.equal(p.bins[0].cumulativeVillagers,1);assert.equal(p.bins[1].cumulativeVillagers,2);assert.equal(p.bins.at(-1).cumulativeVillagers,3);});
test('rolling sample uses actual prior-window inputs and exact bounds',()=>{const q=t=>event({unit:'Villager',unit_type_id:83,time_seconds:t});const p=window(build(report([q(0),q(120),q(180),q(240)])),180,600).players[0];assert.equal(p.bins[0].rollingVillagers,3);assert.equal(p.bins[0].cumulativeVillagers,1);});
test('TC gaps match exact initial IDs and retain research context without subtraction',()=>{const q=(t,id)=>event({unit:'Villager',unit_type_id:83,time_seconds:t,object_ids:[id]});const r=event({time_seconds:30,action:'RESEARCH',kind:'research_command',technology:'Loom'});const p=player(report([q(10,100),r,q(60,101),q(90,25600),q(100,999)]));assert.equal(p.gaps.length,1);assert.equal(p.gaps[0].seconds,50);assert.equal(p.gaps[0].research.length,1);});
test('TC gaps omit unsupported start/end idle and later-TC capacity',()=>{const p=player(report([event({unit:'Villager',time_seconds:20}),event({action:'BUILD',kind:'build_command',building:'Town Center',time_seconds:80})]));assert.equal(p.gaps.length,0);assert.equal(p.player.tcPlacements.length,1);});
test('no initial TC IDs means gaps unavailable, not reconstructed',()=>{const p=player(report([event({unit:'Villager'}),event({unit:'Villager',time_seconds:60})],{initial_town_centers:[]}));assert.equal(p.player.initialTCIds.length,0);assert.equal(p.gaps.length,0);});
test('only observed age events become milestones; duplicates retained and flagged',()=>{const r=event({action:'RESEARCH',technology:'Feudal Age'}),a=event({action:'AGE_REACHED',status:'observed_milestone',technology:'Feudal Age'}),b=event({action:'AGE_REACHED',status:'observed_milestone',technology:'Feudal Age',time_seconds:20});const m=build(report([r,a,b]));assert.equal(m.players[0].ages.length,2);assert(m.ambiguousAges);});
test('research retries preserved; no absence-to-never inference',()=>{const q=id=>event({action:'RESEARCH',kind:'research_command',technology:'Horse Collar',technology_id:id});const rows=technologyRows(build(report([q(14),q(14),q(15)]))).rows;assert.equal(rows.length,2);assert.equal(rows[0].requests.size,1);assert.equal(rows[0].requests.get(1).length,2);assert(!rows[0].requests.has(2));});
test('duplicate source IDs, malformed scope and invalid clocks fail closed',()=>{const e=event();for(const r of [report([e,e]),report([],{match_id:'x'.repeat(64)}),report([],{schema_version:4}),report([event({time_seconds:NaN})]),report([event({time_seconds:601})]),report([],{players:[{id:1,name:'A'},{id:1,name:'B'}]})])assert.equal(build(r),null);});
test('malformed nested labels, IDs and object arrays fail closed',()=>{for(const bad of [{unit:{}},{object_ids:{}},{object_ids:[NaN]},{technology_id:true},{player_id:'1'},{order:[]},{status:{}}])assert.equal(build(report([event(bad)])),null);});
test('unit-row truncation disclosed without changing total command count',()=>{const es=Array.from({length:90},(_,i)=>event({unit:`Unit${i}`,unit_type_id:i})),p=player(report(es));assert.equal(p.rows.length,80);assert(p.unitRowsTruncated);assert.equal(p.military.length,90);});
test('technology truncation disclosed and bins bounded',()=>{const es=Array.from({length:140},(_,i)=>event({action:'RESEARCH',technology:`Tech${i}`,technology_id:i})),m=build(report(es,{duration_seconds:50000}));assert(technologyRows(m).truncated);assert.equal(technologyRows(m).rows.length,128);assert(window(m).players[0].bins.length<=120);});
test('inputs are immutable and no output depends on outcome/rating',()=>{const a=report([event()]),before=JSON.stringify(a),x=JSON.stringify(window(build(a)));assert.equal(JSON.stringify(a),before);a.players[0].won=true;a.players[0].elo_snapshot=9999;assert.equal(JSON.stringify(window(build(a))),x);});
if(process.env.CHART_LIVE_CHECK==='1'){
 // Private replay identities belong in ignored local fixtures, not Git history.
 const casesFile=process.env.CHART_LIVE_CASES_FILE || new URL('../data/development-notes/chart-live-cases.json',import.meta.url);
 assert(fs.existsSync(casesFile),'Live regression checks require a private CHART_LIVE_CASES_FILE; replay fixtures are not distributed.');
 const cases=JSON.parse(fs.readFileSync(casesFile,'utf8'));assert(Array.isArray(cases)&&cases.length<=20);
 for(const [id,expected] of cases){
  assert(typeof id==='string'&&/^[a-f0-9]{20}$/.test(id));
  const a=await(await fetch(`http://127.0.0.1:8765/api/analysis?game_id=${id}`)).json(),m=build(a);assert(m);assert.deepEqual(window(m).players.map(p=>[p.military.length,p.cancels.length]),expected);console.log(`PASS known replay read-only regression ${id}`);
 }
}
console.log(`${passed} command-chart unit tests passed.`);

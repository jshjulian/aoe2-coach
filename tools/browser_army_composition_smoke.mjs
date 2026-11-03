import assert from 'node:assert/strict';
import fs from 'node:fs';
import {mkdir,chmod} from 'node:fs/promises';
import {createRequire} from 'node:module';
process.umask(0o077);
const require=createRequire(import.meta.url),{chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright'),ts=require('../viewer/node_modules/typescript'),Module=require('node:module');
function compile(file,deps={}){const m=new Module(file);m.require=id=>deps[id];m._compile(ts.transpileModule(fs.readFileSync(`viewer/src/lib/${file}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,file);return m.exports;}
const api=process.env.ARMY_TEST_API_URL,viewer=process.env.VIEWER_URL||'http://127.0.0.1:3000';assert(api&&!['8765','8766'].includes(new URL(api).port));const get=async p=>{const r=await fetch(api+p);assert(r.ok);return r.json();};
let game,player,before;
for(let attempt=0;attempt<40&&!game;attempt++){
 const library=await get('/api/library'),candidates=library.games.filter(g=>g.status==='ready'&&g.players.length===2&&g.players.some(p=>p.civilization==='Franks')&&(!process.env.ARMY_TEST_GAME_ID||g.game_id===process.env.ARMY_TEST_GAME_ID)).sort((a,b)=>Number(b.players.some(p=>p.civilization==='Malians'))-Number(a.players.some(p=>p.civilization==='Malians'))).slice(0,12);
 for(const g of candidates){const name=g.players.find(p=>p.civilization==='Franks').name,p=await get('/api/coaching?'+new URLSearchParams({game_id:g.game_id,match_id:g.match_id,player:name}));if(p.composition_context?.status==='available'&&p.composition_context.windows.length&&p.composition_context.reference.profiles.length){game=g;player=name;before=p;break;}}
 if(!game)await new Promise(r=>setTimeout(r,300));
}
assert(game,'Needs a supported local completed Franks replay and explicitly restored pinned public reference snapshot; no runtime download.');
const query=new URLSearchParams({game_id:game.game_id,match_id:game.match_id,player}),analysis=await get(`/api/analysis?${query}`),p=before.composition_context,browser=await chromium.launch({headless:true});
try{
 const context=await browser.newContext({viewport:{width:1500,height:1100},reducedMotion:'reduce'}),errors=[],writes=[],requests=[];let corrupt=false,missing=false;
 await context.route('**/*',async route=>{
  const req=route.request(),u=new URL(req.url());if(!['127.0.0.1','localhost'].includes(u.hostname))return route.abort();requests.push(u.pathname);
  if(!u.pathname.startsWith('/api/'))return route.continue();if(!['GET','HEAD'].includes(req.method())){writes.push(u.pathname);return route.abort();}
  const headers={...req.headers()};delete headers.host;const r=await fetch(`${api}${u.pathname}${u.search}`,{headers});let body=Buffer.from(await r.arrayBuffer());
  if(u.pathname==='/api/library'){const p=JSON.parse(body);p.games=[game];p.total=1;p.counts={ready:1,queued:0,analyzing:0,error:0};body=Buffer.from(JSON.stringify(p));}
  if(u.pathname==='/api/coaching'&&(corrupt||missing)){const data=JSON.parse(body);if(corrupt)data.composition_context.fielded_army_established=true;if(missing){data.composition_context.reference.status='unavailable';data.composition_context.reference.profiles=[];data.composition_context.reference.compositions=[];}body=Buffer.from(JSON.stringify(data));}
  return route.fulfill({status:r.status,headers:Object.fromEntries(r.headers),body});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(viewer,{waitUntil:'domcontentloaded'});await page.getByRole('heading',{name:'Match review',exact:true}).first().waitFor({timeout:60000});await page.getByRole('combobox').first().selectOption(player);await page.getByTitle(game.file,{exact:true}).click();
 const section=page.locator('[data-army-composition]');await section.waitFor({timeout:60000});assert(!requests.includes('/api/replay'));assert.equal(await page.evaluate(()=>Boolean(window.__aoe2rec)),false);
 const gbetoWindow=p.windows.find(w=>w.summaries.some(s=>s.player_id===p.opponent.id&&s.roles.some(r=>r.role==='ranged_melee')))||p.windows[0];
 if(p.windows.length>1)await section.getByRole('combobox',{name:'Composition production window',exact:true}).selectOption(gbetoWindow.id);
 const select=section.getByRole('combobox',{name:'Unit mechanics reference',exact:true});await select.selectOption('1013');const unit=section.locator('[data-unit-mechanics="1013"]');assert((await unit.innerText()).includes('ranged delivery, melee damage'));assert((await unit.innerText()).includes('1.25'));assert((await section.locator('[data-mechanics-scope]').innerText()).includes('Not effective match stats'));
 await section.getByText('Compare base mobility / armour—not a fight prediction',{exact:true}).click();await section.getByRole('combobox',{name:'Compare unit mechanics',exact:true}).selectOption('38');assert((await section.innerText()).includes('does not prove it could catch'));
 await select.selectOption('125');assert((await section.locator('[data-unit-mechanics="125"]').innerText()).includes('no primary attack damage'));assert((await section.innerText()).includes('not an armour-damage formula'));await select.selectOption('1013');
 const options=gbetoWindow.composition_option_ids.filter(id=>id.startsWith('gbeto-'));for(const id of options)await section.locator(`[data-composition-option="${id}"]`).waitFor();assert((await section.innerText()).includes('neither reaction time')||(await section.innerText()).includes('no late/early verdict'));
 assert.deepEqual(await get(`/api/coaching?${query}`),before);assert.equal(writes.length,0);
 await mkdir('data/smoke',{recursive:true});
 for(const theme of ['dark','light']){if((await page.getByRole('checkbox',{name:'Dark mode'}).isChecked())!==(theme==='dark'))await page.getByText('Dark mode',{exact:true}).click();await section.evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:`data/smoke/army-composition-${theme}.png`});}
 await page.setViewportSize({width:390,height:844});await section.evaluate(e=>e.scrollIntoView({block:'start'}));await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await page.screenshot({path:'data/smoke/army-composition-mobile.png'});for(const theme of ['dark','light','mobile'])await chmod(`data/smoke/army-composition-${theme}.png`,0o600);
 const exported=compile('shareableReview',{'./teamIdentity':compile('teamIdentity')}).makeShareableReview(analysis,before,true);assert(!exported.includes(p.practice_cue));assert(!exported.includes(gbetoWindow.id));
 await page.setViewportSize({width:1500,height:1100});await section.getByText(`Inspect exact cited requests · ${gbetoWindow.event_ids.length} sources`,{exact:true}).click();const expected=analysis.events.find(e=>e.id===gbetoWindow.evidence[0].event_id);await section.locator('details').filter({has:page.getByText(`Inspect exact cited requests · ${gbetoWindow.event_ids.length} sources`,{exact:true})}).getByRole('button').first().click();const slider=page.locator('input[type="range"]').first();await slider.waitFor({timeout:60000});await page.waitForFunction(t=>Number(document.querySelector('input[type="range"]')?.max)>t,expected.time_seconds);assert(Math.abs(Number(await slider.inputValue())-expected.time_seconds)<1);await page.getByRole('button',{name:'Coach',exact:true}).click();
 missing=true;await page.reload({waitUntil:'domcontentloaded'});await section.waitFor({timeout:60000});await section.getByText('Verified local mechanics data is unavailable.',{exact:false}).waitFor();assert.equal(await section.locator('[data-unit-mechanics]').count(),0);
 missing=false;corrupt=true;await page.reload({waitUntil:'domcontentloaded'});await page.locator('[data-composition-unavailable]').waitFor({timeout:60000});assert.equal(await page.locator('[data-army-composition]').count(),0);
 assert.deepEqual(await get(`/api/coaching?${query}`),before);assert.deepEqual(errors,[]);assert.equal(writes.length,0);
 console.log('PASS army composition: exact recorded-role windows, Gbeto ranged/melee mechanics, base mobility/armour comparison, conditional compositions, no timing verdict, missing/corrupt fallbacks, exact shared-clock seek, private export, themes/mobile, no eager replay parsing or writes.');
}finally{await browser.close();}

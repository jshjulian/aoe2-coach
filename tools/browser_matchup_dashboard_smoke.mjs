import assert from 'node:assert/strict';
import fs from 'node:fs';
import {mkdir,chmod} from 'node:fs/promises';
import {createRequire} from 'node:module';
process.umask(0o077);
const require=createRequire(import.meta.url),{chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright'),ts=require('../viewer/node_modules/typescript'),Module=require('node:module');
function compile(file,deps={}){const m=new Module(file);m.require=id=>deps[id];m._compile(ts.transpileModule(fs.readFileSync(`viewer/src/lib/${file}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,file);return m.exports;}
const {buildGuideBoard}=compile('matchupGuide',{'./matchupGuideData':compile('matchupGuideData')});
const api=process.env.DASHBOARD_TEST_API_URL,viewer=process.env.VIEWER_URL||'http://127.0.0.1:3000';assert(api&&!['8765','8766'].includes(new URL(api).port));
const get=async p=>{const r=await fetch(api+p);assert(r.ok);return r.json();};
let game,analysis,board,player;
for(let attempt=0;attempt<40&&!board;attempt++){
 const library=await get('/api/library');
 for(const g of library.games.filter(g=>g.status==='ready'&&g.players.length===2&&g.players.some(p=>p.civilization==='Franks')&&g.players.some(p=>p.civilization==='Sicilians')&&(!process.env.DASHBOARD_TEST_GAME_ID||g.game_id===process.env.DASHBOARD_TEST_GAME_ID)).slice(0,8)){
  const name=g.players.find(p=>p.civilization==='Franks').name,a=await get(`/api/analysis?game_id=${g.game_id}`),b=buildGuideBoard(a,name);
  if(b){game=g;analysis=a;board=b;player=name;break;}
 }
 if(!board)await new Promise(r=>setTimeout(r,300));
}
assert(board,'Needs a supported local completed Franks–Sicilians replay; no private case is bundled.');
const query=new URLSearchParams({game_id:game.game_id,match_id:game.match_id,player}),before=await get(`/api/coaching?${query}`),browser=await chromium.launch({headless:true});
try{
 const context=await browser.newContext({viewport:{width:1500,height:1100},reducedMotion:'reduce'}),errors=[],writes=[],requests=[];let corrupt=false,general=false;
 await context.route('**/*',async route=>{
  const req=route.request(),u=new URL(req.url());if(!['127.0.0.1','localhost'].includes(u.hostname))return route.abort();requests.push(u.pathname);
  if(!u.pathname.startsWith('/api/'))return route.continue();if(!['GET','HEAD'].includes(req.method())){writes.push(u.pathname);return route.abort();}
  const headers={...req.headers()};delete headers.host;const r=await fetch(`${api}${u.pathname}${u.search}`,{headers});let body=Buffer.from(await r.arrayBuffer());
  if(u.pathname==='/api/library'){const p=JSON.parse(body);p.games=[game];p.total=1;p.counts={ready:1,queued:0,analyzing:0,error:0};body=Buffer.from(JSON.stringify(p));}
  if(u.pathname==='/api/analysis'&&(corrupt||general)){
   const p=JSON.parse(body);if(corrupt)p.events.push({...p.events[0]});if(general)p.players.find(p=>p.name!==player).civilization='Armenians';body=Buffer.from(JSON.stringify(p));
  }
  return route.fulfill({status:r.status,headers:Object.fromEntries(r.headers),body});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(viewer,{waitUntil:'domcontentloaded'});await page.getByRole('heading',{name:'Match review',exact:true}).first().waitFor({timeout:60000});await page.getByRole('combobox').first().selectOption(player);await page.getByTitle(game.file,{exact:true}).click();
 const dashboard=page.locator('[data-matchup-dashboard]');await dashboard.waitFor({timeout:60000});assert.equal(await dashboard.locator('[data-guide-card]').count(),8);assert((await dashboard.innerText()).includes('Donjons'));assert((await dashboard.locator('[data-guide-patch]').innerText()).includes('185872'));
 assert(!requests.includes('/api/replay'),'Dashboard does not fetch native replay bytes.');assert.equal(await page.evaluate(()=>Boolean(window.__aoe2rec)),false);
 const tabs=dashboard.getByRole('group',{name:'Reference age, not measured current state'});await tabs.getByRole('button',{name:'Feudal',exact:true}).focus();await page.keyboard.press('Enter');assert.equal(await tabs.getByRole('button',{name:'Feudal',exact:true}).getAttribute('aria-pressed'),'true');assert((await dashboard.locator('[data-guide-age-advice]').innerText()).includes('slowly'));
 await tabs.getByRole('button',{name:'Imperial',exact:true}).click();assert((await dashboard.locator('[data-guide-age-advice]').innerText()).includes('Chemistry'));await tabs.getByRole('button',{name:'Castle',exact:true}).click();assert((await dashboard.locator('[data-guide-age-advice]').innerText()).includes('Pikemen'));
 assert.equal(writes.length,0);assert.deepEqual(await get(`/api/coaching?${query}`),before);
 await mkdir('data/smoke',{recursive:true});
 for(const theme of ['dark','light']){if((await page.getByRole('checkbox',{name:'Dark mode'}).isChecked())!==(theme==='dark'))await page.getByText('Dark mode',{exact:true}).click();await dashboard.evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:`data/smoke/matchup-dashboard-${theme}.png`});}
 await page.setViewportSize({width:390,height:844});await dashboard.evaluate(e=>e.scrollIntoView({block:'start'}));await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await page.screenshot({path:'data/smoke/matchup-dashboard-mobile.png'});
 for(const theme of ['dark','light','mobile'])await chmod(`data/smoke/matchup-dashboard-${theme}.png`,0o600);
 await page.setViewportSize({width:1500,height:1100});await dashboard.getByRole('button',{name:'Jump to replay review ↓',exact:true}).click();assert(await page.locator('[data-replay-briefing]').evaluate(e=>e.getBoundingClientRect().top>=-2&&e.getBoundingClientRect().top<innerHeight));
 const share=compile('shareableReview',{'./teamIdentity':compile('teamIdentity')}).makeShareableReview(analysis,before,true);assert(!share.includes(board.guide.cue));assert(!share.includes(board.guide.headline));
 if(board.opponentQueues.length){const expected=board.opponentQueues[0].first;await dashboard.locator('[data-guide-card="opponent"] button').first().click();const slider=page.locator('input[type="range"]').first();await slider.waitFor({timeout:60000});await page.waitForFunction(t=>Number(document.querySelector('input[type="range"]')?.max)>t,expected.time_seconds);assert(Math.abs(Number(await slider.inputValue())-expected.time_seconds)<1);await page.getByRole('button',{name:'Coach',exact:true}).click();}
 general=true;await page.reload({waitUntil:'domcontentloaded'});await dashboard.waitFor({timeout:60000});assert((await dashboard.locator('[data-guide-card="matchup"]').innerText()).includes('pair-specific coverage not authored'));assert(!(await dashboard.locator('[data-guide-card="matchup"]').innerText()).includes('Serjeants'));
 general=false;corrupt=true;await page.reload({waitUntil:'domcontentloaded'});await page.locator('[data-matchup-dashboard-unavailable]').waitFor({timeout:60000});assert.equal(await page.locator('[data-matchup-dashboard]').count(),0);
 assert.equal(writes.length,0);assert.deepEqual(errors,[]);assert.deepEqual(await get(`/api/coaching?${query}`),before);
 console.log('PASS matchup dashboard: 8 bento cards, authored Sicilian reference, conditional age options, separate exact input summaries/seeks, keyboard, dark/light/mobile, no eager native parse, general/invalid-source fallbacks, unchanged review/store, export exclusion and no writes.');
}finally{await browser.close();}

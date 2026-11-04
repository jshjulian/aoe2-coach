import assert from 'node:assert/strict';
import fs from 'node:fs';
import {mkdir,chmod} from 'node:fs/promises';
import {createRequire} from 'node:module';
process.umask(0o077);
const require=createRequire(import.meta.url),{chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright'),ts=require('../viewer/node_modules/typescript'),Module=require('node:module');
function compile(name,deps={}){const m=new Module(name);m.require=id=>deps[id];m._compile(ts.transpileModule(fs.readFileSync(`viewer/src/lib/${name}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,name);return m.exports;}
const guide=compile('matchupGuide',{'./matchupGuideData':compile('matchupGuideData')}),army=compile('armyComposition'),takeaway=compile('balancedTakeaway'),reasoning=compile('militaryReasoning');
const {buildReplayHome,homeTime}=compile('replayCoachHome',{'./matchupGuide':guide,'./armyComposition':army,'./balancedTakeaway':takeaway,'./militaryReasoning':reasoning});
const api=process.env.ARMY_TEST_API_URL,viewer=process.env.VIEWER_URL||'http://127.0.0.1:3000';assert(api&&!['8765','8766'].includes(new URL(api).port));const get=async p=>{const r=await fetch(api+p);assert(r.ok);return r.json();};
let game,player,before,analysis,home;
for(let attempt=0;attempt<40&&!game;attempt++){
 const library=await get('/api/library'),candidates=library.games.filter(g=>g.status==='ready'&&g.players.length===2&&g.players.some(p=>p.civilization==='Franks')&&(!process.env.HOME_TEST_GAME_ID||g.game_id===process.env.HOME_TEST_GAME_ID)).sort((a,b)=>Number(b.players.some(p=>p.civilization==='Georgians'))-Number(a.players.some(p=>p.civilization==='Georgians'))).slice(0,12);
 for(const g of candidates){const name=g.players.find(p=>p.civilization==='Franks').name,q=new URLSearchParams({game_id:g.game_id,match_id:g.match_id,player:name}),p=await get('/api/coaching?'+q),a=await get('/api/analysis?'+q),h=buildReplayHome(a,name,p);if(h?.moments.length>=2&&h.plan.named){game=g;player=name;before=p;analysis=a;home=h;break;}}
 if(!game)await new Promise(r=>setTimeout(r,300));
}
assert(game,'Needs a supported local completed Franks replay and restored public reference snapshot; no replay/identity is bundled.');
const query=new URLSearchParams({game_id:game.game_id,match_id:game.match_id,player}),browser=await chromium.launch({headless:true});
try{
 const context=await browser.newContext({viewport:{width:1600,height:1150},reducedMotion:'reduce'}),errors=[],writes=[],requests=[];let missing=false,corrupt=false;
 await context.route('**/*',async route=>{
  const req=route.request(),u=new URL(req.url());if(!['127.0.0.1','localhost'].includes(u.hostname))return route.abort();requests.push(u.pathname);if(!u.pathname.startsWith('/api/'))return route.continue();if(!['GET','HEAD'].includes(req.method())){writes.push(u.pathname);return route.abort();}
  const headers={...req.headers()};delete headers.host;const r=await fetch(`${api}${u.pathname}${u.search}`,{headers});let body=Buffer.from(await r.arrayBuffer());
  if(u.pathname==='/api/library'){const p=JSON.parse(body);p.games=[game];p.total=1;p.counts={ready:1,queued:0,analyzing:0,error:0};body=Buffer.from(JSON.stringify(p));}
  if(u.pathname==='/api/coaching'&&(missing||corrupt)){const p=JSON.parse(body);if(missing){p.composition_context.reference.status='unavailable';p.composition_context.reference.profiles=[];p.composition_context.reference.compositions=[];}if(corrupt)p.composition_context.player.id=99;body=Buffer.from(JSON.stringify(p));}
  return route.fulfill({status:r.status,headers:Object.fromEntries(r.headers),body});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(viewer,{waitUntil:'domcontentloaded'});await page.getByRole('heading',{name:'Match review',exact:true}).first().waitFor({timeout:60000});await page.getByRole('combobox').first().selectOption(player);await page.getByTitle(game.file,{exact:true}).click();
 const root=page.locator('[data-replay-coach-home]');await root.waitFor({timeout:60000});await root.getByRole('heading',{name:home.plan.title,exact:true}).waitFor();assert.equal(await root.locator('[data-home-moment]').count(),home.moments.length);assert.equal(await page.locator('[data-coach-reference-book]').evaluate(e=>e.open),false);assert(!requests.includes('/api/replay'));assert.equal(await page.evaluate(()=>Boolean(window.__aoe2rec)),false);
 const headings=await root.locator('h2,h3,h4').allTextContents();assert(!headings.join(' ').match(/no verdict|conditional|no authored|unverified/i));assert(await root.evaluate(e=>e.getBoundingClientRect().top<innerHeight));
 for(const m of home.moments){await root.getByRole('heading',{name:m.title,exact:true}).waitFor();await root.getByRole('button',{name:`Watch ${m.title} at ${homeTime(m.anchor.time_seconds)}`,exact:true}).waitFor();}
 const note=root.locator('[data-home-evidence-note]');assert.equal(await note.evaluate(e=>e.open),false);await note.locator('summary').click();assert((await note.innerText()).includes('not completed or surviving armies'));await note.locator('summary').click();
 await root.getByRole('button',{name:'Jump to replay review ↓',exact:true}).click();assert(await page.locator('[data-replay-briefing]').evaluate(e=>e===document.activeElement));assert(await page.locator('[data-replay-briefing]').evaluate(e=>e.getBoundingClientRect().top>=-2&&e.getBoundingClientRect().top<innerHeight));
 await mkdir('data/smoke',{recursive:true});for(const theme of ['dark','light']){if((await page.getByRole('checkbox',{name:'Dark mode'}).isChecked())!==(theme==='dark'))await page.getByText('Dark mode',{exact:true}).click();await root.evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:`data/smoke/replay-coach-home-${theme}.png`});}
 await page.setViewportSize({width:390,height:844});await root.evaluate(e=>e.scrollIntoView({block:'start'}));await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await page.screenshot({path:'data/smoke/replay-coach-home-mobile.png'});for(const name of ['dark','light','mobile'])await chmod(`data/smoke/replay-coach-home-${name}.png`,0o600);
 const first=home.moments[0];await root.getByRole('button',{name:`Watch ${first.title} at ${homeTime(first.anchor.time_seconds)}`,exact:true}).focus();await page.keyboard.press('Enter');const slider=page.locator('input[type="range"]').first();await slider.waitFor({timeout:60000});await page.waitForFunction(t=>Number(document.querySelector('input[type="range"]')?.max)>t,first.anchor.time_seconds);assert(Math.abs(Number(await slider.inputValue())-first.anchor.time_seconds)<1);await page.getByRole('button',{name:'Coach',exact:true}).click();
 await page.getByText('Matchup & unit reference book',{exact:true}).click();await page.locator('[data-matchup-dashboard]').waitFor();assert.equal(await page.locator('[data-guide-card]').count(),8);await page.locator('[data-army-composition]').waitFor();await page.getByText('Matchup & unit reference book',{exact:true}).click();
 const exported=compile('shareableReview',{'./teamIdentity':compile('teamIdentity')}).makeShareableReview(analysis,before,false);for(const m of home.moments.filter(m=>m.id.startsWith('home:')))assert(!exported.includes(m.id));assert(!exported.includes('Your next game starts here'));
 missing=true;await page.reload({waitUntil:'domcontentloaded'});await root.waitFor({timeout:60000});await root.getByRole('heading',{name:home.plan.title,exact:true}).waitFor({state:'hidden'});assert(await root.locator('[data-home-moment]').count()>=2);
 missing=false;corrupt=true;await page.reload({waitUntil:'domcontentloaded'});await root.waitFor({timeout:60000});assert(await root.locator('[data-home-moment]').count()>=2);assert.equal(await page.locator('[data-coach-reference-book]').evaluate(e=>e.open),false);
 assert.deepEqual(await get(`/api/coaching?${query}`),before);assert.deepEqual(errors,[]);assert.equal(writes.length,0);
 console.log('PASS replay-first home: real timed moments before references, named supported composition and preparation, compact evidence note, existing-review focus, keyboard exact shared seek, reference access, missing/corrupt fallbacks, dark/light/mobile, export exclusion and no writes.');
}finally{await browser.close();}

import assert from 'node:assert/strict';
import fs from 'node:fs';
import {mkdir,chmod} from 'node:fs/promises';
import {createRequire} from 'node:module';
process.umask(0o077);
const require=createRequire(import.meta.url),{chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const api=process.env.COMMITMENT_TEST_API_URL,viewer=process.env.VIEWER_URL||'http://127.0.0.1:3000';
assert(api&&!['8765','8766'].includes(new URL(api).port),'Only an ephemeral test API may receive writes.');
const get=async path=>{const r=await fetch(api+path);assert(r.ok);return r.json();};
let game,player,before;
for(let attempt=0;attempt<40&&!game;attempt++){
 const library=await get('/api/library');
 for(const g of library.games.filter(g=>g.status==='ready'&&(!process.env.COMMITMENT_TEST_GAME_ID||g.game_id===process.env.COMMITMENT_TEST_GAME_ID)).slice(0,12)){
  const name=process.env.COMMITMENT_TEST_PLAYER||g.players[0]?.name;if(!name)continue;
  const p=await get('/api/coaching?'+new URLSearchParams({game_id:g.game_id,match_id:g.match_id,player:name}));
  if(p.commitment_context?.status==='available'&&p.commitment_context.windows.length){game=g;player=name;before=p;break;}
 }
 if(!game)await new Promise(r=>setTimeout(r,300));
}
assert(game,'Need a local completed replay with a supported commitment window; optionally set COMMITMENT_TEST_GAME_ID / COMMITMENT_TEST_PLAYER.');
const query=new URLSearchParams({game_id:game.game_id,match_id:game.match_id,player});
const analysis=await get(`/api/analysis?${query}`),browser=await chromium.launch({headless:true});
const note='Synthetic browser clarification, not player testimony.';
try{
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),errors=[],writes=[];let allowWrites=false,tamper=false;
 await context.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url());if(!['127.0.0.1','localhost'].includes(url.hostname))return route.abort();
  if(!url.pathname.startsWith('/api/'))return route.continue();
  if(!['GET','HEAD'].includes(req.method())){
   assert(allowWrites,'Browsing or editing must not write.');
   const body=req.postDataJSON();assert.equal(body.operation,'commitment_answer');writes.push(body);
  }
  const headers={...req.headers()};delete headers.host;
  const response=await fetch(`${api}${url.pathname}${url.search}`,{method:req.method(),headers,body:['GET','HEAD'].includes(req.method())?undefined:req.postDataBuffer()});
  let body=Buffer.from(await response.arrayBuffer());
  if(url.pathname==='/api/library'){
   const p=JSON.parse(body);p.games=[game];p.total=1;p.counts={ready:1,queued:0,analyzing:0,error:0};body=Buffer.from(JSON.stringify(p));
  }
  if(tamper&&url.pathname==='/api/coaching'){
   const p=JSON.parse(body);if(p.commitment_context)p.commitment_context.causal_claim=true;body=Buffer.from(JSON.stringify(p));
  }
  return route.fulfill({status:response.status,headers:Object.fromEntries(response.headers),body});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(viewer,{waitUntil:'domcontentloaded'});await page.getByRole('heading',{name:'Match review',exact:true}).first().waitFor({timeout:60000});
 await page.getByRole('combobox').first().selectOption(player);await page.getByTitle(game.file,{exact:true}).click();
 const panel=page.locator('[data-military-commitment]');await panel.waitFor({timeout:60000});assert.equal(await panel.evaluate(e=>e.open),false);
 await panel.locator(':scope > summary').click();const form=panel.locator('[data-commitment-clarification]');await form.locator('summary').click();
 const submit=panel.getByRole('button',{name:'Save commitment explanation locally',exact:true});assert(await submit.isDisabled());
 assert.equal(await panel.getByRole('combobox',{name:'Military investment job',exact:true}).inputValue(),'');
 assert.equal(await panel.getByRole('combobox',{name:'Military investment constraint',exact:true}).inputValue(),'');
 await panel.getByRole('combobox',{name:'Military investment job',exact:true}).selectOption('clear_pressure');
 await panel.getByRole('combobox',{name:'Military investment constraint',exact:true}).selectOption('resource_setup');
 await panel.getByRole('textbox',{name:'Military commitment note',exact:true}).fill(note);
 await page.waitForTimeout(200);assert.equal(writes.length,0);assert.deepEqual(await get(`/api/coaching?${query}`),before);
 await mkdir('data/smoke',{recursive:true});
 for(const theme of ['dark','light']){
  if((await page.getByRole('checkbox',{name:'Dark mode'}).isChecked())!==(theme==='dark'))await page.getByText('Dark mode',{exact:true}).click();
  await panel.scrollIntoViewIfNeeded();await page.screenshot({path:`data/smoke/military-commitment-${theme}.png`});
 }
 await page.setViewportSize({width:390,height:844});await panel.scrollIntoViewIfNeeded();await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await page.screenshot({path:'data/smoke/military-commitment-mobile.png'});
 for(const theme of ['dark','light','mobile'])await chmod(`data/smoke/military-commitment-${theme}.png`,0o600);
 await page.setViewportSize({width:1440,height:1000});allowWrites=true;
 await panel.getByRole('checkbox').check();await submit.click();await panel.getByText('Edit your explanation · revision 1',{exact:true}).waitFor();
 const saved=await get(`/api/coaching?${query}`),strip=p=>{const {commitment_context,...rest}=p;return rest;};assert.deepEqual(strip(saved),strip(before));assert.equal(writes.length,1);
 assert.equal(saved.commitment_context.windows[0].reviewed_context.note,note);assert.equal(saved.commitment_context.windows[0].reviewed_context.eligible_for_measurements,false);
 // Markdown export remains the legacy/situation serializer, never the new account or window.
 const ts=require('../viewer/node_modules/typescript'),Module=require('node:module');
 function compile(file,deps={}){const m=new Module(file);m.require=id=>deps[id];m._compile(ts.transpileModule(fs.readFileSync(`viewer/src/lib/${file}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,file);return m.exports;}
 const markdown=compile('shareableReview',{'./teamIdentity':compile('teamIdentity')}).makeShareableReview(analysis,saved,true);
 assert(!markdown.includes(note));assert(!markdown.includes(saved.commitment_context.windows[0].id));
 await form.locator('summary').click();await panel.getByRole('combobox',{name:'Military investment constraint',exact:true}).selectOption('not_applicable');
 await panel.getByRole('checkbox').check();await submit.click();await panel.getByText('Edit your explanation · revision 2',{exact:true}).waitFor();
 assert.equal(await panel.locator('[data-commitment-practice]').count(),0);assert.equal(writes.length,2);allowWrites=false;
 const after=await get(`/api/coaching?${query}`);assert.deepEqual(strip(after),strip(before));
 await panel.locator('[data-commitment-sources] > summary').click();const source=after.commitment_context.windows[0].evidence[0],event=analysis.events.find(e=>e.id===source.event_id);
 await panel.locator('[data-commitment-sources] button').first().click();const slider=page.locator('input[type="range"]').first();await slider.waitFor({timeout:60000});await page.waitForFunction(t=>Number(document.querySelector('input[type="range"]')?.max)>t,event.time_seconds);assert(Math.abs(Number(await slider.inputValue())-event.time_seconds)<1);
 await page.getByRole('button',{name:'Coach',exact:true}).click();tamper=true;await page.reload({waitUntil:'domcontentloaded'});await page.locator('[data-commitment-unavailable]').waitFor({timeout:60000});
 assert.equal(await page.locator('[data-military-commitment]').count(),0);assert.deepEqual(errors,[]);assert.equal(writes.length,2);
 console.log('PASS military commitment: explicit-only saves/revisions, exact source seek, unknown resources, correction withholding, unchanged legacy/practice packet, private export, malformed optional fallback, themes/mobile; only ephemeral clarification records.');
}finally{await browser.close();}

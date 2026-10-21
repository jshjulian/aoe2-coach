'use strict';
(() => {
 const task=JSON.parse(document.getElementById('task-data').textContent);
 const $=id=>document.getElementById(id),labels=new Map(task.samples.map(s=>[s.sample_id,{sample_id:s.sample_id,status:'unlabeled',text:''}]));
 const statuses=['unlabeled','exact','rounded','unreadable','not_displayed','crop_incomplete','disputed'];let frameIndex=0;
 function text(tag,value,parent){const e=document.createElement(tag);e.textContent=value;parent.appendChild(e);return e;}
 function clock(t){return `${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;}
 $('scope').textContent=`Dataset partition: ${task.partition}. Extractor: ${task.extractor_version}. ${task.frames.length} original frames; ${task.samples.length} labels. This pack never enables coaching.`;
 function progress(){const count=[...labels.values()].filter(l=>l.status!=='unlabeled').length;$('progress').textContent=`${count}/${labels.size} labelled`;}
 function draw(){
  const f=task.frames[frameIndex];$('frame-title').textContent=`Evidence frame ${frameIndex+1} / ${task.frames.length}`;
  $('previous').disabled=frameIndex===0;$('next').disabled=frameIndex===task.frames.length-1;
  $('original').src=f.evidence_file;$('original-link').href=f.evidence_file;
  $('identity').textContent=`Operator-bound roles (not automatically verified): left = ${task.roles.left.name} / parser ${task.roles.left.id}; right = ${task.roles.right.name} / parser ${task.roles.right.id}.`;
  const container=$('samples');container.replaceChildren();
  for(const s of task.samples.filter(s=>s.source_sha256===f.source_sha256)){
   const state=labels.get(s.sample_id),card=document.createElement('article');card.dataset.sampleId=s.sample_id;card.dataset.field=s.field;
   text('b',s.field,card).className='word';
   if(s.field.endsWith('_economic_unit_count'))text('p','Raw economic-unit header, not automatically villagers alive. Do not replace it with the villager portrait count.',card).className='muted';
   const image=document.createElement('img');image.className='crop';image.src=s.crop_file;image.alt=`Visible source crop: ${s.field}`;card.appendChild(image);
   const label=text('label','Reference status ',card),select=document.createElement('select');select.setAttribute('aria-label',`${s.field} status`);
   for(const value of statuses){const option=document.createElement('option');option.value=value;option.textContent=value.replaceAll('_',' ');select.appendChild(option);}select.value=state.status;select.addEventListener('change',()=>{state.status=select.value;progress();});label.appendChild(select);
   const tokenLabel=text('label',s.kind==='duration'?'Literal displayed time':'Literal displayed token',card),input=document.createElement('input');input.type='text';input.maxLength=80;input.autocomplete='off';input.spellcheck=false;input.value=state.text;input.placeholder=s.kind==='duration'?'m:ss or h:mm:ss — do not infer':'Exact digits, or visible rounded token';input.setAttribute('aria-label',`${s.field} visible text`);input.addEventListener('input',()=>{state.text=input.value;});tokenLabel.appendChild(input);
   container.appendChild(card);
  }
  progress();
 }
 $('previous').addEventListener('click',()=>{if(frameIndex>0){frameIndex--;draw();}});
 $('next').addEventListener('click',()=>{if(frameIndex<task.frames.length-1){frameIndex++;draw();}});
 $('download').addEventListener('click',()=>{
  const kind=$('reviewer-kind').value,id=$('reviewer-id').value.trim();$('error').textContent='';
  if(!['human','assistant'].includes(kind)||!id){$('error').textContent='Choose an explicit reviewer kind and local pseudonym.';return;}
  for(const s of task.samples){const l=labels.get(s.sample_id);if(l.status==='exact'&&!(s.kind==='duration'?/^[0-9]{1,3}:[0-5][0-9](?::[0-5][0-9])?$/:/^[0-9]{1,6}$/).test(l.text)){$('error').textContent=`Invalid exact token for ${s.field}; enter literal digits/time or choose a non-exact status.`;return;}}
  const data={schema_version:1,task_id:task.task_id,reviewer:{kind,id,blind_to_predictions:$('blind').checked},labels:[...labels.values()]};
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=`agewise-audit-labels-${task.task_id.slice(0,12)}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 });
 const context=$('context'),c=task.command_context;
 if(!c)text('p','No parser-clock review window supplied. This is not evidence of no activity.',context);
 else {
  text('p',`Parser-clock window ${clock(c.parser_window_seconds[0])}–${clock(c.parser_window_seconds[1])}: ${c.source_event_records} source records; ${c.named_input_records} named queue/research/placement inputs. ${c.omitted_named_records} named rows omitted from the bounded detail list.`,context);
  for(const s of c.limitations)text('p',s,context).className='muted';
  const counts=document.createElement('ul');context.appendChild(counts);
  for(const row of c.input_record_counts)text('li',`${row.player_name}: ${row.label} · ${row.kind} · ${row.input_records} input records (not completed units)`,counts);
  const categories=document.createElement('details');context.appendChild(categories);text('summary','All command categories, including queue cancellations',categories);
  for(const row of c.all_input_record_counts||[])text('p',`${row.player_name}: ${row.kind} · ${row.input_records} source records`,categories).className='compact';
  const details=document.createElement('details');context.appendChild(details);text('summary','Named recorded inputs and source event IDs',details);
  const scroll=document.createElement('div');scroll.className='scroll';details.appendChild(scroll);const table=document.createElement('table');scroll.appendChild(table);
  const head=document.createElement('tr');table.appendChild(head);for(const s of ['Parser time','Player','Input','Source ID'])text('th',s,head);
  for(const e of c.events){const row=document.createElement('tr');table.appendChild(row);for(const s of [clock(e.time_seconds),e.player_name,`${e.label} · ${e.kind}`,e.event_id])text('td',s,row);}
 }
 draw();
})();

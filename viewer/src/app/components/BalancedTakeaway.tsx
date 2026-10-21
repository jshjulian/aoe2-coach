"use client";
import type {TakeawayContext} from '@/lib/balancedTakeaway';
import type {PracticeContext} from '@/lib/practice';
import type {PythonAnalysis} from '@/lib/coachAnalysis';
import type {OpenEvidence} from '@/lib/coachingReview';

const clock=(s:number)=>`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;
const button='rounded-lg border border-[color:var(--border-subtle)] px-3 py-2 text-xs disabled:opacity-50';

export function BalancedTakeaway({packet,analysis,practice,selectedId,selectedPositiveId,onSelectPositive,onSelect,onPractice,onDetails,onOpenEvidence,busy}:{
 packet:TakeawayContext;analysis:PythonAnalysis;practice:PracticeContext;selectedId:string|null;
 selectedPositiveId:string|null;onSelectPositive:(id:string)=>void;onSelect:(id:string)=>void;onPractice:(id:string)=>void;onDetails:(id:string)=>void;onOpenEvidence:OpenEvidence;busy:boolean;
}){
 const positive=packet.positives.find(p=>p.id===(selectedPositiveId??packet.primary_positive_id))??packet.positives[0];
 const revisit=packet.revisits.find(r=>r.id===(selectedId??packet.primary_revisit_id));
 const suggestion=practice.suggestions.find(s=>s.id===revisit?.practice_id),focus=practice.active_focus;
 const already=!!focus&&!!suggestion&&(['label','when','action','adapt'] as const).every(k=>focus[k]===suggestion[k]);
 const events=new Map(analysis.events.map(e=>[e.id,e]));
 function evidence(ids:string[]){return ids.map(id=>{const e=events.get(id);return e?<button key={id} className={button} data-takeaway-evidence-link={id} onClick={()=>onOpenEvidence(e,'Takeaway evidence · recorded input / milestone, not battle state')}>{e.time} · {e.player_id===packet.player?.id?'You':e.player_id==null?'Actor unknown':'Other player'} · {e.action}{e.unit?` ${e.unit}`:e.building?` ${e.building}`:e.technology?` ${e.technology}`:''}</button>:null;});}
 return <section data-balanced-takeaway data-primary-review={revisit?true:undefined} data-takeaway-revisit={revisit?.id} className="studio-decision min-w-0 break-words">
  <h2 className="text-xs font-bold uppercase tracking-widest text-[color:var(--muted)]">Match review</h2>
  <div className="mt-4 grid items-start gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(250px,1fr)]">
   <section data-takeaway-keep className="lg:col-span-2 border-l-2 border-teal-600 pl-3">
    <h3 className="text-sm font-bold">Keep this</h3>
    <p className="mt-1 text-sm">{positive?.text??'No specific positive established from this evidence. This is not a verdict on everything you did.'}</p>
    {positive&&<><p className="mt-1 text-xs text-[color:var(--muted)]">{positive.caveat}</p><details className="mt-2 text-xs"><summary className="cursor-pointer">Recorded positive evidence</summary><p className="mt-2">{positive.derivation}</p><div className="mt-2 flex flex-wrap gap-2">{evidence(positive.event_ids)}</div></details></>}
   </section>
   <section data-takeaway-question>
    <h3 className="text-sm font-bold">Revisit this{revisit?` · ${clock(revisit.replay_anchor.time_seconds)}`:''}</h3>
    {revisit?<><p className="takeaway-title mt-1 text-lg font-bold sm:text-xl">{revisit.title}</p><p className="mt-2 text-sm">{revisit.recorded}</p>
     <p className="mt-1 text-xs text-[color:var(--muted)]">A decision to inspect, not a detected mistake. Actual forces, visibility and affordability remain unknown.</p>
     <button className={`${button} studio-primary mt-3`} data-takeaway-review={revisit.replay_anchor.event_id} onClick={()=>{const e=events.get(revisit.replay_anchor.event_id);if(e)onOpenEvidence(e,revisit.title);}}>Review {clock(revisit.replay_anchor.time_seconds)} →</button>
    </>:<p className="mt-1 text-sm">No clear decision to revisit from the current coverage. This does not establish mistake-free play.</p>}
   </section>
   <section data-takeaway-practice className="lesson-card rounded-xl p-4">
    <h3 className="text-sm font-bold">Practise this next game</h3>
    <p data-takeaway-action className="mt-2 text-sm">{suggestion?.action??'No new replay-based practice suggested. Your saved training plan is unchanged.'}</p>
    {suggestion&&!already&&<button className={`${button} studio-secondary mt-3`} disabled={busy} onClick={()=>onPractice(suggestion.id)}>{focus?'Use this habit instead':'Practise this'}</button>}
    {already&&<p className="mt-3 text-xs font-semibold text-[color:var(--training-accent)]">Already in your training plan</p>}
   </section>
  </div>
  {packet.scope_notes.slice(1).map(note=><p key={note} data-takeaway-scope className="mt-3 text-xs text-[color:var(--muted)]">{note}</p>)}
  <details data-takeaway-alternatives className="mt-4 border-t border-[color:var(--border-subtle)] pt-3 text-xs">
   <summary className="cursor-pointer font-semibold">More from this replay · {packet.positives.length} positives, {packet.revisits.length} questions, {packet.practice_ids.length} practices</summary>
   <p className="mt-2">Optional exploration. Changing the visible takeaway does not save or replace a habit. The positive is independent; the question and practice always move together. These are supported inputs/questions, not a complete list of good or bad decisions.</p>
   {packet.positives.length>1&&<details className="mt-3"><summary className="cursor-pointer font-semibold">Other positives</summary><ul className="mt-2 space-y-3">{packet.positives.map(p=><li key={p.id}><p>{p.text}</p><p className="mt-1 text-[color:var(--muted)]">{p.caveat}</p><button className={`${button} mt-2`} disabled={p.id===positive?.id} onClick={()=>onSelectPositive(p.id)}>{p.id===positive?.id?'Visible positive':'Show this positive'}</button><div className="mt-2 flex flex-wrap gap-2">{evidence(p.event_ids)}</div></li>)}</ul></details>}
   {!!packet.revisits.length&&<label className="mt-3 block font-semibold">Another decision and its practice
    <select aria-label="Takeaway decision" className="mt-2 block w-full min-w-0 rounded-lg border bg-[color:var(--panel)] p-2 text-xs" value={revisit?.id??''} onChange={e=>onSelect(e.target.value)}>{packet.revisits.map(r=><option key={r.id} value={r.id}>{clock(r.replay_anchor.time_seconds)} · {r.title}</option>)}</select>
   </label>}
   {!!packet.practice_ids.length&&<details className="mt-3"><summary className="cursor-pointer font-semibold">Other practice suggestions · choose a question/action pair</summary><ul className="mt-2 space-y-3">{packet.revisits.filter(r=>r.practice_id).map(r=>{const s=practice.suggestions.find(s=>s.id===r.practice_id);return s?<li key={r.id}><b>{clock(r.replay_anchor.time_seconds)} · {r.title}</b><p className="mt-1">{s.action}</p><button className={`${button} mt-2`} disabled={r.id===revisit?.id} onClick={()=>onSelect(r.id)}>{r.id===revisit?.id?'Visible question / practice':'Show this question / practice'}</button></li>:null;})}</ul></details>}
   {(packet.coverage.positives_truncated||packet.coverage.revisits_truncated)&&<p className="mt-2">This bounded view is truncated; additional raw command evidence remains in the full review.</p>}
  </details>
  <details data-takeaway-details className="mt-3 text-xs">
   <summary className="cursor-pointer font-semibold">Evidence, selection & limitations</summary>
   <div className="mt-3 space-y-3">
    {revisit&&<><p><b>Focused review question:</b> {revisit.question}</p><p><b>Window:</b> {revisit.window_seconds.map(clock).join('–')}. {clock(revisit.recording_seconds_remaining)} remains in the recording; this is not information the player had.</p><div className="flex flex-wrap gap-2">{evidence(revisit.event_ids)}</div><p>{revisit.selection_reason}</p><button className={button} onClick={()=>onDetails(revisit.id)}>Full source evidence & corrections</button></>}
    {suggestion&&<><p><b>Trigger:</b> {suggestion.when}</p><p><b>Adapt / stop:</b> {suggestion.adapt}</p></>}
    {packet.scope_notes.map(note=><p key={note}>{note}</p>)}
    <p>Replay and Events can locate the input, but cannot by themselves establish army readiness, escort arrival, completed defenses or fight results. No missing value is treated as zero.</p>
    <details><summary>How the main takeaway was selected</summary><p className="mt-2">{packet.selection_policy}</p><p className="mt-2">Composition v{packet.policy_version}. {packet.coverage.positive_scope} {packet.coverage.garrison_selection} Initial positive: {packet.coverage.positive_selection}</p><p className="mt-2">{packet.id} · {revisit?.rule_id} v{revisit?.rule_version}. All alternatives: {packet.revisits.map(r=>`${r.id}: ${r.selection_reason}`).join(' ')}</p></details>
   </div>
  </details>
 </section>;
}

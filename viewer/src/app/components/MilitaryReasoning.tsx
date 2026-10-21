"use client";
import {useEffect,useState} from 'react';
import type {PythonAnalysis} from '@/lib/coachAnalysis';
import type {MilitaryReasoning as Packet,MilitarySituation} from '@/lib/militaryReasoning';
import type {OpenEvidence} from '@/lib/coachingReview';
import type {TakeawayPositive} from '@/lib/balancedTakeaway';

const button='studio-secondary rounded-lg border px-3 py-2 text-sm font-semibold disabled:opacity-50';
const field='w-full min-w-0 rounded-lg border border-[color:var(--border-subtle)] bg-[color:var(--panel)] px-3 py-2 text-sm';
export function MilitaryReasoning({packet,analysis,selectedId,onSelect,onOpenEvidence,onPractice,canPractice,busy,save,keep}:{
 packet:Packet;analysis:PythonAnalysis;selectedId:string;onSelect:(id:string)=>void;onOpenEvidence:OpenEvidence;onPractice:(id:string)=>void;
 canPractice:(id:string)=>boolean;busy:boolean;save:(payload:Record<string,unknown>)=>Promise<void>;keep?:TakeawayPositive;
}){
 const c=packet.situations.find(c=>c.id===selectedId)??packet.situations.find(c=>c.id===packet.primary_id)!;
 const events=new Map(analysis.events.map(e=>[e.id,e]));
 function evidence(ids:string[]){return ids.map(id=>{const e=events.get(id);return e?<button key={id} type="button" className={button} data-reasoning-evidence={id} onClick={()=>onOpenEvidence(e,'Composition decision · recorded input, not verified state')}>{e.time} · {e.unit??e.technology??e.building??e.action}{e.status==='observed_milestone'?' milestone':' request'}</button>:null;});}
 const alt=c.comparison.alternative;
 const cost=alt?.base_cost?Object.entries(alt.base_cost).map(([r,n])=>`${n} ${r.toLowerCase()}`).join(' / '):'unavailable';
 return <section data-military-reasoning data-situation-id={c.id} className="mt-3 min-w-0 space-y-4">
  <div><p className="studio-kicker">Experimental decision question · military composition</p><h2 className="headline mt-1 text-2xl font-bold">{c.title}</h2><p className="mt-1 text-xs text-[color:var(--muted)]">Basic-unit roles · last recorded age Feudal · deterministic/local, not reconstructed combat</p></div>
  {c.assessment.positive?<aside data-reasoning-positive className="rounded-lg border border-[color:var(--border-subtle)] p-3 text-sm"><strong>Keep this reasoning</strong><p className="mt-1">{c.assessment.positive}</p></aside>:keep&&<aside className="rounded-lg border border-[color:var(--border-subtle)] p-3 text-sm"><strong>Keep · recorded positive elsewhere in this match</strong><p className="mt-1">{keep.text}</p><p className="mt-1 text-xs text-[color:var(--muted)]">{keep.caveat}</p><div className="mt-2 flex flex-wrap gap-2">{evidence(keep.event_ids)}</div></aside>}
  <div className="text-sm"><p><strong>Recognized queue sequence:</strong> {c.transition.sequence.map(x=>x.unit).join(' → ')}.</p><div className="mt-2 flex flex-wrap gap-2">{evidence([c.replay_anchor.event_id])}</div></div>
  <details data-reasoning-inputs className="text-sm"><summary className="cursor-pointer font-semibold">Requests behind this question · opponent information is retrospective</summary><div className="mt-3"><p><strong>Recorded response:</strong> {c.transition.sequence.map(x=>x.unit).join(' → ')}. These are queue inputs, not fielded composition.</p><div className="mt-2 flex flex-wrap gap-2">{evidence(c.transition.event_ids)}</div><p className="mt-3"><strong>Opponent investment:</strong> {c.threat.event_ids.map(id=>events.get(id)?.unit??events.get(id)?.technology).join(' · ')}. Retrospective—not proof you saw these units.</p><div className="mt-2 flex flex-wrap gap-2">{evidence(c.threat.event_ids)}</div>
   {!!c.fortification_context.event_ids.length&&<><p className="mt-3"><strong>Fortification context:</strong> a nearby-in-time opposing Tower request; gold denial and tower completion need your review.</p><div className="mt-2 flex flex-wrap gap-2">{evidence([...c.fortification_context.event_ids,...c.prior_production.filter(ref=>events.get(ref.event_id)?.building==='Watch Tower').map(ref=>ref.event_id)])}</div></>}
  </div></details>
  <div data-reasoning-assessment className="rounded-lg bg-[color:var(--panel)] p-3 text-sm"><h3 className="font-semibold">{c.assessment.headline}</h3><p className="mt-2 leading-relaxed">{c.reviewed_context.status==='reviewed'?c.assessment.text:c.comparison.selected_role.purpose}</p></div>
  {c.assessment.status!=='withheld_after_correction'&&<>
   <div className="grid min-w-0 gap-3 md:grid-cols-2 text-sm">
    <div className="rounded-lg border border-[color:var(--border-subtle)] p-3"><h3 className="font-semibold">{alt?(c.reviewed_context.answer==='resource_constraint'?'Stabilize before forcing production':'Or stabilize first'):`Requested · ${c.transition.to_unit}`}</h3><p className="mt-2">{alt?c.comparison.position_alternative:c.comparison.selected_role.exceptions}</p></div>
    <div data-reasoning-alternative className="rounded-lg border border-[color:var(--border-subtle)] p-3"><h3 className="font-semibold">{c.reviewed_context.answer==='resource_constraint'?'Possible later':'Compare'} · {alt?`${alt.name} production`:'position and resource access first'}</h3><p className="mt-2">{alt?`If ${c.threat.name} was the problem you were answering, consider keeping or adding ${alt.name} production. ${c.comparison.alternative_role?.purpose??''} Only do this if the production, funding and position actually support it.`:c.comparison.position_alternative}</p>{alt&&<p className="mt-2 text-xs text-[color:var(--muted)]">Reference base cost: {cost}. Requires a completed/surviving {alt.building_name}, actual funding, population room and safe positioning. Bonuses/rules may change effective costs.</p>}</div>
   </div>
  </>}
  <Clarification key={c.id} c={c} playerName={packet.player!.name} busy={busy} save={save}/>
  {c.assessment.status!=='withheld_after_correction'&&<div data-reasoning-practice className="training-shortcut rounded-lg p-3 text-sm"><div><strong className="text-[color:var(--training-accent)]">Practise · {c.practice_title}</strong><p className="mt-1">{c.practice_short}</p><p className="mt-1 text-xs text-[color:var(--muted)]">Manual opportunity review only; no comparable progress or verified execution is established.</p></div>{canPractice(c.id)&&<button type="button" className={button} disabled={busy} onClick={()=>onPractice(c.id)}>Choose this practice</button>}</div>}
  <details data-reasoning-details className="rounded-lg border border-[color:var(--border-subtle)] p-3 text-sm"><summary className="cursor-pointer font-semibold">Evidence, feasibility checks & what could change the advice</summary><div className="mt-3 space-y-3">
   <p><strong>Reasoning:</strong> {c.assessment.text}</p>
   <p><strong>Possible objective, not proven intent:</strong> {c.objective.text}</p><p>{c.comparison.conditions}</p>
   {c.comparison.requirements.map(r=><div key={r.check}><p><strong>{r.check.replaceAll('_',' ')} · {r.status.replaceAll('_',' ')}</strong></p><p>{r.text}</p><div className="mt-2 flex flex-wrap gap-2">{evidence(r.event_ids)}</div></div>)}
   {alt&&<p className="flex flex-wrap gap-3"><a href={alt.source_ref} target="_blank" rel="noopener noreferrer" className="underline">Pinned base cost data</a><a href={alt.availability_source_ref} target="_blank" rel="noopener noreferrer" className="underline">Pinned availability / age / production mapping</a></p>}
   <p><strong>Mechanics and exceptions:</strong> {c.comparison.selected_role.exceptions} {c.comparison.threat_role.exceptions}</p>
   <p>{c.comparison.position_exceptions}</p><p>{c.fortification_context.qualification}</p>
   <div><strong>Could reverse this interpretation</strong><ul className="mt-1 list-disc pl-5">{c.counterevidence.map(x=><li key={x}>{x}</li>)}</ul></div>
   <div><strong>Still missing</strong><ul className="mt-1 list-disc pl-5">{c.missing_information.map(x=><li key={x}>{x}</li>)}</ul></div>
   <p><strong>Afterward:</strong> only subsequent inputs are available; local outcome remains unknown.</p><div className="flex flex-wrap gap-2">{evidence(c.subsequent_observations.event_ids)}</div>
   <details><summary className="cursor-pointer font-semibold">All bounded source inputs</summary><div className="mt-2 flex flex-wrap gap-2">{evidence(c.event_ids)}</div></details>
   <p><strong>{packet.catalog.civilization} · pinned reference only:</strong> {packet.catalog.civilization_description}</p><p>{packet.catalog.qualification}</p><p>{packet.knowledge.authorship}</p><p>Patch {packet.replay_build}; catalog {packet.knowledge.source_commit.slice(0,12)}; rules pack v{packet.knowledge.pack_version}. Normalized report schema 5; original cache-generator identity was not recorded and is not invented here. No qualified full-state provider or AI output.</p>
   <p>{packet.coverage.scope} {packet.coverage.truncated?'Additional supported windows were truncated. ':''}Recent own requests are bounded to 24, follow-up to six, and opposing Tower context to two requests. Prior production requests may predate the decision window; none establish surviving production. {packet.coverage.selection}</p>
  </div></details>
  {packet.situations.length>1&&<details className="text-sm"><summary className="cursor-pointer font-semibold">Other composition-response questions ({packet.situations.length-1})</summary><label className="mt-2 block">Inspect a different transition<select aria-label="Composition-response question" className={`${field} mt-1`} value={c.id} onChange={e=>onSelect(e.target.value)}>{packet.situations.map(x=><option key={x.id} value={x.id}>{x.title} · {events.get(x.replay_anchor.event_id)?.time}</option>)}</select></label></details>}
 </section>;
}
function Clarification({c,playerName,busy,save}:{c:MilitarySituation;playerName:string;busy:boolean;save:(payload:Record<string,unknown>)=>Promise<void>}){
 const [answer,setAnswer]=useState(c.reviewed_context.answer??'');const [note,setNote]=useState(c.reviewed_context.note);const [confirmed,setConfirmed]=useState(false);
 useEffect(()=>{setAnswer(c.reviewed_context.answer??'');setNote(c.reviewed_context.note);setConfirmed(false);},[c.reviewed_context.revision,c.reviewed_context.answer,c.reviewed_context.note]);
 return <form data-reasoning-clarification className="rounded-lg border border-[color:var(--border-subtle)] p-3 text-sm" onSubmit={e=>{e.preventDefault();void save({operation:'reasoning_answer',situation_id:c.id,question_id:c.clarification.id,answer,note,confirm_identity:confirmed,expected_revision:c.reviewed_context.revision});}}>
  <label className="block font-semibold">{c.clarification.question}<select aria-label="What prompted this unit-role switch?" className={`${field} mt-2 font-normal`} value={answer} disabled={busy||c.reviewed_context.status==='unavailable'} onChange={e=>setAnswer(e.target.value)}><option value="" disabled>Choose what your review supports—not what the commands imply</option>{c.clarification.choices.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
  {!!answer&&<><label className="mt-3 block">Your context / correction (optional, local only)<textarea aria-label="Composition decision context" className={`${field} mt-1`} rows={2} maxLength={1000} value={note} onChange={e=>setNote(e.target.value)} disabled={busy||c.reviewed_context.status==='unavailable'}/></label>
  <label className="mt-2 block"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={busy||c.reviewed_context.status==='unavailable'}/> I reviewed this moment as {playerName}; this is my account, not verified game state.</label>
  <div className="mt-3 flex flex-wrap items-center gap-3"><button className={button} type="submit" disabled={busy||!answer||!confirmed||c.reviewed_context.status==='unavailable'}>Save reviewed context</button><span data-reasoning-save-status className="text-xs text-[color:var(--muted)]">{c.reviewed_context.status==='reviewed'?`Saved locally · revision ${c.reviewed_context.revision}; correct it here.`:c.reviewed_context.status==='unavailable'?c.reviewed_context.reason:'Not answered; no context has been saved.'}</span></div></>}
  {!answer&&<p data-reasoning-save-status className="mt-2 text-xs text-[color:var(--muted)]">{c.reviewed_context.status==='unavailable'?c.reviewed_context.reason:'Not answered; no context has been saved.'}</p>}
  <p className="mt-2 text-xs text-[color:var(--muted)]">Answers and edits remain separate, revisioned player-reviewed context. They never become measured army/resource state, choose your saved habit or enter the Markdown export.</p>
 </form>;
}

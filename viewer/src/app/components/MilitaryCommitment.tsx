"use client";
import {useMemo,useState} from 'react';
import {usableCommitment,type CommitmentContext,type CommitmentWindow} from '@/lib/militaryCommitment';
import type {PythonAnalysis} from '@/lib/coachAnalysis';
import type {OpenEvidence} from '@/lib/coachingReview';

const field='mt-1 block w-full min-w-0 rounded-lg border border-[color:var(--border-subtle)] bg-[color:var(--panel)] p-2 text-sm';
const button='rounded-lg border border-[color:var(--border-subtle)] px-3 py-2 text-left text-xs hover:bg-[color:var(--panel)] disabled:opacity-50';
type Save=(payload:Record<string,unknown>)=>Promise<void>;

function WindowReview({packet,window,analysis,busy,save,onOpenEvidence}:{packet:CommitmentContext;window:CommitmentWindow;analysis:PythonAnalysis;busy:boolean;save:Save;onOpenEvidence:OpenEvidence}){
  const reviewed=window.reviewed_context;
  const [constraint,setConstraint]=useState(reviewed.constraint??'');
  const [intent,setIntent]=useState(reviewed.intent??'');
  const [note,setNote]=useState(reviewed.note);
  const [confirmed,setConfirmed]=useState(false);
  const events=useMemo(()=>new Map(analysis.events.map(e=>[e.id,e])),[analysis]);
  const withheld=reviewed.constraint==='not_applicable';
  const clock=(t:number)=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
  return <article data-commitment-window={window.id} className="mt-3 min-w-0">
    <h3 className="font-semibold">{window.title}</h3>
    <p className="mt-1 text-xs text-[color:var(--muted)]">{clock(window.window_seconds[0])}–{clock(window.window_seconds[1])} · chronological review window, not a ranked mistake</p>
    <p className="mt-3 text-sm">{window.assessment}</p>
    {reviewed.status==='reviewed'&&<p className="mt-2 text-xs"><strong>Reported job:</strong> {packet.intent_choices.find(c=>c.id===reviewed.intent)?.label} <strong>Reported explanation:</strong> {packet.constraint_choices.find(c=>c.id===reviewed.constraint)?.label}</p>}
    <p className="mt-2 text-xs text-[color:var(--muted)]">{reviewed.status==='reviewed'?'Your saved explanation is a player account—not measured game state.':'The job and constraint are unknown until you choose to explain them.'} Bank, income, safe access, fielded units and production completion are not established.</p>
    {!withheld&&<><div className="mt-4 grid gap-2 sm:grid-cols-2">{window.options.map(o=><section key={o.id} className="min-w-0 rounded-lg border border-[color:var(--border-subtle)] p-3"><h4 className="text-sm font-semibold">{o.title}</h4><p className="mt-1 text-xs">{o.question}</p></section>)}</div>
      <p data-commitment-practice className="mt-3 rounded-lg bg-[color:var(--panel)] p-3 text-sm"><strong>Practice cue · not saved:</strong> {window.practice_cue}</p>
      <p className="mt-1 text-xs text-[color:var(--muted)]">This does not select or replace your active habit. No automatic rush recommendation or counter verdict.</p></>}
    <details data-commitment-sources className="mt-4 text-sm"><summary className="cursor-pointer font-semibold">Recorded inputs · {window.event_ids.length} exact sources</summary><p className="mt-2 text-xs text-[color:var(--muted)]">Own inputs and retrospective opponent inputs are separate. These are not player vision, actual unit positions, successful attacks or completed investments. Sources are bounded context, not a complete economic ledger.</p>
      <div className="mt-2 flex flex-col gap-2">{window.evidence.map(ref=>{const e=events.get(ref.event_id)!;return <button key={e.id} className={button} onClick={()=>onOpenEvidence(e,'Military commitment source')}><span className="font-semibold">{e.player_id===packet.player.id?'Own input':'Opponent input · retrospective'}</span> · {clock(e.time_seconds)} · {e.action} {e.unit??e.building??e.technology??e.order??''} · {e.id}</button>;})}</div>
    </details>
    <details data-commitment-clarification className="mt-4 rounded-lg border border-[color:var(--border-subtle)] p-3 text-sm"><summary className="cursor-pointer font-semibold">{reviewed.status==='reviewed'?`Edit your explanation · revision ${reviewed.revision}`:'Explain the job and constraint · optional, local only'}</summary>
      <p className="mt-2">{window.question}</p>
      {reviewed.status==='unavailable'&&<p role="alert" className="mt-2 text-sm">The saved clarification is unavailable or no longer bound to these sources. It was not reset. Saving is disabled.</p>}
      <form className="mt-3 flex flex-col gap-3" onSubmit={e=>{e.preventDefault();if(confirmed&&constraint&&intent&&!busy&&reviewed.status!=='unavailable')void save({operation:'commitment_answer',situation_id:window.id,question_id:'military-commitment-v1',constraint,intent,note,expected_revision:reviewed.revision,confirm_identity:true});}}>
        <label>What was the job?<select aria-label="Military investment job" className={field} value={intent} disabled={busy||reviewed.status==='unavailable'} onChange={e=>setIntent(e.target.value)}><option value="">Choose explicitly…</option>{packet.intent_choices.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></label>
        <label>What limited or explains the response?<select aria-label="Military investment constraint" className={field} value={constraint} disabled={busy||reviewed.status==='unavailable'} onChange={e=>setConstraint(e.target.value)}><option value="">Choose explicitly…</option>{packet.constraint_choices.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></label>
        <label>Explanation or correction · optional<textarea aria-label="Military commitment note" className={field} maxLength={1000} value={note} disabled={busy||reviewed.status==='unavailable'} onChange={e=>setNote(e.target.value)}/></label>
        <label className="flex items-start gap-2"><input type="checkbox" className="mt-1" checked={confirmed} disabled={busy||reviewed.status==='unavailable'} onChange={e=>setConfirmed(e.target.checked)}/><span>I confirm {packet.player.name} is my player and this is my retrospective account—not a measured replay fact.</span></label>
        <button className={`${button} self-start font-semibold`} type="submit" disabled={busy||!confirmed||!intent||!constraint||reviewed.status==='unavailable'}>Save commitment explanation locally</button>
        <p className="text-xs text-[color:var(--muted)]">Only this explicit save writes a revision. Browsing and changing fields do not save. Notes are excluded from Markdown export and do not rank the main takeaway or enter practice progress.</p>
      </form>
    </details>
  </article>;
}

export function MilitaryCommitment({value,analysis,profileName,busy,save,onOpenEvidence}:{value:unknown;analysis:PythonAnalysis;profileName:string;busy:boolean;save:Save;onOpenEvidence:OpenEvidence}){
  const packet=useMemo(()=>usableCommitment(value,analysis,profileName),[value,analysis,profileName]);
  const [selected,setSelected]=useState('');
  if(!value)return null;
  if(!packet)return <details data-commitment-unavailable className="panel-strong rounded-xl p-4 text-sm"><summary>Military commitment · unavailable</summary><p className="mt-2">This optional review has unsupported scope or an identity/source mismatch. No interpretation is proposed. The existing coach remains available.</p></details>;
  const window=packet.windows.find(w=>w.id===selected)??packet.windows[0];
  return <details data-military-commitment className="panel-strong min-w-0 rounded-xl border border-[color:var(--border-subtle)] p-4">
    <summary className="cursor-pointer text-sm font-semibold">Military commitment · {packet.windows.length} decision window{packet.windows.length===1?'':'s'}</summary>
    <p className="mt-3 text-sm">Stabilise or switch? Review the job, funding and protection behind a military investment—whether defending or trying to sustain a push. No attack is inferred from the inputs.</p>
    {packet.windows.length>1&&<label className="mt-3 block text-sm">Choose a commitment window<select aria-label="Military commitment window" className={field} value={window.id} onChange={e=>setSelected(e.target.value)}>{packet.windows.map(w=><option key={w.id} value={w.id}>{w.title}</option>)}</select></label>}
    {window?<WindowReview key={`${window.id}:${window.reviewed_context.revision}`} packet={packet} window={window} analysis={analysis} busy={busy} save={save} onOpenEvidence={onOpenEvidence}/>:<p className="mt-3 text-sm">{packet.reason}</p>}
    <details className="mt-4 text-xs text-[color:var(--muted)]"><summary>Coverage and limits</summary><p className="mt-2">{packet.coverage.selection}</p><p>{packet.coverage.unknown_military_inputs} unclassified military queue inputs. {packet.coverage.truncated?'Window limit reached; additional windows withheld.':''}</p>{packet.limitations.map(s=><p key={s} className="mt-1">{s}</p>)}</details>
  </details>;
}

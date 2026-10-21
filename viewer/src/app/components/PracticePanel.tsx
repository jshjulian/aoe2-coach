"use client";
import {useEffect,useRef,useState} from 'react';
import type {PythonAnalysis} from '@/lib/coachAnalysis';
import type {OpenEvidence} from '@/lib/coachingReview';
import type {PracticeContext,PracticeEvidence,PracticeLog,PracticeFocus,PracticeChoiceRequest} from '@/lib/practice';
import {PracticeChooser} from './PracticeChooser';
const field='w-full rounded-lg border border-[color:var(--border-subtle)] bg-[color:var(--panel)] p-2 text-sm';
const button='rounded-lg border border-[color:var(--border-subtle)] px-3 py-2 text-sm font-semibold disabled:opacity-50';
const labels={reported_attempt:'Reported attempt',reported_not_attempted:'Reported not attempted',not_applicable:'Not applicable · user report',insufficient_evidence:'Insufficient evidence / uncertain'};
export function PracticePanel({packet,analysis,playerName,busy,save,onOpenEvidence,onOpenMatch,knownMatches=[],preferredSuggestion,saveError}:{
 packet?:PracticeContext;analysis:PythonAnalysis;playerName:string;busy:boolean;save:(payload:Record<string,unknown>)=>Promise<void>;
 onOpenEvidence:OpenEvidence;onOpenMatch?:(matchId:string)=>void;knownMatches?:string[];preferredSuggestion?:PracticeChoiceRequest;saveError?:string|null;
}) {
 const [changing,setChanging]=useState(false);
 const panelRef=useRef<HTMLDetailsElement>(null);
 useEffect(()=>{
  if(!changing)return;
  const frame=requestAnimationFrame(()=>{
   const chooser=panelRef.current?.querySelector<HTMLElement>('[data-practice-chooser]');
   chooser?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
   chooser?.querySelector<HTMLElement>('h3')?.focus({preventScroll:true});
  });
  return ()=>cancelAnimationFrame(frame);
 },[changing,preferredSuggestion?.request]);
 const [opportunity,setOpportunity]=useState('uncertain'),[attempt,setAttempt]=useState('uncertain'),[note,setNote]=useState(''),[after,setAfter]=useState(false);
 const id=packet?.active_focus?.id;
 useEffect(()=>{setChanging(false);},[id]);
 useEffect(()=>{if(preferredSuggestion)setChanging(preferredSuggestion.change===true);},[preferredSuggestion]);
 useEffect(()=>{setOpportunity(packet?.current_log?.opportunity??'uncertain');setAttempt(packet?.current_log?.attempt??'uncertain');setNote(packet?.current_log?.note??'');setAfter(false);},[id,packet?.current_log?.recorded_at,analysis.match_id]);
 const player=analysis.players.find(p=>p.name===playerName);
 const ownsFocus=(f:PracticeFocus)=>f?.player_name===playerName&&f.origin?.player?.name===playerName&&['user_authored','situation_suggestion'].includes(f.source?.kind);
 const ownsLog=(l:PracticeLog,focusId?:string)=>l?.match?.player?.name===playerName&&l.focus_id===focusId&&l.provenance==='user_report_not_verified_execution'&&l.skill_improvement_established===false;
 const valid=packet&&packet.schema_version===1&&packet.current_match?.match_id===analysis.match_id&&packet.current_match.player?.name===playerName&&packet.current_match.player?.id===player?.id&&packet.eligible_for_automatic_priority===false&&packet.skill_improvement_established===false&&(!packet.active_focus||(ownsFocus(packet.active_focus)&&packet.active_focus.status==='active'))&&Array.isArray(packet.recent_logs)&&packet.recent_logs.every(l=>ownsLog(l,packet.active_focus?.id))&&Array.isArray(packet.history)&&packet.history.every(h=>ownsFocus(h.focus)&&h.focus.status==='retired'&&h.recent_logs.every(l=>ownsLog(l,h.focus.id)))&&(!packet.current_log||(ownsLog(packet.current_log,packet.active_focus?.id)&&packet.current_log.match.match_id===analysis.match_id&&packet.current_log.match.player?.id===player?.id));
 if(!packet)return <section data-practice className="panel-strong rounded-xl p-4"><h2 className="font-semibold">My practice across games</h2><p className="mt-1 text-sm text-[color:var(--muted)]">{playerName?'Loading practice…':'Select your player to choose a practice focus.'}</p></section>;
 if(packet.status==='unavailable')return <section data-practice className="panel-strong rounded-xl p-4"><h2 className="font-semibold">My practice across games</h2><p role="alert" className="mt-2 text-sm">The local practice journal could not be read. No records were cleared or replaced; automatic Coach is still separate. Restore or repair the local journal before saving practice.</p></section>;
 if(packet.status==='select_player')return <section data-practice className="panel-strong rounded-xl p-4"><h2 className="font-semibold">My practice across games</h2><p className="mt-2 text-sm">Select an unambiguous player in this replay to choose a practice focus.</p></section>;
 if(!valid)return <section data-practice className="panel-strong rounded-xl p-4"><h2 className="font-semibold">My practice across games</h2><p role="alert" className="mt-2 text-sm">Practice identity or qualification mismatch. Reload the selected player; no practice controls are available.</p></section>;
 const focus=packet.active_focus;
 function evidence(refs:PracticeEvidence[],matchId:string){
  if(matchId!==analysis.match_id)return null;
  return refs.map(ref=>{const event=analysis.events.find(e=>e.id===ref.event_id&&e.time_seconds===ref.time_seconds);return event?<button key={ref.event_id} className={button} onClick={()=>onOpenEvidence(event,'Practice command cue · not verified execution')}>{event.time} · Inspect recorded cue</button>:null;});
 }
 function openMatch(matchId:string){return matchId!==analysis.match_id&&onOpenMatch?<button className={button} disabled={!knownMatches.includes(matchId)} onClick={()=>onOpenMatch(matchId)}>{knownMatches.includes(matchId)?'Open reviewed match':'Replay not currently indexed'}</button>:null;}
 function logRows(logs:PracticeLog[]){return logs.map(log=><article data-practice-log key={log.match.match_id} className="mt-2 rounded-lg border border-[color:var(--border-subtle)] p-3 text-sm">
  <p className="font-semibold">{labels[log.status]}</p><p className="mt-1 text-xs text-[color:var(--muted)]">{log.match.map} · {log.match.player?.civilization} · manually logged {new Date(log.recorded_at).toLocaleDateString()} · {log.match.match_id.slice(0,12)}</p>
  {log.note&&<p className="mt-2 whitespace-pre-wrap break-words">{log.note}</p>}<div className="mt-2 flex flex-wrap gap-2">{evidence(log.evidence,log.match.match_id)}{openMatch(log.match.match_id)}</div>
 </article>);}
 return <details ref={panelRef} data-practice className="panel-strong training-workspace min-w-0 break-words rounded-xl p-4">
  <summary className="cursor-pointer text-sm font-semibold">My practice across games · journal & history</summary>
  {saveError&&<p role="alert" className="mt-3 rounded-lg border border-amber-500/40 p-3 text-sm">{saveError} Could not confirm this save. Reload to check the saved plan before trying again; history is not deleted.</p>}
  <p className="mt-3 text-xs text-[color:var(--muted)]">For the explicitly selected replay name <b>{playerName}</b>; not a verified account or automatic alias merge. This is a local practice journal, not a skill score. Reports do not change Coach priorities.</p>
  {focus?<>
   <div className="training-plan-card mt-3 rounded-lg border border-[color:var(--border-subtle)] p-3"><p className="studio-eyebrow">Saved across games · not this replay’s main review</p><h2 className="mt-1 font-bold">{focus.label}</h2><p className="mt-2 text-sm"><b>When:</b> {focus.when}</p><p className="mt-1 text-sm"><b>I will:</b> {focus.action}</p>{focus.adapt&&<p className="mt-1 text-sm"><b>Adapt if needed:</b> {focus.adapt}</p>}
   <p className="mt-2 text-xs text-[color:var(--muted)]">{focus.source.kind==='user_authored'?'Your own practice focus':'Explicitly selected from an automatic review suggestion'} · selected {new Date(focus.selected_at).toLocaleDateString()}. No replay has been silently added to your history.</p>
   <div className="mt-2 flex flex-wrap gap-2">{evidence(focus.evidence,focus.origin.match_id)}{openMatch(focus.origin.match_id)}</div></div>
   <div className="mt-3 flex flex-wrap gap-2"><button className={`${button} studio-secondary`} disabled={busy} onClick={()=>setChanging(!changing)}>Change habit</button><button className={button} disabled={busy} onClick={()=>save({operation:'practice_keep',focus_id:focus.id})}>Keep practising</button><button className={button} disabled={busy} onClick={()=>save({operation:'practice_retire',focus_id:focus.id})}>Retire focus / choose another</button></div>
   {changing&&<PracticeChooser key={`${focus.id}:${preferredSuggestion?.request??0}`} packet={packet} playerName={playerName} busy={busy} save={save} currentFocus={focus} preferredSuggestion={preferredSuggestion} onCancel={()=>setChanging(false)} />}
   {focus.last_kept_at&&<p role="status" className="mt-2 text-xs">Kept for the next game. No improvement claim was added.</p>}
   {focus.origin.match_id===analysis.match_id?<p className="mt-4 text-sm">This is the replay where you selected the focus. Play another game, then select that replay to review a practice opportunity.</p>:<section className="mt-4 rounded-lg border border-[color:var(--border-subtle)] p-3">
    <h3 className="font-semibold">Review this game’s opportunity</h3><p className="mt-2 text-sm">{packet.opportunity?.explanation}</p><div className="mt-2 flex flex-wrap gap-2">{evidence(packet.opportunity?.evidence??[],analysis.match_id)}</div>
    <p className="mt-2 text-xs text-[color:var(--muted)]">Recorded cues are not proof of player vision, a real attack, intent, a completed response or a good outcome. Your answers below remain self-reports.</p>
    <label className="mt-3 block text-sm"><input type="checkbox" checked={after} onChange={e=>setAfter(e.target.checked)}/> I played this match after selecting this focus. File dates alone do not establish this.</label>
    <label className="mt-3 block text-sm">Did a relevant opportunity actually occur?<select aria-label="Practice opportunity" className={field} value={opportunity} onChange={e=>{setOpportunity(e.target.value);setAttempt('uncertain');}}><option value="uncertain">Uncertain / insufficient evidence</option><option value="yes">Yes · my review or recollection</option><option value="no">No · not applicable</option></select></label>
    {opportunity==='yes'&&<label className="mt-3 block text-sm">Did you try the intended action?<select aria-label="Practice attempt" className={field} value={attempt} onChange={e=>setAttempt(e.target.value)}><option value="uncertain">Uncertain</option><option value="yes">Yes · reported attempt, not verified execution</option><option value="no">No · reported not attempted</option></select></label>}
    <label className="mt-3 block text-sm">What happened or made you adapt? <textarea aria-label="Practice review note" className={field} maxLength={1000} value={note} onChange={e=>setNote(e.target.value)} placeholder="Optional recollection; not a parser fact. Avoid personal information you do not want stored locally."/></label>
    <button className={`${button} mt-3`} disabled={busy||!after} onClick={()=>save({operation:'practice_log',focus_id:focus.id,played_after_selection:after,opportunity,attempt:opportunity==='yes'?attempt:'uncertain',note})}>{packet.current_log?'Update this practice review':'Save this practice review'}</button>
    {packet.current_log&&<p className="mt-2 text-xs">Updating replaces this match’s current journal entry, retaining revisions—not an extra counted opportunity.</p>}
   </section>}
   <details className="mt-4"><summary className="text-sm font-semibold">Recent manually logged matches · {packet.logged_match_count}</summary><p className="mt-2 text-xs text-[color:var(--muted)]">{packet.limitation} Showing up to 30 entries in logging order, not an inferred game chronology.</p>{logRows(packet.recent_logs)}{!packet.recent_logs.length&&<p className="mt-2 text-sm">No practice opportunities logged yet.</p>}</details>
  </>:<>
   {packet.legacy_goal_active?<div className="mt-3 text-sm"><p>Your existing legacy goal is preserved. Stop it explicitly before selecting a new focus here; its history will remain.</p><button className={`${button} mt-2`} disabled={busy} onClick={()=>save({operation:'stop_goal'})}>Stop legacy goal, preserve history</button></div>:<>
    <PracticeChooser key={preferredSuggestion?.request??0} packet={packet} playerName={playerName} busy={busy} save={save} preferredSuggestion={preferredSuggestion} />
   </>}
  </>}
  {packet.history.length>0&&<details className="mt-4"><summary className="text-sm font-semibold">Retired practice history · recent focuses</summary>{packet.history.map(h=><details key={h.focus.id} className="mt-3 rounded-lg border border-[color:var(--border-subtle)] p-3"><summary className="text-sm font-semibold">{h.focus.label} · {h.logged_match_count} logged matches</summary><p className="mt-2 text-sm">{h.focus.when} {h.focus.action}</p><p className="mt-1 text-xs text-[color:var(--muted)]">Retired—not labelled mastered or failed. Showing up to five journal entries.</p>{logRows(h.recent_logs)}</details>)}</details>}
 </details>;
}

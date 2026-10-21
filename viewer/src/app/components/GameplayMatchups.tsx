"use client";
import type {GameplayContext} from '@/lib/gameplay';
import type {PythonAnalysis} from '@/lib/coachAnalysis';
import type {OpenEvidence} from '@/lib/coachingReview';
export function GameplayMatchups({packet,analysis,onOpenEvidence}:{packet:GameplayContext;analysis:PythonAnalysis;onOpenEvidence:OpenEvidence}){
 const m=packet.matchups,byId=new Map(analysis.events.map(e=>[e.id,e]));
 if(!m)return null;
 const valid=m.effective_state_established===false&&m.evidence_class==='conditional_advice'&&m.opponents.every(o=>analysis.players.some(p=>p.id===o.player_id&&p.civilization===o.civilization)&&o.retrospective_inputs.every(r=>byId.get(r.event_id)?.player_id===o.player_id&&byId.get(r.event_id)?.time_seconds===r.time_seconds)&&o.options.every(a=>a.evidence_class==='conditional_advice'&&a.catalog_options.every(x=>packet.reference?.entities.some(e=>e.kind===x.kind&&e.entity_id===x.entity_id&&e.name===x.name&&e.catalog_available))));
 if(!valid)return <p role="alert" className="mt-3 text-xs">Matchup identity or qualification mismatch. No matchup options shown.</p>;
 return <details data-gameplay-matchups className="mt-4 text-xs"><summary className="cursor-pointer font-semibold">Civilization matchups & scouting choices</summary>
  <p className="mt-3">{m.limitation}</p><p className="mt-2"><b>{packet.player?.civilization} · own reference:</b> {packet.reference?.status}. {packet.reference?.civilization_description}</p>
  {m.reason&&<p className="mt-2">{m.reason}</p>}
  {m.opponents.map(o=><article key={o.player_id} className="mt-3 rounded border border-[color:var(--border-subtle)] p-3">
   <h3 className="font-bold">Against {o.civilization} · catalog, not actual composition</h3><p className="mt-2">{o.reference.status}: {o.reference.civilization_description||o.reference.reason}</p>
   <p className="mt-2 font-semibold">{o.question}</p>
   <details className="mt-2"><summary>Whole-match opponent inputs — retrospective, not player vision</summary>{o.retrospective_inputs.map(r=>{const e=byId.get(r.event_id);return e?<button key={r.event_id} className="mr-2 mt-2 rounded border border-[color:var(--border-subtle)] px-2 py-1" onClick={()=>onOpenEvidence(e,'Retrospective opponent queue · not player vision')}>{e.time} · {r.unit} queue input</button>:null;})}{!o.retrospective_inputs.length&&<p className="mt-2">No recognized role-family queue input in current coverage. This does not establish the opponent's army.</p>}</details>
   {o.options.map(a=><div key={a.family} className="mt-3"><p>{a.advice}</p><p className="mt-1"><b>Your pinned-catalog options:</b> {a.catalog_options.map(c=>c.name).join(', ')||'No verified specific option in this catalog; inspect available alternatives.'} {a.qualification}</p></div>)}
   <p className="mt-2 text-[color:var(--muted)]">Source commit {o.reference.source?.commit??'unavailable'} · declared update {o.reference.source?.declared_update??'unknown'}. Not live stats, a counter verdict or an explanation of the result.</p>
  </article>)}
 </details>;
}

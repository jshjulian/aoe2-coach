"use client";
import type { ObservationContext, ReviewedMomentContext, OpenObservedEvidence } from '@/lib/reviewedMoments';

const button='rounded border border-[color:var(--border-subtle)] px-2 py-1 text-xs font-semibold hover:bg-[color:var(--panel)]';
const clock=(t:number)=>`${Math.floor(t/60)}:${String(t%60).padStart(2,'0')}`;

export function ReviewEvidence({matchId,player,observations,reviewed,onOpen}: {
  matchId:string;player?:{id:number;name:string};observations?:ObservationContext;
  reviewed?:ReviewedMomentContext;onOpen?:OpenObservedEvidence;
}) {
  const obs=observations?.match_id===matchId && observations.selected_player_id===player?.id && observations.validated_for_application===false ? observations : undefined;
  const identityOK=reviewed?.schema_version===1 && reviewed.match_id===matchId && reviewed.independently_validated===false && reviewed.eligible_for_automatic_priority===false && reviewed.causal_claim===false;
  const candidate=identityOK && reviewed?.status==='available' ? reviewed.moment : null;
  const moment=candidate?.match_id===matchId && obs?.status==='experimental' && candidate.observation_batch_id===obs.batch_id && candidate.player.id===player?.id && candidate.player.name===player?.name && ['assistant','user'].includes(candidate.author_kind) ? candidate : null;
  const status=!player?'Select your player':!obs?'Evidence coverage unavailable':obs.status==='experimental'?`Experimental observations · ${obs.checkpoint_count} checkpoints`:obs.status==='invalid'?'Observation evidence unavailable':obs.status==='not_collected'?'Replay only · no imported observations':'No observations for this player';
  return <div className="space-y-3" data-review-evidence>
    <details className="rounded-lg border border-[color:var(--border-subtle)] px-3 py-2 text-xs" data-evidence-coverage>
      <summary className="cursor-pointer font-semibold">Evidence · {status}{moment ? ` · ${moment.author_kind==='assistant'?'Assistant':'User'} review available` : ''}</summary>
      <p className="mt-2 text-[color:var(--muted)]">Automatic Coach uses decoded commands and situation rules, not verified continuous state. Authored reviews are separate interpretations and do not change automatic priority or your saved practice goal.</p>
      {obs?.status==='experimental' && <p className="mt-2">{obs.checked_point_count} visually checked measurements; {obs.readable_point_count} readable; {obs.rejected_point_count} rejected. {obs.readable_window_seconds && `Readable checkpoints ${clock(obs.readable_window_seconds[0])}–${clock(obs.readable_window_seconds[1])}. `}This is not continuous coverage or independent accuracy validation.</p>}
      <p className="mt-2 text-[color:var(--muted)]">No military idle/utilization measurement. Missing observations are not zero. No game or CaptureAge is launched from this page. Availability is a snapshot from the last match load; refresh the page after local imports.</p>
      {onOpen && <button className={`${button} mt-2`} onClick={()=>onOpen(moment?.anchor_seconds??0,'economy')}>Inspect Economy evidence</button>}
      {reviewed?.status==='unavailable' && <p className="mt-2 text-amber-700 dark:text-amber-300">Authored review unavailable: its review or active observation evidence failed checks.</p>}
      {reviewed?.status==='available' && !moment && <p role="alert" className="mt-2">Authored review identity/qualification mismatch; hidden.</p>}
    </details>
    {moment && <details className="rounded-lg border border-[color:var(--border-subtle)] p-3" data-authored-review>
      <summary className="cursor-pointer text-sm font-semibold">{moment.author_kind==='assistant'?'Assistant':'User'}-reviewed · {moment.title} · {clock(moment.anchor_seconds)}</summary>
      <p className="mt-2 text-xs text-[color:var(--muted)]">Local authored interpretation · experimental observations · not an automatic finding or proven cause</p>
      <p className="mt-2 text-sm">{moment.summary}</p>
      <p className="mt-2 text-sm"><b>One practice:</b> {moment.practice}</p>
      {onOpen && <div className="mt-3 flex flex-wrap gap-2"><button className={button} onClick={()=>onOpen(moment.anchor_seconds,'replay')}>View reviewed moment · {clock(moment.anchor_seconds)}</button><button className={button} onClick={()=>onOpen(moment.anchor_seconds,'economy')}>Inspect checked observations</button></div>}
      <details className="mt-3 text-xs"><summary>Referenced observations, alternatives & limitations</summary>
        <p className="mt-2 text-[color:var(--muted)]">Values below resolve from the intact active batch. Visual checks are operator assertions, not independent engine validation. Player names identify whose values are shown.</p>
        <ul className="mt-2 space-y-2">{moment.facts.map(f=><li key={`${f.player_id}:${f.metric}:${f.time_seconds}`} className="break-words">{clock(f.time_seconds)} · {f.player_name} · {f.label}: <b>{f.value} {f.unit}</b>{onOpen && f.player_id===player?.id && <button className={`${button} ml-2`} onClick={()=>onOpen(f.time_seconds,'economy')}>Inspect checkpoint</button>}<p className="mt-1 break-all font-mono text-[10px] text-[color:var(--muted)]">Evidence SHA-256: {f.evidence_sha256}</p></li>)}</ul>
        <p className="mt-3 font-semibold">Alternative explanations</p><ul className="list-disc pl-4">{moment.alternatives.map((s,i)=><li key={i}>{s}</li>)}</ul>
        <p className="mt-3 font-semibold">Limitations</p><ul className="list-disc pl-4">{moment.limitations.map((s,i)=><li key={i}>{s}</li>)}</ul>
      </details>
    </details>}
  </div>;
}

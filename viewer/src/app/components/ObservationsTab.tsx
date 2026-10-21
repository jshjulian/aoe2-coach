"use client";
import {useEffect,useState} from 'react';
import type {PythonAnalysis} from '@/lib/coachAnalysis';
import {validateObservationResponse,type ObservationData,type ObservationSeries} from '@/lib/observations';

type Props={analysis:PythonAnalysis|null;gameId:string|null;profileName:string;selectedTime:number;formatClock:(s:number)=>string;onSeek:(s:number)=>void};

function Chart({series,data,duration,selectedTime,formatClock,onSeek}:{series:ObservationSeries;data:ObservationData;duration:number;selectedTime:number;formatClock:Props['formatClock'];onSeek:Props['onSeek']}) {
  const [increments,setIncrements]=useState(false); const [page,setPage]=useState(0); const [fitWindow,setFitWindow]=useState(true);
  const meta=data.metrics[series.metric];
  const values=increments ? series.increments.map(p=>({time:p.end,value:p.value,quality:p.quality,evidence:p.evidence_sha256.join(', '),start:p.start}))
    : series.points.filter(p=>p.value!==null).map(p=>({time:p.time_seconds,value:p.value!,quality:p.quality,evidence:p.evidence_sha256,start:null}));
  const max=Math.max(1,...values.map(p=>p.value));
  const first=series.coverage.first_seconds ?? 0, last=series.coverage.last_seconds ?? duration;
  const start=fitWindow?Math.max(0,first-(first===last?1:0)):0;
  const end=fitWindow?Math.min(duration,last+(first===last?1:0)):duration;
  const x=(time:number)=>55+Math.min(1,Math.max(0,(time-start)/Math.max(end-start,1)))*700;
  const y=(value:number)=>180-(value/max)*145;
  return <article data-observation-chart={series.metric} className="panel-strong rounded-xl p-4">
    <h2 className="font-semibold">{meta.label}{increments?' · increase between checkpoints':''}</h2>
    <p className="mt-1 text-xs text-[color:var(--muted)]">{meta.definition || 'Reported HUD count; extraction and definition require validation.'}</p>
    <p className="mt-2 text-sm">{series.coverage.readable} readable checkpoints · {series.coverage.rejected} rejected · {series.gaps.length} gaps longer than {data.max_comparable_gap_seconds}s · {series.counter_resets.length} counter decreases/resets</p>
    <p className="mt-1 text-xs">Readable observations: {series.coverage.first_seconds===null?'none':`${formatClock(first)}–${formatClock(last)}`} of a {formatClock(duration)} match. This is not full-match coverage.</p>
    <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={fitWindow} onChange={e=>setFitWindow(e.target.checked)}/>Fit collected window</label>
    {meta.kind==='counter' && <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={increments} onChange={e=>{setIncrements(e.target.checked);setPage(0);}}/>Show additional reported time between checkpoints</label>}
    {!values.length ? <p className="mt-3 text-sm">No comparable values in this view. Gaps, unreadable checkpoints and resets are not filled in.</p> : <>
      <svg viewBox="0 0 800 220" className="mt-3 w-full" role="img" aria-label={`${meta.label}: experimental reported observations over game time`}>
        <title>{meta.label} · {meta.unit}. Dots are observations, not interpolated state.</title>
        <line x1="55" x2="755" y1="180" y2="180" stroke="currentColor" opacity=".4"/>
        <text x="5" y="38" fontSize="12" fill="currentColor">{max}</text><text x="30" y="180" fontSize="12" fill="currentColor">0</text>
        <text x="55" y="207" fontSize="12" fill="currentColor">{formatClock(start)}</text><text x="710" y="207" fontSize="12" fill="currentColor">{formatClock(end)}</text>
        {selectedTime>=start&&selectedTime<=end&&<line x1={x(selectedTime)} x2={x(selectedTime)} y1="30" y2="180" stroke="currentColor" strokeDasharray="4 4" opacity=".5"/>}
        {values.map((p,i)=><circle key={i} cx={x(p.time)} cy={y(p.value)} r="3.5" fill={p.quality==='visually_checked'?'#0284c7':'#a16207'} className="cursor-pointer" onClick={()=>onSeek(p.time)}><title>{formatClock(p.time)} · {p.value} {meta.unit} · {p.quality}</title></circle>)}
      </svg>
      <p className="text-xs text-[color:var(--muted)]">Y: {meta.unit} · X: game clock. Dots only; no interpolation or missing-to-zero. Blue: operator visually checked; amber: unreviewed. Neither is independently verified game state. Click a dot to open Replay.</p>
      <details className="mt-3"><summary className="text-sm">Checkpoint values & evidence</summary>
        <div className="overflow-x-auto"><table className="mt-2 w-full text-left text-xs"><thead><tr><th>Game time</th><th>Reported value</th><th>Quality / screenshot SHA-256</th></tr></thead><tbody>{values.slice(page*50,(page+1)*50).map((p,i)=><tr key={i}><td className="py-2"><button className="underline" onClick={()=>onSeek(p.time)}>{p.start!==null?`${formatClock(p.start)}–`:''}{formatClock(p.time)}</button></td><td>{p.value} {meta.unit}</td><td><p>{p.quality}</p><code className="break-all">{p.evidence}</code></td></tr>)}</tbody></table></div>
        <div className="mt-2 flex gap-3"><button disabled={page===0} onClick={()=>setPage(page-1)}>Previous</button><span>{page+1} / {Math.max(1,Math.ceil(values.length/50))}</span><button disabled={(page+1)*50>=values.length} onClick={()=>setPage(page+1)}>Next</button></div>
      </details>
    </>}
  </article>;
}

export function ObservationsTab({analysis,gameId,profileName,selectedTime,formatClock,onSeek}:Props) {
  const [data,setData]=useState<ObservationData|null>(null); const [error,setError]=useState<string|null>(null);
  const [showExperimental,setShowExperimental]=useState(false); const [metric,setMetric]=useState('tc_idle_seconds'); const [revision,setRevision]=useState(0);
  const player=analysis?.players.filter(p=>p.name===profileName); const playerId=player?.length===1?player[0].id:null;
  useEffect(()=>{
    setData(null);setError(null);setShowExperimental(false);
    if(!analysis)return;
    const controller=new AbortController();
    const api=process.env.NEXT_PUBLIC_COACH_API_URL || 'http://127.0.0.1:8765';
    const query=new URLSearchParams({match_id:analysis.match_id,player:profileName});
    if(gameId)query.set('game_id',gameId);else query.set('file',analysis.source_file);
    fetch(`${api}/api/observations?${query}`,{signal:controller.signal}).then(async response=>{
      const body=await response.json();if(!response.ok)throw new Error(body.error || 'Observations unavailable.');
      if(!validateObservationResponse(body,analysis.match_id,playerId))throw new Error('Observation identity/schema mismatch; nothing displayed.');
      if(!controller.signal.aborted){setData(body);setMetric(body.series.find((s:ObservationSeries)=>s.metric==='tc_idle_seconds')?.metric ?? body.series[0]?.metric ?? 'tc_idle_seconds');}
    }).catch(e=>{if(!controller.signal.aborted)setError(String(e.message));});
    return ()=>controller.abort();
  },[analysis,gameId,profileName,playerId,revision]);
  if(!analysis)return <section className="panel-strong rounded-xl p-5">Open a match to inspect optional economy/state observations.</section>;
  const selected=data?.series.find(s=>s.metric===metric);
  return <section data-observations-status={error?'error':data?.status ?? 'loading'} className="flex flex-col gap-4">
    <header className="panel-strong rounded-xl p-5"><h1 className="text-xl font-bold">Economy & state observations</h1>
      <p className="mt-2 text-sm">Optional CaptureAge evidence for {profileName || 'your selected player'}. This page never launches Steam, the game or CaptureAge.</p>
      <p className="mt-2 text-xs text-[color:var(--muted)]">Parser queue-command gaps are not measured TC idle. These observations stay separate from parser facts and the primary Coach review.</p>
      <button className="mt-3 rounded border px-3 py-1 text-sm" onClick={()=>setRevision(revision+1)}>Refresh observations</button>
    </header>
    {error && <p role="alert" className="panel-strong rounded-xl p-4">{error}</p>}
    {!data&&!error&&<p>Loading optional observations…</p>}
    {data?.status==='select_player'&&<p className="panel-strong rounded-xl p-4">Select your player to bind observations to an explicit parser player ID.</p>}
    {data && ['not_collected','no_player_observations'].includes(data.status) && <div className="panel-strong rounded-xl p-5"><h2 className="font-semibold">No observations collected for this player</h2><p className="mt-2 text-sm">There is no TC-idle, villager or economy curve to show yet—not a zero result. Local import hooks are ready; managed collection controls are not connected.</p><p className="mt-2 text-sm">Food, wood, gold and stone have a saved-image OCR pilot. TC idle, workers, population and army statistics still need extraction and validation.</p></div>}
    {data?.status==='invalid'&&<p role="alert" className="panel-strong rounded-xl p-4">Stored observations failed identity/schema/integrity checks. No graph or diagnosis is shown.</p>}
    {data?.status==='experimental'&&<>
      {data.collection_summary&&<p className="text-sm">Collection: {data.collection_summary.exported_frames} of {data.collection_summary.total_frames} frames exported; {data.collection_summary.excluded_frames} rejected/unanchored frames excluded, not filled in.</p>}
      <label className="panel-strong flex items-start gap-3 rounded-xl p-4 text-sm"><input type="checkbox" checked={showExperimental} onChange={e=>setShowExperimental(e.target.checked)}/><span>Show experimental observations. CaptureAge-reported values and OCR can be wrong; visual checking is not independent validation. They do not establish causes of defeat.</span></label>
      {showExperimental&&<>
        <label className="text-sm">Statistic <select className="ml-2 rounded border bg-[color:var(--panel)] p-2" value={metric} onChange={e=>setMetric(e.target.value)}>{data.series.map(s=><option key={s.metric} value={s.metric}>{data.metrics[s.metric].label}</option>)}</select></label>
        {selected&&<Chart key={`${data.batch_id}:${metric}`} series={selected} data={data} duration={analysis.duration_seconds} selectedTime={selectedTime} formatClock={formatClock} onSeek={onSeek}/>}
        {!!data.review_questions.length&&<section className="panel-strong rounded-xl p-4"><h2 className="font-semibold">Experimental review questions · not causal diagnoses</h2>{data.review_questions.map((q,i)=><article key={i} className="mt-4 text-sm"><button className="underline" onClick={()=>onSeek(q.time_seconds)}>{formatClock(q.time_seconds)} · Review this checkpoint</button><p className="mt-1">{q.observation}</p><p className="mt-1 font-semibold">{q.question}</p><p className="mt-1">{q.interpretation}</p><details className="mt-2 text-xs"><summary>Alternatives & evidence</summary><ul>{q.alternatives.map(a=><li key={a}>{a}</li>)}</ul><p className="break-all">Screenshot SHA-256: {q.evidence_sha256.join(', ')}</p></details></article>)}</section>}
      </>}
    </>}
    {data&&<details className="panel-strong rounded-xl p-4 text-xs"><summary>Metric availability, provenance & limitations</summary><p className="mt-2">{data.provider?`${data.provider.name} ${data.provider.ui_version} · ${data.provider.method} · ${data.provider.extractor_version ?? 'extractor version unavailable'}`:'No provider observations imported.'} All metrics remain unqualified for primary coaching. Sparse checkpoints do not establish full-match coverage.</p><ul className="mt-2 space-y-1">{Object.entries(data.metrics).map(([key,m])=><li key={key}><b>{m.label}</b>: {data.series.some(s=>s.metric===key)?'experimental observations imported':m.extraction==='planned'?'extractor planned':'saved-image OCR pilot; no observations imported'} · {m.unit}</li>)}</ul><p className="mt-2">TC-idle increases can sum over multiple TCs; they are not an idle percentage. Low food plus idle does not prove poor allocation: research, population cap, garrison, spending and intentional pauses require review. No resource/army graph is inferred from command counts.</p></details>}
  </section>;
}

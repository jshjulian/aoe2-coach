"use client";

import { useEffect, useMemo, useState } from 'react';
import { makeShareableReview } from '@/lib/shareableReview';
import { MatchupBriefing } from './MatchupBriefing';
import { SituationReview } from './SituationReview';
import { GameplayDecision } from './GameplayDecision';
import { BalancedTakeaway } from './BalancedTakeaway';
import { MilitaryReasoning } from './MilitaryReasoning';
import { usableReasoning } from '@/lib/militaryReasoning';
import { usableTakeaway } from '@/lib/balancedTakeaway';
import { GameplayMatchups } from './GameplayMatchups';
import { PracticePanel } from './PracticePanel';
import { PracticeGuide } from './PracticeGuide';
import { ReviewEvidence } from './ReviewEvidence';
import type { OpenObservedEvidence } from '@/lib/reviewedMoments';
import type { PythonAnalysis } from '@/lib/coachAnalysis';
import type { PracticeChoiceRequest } from '@/lib/practice';
import type { CoachingResponse, OpenEvidence } from '@/lib/coachingReview';

const PLAN = 'franks-scouts-knights';
const api = process.env.NEXT_PUBLIC_COACH_API_URL || 'http://127.0.0.1:8765';
const field = 'rounded border border-[color:var(--border-subtle)] bg-[color:var(--panel)] px-2 py-1.5 text-sm';
const button = 'rounded-lg border border-[color:var(--border-subtle)] px-3 py-2 text-sm font-semibold disabled:opacity-50 hover:bg-[color:var(--panel)]';

export function CoachingReview({ analysis, gameId, profileName, onOpenEvidence, onOpenObservedEvidence, onOpenPracticeMatch, practiceMatchIds }: {
  analysis: PythonAnalysis; gameId?: string | null; profileName: string; onOpenEvidence: OpenEvidence; onOpenObservedEvidence?: OpenObservedEvidence; onOpenPracticeMatch?: (matchId: string) => void; practiceMatchIds?: string[];
}) {
  const [response, setResponse] = useState<CoachingResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [verdict, setVerdict] = useState('inconclusive');
  const [note, setNote] = useState('');
  const [checklist, setChecklist] = useState('uncertain');
  const [adaptation, setAdaptation] = useState('uncertain');
  const [after, setAfter] = useState(false);
  const [includeNames, setIncludeNames] = useState(false);
  const [exportStatus, setExportStatus] = useState('');
  const [decisionId,setDecisionId]=useState<string|null>(null);
  const [takeawayDecisionId,setTakeawayDecisionId]=useState<string|null>(null);
  const [reasoningId,setReasoningId]=useState<string|null>(null);
  const [takeawayPositiveId,setTakeawayPositiveId]=useState<string|null>(null);
  const [fullReview,setFullReview]=useState(false);
  const [sourceDetailId,setSourceDetailId]=useState<string|null>(null);
  const [practiceSuggestion,setPracticeSuggestion]=useState<PracticeChoiceRequest>();
  const identity = { game_id: gameId || '', file: analysis.source_file, match_id: analysis.match_id, player: profileName };

  function apply(data: CoachingResponse) {
    if (data.review.match_id !== analysis.match_id || (data.review.player && (data.review.player.name !== profileName || data.review.player.id !== analysis.players.find(p=>p.name===profileName)?.id))) throw new Error('Coaching response identity mismatch.');
    setResponse(data); setPlan(data.state.plan?.id ?? ''); setConfirmed(data.state.plan?.confirmed ?? false);
    setVerdict(data.state.feedback?.verdict ?? 'inconclusive'); setNote(data.state.feedback?.note ?? '');
  }
  useEffect(() => {
    if (!profileName) return;
    const controller = new AbortController();
    const query = new URLSearchParams(identity);
    fetch(`${api}/api/coaching?${query}`, { signal: controller.signal })
      .then(async r => { const data = await r.json(); if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`); return data; })
      .then(apply).catch(e => { if (!controller.signal.aborted) setError(String(e)); });
    return () => controller.abort();
    // Component is keyed by content match ID and player; a game change discards drafts.
  }, [analysis.match_id, gameId, profileName]);

  async function save(payload: Record<string, unknown>) {
    setBusy(true); setError('');
    try {
      const session = await fetch(`${api}/api/coaching/session`);
      const token = await session.json();
      if (!session.ok) throw new Error(token.error || 'Could not open local coaching session.');
      const r = await fetch(`${api}/api/coaching/state`, { method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Coaching-Token': token.csrf_token},
        body: JSON.stringify({...identity, ...payload}) });
      const data = await r.json(); if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
      apply(data); setAfter(false);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  const byId = useMemo(() => new Map(analysis.events.map(event => [event.id, event])), [analysis]);
  const exportMarkdown = useMemo(() => response ? makeShareableReview(analysis, response, includeNames) : '', [analysis, response, includeNames]);
  function evidence(ids: string[]) {
    return [...new Set(ids)].map(id => {
      const event = byId.get(id);
      return event ? <button key={id} className={button} onClick={() => onOpenEvidence(event, 'Coaching evidence')}>
        {event.time} · {event.action}{event.unit ? ` ${event.unit}` : ''}{event.building ? ` ${event.building}` : ''} · {id}
      </button> : <span key={id}>Unresolved evidence {id}</span>;
    });
  }
  const review = response?.review;
  const primary = review?.primary;
  const state = response?.state;
  const gameplay=response?.gameplay_context;
  const gameplayIdentity=gameplay?.schema_version===2&&gameplay.match_id===analysis.match_id&&gameplay.player?.name===profileName&&gameplay.player.id===analysis.players.find(p=>p.name===profileName)?.id&&gameplay.player.civilization===analysis.players.find(p=>p.name===profileName)?.civilization&&gameplay.causal_claim===false&&gameplay.skill_rating===null;
  const practicePacket=response?.practice_context;
  const practiceIdentity=practicePacket?.schema_version===1&&practicePacket.current_match?.match_id===analysis.match_id&&practicePacket.current_match.player?.name===profileName&&practicePacket.current_match.player.id===analysis.players.find(p=>p.name===profileName)?.id&&analysis.players.filter(p=>p.name===profileName).length===1&&practicePacket.eligible_for_automatic_priority===false&&practicePacket.skill_improvement_established===false&&Array.isArray(practicePacket.suggestions)&&(!practicePacket.active_focus||(practicePacket.active_focus.player_name===profileName&&practicePacket.active_focus.status==='active'));
  const focus=practiceIdentity?practicePacket.active_focus:undefined;
  // A saved cross-game habit must NEVER select this replay's main review.
  const selectedDecision=decisionId==='existing-review'?null:gameplay?.candidates.find(c=>c.id===decisionId)??gameplay?.primary;
  function preparePractice(id?:string,change=false){
    setPracticeSuggestion(old=>({id,change,request:(old?.request??0)+1}));
    const panel=document.querySelector<HTMLDetailsElement>('[data-practice]');
    if(panel){panel.open=true;panel.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});}
  }
  const takeaway=usableTakeaway(response,analysis,profileName);
  const reasoning=usableReasoning(response,analysis,profileName);
  const selectedReasoning=reasoning?.situations.find(c=>c.id===reasoningId)??reasoning?.situations.find(c=>c.id===reasoning.primary_id);
  const compactReview=!!takeaway||!!reasoning;
  const takeawaySourceId=takeaway?.revisits.find(r=>r.id===takeawayDecisionId)?.id??takeaway?.primary_revisit_id??undefined;
  const sourceSituation=response?.situation&&response.situation.recommendations.some(r=>r.id===sourceDetailId)?{...response.situation,recommendations:[...response.situation.recommendations.filter(r=>r.id===sourceDetailId),...response.situation.recommendations.filter(r=>r.id!==sourceDetailId)]}:response?.situation;
  const displayedSourceId=reasoning&&!fullReview?selectedReasoning?.id:takeaway&&!fullReview?takeawaySourceId:selectedDecision?.id??sourceSituation?.recommendations[0]?.id;
  const displayedSuggestion=practiceIdentity?practicePacket.suggestions.find(s=>s.id===displayedSourceId):undefined;
  const alreadyTraining=!!focus&&!!displayedSuggestion&&(['label','when','action','adapt'] as const).every(k=>focus[k]===displayedSuggestion[k]);
  return <>{focus&&<div data-training-shortcut className="training-shortcut rounded-lg px-4 py-3 text-xs"><div className="min-w-0"><span className="font-semibold text-[color:var(--training-accent)]">Saved habit · across games</span><p className="mt-1 break-words">{focus.label} <span className="text-[color:var(--muted)]">— separate from this replay’s review.</span></p></div><button className="studio-secondary shrink-0 rounded-lg border px-3 py-2 font-semibold" disabled={busy} onClick={()=>preparePractice(displayedSuggestion?.id,true)}>Change habit</button></div>}<section className="coach-studio studio-review panel-strong rounded-xl border border-[color:var(--border-subtle)] p-5">
    <div className="studio-section-heading"><span>01 / Replay briefing</span><span>This match’s evidence. Not your saved habit.</span></div>
    {reasoning&&selectedReasoning&&!fullReview&&<MilitaryReasoning packet={reasoning} analysis={analysis} selectedId={selectedReasoning.id} onSelect={setReasoningId} onOpenEvidence={onOpenEvidence} onPractice={id=>preparePractice(id,!!focus)} canPractice={id=>!!practiceIdentity&&!!practicePacket?.suggestions.some(s=>s.id===id)} busy={busy} save={save} keep={takeaway?.positives.find(p=>p.id===takeaway.primary_positive_id)} />}
    {response?.reasoning_context?.status==='available'&&response.reasoning_context.primary_id&&!reasoning&&<p data-reasoning-invalid role="alert" className="mt-3 text-xs">Composition comparison identity, source or qualification mismatch. The compatible review remains available.</p>}
    {reasoning&&takeaway&&!fullReview&&<details data-other-review-questions className="mt-4 text-sm"><summary className="cursor-pointer font-semibold">Other observations & previous review questions</summary><BalancedTakeaway packet={takeaway} analysis={analysis} practice={practicePacket!} selectedId={takeawaySourceId??null} selectedPositiveId={takeawayPositiveId} onSelectPositive={setTakeawayPositiveId} onSelect={setTakeawayDecisionId} onPractice={id=>preparePractice(id,!!focus)} onDetails={id=>{setSourceDetailId(id);setDecisionId(gameplay?.candidates.some(c=>c.id===id)?id:'existing-review');setFullReview(true);}} onOpenEvidence={onOpenEvidence} busy={busy} /></details>}
    {takeaway&&!reasoning&&!fullReview&&<BalancedTakeaway packet={takeaway} analysis={analysis} practice={practicePacket!} selectedId={takeawaySourceId??null} selectedPositiveId={takeawayPositiveId} onSelectPositive={setTakeawayPositiveId} onSelect={setTakeawayDecisionId} onPractice={id=>preparePractice(id,!!focus)} onDetails={id=>{setSourceDetailId(id);setDecisionId(gameplay?.candidates.some(c=>c.id===id)?id:'existing-review');setFullReview(true);}} onOpenEvidence={onOpenEvidence} busy={busy} />}
    {response?.takeaway_context?.status==='available'&&!takeaway&&<p data-takeaway-invalid role="alert" className="mt-3 text-xs">Balanced takeaway identity or source mismatch. The compatible command review remains available below.</p>}
    <details data-full-command-review className="mt-4 text-sm" open={!compactReview||fullReview} onToggle={e=>{if(compactReview){setFullReview(e.currentTarget.open);if(!e.currentTarget.open)setSourceDetailId(null);}}}><summary className="cursor-pointer font-semibold">Full command reviews, corrections & timeline</summary>
    {(!compactReview||fullReview)&&<div className="mt-3">
    {gameplayIdentity&&!!gameplay?.candidates.length&&<details data-gameplay-topics className="mb-3 text-xs"><summary className="cursor-pointer font-semibold">Other moments in this replay · explore / change the review</summary><label className="mt-2 block font-semibold">Inspect another decision · conditional questions, not ranked mistakes
      <select aria-label="Gameplay decision topic" className={`${field} mt-2 block w-full min-w-0`} value={selectedDecision?.id??'existing-review'} onChange={e=>{setSourceDetailId(null);setDecisionId(e.target.value);if(takeaway?.revisits.some(r=>r.id===e.target.value))setTakeawayDecisionId(e.target.value);}}> 
        <option value="existing-review">Existing command-based review & timeline</option>
        {gameplay.candidates.map(c=><option key={c.id} value={c.id}>{c.title} · {Math.floor(c.replay_anchor.time_seconds/60)}:{String(Math.floor(c.replay_anchor.time_seconds%60)).padStart(2,'0')}</option>)}
      </select>
    </label></details>}
    {gameplay&&selectedDecision ? <>
      <GameplayDecision key={selectedDecision.id} packet={{...gameplay,primary:selectedDecision}} analysis={analysis} playerName={profileName} busy={busy} save={save} onOpenEvidence={onOpenEvidence} onPractice={!alreadyTraining&&displayedSuggestion?()=>preparePractice(selectedDecision.id,!!focus):undefined} practiceLabel={focus?'Use this habit instead':'Practise this decision'} alreadyTraining={alreadyTraining} />
      <details className="mt-4 text-sm"><summary className="cursor-pointer font-semibold">Other command-based review & timeline</summary><div className="mt-3"><SituationReview analysis={analysis} review={sourceSituation} profileName={profileName} onOpenEvidence={onOpenEvidence} /></div></details>
    </> : <SituationReview analysis={analysis} review={sourceSituation} profileName={profileName} onOpenEvidence={onOpenEvidence} />}
    </div>}</details>
    <div className="mt-4"><ReviewEvidence matchId={analysis.match_id} player={analysis.players.find(p=>p.name===profileName)} observations={response?.observation_context} reviewed={response?.reviewed_moment_context} onOpen={onOpenObservedEvidence} /></div>
    {gameplayIdentity&&gameplay&&(reasoning?<details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold">Other conditional matchup references</summary><GameplayMatchups packet={gameplay} analysis={analysis} onOpenEvidence={onOpenEvidence} /></details>:<GameplayMatchups packet={gameplay} analysis={analysis} onOpenEvidence={onOpenEvidence} />)}
    {error && <p role="alert" className="mt-3 rounded border border-amber-500/40 p-3 text-sm">{error} — restart the local app if this API is unavailable.</p>}
  </section>
  <PracticeGuide packet={response?.practice_context} progress={response?.progress_context} analysis={analysis} playerName={profileName} busy={busy} save={save} openJournal={()=>preparePractice(focus?undefined:displayedSourceId)} onChangeHabit={()=>preparePractice(displayedSuggestion?.id,true)} onOpenEvidence={onOpenEvidence} onOpenMatch={onOpenPracticeMatch} knownMatches={practiceMatchIds} />
  <PracticePanel packet={response?.practice_context} analysis={analysis} playerName={profileName} busy={busy} save={save} onOpenEvidence={onOpenEvidence} onOpenMatch={onOpenPracticeMatch} knownMatches={practiceMatchIds} preferredSuggestion={practiceSuggestion} saveError={error} />
  <details className="panel-strong rounded-xl p-4"><summary className="text-sm font-semibold">Saved practice, references & export</summary><section>
    <details className="mt-4 rounded-lg border border-[color:var(--border-subtle)] p-3"><summary className="text-sm font-semibold">Optional legacy plan-specific review & saved practice goal</summary>
    <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-[color:var(--muted)]">Legacy practice review · not the situation priority</p>
    <h2 className="headline mt-1 text-2xl font-bold">Plan-specific practice</h2>
    <p className="mt-1 text-xs text-[color:var(--muted)]">No skill grade or causal verdict. Evidence and feedback stay on this machine.</p>
    <details className="mt-3 rounded-lg border border-[color:var(--border-subtle)] p-3">
      <summary className="text-sm font-semibold">Player and intended plan · {profileName || 'choose your player in the library'}</summary>
      <div className="mt-3 flex flex-col gap-3">
        <label className="text-sm">Intended game plan <select className={`${field} ml-2`} value={plan} onChange={e => {setPlan(e.target.value); setConfirmed(false);}}>
          <option value="">Other / unknown — no plan-specific verdict</option><option value={PLAN}>Franks — Scouts → Knights</option>
        </select></label>
        <label className="text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> I confirm {profileName || 'the selected identity'} is my player and this was my intended plan for this match.</label>
        <p className="text-xs text-[color:var(--muted)]">Optional context for the legacy plan-specific rule; observed openings above do not require it. Retrospective user context is not a parser fact. Population at the age click is not verified. The first rule only supports Arabia 1v1; Arena/team games are not penalized.</p>
        <button className={`${button} self-start`} disabled={busy || !profileName || !response} onClick={() => save({operation: 'plan', plan, confirmed})}>Save match context locally</button>
      </div>
    </details>
    {!profileName ? <p className="mt-4">Select your player in the sidebar. Coaching never assumes player slot 1.</p> : !review ? <p className="mt-4">Loading this match’s local review…</p> : <>
      {primary ? <article className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
        <p className="text-xs font-semibold text-amber-700 dark:text-amber-300">Review question · {primary.interpretation.confidence} interpretation confidence · not a confirmed mistake</p>
        <h3 className="mt-2 text-lg font-bold">{primary.title}</h3>
        {primary.observations.map(o => <p key={o.id} className="mt-2 text-sm"><b>Recorded:</b> {o.text}</p>)}
        <p className="mt-2 text-sm"><b>What it might mean:</b> {primary.interpretation.text}</p>
        <p className="mt-2 text-sm"><b>Try next time:</b> {primary.recommendation.action}</p>
        <div className="mt-3 flex flex-wrap gap-2">{evidence([primary.replay_anchor.event_id])}</div>
        <details className="mt-3 text-sm"><summary>Why this priority, evidence quality and alternative explanations</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">{primary.priority_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
          <p className="mt-3"><b>Evidence:</b> anchors decoded: {String(primary.evidence_quality.anchors_reliably_decoded)}; interval anchors complete: {String(primary.evidence_quality.complete_for_measure)}; full command stream completeness: {primary.evidence_quality.stream_completeness}. {primary.evidence_quality.reason}</p>
          <p className="mt-2"><b>Context coverage:</b> {primary.context.window_seconds.map(s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`).join('–')}. {primary.context.evidence_quality.reason}</p>
          <ul className="mt-2 list-disc pl-5">{primary.interpretation.alternatives.map(a => <li key={a}>{a}</li>)}</ul>
          <div className="mt-3 flex flex-wrap gap-2">{evidence(primary.observations.flatMap(o => o.event_ids))}</div>
          <details className="mt-3"><summary>Nearby opponent-order cues ({primary.supporting_context_event_ids.length}) — not confirmed attacks</summary><div className="mt-2 flex flex-wrap gap-2">{evidence(primary.supporting_context_event_ids)}</div></details>
          <details className="mt-3"><summary>Possible adaptations / counterevidence ({primary.counterevidence_event_ids.length})</summary><div className="mt-2 flex flex-wrap gap-2">{evidence(primary.counterevidence_event_ids)}</div></details>
          <p className="mt-2 text-xs">Rule {primary.rule_id} v{primary.rule_version}. Not claimed: {primary.recommendation.not_claimed.join(', ')}.</p>
        </details>
        <details className="mt-4 text-sm"><summary>Review this advice · {state?.feedback?.verdict ?? 'not reviewed'}</summary>
          <div className="mt-2 flex flex-col items-start gap-2"><select aria-label="Advice feedback" className={field} value={verdict} onChange={e => setVerdict(e.target.value)}>
            <option value="useful">Useful</option><option value="incorrect">Incorrect</option><option value="inconclusive">Inconclusive</option>
          </select><textarea aria-label="What really happened" className={`${field} w-full`} maxLength={2000} placeholder="Optional: what really happened? Was this a defensive adaptation?" value={note} onChange={e => setNote(e.target.value)} />
          <button className={button} disabled={busy} onClick={() => save({operation: 'feedback', recommendation_id: primary.id, verdict, note})}>Save feedback locally</button>
          <p className="text-xs text-[color:var(--muted)]">A versioned user annotation, separate from parser facts. Feedback does not automatically retune rules.</p></div>
        </details>
      </article> : <div className="mt-4 rounded-lg bg-[color:var(--panel)] p-4"><h3 className="font-semibold">No primary recommendation</h3><p className="mt-1 text-sm">{review.abstention_reason}</p></div>}
      <section className="mt-4"><h3 className="font-bold">What went well</h3>{review.what_went_well.length ? review.what_went_well.map(o => <div key={o.id} className="mt-2 rounded-lg border border-emerald-500/25 p-3"><p className="text-sm">{o.text}</p><details className="mt-2 text-xs"><summary>Recorded evidence · {o.evidence_class}</summary><div className="mt-2 flex flex-wrap gap-2">{evidence(o.event_ids)}</div></details></div>) : <p className="mt-1 text-sm text-[color:var(--muted)]">Not enough decoded milestone evidence to identify a specific positive. No praise is invented.</p>}</section>
      <section className="mt-4"><h3 className="font-bold">What to practice next game</h3>{review.practice_goals.map(goal => <div key={goal.id} className="mt-2 rounded-lg border border-[color:var(--border-subtle)] p-3">
        <p className="font-semibold">{goal.label}</p><p className="mt-1 text-sm">{goal.primary_measure.target}</p><p className="mt-1 text-xs">Supporting metric: {goal.supporting_indicator.name}; this match {goal.supporting_indicator.baseline_seconds.toFixed(1)}s. {goal.supporting_indicator.caveat}</p><p className="mt-1 text-xs">{goal.stop_or_adapt}</p>
        <button className={`${button} mt-2`} disabled={busy || state?.goal?.active} onClick={() => save({operation: 'select_goal'})}>Select this one practice goal</button>
      </div>)}{!review.practice_goals.length && !state?.goal?.active && <p className="mt-1 text-sm text-[color:var(--muted)]">No new goal suggested without an actionable primary.</p>}</section>
      {state?.goal?.active && <details className="mt-4 rounded-lg border border-[color:var(--border-subtle)] p-3"><summary className="text-sm font-semibold">Selected practice goal · {state.evaluations.length} manually logged comparable matches</summary>
        <p className="mt-2 text-sm">{state.goal.label} · baseline {state.goal.baseline_seconds.toFixed(1)}s</p>
        <p className="mt-1 text-xs text-[color:var(--muted)]">Only explicitly reviewed matches, not a library-wide trend. Map, civ, format, plan, duration band and pressure-cue category must match. Unknown aggression is not verified safety. Timing change does not prove improvement or a causal effect of practice.</p>
        {state.evaluations.map(e => <p key={e.match_id} className="mt-2 text-xs">{e.match_id.slice(0, 12)} · check: {e.checklist} · adaptation: {e.adaptation} · {e.metric_status} · {e.interval_seconds ?? 'missing'}s{e.delta_from_baseline_seconds != null ? ` · change ${e.delta_from_baseline_seconds > 0 ? '+' : ''}${e.delta_from_baseline_seconds.toFixed(1)}s` : ''}</p>)}
        {state.goal.baseline_match_id !== analysis.match_id && <div className="mt-3 flex flex-col items-start gap-2">
          <label className="text-sm"><input type="checkbox" checked={after} onChange={e => setAfter(e.target.checked)} /> I played this match after selecting the goal.</label>
          <label className="text-sm">Did the checklist? <select className={field} value={checklist} onChange={e => setChecklist(e.target.value)}><option value="uncertain">Uncertain</option><option value="yes">Yes</option><option value="no">No</option><option value="not_applicable">Not applicable · no Castle transition</option></select></label>
          <label className="text-sm">Defense / changed plan affected the transition? <select className={field} value={adaptation} onChange={e => setAdaptation(e.target.value)}><option value="uncertain">Uncertain</option><option value="yes">Yes</option><option value="no">No</option></select></label>
          <button className={button} disabled={busy || !after} onClick={() => save({operation: 'evaluate_goal', checklist, adaptation, played_after_selection: after})}>Log this practice review</button>
        </div>}
        <button className={`${button} mt-3`} disabled={busy} onClick={() => save({operation: 'stop_goal'})}>Stop this goal</button>
      </details>}
    </>}
    </details>
    {review && <>
      <details className="mt-4 rounded-lg border border-[color:var(--border-subtle)] p-3"><summary className="text-sm font-semibold">Export / share this review</summary>
        <p className="mt-2 text-xs text-[color:var(--muted)]">Exports the previous automatic situation/legacy review only—not situational composition reasoning or its player-reviewed answers, the balanced takeaway, new gameplay checkpoint or its corrections, practice journal, custom focuses, authored reviews, observation batches, screenshots or raw events. Player names are anonymized by default; local paths and match hashes are never included.</p>
        <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={includeNames} onChange={e => setIncludeNames(e.target.checked)} /> Include player names in this export</label>
        <div className="mt-3 flex flex-wrap gap-2"><button className={button} onClick={async () => {
          const markdown = exportMarkdown;
          try { await navigator.clipboard.writeText(markdown); setExportStatus('Copied Markdown to clipboard.'); }
          catch { setExportStatus('Clipboard access was unavailable; use Download Markdown instead.'); }
        }}>Copy Markdown</button><button className={button} onClick={() => {
          const markdown = exportMarkdown;
          const blob = new Blob([markdown], {type: 'text/markdown;charset=utf-8'});
          const url = URL.createObjectURL(blob); const link = document.createElement('a');
          const safeMap = analysis.map.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'match';
          link.href = url; link.download = `aoe2-${safeMap}-coaching-review.md`; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
          setExportStatus('Downloaded Markdown review.');
        }}>Download Markdown</button></div>
        {exportStatus && <p role="status" className="mt-2 text-xs text-[color:var(--muted)]">{exportStatus}</p>}
        <details className="mt-3"><summary className="text-xs">Preview export</summary><pre data-review-export className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-[color:var(--panel)] p-3 text-[11px]">{exportMarkdown}</pre></details>
      </details>
      <details className="mt-4 text-xs text-[color:var(--muted)]"><summary>Legacy detector decisions and priority audit</summary><p className="mt-2">{review.ranking_policy.join(' → ')}. {review.ranking_note}</p>{review.detectors.map(d => <div key={d.rule_id} className="mt-2"><b>{d.rule_id} v{d.rule_version}: {d.status}</b><p>{d.reason}</p><p>Decoded anchors: {String(d.evidence_quality.anchors_reliably_decoded)}; interval anchors complete: {String(d.evidence_quality.complete_for_measure)}; stream: {d.evidence_quality.stream_completeness}. {d.evidence_quality.reason}</p></div>)}</details>
    </>}
  </section>
    {response?.matchup && <details className="panel-strong rounded-xl p-4"><summary className="font-semibold">Optional matchup reference & match-rules declaration</summary><div className="mt-3"><MatchupBriefing analysis={analysis} matchup={response.matchup} rulesContext={state?.rules_context} busy={busy}
      onSaveRules={rules => { void save({operation: 'rules_context', rules}); }} onOpenEvidence={onOpenEvidence} /></div></details>}
  </details></>;
}
